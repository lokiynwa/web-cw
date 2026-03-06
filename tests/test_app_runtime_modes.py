"""Tests for env-driven application runtime mode selection."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from types import ModuleType

import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app


def _route_paths(app: FastAPI) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_rest_runtime_mode_keeps_rest_routes() -> None:
    app = create_app(
        Settings(
            app_runtime_mode="rest",
            mcp_http_enabled=False,
            api_prefix="/api/v1",
        )
    )

    assert "/api/v1/health" in _route_paths(app)


def test_mcp_runtime_mode_requires_http_enablement() -> None:
    with pytest.raises(RuntimeError, match="MCP runtime mode selected"):
        create_app(
            Settings(
                app_runtime_mode="mcp",
                mcp_http_enabled=False,
            )
        )


def test_both_runtime_mode_mounts_mcp_and_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _StubIntegration:
        def __init__(self) -> None:
            self.asgi_app = FastAPI()

            @asynccontextmanager
            async def _lifespan(_app: FastAPI):
                yield

            self.lifespan = _lifespan

    stub_module = ModuleType("app.mcp.server")

    def _create_mcp_http_integration(_settings: Settings) -> _StubIntegration:
        return _StubIntegration()

    stub_module.create_mcp_http_integration = _create_mcp_http_integration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.mcp.server", stub_module)

    app = create_app(
        Settings(
            app_runtime_mode="both",
            mcp_http_enabled=True,
            mcp_http_mount_path="/mcp",
            api_prefix="/api/v1",
        )
    )

    paths = _route_paths(app)
    assert "/api/v1/health" in paths
    assert "/mcp" in paths
