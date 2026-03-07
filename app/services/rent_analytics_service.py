"""Reusable business logic for rental analytics."""

from __future__ import annotations

from decimal import Decimal
from statistics import median
import re

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import CleanedListing

CITY_NOISE_PATTERN = re.compile(r"\b(road|rd|street|st|avenue|ave|lane|ln|close|court|drive|dr|terrace|way)\b", re.I)
NON_CITY_TOKENS = {"yorkshire", "leicestershire"}


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


def _display_city_name(norm: str, variants: dict[str, int]) -> str:
    ranked_variants = sorted(variants.items(), key=lambda pair: (-pair[1], pair[0].lower()))
    chosen = ranked_variants[0][0]
    if chosen.islower() or chosen.isupper():
        return " ".join(part.capitalize() for part in norm.split())
    return chosen


def _is_city_name_noise(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in NON_CITY_TOKENS:
        return True
    if CITY_NOISE_PATTERN.search(lowered):
        return True
    return False


def list_rent_cities(db: Session, *, min_sample_size: int = 1) -> dict:
    stmt = (
        select(CleanedListing.city, func.count(CleanedListing.id))
        .where(
            CleanedListing.is_excluded.is_(False),
            CleanedListing.valid_price.is_(True),
            CleanedListing.price_gbp_weekly.is_not(None),
            CleanedListing.city.is_not(None),
        )
        .group_by(CleanedListing.city)
        .order_by(func.lower(CleanedListing.city))
    )

    rows = db.execute(stmt).all()

    grouped: dict[str, dict] = {}
    for city, sample_size in rows:
        if city is None:
            continue
        city_clean = city.strip()
        if not city_clean:
            continue

        norm = city_clean.lower()
        entry = grouped.setdefault(norm, {"sample_size": 0, "variants": {}})
        entry["sample_size"] += int(sample_size)
        variants: dict[str, int] = entry["variants"]
        variants[city_clean] = variants.get(city_clean, 0) + int(sample_size)

    cities = []
    for norm, entry in grouped.items():
        sample_size = entry["sample_size"]
        if sample_size < min_sample_size:
            continue
        display_name = _display_city_name(norm, entry["variants"])
        if _is_city_name_noise(display_name):
            continue
        cities.append({"name": display_name, "sample_size": sample_size})

    cities.sort(key=lambda item: item["name"].lower())
    return {"cities": cities, "total": len(cities)}


def city_rent_analytics(
    db: Session,
    *,
    city: str,
    bedrooms: int | None,
    property_type: str | None,
    ensuite_proxy: bool | None,
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


def area_rent_analytics(
    db: Session,
    *,
    city: str,
    area: str,
    bedrooms: int | None,
    property_type: str | None,
    ensuite_proxy: bool | None,
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


def city_area_rent_analytics(
    db: Session,
    *,
    city: str,
    bedrooms: int | None,
    property_type: str | None,
    ensuite_proxy: bool | None,
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


def rank_city_areas_by_rent(
    db: Session,
    *,
    city: str,
    bedrooms: int | None,
    property_type: str | None,
    ensuite_proxy: bool | None,
) -> list[dict]:
    """Future MCP-friendly area ranking entry point.

    Rankings are based on average rent ascending (lower average rent ranks first).
    """

    payload = city_area_rent_analytics(
        db,
        city=city,
        bedrooms=bedrooms,
        property_type=property_type,
        ensuite_proxy=ensuite_proxy,
    )

    def _ranking_key(item: dict) -> tuple[int, float, str]:
        average = item.get("average")
        if average is None:
            return (1, 0.0, str(item.get("area", "")).lower())
        return (0, float(average), str(item.get("area", "")).lower())

    ranked = sorted(payload["areas"], key=_ranking_key)
    return [
        {
            "rank": index + 1,
            **area_item,
        }
        for index, area_item in enumerate(ranked)
    ]
