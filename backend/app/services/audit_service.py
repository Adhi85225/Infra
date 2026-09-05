"""Audit-log writer.

Every security-relevant action funnels through :func:`record`.  Context is
redacted before it is persisted, so a caller cannot accidentally store a
password or token in the log.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, redact
from app.models.audit import AuditLog
from app.models.enums import AuditAction
from app.models.user import User

logger = get_logger(__name__)


def _request_metadata(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )
    return ip, request.headers.get("user-agent")


async def record(
    db: AsyncSession,
    action: AuditAction | str,
    *,
    actor: User | None = None,
    actor_email: str | None = None,
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | UUID | None = None,
    success: bool = True,
    context: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Append an entry. The caller is responsible for committing the session."""
    ip, user_agent = _request_metadata(request)

    entry = AuditLog(
        actor_user_id=actor.id if actor else actor_user_id,
        actor_email=(actor.email if actor else actor_email),
        action=str(action),
        success=success,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip_address=ip,
        user_agent=user_agent,
        context=redact(context) if context else None,
    )
    db.add(entry)

    logger.info(
        "audit",
        extra={
            "audit_action": str(action),
            "actor": entry.actor_email,
            "entity_type": entity_type,
            "entity_id": entry.entity_id,
            "success": success,
        },
    )
    return entry


async def list_logs(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
) -> tuple[list[AuditLog], int]:
    from sqlalchemy import func

    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if actor_user_id:
        conditions.append(AuditLog.actor_user_id == actor_user_id)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)

    base = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    for condition in conditions:
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), int(total)
