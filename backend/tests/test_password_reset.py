"""Forgot-password and reset-token security."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core.config import settings
from app.core.security import hash_token
from app.models import PasswordResetToken, Session
from app.models.enums import AuditAction
from tests.conftest import GUEST_PASSWORD, auth_headers, login, read_outbox_token

NEW_PASSWORD = "Recovered!Pass2026"


async def request_reset(client, email: str):
    return await client.post("/api/v1/auth/forgot-password", json={"email": email})


class TestForgotPassword:
    async def test_request_for_a_known_address_is_accepted(self, client, guest):
        response = await request_reset(client, guest.email)
        assert response.status_code == 202

    async def test_response_is_identical_for_unknown_addresses(self, client, guest):
        known = await request_reset(client, guest.email)
        unknown = await request_reset(client, "no-such-person@test.internal")
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()

    async def test_no_token_is_created_for_an_unknown_address(self, client, db):
        await request_reset(client, "no-such-person@test.internal")
        db.expire_all()
        count = (
            await db.execute(sa.select(sa.func.count()).select_from(PasswordResetToken))
        ).scalar_one()
        assert count == 0

    async def test_inactive_accounts_get_no_token(self, client, db, guest):
        from app.models import User
        from app.models.enums import UserStatus

        guest_id = guest.id
        await db.execute(
            sa.update(User).where(User.id == guest_id).values(status=UserStatus.INACTIVE)
        )
        await db.commit()

        response = await request_reset(client, guest.email)
        assert response.status_code == 202  # still indistinguishable

        db.expire_all()
        count = (
            await db.execute(sa.select(sa.func.count()).select_from(PasswordResetToken))
        ).scalar_one()
        assert count == 0

    async def test_only_a_hash_of_the_token_is_stored(self, client, db, guest):
        await request_reset(client, guest.email)
        raw = read_outbox_token(guest.email)
        assert raw

        db.expire_all()
        row = (await db.execute(sa.select(PasswordResetToken))).scalar_one()
        assert row.token_hash != raw
        assert row.token_hash == hash_token(raw)
        assert len(row.token_hash) == 64  # SHA-256 hex

    async def test_requesting_again_invalidates_the_previous_link(self, client, db, guest):
        await request_reset(client, guest.email)
        first = read_outbox_token(guest.email)
        await request_reset(client, guest.email)
        second = read_outbox_token(guest.email)
        assert first != second

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": first, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert response.status_code == 422

    async def test_request_is_audited(self, client, db, guest):
        from app.models import AuditLog

        await request_reset(client, guest.email)
        db.expire_all()
        actions = (await db.execute(sa.select(AuditLog.action))).scalars().all()
        assert AuditAction.PASSWORD_RESET_REQUESTED in actions


class TestResetPassword:
    async def test_a_valid_token_sets_the_new_password(self, client, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert response.status_code == 200
        assert (await login(client, guest.email, NEW_PASSWORD)).status_code == 200

    async def test_the_old_password_stops_working(self, client, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert (await login(client, guest.email, GUEST_PASSWORD)).status_code == 401

    async def test_a_token_cannot_be_reused(self, client, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)

        first = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": token,
                "new_password": "Different!Pass2026",
                "confirm_password": "Different!Pass2026",
            },
        )
        assert second.status_code == 422
        assert second.json()["error"]["code"] == "invalid_reset_token"

    async def test_an_expired_token_is_refused(self, client, db, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)

        db.expire_all()
        await db.execute(
            sa.update(PasswordResetToken).values(
                expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1)
            )
        )
        await db.commit()

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert response.status_code == 422

    async def test_an_unknown_token_is_refused(self, client):
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "x" * 64,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_reset_token"

    async def test_confirmation_must_match(self, client, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": token,
                "new_password": NEW_PASSWORD,
                "confirm_password": "Mismatch!Pass2026",
            },
        )
        assert response.status_code == 422

    async def test_the_password_policy_still_applies(self, client, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "weak", "confirm_password": "weak"},
        )
        assert response.status_code == 422

    async def test_reset_revokes_every_existing_session(self, client, db, guest):
        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        assert (await client.get("/api/v1/auth/me", headers=guest_headers)).status_code == 200

        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )

        assert (await client.get("/api/v1/auth/me", headers=guest_headers)).status_code == 401

        db.expire_all()
        active = (
            await db.execute(
                sa.select(sa.func.count())
                .select_from(Session)
                .where(Session.revoked_at.is_(None))
            )
        ).scalar_one()
        assert active == 0

    async def test_reset_does_not_leave_the_change_requirement_set(self, client, guest):
        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        body = (await login(client, guest.email, NEW_PASSWORD)).json()
        assert body["must_change_password"] is False

    async def test_completion_is_audited(self, client, db, guest):
        from app.models import AuditLog

        await request_reset(client, guest.email)
        token = read_outbox_token(guest.email)
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        db.expire_all()
        actions = (await db.execute(sa.select(AuditLog.action))).scalars().all()
        assert AuditAction.PASSWORD_RESET_COMPLETED in actions


class TestResetEmail:
    async def test_the_link_points_at_the_frontend_reset_route(self, client, guest):
        from pathlib import Path

        await request_reset(client, guest.email)
        files = sorted(Path(settings.dev_outbox_dir).glob("*.txt"))
        body = files[-1].read_text()
        assert f"{settings.frontend_base_url}/reset-password?token=" in body

    async def test_the_token_is_not_written_to_the_application_log(self, client, guest, caplog):
        import logging

        with caplog.at_level(logging.INFO):
            await request_reset(client, guest.email)

        token = read_outbox_token(guest.email)
        assert token
        assert token not in caplog.text
