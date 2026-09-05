"""User administration: creation, roles, status and admin resets."""

from __future__ import annotations

import pytest

from app.models import User
from app.models.enums import AuditAction, UserStatus
from tests.conftest import (
    ADMIN_PASSWORD,
    GUEST_PASSWORD,
    SUPERADMIN_PASSWORD,
    USER_PASSWORD,
    auth_headers,
    login,
    refetch,
)


@pytest.fixture
async def admin_headers(client, admin):
    return await auth_headers(client, admin.email, ADMIN_PASSWORD)


@pytest.fixture
async def superadmin_headers(client, superadmin):
    return await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)


NEW_USER = {
    "email": "created@test.internal",
    "first_name": "Created",
    "last_name": "Person",
    "role_keys": ["USER"],
}


class TestCreateUser:
    async def test_admin_can_create_a_user(self, client, admin_headers):
        response = await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        assert response.status_code == 201

        body = response.json()
        assert body["user"]["email"] == "created@test.internal"
        assert [role["key"] for role in body["user"]["roles"]] == ["USER"]

    async def test_created_user_must_change_password_on_first_login(self, client, admin_headers):
        body = (
            await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        ).json()
        assert body["user"]["must_change_password"] is True

        # The generated password works, and immediately forces a change.
        session = (await login(client, NEW_USER["email"], body["temporary_password"])).json()
        assert session["must_change_password"] is True

    async def test_temporary_password_satisfies_the_policy(self, client, admin_headers):
        from app.core.security import validate_password_strength

        body = (
            await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        ).json()
        assert validate_password_strength(body["temporary_password"]) == []

    async def test_password_is_hashed_not_stored(self, client, db, admin_headers):
        body = (
            await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        ).json()
        db.expire_all()
        import sqlalchemy as sa

        stored = (
            await db.execute(sa.select(User).where(User.email == NEW_USER["email"]))
        ).scalar_one()
        assert stored.password_hash != body["temporary_password"]
        assert stored.password_hash.startswith("$argon2id$")

    async def test_email_is_normalised_to_lowercase(self, client, admin_headers):
        response = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={**NEW_USER, "email": "MiXeD.CaSe@Test.Internal"},
        )
        assert response.json()["user"]["email"] == "mixed.case@test.internal"

    async def test_duplicate_email_is_rejected(self, client, admin_headers):
        await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        response = await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "email_taken"

    async def test_duplicate_detection_ignores_case(self, client, admin_headers):
        await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        response = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={**NEW_USER, "email": NEW_USER["email"].upper()},
        )
        assert response.status_code == 409

    async def test_invalid_email_is_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/users", headers=admin_headers, json={**NEW_USER, "email": "not-an-email"}
        )
        assert response.status_code == 422

    async def test_unknown_role_is_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/users", headers=admin_headers, json={**NEW_USER, "role_keys": ["WIZARD"]}
        )
        assert response.status_code == 422

    async def test_multiple_roles_can_be_assigned_at_creation(self, client, admin_headers):
        response = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={**NEW_USER, "role_keys": ["USER", "GUEST"]},
        )
        assert sorted(r["key"] for r in response.json()["user"]["roles"]) == ["GUEST", "USER"]

    async def test_creation_is_audited(self, client, db, admin, admin_headers):
        import sqlalchemy as sa

        from app.models import AuditLog

        # Read the id before expiring: an expired instance would try to lazy-load.
        admin_id = admin.id
        await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        db.expire_all()
        actions = (
            await db.execute(sa.select(AuditLog.action).where(AuditLog.actor_user_id == admin_id))
        ).scalars().all()
        assert AuditAction.USER_CREATED in actions


class TestCreateUserAuthorization:
    async def test_anonymous_cannot_create(self, client):
        assert (await client.post("/api/v1/users", json=NEW_USER)).status_code == 401

    async def test_guest_cannot_create(self, client, guest):
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        response = await client.post("/api/v1/users", headers=headers, json=NEW_USER)
        assert response.status_code == 403

    async def test_standard_user_cannot_create(self, client, normal_user):
        """USER has READ_ONLY on Access Management: it may look, not write."""
        headers = await auth_headers(client, normal_user.email, USER_PASSWORD)
        assert (await client.get("/api/v1/users", headers=headers)).status_code == 200
        response = await client.post("/api/v1/users", headers=headers, json=NEW_USER)
        assert response.status_code == 403

    async def test_admin_cannot_grant_superadmin(self, client, admin_headers):
        response = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={**NEW_USER, "role_keys": ["SUPER_ADMIN"]},
        )
        assert response.status_code == 403

    async def test_superadmin_can_grant_superadmin(self, client, superadmin_headers):
        response = await client.post(
            "/api/v1/users",
            headers=superadmin_headers,
            json={**NEW_USER, "role_keys": ["SUPER_ADMIN"]},
        )
        assert response.status_code == 201


class TestListUsers:
    async def test_listing_is_paginated(self, client, admin_headers, admin):
        for index in range(3):
            await client.post(
                "/api/v1/users",
                headers=admin_headers,
                json={**NEW_USER, "email": f"user{index}@test.internal"},
            )

        body = (await client.get("/api/v1/users?limit=2", headers=admin_headers)).json()
        assert len(body["items"]) == 2
        assert body["total"] == 4  # 3 created + the admin

    async def test_search_matches_name_and_email(self, client, admin_headers):
        await client.post("/api/v1/users", headers=admin_headers, json=NEW_USER)
        body = (
            await client.get("/api/v1/users?search=created", headers=admin_headers)
        ).json()
        assert body["total"] == 1

    async def test_filter_by_role(self, client, admin_headers, guest):
        body = (
            await client.get("/api/v1/users?role_key=GUEST", headers=admin_headers)
        ).json()
        assert [item["email"] for item in body["items"]] == [guest.email]

    async def test_password_hash_is_never_serialised(self, client, admin_headers):
        body = (await client.get("/api/v1/users", headers=admin_headers)).json()
        assert "password_hash" not in body["items"][0]


class TestRoleAssignment:
    async def test_roles_can_be_replaced(self, client, admin_headers, guest):
        response = await client.put(
            f"/api/v1/users/{guest.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["USER", "GUEST"]},
        )
        assert response.status_code == 200
        assert sorted(r["key"] for r in response.json()["roles"]) == ["GUEST", "USER"]

    async def test_roles_can_be_cleared(self, client, admin_headers, guest):
        response = await client.put(
            f"/api/v1/users/{guest.id}/roles", headers=admin_headers, json={"role_keys": []}
        )
        assert response.json()["roles"] == []

    async def test_admin_cannot_self_promote_to_superadmin(self, client, admin, admin_headers):
        response = await client.put(
            f"/api/v1/users/{admin.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["ADMIN", "SUPER_ADMIN"]},
        )
        assert response.status_code == 403

    async def test_admin_cannot_modify_a_superadmin(self, client, admin_headers, superadmin):
        response = await client.put(
            f"/api/v1/users/{superadmin.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["USER"]},
        )
        assert response.status_code == 403

    async def test_nobody_can_change_their_own_roles(
        self, client, superadmin, superadmin_headers
    ):
        """Self-assignment is the most direct escalation path, so it is refused
        outright -- for everyone, in both directions."""
        response = await client.put(
            f"/api/v1/users/{superadmin.id}/roles",
            headers=superadmin_headers,
            json={"role_keys": ["ADMIN"]},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "self_role_change_denied"

    async def test_admin_cannot_grant_themselves_more_roles(
        self, client, admin, admin_headers
    ):
        response = await client.put(
            f"/api/v1/users/{admin.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["ADMIN", "USER"]},
        )
        assert response.status_code == 403


class TestUpdateUser:
    async def test_profile_fields_can_be_updated(self, client, admin_headers, guest):
        response = await client.patch(
            f"/api/v1/users/{guest.id}",
            headers=admin_headers,
            json={"first_name": "Renamed", "job_title": "Engineer"},
        )
        assert response.status_code == 200
        assert response.json()["first_name"] == "Renamed"
        assert response.json()["job_title"] == "Engineer"

    async def test_status_can_be_changed(self, client, admin_headers, guest):
        response = await client.patch(
            f"/api/v1/users/{guest.id}", headers=admin_headers, json={"status": "SUSPENDED"}
        )
        assert response.json()["status"] == "SUSPENDED"

    async def test_admin_cannot_change_their_own_status(self, client, admin, admin_headers):
        response = await client.patch(
            f"/api/v1/users/{admin.id}", headers=admin_headers, json={"status": "INACTIVE"}
        )
        assert response.status_code == 422

    async def test_unknown_user_returns_404(self, client, admin_headers):
        response = await client.patch(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
            json={"first_name": "Ghost"},
        )
        assert response.status_code == 404


class TestAdminPasswordReset:
    async def test_admin_issues_a_working_temporary_password(
        self, client, db, admin_headers, guest
    ):
        response = await client.post(
            f"/api/v1/users/{guest.id}/reset-password", headers=admin_headers
        )
        assert response.status_code == 200
        temporary = response.json()["temporary_password"]

        assert (await login(client, guest.email, GUEST_PASSWORD)).status_code == 401
        session = await login(client, guest.email, temporary)
        assert session.status_code == 200
        assert session.json()["must_change_password"] is True

    async def test_reset_revokes_existing_sessions(self, client, admin_headers, guest):
        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        await client.post(f"/api/v1/users/{guest.id}/reset-password", headers=admin_headers)
        assert (await client.get("/api/v1/auth/me", headers=guest_headers)).status_code == 401

    async def test_reset_clears_an_account_lockout(self, client, db, admin_headers, guest):
        from app.core.config import settings

        for _ in range(settings.max_failed_logins):
            await login(client, guest.email, "WrongPassword!2026")
        assert (await refetch(db, User, guest.id)).locked_until is not None

        await client.post(f"/api/v1/users/{guest.id}/reset-password", headers=admin_headers)
        assert (await refetch(db, User, guest.id)).locked_until is None
