"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.routers import api_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for the Student Affordability Intelligence API."""
    resolved_settings = settings or get_settings()
    runtime_mode = resolved_settings.app_runtime_mode

    include_rest_api = runtime_mode in {"rest", "both"}
    include_mcp_http = runtime_mode in {"mcp", "both"}

    if include_mcp_http and not resolved_settings.mcp_http_enabled:
        raise RuntimeError(
            "MCP runtime mode selected but MCP HTTP transport is disabled. "
            "Set MCP_HTTP_ENABLED=true or switch APP_RUNTIME_MODE to 'rest'."
        )

    mcp_lifespan = None
    mcp_mount_app = None
    if include_mcp_http:
        if not resolved_settings.mcp_http_mount_path.startswith("/"):
            raise RuntimeError("MCP_HTTP_MOUNT_PATH must start with '/'.")

        from app.mcp.server import create_mcp_http_integration

        mcp_http_integration = create_mcp_http_integration(resolved_settings)
        mcp_lifespan = mcp_http_integration.lifespan
        mcp_mount_app = mcp_http_integration.asgi_app

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        lifespan=mcp_lifespan,
    )

    cors_origins = [
        origin.strip()
        for origin in resolved_settings.cors_allowed_origins.split(",")
        if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if include_rest_api:
        app.include_router(api_router, prefix=resolved_settings.api_prefix)

    if mcp_mount_app is not None:
        app.mount(resolved_settings.mcp_http_mount_path, mcp_mount_app)

    return app


app = create_app()
