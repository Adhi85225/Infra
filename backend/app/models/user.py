"""User, Role and their many-to-many association."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserStatus

if TYPE_CHECKING:
    from app.models.permission import RoleModulePermission


class UserRole(Base):
    """Association row for User <-> Role (many-to-many).

    Roles are modelled relationally -- never as a string column on ``users`` --
    so a user can hold any number of roles and permissions stay queryable.
    """

    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(
        back_populates="user_roles", foreign_keys=[user_id], lazy="selectin"
    )
    role: Mapped["Role"] = relationship(back_populates="user_roles", lazy="selectin")


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    # Stable machine key (SUPER_ADMIN, ADMIN, ...) referenced by code/seeds.
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # System roles cannot be deleted or re-keyed through the API.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # SuperAdmin holds this flag: it short-circuits permission resolution to
    # COMPLETE on every module, including modules added in the future.
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    module_permissions: Mapped[list["RoleModulePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    # Stored lower-cased; uniqueness is therefore case-insensitive in practice.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)

    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        String(32), default=UserStatus.ACTIVE, nullable=False, index=True
    )

    # Set when an admin creates the account or performs an administrative
    # reset; cleared once the user chooses their own password.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Extensible profile fields -- adding more here does not affect auth.
    job_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        foreign_keys=[UserRole.user_id],
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def roles(self) -> list[Role]:
        return [assignment.role for assignment in self.user_roles]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_superuser(self) -> bool:
        return any(role.is_superuser for role in self.roles)

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now
