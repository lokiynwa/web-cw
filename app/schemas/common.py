"""Common API response schemas used across endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.base import SchemaBase


class ErrorResponse(SchemaBase):
    """Standard error envelope for documented API responses."""

    detail: str | dict[str, Any] = Field(
        ...,
        description="Error detail string or structured detail object.",
        examples=["City not found", {"message": "Validation failed", "reasons": ["amount_outside_range"]}],
    )


class HealthResponse(SchemaBase):
    """Health endpoint response payload."""

    status: str = Field(..., description="Service status indicator.", examples=["ok"])
    timestamp: str = Field(..., description="Current UTC timestamp in ISO-8601 format.", examples=["2026-03-04T12:00:00Z"])
