"""Double-submit CSRF protection for cookie-authenticated endpoints.

Only two endpoints authenticate via cookie -- ``/auth/refresh`` and
``/auth/logout`` -- because the refresh token lives in an httpOnly cookie.
Everything else uses a Bearer token and is therefore not CSRF-reachable.

On login/refresh the server sets two cookies:

* ``ght_refresh``  -- httpOnly, the actual credential.
* ``ght_csrf``     -- readable by JS, a random value the client must echo back
  in the ``X-CSRF-Token`` header.

An attacker's cross-site request carries the cookies but cannot read the CSRF
value to set the header, so the comparison fails.
"""

from __future__ import annotations

from fastapi import Request

from app.core.config import settings
from app.core.errors import CSRFError
from app.core.security import generate_token, tokens_equal


def generate_csrf_token() -> str:
    return generate_token(32)


async def require_csrf(request: Request) -> None:
    cookie_value = request.cookies.get(settings.csrf_cookie_name)
    header_value = request.headers.get(settings.csrf_header_name)

    if not cookie_value or not header_value:
        raise CSRFError("Missing CSRF token.")
    if not tokens_equal(cookie_value, header_value):
        raise CSRFError("CSRF token mismatch.")
