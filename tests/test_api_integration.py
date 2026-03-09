"""Integration tests for FastAPI routes using an isolated test database."""

from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal

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
from app.models import (
    ApiKey,
    CleanedListing,
    CostSubmissionType,
    ImportBatch,
    ModerationStatus,
    RawListing,
)
from app.services.api_key_auth import hash_api_key


class _FakeMCPServer:
    """Minimal FastMCP-compatible registry for testing tool functions."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):  # type: ignore[no-untyped-def]
        def decorator(func):  # type: ignore[no-untyped-def]
            self.tools[func.__name__] = func
            return func

        return decorator


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
                ModerationStatus(code="ACTIVE", label="Active", is_terminal=False),
                ModerationStatus(code="FLAGGED", label="Flagged", is_terminal=False),
                ModerationStatus(code="REMOVED", label="Removed", is_terminal=False),
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


def _seed_cleaned_listings(session_factory: sessionmaker, listings: list[dict]) -> None:
    with session_factory() as db:
        batch = ImportBatch(
            source_filename="test-cleaned-seed.csv",
            source_file_sha256="0" * 64,
            source_row_count=len(listings),
            imported_row_count=len(listings),
            status="completed",
        )
        db.add(batch)
        db.flush()

        for source_row_number, row in enumerate(listings, start=1):
            raw_listing = RawListing(
                import_batch_id=batch.id,
                source_row_number=source_row_number,
                source_row_data=row.get("source_row_data", {"seed": source_row_number}),
                source_row_hash=f"{source_row_number:064x}"[-64:],
            )
            db.add(raw_listing)
            db.flush()

            db.add(
                CleanedListing(
                    raw_listing_id=raw_listing.id,
                    import_batch_id=batch.id,
                    cleaning_version=row.get("cleaning_version", "v1"),
                    price_gbp_weekly=row.get("price_gbp_weekly"),
                    deposit_gbp=row.get("deposit_gbp"),
                    bedrooms=row.get("bedrooms"),
                    bathrooms=row.get("bathrooms"),
                    listing_type=row.get("listing_type"),
                    address_normalized=row.get("address_normalized"),
                    city=row.get("city"),
                    area=row.get("area"),
                    is_ensuite_proxy=row.get("is_ensuite_proxy"),
                    house_size_bucket=row.get("house_size_bucket"),
                    valid_price=row.get("valid_price", True),
                    valid_deposit=row.get("valid_deposit", False),
                    valid_bedrooms=row.get("valid_bedrooms", False),
                    valid_bathrooms=row.get("valid_bathrooms", False),
                    valid_type=row.get("valid_type", False),
                    valid_address=row.get("valid_address", False),
                    is_excluded=row.get("is_excluded", False),
                    exclusion_reasons=row.get("exclusion_reasons", []),
                )
            )

        db.commit()


def _register_mcp_analytics_tools_for_test(
    session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    from app.mcp.tools import analytics as analytics_tools_module
    from app.mcp.tools.analytics import register_analytics_tools

    fake_server = _FakeMCPServer()
    monkeypatch.setattr(analytics_tools_module, "SessionLocal", session_factory)
    register_analytics_tools(fake_server)  # type: ignore[arg-type]
    return fake_server.tools


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
    assert set(payload.keys()) == {
        "id",
        "city",
        "area",
        "submission_type",
        "moderation_status",
        "amount_gbp",
        "is_analytics_eligible",
        "is_suspicious",
        "suspicious_reasons",
        "duplicate_fingerprint",
        "venue_name",
        "item_name",
        "submission_notes",
        "submitted_at",
        "created_at",
        "updated_at",
    }
    assert payload["moderation_status"] == "ACTIVE"
    assert payload["is_analytics_eligible"] is True


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
    duplicate_detail = duplicate.json()["detail"]
    assert duplicate_detail["message"] == "Possible duplicate submission in recent window"
    assert duplicate_detail["duplicate_submission_id"] == first.json()["id"]


def test_moderation_flag_flow(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
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
        json={"moderation_status": "FLAGGED", "moderator_note": "Looks suspicious"},
        headers={"X-API-Key": "moderator-key-1"},
    )

    assert moderate_resp.status_code == 200
    moderation_payload = moderate_resp.json()
    assert set(moderation_payload.keys()) == {
        "id",
        "submission_id",
        "from_moderation_status",
        "to_moderation_status",
        "moderator_api_key_id",
        "moderator_key_name",
        "moderator_note",
        "created_at",
    }
    assert moderation_payload["to_moderation_status"] == "FLAGGED"

    get_resp = client.get(f"/api/v1/submissions/{submission_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["moderation_status"] == "FLAGGED"
    assert get_resp.json()["is_analytics_eligible"] is False


def test_invalid_moderation_transition_returns_conflict(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-8",
        raw_key="contrib-key-8",
        can_write=True,
        is_moderator=False,
    )
    _create_api_key(
        session_factory,
        key_name="moderator-8",
        raw_key="moderator-key-8",
        can_write=True,
        is_moderator=True,
    )

    create_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(amount_gbp="6.40"),
        headers={"X-API-Key": "contrib-key-8"},
    )
    assert create_resp.status_code == 201
    submission_id = create_resp.json()["id"]

    invalid_transition = client.post(
        f"/api/v1/submissions/{submission_id}/moderation",
        json={"moderation_status": "ACTIVE"},
        headers={"X-API-Key": "moderator-key-8"},
    )
    assert invalid_transition.status_code == 409
    assert "Invalid moderation transition" in invalid_transition.json()["detail"]


def test_active_submissions_are_included_in_cost_analytics(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-5",
        raw_key="contrib-key-5",
        can_write=True,
        is_moderator=False,
    )

    first_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="York", submission_type="PINT", amount_gbp="5.00"),
        headers={"X-API-Key": "contrib-key-5"},
    )
    assert first_resp.status_code == 201

    second_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="York", submission_type="PINT", amount_gbp="6.00"),
        headers={"X-API-Key": "contrib-key-5"},
    )
    assert second_resp.status_code == 201

    analytics = client.get("/api/v1/analytics/costs/cities/York?submission_type=PINT")
    assert analytics.status_code == 200
    assert analytics.json() == {
        "city": "York",
        "filters": {"submission_type": "PINT"},
        "metrics": {
            "average": 5.5,
            "median": 5.5,
            "min": 5.0,
            "max": 6.0,
            "sample_size": 2,
        },
    }


def test_affordability_score_response(client_and_sessionmaker: tuple[TestClient, sessionmaker]) -> None:
    client, session_factory = client_and_sessionmaker
    _create_api_key(
        session_factory,
        key_name="contributor-6",
        raw_key="contrib-key-6",
        can_write=True,
        is_moderator=False,
    )

    create_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="Bristol", submission_type="PINT", amount_gbp="5.80"),
        headers={"X-API-Key": "contrib-key-6"},
    )
    assert create_resp.status_code == 201

    score_resp = client.get("/api/v1/affordability/cities/Bristol/score?components=pint")
    assert score_resp.status_code == 200

    payload = score_resp.json()
    assert payload["city"] == "Bristol"
    assert payload["selected_components"] == ["pint"]
    assert set(payload.keys()) == {"city", "selected_components", "score", "score_band", "components", "weights", "formula"}
    assert "score" in payload
    assert "score_band" in payload
    assert "components" in payload
    assert "pint" in payload["components"]
    assert payload["formula"] == {
        "description": "No merged overall cost component. Pint and takeaway are scored separately.",
        "overall": "score = weighted_average(selected_component_scores)",
        "component": "component_score = clamp(100 * (ceiling - average_cost) / (ceiling - floor), 0, 100)",
    }


def test_rent_analytics_response_contracts_unchanged(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = client_and_sessionmaker
    _seed_cleaned_listings(
        session_factory,
        [
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("100.00"),
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("120.00"),
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "City Centre",
                "price_gbp_weekly": Decimal("200.00"),
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "City Centre",
                "price_gbp_weekly": Decimal("50.00"),
                "valid_price": False,
            },
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("80.00"),
                "valid_price": True,
                "is_excluded": True,
            },
        ],
    )

    cities_resp = client.get("/api/v1/analytics/rent/cities")
    assert cities_resp.status_code == 200
    assert cities_resp.json() == {
        "cities": [
            {
                "name": "Leeds",
                "sample_size": 3,
            }
        ],
        "total": 1,
    }

    city_resp = client.get("/api/v1/analytics/rent/cities/Leeds")
    assert city_resp.status_code == 200
    assert city_resp.json() == {
        "city": "Leeds",
        "filters": {"bedrooms": None, "property_type": None, "ensuite_proxy": None},
        "metrics": {
            "average": 140.0,
            "median": 120.0,
            "min": 100.0,
            "max": 200.0,
            "sample_size": 3,
        },
    }

    area_resp = client.get("/api/v1/analytics/rent/cities/Leeds/areas/Hyde%20Park")
    assert area_resp.status_code == 200
    assert area_resp.json() == {
        "city": "Leeds",
        "area": "Hyde Park",
        "filters": {"bedrooms": None, "property_type": None, "ensuite_proxy": None},
        "metrics": {
            "average": 110.0,
            "median": 110.0,
            "min": 100.0,
            "max": 120.0,
            "sample_size": 2,
        },
    }

    city_areas_resp = client.get("/api/v1/analytics/rent/cities/Leeds/areas")
    assert city_areas_resp.status_code == 200
    assert city_areas_resp.json() == {
        "city": "Leeds",
        "filters": {"bedrooms": None, "property_type": None, "ensuite_proxy": None},
        "areas": [
            {
                "area": "City Centre",
                "average": 200.0,
                "median": 200.0,
                "min": 200.0,
                "max": 200.0,
                "sample_size": 1,
            },
            {
                "area": "Hyde Park",
                "average": 110.0,
                "median": 110.0,
                "min": 100.0,
                "max": 120.0,
                "sample_size": 2,
            },
        ],
    }


def test_rent_city_discovery_merges_case_variants_and_applies_min_sample_size(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
) -> None:
    client, session_factory = client_and_sessionmaker
    _seed_cleaned_listings(
        session_factory,
        [
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("100.00"),
                "valid_price": True,
            },
            {
                "city": "leeds",
                "area": "Headingley",
                "price_gbp_weekly": Decimal("120.00"),
                "valid_price": True,
            },
            {
                "city": "Ecclesall road",
                "area": "Sharrow",
                "price_gbp_weekly": Decimal("110.00"),
                "valid_price": True,
            },
        ],
    )

    cities_resp = client.get("/api/v1/analytics/rent/cities?min_sample_size=2")
    assert cities_resp.status_code == 200
    assert cities_resp.json() == {
        "cities": [
            {
                "name": "Leeds",
                "sample_size": 2,
            }
        ],
        "total": 1,
    }


def test_workflow_active_to_removed_to_active_affects_analytics(
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
    assert before.status_code == 200
    assert before.json()["metrics"]["sample_size"] == 1
    assert before.json()["metrics"]["average"] == 9.5

    remove = client.post(
        f"/api/v1/submissions/{submission_id}/moderation",
        json={"moderation_status": "REMOVED"},
        headers={"X-API-Key": "moderator-key-4"},
    )
    assert remove.status_code == 200

    after_remove = client.get("/api/v1/analytics/costs/cities/Cardiff?submission_type=TAKEAWAY")
    assert after_remove.status_code == 404

    restore = client.post(
        f"/api/v1/submissions/{submission_id}/moderation",
        json={"moderation_status": "ACTIVE"},
        headers={"X-API-Key": "moderator-key-4"},
    )
    assert restore.status_code == 200

    after_restore = client.get("/api/v1/analytics/costs/cities/Cardiff?submission_type=TAKEAWAY")
    assert after_restore.status_code == 200
    assert after_restore.json()["metrics"]["sample_size"] == 1
    assert after_restore.json()["metrics"]["average"] == 9.5


def test_mcp_city_rent_matches_rest_output(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = client_and_sessionmaker
    _seed_cleaned_listings(
        session_factory,
        [
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("110.00"),
                "bedrooms": 2,
                "listing_type": "flat",
                "is_ensuite_proxy": True,
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("130.00"),
                "bedrooms": 3,
                "listing_type": "house",
                "is_ensuite_proxy": False,
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "Headingley",
                "price_gbp_weekly": Decimal("150.00"),
                "bedrooms": 2,
                "listing_type": "flat",
                "is_ensuite_proxy": True,
                "valid_price": True,
            },
        ],
    )

    tools = _register_mcp_analytics_tools_for_test(session_factory, monkeypatch)
    mcp_payload = tools["get_city_rent_analytics"](city="Leeds")  # type: ignore[operator]

    rest_payload = client.get("/api/v1/analytics/rent/cities/Leeds").json()
    assert mcp_payload == rest_payload


def test_mcp_area_rent_matches_rest_output(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = client_and_sessionmaker
    _seed_cleaned_listings(
        session_factory,
        [
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("110.00"),
                "bedrooms": 2,
                "listing_type": "flat",
                "is_ensuite_proxy": True,
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("130.00"),
                "bedrooms": 3,
                "listing_type": "house",
                "is_ensuite_proxy": False,
                "valid_price": True,
            },
            {
                "city": "Leeds",
                "area": "Hyde Park",
                "price_gbp_weekly": Decimal("125.00"),
                "bedrooms": 2,
                "listing_type": "flat",
                "is_ensuite_proxy": False,
                "valid_price": True,
            },
        ],
    )

    tools = _register_mcp_analytics_tools_for_test(session_factory, monkeypatch)
    mcp_payload = tools["get_area_rent_analytics"](
        city="Leeds",
        area="Hyde Park",
        bedrooms=2,
        property_type="FLAT",
        ensuite_proxy=True,
    )  # type: ignore[operator]

    rest_payload = client.get(
        "/api/v1/analytics/rent/cities/Leeds/areas/Hyde%20Park?bedrooms=2&property_type=FLAT&ensuite_proxy=true"
    ).json()
    assert mcp_payload == rest_payload


def test_mcp_affordability_score_matches_rest_output(
    client_and_sessionmaker: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = client_and_sessionmaker
    _seed_cleaned_listings(
        session_factory,
        [
            {
                "city": "Manchester",
                "area": "Fallowfield",
                "price_gbp_weekly": Decimal("160.00"),
                "valid_price": True,
            },
            {
                "city": "Manchester",
                "area": "City Centre",
                "price_gbp_weekly": Decimal("200.00"),
                "valid_price": True,
            },
        ],
    )

    _create_api_key(
        session_factory,
        key_name="mcp-contributor-1",
        raw_key="mcp-contrib-key-1",
        can_write=True,
        is_moderator=False,
    )
    create_resp = client.post(
        "/api/v1/submissions",
        json=_submission_payload(city="Manchester", area="Fallowfield", submission_type="PINT", amount_gbp="6.20"),
        headers={"X-API-Key": "mcp-contrib-key-1"},
    )
    assert create_resp.status_code == 201

    tools = _register_mcp_analytics_tools_for_test(session_factory, monkeypatch)
    mcp_payload = tools["get_affordability_score"](
        city="Manchester",
        components="rent,pint",
        rent_weight=0.7,
        pint_weight=0.3,
        takeaway_weight=0.0,
    )  # type: ignore[operator]

    rest_payload = client.get(
        "/api/v1/affordability/cities/Manchester/score"
        "?components=rent,pint&rent_weight=0.7&pint_weight=0.3&takeaway_weight=0.0"
    ).json()
    # REST response models include optional keys with null values; MCP returns raw service output.
    if rest_payload.get("components", {}).get("rent", {}).get("submission_type") is None:
        rest_payload["components"]["rent"].pop("submission_type", None)
    assert mcp_payload == rest_payload
