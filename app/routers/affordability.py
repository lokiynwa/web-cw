"""Affordability scoring endpoints with separate rent/pint/takeaway components."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.analytics import CityAffordabilityScoreResponse, CityAreaAffordabilityResponse
from app.schemas.common import ErrorResponse
from app.services.affordability_service import (
    _combine_component_scores,
    _resolve_requested_weights,
    _score_component,
    city_affordability_score,
    city_area_affordability,
)

router = APIRouter()


@router.get(
    "/cities/{city}/score",
    summary="City Affordability Score",
    description=(
        "Return a bounded 0-100 affordability score with transparent component breakdowns. "
        "Components are scored separately for rent, pint, and takeaway (no merged cost component)."
    ),
    response_model=CityAffordabilityScoreResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City not found or no data for selected components."},
        422: {"model": ErrorResponse, "description": "Invalid components or invalid weight values."},
    },
)
def get_city_affordability_score(
    city: str,
    components: str | None = Query(
        default=None,
        description="Comma-separated components: rent,pint,takeaway. Default: all.",
    ),
    rent_weight: float | None = Query(default=None, ge=0),
    pint_weight: float | None = Query(default=None, ge=0),
    takeaway_weight: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> CityAffordabilityScoreResponse:
    return city_affordability_score(
        db,
        city=city,
        components=components,
        rent_weight=rent_weight,
        pint_weight=pint_weight,
        takeaway_weight=takeaway_weight,
    )


@router.get(
    "/cities/{city}/areas",
    summary="City Area Affordability Table",
    description=(
        "Return per-area affordability scores and component breakdowns for a city. "
        "Users can request specific components (rent, pint, takeaway) or all components together."
    ),
    response_model=CityAreaAffordabilityResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City not found."},
        422: {"model": ErrorResponse, "description": "Invalid components or invalid weight values."},
    },
)
def get_city_area_affordability(
    city: str,
    components: str | None = Query(
        default=None,
        description="Comma-separated components: rent,pint,takeaway. Default: all.",
    ),
    rent_weight: float | None = Query(default=None, ge=0),
    pint_weight: float | None = Query(default=None, ge=0),
    takeaway_weight: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> CityAreaAffordabilityResponse:
    return city_area_affordability(
        db,
        city=city,
        components=components,
        rent_weight=rent_weight,
        pint_weight=pint_weight,
        takeaway_weight=takeaway_weight,
    )

