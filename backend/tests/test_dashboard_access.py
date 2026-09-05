"""Dashboard visibility and server-side route/API protection.

Two separate guarantees are asserted here:

1. The permission payload the dashboard renders from lists exactly the modules
   the user may open (visibility).
2. The API refuses unauthorised modules regardless of what the client sends
   (enforcement). Hiding a card is never the security boundary.
"""

from __future__ import annotations

import pytest

from tests.conftest import (
    ADMIN_PASSWORD,
    GUEST_PASSWORD,
    SUPERADMIN_PASSWORD,
    USER_PASSWORD,
    auth_headers,
    create_user,
)

ALL_MODULES = {
    "DASHBOARD",
    "TEAM_MEMBERS",
    "ACCESS_MANAGEMENT",
    "ASSET_INVENTORY",
    "DAS_ONBOARDING",
    "ILO_INVENTORY",
    "ZABBIX",
    "NEXUS",
    "CLOUD_INFORMATION",
    "TASK_UPDATES",
    "REPORTS",
    "SETTINGS",
}


async def visible_modules(client, email: str, password: str) -> set[str]:
    """The modules the dashboard would render for this user."""
    headers = await auth_headers(client, email, password)
    body = (await client.get("/api/v1/auth/me", headers=headers)).json()
    return {p["module_key"] for p in body["permissions"] if p["can_view"]}


class TestDashboardVisibility:
    async def test_superadmin_sees_everything(self, client, superadmin):
        assert await visible_modules(
            client, superadmin.email, SUPERADMIN_PASSWORD
        ) == ALL_MODULES

    async def test_admin_sees_everything(self, client, admin):
        assert await visible_modules(client, admin.email, ADMIN_PASSWORD) == ALL_MODULES

    async def test_user_does_not_see_settings(self, client, normal_user):
        visible = await visible_modules(client, normal_user.email, USER_PASSWORD)
        assert "SETTINGS" not in visible
        assert "DASHBOARD" in visible

    async def test_guest_sees_neither_settings_nor_access_management(self, client, guest):
        visible = await visible_modules(client, guest.email, GUEST_PASSWORD)
        assert "SETTINGS" not in visible
        assert "ACCESS_MANAGEMENT" not in visible
        assert "DASHBOARD" in visible

    async def test_a_user_with_no_roles_sees_nothing(self, client, db):
        nobody = await create_user(
            db, email="nobody@test.internal", password=USER_PASSWORD, role_keys=[]
        )
        assert await visible_modules(client, nobody.email, USER_PASSWORD) == set()

    async def test_custom_role_sees_exactly_its_grants(self, client, db, admin):
        """The worked example from the requirements."""
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        await client.post(
            "/api/v1/roles",
            headers=headers,
            json={
                "name": "Field Engineer",
                "permissions": {
                    "DASHBOARD": "COMPLETE",
                    "ASSET_INVENTORY": "COMPLETE",
                    "ZABBIX": "READ_ONLY",
                    "REPORTS": "READ_ONLY",
                    "NEXUS": "NONE",
                    "CLOUD_INFORMATION": "NONE",
                },
            },
        )
        engineer = await create_user(
            db,
            email="engineer@test.internal",
            password=USER_PASSWORD,
            role_keys=["FIELD_ENGINEER"],
        )

        visible = await visible_modules(client, engineer.email, USER_PASSWORD)
        assert visible == {"DASHBOARD", "ASSET_INVENTORY", "ZABBIX", "REPORTS"}
        assert "NEXUS" not in visible
        assert "CLOUD_INFORMATION" not in visible

    async def test_multiple_roles_union_their_visibility(self, client, db, admin):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        await client.post(
            "/api/v1/roles",
            headers=headers,
            json={"name": "Asset Only", "permissions": {"ASSET_INVENTORY": "COMPLETE"}},
        )
        await client.post(
            "/api/v1/roles",
            headers=headers,
            json={"name": "Reports Only", "permissions": {"REPORTS": "READ_ONLY"}},
        )
        john = await create_user(
            db,
            email="john@test.internal",
            password=USER_PASSWORD,
            role_keys=["ASSET_ONLY", "REPORTS_ONLY"],
        )

        visible = await visible_modules(client, john.email, USER_PASSWORD)
        assert {"ASSET_INVENTORY", "REPORTS"} <= visible
        assert "SETTINGS" not in visible

    async def test_the_payload_carries_the_level_the_ui_renders(self, client, guest):
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        body = (await client.get("/api/v1/auth/me", headers=headers)).json()
        dashboard = next(p for p in body["permissions"] if p["module_key"] == "DASHBOARD")
        assert dashboard["can_view"] is True
        assert dashboard["can_manage"] is False
        assert dashboard["access_level"] == "READ_ONLY"


class TestServerSideEnforcement:
    """A hidden card must also be an unreachable API."""

    ADMIN_ONLY_ENDPOINTS = [
        ("GET", "/api/v1/users"),
        ("GET", "/api/v1/roles"),
        ("GET", "/api/v1/modules"),
        ("GET", "/api/v1/audit-logs"),
    ]

    @pytest.mark.parametrize(("method", "path"), ADMIN_ONLY_ENDPOINTS)
    async def test_guest_is_refused(self, client, guest, method, path):
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        response = await client.request(method, path, headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    @pytest.mark.parametrize(("method", "path"), ADMIN_ONLY_ENDPOINTS)
    async def test_anonymous_is_refused(self, client, method, path):
        response = await client.request(method, path)
        assert response.status_code == 401

    async def test_a_custom_role_cannot_reach_what_it_was_not_granted(
        self, client, db, admin
    ):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        await client.post(
            "/api/v1/roles",
            headers=headers,
            json={"name": "Asset Only", "permissions": {"ASSET_INVENTORY": "COMPLETE"}},
        )
        holder = await create_user(
            db, email="holder@test.internal", password=USER_PASSWORD, role_keys=["ASSET_ONLY"]
        )
        holder_headers = await auth_headers(client, holder.email, USER_PASSWORD)

        # Access Management was never granted, so every one of its endpoints is shut.
        for method, path in self.ADMIN_ONLY_ENDPOINTS:
            response = await client.request(method, path, headers=holder_headers)
            assert response.status_code == 403, path

    async def test_write_is_refused_at_read_only(self, client, normal_user):
        """READ_ONLY may look at Access Management but not change it."""
        headers = await auth_headers(client, normal_user.email, USER_PASSWORD)
        assert (await client.get("/api/v1/users", headers=headers)).status_code == 200

        assert (
            await client.post(
                "/api/v1/users",
                headers=headers,
                json={
                    "email": "x@test.internal",
                    "first_name": "X",
                    "last_name": "Y",
                    "role_keys": [],
                },
            )
        ).status_code == 403
        assert (
            await client.post(
                "/api/v1/roles", headers=headers, json={"name": "Nope", "permissions": {}}
            )
        ).status_code == 403

    async def test_the_client_cannot_supply_its_own_permissions(self, client, guest):
        """Permissions are never taken from the request.

        A caller inventing permission headers or a body must change nothing --
        the server resolves access from the database every time.
        """
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        forged = {
            **headers,
            "X-Access-Level": "COMPLETE",
            "X-Permissions": "ACCESS_MANAGEMENT=COMPLETE",
            "X-Roles": "SUPER_ADMIN",
        }
        assert (await client.get("/api/v1/users", headers=forged)).status_code == 403

    async def test_revoking_access_closes_the_api_immediately(self, client, db, admin, guest):
        """No sign-out needed: the next request is already refused."""
        admin_headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        await client.post(
            "/api/v1/roles",
            headers=admin_headers,
            json={"name": "Temp Access", "permissions": {"ACCESS_MANAGEMENT": "READ_ONLY"}},
        )
        await client.put(
            f"/api/v1/users/{guest.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["GUEST", "TEMP_ACCESS"]},
        )

        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        assert (await client.get("/api/v1/users", headers=guest_headers)).status_code == 200

        await client.put(
            f"/api/v1/users/{guest.id}/roles",
            headers=admin_headers,
            json={"role_keys": ["GUEST"]},
        )
        # Same token, same session -- access is gone.
        assert (await client.get("/api/v1/users", headers=guest_headers)).status_code == 403


class TestModuleRegistry:
    async def test_the_catalogue_is_the_single_source_of_module_metadata(
        self, client, superadmin
    ):
        """Every module the dashboard can render comes from the registry-seeded
        catalogue, with the metadata the UI needs."""
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        modules = (await client.get("/api/v1/modules", headers=headers)).json()

        assert {module["key"] for module in modules} == ALL_MODULES
        for module in modules:
            assert module["name"]
            assert module["route"].startswith("/")
            assert "icon" in module
            assert "description" in module
            assert isinstance(module["sort_order"], int)

    async def test_routes_are_unique(self, client, superadmin):
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        modules = (await client.get("/api/v1/modules", headers=headers)).json()
        routes = [module["route"] for module in modules]
        assert len(routes) == len(set(routes))

    async def test_permission_payload_matches_the_catalogue(self, client, superadmin):
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        modules = (await client.get("/api/v1/modules", headers=headers)).json()
        me = (await client.get("/api/v1/auth/me", headers=headers)).json()

        by_key = {module["key"]: module for module in modules}
        for permission in me["permissions"]:
            # The route the frontend guards on must come from the same source.
            assert permission["route"] == by_key[permission["module_key"]]["route"]
