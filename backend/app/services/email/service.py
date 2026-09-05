"""Email facade used by the rest of the application."""

from __future__ import annotations

from functools import lru_cache

from app.core.logging import get_logger
from app.services.email.transports import EmailMessage, EmailTransport, build_transport

logger = get_logger(__name__)


class EmailService:
    def __init__(self, transport: EmailTransport) -> None:
        self.transport = transport

    async def send(self, message: EmailMessage) -> bool:
        """Attempt delivery. Returns success; never raises into the request path.

        A failure to send must not, for example, reveal to an unauthenticated
        caller that a password-reset address exists -- so errors are logged and
        swallowed here.
        """
        try:
            await self.transport.send(message)
            return True
        except NotImplementedError as exc:
            logger.warning(
                "email.not_sent", extra={"reason": str(exc), "email_to": message.to}
            )
            return False
        except Exception as exc:  # pragma: no cover - transport specific
            logger.error("email.failed", extra={"reason": str(exc), "email_to": message.to})
            return False


@lru_cache
def get_email_service() -> EmailService:
    return EmailService(build_transport())
