"""Application modules (the "tools") as first-class database rows.

Adding a new tool to the platform is a data change -- a row here plus a route in
the frontend -- not an authorization code change.  See ``app/modules/registry.py``
for the canonical Phase 1 catalogue that seeds this table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.permission import RoleModulePermission


class Module(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "modules"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    route: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # Inactive modules are hidden everywhere and always resolve to NONE.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Core modules are part of the platform foundation (Dashboard, Access
    # Management, Settings) and cannot be removed via the API.
    is_core: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Phase 1 ships placeholders; flipped to True as each tool is built.
    is_implemented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    role_permissions: Mapped[list["RoleModulePermission"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )
