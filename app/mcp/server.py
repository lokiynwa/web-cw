"""MCP server entrypoints for stdio and HTTP transports."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.config import Settings, get_settings
from app.mcp.security import MCPHTTPSecurityMiddleware

if TYPE_CHECKING:
    from fastapi import FastAPI
    from mcp.server.fastmcp import FastMCP
    from starlette.types import ASGIApp


def _import_fastmcp_class() -> type[FastMCP]:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only when dependency missing.
        raise RuntimeError(
            "FastMCP is not installed. Install the MCP SDK (e.g. `pip install mcp`) before running MCP transports."
        ) from exc
    return FastMCP


def create_mcp_server(settings: Settings | None = None) -> FastMCP:
    """Build and configure an MCP server instance."""
    from app.mcp.tools import register_analytics_tools, register_submission_tools

    FastMCP = _import_fastmcp_class()
    resolved_settings = settings or get_settings()
    server = FastMCP(f"{resolved_settings.app_name} MCP")

    register_analytics_tools(server)
    register_submission_tools(server)

    return server


@dataclass
class MCPHTTPIntegration:
    """HTTP-mount integration objects for FastAPI apps."""

    asgi_app: ASGIApp
    lifespan: Callable[[FastAPI], Any]


def create_mcp_http_integration(settings: Settings | None = None) -> MCPHTTPIntegration:
    """Create Streamable HTTP MCP integration for mounting into FastAPI."""
    resolved_settings = settings or get_settings()
    if not resolved_settings.mcp_http_enabled:
        raise RuntimeError("MCP HTTP transport is disabled. Set MCP_HTTP_ENABLED=true to mount MCP over HTTP.")

    server = create_mcp_server(resolved_settings)
    streamable_http_app = server.streamable_http_app(stateless_http=resolved_settings.mcp_http_stateless)
    secured_streamable_http_app = MCPHTTPSecurityMiddleware(streamable_http_app, resolved_settings)

    @asynccontextmanager
    async def mcp_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with server.session_manager.run():
            yield

    return MCPHTTPIntegration(asgi_app=secured_streamable_http_app, lifespan=mcp_lifespan)


def main() -> None:
    """Run the MCP server over local stdio transport."""
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    main()
