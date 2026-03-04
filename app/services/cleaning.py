"""Conservative rule-based cleaning utilities for rental listings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

POSTCODE_PATTERN = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE)
SPACES_PATTERN = re.compile(r"\s+")
RANGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:-|to|/)\s*\d+(?:\.\d+)?\b", re.IGNORECASE)
NON_NUMERIC_PATTERN = re.compile(r"[^0-9.\-]")

KNOWN_LOCATION_SUFFIXES = {"uk", "united kingdom", "england"}

TYPE_MAP = {
    "flat": "flat",
    "apartment": "flat",
    "house": "house",
    "studio": "studio",
    "room": "room",
    "ensuite": "ensuite_room",
    "en-suite": "ensuite_room",
}


@dataclass
class CleaningResult:
    """Normalized values and validation outcomes for a raw listing."""

    price_gbp_weekly: Decimal | None
    deposit_gbp: Decimal | None
    bedrooms: int | None
    bathrooms: int | None
    listing_type: str | None
    address_normalized: str | None
    city: str | None
    area: str | None
    is_ensuite_proxy: bool | None
    house_size_bucket: str | None
    valid_price: bool
    valid_deposit: bool
    valid_bedrooms: bool
    valid_bathrooms: bool
    valid_type: bool
    valid_address: bool
    is_excluded: bool
    exclusion_reasons: list[str]


@dataclass
class ParseOutcome:
    value: Any
    valid: bool
    reason: str | None = None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return SPACES_PATTERN.sub(" ", str(value)).strip()


def _parse_money(value: Any, *, field: str) -> ParseOutcome:
    raw = _clean_text(value)
    if not raw:
        if field == "deposit":
            return ParseOutcome(None, False)
        return ParseOutcome(None, False, f"{field}_missing")

    lowered = raw.lower()
    if RANGE_PATTERN.search(lowered):
        return ParseOutcome(None, False, f"{field}_ambiguous_range")

    if field == "price" and any(token in lowered for token in ("pcm", "per month", "monthly")):
        return ParseOutcome(None, False, "price_unsupported_monthly_unit")

    if field == "deposit" and any(token in lowered for token in ("pcm", "per month", "monthly", "weekly", "pw")):
        return ParseOutcome(None, False, "deposit_unsupported_unit")

    numeric_text = NON_NUMERIC_PATTERN.sub("", raw)
    if not numeric_text or numeric_text in {"-", ".", "-."}:
        return ParseOutcome(None, False, f"{field}_not_numeric")

    try:
        numeric = Decimal(numeric_text)
    except InvalidOperation:
        return ParseOutcome(None, False, f"{field}_not_numeric")

    if numeric <= 0:
        return ParseOutcome(None, False, f"{field}_non_positive")

    # Conservative upper bound to reject clearly broken values.
    if numeric > Decimal("10000"):
        return ParseOutcome(None, False, f"{field}_out_of_range")

    return ParseOutcome(numeric.quantize(Decimal("0.01")), True)


def _parse_int(value: Any, *, field: str) -> ParseOutcome:
    raw = _clean_text(value)
    if not raw:
        return ParseOutcome(None, False, f"{field}_missing")

    lowered = raw.lower()
    if RANGE_PATTERN.search(lowered) or "+" in lowered:
        return ParseOutcome(None, False, f"{field}_ambiguous")

    numeric_text = NON_NUMERIC_PATTERN.sub("", raw)
    if not numeric_text:
        return ParseOutcome(None, False, f"{field}_not_numeric")

    try:
        decimal_value = Decimal(numeric_text)
    except InvalidOperation:
        return ParseOutcome(None, False, f"{field}_not_numeric")

    if decimal_value != decimal_value.to_integral_value():
        return ParseOutcome(None, False, f"{field}_not_integer")

    integer_value = int(decimal_value)
    if integer_value <= 0:
        return ParseOutcome(None, False, f"{field}_non_positive")

    if integer_value > 20:
        return ParseOutcome(None, False, f"{field}_out_of_range")

    return ParseOutcome(integer_value, True)


def _standardize_type(value: Any) -> ParseOutcome:
    raw = _clean_text(value)
    if not raw:
        return ParseOutcome(None, False, "type_missing")

    lowered = raw.lower()
    for keyword, normalized in TYPE_MAP.items():
        if keyword in lowered:
            return ParseOutcome(normalized, True)

    return ParseOutcome(None, False, "type_unrecognized")


def _standardize_address(value: Any) -> ParseOutcome:
    raw = _clean_text(value)
    if not raw:
        return ParseOutcome(None, False, "address_missing")

    parts = [part.strip() for part in raw.split(",") if part and part.strip()]
    if not parts:
        return ParseOutcome(None, False, "address_missing")

    normalized = ", ".join(parts)
    return ParseOutcome(normalized, True)


def _derive_city_area(address: str | None) -> tuple[str | None, str | None, str | None]:
    if not address:
        return None, None, "address_missing"

    cleaned_parts: list[str] = []
    for part in (segment.strip() for segment in address.split(",")):
        if not part:
            continue

        no_postcode = POSTCODE_PATTERN.sub("", part).strip(" ,")
        if not no_postcode:
            continue

        if no_postcode.lower() in KNOWN_LOCATION_SUFFIXES:
            continue

        cleaned_parts.append(no_postcode)

    if not cleaned_parts:
        return None, None, "address_no_location_tokens"

    city = cleaned_parts[-1]
    area = cleaned_parts[-2] if len(cleaned_parts) >= 2 else None

    if not city:
        return None, area, "city_missing"

    return city, area, None


def _house_size_bucket(bedrooms: int | None) -> str | None:
    if bedrooms is None:
        return None
    if bedrooms <= 1:
        return "small"
    if bedrooms <= 3:
        return "medium"
    return "large"


def clean_listing_row(raw_row: Mapping[str, Any]) -> CleaningResult:
    """Apply conservative rule-based normalization to a raw listing row."""

    reasons: list[str] = []

    price_outcome = _parse_money(raw_row.get("Price"), field="price")
    deposit_outcome = _parse_money(raw_row.get("deposit"), field="deposit")
    bedrooms_outcome = _parse_int(raw_row.get("Bedrooms"), field="bedrooms")
    bathrooms_outcome = _parse_int(raw_row.get("Bathrooms"), field="bathrooms")
    type_outcome = _standardize_type(raw_row.get("type"))
    address_outcome = _standardize_address(raw_row.get("address"))

    if price_outcome.reason:
        reasons.append(price_outcome.reason)
    if bedrooms_outcome.reason:
        reasons.append(bedrooms_outcome.reason)
    if bathrooms_outcome.reason:
        reasons.append(bathrooms_outcome.reason)
    if type_outcome.reason:
        reasons.append(type_outcome.reason)
    if address_outcome.reason:
        reasons.append(address_outcome.reason)

    city, area, city_area_reason = _derive_city_area(address_outcome.value)
    if city_area_reason:
        reasons.append(city_area_reason)

    bedrooms = bedrooms_outcome.value if bedrooms_outcome.valid else None
    bathrooms = bathrooms_outcome.value if bathrooms_outcome.valid else None

    is_ensuite_proxy: bool | None = None
    if bedrooms is not None and bathrooms is not None:
        is_ensuite_proxy = bathrooms >= bedrooms

    house_size_bucket = _house_size_bucket(bedrooms)

    # Deposit can be legitimately absent in source data, so it does not exclude by itself.
    required_valid = [
        price_outcome.valid,
        bedrooms_outcome.valid,
        bathrooms_outcome.valid,
        type_outcome.valid,
        address_outcome.valid,
        city is not None,
    ]
    is_excluded = not all(required_valid)

    unique_reasons = sorted(set(reasons))

    return CleaningResult(
        price_gbp_weekly=price_outcome.value if price_outcome.valid else None,
        deposit_gbp=deposit_outcome.value if deposit_outcome.valid else None,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        listing_type=type_outcome.value if type_outcome.valid else None,
        address_normalized=address_outcome.value if address_outcome.valid else None,
        city=city,
        area=area,
        is_ensuite_proxy=is_ensuite_proxy,
        house_size_bucket=house_size_bucket,
        valid_price=price_outcome.valid,
        valid_deposit=deposit_outcome.valid,
        valid_bedrooms=bedrooms_outcome.valid,
        valid_bathrooms=bathrooms_outcome.valid,
        valid_type=type_outcome.valid,
        valid_address=address_outcome.valid,
        is_excluded=is_excluded,
        exclusion_reasons=unique_reasons,
    )
