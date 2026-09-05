"""Email infrastructure.

Phase 1 scope: the *configuration surface* and the *sending seam* exist and are
exercised by the password-reset flow, but no real SMTP delivery is performed.
Messages are rendered and written to the application log instead.

To switch on real delivery later:

1. Populate the ``SMTP_*`` variables (see ``docs/SMTP.md`` / ``.env.example``).
2. Set ``EMAIL_TRANSPORT=smtp``.
3. Implement :meth:`SMTPTransport.send` -- the only place that needs code.

Nothing else in the application changes.
"""

from app.services.email.messages import (
    build_password_reset_email,
    build_welcome_email,
)
from app.services.email.service import EmailService, get_email_service
from app.services.email.outbox import write_to_outbox
from app.services.email.transports import EmailMessage, EmailTransport

__all__ = [
    "EmailMessage",
    "EmailService",
    "EmailTransport",
    "build_password_reset_email",
    "build_welcome_email",
    "get_email_service",
    "write_to_outbox",
]
