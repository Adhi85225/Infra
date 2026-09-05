"""Development email outbox.

The application log redacts tokens by design, which means a password-reset link
can never be read back out of it.  That is correct for production and useless
for development, where the whole point of the log transport is to hand the
operator a working reset link while real SMTP is not yet implemented.

The outbox resolves that tension: full message bodies are written to files on
disk, and **never in production**.  See ``docs/SMTP.md``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.email.transports import EmailMessage

logger = get_logger(__name__)

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def write_to_outbox(message: EmailMessage) -> Path | None:
    """Persist ``message`` for developer inspection. Returns the file path.

    Returns ``None`` -- writing nothing at all -- when running in production, so
    that a misconfigured deployment cannot leak reset tokens onto disk.
    """
    if settings.is_production:
        return None

    directory = Path(settings.dev_outbox_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        recipient = _SAFE_NAME.sub("_", message.to)
        path = directory / f"{stamp}_{recipient}.txt"
        path.write_text(
            f"To: {message.to}\n"
            f"From: {settings.smtp.from_name} <{settings.smtp.from_email}>\n"
            f"Subject: {message.subject}\n"
            f"Tags: {message.tags}\n"
            f"{'-' * 72}\n"
            f"{message.text_body}",
            encoding="utf-8",
        )
        return path
    except OSError as exc:
        logger.warning("email.outbox_write_failed", extra={"reason": str(exc)})
        return None
