"""Authentication endpoints.

Routes (all prefixed with ``/api/v1/auth``)::

    POST /login             email + password  -> access token + refresh cookie
    POST /refresh           rotate the refresh cookie
    POST /logout            revoke the session
    GET  /me                current user + effective permissions
    POST /change-password   authenticated password change
    POST /forgot-password   request a reset link (always 202)
    POST /reset-password    complete a reset with a token
    GET  /password-policy   the rules the UI should display
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, DbSession, get_refresh_token
from app.core.config import settings
from app.core.csrf import require_csrf
from app.core.errors import AuthenticationError
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    PasswordPolicyResponse,
    PermissionEntry,
    ResetPasswordRequest,
    SessionResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserSummary
from app.services import auth_service, permission_service
from app.services.auth_service import TokenBundle
from app.services.email import build_password_reset_email, get_email_service
from app.services.permission_service import PermissionMap

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

# The refresh cookie is scoped to the auth routes so it is not attached to every
# API call -- it is only ever needed by /refresh and /logout.
_REFRESH_COOKIE_PATH = f"{settings.api_v1_prefix}/auth"


def _set_session_cookies(response: Response, bundle: TokenBundle) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        bundle.refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=_REFRESH_COOKIE_PATH,
    )
    # Readable by JS on purpose: the client echoes it in the X-CSRF-Token header.
    response.set_cookie(
        settings.csrf_cookie_name,
        bundle.csrf_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name, path=_REFRESH_COOKIE_PATH, domain=settings.cookie_domain
    )
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)


def _permission_entries(permissions: PermissionMap) -> list[PermissionEntry]:
    return [
        PermissionEntry(
            module_key=item.module_key,
            module_name=item.module_name,
            icon=item.icon,
            route=item.route,
            description=item.description,
            sort_order=item.sort_order,
            is_implemented=item.is_implemented,
            access_level=item.access_level,
            can_view=item.can_view,
            can_manage=item.can_manage,
        )
        for item in sorted(permissions.values(), key=lambda p: p.sort_order)
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=SessionResponse,
    dependencies=[Depends(rate_limit("login", settings.rate_limit_login))],
    summary="Sign in with email and password",
)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> SessionResponse:
    user = await auth_service.authenticate(
        db, email=payload.email, password=payload.password, request=request
    )
    bundle = await auth_service.start_session(db, user, request=request)

    from app.models.enums import AuditAction
    from app.services import audit_service

    await audit_service.record(db, AuditAction.LOGIN_SUCCESS, actor=user, request=request)
    await db.commit()
    await db.refresh(user)

    permissions = await permission_service.resolve_permissions(db, user, use_cache=False)
    _set_session_cookies(response, bundle)

    return SessionResponse(
        access_token=bundle.access_token,
        expires_at=bundle.access_token_expires_at,
        must_change_password=user.must_change_password,
        user=UserSummary.model_validate(user),
        permissions=_permission_entries(permissions),
    )


@router.post(
    "/refresh",
    response_model=SessionResponse,
    dependencies=[Depends(require_csrf)],
    summary="Rotate the refresh token and obtain a new access token",
)
async def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Depends(get_refresh_token)],
) -> SessionResponse:
    if not refresh_token:
        raise AuthenticationError("No active session.", code="no_session")

    user, bundle = await auth_service.refresh_session(
        db, refresh_token=refresh_token, request=request
    )
    await db.commit()
    await db.refresh(user)

    permissions = await permission_service.resolve_permissions(db, user)
    _set_session_cookies(response, bundle)

    return SessionResponse(
        access_token=bundle.access_token,
        expires_at=bundle.access_token_expires_at,
        must_change_password=user.must_change_password,
        user=UserSummary.model_validate(user),
        permissions=_permission_entries(permissions),
    )


@router.post(
    "/logout",
    response_model=Message,
    dependencies=[Depends(require_csrf)],
    summary="Revoke the current session",
)
async def logout(
    request: Request,
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Depends(get_refresh_token)],
) -> Message:
    # Authentication is optional here: logging out must always succeed, even
    # with an expired access token, so the client can clear its state.
    user = None
    jti = None
    expires_at = None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        try:
            from app.core.jwt import decode_access_token

            token_payload = decode_access_token(header.split(" ", 1)[1])
            jti, expires_at = token_payload.jti, token_payload.expires_at
            from sqlalchemy import select

            from app.models.user import User

            user = (
                await db.execute(select(User).where(User.id == token_payload.user_id))
            ).scalar_one_or_none()
        except AuthenticationError:
            pass

    await auth_service.logout(
        db,
        refresh_token=refresh_token,
        user=user,
        jti=jti,
        access_expires_at=expires_at,
        request=request,
    )
    await db.commit()
    _clear_session_cookies(response)
    return Message(message="Signed out.")


@router.get("/me", response_model=MeResponse, summary="Current user and effective permissions")
async def me(db: DbSession, user: CurrentUser) -> MeResponse:
    permissions = await permission_service.resolve_permissions(db, user)
    return MeResponse(
        user=UserSummary.model_validate(user),
        permissions=_permission_entries(permissions),
        must_change_password=user.must_change_password,
    )


@router.post(
    "/change-password",
    response_model=SessionResponse,
    summary="Change your own password",
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: DbSession,
    user: CurrentUser,
) -> SessionResponse:
    """Also satisfies the mandatory first-login change.

    Depends on ``CurrentUser`` (not ``ActiveUser``) precisely so a user in the
    "must change password" state can reach it -- that state blocks every other
    protected endpoint.

    A password change invalidates *all* existing sessions (the point is to lock
    out anyone holding the old credential). To avoid bouncing the caller back to
    the sign-in screen, a brand-new session is issued and returned here, so the
    client simply swaps in the new access token.
    """
    await auth_service.change_password(
        db,
        user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        request=request,
    )
    await auth_service.revoke_all_sessions(db, user.id, "password_changed")
    await db.flush()

    bundle = await auth_service.start_session(db, user, request=request)
    await db.commit()
    await db.refresh(user)

    permissions = await permission_service.resolve_permissions(db, user, use_cache=False)
    _set_session_cookies(response, bundle)

    return SessionResponse(
        access_token=bundle.access_token,
        expires_at=bundle.access_token_expires_at,
        must_change_password=user.must_change_password,
        user=UserSummary.model_validate(user),
        permissions=_permission_entries(permissions),
    )


@router.post(
    "/forgot-password",
    response_model=Message,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot_password", settings.rate_limit_forgot_password))],
    summary="Request a password reset link",
)
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: DbSession
) -> Message:
    """Always returns the same response.

    Whether or not the address exists, the caller sees an identical 202 -- this
    endpoint cannot be used to enumerate accounts.
    """
    token = await auth_service.request_password_reset(
        db, email=payload.email, request=request
    )
    await db.commit()

    if token:
        user = await auth_service.get_user_by_email(db, payload.email)
        if user is not None:
            message = build_password_reset_email(
                to=user.email,
                first_name=user.first_name,
                token=token,
                ttl_minutes=settings.password_reset_ttl_minutes,
            )
            await get_email_service().send(message)

    return Message(
        message=(
            "If an account exists for that email address, a password reset link has been sent."
        )
    )


@router.post(
    "/reset-password",
    response_model=Message,
    dependencies=[Depends(rate_limit("reset_password", settings.rate_limit_reset_password))],
    summary="Set a new password using a reset token",
)
async def reset_password(
    payload: ResetPasswordRequest, request: Request, db: DbSession
) -> Message:
    await auth_service.reset_password(
        db, token=payload.token, new_password=payload.new_password, request=request
    )
    await db.commit()
    return Message(message="Your password has been reset. You can now sign in.")


@router.get(
    "/password-policy",
    response_model=PasswordPolicyResponse,
    summary="Password rules, so the UI does not duplicate them",
)
async def password_policy() -> PasswordPolicyResponse:
    return PasswordPolicyResponse(
        min_length=settings.password_min_length,
        max_length=settings.password_max_length,
        require_uppercase=settings.password_require_upper,
        require_lowercase=settings.password_require_lower,
        require_digit=settings.password_require_digit,
        require_symbol=settings.password_require_symbol,
        history_depth=settings.password_history_depth,
    )
