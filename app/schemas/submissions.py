"""Request/response schemas for user cost submissions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field, field_validator

from app.schemas.base import SchemaBase


class SubmissionBase(SchemaBase):
    """Shared submission fields."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "city": "Leeds",
                "area": "Hyde Park",
                "submission_type": "PINT",
                "amount_gbp": "5.60",
                "venue_name": "The Fenton",
                "item_name": "Pint of Lager",
                "submission_notes": "Weeknight price",
            }
        },
    )

    city: str = Field(min_length=1, max_length=120, description="City where the observed price was recorded.")
    area: str | None = Field(default=None, max_length=120, description="Optional area within the city.")
    submission_type: str = Field(
        min_length=1,
        max_length=50,
        description="Submission type code. Common values: PINT, TAKEAWAY.",
    )
    amount_gbp: Decimal = Field(
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=2,
        description="Observed price amount in GBP.",
    )
    venue_name: str | None = Field(default=None, max_length=200, description="Optional venue or shop name.")
    item_name: str | None = Field(default=None, max_length=200, description="Optional item name.")
    submission_notes: str | None = Field(default=None, description="Optional free-text notes.")

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
    """Payload for updating a submission while active."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {"amount_gbp": "6.00", "submission_notes": "Price corrected."}},
    )

    city: str | None = Field(default=None, min_length=1, max_length=120, description="Updated city value.")
    area: str | None = Field(default=None, max_length=120, description="Updated area value.")
    submission_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Updated submission type code.",
    )
    amount_gbp: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=2,
        description="Updated price amount in GBP.",
    )
    venue_name: str | None = Field(default=None, max_length=200, description="Updated venue name.")
    item_name: str | None = Field(default=None, max_length=200, description="Updated item name.")
    submission_notes: str | None = Field(default=None, description="Updated notes.")

    @field_validator("city", "area", "submission_type", "venue_name", "item_name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None


class SubmissionResponse(SchemaBase):
    """Serialized submission response."""

    id: int = Field(..., description="Submission identifier.")
    city: str = Field(..., description="City for the submission.")
    area: str | None = Field(None, description="Area for the submission.")
    submission_type: str = Field(..., description="Submission type code.")
    moderation_status: str = Field(..., description="Current moderation state.")
    amount_gbp: Decimal = Field(..., description="Observed amount in GBP.")
    is_analytics_eligible: bool = Field(..., description="True when active and included in analytics.")
    is_suspicious: bool = Field(..., description="True when automated checks flagged suspicious attributes.")
    suspicious_reasons: list[str] = Field(default_factory=list, description="Reasons for suspicious flagging.")
    duplicate_fingerprint: str | None = Field(None, description="Deterministic fingerprint used for duplicate checks.")
    created_by_user_id: int | None = Field(None, description="Owning website user account ID when created via login.")
    submitted_via_api_key_id: int | None = Field(None, description="Legacy API key ID when created via API key.")
    venue_name: str | None = Field(None, description="Venue or shop name.")
    item_name: str | None = Field(None, description="Item name.")
    submission_notes: str | None = Field(None, description="Additional notes.")
    submitted_at: datetime = Field(..., description="Submission timestamp (UTC).")
    created_at: datetime = Field(..., description="Record creation timestamp (UTC).")
    updated_at: datetime = Field(..., description="Record update timestamp (UTC).")


class SubmissionListResponse(SchemaBase):
    """Collection response for submission listings."""

    items: list[SubmissionResponse] = Field(..., description="Submission records in the response page.")
    total: int = Field(..., ge=0, description="Number of returned records.")


class SubmissionModerationRequest(SchemaBase):
    """Payload for a moderation decision."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"moderation_status": "FLAGGED", "moderator_note": "Needs follow-up."}},
    )

    moderation_status: str = Field(
        min_length=1,
        max_length=50,
        description="Target moderation state. Typical values: ACTIVE, FLAGGED, REMOVED.",
    )
    moderator_note: str | None = Field(default=None, description="Optional moderator note.")

    @field_validator("moderation_status", mode="before")
    @classmethod
    def normalize_status_code(cls, value: str) -> str:
        return str(value).strip().upper()


class SubmissionModerationLogEntry(SchemaBase):
    """Single moderation log record."""

    id: int = Field(..., description="Moderation log identifier.")
    submission_id: int = Field(..., description="Submission identifier.")
    from_moderation_status: str | None = Field(None, description="Previous moderation status.")
    to_moderation_status: str = Field(..., description="New moderation status.")
    moderator_user_id: int | None = Field(None, description="Moderator user account ID when moderated via login.")
    moderator_display_name: str | None = Field(None, description="Moderator display name when moderated via login.")
    moderator_api_key_id: int | None = Field(None, description="Moderator API key record identifier.")
    moderator_key_name: str | None = Field(None, description="Moderator key display name.")
    moderator_note: str | None = Field(None, description="Moderator comment.")
    created_at: datetime = Field(..., description="Decision timestamp (UTC).")


class SubmissionModerationLogResponse(SchemaBase):
    """Moderation history response for a submission."""

    submission_id: int = Field(..., description="Submission identifier.")
    items: list[SubmissionModerationLogEntry] = Field(..., description="Chronological moderation records.")
    total: int = Field(..., ge=0, description="Number of moderation log records.")
