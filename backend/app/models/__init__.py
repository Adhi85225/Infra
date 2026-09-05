"""SQLAlchemy models.

Importing this package registers every model on ``Base.metadata``, which Alembic
relies on for autogeneration.
"""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.enums import (
    ASSIGNABLE_ACCESS_LEVELS,
    AccessLevel,
    AuditAction,
    ModuleAction,
    UserStatus,
    access_rank,
    highest,
    level_allows,
)
from app.models.module import Module
from app.models.permission import RoleModulePermission
from app.models.token import PasswordHistory, PasswordResetToken, Session
from app.models.user import Role, User, UserRole

__all__ = [
    "ASSIGNABLE_ACCESS_LEVELS",
    "AccessLevel",
    "AuditAction",
    "AuditLog",
    "Base",
    "Module",
    "ModuleAction",
    "PasswordHistory",
    "PasswordResetToken",
    "Role",
    "RoleModulePermission",
    "Session",
    "User",
    "UserRole",
    "UserStatus",
    "access_rank",
    "highest",
    "level_allows",
]
