"""Tool registration modules for the local MCP server."""

from app.mcp.tools.analytics import register_analytics_tools
from app.mcp.tools.submissions import register_submission_tools

__all__ = ["register_analytics_tools", "register_submission_tools"]

