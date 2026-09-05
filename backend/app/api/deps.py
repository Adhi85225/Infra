"""FastAPI dependencies for authentication and authorization.

Endpoints declare *what* they need; all the reasoning lives here and in
:mod:`app.services.permission_service`.

Typical use::

    @router.get("/", dependencies=[Depends(require_access("TEAM_MEMBERS", ModuleAction.VIEW))])
    async def list_team(user: CurrentUser): ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.errors import (
    AccountInactiveError,
    AuthenticationError,
    PasswordChangeRequiredError,
)
from app.core.jwt import TokenPayload, decode_access_token
from app.models.enums import ModuleAction, UserStatus
from app.models.token import Session
from app.models.user import User
from app.services import auth_service, permission_service
from app.services.permission_service import PermissionMap

DbSession = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False, description="Short-lived access token")


async def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenPayload:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError(
            "Authentication is required.", headers={"WWW-Authenticate": "Bearer"}
        )
    return decode_access_token(credentials.credentials)


async def get_current_user(
    db: DbSession,
    payload: Annotated[TokenPayload, Depends(get_token_payload)],
) -> User:
    """Resolve, and re-validate, the caller on every request.

    The token alone is not trusted: the user's status and the backing session
    are checked against the database so that a deactivated account or a
    revoked session stops working immediately rather than at token expiry.
    """
    if await auth_service.is_access_token_revoked(payload.jti):
        raise AuthenticationError("This session has been signed out.", code="token_revoked")

    user = (
        await db.execute(select(User).where(User.id == payload.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise AuthenticationError("Invalid authentication token.", code="invalid_token")

    if not UserStatus(user.status).can_authenticate:
        raise AccountInactiveError()

    session = (
        await db.execute(select(Session).where(Session.id == payload.session_id))
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        # Any revoked session invalidates its access token immediately -- including
        # the "rotated" case. Each refresh mints a token bound to the *successor*
        # session, so the current token is unaffected; only tokens the client has
        # already replaced stop working. Accepting "rotated" here would keep a
        # pre-logout access token alive for its full remaining lifetime.
        raise AuthenticationError(
            "This session is no longer valid. Please sign in again.", code="session_revoked"
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_active_user(user: CurrentUser) -> User:
    """A fully authorized caller: authenticated *and* password not pending.

    Every protected endpoint uses this instead of :func:`get_current_user`, so a
    user who must change their password cannot reach any other part of the API.
    The few endpoints they *may* reach (``/auth/me``, ``/auth/change-password``,
    ``/auth/logout``) depend on ``CurrentUser`` directly.
    """
    if user.must_change_password:
        raise PasswordChangeRequiredError(
            "You must change your password before using the application.",
        )
    return user


ActiveUser = Annotated[User, Depends(get_active_user)]


async def get_permissions(db: DbSession, user: CurrentUser) -> PermissionMap:
    return await permission_service.resolve_permissions(db, user)


CurrentPermissions = Annotated[PermissionMap, Depends(get_permissions)]


def require_access(module_key: str, action: ModuleAction = ModuleAction.VIEW):
    """Build a dependency enforcing ``action`` on ``module_key``.

    This is the *only* supported way for an endpoint to express an access
    requirement.
    """

    async def dependency(db: DbSession, user: ActiveUser) -> User:
        await permission_service.require_permission(db, user, module_key, action)
        return user

    return dependency


def require_superuser():
    async def dependency(user: ActiveUser) -> User:
        from app.core.errors import PermissionDeniedError

        if not user.is_superuser:
            raise PermissionDeniedError("This action requires Super Admin.")
        return user

    return dependency


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------


def get_refresh_token(request: Request) -> str | None:
    return request.cookies.get(settings.refresh_cookie_name)
