"""Structured JSON logging with mandatory secret redaction.

Security requirement: passwords, tokens and authorization headers must never
reach the log stream.  Redaction happens in a filter so it applies to *every*
logger in the process, including third-party libraries.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

# Patterns that must never appear in plaintext in the logs.
_SENSITIVE_KEYS = {
    "password",
    "current_password",
    "new_password",
    "confirm_password",
    "temporary_password",
    "token",
    "access_token",
    "refresh_token",
    "reset_token",
    "authorization",
    "cookie",
    "set-cookie",
    "jwt_secret",
    "smtp_password",
    "secret",
    "api_key",
}

_REDACTED = "***REDACTED***"

# Catches `password=hunter2`, `"token": "abc"`, `token=abc` in free-form strings.
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b(" + "|".join(re.escape(k) for k in _SENSITIVE_KEYS) + r")\b(\"?\s*[:=]\s*\"?)([^\s,&\"}]+)"
)


def redact(value: Any, _depth: int = 0) -> Any:
    """Recursively strip sensitive values out of arbitrary log payloads."""
    if _depth > 6:
        return value
    if isinstance(value, dict):
        return {
            key: (_REDACTED if str(key).lower() in _SENSITIVE_KEYS else redact(val, _depth + 1))
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, _depth + 1) for item in value]
    if isinstance(value, str):
        return _INLINE_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", value)
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        if isinstance(record.args, dict):
            record.args = redact(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact(list(record.args)))
        if hasattr(record, "context"):
            record.context = redact(record.context)  # type: ignore[attr-defined]
        return True


_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Caller-supplied context goes in first so that the core fields below
        # always win -- an `extra={"level": ...}` must never masquerade as the
        # real log level.
        payload: dict[str, Any] = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED and not key.startswith("_")
        }
        payload.update(
            timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), default=str)


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn ships its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.database_echo else logging.WARNING
    )


# Attribute names the stdlib already puts on every LogRecord. Passing any of
# these via ``extra=`` raises KeyError, so the adapter below renames them.
_RESERVED_LOGRECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}


class ContextLogger(logging.LoggerAdapter):
    """Logger that accepts arbitrary ``extra`` keys without blowing up.

    Call sites should be free to log domain fields (``module``, ``name``,
    ``filename`` ...) without knowing which names the logging module has
    reserved; colliding keys are prefixed rather than rejected.
    """

    def process(self, msg, kwargs):
        extra = kwargs.get("extra")
        if extra:
            kwargs["extra"] = {
                (f"ctx_{key}" if key in _RESERVED_LOGRECORD_ATTRS else key): value
                for key, value in extra.items()
            }
        return msg, kwargs


def get_logger(name: str) -> ContextLogger:
    return ContextLogger(logging.getLogger(name), {})
