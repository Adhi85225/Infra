"""Task-update schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaskService, TaskStatus


def _blank_to_none(value: str | None) -> str | None:
    """Treat a whitespace-only optional field as absent.

    Browsers submit "" for an untouched optional input; storing that would make
    the column hold two different spellings of "no value".
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class TaskSummary(BaseModel):
    """A task as returned by the API.

    The owner's name and email are flattened onto the row so the table can
    render the User column without a second request per task.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_date: date
    reference_number: str | None = None
    site_name: str | None = None
    description: str
    status: TaskStatus
    remarks: str | None = None
    service: TaskService
    user_id: uuid.UUID
    user_name: str = ""
    user_email: str = ""
    created_at: datetime
    updated_at: datetime

    #: Whether *the caller* may edit this row. Resolved server-side so the UI
    #: never has to re-derive the authorization rule.
    can_edit: bool = False


class TaskCreate(BaseModel):
    task_date: date
    description: str = Field(min_length=1, max_length=4000)
    service: TaskService
    status: TaskStatus = TaskStatus.CREATED
    reference_number: str | None = Field(default=None, max_length=120)
    site_name: str | None = Field(default=None, max_length=160)
    remarks: str | None = Field(default=None, max_length=4000)

    #: Whom the task belongs to. Ignored for callers without administrative
    #: access, who may only file tasks against themselves -- enforced in the
    #: service layer, never here.
    user_id: uuid.UUID | None = None

    _normalize = field_validator("reference_number", "site_name", "remarks")(_blank_to_none)

    @field_validator("description")
    @classmethod
    def _require_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("A description is required.")
        return stripped


class TaskUpdate(BaseModel):
    """Partial update. Only the fields present in the payload are changed."""

    task_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    service: TaskService | None = None
    status: TaskStatus | None = None
    reference_number: str | None = Field(default=None, max_length=120)
    site_name: str | None = Field(default=None, max_length=160)
    remarks: str | None = Field(default=None, max_length=4000)
    user_id: uuid.UUID | None = None

    _normalize = field_validator("reference_number", "site_name", "remarks")(_blank_to_none)

    @field_validator("description")
    @classmethod
    def _require_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("A description is required.")
        return stripped


class TaskOptions(BaseModel):
    """Dropdown contents (**D1** and **D2**), served from the enums.

    The UI reads its options from here rather than hardcoding them, so the two
    can never drift apart.
    """

    services: list[str]
    statuses: list[str]
