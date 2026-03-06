"""Submission MCP tools placeholder for future write-capable operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.mcp.security import MCPToolAccessLevel, register_tool_access_level

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_submission_tools(_server: FastMCP) -> None:
    """Register submission tools.

    Intentionally empty for now: local MCP currently exposes read-only tools only.
    """
    # Pre-register future sensitive tool names with secure defaults.
    register_tool_access_level("create_submission", MCPToolAccessLevel.CONTRIBUTOR)
    register_tool_access_level("update_submission", MCPToolAccessLevel.CONTRIBUTOR)
    register_tool_access_level("delete_submission", MCPToolAccessLevel.CONTRIBUTOR)
    register_tool_access_level("moderate_submission", MCPToolAccessLevel.MODERATOR)
