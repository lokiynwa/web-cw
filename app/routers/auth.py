"""Account authentication endpoints for register/login/me flows."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import UserAccount
from app.schemas.auth import AuthLoginRequest, AuthRegisterRequest, AuthTokenResponse, AuthUserResponse
from app.schemas.common import ErrorResponse
from app.services.user_auth import (
    authenticate_user,
    create_access_token_for_user,
    get_current_user,
    get_user_by_email,
    hash_password,
    validate_password_rules,
)

router = APIRouter()


def _to_user_response(user: UserAccount) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    summary="Register User Account",
    description="Create a standard USER account for website login.",
    response_model=AuthUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Account created."},
        409: {"model": ErrorResponse, "description": "Email already registered."},
        422: {"model": ErrorResponse, "description": "Validation failed (including password rules)."},
    },
)
def register_account(
    payload: AuthRegisterRequest = Body(..., description="Registration payload."),
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_violations = validate_password_rules(payload.password)
    if password_violations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Password failed policy validation",
                "violations": password_violations,
            },
        )

    user = UserAccount(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
        role="USER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _to_user_response(user)


@router.post(
    "/login",
    summary="Login User Account",
    description="Authenticate a user account and return bearer access token.",
    response_model=AuthTokenResponse,
    responses={
        200: {"description": "Login successful."},
        401: {"model": ErrorResponse, "description": "Invalid email or password."},
    },
)
def login_account(
    payload: AuthLoginRequest = Body(..., description="Login credentials."),
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    user = authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    settings = get_settings()
    return AuthTokenResponse(
        access_token=create_access_token_for_user(user),
        token_type="bearer",
        expires_in_seconds=settings.auth_jwt_exp_minutes * 60,
    )


@router.get(
    "/me",
    summary="Current Authenticated User",
    description="Return the currently authenticated account from bearer token.",
    response_model=AuthUserResponse,
    responses={
        200: {"description": "Current user resolved."},
        401: {"model": ErrorResponse, "description": "Missing or invalid bearer token."},
    },
)
def get_me(current_user: UserAccount = Depends(get_current_user)) -> AuthUserResponse:
    return _to_user_response(current_user)
