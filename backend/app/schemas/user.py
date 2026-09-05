"""User, role and module schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import AccessLevel, UserStatus


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    is_system: bool
    is_superuser: bool
    sort_order: int = 100
    # Populated by the API; not a column on the model.
    user_count: int = 0
    #: False for seeded roles, which are protected from deletion.
    is_deletable: bool = True


class RoleWithPermissions(RoleSummary):
    permissions: dict[str, AccessLevel]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    # Optional: derived from the name when omitted (e.g. "Asset Manager" ->
    # ASSET_MANAGER). Immutable once the role exists.
    key: str | None = Field(default=None, min_length=2, max_length=64)
    permissions: dict[str, AccessLevel] = Field(default_factory=dict)
    sort_order: int = Field(default=500, ge=0, le=10000)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class ModuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    icon: str | None = None
    route: str
    sort_order: int
    is_active: bool
    is_core: bool
    is_implemented: bool


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str
    status: UserStatus
    must_change_password: bool
    job_title: str | None = None
    department: str | None = None
    phone: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    roles: list[RoleSummary]


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    role_keys: list[str] = Field(default_factory=list, max_length=20)
    status: UserStatus = UserStatus.ACTIVE
    job_title: str | None = Field(default=None, max_length=160)
    department: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=64)

    @field_validator("role_keys")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class UserCreateResponse(BaseModel):
    user: UserSummary
    # Returned once, at creation time, so an admin can hand it over out-of-band
    # while real SMTP delivery is not yet implemented. Never logged, never stored.
    temporary_password: str
    email_delivered: bool


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    status: UserStatus | None = None
    job_title: str | None = Field(default=None, max_length=160)
    department: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=64)


class UserRolesUpdate(BaseModel):
    role_keys: list[str] = Field(max_length=20)

    @field_validator("role_keys")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class AdminPasswordResetResponse(BaseModel):
    temporary_password: str
    email_delivered: bool


class RolePermissionsUpdate(BaseModel):
    permissions: dict[str, AccessLevel] = Field(
        description="Module key -> access level. Omitted modules are left unchanged."
    )
