#!/usr/bin/env python3
"""Create contributor/moderator API keys and store only key hashes."""

from __future__ import annotations

import argparse
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import ApiKey
from app.services.api_key_auth import hash_api_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an API key record.")
    parser.add_argument("--name", required=True, help="Unique API key name (e.g. contributor-local-1)")
    parser.add_argument(
        "--role",
        choices=["contributor", "moderator", "readonly"],
        default="contributor",
        help="Permission role (default: contributor)",
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=None,
        help="Optional expiry in whole days from now.",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Create key as inactive.",
    )
    parser.add_argument(
        "--raw-key",
        default=None,
        help="Optional explicit raw key. If omitted, a secure random key is generated.",
    )
    return parser.parse_args()


def role_permissions(role: str) -> tuple[bool, bool]:
    if role == "moderator":
        return True, True
    if role == "contributor":
        return True, False
    return False, False


def main() -> None:
    args = parse_args()

    if args.expires_days is not None and args.expires_days <= 0:
        raise ValueError("--expires-days must be a positive integer")

    raw_key = args.raw_key.strip() if args.raw_key else f"{args.role}_{secrets.token_urlsafe(24)}"
    if not raw_key:
        raise ValueError("Raw key must not be empty")

    can_write, is_moderator = role_permissions(args.role)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=args.expires_days) if args.expires_days else None

    db = SessionLocal()
    try:
        record = ApiKey(
            key_name=args.name,
            key_prefix=raw_key[:16],
            key_hash=hash_api_key(raw_key),
            can_write=can_write,
            is_moderator=is_moderator,
            is_active=not args.inactive,
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError(
            "Failed to create API key. Ensure --name is unique and raw key has not been used before."
        ) from exc
    finally:
        db.close()

    print("API key created")
    print("---------------")
    print(f"id: {record.id}")
    print(f"name: {record.key_name}")
    print(f"role: {args.role}")
    print(f"can_write: {record.can_write}")
    print(f"is_moderator: {record.is_moderator}")
    print(f"is_active: {record.is_active}")
    print(f"expires_at: {record.expires_at.isoformat() if record.expires_at else 'none'}")
    print("\nRaw key (save now; only hash is stored):")
    print(raw_key)


if __name__ == "__main__":
    main()
