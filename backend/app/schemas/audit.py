"""Audit-log schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, ConfigDict, field_validator


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    actor_email: str | None = None
    action: str
    success: bool
    entity_type: str | None = None
    entity_id: str | None = None
    ip_address: str | None = None
    context: dict | None = None
    created_at: datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def _stringify_ip(cls, value: object) -> object:
        # asyncpg maps PostgreSQL INET to an ipaddress object, not a string.
        if isinstance(value, (IPv4Address, IPv6Address)):
            return str(value)
        return value
