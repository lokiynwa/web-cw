"""Lightweight health endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    """Return service availability status."""
    return {"status": "ok"}
