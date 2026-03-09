"""Reusable business logic for active crowd-cost analytics."""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import CostSubmissionType, ModerationStatus, UserCostSubmission


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _base_active_stmt() -> Select:
    return (
        select(UserCostSubmission)
        .join(UserCostSubmission.moderation_status)
        .where(
            UserCostSubmission.is_analytics_eligible.is_(True),
            UserCostSubmission.price_gbp.is_not(None),
            UserCostSubmission.city.is_not(None),
            func.lower(ModerationStatus.code) == "active",
        )
    )


def _city_exists(db: Session, city: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(UserCostSubmission)
        .join(UserCostSubmission.moderation_status)
        .where(
            UserCostSubmission.is_analytics_eligible.is_(True),
            func.lower(ModerationStatus.code) == "active",
            func.lower(UserCostSubmission.city) == _normalize_text(city),
        )
    )
    return db.execute(stmt).scalar_one() > 0


def _area_exists(db: Session, city: str, area: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(UserCostSubmission)
        .join(UserCostSubmission.moderation_status)
        .where(
            UserCostSubmission.is_analytics_eligible.is_(True),
            func.lower(ModerationStatus.code) == "active",
            func.lower(UserCostSubmission.city) == _normalize_text(city),
            func.lower(func.coalesce(UserCostSubmission.area, "")) == _normalize_text(area),
        )
    )
    return db.execute(stmt).scalar_one() > 0


def _validate_submission_type_filter(db: Session, submission_type: str | None) -> str | None:
    if submission_type is None:
        return None

    type_code = submission_type.strip().upper()
    stmt = select(CostSubmissionType).where(func.lower(CostSubmissionType.code) == type_code.lower())
    match = db.execute(stmt).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=422, detail="Invalid submission_type filter")
    return type_code


def _apply_submission_type_filter(stmt: Select, submission_type: str | None) -> Select:
    if submission_type is None:
        return stmt
    return stmt.join(UserCostSubmission.submission_type).where(func.lower(CostSubmissionType.code) == submission_type.lower())


def _compute_metrics(values: list[Decimal]) -> dict[str, float | int | None]:
    sample_size = len(values)
    if sample_size == 0:
        return {
            "average": None,
            "median": None,
            "min": None,
            "max": None,
            "sample_size": 0,
        }

    sorted_values = sorted(values)
    avg = sum(sorted_values) / Decimal(sample_size)
    med = median(sorted_values)

    return {
        "average": float(round(avg, 2)),
        "median": float(round(Decimal(med), 2)),
        "min": float(round(sorted_values[0], 2)),
        "max": float(round(sorted_values[-1], 2)),
        "sample_size": sample_size,
    }


def city_cost_analytics(
    db: Session,
    *,
    city: str,
    submission_type: str | None,
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")

    submission_type_code = _validate_submission_type_filter(db, submission_type)

    stmt = _base_active_stmt().where(func.lower(UserCostSubmission.city) == _normalize_text(city))
    stmt = _apply_submission_type_filter(stmt, submission_type_code)

    values = [row.price_gbp for row in db.execute(stmt).scalars().all() if row.price_gbp is not None]

    return {
        "city": city,
        "filters": {"submission_type": submission_type_code},
        "metrics": _compute_metrics(values),
    }


def area_cost_analytics(
    db: Session,
    *,
    city: str,
    area: str,
    submission_type: str | None,
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")
    if not _area_exists(db, city, area):
        raise HTTPException(status_code=404, detail="Area not found")

    submission_type_code = _validate_submission_type_filter(db, submission_type)

    stmt = _base_active_stmt().where(
        func.lower(UserCostSubmission.city) == _normalize_text(city),
        func.lower(func.coalesce(UserCostSubmission.area, "")) == _normalize_text(area),
    )
    stmt = _apply_submission_type_filter(stmt, submission_type_code)

    values = [row.price_gbp for row in db.execute(stmt).scalars().all() if row.price_gbp is not None]

    return {
        "city": city,
        "area": area,
        "filters": {"submission_type": submission_type_code},
        "metrics": _compute_metrics(values),
    }
