"""Submission MCP tools placeholder for future write-capable operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_submission_tools(_server: FastMCP) -> None:
    """Register submission tools.

    Intentionally empty for now: local MCP currently exposes read-only tools only.
    """
