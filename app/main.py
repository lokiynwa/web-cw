"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.config import get_settings
from app.routers import api_router


def create_app() -> FastAPI:
    """Application factory for the Student Affordability Intelligence API."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
