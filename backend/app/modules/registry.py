"""Canonical catalogue of application modules ("tools").

This is the *seed* definition.  At runtime the database is authoritative -- an
administrator may change any module's default grants without a deployment.  The
registry exists so that:

* a new tool is added in exactly one place, and
* a fresh environment comes up with a sensible, documented permission baseline.

Adding a module later means appending a :class:`ModuleDefinition` here and
running the sync (``python -m app.db.seed``).  No authorization code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import AccessLevel

# Stable role keys referenced by the defaults below.
ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_USER = "USER"
ROLE_GUEST = "GUEST"


@dataclass(frozen=True)
class RoleDefinition:
    key: str
    name: str
    description: str
    is_system: bool = True
    is_superuser: bool = False
    sort_order: int = 100


ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        key=ROLE_SUPER_ADMIN,
        name="Super Admin",
        description=(
            "Unrestricted access to every module, including modules added in the "
            "future. Permission checks short-circuit for this role."
        ),
        is_superuser=True,
        sort_order=10,
    ),
    RoleDefinition(
        key=ROLE_ADMIN,
        name="Admin",
        description="Full access to application modules and user administration.",
        sort_order=20,
    ),
    RoleDefinition(
        key=ROLE_USER,
        name="User",
        description="Standard access. Exact permissions are refined in a later phase.",
        sort_order=30,
    ),
    RoleDefinition(
        key=ROLE_GUEST,
        name="Guest",
        description="Read-only visibility of non-sensitive modules.",
        sort_order=40,
    ),
)


@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    name: str
    icon: str
    route: str
    description: str
    sort_order: int
    is_core: bool = False
    is_implemented: bool = False
    # Default grant per role key. SUPER_ADMIN is omitted deliberately -- it is
    # resolved as COMPLETE by the permission service, not by stored rows.
    defaults: dict[str, AccessLevel] = field(default_factory=dict)


def _defaults(
    admin: AccessLevel = AccessLevel.COMPLETE,
    user: AccessLevel = AccessLevel.READ_ONLY,
    guest: AccessLevel = AccessLevel.READ_ONLY,
) -> dict[str, AccessLevel]:
    """Default grants for the seeded roles.

    The Guest role is read-only through an ordinary ``READ_ONLY`` grant rather
    than a special access level -- see :class:`AccessLevel`.
    """
    return {ROLE_ADMIN: admin, ROLE_USER: user, ROLE_GUEST: guest}


MODULE_DEFINITIONS: tuple[ModuleDefinition, ...] = (
    ModuleDefinition(
        key="DASHBOARD",
        name="Dashboard",
        icon="\N{HOUSE BUILDING}",
        route="/dashboard",
        description="Landing page listing the tools available to you.",
        sort_order=10,
        is_core=True,
        is_implemented=True,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="TEAM_MEMBERS",
        name="Team Members",
        icon="\N{BUSTS IN SILHOUETTE}",
        route="/team-members",
        description="Directory of team members and their details.",
        sort_order=20,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="ACCESS_MANAGEMENT",
        name="Access Management",
        icon="\N{CLOSED LOCK WITH KEY}",
        route="/access-management",
        description="Manage users, roles, module permissions and account status.",
        sort_order=30,
        is_core=True,
        is_implemented=True,
        # Sensitive: standard users get read-only, guests get nothing.
        defaults={
            ROLE_ADMIN: AccessLevel.COMPLETE,
            ROLE_USER: AccessLevel.READ_ONLY,
            ROLE_GUEST: AccessLevel.NONE,
        },
    ),
    ModuleDefinition(
        key="ASSET_INVENTORY",
        name="Asset Inventory",
        icon="\N{PERSONAL COMPUTER}",
        route="/asset-inventory",
        description="Hardware and software asset register.",
        sort_order=40,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="DAS_ONBOARDING",
        name="DAS Onboarding",
        icon="\N{BUST IN SILHOUETTE}",
        route="/das-onboarding",
        description="Direct-attached storage onboarding workflow.",
        sort_order=50,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="ILO_INVENTORY",
        name="ILO Inventory",
        icon="\N{PACKAGE}",
        route="/ilo-inventory",
        description="Integrated Lights-Out management inventory.",
        sort_order=60,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="ZABBIX",
        name="Zabbix",
        icon="\N{BAR CHART}",
        route="/zabbix",
        description="Monitoring overview sourced from Zabbix.",
        sort_order=70,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="NEXUS",
        name="Nexus",
        icon="\N{SHIELD}\N{VARIATION SELECTOR-16}",
        route="/nexus",
        description="Nexus repository and artifact information.",
        sort_order=80,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="CLOUD_INFORMATION",
        name="Cloud Information",
        icon="\N{CLOUD}\N{VARIATION SELECTOR-16}",
        route="/cloud-information",
        description="Cloud accounts, resources and spend overview.",
        sort_order=90,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="TASK_UPDATES",
        name="Task Updates",
        icon="\N{WHITE HEAVY CHECK MARK}",
        route="/task-updates",
        description="Team task tracking and status updates.",
        sort_order=100,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="REPORTS",
        name="Reports",
        icon="\N{CHART WITH UPWARDS TREND}",
        route="/reports",
        description="Manager and admin reporting.",
        sort_order=110,
        defaults=_defaults(),
    ),
    ModuleDefinition(
        key="SETTINGS",
        name="Settings",
        icon="\N{GEAR}\N{VARIATION SELECTOR-16}",
        route="/settings",
        description="Application configuration. Administrators only.",
        sort_order=120,
        is_core=True,
        # Admin-only by design.
        defaults={
            ROLE_ADMIN: AccessLevel.COMPLETE,
            ROLE_USER: AccessLevel.NONE,
            ROLE_GUEST: AccessLevel.NONE,
        },
    ),
)

MODULE_KEYS: tuple[str, ...] = tuple(m.key for m in MODULE_DEFINITIONS)


def get_module_definition(key: str) -> ModuleDefinition | None:
    return next((m for m in MODULE_DEFINITIONS if m.key == key), None)
