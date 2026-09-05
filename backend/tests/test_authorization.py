"""Authorization: role resolution, module access levels and enforcement.

These tests exercise the *central* permission service and the server-side
enforcement it backs.  Nothing here relies on the UI hiding anything.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.models import Module, Role, RoleModulePermission
from app.models.enums import AccessLevel, ModuleAction, highest, level_allows
from app.services import permission_service
from tests.conftest import (
    ADMIN_PASSWORD,
    GUEST_PASSWORD,
    SUPERADMIN_PASSWORD,
    USER_PASSWORD,
    auth_headers,
    create_user,
)


class TestAccessLevelAlgebra:
    """The ordering that makes 'multiple roles' well-defined."""

    def test_levels_are_ordered(self):
        assert highest(AccessLevel.NONE, AccessLevel.GUEST) is AccessLevel.GUEST
        assert highest(AccessLevel.GUEST, AccessLevel.READ_ONLY) is AccessLevel.READ_ONLY
        assert highest(AccessLevel.READ_ONLY, AccessLevel.COMPLETE) is AccessLevel.COMPLETE

    def test_no_levels_means_no_access(self):
        assert highest() is AccessLevel.NONE

    def test_order_does_not_matter(self):
        assert highest(AccessLevel.COMPLETE, AccessLevel.NONE) is AccessLevel.COMPLETE
        assert highest(AccessLevel.NONE, AccessLevel.COMPLETE) is AccessLevel.COMPLETE

    @pytest.mark.parametrize(
        ("level", "action", "allowed"),
        [
            (AccessLevel.NONE, ModuleAction.VIEW, False),
            (AccessLevel.GUEST, ModuleAction.VIEW, True),
            (AccessLevel.GUEST, ModuleAction.CREATE, False),
            (AccessLevel.READ_ONLY, ModuleAction.VIEW, True),
            (AccessLevel.READ_ONLY, ModuleAction.UPDATE, False),
            (AccessLevel.COMPLETE, ModuleAction.VIEW, True),
            (AccessLevel.COMPLETE, ModuleAction.DELETE, True),
            (AccessLevel.COMPLETE, ModuleAction.MANAGE, True),
        ],
    )
    def test_actions_permitted_per_level(self, level, action, allowed):
        assert level_allows(level, action) is allowed


class TestPermissionResolution:
    async def test_superadmin_gets_complete_on_everything(self, db, superadmin):
        permissions = await permission_service.resolve_permissions(db, superadmin)
        assert len(permissions) == 12
        assert all(p.access_level is AccessLevel.COMPLETE for p in permissions.values())

    async def test_superadmin_access_is_implicit_not_stored(self, db, superadmin):
        """No grant rows exist for SUPER_ADMIN -- future modules are covered too."""
        role = (await db.execute(sa.select(Role).where(Role.key == "SUPER_ADMIN"))).scalar_one()
        count = (
            await db.execute(
                sa.select(sa.func.count())
                .select_from(RoleModulePermission)
                .where(RoleModulePermission.role_id == role.id)
            )
        ).scalar_one()
        assert count == 0

    async def test_superadmin_covers_a_newly_added_module(self, db, superadmin):
        db.add(
            Module(
                key="BRAND_NEW_TOOL",
                name="Brand New Tool",
                route="/brand-new-tool",
                sort_order=999,
            )
        )
        await db.commit()

        permissions = await permission_service.resolve_permissions(db, superadmin, use_cache=False)
        assert permissions["BRAND_NEW_TOOL"].access_level is AccessLevel.COMPLETE

    async def test_admin_defaults(self, db, admin):
        permissions = await permission_service.resolve_permissions(db, admin)
        assert permissions["ACCESS_MANAGEMENT"].access_level is AccessLevel.COMPLETE
        assert permissions["SETTINGS"].access_level is AccessLevel.COMPLETE

    async def test_user_defaults(self, db, normal_user):
        permissions = await permission_service.resolve_permissions(db, normal_user)
        assert permissions["DASHBOARD"].access_level is AccessLevel.READ_ONLY
        assert permissions["ACCESS_MANAGEMENT"].access_level is AccessLevel.READ_ONLY
        assert permissions["SETTINGS"].access_level is AccessLevel.NONE

    async def test_guest_defaults(self, db, guest):
        # Guest is read-only through an ordinary READ_ONLY grant; the legacy
        # GUEST access level is no longer issued (migration 0002).
        permissions = await permission_service.resolve_permissions(db, guest)
        assert permissions["DASHBOARD"].access_level is AccessLevel.READ_ONLY
        assert permissions["ACCESS_MANAGEMENT"].access_level is AccessLevel.NONE
        assert permissions["SETTINGS"].access_level is AccessLevel.NONE

    async def test_guest_role_grants_read_but_not_write(self, db, guest):
        assert await permission_service.has_permission(
            db, guest, "DASHBOARD", ModuleAction.VIEW
        )
        assert not await permission_service.has_permission(
            db, guest, "DASHBOARD", ModuleAction.UPDATE
        )

    async def test_user_with_no_roles_has_no_access(self, db):
        nobody = await create_user(
            db, email="nobody@test.internal", password=USER_PASSWORD, role_keys=[]
        )
        permissions = await permission_service.resolve_permissions(db, nobody)
        assert all(p.access_level is AccessLevel.NONE for p in permissions.values())

    async def test_multiple_roles_take_the_highest_level(self, db):
        """The core multi-role rule: union, never intersection."""
        both = await create_user(
            db, email="both@test.internal", password=USER_PASSWORD, role_keys=["GUEST", "USER"]
        )
        permissions = await permission_service.resolve_permissions(db, both)
        # GUEST alone would give NONE here; USER contributes READ_ONLY.
        assert permissions["ACCESS_MANAGEMENT"].access_level is AccessLevel.READ_ONLY
        # GUEST gives GUEST, USER gives READ_ONLY -> READ_ONLY wins.
        assert permissions["DASHBOARD"].access_level is AccessLevel.READ_ONLY

    async def test_admin_plus_guest_keeps_admin_level(self, db):
        mixed = await create_user(
            db, email="mixed@test.internal", password=USER_PASSWORD, role_keys=["ADMIN", "GUEST"]
        )
        permissions = await permission_service.resolve_permissions(db, mixed)
        assert permissions["SETTINGS"].access_level is AccessLevel.COMPLETE

    async def test_inactive_module_resolves_to_none(self, db, admin):
        module = (
            await db.execute(sa.select(Module).where(Module.key == "ZABBIX"))
        ).scalar_one()
        module.is_active = False
        await db.commit()

        permissions = await permission_service.resolve_permissions(db, admin, use_cache=False)
        assert "ZABBIX" not in permissions

    async def test_require_permission_raises_when_denied(self, db, guest):
        from app.core.errors import PermissionDeniedError

        with pytest.raises(PermissionDeniedError):
            await permission_service.require_permission(
                db, guest, "ACCESS_MANAGEMENT", ModuleAction.VIEW
            )

    async def test_require_permission_returns_the_level_when_allowed(self, db, admin):
        level = await permission_service.require_permission(
            db, admin, "ACCESS_MANAGEMENT", ModuleAction.CREATE
        )
        assert level is AccessLevel.COMPLETE


class TestPermissionsOverTheApi:
    @pytest.mark.parametrize(
        ("role_key", "password", "expected"),
        [
            ("SUPER_ADMIN", SUPERADMIN_PASSWORD, "COMPLETE"),
            ("ADMIN", ADMIN_PASSWORD, "COMPLETE"),
            ("USER", USER_PASSWORD, "READ_ONLY"),
            ("GUEST", GUEST_PASSWORD, "NONE"),
        ],
    )
    async def test_me_reports_access_management_level(
        self, client, superadmin, admin, normal_user, guest, role_key, password, expected
    ):
        # The fixtures are requested directly rather than via getfixturevalue:
        # that helper returns an un-awaited coroutine for async fixtures.
        user = {
            "SUPER_ADMIN": superadmin,
            "ADMIN": admin,
            "USER": normal_user,
            "GUEST": guest,
        }[role_key]
        headers = await auth_headers(client, user.email, password)
        body = (await client.get("/api/v1/auth/me", headers=headers)).json()
        levels = {p["module_key"]: p["access_level"] for p in body["permissions"]}
        assert levels["ACCESS_MANAGEMENT"] == expected

    async def test_every_module_appears_for_every_user(self, client, guest):
        """Guests still receive the full catalogue -- with NONE where denied.

        The dashboard needs the whole list so it can render a locked card rather
        than silently omitting tools.
        """
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        body = (await client.get("/api/v1/auth/me", headers=headers)).json()
        assert len(body["permissions"]) == 12

    async def test_view_is_enforced_server_side(self, client, guest):
        headers = await auth_headers(client, guest.email, GUEST_PASSWORD)
        for path in ("/api/v1/users", "/api/v1/roles", "/api/v1/modules", "/api/v1/audit-logs"):
            response = await client.get(path, headers=headers)
            assert response.status_code == 403, path

    async def test_read_only_can_view_but_not_write(self, client, normal_user):
        headers = await auth_headers(client, normal_user.email, USER_PASSWORD)
        assert (await client.get("/api/v1/roles", headers=headers)).status_code == 200
        response = await client.post(
            "/api/v1/users",
            headers=headers,
            json={"email": "x@test.internal", "first_name": "X", "last_name": "Y", "role_keys": []},
        )
        assert response.status_code == 403


class TestRolePermissionEditing:
    async def test_permissions_can_be_changed_without_code_changes(
        self, client, db, superadmin, guest
    ):
        """The point of the design: a grant is data, not a deployment."""
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)

        assert (await client.get("/api/v1/users", headers=guest_headers)).status_code == 403

        role = (await db.execute(sa.select(Role).where(Role.key == "GUEST"))).scalar_one()
        response = await client.put(
            f"/api/v1/roles/{role.id}/permissions",
            headers=headers,
            json={"permissions": {"ACCESS_MANAGEMENT": "READ_ONLY"}},
        )
        assert response.status_code == 200
        assert response.json()["permissions"]["ACCESS_MANAGEMENT"] == "READ_ONLY"

        # Same user, same token -- the change takes effect immediately.
        assert (await client.get("/api/v1/users", headers=guest_headers)).status_code == 200

    async def test_revoking_access_takes_effect_immediately(self, client, db, superadmin, admin):
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        admin_headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        assert (await client.get("/api/v1/users", headers=admin_headers)).status_code == 200

        role = (await db.execute(sa.select(Role).where(Role.key == "ADMIN"))).scalar_one()
        await client.put(
            f"/api/v1/roles/{role.id}/permissions",
            headers=headers,
            json={"permissions": {"ACCESS_MANAGEMENT": "NONE"}},
        )
        assert (await client.get("/api/v1/users", headers=admin_headers)).status_code == 403

    async def test_superadmin_permissions_cannot_be_edited(self, client, db, superadmin):
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        role = (
            await db.execute(sa.select(Role).where(Role.key == "SUPER_ADMIN"))
        ).scalar_one()
        response = await client.put(
            f"/api/v1/roles/{role.id}/permissions",
            headers=headers,
            json={"permissions": {"SETTINGS": "NONE"}},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "role_immutable"

    async def test_admin_cannot_edit_admin_permissions(self, client, db, admin):
        headers = await auth_headers(client, admin.email, ADMIN_PASSWORD)
        role = (await db.execute(sa.select(Role).where(Role.key == "ADMIN"))).scalar_one()
        response = await client.put(
            f"/api/v1/roles/{role.id}/permissions",
            headers=headers,
            json={"permissions": {"SETTINGS": "NONE"}},
        )
        assert response.status_code == 403

    async def test_unknown_module_is_rejected(self, client, db, superadmin):
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        role = (await db.execute(sa.select(Role).where(Role.key == "GUEST"))).scalar_one()
        response = await client.put(
            f"/api/v1/roles/{role.id}/permissions",
            headers=headers,
            json={"permissions": {"NOT_A_MODULE": "COMPLETE"}},
        )
        assert response.status_code == 422

    async def test_audit_log_is_readable_with_a_recorded_ip(self, client, db, superadmin):
        """Regression: PostgreSQL INET comes back as an ipaddress object.

        Serialising it without coercing to a string raised a 500 on this
        endpoint. A row with a known address is inserted so the assertion is
        about that value specifically.
        """
        from app.models import AuditLog

        db.add(
            AuditLog(
                action="LOGIN_SUCCESS",
                actor_email="someone@test.internal",
                success=True,
                ip_address="203.0.113.7",
            )
        )
        await db.commit()

        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        response = await client.get("/api/v1/audit-logs", headers=headers)
        assert response.status_code == 200

        entry = next(
            item
            for item in response.json()["items"]
            if item["actor_email"] == "someone@test.internal"
        )
        assert entry["ip_address"] == "203.0.113.7"

        # Every row must serialise, including those the API itself wrote.
        assert all(
            item["ip_address"] is None or isinstance(item["ip_address"], str)
            for item in response.json()["items"]
        )

    async def test_role_change_updates_effective_access(self, client, db, superadmin, guest):
        headers = await auth_headers(client, superadmin.email, SUPERADMIN_PASSWORD)
        guest_headers = await auth_headers(client, guest.email, GUEST_PASSWORD)

        await client.put(
            f"/api/v1/users/{guest.id}/roles", headers=headers, json={"role_keys": ["ADMIN"]}
        )
        body = (await client.get("/api/v1/auth/me", headers=guest_headers)).json()
        levels = {p["module_key"]: p["access_level"] for p in body["permissions"]}
        assert levels["SETTINGS"] == "COMPLETE"
