"""API smoke tests."""

from datetime import datetime

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, create_app


def test_health_check_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "timestamp" in payload
    # Accept the endpoint's UTC Z-suffixed ISO timestamp.
    datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))


def test_create_app_uses_injected_settings() -> None:
    custom_settings = Settings(
        app_name="Test API",
        app_version="9.9.9",
        debug=True,
        api_prefix="/custom",
    )
    custom_app = create_app(custom_settings)

    assert custom_app.title == "Test API"
    assert custom_app.version == "9.9.9"
    assert custom_app.debug is True
