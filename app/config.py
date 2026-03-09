"""Application configuration management."""

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_running_on_railway() -> bool:
    """Return True when process is running inside Railway runtime."""
    return any(
        [
            bool(os.getenv("RAILWAY_ENVIRONMENT")),
            bool(os.getenv("RAILWAY_PROJECT_ID")),
            bool(os.getenv("RAILWAY_SERVICE_ID")),
        ]
    )


class Settings(BaseSettings):
    """Environment-driven settings."""

    app_name: str = "Student Affordability Intelligence API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"
    app_runtime_mode: Literal["rest", "mcp", "both"] = "rest"

    database_url: str = "sqlite:///./student_affordability.db"
    api_key_enabled: bool = False
    api_key_header_name: str = "X-API-Key"
    api_key_secret: str = ""
    auth_jwt_secret: str = "change-me-in-production"
    auth_jwt_exp_minutes: int = 120
    auth_password_min_length: int = 8
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    affordability_rent_weight: float = 0.6
    affordability_pint_weight: float = 0.2
    affordability_takeaway_weight: float = 0.2
    affordability_rent_floor_gbp_weekly: float = 80.0
    affordability_rent_ceiling_gbp_weekly: float = 450.0
    affordability_cost_floor_gbp: float = 2.0
    affordability_cost_ceiling_gbp: float = 20.0
    affordability_pint_floor_gbp: float = 2.0
    affordability_pint_ceiling_gbp: float = 10.0
    affordability_takeaway_floor_gbp: float = 5.0
    affordability_takeaway_ceiling_gbp: float = 25.0
    mcp_http_enabled: bool = False
    mcp_http_mount_path: str = "/mcp"
    mcp_http_stateless: bool = True
    mcp_http_validate_origin: bool = True
    mcp_http_allowed_origins: str = ""
    mcp_http_allow_requests_without_origin: bool = True
    mcp_http_public_read_tools: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Normalize common PostgreSQL URL forms for SQLAlchemy + psycopg."""
        raw = str(value).strip()
        if not raw:
            raise ValueError("DATABASE_URL cannot be empty.")

        raw_lower = raw.lower()

        if raw_lower.startswith("postgres://"):
            return "postgresql+psycopg://" + raw[len("postgres://") :]

        if raw_lower.startswith("postgresql://"):
            scheme, _, remainder = raw.partition("://")
            if "+" not in scheme:
                return "postgresql+psycopg://" + remainder

        if _is_running_on_railway() and raw_lower.startswith("sqlite"):
            raise ValueError("Railway deployment requires DATABASE_URL to point to PostgreSQL, not SQLite.")

        return raw

    @field_validator("auth_jwt_secret")
    @classmethod
    def validate_auth_jwt_secret(cls, value: str) -> str:
        """Require explicit JWT secret in hosted Railway deployments."""
        secret = value.strip()
        if not secret:
            raise ValueError("AUTH_JWT_SECRET cannot be empty.")
        if _is_running_on_railway() and secret == "change-me-in-production":
            raise ValueError("AUTH_JWT_SECRET must be set to a secure non-default value on Railway.")
        return secret


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
