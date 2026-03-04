"""Rental analytics endpoints backed by cleaned listings."""

from __future__ import annotations

from decimal import Decimal
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CleanedListing

router = APIRouter()


def _normalize_location(value: str) -> str:
    return value.strip().lower()


def _base_valid_stmt() -> Select:
    return select(CleanedListing).where(
        CleanedListing.is_excluded.is_(False),
        CleanedListing.valid_price.is_(True),
        CleanedListing.price_gbp_weekly.is_not(None),
        CleanedListing.city.is_not(None),
    )


def _apply_filters(
    stmt: Select,
    *,
    bedrooms: int | None,
    property_type: str | None,
    ensuite_proxy: bool | None,
) -> Select:
    if bedrooms is not None:
        stmt = stmt.where(CleanedListing.bedrooms == bedrooms)
    if property_type is not None:
        stmt = stmt.where(func.lower(CleanedListing.listing_type) == property_type.strip().lower())
    if ensuite_proxy is not None:
        stmt = stmt.where(CleanedListing.is_ensuite_proxy.is_(ensuite_proxy))
    return stmt


def _city_exists(db: Session, city: str) -> bool:
    city_norm = _normalize_location(city)
    stmt = (
        select(func.count())
        .select_from(CleanedListing)
        .where(
            CleanedListing.is_excluded.is_(False),
            CleanedListing.city.is_not(None),
            func.lower(CleanedListing.city) == city_norm,
        )
    )
    return db.execute(stmt).scalar_one() > 0


def _area_exists(db: Session, city: str, area: str) -> bool:
    city_norm = _normalize_location(city)
    area_norm = _normalize_location(area)
    stmt = (
        select(func.count())
        .select_from(CleanedListing)
        .where(
            CleanedListing.is_excluded.is_(False),
            CleanedListing.city.is_not(None),
            CleanedListing.area.is_not(None),
            func.lower(CleanedListing.city) == city_norm,
            func.lower(CleanedListing.area) == area_norm,
        )
    )
    return db.execute(stmt).scalar_one() > 0


def _compute_metrics(prices: list[Decimal]) -> dict[str, float | int | None]:
    sample_size = len(prices)
    if sample_size == 0:
        return {
            "average": None,
            "median": None,
            "min": None,
            "max": None,
            "sample_size": 0,
        }

    sorted_prices = sorted(prices)
    avg = sum(prices) / Decimal(sample_size)
    med = median(sorted_prices)

    return {
        "average": float(round(avg, 2)),
        "median": float(round(Decimal(med), 2)),
        "min": float(round(sorted_prices[0], 2)),
        "max": float(round(sorted_prices[-1], 2)),
        "sample_size": sample_size,
    }


@router.get("/cities/{city}")
def get_city_rent_analytics(
    city: str,
    bedrooms: int | None = Query(default=None, ge=1),
    property_type: str | None = Query(default=None),
    ensuite_proxy: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")

    stmt = _base_valid_stmt().where(func.lower(CleanedListing.city) == _normalize_location(city))
    stmt = _apply_filters(stmt, bedrooms=bedrooms, property_type=property_type, ensuite_proxy=ensuite_proxy)

    prices = [row.price_gbp_weekly for row in db.execute(stmt).scalars().all() if row.price_gbp_weekly is not None]

    return {
        "city": city,
        "filters": {
            "bedrooms": bedrooms,
            "property_type": property_type,
            "ensuite_proxy": ensuite_proxy,
        },
        "metrics": _compute_metrics(prices),
    }


@router.get("/cities/{city}/areas/{area}")
def get_area_rent_analytics(
    city: str,
    area: str,
    bedrooms: int | None = Query(default=None, ge=1),
    property_type: str | None = Query(default=None),
    ensuite_proxy: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")
    if not _area_exists(db, city, area):
        raise HTTPException(status_code=404, detail="Area not found")

    stmt = _base_valid_stmt().where(
        func.lower(CleanedListing.city) == _normalize_location(city),
        func.lower(CleanedListing.area) == _normalize_location(area),
    )
    stmt = _apply_filters(stmt, bedrooms=bedrooms, property_type=property_type, ensuite_proxy=ensuite_proxy)

    prices = [row.price_gbp_weekly for row in db.execute(stmt).scalars().all() if row.price_gbp_weekly is not None]

    return {
        "city": city,
        "area": area,
        "filters": {
            "bedrooms": bedrooms,
            "property_type": property_type,
            "ensuite_proxy": ensuite_proxy,
        },
        "metrics": _compute_metrics(prices),
    }


@router.get("/cities/{city}/areas")
def list_city_area_rent_analytics(
    city: str,
    bedrooms: int | None = Query(default=None, ge=1),
    property_type: str | None = Query(default=None),
    ensuite_proxy: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not _city_exists(db, city):
        raise HTTPException(status_code=404, detail="City not found")

    stmt = _base_valid_stmt().where(
        func.lower(CleanedListing.city) == _normalize_location(city),
        CleanedListing.area.is_not(None),
    )
    stmt = _apply_filters(stmt, bedrooms=bedrooms, property_type=property_type, ensuite_proxy=ensuite_proxy)

    rows = db.execute(stmt).scalars().all()

    prices_by_area: dict[str, list[Decimal]] = {}
    for row in rows:
        if row.area is None or row.price_gbp_weekly is None:
            continue
        prices_by_area.setdefault(row.area, []).append(row.price_gbp_weekly)

    areas_payload = [
        {
            "area": area_name,
            **_compute_metrics(prices),
        }
        for area_name, prices in sorted(prices_by_area.items(), key=lambda pair: pair[0].lower())
    ]

    return {
        "city": city,
        "filters": {
            "bedrooms": bedrooms,
            "property_type": property_type,
            "ensuite_proxy": ensuite_proxy,
        },
        "areas": areas_payload,
    }
