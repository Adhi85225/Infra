"""Authentication request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import AccessLevel
from app.schemas.user import UserSummary


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class PermissionEntry(BaseModel):
    module_key: str
    module_name: str
    icon: str | None = None
    route: str
    description: str | None = None
    sort_order: int
    is_implemented: bool
    access_level: AccessLevel
    can_view: bool
    can_manage: bool


class SessionResponse(BaseModel):
    """What the client needs after sign-in or refresh.

    The refresh token is *not* in the body -- it is set as an httpOnly cookie.
    """

    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime
    must_change_password: bool
    user: UserSummary
    permissions: list[PermissionEntry]


class MeResponse(BaseModel):
    user: UserSummary
    permissions: list[PermissionEntry]
    must_change_password: bool


class _NewPasswordMixin(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match.")
        return self


class ChangePasswordRequest(_NewPasswordMixin):
    current_password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(_NewPasswordMixin):
    token: str = Field(min_length=16, max_length=512)


class PasswordPolicyResponse(BaseModel):
    """Advertised so the UI can show the rules without duplicating them."""

    min_length: int
    max_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_symbol: bool
    history_depth: int
