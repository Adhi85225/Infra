"""Task updates: listing, creation and editing.

Visibility model
----------------
Two questions are kept apart, because the requirements answer them differently:

*What may I do?*  -- the ``TASK_UPDATES`` module access level, resolved by
:mod:`app.services.permission_service` exactly like every other module.  VIEW
opens the pages, CREATE adds a task, UPDATE edits one.

*Whose tasks?*  -- ``MANAGE`` on ``ACCESS_MANAGEMENT``.  A caller holding it is a
*task administrator*: they see and edit everybody's tasks and may filter by
user.  Everyone else is scoped to their own rows on the service pages.

Access level alone cannot express this, because no level grants CREATE/UPDATE
without also granting MANAGE.  Reusing the Access Management grant keeps the
rule inside the existing model -- an operator can hand task oversight to a
custom role by editing that role's permissions, with no code change.

The one deliberate exception is the global **Task Updates** page: it lists every
task regardless of owner, for every caller who can view the module.  That is a
stated requirement, and it is expressed here by ``service=None`` meaning
"unscoped".
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import Request
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.models.enums import AuditAction, ModuleAction, TaskService, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.services import audit_service, permission_service

#: Module governing the task pages themselves.
MODULE = "TASK_UPDATES"

#: Holding MANAGE here makes a caller a task administrator. See the module
#: docstring for why this is not simply COMPLETE on TASK_UPDATES.
ADMIN_MODULE = "ACCESS_MANAGEMENT"

#: Columns a client may sort by, mapped to what that means in SQL.
#:
#: A whitelist rather than free-form input: the value reaches ``ORDER BY``.
#: "Sl. No." is absent deliberately -- it is the row's position in the current
#: result, not stored data, so it cannot be sorted on.
SORTABLE: dict[str, tuple] = {
    "task_date": (Task.task_date,),
    "reference_number": (Task.reference_number,),
    "site_name": (Task.site_name,),
    "description": (Task.description,),
    "status": (Task.status,),
    "remarks": (Task.remarks,),
    "service": (Task.service,),
    "user": (User.first_name, User.last_name),
}

DEFAULT_SORT = "task_date"
DEFAULT_DIRECTION = "desc"


async def is_task_admin(db: AsyncSession, user: User) -> bool:
    """Whether ``user`` may see and edit other people's tasks."""
    return await permission_service.has_permission(db, user, ADMIN_MODULE, ModuleAction.MANAGE)


def _apply_filters(
    stmt: Select,
    *,
    service: TaskService | None,
    user_id: uuid.UUID | None,
    status: TaskStatus | None,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
) -> Select:
    if service is not None:
        stmt = stmt.where(Task.service == service)
    if user_id is not None:
        stmt = stmt.where(Task.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if date_from is not None:
        stmt = stmt.where(Task.task_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Task.task_date <= date_to)

    if search and search.strip():
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Task.reference_number).like(pattern),
                func.lower(Task.site_name).like(pattern),
                func.lower(Task.description).like(pattern),
                func.lower(Task.remarks).like(pattern),
                func.lower(Task.service).like(pattern),
                func.lower(Task.status).like(pattern),
                func.lower(User.first_name).like(pattern),
                func.lower(User.last_name).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )
    return stmt


def resolve_scope(
    *,
    viewer: User,
    admin: bool,
    service: TaskService | None,
    requested_user_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Decide which owner's rows the caller may see.

    Returns the ``user_id`` to filter on, or ``None`` for "every user".

    * No service -> the global Task Updates page, which shows every task to
      everybody. A requested user filter is still honoured.
    * A service  -> a service page. Administrators see everyone (or one chosen
      user); everyone else is pinned to their own rows, whatever they asked for.
    """
    if service is None:
        return requested_user_id
    if admin:
        return requested_user_id
    return viewer.id


async def list_tasks(
    db: AsyncSession,
    *,
    viewer: User,
    admin: bool,
    service: TaskService | None = None,
    user_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    sort_by: str = DEFAULT_SORT,
    direction: str = DEFAULT_DIRECTION,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Task], int]:
    if sort_by not in SORTABLE:
        raise ValidationError(
            "Unknown sort column.",
            details={"sort_by": f"Must be one of: {', '.join(sorted(SORTABLE))}."},
        )
    if direction not in ("asc", "desc"):
        raise ValidationError(
            "Unknown sort direction.", details={"direction": "Must be 'asc' or 'desc'."}
        )

    scoped_user_id = resolve_scope(
        viewer=viewer, admin=admin, service=service, requested_user_id=user_id
    )

    filters = {
        "service": service,
        "user_id": scoped_user_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "search": search,
    }

    # Joined rather than lazily loaded: the User columns are needed for both the
    # search predicate and the "sort by user" case.
    stmt = _apply_filters(select(Task).join(User, User.id == Task.user_id), **filters)
    count_stmt = _apply_filters(
        select(func.count()).select_from(Task).join(User, User.id == Task.user_id), **filters
    )

    columns = SORTABLE[sort_by]
    ordering = [column.desc() if direction == "desc" else column.asc() for column in columns]
    # A stable tiebreaker, so paging through equal values cannot repeat or skip
    # a row between requests.
    ordering.append(Task.id.desc())

    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        (
            await db.execute(
                stmt.options(selectinload(Task.user))
                .order_by(*ordering)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return list(rows), total


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task:
    task = (
        await db.execute(select(Task).options(selectinload(Task.user)).where(Task.id == task_id))
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError("Task not found.")
    return task


def can_edit(task: Task, *, viewer: User, admin: bool) -> bool:
    """Administrators edit anything; everyone else edits only their own tasks."""
    return admin or task.user_id == viewer.id


def require_can_edit(task: Task, *, viewer: User, admin: bool) -> None:
    if not can_edit(task, viewer=viewer, admin=admin):
        raise PermissionDeniedError("You may only edit your own tasks.")


async def _resolve_owner(
    db: AsyncSession, *, requested: uuid.UUID | None, actor: User, admin: bool
) -> uuid.UUID:
    """Whose task this is.

    Only an administrator may name someone else. For everyone else the field is
    ignored rather than rejected, so a stale or tampered client cannot file work
    against another user.
    """
    if requested is None or not admin or requested == actor.id:
        return actor.id

    exists = (await db.execute(select(User.id).where(User.id == requested))).scalar_one_or_none()
    if exists is None:
        raise ValidationError("Unknown user.", details={"user_id": "No such user."})
    return requested


async def create_task(
    db: AsyncSession,
    *,
    actor: User,
    admin: bool,
    task_date: date,
    description: str,
    service: TaskService,
    status: TaskStatus,
    reference_number: str | None = None,
    site_name: str | None = None,
    remarks: str | None = None,
    user_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> Task:
    owner_id = await _resolve_owner(db, requested=user_id, actor=actor, admin=admin)

    task = Task(
        task_date=task_date,
        description=description,
        service=service,
        status=status,
        reference_number=reference_number,
        site_name=site_name,
        remarks=remarks,
        user_id=owner_id,
        created_by_id=actor.id,
    )
    db.add(task)
    await db.flush()

    await audit_service.record(
        db,
        AuditAction.TASK_CREATED,
        actor=actor,
        entity_type="task",
        entity_id=task.id,
        context={"service": str(service), "status": str(status), "user_id": str(owner_id)},
        request=request,
    )
    return task


async def update_task(
    db: AsyncSession,
    *,
    actor: User,
    admin: bool,
    task: Task,
    changes: dict,
    request: Request | None = None,
) -> Task:
    """Apply ``changes`` (already validated) to ``task``.

    The caller's right to edit this row is checked here rather than at the
    endpoint, so no route can forget to ask.
    """
    require_can_edit(task, viewer=actor, admin=admin)

    applied: dict[str, str] = {}
    for field in (
        "task_date",
        "description",
        "service",
        "status",
        "reference_number",
        "site_name",
        "remarks",
    ):
        if field not in changes:
            continue
        value = changes[field]
        if getattr(task, field) != value:
            setattr(task, field, value)
            applied[field] = str(value)

    # Reassignment is administrative: a normal user editing their own task
    # cannot hand it to someone else.
    if "user_id" in changes and changes["user_id"] is not None:
        owner_id = await _resolve_owner(db, requested=changes["user_id"], actor=actor, admin=admin)
        if owner_id != task.user_id:
            task.user_id = owner_id
            applied["user_id"] = str(owner_id)

    if applied:
        await audit_service.record(
            db,
            AuditAction.TASK_UPDATED,
            actor=actor,
            entity_type="task",
            entity_id=task.id,
            context={"changed": sorted(applied)},
            request=request,
        )
    return task


def options() -> tuple[list[str], list[str]]:
    """Contents of dropdowns D1 (services) and D2 (statuses), in display order."""
    return [service.value for service in TaskService], [status.value for status in TaskStatus]
