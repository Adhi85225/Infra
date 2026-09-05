"""Message templates.

Deliberately plain text: these are transactional security emails, and keeping
them simple avoids HTML-rendering inconsistencies across mail clients.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.email.transports import EmailMessage


def _reset_url(token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token}"


def build_password_reset_email(*, to: str, first_name: str, token: str, ttl_minutes: int) -> EmailMessage:
    url = _reset_url(token)
    body = f"""Hello {first_name},

We received a request to reset the password for your {settings.app_name} account.

Open the link below to choose a new password. It expires in {ttl_minutes} minutes
and can only be used once.

{url}

If you did not request this, you can ignore this email -- your password will not
change.

-- {settings.smtp.from_name}
"""
    return EmailMessage(
        to=to,
        subject=f"Reset your {settings.app_name} password",
        text_body=body,
        tags={"type": "password_reset"},
    )


def build_welcome_email(*, to: str, first_name: str, temporary_password: str) -> EmailMessage:
    login_url = f"{settings.frontend_base_url.rstrip('/')}/login"
    body = f"""Hello {first_name},

An account has been created for you on {settings.app_name}.

    Sign in at: {login_url}
    Email:      {to}
    Temporary password: {temporary_password}

You will be required to choose a new password the first time you sign in.

-- {settings.smtp.from_name}
"""
    return EmailMessage(
        to=to,
        subject=f"Your {settings.app_name} account",
        text_body=body,
        tags={"type": "welcome"},
    )
