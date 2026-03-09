"""Cost analytics endpoints backed by active user submissions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.analytics import AreaCostAnalyticsResponse, CityCostAnalyticsResponse
from app.schemas.common import ErrorResponse
from app.services.cost_analytics_service import area_cost_analytics, city_cost_analytics

router = APIRouter()


@router.get(
    "/cities/{city}",
    summary="City Crowd Cost Metrics",
    description="Return active crowd-sourced cost summary statistics for a city (including new live submissions).",
    response_model=CityCostAnalyticsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City not found in active cost dataset."},
        422: {"model": ErrorResponse, "description": "Invalid submission type filter."},
    },
)
def get_city_cost_analytics(
    city: str,
    submission_type: str | None = Query(default=None, description="Filter by submission type code, e.g. PINT."),
    db: Session = Depends(get_db),
) -> CityCostAnalyticsResponse:
    return city_cost_analytics(
        db,
        city=city,
        submission_type=submission_type,
    )


@router.get(
    "/cities/{city}/areas/{area}",
    summary="Area Crowd Cost Metrics",
    description="Return active crowd-sourced cost summary statistics for an area in a city (including new live submissions).",
    response_model=AreaCostAnalyticsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City or area not found in active cost dataset."},
        422: {"model": ErrorResponse, "description": "Invalid submission type filter."},
    },
)
def get_area_cost_analytics(
    city: str,
    area: str,
    submission_type: str | None = Query(default=None, description="Filter by submission type code, e.g. TAKEAWAY."),
    db: Session = Depends(get_db),
) -> AreaCostAnalyticsResponse:
    return area_cost_analytics(
        db,
        city=city,
        area=area,
        submission_type=submission_type,
    )
