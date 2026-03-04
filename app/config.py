"""Application configuration management."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings."""

    app_name: str = "Student Affordability Intelligence API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./student_affordability.db"
    api_key_enabled: bool = False
    api_key_header_name: str = "X-API-Key"
    api_key_secret: str = ""
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    affordability_rent_weight: float = 0.6
    affordability_pint_weight: float = 0.2
    affordability_takeaway_weight: float = 0.2
    affordability_rent_floor_gbp_weekly: float = 80.0
    affordability_rent_ceiling_gbp_weekly: float = 300.0
    affordability_cost_floor_gbp: float = 2.0
    affordability_cost_ceiling_gbp: float = 20.0
    affordability_pint_floor_gbp: float = 2.0
    affordability_pint_ceiling_gbp: float = 10.0
    affordability_takeaway_floor_gbp: float = 5.0
    affordability_takeaway_ceiling_gbp: float = 25.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
