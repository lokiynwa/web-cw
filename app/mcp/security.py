"""Security controls for HTTP-based MCP transport."""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.db import SessionLocal
from app.services.api_key_auth import resolve_api_key_record_from_raw_value

if TYPE_CHECKING:
    from app.models import ApiKey


class MCPToolAccessLevel(str, Enum):
    """Access levels used to secure MCP tool calls."""

    PUBLIC_READ = "public_read"
    AUTHENTICATED = "authenticated"
    CONTRIBUTOR = "contributor"
    MODERATOR = "moderator"


_TOOL_ACCESS_LEVELS: dict[str, MCPToolAccessLevel] = {}


def register_tool_access_level(tool_name: str, access_level: MCPToolAccessLevel) -> None:
    """Register access level metadata for a tool name."""
    _TOOL_ACCESS_LEVELS[tool_name] = access_level


def _default_access_level_for_tool(tool_name: str) -> MCPToolAccessLevel:
    name = tool_name.strip().lower()
    if name.startswith(("get_", "list_", "search_")):
        return MCPToolAccessLevel.PUBLIC_READ
    if "moderat" in name or name.startswith(("approve_", "reject_")):
        return MCPToolAccessLevel.MODERATOR
    if name.startswith(("create_", "update_", "delete_", "submit_")):
        return MCPToolAccessLevel.CONTRIBUTOR
    if "submission" in name or "write" in name:
        return MCPToolAccessLevel.CONTRIBUTOR
    return MCPToolAccessLevel.CONTRIBUTOR


def resolve_tool_access_level(tool_name: str) -> MCPToolAccessLevel:
    """Resolve access level for a tool using explicit metadata or secure defaults."""
    return _TOOL_ACCESS_LEVELS.get(tool_name, _default_access_level_for_tool(tool_name))


def _access_level_rank(level: MCPToolAccessLevel) -> int:
    order = {
        MCPToolAccessLevel.PUBLIC_READ: 0,
        MCPToolAccessLevel.AUTHENTICATED: 1,
        MCPToolAccessLevel.CONTRIBUTOR: 2,
        MCPToolAccessLevel.MODERATOR: 3,
    }
    return order[level]


def _merge_access_levels(levels: list[MCPToolAccessLevel]) -> MCPToolAccessLevel | None:
    if not levels:
        return None
    return max(levels, key=_access_level_rank)


def _normalize_allowed_origins(raw_value: str) -> set[str]:
    if not raw_value.strip():
        return set()
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def _extract_called_tool_names(payload: object) -> list[str]:
    names: list[str] = []

    if isinstance(payload, list):
        for item in payload:
            names.extend(_extract_called_tool_names(item))
        return names

    if not isinstance(payload, dict):
        return names

    method = payload.get("method")
    if method == "tools/call":
        params = payload.get("params")
        if isinstance(params, dict):
            name = params.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())

    # Support wrapper payloads by scanning nested objects.
    for nested_key in ("messages", "batch", "requests"):
        nested = payload.get(nested_key)
        if isinstance(nested, list):
            names.extend(_extract_called_tool_names(nested))

    return names


class MCPHTTPSecurityMiddleware:
    """ASGI middleware for origin and API-key based MCP HTTP controls."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings
        self.allowed_origins = _normalize_allowed_origins(settings.mcp_http_allowed_origins)
        self.api_key_header_name = settings.api_key_header_name.lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}

        origin_error = self._validate_origin(headers.get("origin"))
        if origin_error is not None:
            await JSONResponse(status_code=403, content={"detail": origin_error})(scope, receive, send)
            return

        body = await self._read_request_body(receive)
        required_access = self._required_access_for_request(body)

        auth_error = self._authorize_request(required_access, headers.get(self.api_key_header_name))
        if auth_error is not None:
            status_code, detail = auth_error
            await JSONResponse(status_code=status_code, content={"detail": detail})(scope, receive, send)
            return

        replay_receive = self._build_replay_receive(body)
        await self.app(scope, replay_receive, send)

    def _validate_origin(self, origin_header: str | None) -> str | None:
        if not self.settings.mcp_http_validate_origin:
            return None

        origin = (origin_header or "").strip()
        if not origin:
            if self.settings.mcp_http_allow_requests_without_origin:
                return None
            return "Origin header is required for MCP HTTP requests"

        if "*" in self.allowed_origins:
            return None
        if not self.allowed_origins:
            return "Origin validation is enabled but no allowed origins are configured"
        if origin not in self.allowed_origins:
            return "Origin is not allowed for MCP HTTP requests"
        return None

    @staticmethod
    async def _read_request_body(receive: Receive) -> bytes:
        body_chunks: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body_chunks.append(message.get("body", b""))
            more_body = message.get("more_body", False)
        return b"".join(body_chunks)

    @staticmethod
    def _build_replay_receive(body: bytes) -> Receive:
        sent = False

        async def replay_receive() -> Message:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return replay_receive

    def _required_access_for_request(self, body: bytes) -> MCPToolAccessLevel | None:
        if not body:
            return None

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        tool_names = _extract_called_tool_names(payload)
        if not tool_names:
            return None

        levels = [resolve_tool_access_level(tool_name) for tool_name in tool_names]
        required = _merge_access_levels(levels)
        if required is None:
            return None

        if required == MCPToolAccessLevel.PUBLIC_READ and not self.settings.mcp_http_public_read_tools:
            return MCPToolAccessLevel.AUTHENTICATED

        return required

    def _authorize_request(
        self,
        required_access: MCPToolAccessLevel | None,
        api_key_value: str | None,
    ) -> tuple[int, str] | None:
        if required_access is None:
            return None
        if required_access == MCPToolAccessLevel.PUBLIC_READ:
            return None

        with SessionLocal() as db:
            api_key = resolve_api_key_record_from_raw_value(api_key_value, db)

        if api_key is None:
            return 401, "Missing or invalid API key"

        if required_access == MCPToolAccessLevel.AUTHENTICATED:
            return None
        if required_access == MCPToolAccessLevel.CONTRIBUTOR:
            if not self._is_contributor(api_key):
                return 403, "Contributor API key required"
            return None
        if required_access == MCPToolAccessLevel.MODERATOR:
            if not api_key.is_moderator:
                return 403, "Moderator API key required"
            return None

        return 403, "Forbidden"

    @staticmethod
    def _is_contributor(api_key: ApiKey) -> bool:
        return bool(api_key.can_write or api_key.is_moderator)
