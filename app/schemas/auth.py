"""Request/response schemas for account authentication endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.schemas.base import SchemaBase
from app.services.user_auth import normalize_email


class AuthRegisterRequest(SchemaBase):
    """Payload for registering a new user account."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "email": "student@example.com",
                "password": "SecurePass123",
                "display_name": "Student User",
            }
        },
    )

    email: str = Field(min_length=5, max_length=255, description="User email address (unique).")
    password: str = Field(min_length=1, max_length=200, description="Raw password for account setup.")
    display_name: str = Field(min_length=1, max_length=120, description="Display name for API responses.")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        normalized = normalize_email(str(value))
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Invalid email format")
        return normalized


class AuthLoginRequest(SchemaBase):
    """Payload for logging in with account credentials."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {"email": "student@example.com", "password": "SecurePass123"}},
    )

    email: str = Field(min_length=5, max_length=255, description="User email address.")
    password: str = Field(min_length=1, max_length=200, description="Raw password.")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        normalized = normalize_email(str(value))
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Invalid email format")
        return normalized


class AuthUserResponse(SchemaBase):
    """Serialized authenticated user profile."""

    id: int
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime


class AuthTokenResponse(SchemaBase):
    """Bearer token response for successful login."""

    access_token: str = Field(..., description="Signed bearer token.")
    token_type: str = Field(..., description="Token type. Always 'bearer'.")
    expires_in_seconds: int = Field(..., ge=1, description="Access token lifetime in seconds.")
