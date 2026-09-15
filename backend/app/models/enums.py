"""Domain enumerations shared by models, schemas and services."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

    @property
    def can_authenticate(self) -> bool:
        return self is UserStatus.ACTIVE


class AccessLevel(StrEnum):
    """Access a role grants on a module.

    Ordered from least to most privileged; see :func:`access_rank`.

    ``GUEST`` is **deprecated**. Guest access is now expressed through ordinary
    effective permissions (the Guest *role* holding ``READ_ONLY`` grants) rather
    than through a distinct level, so roles are configured with the three levels
    operators actually reason about: No access / Read only / Complete.

    The value is retained so that rows written before migration ``0002`` still
    load and rank correctly. Nothing issues it any more -- see
    :data:`ASSIGNABLE_ACCESS_LEVELS`.
    """

    NONE = "NONE"
    GUEST = "GUEST"
    READ_ONLY = "READ_ONLY"
    COMPLETE = "COMPLETE"


#: The levels an administrator may assign when configuring a role.
ASSIGNABLE_ACCESS_LEVELS: tuple["AccessLevel", ...] = (
    AccessLevel.NONE,
    AccessLevel.READ_ONLY,
    AccessLevel.COMPLETE,
)


_ACCESS_RANK: dict[AccessLevel, int] = {
    AccessLevel.NONE: 0,
    AccessLevel.GUEST: 1,
    AccessLevel.READ_ONLY: 2,
    AccessLevel.COMPLETE: 3,
}


def access_rank(level: AccessLevel) -> int:
    """Numeric ordering used to combine the permissions of multiple roles."""
    return _ACCESS_RANK[level]


def highest(*levels: AccessLevel) -> AccessLevel:
    """Return the most privileged of ``levels`` (``NONE`` when empty).

    This is the single place where "a user with multiple roles gets the union of
    their access" is expressed.
    """
    return max(levels, key=access_rank, default=AccessLevel.NONE)


class ModuleAction(StrEnum):
    """Actions a caller may attempt against a module."""

    VIEW = "VIEW"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    MANAGE = "MANAGE"


# Which actions each access level permits. Centralised here so no endpoint or
# component ever re-derives this mapping.
_ALLOWED_ACTIONS: dict[AccessLevel, frozenset[ModuleAction]] = {
    AccessLevel.NONE: frozenset(),
    AccessLevel.GUEST: frozenset({ModuleAction.VIEW}),
    AccessLevel.READ_ONLY: frozenset({ModuleAction.VIEW}),
    AccessLevel.COMPLETE: frozenset(ModuleAction),
}


def level_allows(level: AccessLevel, action: ModuleAction) -> bool:
    return action in _ALLOWED_ACTIONS[level]


class AuditAction(StrEnum):
    """Recorded security/administrative events.

    Stored as a string column so future modules can add actions without a
    database migration.
    """

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    TOKEN_REUSE_DETECTED = "TOKEN_REUSE_DETECTED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_STATUS_CHANGED = "USER_STATUS_CHANGED"
    USER_ROLES_CHANGED = "USER_ROLES_CHANGED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
    ADMIN_PASSWORD_RESET = "ADMIN_PASSWORD_RESET"
    ROLE_PERMISSIONS_CHANGED = "ROLE_PERMISSIONS_CHANGED"
    ROLE_CREATED = "ROLE_CREATED"
    ROLE_UPDATED = "ROLE_UPDATED"
    ROLE_DELETED = "ROLE_DELETED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"


class TaskService(StrEnum):
    """The service a task update belongs to (dropdown **D1**).

    The stored value *is* the label the user sees. These strings are part of the
    API contract and are rendered verbatim in the UI, so they must not be
    reworded -- see :class:`TaskStatus` for the same reasoning.
    """

    ACCESS_MANAGEMENT = "Access Management"
    DAS = "DAS"
    ILO = "ILO"
    ZABBIX = "Zabbix"
    NEXUS = "Nexus"
    SERVERS = "Patch Management"

    @property
    def module_key(self) -> str:
        """The **existing** application module whose page owns this service.

        Task Updates is a cross-service layer, not a parent of the services: a
        task tagged ``DAS`` surfaces on the existing DAS Onboarding page, not on
        a service page invented by this module. This mapping is the single place
        that relationship is recorded.
        """
        return _SERVICE_MODULES[self]

    @classmethod
    def for_module(cls, module_key: str) -> TaskService | None:
        """The service a module page shows tasks for, if any."""
        return next(
            (member for member in cls if _SERVICE_MODULES[member] == module_key), None
        )





#: Service -> the existing module whose page shows its tasks.
#:
#: The names differ deliberately: these modules were named before Task Updates
#: existed ("DAS Onboarding", "ILO Inventory"), and renaming them to match would
#: be a gratuitous change to unrelated features.
_SERVICE_MODULES: dict[TaskService, str] = {
    TaskService.ACCESS_MANAGEMENT: "ACCESS_MANAGEMENT",
    TaskService.DAS: "DAS_ONBOARDING",
    TaskService.ILO: "ILO_INVENTORY",
    TaskService.ZABBIX: "ZABBIX",
    TaskService.NEXUS: "NEXUS",
    TaskService.SERVERS: "SERVERS",
}


class TaskStatus(StrEnum):
    """Progress of a task update (dropdown **D2**).

    ``Inprogress`` and ``Onhold`` are deliberately spelled as single words: the
    value is stored, filtered and displayed unchanged, so introducing a separate
    display label ("In Progress") would create two spellings of one status and
    break filters written against the other.
    """

    CREATED = "Created"
    INPROGRESS = "Inprogress"
    ONHOLD = "Onhold"
    COMPLETED = "Completed"
    TRIAGE = "Triage"


class TaskStatusFilter(StrEnum):
    """What the ``status`` query filter accepts.

    The five real statuses, plus ``Ongoing`` -- everything still open, i.e. any
    status other than ``Completed``. It lives here rather than in
    :class:`TaskStatus` because it is a *query* over statuses, not one a task
    can be in: no row is ever stored as "Ongoing".
    """

    CREATED = "Created"
    INPROGRESS = "Inprogress"
    ONHOLD = "Onhold"
    COMPLETED = "Completed"
    TRIAGE = "Triage"
    ONGOING = "Ongoing"

    @property
    def is_group(self) -> bool:
        return self is TaskStatusFilter.ONGOING
