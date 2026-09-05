"""Authentication: sign-in, session rotation, password change and reset.

Security posture (rationale in ``docs/AUTHENTICATION.md``):

* Access tokens are short-lived JWTs sent in the ``Authorization`` header.
* Refresh tokens are opaque, single-use and **rotated** on every refresh; only
  a SHA-256 digest is stored.  Presenting an already-rotated token revokes the
  entire session family, which is the standard defence against token theft.
* Failed sign-ins are counted per account and trigger a temporary lockout.
* ``/forgot-password`` always returns the same response, so it cannot be used to
  discover which email addresses have accounts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationError,
    InvalidCredentialsError,
    ValidationError,
)
from app.core.jwt import create_access_token
from app.core.logging import get_logger
from app.core.redis import safe_call
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.models.enums import AuditAction, UserStatus
from app.models.token import PasswordHistory, PasswordResetToken, Session
from app.models.user import User
from app.services import audit_service

logger = get_logger(__name__)

_REVOKED_JTI_PREFIX = "revoked_jti:v1:"


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@dataclass
class TokenBundle:
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    session_id: uuid.UUID
    csrf_token: str


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    normalized = email.strip().lower()
    return (
        await db.execute(select(User).where(User.email == normalized))
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------


async def authenticate(
    db: AsyncSession, *, email: str, password: str, request: Request | None = None
) -> User:
    """Verify credentials and account state, or raise.

    Unknown email and wrong password produce the *same* error so that the
    endpoint does not confirm which addresses exist.
    """
    now = _now()
    user = await get_user_by_email(db, email)

    if user is None:
        # Burn comparable CPU so response timing does not distinguish the cases.
        verify_password(password, None)
        await audit_service.record(
            db,
            AuditAction.LOGIN_FAILED,
            actor_email=email.strip().lower(),
            success=False,
            context={"reason": "unknown_email"},
            request=request,
        )
        await db.commit()
        raise InvalidCredentialsError()

    if user.is_locked(now):
        await audit_service.record(
            db,
            AuditAction.LOGIN_FAILED,
            actor=user,
            success=False,
            context={"reason": "account_locked", "locked_until": user.locked_until.isoformat()},
            request=request,
        )
        await db.commit()
        raise AccountLockedError(
            "This account is temporarily locked due to repeated failed sign-in attempts. "
            f"Try again after {user.locked_until:%H:%M UTC}."
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        reason = "bad_password"
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
            reason = "account_locked"
            await audit_service.record(
                db, AuditAction.ACCOUNT_LOCKED, actor=user, success=False, request=request
            )
        await audit_service.record(
            db,
            AuditAction.LOGIN_FAILED,
            actor=user,
            success=False,
            context={"reason": reason},
            request=request,
        )
        await db.commit()
        raise InvalidCredentialsError()

    if not UserStatus(user.status).can_authenticate:
        await audit_service.record(
            db,
            AuditAction.LOGIN_FAILED,
            actor=user,
            success=False,
            context={"reason": "inactive_status", "status": user.status},
            request=request,
        )
        await db.commit()
        raise AccountInactiveError(
            "This account is not active. Please contact an administrator."
        )

    # Transparently upgrade the stored hash if the parameters have changed.
    if user.password_hash and password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    return user


async def start_session(
    db: AsyncSession, user: User, *, request: Request | None = None
) -> TokenBundle:
    """Create a refresh session and issue the first access token."""
    from app.core.csrf import generate_csrf_token

    now = _now()
    refresh_token = generate_token()
    session = Session(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent") if request else None),
        last_used_at=now,
    )
    db.add(session)
    await db.flush()

    access_token, access_expires = create_access_token(
        user_id=user.id, session_id=session.id, jti=str(uuid.uuid4())
    )
    return TokenBundle(
        access_token=access_token,
        access_token_expires_at=access_expires,
        refresh_token=refresh_token,
        refresh_token_expires_at=session.expires_at,
        session_id=session.id,
        csrf_token=generate_csrf_token(),
    )


# ---------------------------------------------------------------------------
# Refresh / logout
# ---------------------------------------------------------------------------


async def _revoke_session_family(db: AsyncSession, session: Session, reason: str) -> None:
    """Revoke a session and everything rotated from it, in both directions."""
    now = _now()
    to_revoke: list[Session] = [session]
    seen: set[uuid.UUID] = set()

    while to_revoke:
        current = to_revoke.pop()
        if current.id in seen:
            continue
        seen.add(current.id)
        if current.revoked_at is None:
            current.revoked_at = now
            current.revoked_reason = reason
        children = (
            await db.execute(select(Session).where(Session.rotated_from_id == current.id))
        ).scalars().all()
        to_revoke.extend(children)


async def refresh_session(
    db: AsyncSession, *, refresh_token: str, request: Request | None = None
) -> tuple[User, TokenBundle]:
    """Rotate a refresh token, returning a fresh bundle."""
    from app.core.csrf import generate_csrf_token

    now = _now()
    digest = hash_token(refresh_token)
    session = (
        await db.execute(select(Session).where(Session.token_hash == digest))
    ).scalar_one_or_none()

    if session is None:
        raise AuthenticationError("Invalid session. Please sign in again.", code="invalid_session")

    if session.revoked_at is not None:
        # A revoked token was replayed: assume theft and kill the whole family.
        await _revoke_session_family(db, session, "reuse_detected")
        await audit_service.record(
            db,
            AuditAction.TOKEN_REUSE_DETECTED,
            actor_user_id=session.user_id,
            success=False,
            entity_type="session",
            entity_id=session.id,
            request=request,
        )
        await db.commit()
        raise AuthenticationError(
            "Your session is no longer valid. Please sign in again.", code="session_revoked"
        )

    if session.expires_at <= now:
        raise AuthenticationError("Your session has expired.", code="session_expired")

    user = session.user
    if not UserStatus(user.status).can_authenticate:
        await _revoke_session_family(db, session, "account_inactive")
        await db.commit()
        raise AccountInactiveError()

    # Rotate: revoke the presented token, mint a successor linked to it.
    session.revoked_at = now
    session.revoked_reason = "rotated"
    session.last_used_at = now

    new_refresh = generate_token()
    successor = Session(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=session.expires_at,  # rotation does not extend the lifetime
        rotated_from_id=session.id,
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent") if request else None),
        last_used_at=now,
    )
    db.add(successor)
    await db.flush()

    access_token, access_expires = create_access_token(
        user_id=user.id, session_id=successor.id, jti=str(uuid.uuid4())
    )
    bundle = TokenBundle(
        access_token=access_token,
        access_token_expires_at=access_expires,
        refresh_token=new_refresh,
        refresh_token_expires_at=successor.expires_at,
        session_id=successor.id,
        csrf_token=generate_csrf_token(),
    )
    await audit_service.record(
        db, AuditAction.TOKEN_REFRESHED, actor=user, entity_type="session", entity_id=successor.id,
        request=request,
    )
    return user, bundle


async def revoke_access_token(jti: str, expires_at: datetime) -> None:
    """Deny-list an access token's ``jti`` for its remaining lifetime.

    Without Redis this is a no-op and the token stays valid until it expires
    (minutes).  That limitation is documented in ``docs/SECURITY.md``.
    """
    ttl = int((expires_at - _now()).total_seconds())
    if ttl > 0:
        await safe_call("setex", f"{_REVOKED_JTI_PREFIX}{jti}", ttl, "1")


async def is_access_token_revoked(jti: str) -> bool:
    return bool(await safe_call("get", f"{_REVOKED_JTI_PREFIX}{jti}"))


async def logout(
    db: AsyncSession,
    *,
    refresh_token: str | None,
    user: User | None = None,
    jti: str | None = None,
    access_expires_at: datetime | None = None,
    request: Request | None = None,
) -> None:
    if refresh_token:
        session = (
            await db.execute(select(Session).where(Session.token_hash == hash_token(refresh_token)))
        ).scalar_one_or_none()
        if session is not None:
            await _revoke_session_family(db, session, "logout")

    if jti and access_expires_at:
        await revoke_access_token(jti, access_expires_at)

    await audit_service.record(db, AuditAction.LOGOUT, actor=user, request=request)


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID, reason: str) -> int:
    """Sign a user out everywhere. Used after password changes/resets."""
    now = _now()
    sessions = (
        await db.execute(
            select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
        )
    ).scalars().all()
    for session in sessions:
        session.revoked_at = now
        session.revoked_reason = reason
    return len(sessions)


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


async def _assert_password_acceptable(db: AsyncSession, user: User, new_password: str) -> None:
    problems = validate_password_strength(new_password, email=user.email)
    if problems:
        raise ValidationError(
            "The new password does not meet the password policy.",
            details={"password": problems},
        )

    if user.password_hash and verify_password(new_password, user.password_hash):
        raise ValidationError(
            "The new password must be different from your current password.",
            details={"password": ["Must not match your current password."]},
        )

    if settings.password_history_depth > 0:
        history = (
            await db.execute(
                select(PasswordHistory)
                .where(PasswordHistory.user_id == user.id)
                .order_by(PasswordHistory.created_at.desc())
                .limit(settings.password_history_depth)
            )
        ).scalars().all()
        if any(verify_password(new_password, entry.password_hash) for entry in history):
            raise ValidationError(
                "The new password must not be one of your recent passwords.",
                details={
                    "password": [
                        f"Must not match your last {settings.password_history_depth} passwords."
                    ]
                },
            )


async def _apply_new_password(db: AsyncSession, user: User, new_password: str) -> None:
    if user.password_hash:
        db.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash))

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = _now()
    user.failed_login_count = 0
    user.locked_until = None

    # Trim history beyond the configured depth.
    if settings.password_history_depth > 0:
        stale = (
            await db.execute(
                select(PasswordHistory)
                .where(PasswordHistory.user_id == user.id)
                .order_by(PasswordHistory.created_at.desc())
                .offset(settings.password_history_depth)
            )
        ).scalars().all()
        for entry in stale:
            await db.delete(entry)


async def change_password(
    db: AsyncSession,
    user: User,
    *,
    current_password: str,
    new_password: str,
    request: Request | None = None,
) -> None:
    if not verify_password(current_password, user.password_hash):
        await audit_service.record(
            db,
            AuditAction.PASSWORD_CHANGED,
            actor=user,
            success=False,
            context={"reason": "wrong_current_password"},
            request=request,
        )
        await db.commit()
        raise ValidationError(
            "Your current password is incorrect.",
            details={"current_password": ["Incorrect password."]},
        )

    await _assert_password_acceptable(db, user, new_password)
    await _apply_new_password(db, user, new_password)
    await audit_service.record(db, AuditAction.PASSWORD_CHANGED, actor=user, request=request)


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------


async def request_password_reset(
    db: AsyncSession, *, email: str, request: Request | None = None
) -> str | None:
    """Create a reset token when the address belongs to an active account.

    Returns the raw token (for the email) or ``None``.  Callers must return an
    identical response either way -- see the endpoint.
    """
    user = await get_user_by_email(db, email)
    if user is None or not UserStatus(user.status).can_authenticate:
        await audit_service.record(
            db,
            AuditAction.PASSWORD_RESET_REQUESTED,
            actor=user,
            actor_email=email.strip().lower(),
            success=False,
            context={"reason": "no_active_account"},
            request=request,
        )
        return None

    # Invalidate any outstanding tokens so only the newest link works.
    now = _now()
    outstanding = (
        await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
    ).scalars().all()
    for token_row in outstanding:
        token_row.used_at = now

    raw_token = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(minutes=settings.password_reset_ttl_minutes),
            requested_ip=_client_ip(request),
        )
    )
    await audit_service.record(
        db, AuditAction.PASSWORD_RESET_REQUESTED, actor=user, request=request
    )
    return raw_token


async def reset_password(
    db: AsyncSession, *, token: str, new_password: str, request: Request | None = None
) -> User:
    now = _now()
    row = (
        await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
        )
    ).scalar_one_or_none()

    if row is None or not row.is_usable(now):
        await audit_service.record(
            db,
            AuditAction.PASSWORD_RESET_COMPLETED,
            actor_user_id=(row.user_id if row else None),
            success=False,
            context={"reason": "invalid_or_expired_token"},
            request=request,
        )
        await db.commit()
        raise ValidationError(
            "This password reset link is invalid or has expired. Please request a new one.",
            code="invalid_reset_token",
        )

    user = row.user
    await _assert_password_acceptable(db, user, new_password)
    await _apply_new_password(db, user, new_password)

    row.used_at = now
    # A reset implies the account may have been compromised: drop every session.
    await revoke_all_sessions(db, user.id, "password_reset")
    await audit_service.record(
        db, AuditAction.PASSWORD_RESET_COMPLETED, actor=user, request=request
    )
    return user
