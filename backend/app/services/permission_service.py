"""Centralised authorization.

**This module is the only place that decides what a user may do.**  Endpoints
ask it a question; they never re-derive permissions themselves, and the frontend
renders from the map it produces.  Development Rule 3 ("do not duplicate
authorization logic") is enforced by keeping every rule here.

Resolution algorithm
--------------------
1. If any of the user's roles is flagged ``is_superuser``, every active module
   resolves to ``COMPLETE`` -- including modules that do not exist yet.
2. Otherwise, collect the ``RoleModulePermission`` rows for all of the user's
   roles and take the **highest** access level per module.  A module with no
   matching row resolves to ``NONE``.
3. Inactive modules always resolve to ``NONE``.

The result is cached briefly in Redis and invalidated explicitly whenever roles
or role permissions change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError
from app.core.redis import safe_call
from app.models.enums import AccessLevel, ModuleAction, highest, level_allows
from app.models.module import Module
from app.models.permission import RoleModulePermission
from app.models.user import User

_CACHE_PREFIX = "perms:v1:"
_CACHE_TTL_SECONDS = 60


@dataclass(frozen=True)
class EffectivePermission:
    module_key: str
    module_name: str
    icon: str | None
    route: str
    description: str | None
    sort_order: int
    is_implemented: bool
    access_level: AccessLevel

    @property
    def can_view(self) -> bool:
        return level_allows(self.access_level, ModuleAction.VIEW)

    @property
    def can_manage(self) -> bool:
        return level_allows(self.access_level, ModuleAction.MANAGE)

    def to_dict(self) -> dict[str, object]:
        return {
            "module_key": self.module_key,
            "module_name": self.module_name,
            "icon": self.icon,
            "route": self.route,
            "description": self.description,
            "sort_order": self.sort_order,
            "is_implemented": self.is_implemented,
            "access_level": self.access_level.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EffectivePermission":
        return cls(
            module_key=data["module_key"],
            module_name=data["module_name"],
            icon=data["icon"],
            route=data["route"],
            description=data["description"],
            sort_order=data["sort_order"],
            is_implemented=data["is_implemented"],
            access_level=AccessLevel(data["access_level"]),
        )


PermissionMap = dict[str, EffectivePermission]


async def resolve_permissions(
    db: AsyncSession, user: User, *, use_cache: bool = True
) -> PermissionMap:
    """Return the user's effective access level for every active module."""
    if use_cache:
        cached = await safe_call("get", f"{_CACHE_PREFIX}{user.id}")
        if cached:
            try:
                return {
                    key: EffectivePermission.from_dict(value)
                    for key, value in json.loads(cached).items()
                }
            except (ValueError, KeyError):
                pass  # Malformed cache entry; fall through and recompute.

    modules = (
        await db.execute(
            select(Module).where(Module.is_active.is_(True)).order_by(Module.sort_order, Module.name)
        )
    ).scalars().all()

    is_superuser = user.is_superuser
    grants: dict[UUID, list[AccessLevel]] = {}

    if not is_superuser:
        role_ids = [assignment.role_id for assignment in user.user_roles]
        if role_ids:
            rows = (
                await db.execute(
                    select(RoleModulePermission).where(
                        RoleModulePermission.role_id.in_(role_ids)
                    )
                )
            ).scalars().all()
            for row in rows:
                grants.setdefault(row.module_id, []).append(AccessLevel(row.access_level))

    permissions: PermissionMap = {}
    for module in modules:
        if is_superuser:
            level = AccessLevel.COMPLETE
        else:
            level = highest(*grants.get(module.id, []))
        permissions[module.key] = EffectivePermission(
            module_key=module.key,
            module_name=module.name,
            icon=module.icon,
            route=module.route,
            description=module.description,
            sort_order=module.sort_order,
            is_implemented=module.is_implemented,
            access_level=level,
        )

    if use_cache:
        await safe_call(
            "setex",
            f"{_CACHE_PREFIX}{user.id}",
            _CACHE_TTL_SECONDS,
            json.dumps({key: value.to_dict() for key, value in permissions.items()}),
        )

    return permissions


async def get_access_level(db: AsyncSession, user: User, module_key: str) -> AccessLevel:
    permissions = await resolve_permissions(db, user)
    permission = permissions.get(module_key)
    return permission.access_level if permission else AccessLevel.NONE


async def has_permission(
    db: AsyncSession, user: User, module_key: str, action: ModuleAction
) -> bool:
    level = await get_access_level(db, user, module_key)
    return level_allows(level, action)


async def require_permission(
    db: AsyncSession, user: User, module_key: str, action: ModuleAction
) -> AccessLevel:
    """Raise :class:`PermissionDeniedError` unless the user may perform ``action``."""
    level = await get_access_level(db, user, module_key)
    if not level_allows(level, action):
        raise PermissionDeniedError(
            f"You do not have permission to {action.value.lower()} in this module.",
            details={"module": module_key, "required_action": action.value, "your_access": level.value},
        )
    return level


async def invalidate_user_cache(user_id: UUID) -> None:
    await safe_call("delete", f"{_CACHE_PREFIX}{user_id}")


async def invalidate_role_cache(db: AsyncSession, role_id: UUID) -> None:
    """Drop cached permissions for every user holding ``role_id``."""
    from app.models.user import UserRole  # local import avoids a cycle

    user_ids = (
        await db.execute(select(UserRole.user_id).where(UserRole.role_id == role_id))
    ).scalars().all()
    for user_id in user_ids:
        await invalidate_user_cache(user_id)


async def invalidate_all_caches() -> None:
    """Used after bulk permission changes (e.g. module sync)."""
    keys = await safe_call("keys", f"{_CACHE_PREFIX}*")
    if keys:
        await safe_call("delete", *keys)
