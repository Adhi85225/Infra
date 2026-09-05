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
