"""Server-side protection rules for crowd cost submissions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import CostSubmissionType, UserCostSubmission

DUPLICATE_WINDOW_HOURS = 24
DUPLICATE_AMOUNT_TOLERANCE = Decimal("0.20")


@dataclass
class PlausibilityResult:
    """Outcome of domain-specific plausibility checks."""

    hard_valid: bool
    suspicious: bool
    suspicious_reasons: list[str]
    hard_fail_reasons: list[str]


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def build_duplicate_fingerprint(
    *,
    contributor_user_id: int | None,
    contributor_api_key_id: int | None,
    city: str,
    area: str | None,
    submission_type_code: str,
    amount_gbp: Decimal,
) -> str:
    """Create deterministic duplicate fingerprint for submission protection."""
    if contributor_user_id is not None:
        contributor_token = f"user:{contributor_user_id}"
    elif contributor_api_key_id is not None:
        contributor_token = f"api_key:{contributor_api_key_id}"
    else:
        contributor_token = "anonymous"
    amount_bucket = amount_gbp.quantize(Decimal("0.10"), rounding=ROUND_HALF_UP)
    payload = "|".join(
        [
            contributor_token,
            _normalize_text(city),
            _normalize_text(area),
            submission_type_code.strip().upper(),
            f"{amount_bucket:.2f}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_plausibility_checks(submission_type_code: str, amount_gbp: Decimal) -> PlausibilityResult:
    """Apply domain-specific checks for PINT and TAKEAWAY values."""
    code = submission_type_code.strip().upper()
    suspicious_reasons: list[str] = []
    hard_fail_reasons: list[str] = []

    if code == "PINT":
        if amount_gbp < Decimal("0.50") or amount_gbp > Decimal("25.00"):
            hard_fail_reasons.append("pint_amount_outside_hard_bounds")
        elif amount_gbp < Decimal("2.00") or amount_gbp > Decimal("10.00"):
            suspicious_reasons.append("pint_amount_outside_typical_range")

    elif code == "TAKEAWAY":
        if amount_gbp < Decimal("1.00") or amount_gbp > Decimal("80.00"):
            hard_fail_reasons.append("takeaway_amount_outside_hard_bounds")
        elif amount_gbp < Decimal("3.00") or amount_gbp > Decimal("35.00"):
            suspicious_reasons.append("takeaway_amount_outside_typical_range")

    else:
        # Fallback: unknown types are already rejected upstream, but keep safe behavior here.
        if amount_gbp < Decimal("0.50") or amount_gbp > Decimal("500.00"):
            suspicious_reasons.append("amount_outside_generic_range")

    return PlausibilityResult(
        hard_valid=not hard_fail_reasons,
        suspicious=bool(suspicious_reasons),
        suspicious_reasons=sorted(set(suspicious_reasons)),
        hard_fail_reasons=sorted(set(hard_fail_reasons)),
    )


def find_recent_soft_duplicate(
    db: Session,
    *,
    contributor_user_id: int | None,
    contributor_api_key_id: int | None,
    city: str,
    area: str | None,
    submission_type_id: int,
    amount_gbp: Decimal,
    exclude_submission_id: int | None = None,
) -> UserCostSubmission | None:
    """Find recent near-duplicate for same contributor/location/type/amount.

    Duplicate checks require contributor identity via user account or API key.
    """
    if contributor_user_id is None and contributor_api_key_id is None:
        return None

    recent_threshold = datetime.now(timezone.utc) - timedelta(hours=DUPLICATE_WINDOW_HOURS)
    amount_low = amount_gbp - DUPLICATE_AMOUNT_TOLERANCE
    amount_high = amount_gbp + DUPLICATE_AMOUNT_TOLERANCE

    contributor_clause = (
        UserCostSubmission.created_by_user_id == contributor_user_id
        if contributor_user_id is not None
        else UserCostSubmission.submitted_via_api_key_id == contributor_api_key_id
    )

    stmt: Select = (
        select(UserCostSubmission)
        .where(
            contributor_clause,
            func.lower(UserCostSubmission.city) == _normalize_text(city),
            func.lower(func.coalesce(UserCostSubmission.area, "")) == _normalize_text(area),
            UserCostSubmission.submission_type_id == submission_type_id,
            UserCostSubmission.submitted_at >= recent_threshold,
            UserCostSubmission.price_gbp >= amount_low,
            UserCostSubmission.price_gbp <= amount_high,
        )
        .order_by(UserCostSubmission.submitted_at.desc(), UserCostSubmission.id.desc())
    )

    if exclude_submission_id is not None:
        stmt = stmt.where(UserCostSubmission.id != exclude_submission_id)

    return db.execute(stmt).scalars().first()


def flag_duplicate_reason(existing_submission: UserCostSubmission) -> list[str]:
    """Return standardized suspicious reasons for duplicate findings."""
    return [f"possible_duplicate_of_submission_{existing_submission.id}"]
