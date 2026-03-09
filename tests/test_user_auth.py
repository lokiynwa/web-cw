"""Unit tests for account-auth password and bearer-token helpers."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models import UserAccount
from app.services.user_auth import (
    authenticate_user,
    create_access_token_for_user,
    decode_access_token,
    hash_password,
    require_moderator_user,
    resolve_user_from_token,
    verify_password,
)


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    try:
        yield testing_session_local
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _create_user(
    session_factory: sessionmaker,
    *,
    email: str,
    password: str,
    role: str = "USER",
    is_active: bool = True,
) -> UserAccount:
    with session_factory() as db:
        user = UserAccount(
            email=email,
            hashed_password=hash_password(password),
            display_name="Test User",
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def test_hash_password_roundtrip() -> None:
    password_hash = hash_password("Sup3rSecurePass!")

    assert password_hash != "Sup3rSecurePass!"
    assert verify_password("Sup3rSecurePass!", password_hash) is True
    assert verify_password("WrongPass", password_hash) is False


def test_token_roundtrip_contains_expected_claims(session_factory: sessionmaker) -> None:
    user = _create_user(
        session_factory,
        email="alice@example.com",
        password="Sup3rSecurePass!",
        role="MODERATOR",
    )
    token = create_access_token_for_user(user)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user.id)
    assert payload["email"] == "alice@example.com"
    assert payload["role"] == "MODERATOR"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)


def test_resolve_user_from_token_rejects_inactive_user(session_factory: sessionmaker) -> None:
    user = _create_user(
        session_factory,
        email="inactive@example.com",
        password="Sup3rSecurePass!",
        is_active=False,
    )
    token = create_access_token_for_user(user)

    with session_factory() as db:
        with pytest.raises(HTTPException) as exc_info:
            resolve_user_from_token(db, token=token)
        assert exc_info.value.status_code == 401


def test_authenticate_user_checks_password_and_active_flag(session_factory: sessionmaker) -> None:
    _create_user(session_factory, email="bob@example.com", password="Sup3rSecurePass!")

    with session_factory() as db:
        ok = authenticate_user(db, email="bob@example.com", password="Sup3rSecurePass!")
        wrong_password = authenticate_user(db, email="bob@example.com", password="wrong")
        missing_user = authenticate_user(db, email="missing@example.com", password="Sup3rSecurePass!")

    assert ok is not None
    assert ok.email == "bob@example.com"
    assert wrong_password is None
    assert missing_user is None


def test_require_moderator_user_enforces_role(session_factory: sessionmaker) -> None:
    user = _create_user(session_factory, email="user@example.com", password="Sup3rSecurePass!", role="USER")
    moderator = _create_user(
        session_factory,
        email="mod@example.com",
        password="Sup3rSecurePass!",
        role="MODERATOR",
    )

    with pytest.raises(HTTPException) as exc_info:
        require_moderator_user(user)
    assert exc_info.value.status_code == 403

    assert require_moderator_user(moderator).role == "MODERATOR"
