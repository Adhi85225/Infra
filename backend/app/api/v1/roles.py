"""Role and permission-matrix endpoints.

Role management is governed by the ``ACCESS_MANAGEMENT`` module, like every
other administrative capability:

* ``VIEW``   -> list and inspect roles
* ``CREATE`` -> create a role
* ``UPDATE`` -> edit a role, its permissions, or delete it

On top of the module permission, :mod:`app.services.role_service` applies two
further rules: seeded roles are protected, and nobody may grant a role more
access than they hold themselves.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import ActiveUser, DbSession, require_access
from app.models.enums import ASSIGNABLE_ACCESS_LEVELS, ModuleAction
from app.models.user import Role
from app.schemas.common import Message
from app.schemas.user import (
    ModuleSummary,
    RoleCreate,
    RolePermissionsUpdate,
    RoleSummary,
    RoleUpdate,
    RoleWithPermissions,
)
from app.services import role_service

MODULE = "ACCESS_MANAGEMENT"

router = APIRouter(tags=["Roles & Modules"])


def _summary(role: Role, user_counts: dict[uuid.UUID, int]) -> RoleSummary:
    summary = RoleSummary.model_validate(role)
    summary.user_count = user_counts.get(role.id, 0)
    summary.is_deletable = not role.is_system and role.key not in role_service.PROTECTED_ROLE_KEYS
    return summary


@router.get(
    "/roles",
    response_model=list[RoleSummary],
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="List roles",
)
async def list_roles(db: DbSession) -> list[RoleSummary]:
    roles = await role_service.list_roles(db)
    counts = await role_service.count_users_per_role(db)
    return [_summary(role, counts) for role in roles]


@router.get(
    "/roles/assignable-access-levels",
    response_model=list[str],
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="Access levels that may be assigned to a role",
)
async def assignable_access_levels() -> list[str]:
    """Published so the UI never hard-codes the list of levels."""
    return [level.value for level in ASSIGNABLE_ACCESS_LEVELS]


@router.get(
    "/roles/{role_id}",
    response_model=RoleWithPermissions,
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="Get a role with its module permission matrix",
)
async def get_role(role_id: uuid.UUID, db: DbSession) -> RoleWithPermissions:
    role = await role_service.get_role(db, role_id)
    matrix = await role_service.get_role_matrix(db, role)
    counts = await role_service.count_users_per_role(db)
    return RoleWithPermissions(**_summary(role, counts).model_dump(), permissions=matrix)


@router.post(
    "/roles",
    response_model=RoleWithPermissions,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom role",
)
async def create_role(
    payload: RoleCreate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.CREATE))],
) -> RoleWithPermissions:
    role = await role_service.create_role(
        db,
        actor=actor,
        name=payload.name,
        description=payload.description,
        key=payload.key,
        permissions=payload.permissions,
        sort_order=payload.sort_order,
        request=request,
    )
    await db.commit()

    matrix = await role_service.get_role_matrix(db, role)
    counts = await role_service.count_users_per_role(db)
    return RoleWithPermissions(**_summary(role, counts).model_dump(), permissions=matrix)


@router.patch(
    "/roles/{role_id}",
    response_model=RoleWithPermissions,
    summary="Update a role's name or description",
)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> RoleWithPermissions:
    role = await role_service.get_role(db, role_id)
    await role_service.update_role(
        db,
        actor=actor,
        role=role,
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
        request=request,
    )
    await db.commit()

    matrix = await role_service.get_role_matrix(db, role)
    counts = await role_service.count_users_per_role(db)
    return RoleWithPermissions(**_summary(role, counts).model_dump(), permissions=matrix)


@router.delete(
    "/roles/{role_id}",
    response_model=Message,
    summary="Delete a custom role",
)
async def delete_role(
    role_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> Message:
    role = await role_service.get_role(db, role_id)
    await role_service.delete_role(db, actor=actor, role=role, request=request)
    await db.commit()
    return Message(message="Role deleted.")


@router.put(
    "/roles/{role_id}/permissions",
    response_model=RoleWithPermissions,
    summary="Replace a role's module permissions",
)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> RoleWithPermissions:
    role = await role_service.get_role(db, role_id)
    matrix = await role_service.set_role_permissions(
        db, actor=actor, role=role, permissions=payload.permissions, request=request
    )
    await db.commit()

    counts = await role_service.count_users_per_role(db)
    return RoleWithPermissions(**_summary(role, counts).model_dump(), permissions=matrix)


@router.get(
    "/modules",
    response_model=list[ModuleSummary],
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="List all modules in the platform catalogue",
)
async def list_modules(db: DbSession, include_inactive: bool = False) -> list[ModuleSummary]:
    modules = await role_service.list_modules(db, include_inactive=include_inactive)
    return [ModuleSummary.model_validate(module) for module in modules]
