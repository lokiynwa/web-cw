"""Lightweight health endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    """Return service availability status."""
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"status": "ok", "timestamp": timestamp}
