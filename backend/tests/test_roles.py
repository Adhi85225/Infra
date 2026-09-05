"""Role management: creating, editing and deleting roles, and their permissions.

Covers the capability added after Phase 1: administrators define custom roles
(``AssetManager``, ``ReportViewer``, …) with module-level permissions, without
any code change.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.models.enums import AccessLevel, AuditAction
from app.services import permission_service, role_service
from tests.conftest import (
    ADMIN_PASSWORD,
    GUEST_PASSWORD,
    SUPERADMIN_PASSWORD,
    USER_PASSWORD,
    auth_headers,
    create_user,
)


@pytest.fixture
async def admin_headers(client, admin):
    return await auth_headers(client, admin.email, ADMIN_PASSWORD)


@pytest.fixture
async def superadmin_headers(client, superadmin):
    return await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)


ASSET_MANAGER = {
    "name": "Asset Manager",
    "description": "Owns the hardware register.",
    "permissions": {
        "DASHBOARD": "COMPLETE",
        "TEAM_MEMBERS": "READ_ONLY",
        "ASSET_INVENTORY": "COMPLETE",
        "DAS_ONBOARDING": "NONE",
        "ZABBIX": "READ_ONLY",
        "REPORTS": "READ_ONLY",
        "SETTINGS": "NONE",
    },
}


class TestKeyDerivation:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Asset Manager", "ASSET_MANAGER"),
            ("ReportViewer", "REPORTVIEWER"),
            ("DAS  Operator", "DAS_OPERATOR"),
            ("Cloud-Admin", "CLOUD_ADMIN"),
            ("network admin 2", "NETWORK_ADMIN_2"),
        ],
    )
    def test_names_become_machine_keys(self, name, expected):
        assert role_service.derive_key(name) == expected


class TestCreateRole:
    async def test_admin_can_create_a_custom_role(self, client, admin_headers):
        response = await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        assert response.status_code == 201

        body = response.json()
        assert body["name"] == "Asset Manager"
        assert body["key"] == "ASSET_MANAGER"
        assert body["is_system"] is False
        assert body["is_deletable"] is True
        assert body["user_count"] == 0

    async def test_permissions_are_stored_as_given(self, client, admin_headers):
        body = (
            await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        ).json()
        assert body["permissions"]["ASSET_INVENTORY"] == "COMPLETE"
        assert body["permissions"]["ZABBIX"] == "READ_ONLY"
        assert body["permissions"]["DAS_ONBOARDING"] == "NONE"
        assert body["permissions"]["SETTINGS"] == "NONE"

    async def test_modules_not_listed_default_to_no_access(self, client, admin_headers):
        body = (
            await client.post(
                "/api/v1/roles",
                headers=admin_headers,
                json={"name": "Narrow Role", "permissions": {"DASHBOARD": "READ_ONLY"}},
            )
        ).json()
        assert body["permissions"]["DASHBOARD"] == "READ_ONLY"
        assert body["permissions"]["NEXUS"] == "NONE"

    async def test_an_explicit_key_is_accepted(self, client, admin_headers):
        body = (
            await client.post(
                "/api/v1/roles",
                headers=admin_headers,
                json={"name": "Network Admin", "key": "NET_ADMIN", "permissions": {}},
            )
        ).json()
        assert body["key"] == "NET_ADMIN"

    async def test_duplicate_key_is_rejected(self, client, admin_headers):
        await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        response = await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "role_key_taken"

    async def test_colliding_with_a_system_role_is_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/roles", headers=admin_headers, json={"name": "Admin", "permissions": {}}
        )
        assert response.status_code == 409

    async def test_invalid_key_is_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Bad", "key": "lower case!", "permissions": {}},
        )
        assert response.status_code == 422

    async def test_unknown_module_is_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Ghost Role", "permissions": {"NOT_A_MODULE": "COMPLETE"}},
        )
        assert response.status_code == 422

    async def test_blank_name_is_rejected(self, client, admin_headers):
        response = await client.post(
            "/api/v1/roles", headers=admin_headers, json={"name": "   ", "permissions": {}}
        )
        assert response.status_code == 422

    async def test_creation_is_audited(self, client, db, admin, admin_headers):
        from app.models import AuditLog

        admin_id = admin.id
        await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        db.expire_all()
        actions = (
            await db.execute(sa.select(AuditLog.action).where(AuditLog.actor_user_id == admin_id))
        ).scalars().all()
        assert AuditAction.ROLE_CREATED in actions


class TestRoleAuthorization:
    async def test_anonymous_cannot_create_a_role(self, client):
        assert (await client.post("/api/v1/roles", json=ASSET_MANAGER)).status_code == 401

    async def test_guest_cannot_read_or_create_roles(self, client, guest):
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        assert (await client.get("/api/v1/roles", headers=headers)).status_code == 403
        assert (
            await client.post("/api/v1/roles", headers=headers, json=ASSET_MANAGER)
        ).status_code == 403

    async def test_read_only_user_can_view_but_not_create(self, client, normal_user):
        headers = await auth_headers(client, normal_user.email, USER_PASSWORD)
        assert (await client.get("/api/v1/roles", headers=headers)).status_code == 200
        assert (
            await client.post("/api/v1/roles", headers=headers, json=ASSET_MANAGER)
        ).status_code == 403

    async def test_a_role_cannot_grant_more_than_its_creator_holds(
        self, client, db, superadmin, superadmin_headers
    ):
        """The key escalation guard.

        A user whose only real power is managing access must not be able to mint
        a role more powerful than themselves and hand it to someone else.
        """
        # A custom role with COMPLETE on Access Management but nothing else.
        await client.post(
            "/api/v1/roles",
            headers=superadmin_headers,
            json={
                "name": "Gatekeeper",
                "permissions": {"ACCESS_MANAGEMENT": "COMPLETE", "DASHBOARD": "READ_ONLY"},
            },
        )
        gatekeeper = await create_user(
            db,
            email="gatekeeper@test.internal",
            password=USER_PASSWORD,
            role_keys=["GATEKEEPER"],
        )
        headers = await auth_headers(client, gatekeeper.email, USER_PASSWORD)

        response = await client.post(
            "/api/v1/roles",
            headers=headers,
            json={"name": "Sneaky Power", "permissions": {"SETTINGS": "COMPLETE"}},
        )
        assert response.status_code == 403
        assert "more access than you have" in response.json()["error"]["message"]

    async def test_admin_may_grant_what_admin_holds(self, client, admin_headers):
        response = await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Settings Helper", "permissions": {"SETTINGS": "COMPLETE"}},
        )
        assert response.status_code == 201


class TestEditRole:
    @pytest.fixture
    async def custom_role_id(self, client, admin_headers) -> str:
        body = (
            await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        ).json()
        return body["id"]

    async def test_name_and_description_can_change(self, client, admin_headers, custom_role_id):
        response = await client.patch(
            f"/api/v1/roles/{custom_role_id}",
            headers=admin_headers,
            json={"name": "Asset Lead", "description": "Updated."},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Asset Lead"
        assert response.json()["description"] == "Updated."

    async def test_the_key_is_immutable(self, client, admin_headers, custom_role_id):
        body = (
            await client.patch(
                f"/api/v1/roles/{custom_role_id}",
                headers=admin_headers,
                json={"name": "Totally Different"},
            )
        ).json()
        assert body["key"] == "ASSET_MANAGER"

    async def test_permissions_can_be_updated(self, client, admin_headers, custom_role_id):
        response = await client.put(
            f"/api/v1/roles/{custom_role_id}/permissions",
            headers=admin_headers,
            json={"permissions": {"NEXUS": "COMPLETE", "ASSET_INVENTORY": "READ_ONLY"}},
        )
        assert response.status_code == 200
        assert response.json()["permissions"]["NEXUS"] == "COMPLETE"
        assert response.json()["permissions"]["ASSET_INVENTORY"] == "READ_ONLY"

    async def test_unknown_role_returns_404(self, client, admin_headers):
        response = await client.patch(
            "/api/v1/roles/00000000-0000-0000-0000-000000000000",
            headers=admin_headers,
            json={"name": "Nope"},
        )
        assert response.status_code == 404


class TestProtectedSystemRoles:
    async def _role_id(self, client, headers, key: str) -> str:
        roles = (await client.get("/api/v1/roles", headers=headers)).json()
        return next(role["id"] for role in roles if role["key"] == key)

    @pytest.mark.parametrize("key", ["SUPER_ADMIN", "ADMIN", "USER", "GUEST"])
    async def test_seeded_roles_are_not_deletable(self, client, superadmin_headers, key):
        role_id = await self._role_id(client, superadmin_headers, key)
        response = await client.delete(f"/api/v1/roles/{role_id}", headers=superadmin_headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "role_protected"

    @pytest.mark.parametrize("key", ["SUPER_ADMIN", "ADMIN", "USER", "GUEST"])
    async def test_seeded_roles_are_flagged_as_protected(self, client, superadmin_headers, key):
        roles = (await client.get("/api/v1/roles", headers=superadmin_headers)).json()
        role = next(r for r in roles if r["key"] == key)
        assert role["is_system"] is True
        assert role["is_deletable"] is False

    async def test_superadmin_permissions_cannot_be_edited(self, client, superadmin_headers):
        role_id = await self._role_id(client, superadmin_headers, "SUPER_ADMIN")
        response = await client.put(
            f"/api/v1/roles/{role_id}/permissions",
            headers=superadmin_headers,
            json={"permissions": {"SETTINGS": "NONE"}},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "role_immutable"

    async def test_admin_cannot_edit_the_admin_role(self, client, admin_headers):
        role_id = await self._role_id(client, admin_headers, "ADMIN")
        response = await client.patch(
            f"/api/v1/roles/{role_id}", headers=admin_headers, json={"name": "Renamed"}
        )
        assert response.status_code == 403

    async def test_the_four_seeded_roles_still_exist(self, client, superadmin_headers):
        roles = (await client.get("/api/v1/roles", headers=superadmin_headers)).json()
        keys = {role["key"] for role in roles}
        assert {"SUPER_ADMIN", "ADMIN", "USER", "GUEST"} <= keys


class TestDeleteRole:
    async def test_an_unused_custom_role_can_be_deleted(self, client, admin_headers):
        role_id = (
            await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        ).json()["id"]

        assert (
            await client.delete(f"/api/v1/roles/{role_id}", headers=admin_headers)
        ).status_code == 200
        assert (
            await client.get(f"/api/v1/roles/{role_id}", headers=admin_headers)
        ).status_code == 404

    async def test_a_role_in_use_is_refused(self, client, db, admin_headers):
        role_id = (
            await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        ).json()["id"]
        await create_user(
            db,
            email="holder@test.internal",
            password=USER_PASSWORD,
            role_keys=["ASSET_MANAGER"],
        )

        response = await client.delete(f"/api/v1/roles/{role_id}", headers=admin_headers)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "role_in_use"

    async def test_user_count_is_reported(self, client, db, admin_headers):
        await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        await create_user(
            db, email="holder@test.internal", password=USER_PASSWORD, role_keys=["ASSET_MANAGER"]
        )

        roles = (await client.get("/api/v1/roles", headers=admin_headers)).json()
        role = next(r for r in roles if r["key"] == "ASSET_MANAGER")
        assert role["user_count"] == 1


class TestCustomRoleInAction:
    """End-to-end: a custom role actually governs what its holder can reach."""

    @pytest.fixture
    async def asset_manager(self, client, db, admin_headers):
        await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        return await create_user(
            db,
            email="assetmgr@test.internal",
            password=USER_PASSWORD,
            role_keys=["ASSET_MANAGER"],
        )

    async def test_effective_permissions_match_the_role(self, db, asset_manager):
        permissions = await permission_service.resolve_permissions(
            db, asset_manager, use_cache=False
        )
        assert permissions["ASSET_INVENTORY"].access_level is AccessLevel.COMPLETE
        assert permissions["ZABBIX"].access_level is AccessLevel.READ_ONLY
        assert permissions["DAS_ONBOARDING"].access_level is AccessLevel.NONE
        assert permissions["SETTINGS"].access_level is AccessLevel.NONE

    async def test_the_holder_sees_only_permitted_modules(self, client, asset_manager):
        headers = await auth_headers(client, asset_manager.email, USER_PASSWORD)
        body = (await client.get("/api/v1/auth/me", headers=headers)).json()

        visible = {p["module_key"] for p in body["permissions"] if p["can_view"]}
        assert "ASSET_INVENTORY" in visible
        assert "ZABBIX" in visible
        assert "REPORTS" in visible
        assert "DAS_ONBOARDING" not in visible
        assert "SETTINGS" not in visible
        assert "NEXUS" not in visible

    async def test_the_holder_is_blocked_from_access_management(self, client, asset_manager):
        headers = await auth_headers(client, asset_manager.email, USER_PASSWORD)
        assert (await client.get("/api/v1/users", headers=headers)).status_code == 403

    async def test_a_new_role_needs_no_deployment(self, client, db, admin_headers):
        """The point of the feature: define a role, assign it, access changes."""
        await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Report Viewer", "permissions": {"REPORTS": "READ_ONLY"}},
        )
        viewer = await create_user(
            db, email="viewer@test.internal", password=USER_PASSWORD, role_keys=["REPORT_VIEWER"]
        )
        permissions = await permission_service.resolve_permissions(db, viewer, use_cache=False)
        assert permissions["REPORTS"].access_level is AccessLevel.READ_ONLY
        assert permissions["ASSET_INVENTORY"].access_level is AccessLevel.NONE


class TestMultipleCustomRoles:
    async def test_effective_access_unions_across_custom_roles(self, client, db, admin_headers):
        await client.post("/api/v1/roles", headers=admin_headers, json=ASSET_MANAGER)
        await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={
                "name": "Report Viewer",
                "permissions": {"REPORTS": "READ_ONLY", "NEXUS": "READ_ONLY"},
            },
        )

        john = await create_user(
            db,
            email="john@test.internal",
            password=USER_PASSWORD,
            role_keys=["USER", "ASSET_MANAGER", "REPORT_VIEWER"],
        )
        permissions = await permission_service.resolve_permissions(db, john, use_cache=False)

        # Highest level wins, across all three roles.
        assert permissions["ASSET_INVENTORY"].access_level is AccessLevel.COMPLETE
        assert permissions["REPORTS"].access_level is AccessLevel.READ_ONLY
        assert permissions["NEXUS"].access_level is AccessLevel.READ_ONLY
        # USER contributes READ_ONLY where the custom roles grant nothing.
        assert permissions["DAS_ONBOARDING"].access_level is AccessLevel.READ_ONLY
        # Nothing grants Settings.
        assert permissions["SETTINGS"].access_level is AccessLevel.NONE

    async def test_a_custom_role_can_lift_access_a_base_role_lacks(
        self, client, db, admin_headers
    ):
        await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Settings Owner", "permissions": {"SETTINGS": "COMPLETE"}},
        )
        # GUEST alone has no Settings access at all.
        both = await create_user(
            db,
            email="both@test.internal",
            password=USER_PASSWORD,
            role_keys=["GUEST", "SETTINGS_OWNER"],
        )
        permissions = await permission_service.resolve_permissions(db, both, use_cache=False)
        assert permissions["SETTINGS"].access_level is AccessLevel.COMPLETE

    async def test_role_changes_take_effect_immediately(self, client, db, admin_headers, guest):
        """No sign-out required: the permission cache is invalidated on change."""
        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        before = (await client.get("/api/v1/auth/me", headers=guest_headers)).json()
        assert all(p["access_level"] == "NONE" for p in before["permissions"] if p["module_key"] == "SETTINGS")

        await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Settings Owner", "permissions": {"SETTINGS": "COMPLETE"}},
        )
        roles = (await client.get("/api/v1/roles", headers=admin_headers)).json()
        assert any(r["key"] == "SETTINGS_OWNER" for r in roles)

        await client.put(
            f"/api/v1/users/{guest.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["GUEST", "SETTINGS_OWNER"]},
        )

        after = (await client.get("/api/v1/auth/me", headers=guest_headers)).json()
        levels = {p["module_key"]: p["access_level"] for p in after["permissions"]}
        assert levels["SETTINGS"] == "COMPLETE"


class TestAssignableAccessLevels:
    async def test_the_api_publishes_the_assignable_levels(self, client, admin_headers):
        response = await client.get(
            "/api/v1/roles/assignable-access-levels", headers=admin_headers
        )
        assert response.status_code == 200
        # Three levels, as specified. GUEST is legacy and not offered.
        assert response.json() == ["NONE", "READ_ONLY", "COMPLETE"]
