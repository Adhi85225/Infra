"""Task-update endpoints.

Access is governed by the ``TASK_UPDATES`` module:

* ``VIEW``   -> list/read tasks
* ``CREATE`` -> add a task
* ``UPDATE`` -> edit a task (own tasks only, unless the caller is a task admin)

Whose tasks a caller may see, and which of them they may edit, is decided in
:mod:`app.services.task_service` -- never here and never by the client.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import ActiveUser, DbSession, require_access
from app.models.enums import ModuleAction, TaskService, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.schemas.common import Page
from app.schemas.task import TaskCreate, TaskOptions, TaskSummary, TaskUpdate
from app.services import task_service

MODULE = task_service.MODULE

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _summary(task: Task, *, viewer: User, admin: bool) -> TaskSummary:
    """Serialise a task, resolving the caller's edit right for that row."""
    return TaskSummary(
        id=task.id,
        task_date=task.task_date,
        reference_number=task.reference_number,
        site_name=task.site_name,
        description=task.description,
        status=TaskStatus(task.status),
        remarks=task.remarks,
        service=TaskService(task.service),
        user_id=task.user_id,
        user_name=task.user.full_name if task.user else "",
        user_email=task.user.email if task.user else "",
        created_at=task.created_at,
        updated_at=task.updated_at,
        can_edit=task_service.can_edit(task, viewer=viewer, admin=admin),
    )


@router.get(
    "/options",
    response_model=TaskOptions,
    dependencies=[Depends(require_access(MODULE, ModuleAction.VIEW))],
    summary="Service (D1) and status (D2) dropdown options",
)
async def get_options() -> TaskOptions:
    services, statuses = task_service.options()
    return TaskOptions(services=services, statuses=statuses)


@router.get(
    "",
    response_model=Page[TaskSummary],
    summary="List task updates",
)
async def list_tasks(
    db: DbSession,
    viewer: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.VIEW))],
    service: TaskService | None = None,
    user_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort_by: Annotated[str, Query(max_length=64)] = task_service.DEFAULT_SORT,
    direction: Annotated[str, Query(pattern="^(asc|desc)$")] = task_service.DEFAULT_DIRECTION,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TaskSummary]:
    """Tasks matching the filters.

    Omitting ``service`` is the global Task Updates view: every task, whoever
    owns it. Supplying one is a service page, where a caller without
    administrative access is silently restricted to their own rows.
    """
    admin = await task_service.is_task_admin(db, viewer)
    tasks, total = await task_service.list_tasks(
        db,
        viewer=viewer,
        admin=admin,
        service=service,
        user_id=user_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        direction=direction,
        limit=limit,
        offset=offset,
    )
    return Page[TaskSummary](
        items=[_summary(task, viewer=viewer, admin=admin) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{task_id}",
    response_model=TaskSummary,
    summary="Get a single task",
)
async def get_task(
    task_id: uuid.UUID,
    db: DbSession,
    viewer: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.VIEW))],
) -> TaskSummary:
    # Readable by anyone who can view the module: the global page already shows
    # every task, so a per-row read restriction here would protect nothing.
    task = await task_service.get_task(db, task_id)
    admin = await task_service.is_task_admin(db, viewer)
    return _summary(task, viewer=viewer, admin=admin)


@router.post(
    "",
    response_model=TaskSummary,
    status_code=201,
    summary="Add a task",
)
async def create_task(
    payload: TaskCreate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.CREATE))],
) -> TaskSummary:
    admin = await task_service.is_task_admin(db, actor)
    task = await task_service.create_task(
        db,
        actor=actor,
        admin=admin,
        task_date=payload.task_date,
        description=payload.description,
        service=payload.service,
        status=payload.status,
        reference_number=payload.reference_number,
        site_name=payload.site_name,
        remarks=payload.remarks,
        user_id=payload.user_id,
        request=request,
    )
    await db.commit()
    created = await task_service.get_task(db, task.id)
    return _summary(created, viewer=actor, admin=admin)


@router.patch(
    "/{task_id}",
    response_model=TaskSummary,
    summary="Edit a task",
)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[ActiveUser, Depends(require_access(MODULE, ModuleAction.UPDATE))],
) -> TaskSummary:
    task = await task_service.get_task(db, task_id)
    admin = await task_service.is_task_admin(db, actor)
    await task_service.update_task(
        db,
        actor=actor,
        admin=admin,
        task=task,
        # exclude_unset so "not sent" and "explicitly cleared" stay distinct.
        changes=payload.model_dump(exclude_unset=True),
        request=request,
    )
    await db.commit()
    updated = await task_service.get_task(db, task_id)
    return _summary(updated, viewer=actor, admin=admin)
