"""Fixed-window rate limiting backed by Redis, with an in-process fallback.

Usage::

    @router.post("/login", dependencies=[Depends(rate_limit("login", settings.rate_limit_login))])

Keys combine the bucket name with the client identity (authenticated user id
when available, otherwise the client IP) so one abusive caller cannot exhaust
another's budget.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request

from app.core.errors import RateLimitedError
from app.core.redis import safe_call

# bucket -> (window_start, count); only used when Redis is unavailable.
_local_counters: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))


def parse_limit(spec: str) -> tuple[int, int]:
    """Parse ``"10/60"`` into ``(max_requests, window_seconds)``."""
    limit_str, _, window_str = spec.partition("/")
    return int(limit_str), int(window_str or 60)


def client_identifier(request: Request) -> str:
    """Best-effort client identity.

    ``X-Forwarded-For`` is honoured only because the app is expected to sit
    behind the bundled reverse proxy; see docs/DEPLOYMENT.md for why the proxy
    must overwrite (not append to) that header.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _increment(key: str, window_seconds: int) -> int:
    """Increment the counter for ``key`` and return the new value."""
    count = await safe_call("incr", key)
    if count is not None:
        if count == 1:
            await safe_call("expire", key, window_seconds)
        return int(count)

    # Fallback: process-local fixed window.
    now = time.monotonic()
    window_start, current = _local_counters[key]
    if now - window_start >= window_seconds:
        _local_counters[key] = (now, 1)
        return 1
    _local_counters[key] = (window_start, current + 1)
    return current + 1


def rate_limit(bucket: str, spec: str):
    """Build a FastAPI dependency enforcing a fixed-window limit.

    Implemented as a factory returning a closure rather than a callable class:
    FastAPI resolves a dependency's type hints through its ``__globals__``, which
    a class *instance* does not have. With ``from __future__ import annotations``
    in effect that would leave ``Request`` an unresolved ForwardRef and FastAPI
    would silently treat it as a query parameter.
    """
    max_requests, window_seconds = parse_limit(spec)

    async def dependency(request: Request) -> None:
        window = int(time.time() // window_seconds)
        key = f"ratelimit:{bucket}:{client_identifier(request)}:{window}"
        count = await _increment(key, window_seconds)
        if count > max_requests:
            raise RateLimitedError(
                "Too many requests. Please slow down and try again shortly.",
                details={"retry_after_seconds": window_seconds},
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency


def reset_local_counters() -> None:
    """Test helper -- clears the in-process fallback state."""
    _local_counters.clear()
