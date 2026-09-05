"""Liveness and readiness probes (used by Docker health checks)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionFactory
from app.core.redis import get_redis

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/ready", summary="Readiness probe (checks dependencies)")
async def readiness(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    redis_client = get_redis()
    if not settings.redis_enabled:
        checks["redis"] = "disabled"
    elif redis_client is None:
        checks["redis"] = "unavailable (degraded)"
    else:
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"

    # Only the database is required to serve traffic; Redis degrades gracefully.
    ready = checks["database"] == "ok"
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}
