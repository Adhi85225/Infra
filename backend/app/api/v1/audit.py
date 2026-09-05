"""Audit-log read endpoint."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_access
from app.models.enums import ModuleAction
from app.schemas.audit import AuditLogEntry
from app.schemas.common import Page
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get(
    "",
    response_model=Page[AuditLogEntry],
    dependencies=[Depends(require_access("ACCESS_MANAGEMENT", ModuleAction.VIEW))],
    summary="List audit-log entries",
)
async def list_audit_logs(
    db: DbSession,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_user_id: uuid.UUID | None = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditLogEntry]:
    logs, total = await audit_service.list_logs(
        db,
        limit=limit,
        offset=offset,
        action=action,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
    )
    return Page[AuditLogEntry](
        items=[AuditLogEntry.model_validate(log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )
