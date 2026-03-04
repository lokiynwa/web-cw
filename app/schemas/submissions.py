"""Request/response schemas for user cost submissions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator

from app.schemas.base import SchemaBase


class SubmissionBase(SchemaBase):
    """Shared submission fields."""

    model_config = ConfigDict(str_strip_whitespace=True)

    city: str = Field(min_length=1, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    submission_type: str = Field(min_length=1, max_length=50)
    amount_gbp: Decimal = Field(gt=Decimal("0"), max_digits=10, decimal_places=2)
    venue_name: str | None = Field(default=None, max_length=200)
    item_name: str | None = Field(default=None, max_length=200)
    submission_notes: str | None = None

    @field_validator("city", "area", "submission_type", "venue_name", "item_name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None


class SubmissionCreateRequest(SubmissionBase):
    """Payload for creating a submission."""


class SubmissionUpdateRequest(SchemaBase):
    """Payload for updating a submission while pending."""

    model_config = ConfigDict(str_strip_whitespace=True)

    city: str | None = Field(default=None, min_length=1, max_length=120)
    area: str | None = Field(default=None, max_length=120)
    submission_type: str | None = Field(default=None, min_length=1, max_length=50)
    amount_gbp: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=10, decimal_places=2)
    venue_name: str | None = Field(default=None, max_length=200)
    item_name: str | None = Field(default=None, max_length=200)
    submission_notes: str | None = None

    @field_validator("city", "area", "submission_type", "venue_name", "item_name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None


class SubmissionResponse(SchemaBase):
    """Serialized submission response."""

    id: int
    city: str
    area: str | None
    submission_type: str
    moderation_status: str
    amount_gbp: Decimal
    venue_name: str | None
    item_name: str | None
    submission_notes: str | None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime


class SubmissionListResponse(SchemaBase):
    """Collection response for submission listings."""

    items: list[SubmissionResponse]
    total: int
