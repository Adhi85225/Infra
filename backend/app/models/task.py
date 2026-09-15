"""Task updates.

One row is one piece of work a team member reports against a service.  The
reference column is deliberately generic: cases, work orders and Jira issues are
all just an identifier from whichever system the work came from, so they share a
single ``reference_number`` rather than three mostly-empty columns.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TaskService, TaskStatus
from app.models.user import User


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"

    # The day the work happened, as reported -- a calendar date, not an instant.
    # Storing a timestamp would make "today" depend on the reader's timezone.
    task_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Case / Work Order / Jira number. One generic column: which system the
    # identifier came from is not something the application reasons about.
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)

    site_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stored as strings, matching how `users.status` holds UserStatus: the value
    # is the label, and a new option needs no migration.
    status: Mapped[TaskStatus] = mapped_column(
        String(32), default=TaskStatus.CREATED, nullable=False, index=True
    )
    service: Mapped[TaskService] = mapped_column(String(64), nullable=False, index=True)

    # The person the task belongs to. Not necessarily whoever typed it in: an
    # administrator may file a task on someone else's behalf.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="selectin")

    __table_args__ = (
        # The service pages are always "this service, this user, newest first";
        # the composite index serves that access path directly.
        Index("ix_tasks_service_user_id_task_date", "service", "user_id", "task_date"),
    )
