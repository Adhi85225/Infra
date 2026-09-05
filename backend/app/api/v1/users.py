"""User administration endpoints.

Access is governed by the ``ACCESS_MANAGEMENT`` module:

* ``VIEW``   -> list/read users
* ``CREATE`` -> create users        (requires COMPLETE)
* ``UPDATE`` -> edit users / roles  (requires COMPLETE)
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import ActiveUser, DbSession, require_access
from app.models.enums import ModuleAction, UserStatus
from app.schemas.common import Page
from app.schemas.user import (
    AdminPasswordResetResponse,
    UserCreate,
    UserCreateResponse,
    UserRolesUpdate,
    UserSummary,
    UserUpdate,
)
from app.services import user_service
from app.services.email import build_welcome_email, get_email_service

MODULE = "ACCESS_MANAGEMENT"

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=Page[UserSummary],
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="List users",
)
async def list_users(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=200)] = None,
    status: UserStatus | None = None,
    role_key: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserSummary]:
    users, total = await user_service.list_users(
        db, search=search, status=status, role_key=role_key, limit=limit, offset=offset
    )
    return Page[UserSummary](
        items=[UserSummary.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{user_id}",
    response_model=UserSummary,
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="Get a single user",
)
async def get_user(user_id: uuid.UUID, db: DbSession) -> UserSummary:
    return UserSummary.model_validate(await user_service.get_user(db, user_id))


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=201,
    summary="Create a user (admin only)",
)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.CREATE))],
) -> UserCreateResponse:
    created = await user_service.create_user(
        db,
        actor=actor,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role_keys=payload.role_keys,
        status=payload.status,
        job_title=payload.job_title,
        department=payload.department,
        phone=payload.phone,
        request=request,
    )
    await db.commit()
    await db.refresh(created.user)

    delivered = await get_email_service().send(
        build_welcome_email(
            to=created.user.email,
            first_name=created.user.first_name,
            temporary_password=created.temporary_password,
        )
    )

    return UserCreateResponse(
        user=UserSummary.model_validate(created.user),
        temporary_password=created.temporary_password,
        email_delivered=delivered,
    )


@router.patch(
    "/{user_id}",
    response_model=UserSummary,
    summary="Update a user's profile or status",
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> UserSummary:
    user = await user_service.get_user(db, user_id)
    await user_service.update_user(
        db,
        actor=actor,
        user=user,
        first_name=payload.first_name,
        last_name=payload.last_name,
        status=payload.status,
        job_title=payload.job_title,
        department=payload.department,
        phone=payload.phone,
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return UserSummary.model_validate(user)


@router.put(
    "/{user_id}/roles",
    response_model=UserSummary,
    summary="Replace a user's roles",
)
async def set_roles(
    user_id: uuid.UUID,
    payload: UserRolesUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> UserSummary:
    user = await user_service.get_user(db, user_id)
    await user_service.set_user_roles(
        db, actor=actor, user=user, role_keys=payload.role_keys, request=request
    )
    await db.commit()
    await db.refresh(user)
    return UserSummary.model_validate(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=AdminPasswordResetResponse,
    summary="Issue a new temporary password for a user",
)
async def reset_user_password(
    user_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> AdminPasswordResetResponse:
    user = await user_service.get_user(db, user_id)
    temporary_password = await user_service.admin_reset_password(
        db, actor=actor, user=user, request=request
    )
    await db.commit()

    delivered = await get_email_service().send(
        build_welcome_email(
            to=user.email, first_name=user.first_name, temporary_password=temporary_password
        )
    )
    return AdminPasswordResetResponse(
        temporary_password=temporary_password, email_delivered=delivered
    )
