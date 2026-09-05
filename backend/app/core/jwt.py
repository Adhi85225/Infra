"""Access-token issuing and verification.

Access tokens are short-lived, signed JWTs carried in the ``Authorization``
header.  They are intentionally *not* stored in a cookie, which removes the
whole CSRF surface for the authenticated API.  Cookie-bearing endpoints
(refresh/logout) are protected separately by :mod:`app.core.csrf`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from app.core.config import settings
from app.core.errors import AuthenticationError

ACCESS_TOKEN_TYPE = "access"


class TokenPayload:
    """Validated access-token claims."""

    __slots__ = ("user_id", "session_id", "jti", "issued_at", "expires_at", "raw")

    def __init__(self, claims: dict[str, Any]) -> None:
        self.raw = claims
        self.user_id = UUID(claims["sub"])
        self.session_id = UUID(claims["sid"])
        self.jti: str = claims["jti"]
        self.issued_at = datetime.fromtimestamp(claims["iat"], tz=timezone.utc)
        self.expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)


def create_access_token(
    *,
    user_id: UUID,
    session_id: UUID,
    jti: str,
    expires_in_minutes: int | None = None,
) -> tuple[str, datetime]:
    """Return ``(encoded_jwt, expires_at)``."""
    ttl = expires_in_minutes or settings.access_token_ttl_minutes
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(minutes=ttl)
    claims = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": jti,
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.app_name,
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> TokenPayload:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Your session has expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.", code="invalid_token") from exc

    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise AuthenticationError("Invalid authentication token.", code="invalid_token")

    try:
        return TokenPayload(claims)
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid authentication token.", code="invalid_token") from exc
