"""Role and role-permission administration."""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import re

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models.enums import AccessLevel, AuditAction, access_rank
from app.models.module import Module
from app.models.permission import RoleModulePermission
from app.models.user import Role, User, UserRole
from app.services import audit_service, permission_service

# Machine keys are uppercase and underscore-separated, e.g. ASSET_MANAGER.
_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")

#: Seeded roles the platform depends on. Protected from deletion and re-keying.
PROTECTED_ROLE_KEYS = frozenset({"SUPER_ADMIN", "ADMIN", "USER", "GUEST"})


async def list_roles(db: AsyncSession) -> list[Role]:
    return list(
        (await db.execute(select(Role).order_by(Role.sort_order, Role.name))).scalars().all()
    )


async def count_users_per_role(db: AsyncSession) -> dict[uuid.UUID, int]:
    """How many users hold each role. Shown in the UI and used to guard deletes."""
    from sqlalchemy import func

    rows = await db.execute(
        select(UserRole.role_id, func.count(UserRole.user_id)).group_by(UserRole.role_id)
    )
    return {role_id: int(count) for role_id, count in rows.all()}


def derive_key(name: str) -> str:
    """Turn a display name into a machine key: 'Asset Manager' -> ASSET_MANAGER."""
    key = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return re.sub(r"_{2,}", "_", key)


async def get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if role is None:
        raise NotFoundError("Role not found.")
    return role


async def _grants_for(db: AsyncSession, role: Role) -> dict[uuid.UUID, RoleModulePermission]:
    """Current grant rows for ``role``, keyed by module id.

    Queried directly rather than through ``role.module_permissions``: that
    relationship is expired by ``commit()``/``refresh()``, and touching an
    expired lazy attribute under asyncio raises ``MissingGreenlet``.
    """
    rows = (
        await db.execute(
            select(RoleModulePermission).where(RoleModulePermission.role_id == role.id)
        )
    ).scalars().all()
    return {row.module_id: row for row in rows}


async def get_role_matrix(db: AsyncSession, role: Role) -> dict[str, AccessLevel]:
    """Access level this role grants on every active module (``NONE`` if unset)."""
    modules = (
        await db.execute(
            select(Module).where(Module.is_active.is_(True)).order_by(Module.sort_order)
        )
    ).scalars().all()
    if role.is_superuser:
        return {module.key: AccessLevel.COMPLETE for module in modules}

    granted = {
        module_id: AccessLevel(row.access_level)
        for module_id, row in (await _grants_for(db, role)).items()
    }
    return {module.key: granted.get(module.id, AccessLevel.NONE) for module in modules}


async def _assert_modules_exist(db: AsyncSession, module_keys: list[str]) -> None:
    """Reject unknown module keys before any authorisation reasoning.

    Checked first so a typo reports "no such module" rather than the escalation
    guard's "you cannot grant that", which would be misleading.
    """
    if not module_keys:
        return
    known = (
        await db.execute(select(Module.key).where(Module.key.in_(module_keys)))
    ).scalars().all()
    missing = set(module_keys) - set(known)
    if missing:
        raise ValidationError(
            "One or more modules do not exist.", details={"modules": sorted(missing)}
        )


async def _assert_may_grant_levels(
    db: AsyncSession, actor: User, permissions: dict[str, AccessLevel]
) -> None:
    """Refuse to let a non-superuser mint access they do not themselves hold.

    Without this, anyone with COMPLETE on Access Management could create a role
    granting COMPLETE on every module and assign it to a confederate -- a
    straightforward privilege-escalation path. A Super Admin is exempt because
    they already hold everything.
    """
    if actor.is_superuser:
        return

    actor_permissions = await permission_service.resolve_permissions(db, actor)
    over_reach: dict[str, str] = {}

    for module_key, level in permissions.items():
        held = actor_permissions.get(module_key)
        held_level = held.access_level if held else AccessLevel.NONE
        if access_rank(level) > access_rank(held_level):
            over_reach[module_key] = f"you hold {held_level.value}, cannot grant {level.value}"

    if over_reach:
        raise PermissionDeniedError(
            "You cannot grant a role more access than you have yourself.",
            details={"modules": over_reach},
        )


def _assert_role_editable(actor: User, role: Role) -> None:
    """Shared guard for every mutation of an existing role."""
    if role.is_superuser:
        raise ValidationError(
            "Super Admin permissions are implicit and cannot be edited.",
            code="role_immutable",
        )
    if not actor.is_superuser and role.key == "ADMIN":
        raise PermissionDeniedError("Only a Super Admin can change the Admin role.")


async def create_role(
    db: AsyncSession,
    *,
    actor: User,
    name: str,
    description: str | None = None,
    key: str | None = None,
    permissions: dict[str, AccessLevel] | None = None,
    sort_order: int = 500,
    request: Request | None = None,
) -> Role:
    """Create a custom role, optionally with its module permissions."""
    name = name.strip()
    if not name:
        raise ValidationError("A role name is required.", details={"name": ["Required."]})

    resolved_key = (key or derive_key(name)).strip().upper()
    if not _KEY_PATTERN.match(resolved_key):
        raise ValidationError(
            "The role key must be 2-64 characters, uppercase letters, digits and underscores.",
            details={"key": ["Invalid format."]},
        )

    existing = (
        await db.execute(select(Role).where(Role.key == resolved_key))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            "A role with this key already exists.",
            code="role_key_taken",
            details={"key": ["Already in use."]},
        )

    grants = permissions or {}
    await _assert_modules_exist(db, list(grants))
    await _assert_may_grant_levels(db, actor, grants)

    role = Role(
        key=resolved_key,
        name=name,
        description=(description or "").strip() or None,
        # Custom roles are never system roles, so they stay deletable.
        is_system=False,
        is_superuser=False,
        sort_order=sort_order,
    )
    db.add(role)
    await db.flush()

    await audit_service.record(
        db,
        AuditAction.ROLE_CREATED,
        actor=actor,
        entity_type="role",
        entity_id=role.id,
        context={"key": role.key, "name": role.name},
        request=request,
    )

    if grants:
        await _apply_permissions(db, actor=actor, role=role, permissions=grants, request=request)

    await db.flush()
    return role


async def update_role(
    db: AsyncSession,
    *,
    actor: User,
    role: Role,
    name: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    request: Request | None = None,
) -> Role:
    """Update a role's descriptive metadata. The key is immutable."""
    _assert_role_editable(actor, role)

    changes: dict[str, object] = {}
    if name is not None and name.strip() and name.strip() != role.name:
        changes["name"] = name.strip()
        role.name = name.strip()
    if description is not None:
        cleaned = description.strip() or None
        if cleaned != role.description:
            changes["description"] = cleaned
            role.description = cleaned
    if sort_order is not None and sort_order != role.sort_order:
        changes["sort_order"] = sort_order
        role.sort_order = sort_order

    if changes:
        await audit_service.record(
            db,
            AuditAction.ROLE_UPDATED,
            actor=actor,
            entity_type="role",
            entity_id=role.id,
            context={"key": role.key, "changes": changes},
            request=request,
        )
    await db.flush()
    return role


async def delete_role(
    db: AsyncSession, *, actor: User, role: Role, request: Request | None = None
) -> None:
    """Delete a custom role.

    Seeded roles are protected, and a role that is still assigned is refused
    rather than silently stripping access from its holders.
    """
    if role.is_system or role.key in PROTECTED_ROLE_KEYS:
        raise ValidationError(
            "System roles cannot be deleted.",
            code="role_protected",
            details={"role": role.key},
        )
    if not actor.is_superuser:
        # Deleting a role revokes access for everyone holding it; keep that
        # under the same bar as editing the Admin role.
        await _assert_may_grant_levels(db, actor, await get_role_matrix(db, role))

    assigned = (await count_users_per_role(db)).get(role.id, 0)
    if assigned:
        raise ConflictError(
            f"This role is still assigned to {assigned} user(s). Reassign them first.",
            code="role_in_use",
            details={"user_count": assigned},
        )

    await audit_service.record(
        db,
        AuditAction.ROLE_DELETED,
        actor=actor,
        entity_type="role",
        entity_id=role.id,
        context={"key": role.key, "name": role.name},
        request=request,
    )
    await db.delete(role)
    await db.flush()


async def _apply_permissions(
    db: AsyncSession,
    *,
    actor: User,
    role: Role,
    permissions: dict[str, AccessLevel],
    request: Request | None = None,
) -> dict[str, str]:
    """Write grant rows for ``role``. Assumes callers have already authorised."""
    modules = (
        await db.execute(select(Module).where(Module.key.in_(list(permissions.keys()))))
    ).scalars().all()
    by_key = {module.key: module for module in modules}

    missing = set(permissions) - set(by_key)
    if missing:
        raise ValidationError(
            "One or more modules do not exist.", details={"modules": sorted(missing)}
        )

    existing = await _grants_for(db, role)
    changes: dict[str, str] = {}

    for module_key, level in permissions.items():
        module = by_key[module_key]
        row = existing.get(module.id)
        if level is AccessLevel.NONE:
            if row is not None:
                changes[module_key] = AccessLevel.NONE.value
                await db.delete(row)
            continue
        if row is None:
            db.add(RoleModulePermission(role_id=role.id, module_id=module.id, access_level=level))
            changes[module_key] = level.value
        elif AccessLevel(row.access_level) is not level:
            row.access_level = level
            changes[module_key] = level.value

    if changes:
        await audit_service.record(
            db,
            AuditAction.ROLE_PERMISSIONS_CHANGED,
            actor=actor,
            entity_type="role",
            entity_id=role.id,
            context={"role": role.key, "changes": changes},
            request=request,
        )
        await permission_service.invalidate_role_cache(db, role.id)

    return changes


async def set_role_permissions(
    db: AsyncSession,
    *,
    actor: User,
    role: Role,
    permissions: dict[str, AccessLevel],
    request: Request | None = None,
) -> dict[str, AccessLevel]:
    """Replace the grants for ``role`` on the supplied module keys."""
    _assert_role_editable(actor, role)
    await _assert_modules_exist(db, list(permissions))
    await _assert_may_grant_levels(db, actor, permissions)

    await _apply_permissions(db, actor=actor, role=role, permissions=permissions, request=request)

    await db.flush()
    return await get_role_matrix(db, role)


async def list_modules(db: AsyncSession, *, include_inactive: bool = False) -> list[Module]:
    stmt = select(Module).order_by(Module.sort_order, Module.name)
    if not include_inactive:
        stmt = stmt.where(Module.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())
