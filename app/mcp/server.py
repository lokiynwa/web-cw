"""Local MCP server entrypoint using FastMCP (stdio transport)."""

from __future__ import annotations

from app.config import get_settings

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised only when dependency missing.
    raise RuntimeError(
        "FastMCP is not installed. Install the MCP SDK (e.g. `pip install mcp`) before running the local MCP server."
    ) from exc


def create_mcp_server() -> FastMCP:
    """Build and configure the local MCP server instance."""
    from app.mcp.tools import register_analytics_tools, register_submission_tools

    settings = get_settings()
    server = FastMCP(f"{settings.app_name} MCP")

    register_analytics_tools(server)
    register_submission_tools(server)

    return server


mcp_server = create_mcp_server()


def main() -> None:
    """Run the local MCP server over stdio."""
    mcp_server.run()


if __name__ == "__main__":
    main()
