"""API smoke tests."""

from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "timestamp" in payload
    # Accept the endpoint's UTC Z-suffixed ISO timestamp.
    datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
