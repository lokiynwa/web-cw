"""Integration tests for FastAPI routes using an isolated test database."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure env is valid before importing app modules that instantiate settings.
_debug_env = os.getenv("DEBUG")
if _debug_env is None:
    os.environ["DEBUG"] = "false"
elif _debug_env.strip().lower() not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
    os.environ["DEBUG"] = "false"

import app.models  # noqa: F401 - ensure model tables are registered on metadata
from app.db import Base, get_db
from app.main import create_app
from app.models import ApiKey, CostSubmissionType, ModerationStatus
from app.services.api_key_auth import hash_api_key


@pytest.fixture()
def client_and_sessionmaker() -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        db.add_all(
            [
                CostSubmissionType(code="PINT", label="Pint", is_active=True),
                CostSubmissionType(code="TAKEAWAY", label="Takeaway", is_active=True),
                ModerationStatus(code="PENDING", label="Pending", is_terminal=False),
                ModerationStatus(code="APPROVED", label="Approved", is_terminal=True),
                ModerationStatus(code="REJECTED", label="Rejected", is_terminal=True),
            ]
        )
        db.commit()

    def override_get_db() -> Iterator:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    try:
        yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _create_api_key(
    session_factory: sessionmaker,
    *,
    key_name: str,
    raw_key: str,
    can_write: bool,
    is_moderator: bool,
) -> None:
    with session_factory() as db:
        db.add(
            ApiKey(
                key_name=key_name,
                key_prefix=raw_key[:16],
                key_hash=hash_api_key(raw_key),
                can_write=can_write,
                is_moderator=is_moderator,
                is_active=True,
            )
        )
        db.commit()


def _submission_payload(
    *,
    city: str = "Leeds",
    area: str = "Hyde Park",
    submission_type: str = "PINT",
    amount_gbp: str = "5.50",
) -> dict:
    return {
        "city": city,
        "area": area,
        "submission_type": submission_type,
        "amount_gbp": amount_gbp,
        "venue_name": "Test Venue",
        "item_name": "Test Item",
    }


def test_submission_creation(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-1",
        raw_key="contrib-key-1",
        can_write=True,
        is_moderator=False,
    )

    response = client.post(
        "/api/v1/submissions",
        json=_submission_payload(),
        headers={"X-API-Key": "contrib-key-1"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["moderation_status"] == "PENDING"
    assert payload["is_analytics_eligible"] is False


def test_invalid_submission_validation(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-2",
        raw_key="contrib-key-2",
        can_write=True,
        is_moderator=False,
    )

    response = client.post(
        "/api/v1/submissions",
        json=_submission_payload(submission_type="INVALID_TYPE", amount_gbp="5.00"),
        headers={"X-API-Key": "contrib-key-2"},
    )

    assert response.status_code == 422


def test_duplicate_prevention(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-3",
        raw_key="contrib-key-3",
        can_write=True,
        is_moderator=False,
    )

    first = client.post(
        "/api/v1/submissions",
        json=_submission_payload(amount_gbp="5.50"),
        headers={"X-API-Key": "contrib-key-3"},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/submissions",
        json=_submission_payload(amount_gbp="5.60"),
        headers={"X-API-Key": "contrib-key-3"},
    )
    assert duplicate.status_code == 409


def test_moderation_approval_flow(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-4",
        raw_key="contrib-key-4",
        can_write=True,
        is_moderator=False,
    )
    _create_api_key(
        session_factory,
        key_name="moderator-1",
        raw_key="moderator-key-1",
        can_write=True,
        is_moderator=True,
    )

    create_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(amount_gbp="6.20"),
        headers={"X-API-Key": "contrib-key-4"},
    )
    submission_id = create_resp.json()["id"]

    moderate_resp = client.post(
        f"/api/v1/submissions/{submission_id}/moderation",
        json={"moderation_status": "APPROVED", "moderator_note": "Looks good"},
        headers={"X-API-Key": "moderator-key-1"},
    )

    assert moderate_resp.status_code == 200
    assert moderate_resp.json()["to_moderation_status"] == "APPROVED"

    get_resp = client.get(f"/api/v1/submissions/{submission_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["moderation_status"] == "APPROVED"
    assert get_resp.json()["is_analytics_eligible"] is True


def test_approved_only_inclusion_in_cost_analytics(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-5",
        raw_key="contrib-key-5",
        can_write=True,
        is_moderator=False,
    )
    _create_api_key(
        session_factory,
        key_name="moderator-2",
        raw_key="moderator-key-2",
        can_write=True,
        is_moderator=True,
    )

    pending_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="York", submission_type="PINT", amount_gbp="5.00"),
        headers={"X-API-Key": "contrib-key-5"},
    )
    assert pending_resp.status_code == 201

    approved_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="York", submission_type="PINT", amount_gbp="6.00"),
        headers={"X-API-Key": "contrib-key-5"},
    )
    assert approved_resp.status_code == 201

    approved_id = approved_resp.json()["id"]
    mod_resp = client.post(
        f"/api/v1/submissions/{approved_id}/moderation",
        json={"moderation_status": "APPROVED"},
        headers={"X-API-Key": "moderator-key-2"},
    )
    assert mod_resp.status_code == 200

    analytics = client.get("/api/v1/analytics/costs/cities/York?submission_type=PINT")
    assert analytics.status_code == 200
    metrics = analytics.json()["metrics"]
    assert metrics["sample_size"] == 1
    assert metrics["average"] == 6.0


def test_affordability_score_response(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-6",
        raw_key="contrib-key-6",
        can_write=True,
        is_moderator=False,
    )
    _create_api_key(
        session_factory,
        key_name="moderator-3",
        raw_key="moderator-key-3",
        can_write=True,
        is_moderator=True,
    )

    create_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="Bristol", submission_type="PINT", amount_gbp="5.80"),
        headers={"X-API-Key": "contrib-key-6"},
    )
    assert create_resp.status_code == 201

    submission_id = create_resp.json()["id"]
    mod_resp = client.post(
        f"/api/v1/submissions/{submission_id}/moderation",
        json={"moderation_status": "APPROVED"},
        headers={"X-API-Key": "moderator-key-3"},
    )
    assert mod_resp.status_code == 200

    score_resp = client.get("/api/v1/affordability/cities/Bristol/score?components=pint")
    assert score_resp.status_code == 200

    payload = score_resp.json()
    assert payload["city"] == "Bristol"
    assert payload["selected_components"] == ["pint"]
    assert "score" in payload
    assert "score_band" in payload
    assert "components" in payload
    assert "pint" in payload["components"]


def test_workflow_pending_to_approved_affects_analytics(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-7",
        raw_key="contrib-key-7",
        can_write=True,
        is_moderator=False,
    )
    _create_api_key(
        session_factory,
        key_name="moderator-4",
        raw_key="moderator-key-4",
        can_write=True,
        is_moderator=True,
    )

    create_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="Cardiff", submission_type="TAKEAWAY", amount_gbp="9.50"),
        headers={"X-API-Key": "contrib-key-7"},
    )
    assert create_resp.status_code == 201
    submission_id = create_resp.json()["id"]

    before = client.get("/api/v1/analytics/costs/cities/Cardiff?submission_type=TAKEAWAY")
    assert before.status_code == 404

    approve = client.post(
        f"/api/v1/submissions/{submission_id}/moderation",
        json={"moderation_status": "APPROVED"},
        headers={"X-API-Key": "moderator-key-4"},
    )
    assert approve.status_code == 200

    after = client.get("/api/v1/analytics/costs/cities/Cardiff?submission_type=TAKEAWAY")
    assert after.status_code == 200
    assert after.json()["metrics"]["sample_size"] == 1
    assert after.json()["metrics"]["average"] == 9.5
