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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
