"""API key authentication helpers for protected endpoints."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiKey


def hash_api_key(raw_key: str) -> str:
    """Hash API key input using SHA-256 hex digest."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get_api_key_record(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Session = Depends(get_db),
) -> ApiKey:
    """Resolve an active API key record from the incoming header."""
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(status_code=401, detail="Missing API key")

    raw_key = x_api_key.strip()
    hashed_key = hash_api_key(raw_key)
    now = datetime.now(timezone.utc)

    stmt = select(ApiKey).where(
        and_(
            ApiKey.is_active.is_(True),
            ApiKey.revoked_at.is_(None),
            or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now),
            or_(func.lower(ApiKey.key_hash) == hashed_key.lower(), func.lower(ApiKey.key_hash) == raw_key.lower()),
        )
    )
    api_key = db.execute(stmt).scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key.last_used_at = now
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return api_key


def require_moderator_api_key(api_key: ApiKey = Depends(get_api_key_record)) -> ApiKey:
    """Enforce moderator privileges for moderation endpoints."""
    if not api_key.is_moderator:
        raise HTTPException(status_code=403, detail="Moderator API key required")
    return api_key


def get_optional_api_key_record(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Session = Depends(get_db),
) -> ApiKey | None:
    """Resolve API key when provided; allow anonymous access when omitted."""
    if not x_api_key or not x_api_key.strip():
        return None
    return get_api_key_record(x_api_key=x_api_key, db=db)
