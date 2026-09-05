"""Redis client used for rate limiting and access-token revocation.

Redis is treated as an *optimisation with a security role*, not a hard
dependency: if it is unreachable the application keeps serving requests using an
in-process fallback.  That trade-off is deliberate and documented in
``docs/ARCHITECTURE.md`` -- a single-node deployment stays correct, and a
multi-node deployment must run Redis for the limits to be global.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: aioredis.Redis | None = None
_unavailable_logged = False


async def init_redis() -> None:
    global _client
    if not settings.redis_enabled:
        logger.info("Redis disabled by configuration; using in-process fallbacks")
        return
    try:
        client = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
        await client.ping()
        _client = client
        logger.info("Connected to Redis")
    except Exception as exc:  # pragma: no cover - depends on infrastructure
        _client = None
        logger.warning("Redis unavailable; falling back to in-process state", extra={"reason": str(exc)})


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> aioredis.Redis | None:
    return _client


async def safe_call(operation: str, *args: Any, **kwargs: Any) -> Any:
    """Run a Redis command, degrading to ``None`` when Redis is not available."""
    global _unavailable_logged
    client = _client
    if client is None:
        return None
    try:
        return await getattr(client, operation)(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - depends on infrastructure
        if not _unavailable_logged:
            logger.warning("Redis command failed", extra={"operation": operation, "reason": str(exc)})
            _unavailable_logged = True
        return None
