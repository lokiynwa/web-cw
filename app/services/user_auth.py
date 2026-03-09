"""Account authentication helpers for password and bearer-token auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import UserAccount

JWT_ALGORITHM = "HS256"
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390000

bearer_token_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Bearer token for authenticated user endpoints.",
)


def normalize_email(email: str) -> str:
    """Normalize user email for lookups and uniqueness checks."""
    return email.strip().lower()


def hash_password(raw_password: str) -> str:
    """Hash a raw password using PBKDF2-HMAC-SHA256 with random salt."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        raw_password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt.hex()}${derived.hex()}"


def validate_password_rules(raw_password: str) -> list[str]:
    """Return password policy violations, or empty list when valid."""
    settings = get_settings()
    violations: list[str] = []

    if len(raw_password) < settings.auth_password_min_length:
        violations.append(f"password_must_be_at_least_{settings.auth_password_min_length}_characters")
    if not any(ch.isalpha() for ch in raw_password):
        violations.append("password_must_include_a_letter")
    if not any(ch.isdigit() for ch in raw_password):
        violations.append("password_must_include_a_number")

    return violations


def verify_password(raw_password: str, password_hash: str) -> bool:
    """Verify a raw password against stored PBKDF2 hash string."""
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = password_hash.split("$", maxsplit=3)
        if algorithm != PASSWORD_HASH_ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    computed = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(computed, expected)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def create_access_token(
    *,
    user_id: int,
    email: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    """Create signed JWT access token for a user identity."""
    settings = get_settings()
    ttl_minutes = settings.auth_jwt_exp_minutes if expires_minutes is None else expires_minutes
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ttl_minutes)

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": normalize_email(email),
        "role": role.strip().upper(),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(
        settings.auth_jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    encoded_signature = _b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def create_access_token_for_user(user: UserAccount) -> str:
    """Create access token using values from a persisted user."""
    return create_access_token(user_id=user.id, email=user.email, role=user.role)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token payload."""
    settings = get_settings()

    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", maxsplit=2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = hmac.new(
        settings.auth_jwt_secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    provided_signature = _b64url_decode(encoded_signature)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        header = json.loads(_b64url_decode(encoded_header).decode("utf-8"))
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    if header.get("alg") != JWT_ALGORITHM:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    exp_raw = payload.get("exp")
    if not isinstance(exp_raw, int):
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    if datetime.now(timezone.utc).timestamp() >= exp_raw:
        raise HTTPException(status_code=401, detail="Authentication token expired")

    return payload


def get_user_by_email(db: Session, email: str) -> UserAccount | None:
    """Fetch a user account by normalized email."""
    stmt = select(UserAccount).where(func.lower(UserAccount.email) == normalize_email(email))
    return db.execute(stmt).scalar_one_or_none()


def authenticate_user(db: Session, *, email: str, password: str) -> UserAccount | None:
    """Authenticate user with email/password and active account check."""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def resolve_user_from_token(db: Session, *, token: str) -> UserAccount:
    """Resolve active user account from bearer token."""
    payload = decode_access_token(token)
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user = db.execute(select(UserAccount).where(UserAccount.id == int(subject))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication user not found or inactive")

    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_token_scheme)] = None,
    db: Session = Depends(get_db),
) -> UserAccount:
    """FastAPI dependency that returns currently authenticated user."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return resolve_user_from_token(db, token=credentials.credentials)


def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_token_scheme)] = None,
    db: Session = Depends(get_db),
) -> UserAccount | None:
    """Resolve bearer user when present; return None when header omitted."""
    if credentials is None or not credentials.credentials:
        return None
    return resolve_user_from_token(db, token=credentials.credentials)


def require_moderator_user(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    """FastAPI dependency that enforces moderator role for account-auth routes."""
    if current_user.role.upper() != "MODERATOR":
        raise HTTPException(status_code=403, detail="Moderator role required")
    return current_user
