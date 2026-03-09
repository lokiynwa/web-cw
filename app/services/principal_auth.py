"""Combined auth principal dependencies for user-token and legacy API-key flows."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException

from app.models import ApiKey, UserAccount
from app.services.api_key_auth import get_optional_api_key_record
from app.services.user_auth import get_optional_current_user


@dataclass
class AuthPrincipal:
    """Authenticated actor context resolved from user token and/or API key."""

    user: UserAccount | None = None
    api_key: ApiKey | None = None

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user is not None else None

    @property
    def api_key_id(self) -> int | None:
        return self.api_key.id if self.api_key is not None else None

    @property
    def is_moderator(self) -> bool:
        user_is_moderator = self.user is not None and self.user.role.upper() == "MODERATOR"
        key_is_moderator = self.api_key is not None and self.api_key.is_moderator
        return bool(user_is_moderator or key_is_moderator)

    @property
    def can_write_submission(self) -> bool:
        if self.user is not None and self.user.is_active:
            return True
        if self.api_key is not None and (self.api_key.can_write or self.api_key.is_moderator):
            return True
        return False


def require_submission_writer_principal(
    current_user: UserAccount | None = Depends(get_optional_current_user),
    api_key: ApiKey | None = Depends(get_optional_api_key_record),
) -> AuthPrincipal:
    """Resolve authenticated actor for submission writes."""
    principal = AuthPrincipal(user=current_user, api_key=api_key)

    if principal.can_write_submission:
        return principal

    if current_user is None and api_key is None:
        raise HTTPException(status_code=401, detail="Missing authentication credentials")

    raise HTTPException(status_code=403, detail="Contributor access required")


def require_moderation_principal(
    current_user: UserAccount | None = Depends(get_optional_current_user),
    api_key: ApiKey | None = Depends(get_optional_api_key_record),
) -> AuthPrincipal:
    """Resolve moderator principal from user role or API key."""
    principal = AuthPrincipal(user=current_user, api_key=api_key)

    if principal.is_moderator:
        return principal

    if current_user is None and api_key is None:
        raise HTTPException(status_code=401, detail="Missing authentication credentials")

    raise HTTPException(status_code=403, detail="Moderator access required")
