"""Role -> Module access grants (the second many-to-many of the auth model)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AccessLevel
from app.models.module import Module
from app.models.user import Role


class RoleModulePermission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The access level a single role grants on a single module.

    A missing row means ``NONE``.  Effective user access is the highest level
    across all of the user's roles -- computed in
    :mod:`app.services.permission_service`, and nowhere else.
    """

    __tablename__ = "role_module_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "module_id", name="uq_role_module_permissions_role_id_module_id"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        String(32), default=AccessLevel.NONE, nullable=False
    )

    role: Mapped[Role] = relationship(back_populates="module_permissions", lazy="selectin")
    module: Mapped[Module] = relationship(back_populates="role_permissions", lazy="selectin")
