"""Authentication: sign-in, sign-out, sessions and password change."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.core.config import settings
from app.models import Session, User
from app.models.enums import AuditAction, UserStatus
from tests.conftest import (
    ADMIN_PASSWORD,
    GUEST_PASSWORD,
    USER_PASSWORD,
    auth_headers,
    create_user,
    login,
    refetch,
)


class TestLogin:
    async def test_valid_login_returns_token_user_and_permissions(self, client, admin):
        response = await login(client, admin.email, ADMIN_PASSWORD)
        assert response.status_code == 200

        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["access_token"]
        assert body["user"]["email"] == admin.email
        assert [role["key"] for role in body["user"]["roles"]] == ["ADMIN"]
        # The permission map ships with the session so the UI never guesses.
        assert len(body["permissions"]) == 12

    async def test_login_is_case_insensitive_on_email(self, client, admin):
        response = await login(client, "ADMIN@TEST.INTERNAL", ADMIN_PASSWORD)
        assert response.status_code == 200

    async def test_login_sets_httponly_refresh_and_readable_csrf_cookies(self, client, admin):
        response = await login(client, admin.email, ADMIN_PASSWORD)
        cookies = {c.name: c for c in response.cookies.jar}
        assert settings.refresh_cookie_name in cookies
        assert settings.csrf_cookie_name in cookies

        set_cookie_headers = response.headers.get_list("set-cookie")
        refresh_header = next(h for h in set_cookie_headers if settings.refresh_cookie_name in h)
        csrf_header = next(h for h in set_cookie_headers if settings.csrf_cookie_name in h)
        assert "HttpOnly" in refresh_header
        assert "HttpOnly" not in csrf_header  # the client must be able to echo it

    async def test_refresh_token_is_never_returned_in_the_body(self, client, admin):
        body = (await login(client, admin.email, ADMIN_PASSWORD)).json()
        assert "refresh_token" not in body

    async def test_wrong_password_is_rejected(self, client, admin):
        response = await login(client, admin.email, "WrongPassword!2026")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"

    async def test_unknown_email_is_indistinguishable_from_wrong_password(self, client, admin):
        unknown = await login(client, "nobody@test.internal", "WrongPassword!2026")
        wrong = await login(client, admin.email, "WrongPassword!2026")
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json() == wrong.json()

    @pytest.mark.parametrize("status", [UserStatus.INACTIVE, UserStatus.SUSPENDED])
    async def test_non_active_account_cannot_sign_in(self, client, db, status):
        user = await create_user(
            db,
            email=f"{status.value.lower()}@test.internal",
            password=USER_PASSWORD,
            role_keys=["USER"],
            status=status,
        )
        response = await login(client, user.email, USER_PASSWORD)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "account_inactive"

    async def test_repeated_failures_lock_the_account(self, client, db, admin):
        for _ in range(settings.max_failed_logins):
            assert (await login(client, admin.email, "WrongPassword!2026")).status_code == 401

        # Even the *correct* password is refused while the lockout holds.
        response = await login(client, admin.email, ADMIN_PASSWORD)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "account_locked"

        refreshed = await refetch(db, User, admin.id)
        assert refreshed.locked_until is not None

    async def test_successful_login_clears_the_failure_counter(self, client, db, admin):
        await login(client, admin.email, "WrongPassword!2026")
        await login(client, admin.email, ADMIN_PASSWORD)

        refreshed = await refetch(db, User, admin.id)
        assert refreshed.failed_login_count == 0
        assert refreshed.last_login_at is not None


class TestFirstLoginPasswordChange:
    @pytest.fixture
    async def pending_user(self, db):
        return await create_user(
            db,
            email="pending@test.internal",
            password=USER_PASSWORD,
            role_keys=["USER"],
            must_change_password=True,
        )

    async def test_login_succeeds_but_flags_the_requirement(self, client, pending_user):
        body = (await login(client, pending_user.email, USER_PASSWORD)).json()
        assert body["must_change_password"] is True

    async def test_every_other_endpoint_is_blocked(self, client, pending_user):
        headers = await auth_headers(client, pending_user.email, USER_PASSWORD)
        response = await client.get("/api/v1/users", headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "password_change_required"

    async def test_the_change_endpoint_itself_stays_reachable(self, client, pending_user):
        headers = await auth_headers(client, pending_user.email, USER_PASSWORD)
        assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200

        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": USER_PASSWORD,
                "new_password": "Chosen!Password2026",
                "confirm_password": "Chosen!Password2026",
            },
        )
        assert response.status_code == 200
        assert response.json()["must_change_password"] is False

    async def test_requirement_is_cleared_and_access_granted(self, client, pending_user):
        headers = await auth_headers(client, pending_user.email, USER_PASSWORD)
        body = (
            await client.post(
                "/api/v1/auth/change-password",
                headers=headers,
                json={
                    "current_password": USER_PASSWORD,
                    "new_password": "Chosen!Password2026",
                    "confirm_password": "Chosen!Password2026",
                },
            )
        ).json()

        # The response carries fresh credentials, so the user continues seamlessly.
        new_headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert (await client.get("/api/v1/auth/me", headers=new_headers)).status_code == 200

        again = (await login(client, pending_user.email, "Chosen!Password2026")).json()
        assert again["must_change_password"] is False


class TestChangePassword:
    async def test_requires_the_correct_current_password(self, client, admin):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "NotMyPassword!2026",
                "new_password": "Another!Password2026",
                "confirm_password": "Another!Password2026",
            },
        )
        assert response.status_code == 422
        assert "current_password" in response.json()["error"]["details"]

    async def test_confirmation_must_match(self, client, admin):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": ADMIN_PASSWORD,
                "new_password": "Another!Password2026",
                "confirm_password": "Mismatched!Password2026",
            },
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "weak",
        ["short1!A", "alllowercase123!", "ALLUPPERCASE123!", "NoDigitsHere!!", "NoSymbols12345"],
    )
    async def test_policy_is_enforced(self, client, admin, weak):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": ADMIN_PASSWORD,
                "new_password": weak,
                "confirm_password": weak,
            },
        )
        assert response.status_code == 422

    async def test_new_password_cannot_repeat_the_current_one(self, client, admin):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": ADMIN_PASSWORD,
                "new_password": ADMIN_PASSWORD,
                "confirm_password": ADMIN_PASSWORD,
            },
        )
        assert response.status_code == 422

    async def test_recent_passwords_are_remembered(self, client, admin):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        second = "Second!Password2026"

        body = (
            await client.post(
                "/api/v1/auth/change-password",
                headers=headers,
                json={
                    "current_password": ADMIN_PASSWORD,
                    "new_password": second,
                    "confirm_password": second,
                },
            )
        ).json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}

        # Cycling straight back to the original is refused.
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": second,
                "new_password": ADMIN_PASSWORD,
                "confirm_password": ADMIN_PASSWORD,
            },
        )
        assert response.status_code == 422

    async def test_other_sessions_are_revoked(self, client, admin):
        first = (await login(client, admin.email, ADMIN_PASSWORD)).json()
        second = (await login(client, admin.email, ADMIN_PASSWORD)).json()

        changed = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {second['access_token']}"},
            json={
                "current_password": ADMIN_PASSWORD,
                "new_password": "Rotated!Password2026",
                "confirm_password": "Rotated!Password2026",
            },
        )
        assert changed.status_code == 200

        stale = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {first['access_token']}"}
        )
        assert stale.status_code == 401


class TestSessionLifecycle:
    async def test_me_requires_authentication(self, client):
        assert (await client.get("/api/v1/auth/me")).status_code == 401

    async def test_malformed_token_is_rejected(self, client):
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"

    async def test_refresh_rotates_the_token(self, client, admin, db):
        await login(client, admin.email, ADMIN_PASSWORD)
        csrf = client.cookies[settings.csrf_cookie_name]
        original_refresh = client.cookies[settings.refresh_cookie_name]

        response = await client.post(
            "/api/v1/auth/refresh", headers={settings.csrf_header_name: csrf}
        )
        assert response.status_code == 200
        assert client.cookies[settings.refresh_cookie_name] != original_refresh

    async def test_replaying_a_rotated_token_kills_the_whole_family(self, client, admin, db):
        await login(client, admin.email, ADMIN_PASSWORD)
        csrf = client.cookies[settings.csrf_cookie_name]
        stolen = client.cookies[settings.refresh_cookie_name]

        # Legitimate rotation.
        assert (
            await client.post("/api/v1/auth/refresh", headers={settings.csrf_header_name: csrf})
        ).status_code == 200

        # Rotation issues a new CSRF token too, so use the current one -- the
        # point of this test is the refresh token, not CSRF.
        csrf = client.cookies[settings.csrf_cookie_name]

        # An attacker replays the token they captured earlier.
        client.cookies.set(settings.refresh_cookie_name, stolen, path="/api/v1/auth")
        replay = await client.post(
            "/api/v1/auth/refresh", headers={settings.csrf_header_name: csrf}
        )
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "session_revoked"

        active = (
            await db.execute(
                sa.select(sa.func.count())
                .select_from(Session)
                .where(Session.user_id == admin.id, Session.revoked_at.is_(None))
            )
        ).scalar_one()
        assert active == 0  # every descendant revoked too

    async def test_refresh_requires_a_matching_csrf_header(self, client, admin):
        await login(client, admin.email, ADMIN_PASSWORD)

        assert (await client.post("/api/v1/auth/refresh")).status_code == 403
        assert (
            await client.post(
                "/api/v1/auth/refresh", headers={settings.csrf_header_name: "wrong"}
            )
        ).status_code == 403

    async def test_logout_revokes_the_session(self, client, admin):
        body = (await login(client, admin.email, ADMIN_PASSWORD)).json()
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        csrf = client.cookies[settings.csrf_cookie_name]

        response = await client.post(
            "/api/v1/auth/logout", headers={**headers, settings.csrf_header_name: csrf}
        )
        assert response.status_code == 200

        assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401

    async def test_deactivating_a_user_invalidates_their_live_session(
        self, client, db, guest, superadmin
    ):
        from tests.conftest import SUPERADMIN_PASSWORD

        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        assert (await client.get("/api/v1/auth/me", headers=guest_headers)).status_code == 200

        admin_headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        response = await client.patch(
            f"/api/v1/users/{guest.id}", headers=admin_headers, json={"status": "INACTIVE"}
        )
        assert response.status_code == 200

        # No waiting for token expiry: status is re-checked on every request.
        assert (await client.get("/api/v1/auth/me", headers=guest_headers)).status_code == 401


class TestAuditTrail:
    async def test_login_and_failure_are_recorded(self, client, db, admin):
        from app.models import AuditLog

        await login(client, admin.email, ADMIN_PASSWORD)
        await login(client, admin.email, "WrongPassword!2026")

        actions = (
            await db.execute(sa.select(AuditLog.action).where(AuditLog.actor_user_id == admin.id))
        ).scalars().all()
        assert AuditAction.LOGIN_SUCCESS in actions
        assert AuditAction.LOGIN_FAILED in actions

    async def test_passwords_never_reach_the_audit_context(self, client, db, admin):
        from app.models import AuditLog

        await login(client, admin.email, ADMIN_PASSWORD)
        rows = (await db.execute(sa.select(AuditLog))).scalars().all()
        blob = " ".join(str(row.context) for row in rows if row.context)
        assert ADMIN_PASSWORD not in blob
