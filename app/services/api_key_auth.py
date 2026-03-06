"""API key authentication helpers for protected endpoints."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiKey

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    scheme_name="ApiKeyAuth",
    description="API key for contributor and moderator protected endpoints.",
)


def hash_api_key(raw_key: str) -> str:
    """Hash API key input using SHA-256 hex digest."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _resolve_api_key_record(api_key_value: str | None, db: Session) -> ApiKey | None:
    """Resolve an active API key record from the incoming key value."""
    if not api_key_value or not api_key_value.strip():
        return None

    hashed_key = hash_api_key(api_key_value.strip())
    now = datetime.now(timezone.utc)

    stmt = select(ApiKey).where(
        and_(
            ApiKey.is_active.is_(True),
            ApiKey.revoked_at.is_(None),
            or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now),
            func.lower(ApiKey.key_hash) == hashed_key.lower(),
        )
    )
    api_key = db.execute(stmt).scalar_one_or_none()
    if api_key is None:
        return None

    api_key.last_used_at = now
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return api_key


def resolve_api_key_record_from_raw_value(api_key_value: str | None, db: Session) -> ApiKey | None:
    """Resolve API key record from a raw header value.

    This helper is used by non-FastAPI-dependency auth paths such as MCP HTTP middleware.
    """
    return _resolve_api_key_record(api_key_value, db)


def get_api_key_record(
    api_key_value: Annotated[str | None, Security(api_key_header)] = None,
    db: Session = Depends(get_db),
) -> ApiKey:
    """Resolve required API key record."""
    if not api_key_value or not api_key_value.strip():
        raise HTTPException(status_code=401, detail="Missing API key")

    api_key = _resolve_api_key_record(api_key_value, db)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def require_contributor_api_key(api_key: ApiKey = Depends(get_api_key_record)) -> ApiKey:
    """Enforce contributor privileges for submission write endpoints."""
    if not (api_key.can_write or api_key.is_moderator):
        raise HTTPException(status_code=403, detail="Contributor API key required")
    return api_key


def require_moderator_api_key(api_key: ApiKey = Depends(get_api_key_record)) -> ApiKey:
    """Enforce moderator privileges for moderation endpoints."""
    if not api_key.is_moderator:
        raise HTTPException(status_code=403, detail="Moderator API key required")
    return api_key


def get_optional_api_key_record(
    api_key_value: Annotated[str | None, Security(api_key_header)] = None,
    db: Session = Depends(get_db),
) -> ApiKey | None:
    """Resolve API key when provided; allow anonymous access when omitted."""
    return _resolve_api_key_record(api_key_value, db)
