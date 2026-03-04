"""Lightweight health endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.common import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    summary="Service Health",
    description="Lightweight liveness check for monitoring and local smoke tests.",
    response_model=HealthResponse,
    responses={200: {"description": "Service is reachable."}},
)
def health_check() -> HealthResponse:
    """Return service availability status."""
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return HealthResponse(status="ok", timestamp=timestamp)
