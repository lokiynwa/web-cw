"""Reusable business logic for affordability scoring."""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CleanedListing, CostSubmissionType, ModerationStatus, UserCostSubmission

settings = get_settings()
ALLOWED_COMPONENTS = {"rent", "pint", "takeaway"}


def _normalize(value: str) -> str:
    return value.strip().lower()


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


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


def _parse_components(components: str | None) -> list[str]:
    if components is None or not components.strip():
        return ["rent", "pint", "takeaway"]

    parsed = [token.strip().lower() for token in components.split(",") if token.strip()]
    deduped: list[str] = []
    for comp in parsed:
        if comp not in deduped:
            deduped.append(comp)

    invalid = [comp for comp in deduped if comp not in ALLOWED_COMPONENTS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid components: {', '.join(invalid)}. Allowed: rent,pint,takeaway",
        )
    if not deduped:
        raise HTTPException(status_code=422, detail="At least one component is required")

    return deduped


def _score_component(value: float | None, floor: float, ceiling: float) -> float | None:
    if value is None or ceiling <= floor:
        return None
    normalized = 100.0 * (ceiling - value) / (ceiling - floor)
    return round(_clamp(normalized), 2)


def _resolve_requested_weights(
    *,
    rent_weight: float | None,
    pint_weight: float | None,
    takeaway_weight: float | None,
) -> dict[str, float]:
    weights = {
        "rent": settings.affordability_rent_weight if rent_weight is None else rent_weight,
        "pint": settings.affordability_pint_weight if pint_weight is None else pint_weight,
        "takeaway": settings.affordability_takeaway_weight if takeaway_weight is None else takeaway_weight,
    }

    if any(value < 0 for value in weights.values()):
        raise HTTPException(status_code=422, detail="Weights must be non-negative")
    return weights


def _combine_component_scores(
    *,
    selected_components: list[str],
    requested_weights: dict[str, float],
    component_scores: dict[str, float | None],
) -> tuple[float | None, dict[str, float]]:
    effective = {
        comp: requested_weights[comp] if component_scores.get(comp) is not None else 0.0
        for comp in selected_components
    }
    total = sum(effective.values())

    if total <= 0:
        return None, {comp: 0.0 for comp in selected_components}

    normalized = {comp: round(effective[comp] / total, 4) for comp in selected_components}
    combined = sum((component_scores.get(comp) or 0.0) * normalized[comp] for comp in selected_components)
    return round(_clamp(combined), 2), normalized


def _band(score: float) -> str:
    if score >= 75:
        return "High Affordability"
    if score >= 50:
        return "Moderate Affordability"
    if score >= 25:
        return "Low Affordability"
    return "Very Low Affordability"


def _city_exists(db: Session, city: str) -> bool:
    city_norm = _normalize(city)

    rent_exists = db.execute(
        select(func.count())
        .select_from(CleanedListing)
        .where(
            CleanedListing.is_excluded.is_(False),
            CleanedListing.valid_price.is_(True),
            func.lower(CleanedListing.city) == city_norm,
        )
    ).scalar_one()

    if rent_exists > 0:
        return True

    costs_exist = db.execute(
        select(func.count())
        .select_from(UserCostSubmission)
        .join(UserCostSubmission.moderation_status)
        .where(
            UserCostSubmission.is_analytics_eligible.is_(True),
            func.lower(ModerationStatus.code) == "active",
            func.lower(UserCostSubmission.city) == city_norm,
        )
    ).scalar_one()

    return costs_exist > 0


def _city_rent_metrics(db: Session, city: str) -> dict[str, float | int | None]:
    stmt: Select = select(CleanedListing).where(
        CleanedListing.is_excluded.is_(False),
        CleanedListing.valid_price.is_(True),
        CleanedListing.price_gbp_weekly.is_not(None),
        func.lower(CleanedListing.city) == _normalize(city),
    )
    values = [row.price_gbp_weekly for row in db.execute(stmt).scalars().all() if row.price_gbp_weekly is not None]
    return _compute_metrics(values)


def _city_cost_type_metrics(db: Session, city: str, submission_type_code: str) -> dict[str, float | int | None]:
    stmt: Select = (
        select(UserCostSubmission)
        .join(UserCostSubmission.moderation_status)
        .join(UserCostSubmission.submission_type)
        .where(
            UserCostSubmission.is_analytics_eligible.is_(True),
            func.lower(ModerationStatus.code) == "active",
            func.lower(UserCostSubmission.city) == _normalize(city),
            func.lower(CostSubmissionType.code) == submission_type_code.lower(),
        )
    )
    values = [row.price_gbp for row in db.execute(stmt).scalars().all() if row.price_gbp is not None]
    return _compute_metrics(values)


def _area_rent_metrics(db: Session, city: str) -> dict[str, dict[str, float | int | None]]:
    stmt: Select = select(CleanedListing).where(
        CleanedListing.is_excluded.is_(False),
        CleanedListing.valid_price.is_(True),
        CleanedListing.price_gbp_weekly.is_not(None),
        CleanedListing.area.is_not(None),
        func.lower(CleanedListing.city) == _normalize(city),
    )
    rows = db.execute(stmt).scalars().all()

    grouped: dict[str, list[Decimal]] = {}
    for row in rows:
        if row.area is None or row.price_gbp_weekly is None:
            continue
        grouped.setdefault(row.area, []).append(row.price_gbp_weekly)

    return {area: _compute_metrics(values) for area, values in grouped.items()}


def _area_cost_type_metrics(
    db: Session, city: str, submission_type_code: str
) -> dict[str, dict[str, float | int | None]]:
    stmt: Select = (
        select(UserCostSubmission)
        .join(UserCostSubmission.moderation_status)
        .join(UserCostSubmission.submission_type)
        .where(
            UserCostSubmission.is_analytics_eligible.is_(True),
            func.lower(ModerationStatus.code) == "active",
            UserCostSubmission.area.is_not(None),
            func.lower(UserCostSubmission.city) == _normalize(city),
            func.lower(CostSubmissionType.code) == submission_type_code.lower(),
        )
    )
    rows = db.execute(stmt).scalars().all()

    grouped: dict[str, list[Decimal]] = {}
    for row in rows:
        if row.area is None or row.price_gbp is None:
            continue
        grouped.setdefault(row.area, []).append(row.price_gbp)

    return {area: _compute_metrics(values) for area, values in grouped.items()}


def city_affordability_score(
    db: Session,
    *,
    city: str,
    components: str | None,
    rent_weight: float | None,
    pint_weight: float | None,
    takeaway_weight: float | None,
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")

    selected = _parse_components(components)
    requested_weights = _resolve_requested_weights(
        rent_weight=rent_weight,
        pint_weight=pint_weight,
        takeaway_weight=takeaway_weight,
    )

    component_payload: dict[str, dict] = {}
    component_scores: dict[str, float | None] = {}

    if "rent" in selected:
        rent_metrics = _city_rent_metrics(db, city)
        rent_score = _score_component(
            rent_metrics["average"],
            settings.affordability_rent_floor_gbp_weekly,
            settings.affordability_rent_ceiling_gbp_weekly,
        )
        component_scores["rent"] = rent_score
        component_payload["rent"] = {
            "metrics": rent_metrics,
            "component_score": rent_score,
            "normalization_bounds": {
                "floor": settings.affordability_rent_floor_gbp_weekly,
                "ceiling": settings.affordability_rent_ceiling_gbp_weekly,
            },
        }

    if "pint" in selected:
        pint_metrics = _city_cost_type_metrics(db, city, "PINT")
        pint_score = _score_component(
            pint_metrics["average"],
            settings.affordability_pint_floor_gbp,
            settings.affordability_pint_ceiling_gbp,
        )
        component_scores["pint"] = pint_score
        component_payload["pint"] = {
            "submission_type": "PINT",
            "metrics": pint_metrics,
            "component_score": pint_score,
            "normalization_bounds": {
                "floor": settings.affordability_pint_floor_gbp,
                "ceiling": settings.affordability_pint_ceiling_gbp,
            },
        }

    if "takeaway" in selected:
        takeaway_metrics = _city_cost_type_metrics(db, city, "TAKEAWAY")
        takeaway_score = _score_component(
            takeaway_metrics["average"],
            settings.affordability_takeaway_floor_gbp,
            settings.affordability_takeaway_ceiling_gbp,
        )
        component_scores["takeaway"] = takeaway_score
        component_payload["takeaway"] = {
            "submission_type": "TAKEAWAY",
            "metrics": takeaway_metrics,
            "component_score": takeaway_score,
            "normalization_bounds": {
                "floor": settings.affordability_takeaway_floor_gbp,
                "ceiling": settings.affordability_takeaway_ceiling_gbp,
            },
        }

    score, effective_weights = _combine_component_scores(
        selected_components=selected,
        requested_weights=requested_weights,
        component_scores=component_scores,
    )

    if score is None:
        raise HTTPException(status_code=404, detail="No affordability inputs available for selected components")

    return {
        "city": city,
        "selected_components": selected,
        "score": score,
        "score_band": _band(score),
        "components": component_payload,
        "weights": {
            "requested": {comp: requested_weights[comp] for comp in selected},
            "effective": effective_weights,
        },
        "formula": {
            "description": "No merged overall cost component. Pint and takeaway are scored separately.",
            "overall": "score = weighted_average(selected_component_scores)",
            "component": "component_score = clamp(100 * (ceiling - average_cost) / (ceiling - floor), 0, 100)",
        },
    }


def city_area_affordability(
    db: Session,
    *,
    city: str,
    components: str | None,
    rent_weight: float | None,
    pint_weight: float | None,
    takeaway_weight: float | None,
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")

    selected = _parse_components(components)
    requested_weights = _resolve_requested_weights(
        rent_weight=rent_weight,
        pint_weight=pint_weight,
        takeaway_weight=takeaway_weight,
    )

    rent_by_area = _area_rent_metrics(db, city) if "rent" in selected else {}
    pint_by_area = _area_cost_type_metrics(db, city, "PINT") if "pint" in selected else {}
    takeaway_by_area = _area_cost_type_metrics(db, city, "TAKEAWAY") if "takeaway" in selected else {}

    all_areas = sorted(
        set(rent_by_area.keys()) | set(pint_by_area.keys()) | set(takeaway_by_area.keys()),
        key=str.lower,
    )
    area_rows: list[dict] = []

    for area in all_areas:
        component_scores: dict[str, float | None] = {}
        component_payload: dict[str, dict] = {}

        if "rent" in selected:
            rent_metrics = rent_by_area.get(area, _compute_metrics([]))
            rent_score = _score_component(
                rent_metrics["average"],
                settings.affordability_rent_floor_gbp_weekly,
                settings.affordability_rent_ceiling_gbp_weekly,
            )
            component_scores["rent"] = rent_score
            component_payload["rent"] = {"metrics": rent_metrics, "component_score": rent_score}

        if "pint" in selected:
            pint_metrics = pint_by_area.get(area, _compute_metrics([]))
            pint_score = _score_component(
                pint_metrics["average"],
                settings.affordability_pint_floor_gbp,
                settings.affordability_pint_ceiling_gbp,
            )
            component_scores["pint"] = pint_score
            component_payload["pint"] = {
                "submission_type": "PINT",
                "metrics": pint_metrics,
                "component_score": pint_score,
            }

        if "takeaway" in selected:
            takeaway_metrics = takeaway_by_area.get(area, _compute_metrics([]))
            takeaway_score = _score_component(
                takeaway_metrics["average"],
                settings.affordability_takeaway_floor_gbp,
                settings.affordability_takeaway_ceiling_gbp,
            )
            component_scores["takeaway"] = takeaway_score
            component_payload["takeaway"] = {
                "submission_type": "TAKEAWAY",
                "metrics": takeaway_metrics,
                "component_score": takeaway_score,
            }

        score, effective_weights = _combine_component_scores(
            selected_components=selected,
            requested_weights=requested_weights,
            component_scores=component_scores,
        )
        if score is None:
            continue

        area_rows.append(
            {
                "area": area,
                "score": score,
                "score_band": _band(score),
                "components": component_payload,
                "weights": {
                    "requested": {comp: requested_weights[comp] for comp in selected},
                    "effective": effective_weights,
                },
            }
        )

    return {
        "city": city,
        "selected_components": selected,
        "formula": {
            "description": "No merged overall cost component. Pint and takeaway are scored separately.",
            "overall": "score = weighted_average(selected_component_scores)",
            "component": "component_score = clamp(100 * (ceiling - average_cost) / (ceiling - floor), 0, 100)",
        },
        "areas": area_rows,
        "total": len(area_rows),
    }
