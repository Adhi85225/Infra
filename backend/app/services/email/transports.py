"""Email transports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None
    # Non-sensitive routing/diagnostic info attached to the log entry.
    tags: dict[str, str] = field(default_factory=dict)


class EmailTransport(ABC):
    name: str

    @abstractmethod
    async def send(self, message: EmailMessage) -> None: ...


class LogTransport(EmailTransport):
    """Phase 1 default: render the message to the log instead of sending it.

    During development this is how you obtain a password-reset link -- the URL
    is printed in the API container's log.  See ``docs/SMTP.md``.
    """

    name = "log"

    async def send(self, message: EmailMessage) -> None:
        # The log line is deliberately body-free: the redaction filter would
        # mangle any token in it anyway, and production logs must not carry
        # credentials. The readable copy goes to the dev outbox instead.
        from app.services.email.outbox import write_to_outbox

        path = write_to_outbox(message)
        logger.info(
            "email.dispatched (log transport -- NOT actually delivered)",
            extra={
                "email_to": message.to,
                "email_subject": message.subject,
                "email_from": f"{settings.smtp.from_name} <{settings.smtp.from_email}>",
                "email_tags": message.tags,
                "outbox_file": str(path) if path else None,
            },
        )


class SMTPTransport(EmailTransport):
    """Real SMTP delivery -- intentionally not implemented in Phase 1.

    The class exists so the wiring, configuration and selection logic are all in
    place and testable.  Implementing ``send`` (e.g. with ``aiosmtplib``) is the
    entire remaining task; see ``docs/SMTP.md`` for the checklist.
    """

    name = "smtp"

    async def send(self, message: EmailMessage) -> None:
        raise NotImplementedError(
            "Real SMTP delivery is not implemented yet (Phase 1). "
            "Set EMAIL_TRANSPORT=log, or implement SMTPTransport.send. "
            "See docs/SMTP.md."
        )


def build_transport() -> EmailTransport:
    if settings.email_transport == "smtp":
        if not settings.smtp.is_configured:
            logger.warning(
                "EMAIL_TRANSPORT=smtp but SMTP is not configured; falling back to log transport",
            )
            return LogTransport()
        return SMTPTransport()
    return LogTransport()
