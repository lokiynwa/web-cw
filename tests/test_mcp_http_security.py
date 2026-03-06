"""Security tests for HTTP-based MCP middleware controls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.mcp.security import MCPHTTPSecurityMiddleware


def _build_secured_test_client(settings: Settings) -> TestClient:
    inner_app = FastAPI()

    @inner_app.post("/")
    async def _echo_ok() -> dict[str, bool]:
        return {"ok": True}

    secured_app = MCPHTTPSecurityMiddleware(inner_app, settings)
    return TestClient(secured_app)


def _tools_call_payload(tool_name: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": {}},
    }


def test_origin_header_is_rejected_when_not_allowlisted() -> None:
    client = _build_secured_test_client(
        Settings(
            mcp_http_validate_origin=True,
            mcp_http_allowed_origins="https://allowed.example",
            mcp_http_allow_requests_without_origin=False,
            mcp_http_public_read_tools=True,
        )
    )

    response = client.post(
        "/",
        json=_tools_call_payload("get_city_rent_analytics"),
        headers={"Origin": "https://blocked.example"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Origin is not allowed for MCP HTTP requests"


def test_origin_header_can_be_required() -> None:
    client = _build_secured_test_client(
        Settings(
            mcp_http_validate_origin=True,
            mcp_http_allowed_origins="https://allowed.example",
            mcp_http_allow_requests_without_origin=False,
            mcp_http_public_read_tools=True,
        )
    )

    response = client.post("/", json=_tools_call_payload("get_city_rent_analytics"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Origin header is required for MCP HTTP requests"


def test_public_read_tool_can_be_called_without_api_key_when_enabled() -> None:
    client = _build_secured_test_client(
        Settings(
            mcp_http_validate_origin=False,
            mcp_http_public_read_tools=True,
        )
    )

    response = client.post("/", json=_tools_call_payload("get_city_rent_analytics"))

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_public_read_tool_requires_api_key_when_configured_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.mcp.security.resolve_api_key_record_from_raw_value",
        lambda raw_key, _db: (
            SimpleNamespace(can_write=False, is_moderator=False) if raw_key == "valid-read-key" else None
        ),
    )

    client = _build_secured_test_client(
        Settings(
            mcp_http_validate_origin=False,
            mcp_http_public_read_tools=False,
        )
    )

    missing_key = client.post("/", json=_tools_call_payload("get_city_rent_analytics"))
    assert missing_key.status_code == 401

    valid_key = client.post(
        "/",
        json=_tools_call_payload("get_city_rent_analytics"),
        headers={"X-API-Key": "valid-read-key"},
    )
    assert valid_key.status_code == 200
    assert valid_key.json() == {"ok": True}


def test_sensitive_write_tool_requires_contributor_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = {
        "viewer-key": SimpleNamespace(can_write=False, is_moderator=False),
        "contributor-key": SimpleNamespace(can_write=True, is_moderator=False),
    }
    monkeypatch.setattr(
        "app.mcp.security.resolve_api_key_record_from_raw_value",
        lambda raw_key, _db: keys.get(raw_key or ""),
    )

    client = _build_secured_test_client(
        Settings(
            mcp_http_validate_origin=False,
            mcp_http_public_read_tools=True,
        )
    )

    missing_key = client.post("/", json=_tools_call_payload("create_submission"))
    assert missing_key.status_code == 401

    viewer_key = client.post(
        "/",
        json=_tools_call_payload("create_submission"),
        headers={"X-API-Key": "viewer-key"},
    )
    assert viewer_key.status_code == 403
    assert viewer_key.json()["detail"] == "Contributor API key required"

    contributor_key = client.post(
        "/",
        json=_tools_call_payload("create_submission"),
        headers={"X-API-Key": "contributor-key"},
    )
    assert contributor_key.status_code == 200


def test_moderation_tool_requires_moderator_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = {
        "contributor-key": SimpleNamespace(can_write=True, is_moderator=False),
        "moderator-key": SimpleNamespace(can_write=True, is_moderator=True),
    }
    monkeypatch.setattr(
        "app.mcp.security.resolve_api_key_record_from_raw_value",
        lambda raw_key, _db: keys.get(raw_key or ""),
    )

    client = _build_secured_test_client(
        Settings(
            mcp_http_validate_origin=False,
            mcp_http_public_read_tools=True,
        )
    )

    contributor_attempt = client.post(
        "/",
        json=_tools_call_payload("moderate_submission"),
        headers={"X-API-Key": "contributor-key"},
    )
    assert contributor_attempt.status_code == 403
    assert contributor_attempt.json()["detail"] == "Moderator API key required"

    moderator_attempt = client.post(
        "/",
        json=_tools_call_payload("moderate_submission"),
        headers={"X-API-Key": "moderator-key"},
    )
    assert moderator_attempt.status_code == 200

