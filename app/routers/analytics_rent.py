"""Rental analytics endpoints backed by cleaned listings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.analytics import (
    AreaRentAnalyticsResponse,
    CityAreaRentAnalyticsResponse,
    CityRentAnalyticsResponse,
)
from app.schemas.common import ErrorResponse
from app.services.rent_analytics_service import (
    area_rent_analytics,
    city_area_rent_analytics,
    city_rent_analytics,
)

router = APIRouter()


@router.get(
    "/cities/{city}",
    summary="City Rent Metrics",
    description="Return rental summary statistics for a city using valid cleaned listings.",
    response_model=CityRentAnalyticsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City not found in rental dataset."},
    },
)
def get_city_rent_analytics(
    city: str,
    bedrooms: int | None = Query(default=None, ge=1, description="Optional bedroom-count filter."),
    property_type: str | None = Query(default=None, description="Optional property type filter."),
    ensuite_proxy: bool | None = Query(default=None, description="Optional ensuite proxy filter."),
    db: Session = Depends(get_db),
) -> CityRentAnalyticsResponse:
    return city_rent_analytics(
        db,
        city=city,
        bedrooms=bedrooms,
        property_type=property_type,
        ensuite_proxy=ensuite_proxy,
    )


@router.get(
    "/cities/{city}/areas/{area}",
    summary="Area Rent Metrics",
    description="Return rental summary statistics for a specific area in a city.",
    response_model=AreaRentAnalyticsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City or area not found in rental dataset."},
    },
)
def get_area_rent_analytics(
    city: str,
    area: str,
    bedrooms: int | None = Query(default=None, ge=1, description="Optional bedroom-count filter."),
    property_type: str | None = Query(default=None, description="Optional property type filter."),
    ensuite_proxy: bool | None = Query(default=None, description="Optional ensuite proxy filter."),
    db: Session = Depends(get_db),
) -> AreaRentAnalyticsResponse:
    return area_rent_analytics(
        db,
        city=city,
        area=area,
        bedrooms=bedrooms,
        property_type=property_type,
        ensuite_proxy=ensuite_proxy,
    )


@router.get(
    "/cities/{city}/areas",
    summary="City Area Rent Table",
    description="Return per-area rental summary statistics for a city.",
    response_model=CityAreaRentAnalyticsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "City not found in rental dataset."},
    },
)
def list_city_area_rent_analytics(
    city: str,
    bedrooms: int | None = Query(default=None, ge=1, description="Optional bedroom-count filter."),
    property_type: str | None = Query(default=None, description="Optional property type filter."),
    ensuite_proxy: bool | None = Query(default=None, description="Optional ensuite proxy filter."),
    db: Session = Depends(get_db),
) -> CityAreaRentAnalyticsResponse:
    return city_area_rent_analytics(
        db,
        city=city,
        bedrooms=bedrooms,
        property_type=property_type,
        ensuite_proxy=ensuite_proxy,
    )
