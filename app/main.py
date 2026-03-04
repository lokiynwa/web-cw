"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.routers import api_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for the Student Affordability Intelligence API."""
    resolved_settings = settings or get_settings()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
    )

    app.include_router(api_router, prefix=resolved_settings.api_prefix)

    return app


app = create_app()
