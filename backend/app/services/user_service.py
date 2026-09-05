"""User administration.

There is no public self-registration: accounts are always created by an
authorized administrator, always start with a generated temporary password, and
are always flagged ``must_change_password``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.security import generate_temporary_password, hash_password
from app.models.enums import AuditAction, UserStatus
from app.models.user import Role, User, UserRole
from app.modules.registry import ROLE_SUPER_ADMIN
from app.services import audit_service, permission_service


@dataclass
class CreatedUser:
    user: User
    temporary_password: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found.")
    return user


async def list_users(
    db: AsyncSession,
    *,
    search: str | None = None,
    status: UserStatus | None = None,
    role_key: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[User], int]:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if search:
        pattern = f"%{search.strip().lower()}%"
        condition = or_(
            func.lower(User.email).like(pattern),
            func.lower(User.first_name).like(pattern),
            func.lower(User.last_name).like(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    if status:
        stmt = stmt.where(User.status == status)
        count_stmt = count_stmt.where(User.status == status)

    if role_key:
        subquery = (
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.key == role_key)
        )
        stmt = stmt.where(User.id.in_(subquery))
        count_stmt = count_stmt.where(User.id.in_(subquery))

    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        await db.execute(
            stmt.order_by(User.first_name, User.last_name).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def _resolve_roles(db: AsyncSession, role_keys: list[str]) -> list[Role]:
    if not role_keys:
        return []
    roles = (
        await db.execute(select(Role).where(Role.key.in_(role_keys)))
    ).scalars().all()
    missing = set(role_keys) - {role.key for role in roles}
    if missing:
        raise ValidationError(
            "One or more roles do not exist.", details={"roles": sorted(missing)}
        )
    return list(roles)


async def _assert_may_grant(db: AsyncSession, actor: User, roles: list[Role]) -> None:
    """Authorise handing out ``roles``.

    Two rules, both aimed at privilege escalation:

    1. Only a Super Admin may hand out the Super Admin role.
    2. A non-superuser may not assign a role that grants more access than they
       hold themselves -- otherwise anyone with COMPLETE on Access Management
       could grant a confederate a role far more powerful than their own.
    """
    if any(role.key == ROLE_SUPER_ADMIN for role in roles) and not actor.is_superuser:
        raise PermissionDeniedError("Only a Super Admin can assign the Super Admin role.")

    if actor.is_superuser or not roles:
        return

    from app.services import role_service

    for role in roles:
        matrix = await role_service.get_role_matrix(db, role)
        await role_service._assert_may_grant_levels(db, actor, matrix)


def _assert_not_self(actor: User, user: User) -> None:
    """Nobody edits their own role assignments.

    Self-assignment is the most direct escalation path there is, and an
    administrator legitimately changing their own roles is rare enough that
    requiring a second administrator is the right trade-off.
    """
    if user.id == actor.id:
        raise PermissionDeniedError(
            "You cannot change your own roles. Ask another administrator.",
            code="self_role_change_denied",
        )


async def create_user(
    db: AsyncSession,
    *,
    actor: User,
    email: str,
    first_name: str,
    last_name: str,
    role_keys: list[str],
    status: UserStatus = UserStatus.ACTIVE,
    job_title: str | None = None,
    department: str | None = None,
    phone: str | None = None,
    request: Request | None = None,
) -> CreatedUser:
    normalized = normalize_email(email)

    existing = (
        await db.execute(select(User).where(User.email == normalized))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            "A user with this email address already exists.",
            code="email_taken",
            details={"email": ["Already in use."]},
        )

    roles = await _resolve_roles(db, role_keys)
    await _assert_may_grant(db, actor, roles)

    temporary_password = generate_temporary_password()
    user = User(
        email=normalized,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        password_hash=hash_password(temporary_password),
        status=status,
        must_change_password=True,
        job_title=job_title,
        department=department,
        phone=phone,
        created_by_id=actor.id,
    )
    db.add(user)
    await db.flush()

    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id, assigned_by_id=actor.id))

    await audit_service.record(
        db,
        AuditAction.USER_CREATED,
        actor=actor,
        entity_type="user",
        entity_id=user.id,
        context={"email": normalized, "roles": [role.key for role in roles], "status": status.value},
        request=request,
    )
    await db.flush()
    await db.refresh(user)
    return CreatedUser(user=user, temporary_password=temporary_password)


async def update_user(
    db: AsyncSession,
    *,
    actor: User,
    user: User,
    first_name: str | None = None,
    last_name: str | None = None,
    status: UserStatus | None = None,
    job_title: str | None = None,
    department: str | None = None,
    phone: str | None = None,
    request: Request | None = None,
) -> User:
    changes: dict[str, object] = {}

    if first_name is not None and first_name.strip() != user.first_name:
        changes["first_name"] = first_name.strip()
        user.first_name = first_name.strip()
    if last_name is not None and last_name.strip() != user.last_name:
        changes["last_name"] = last_name.strip()
        user.last_name = last_name.strip()
    for field, value in (("job_title", job_title), ("department", department), ("phone", phone)):
        if value is not None and getattr(user, field) != value:
            changes[field] = value
            setattr(user, field, value)

    if status is not None and UserStatus(user.status) != status:
        if user.id == actor.id:
            raise ValidationError("You cannot change your own account status.")
        if user.is_superuser and not actor.is_superuser:
            raise PermissionDeniedError("Only a Super Admin can modify a Super Admin account.")
        changes["status"] = status.value
        user.status = status
        await audit_service.record(
            db,
            AuditAction.USER_STATUS_CHANGED,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            context={"status": status.value},
            request=request,
        )
        if not status.can_authenticate:
            from app.services import auth_service

            await auth_service.revoke_all_sessions(db, user.id, "status_changed")

    if changes:
        await audit_service.record(
            db,
            AuditAction.USER_UPDATED,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            context={"changes": changes},
            request=request,
        )
    return user


async def set_user_roles(
    db: AsyncSession,
    *,
    actor: User,
    user: User,
    role_keys: list[str],
    request: Request | None = None,
) -> User:
    _assert_not_self(actor, user)

    roles = await _resolve_roles(db, role_keys)
    await _assert_may_grant(db, actor, roles)

    if user.is_superuser and not actor.is_superuser:
        raise PermissionDeniedError("Only a Super Admin can modify a Super Admin account.")

    previous = sorted(role.key for role in user.roles)

    for assignment in list(user.user_roles):
        await db.delete(assignment)
    await db.flush()

    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id, assigned_by_id=actor.id))

    await audit_service.record(
        db,
        AuditAction.USER_ROLES_CHANGED,
        actor=actor,
        entity_type="user",
        entity_id=user.id,
        context={"from": previous, "to": sorted(role.key for role in roles)},
        request=request,
    )
    await permission_service.invalidate_user_cache(user.id)
    await db.flush()
    await db.refresh(user)
    return user


async def admin_reset_password(
    db: AsyncSession, *, actor: User, user: User, request: Request | None = None
) -> str:
    """Issue a new temporary password and force a change at next sign-in."""
    from app.services import auth_service

    if user.is_superuser and not actor.is_superuser:
        raise PermissionDeniedError("Only a Super Admin can reset a Super Admin password.")

    temporary_password = generate_temporary_password()
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.failed_login_count = 0
    user.locked_until = None

    await auth_service.revoke_all_sessions(db, user.id, "admin_password_reset")
    await audit_service.record(
        db,
        AuditAction.ADMIN_PASSWORD_RESET,
        actor=actor,
        entity_type="user",
        entity_id=user.id,
        request=request,
    )
    return temporary_password
