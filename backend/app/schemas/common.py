"""Shared response envelopes."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Message(BaseModel):
    message: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Total rows matching the filter, ignoring pagination.")
    limit: int
    offset: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
