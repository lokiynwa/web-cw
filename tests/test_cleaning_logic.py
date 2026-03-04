"""Unit tests for deterministic cleaning rules."""

from decimal import Decimal

from app.services.cleaning import _derive_city_area, _house_size_bucket, _parse_money, clean_listing_row


def test_parse_price_accepts_currency_value() -> None:
    outcome = _parse_money("£125.50", field="price")

    assert outcome.valid is True
    assert outcome.value == Decimal("125.50")
    assert outcome.reason is None


def test_parse_price_rejects_monthly_unit() -> None:
    outcome = _parse_money("1200 pcm", field="price")

    assert outcome.valid is False
    assert outcome.value is None
    assert outcome.reason == "price_unsupported_monthly_unit"


def test_parse_deposit_missing_is_not_valid_but_not_hard_reason() -> None:
    outcome = _parse_money("", field="deposit")

    assert outcome.valid is False
    assert outcome.value is None
    assert outcome.reason is None


def test_derive_city_area_from_address_with_postcode() -> None:
    city, area, reason = _derive_city_area("Adderley road, Clarendon park, Leicester, LE21WD")

    assert city == "Leicester"
    assert area == "Clarendon park"
    assert reason is None


def test_house_size_bucket_boundaries() -> None:
    assert _house_size_bucket(None) is None
    assert _house_size_bucket(1) == "small"
    assert _house_size_bucket(2) == "medium"
    assert _house_size_bucket(3) == "medium"
    assert _house_size_bucket(4) == "large"


def test_clean_listing_sets_ensuite_proxy_and_bucket() -> None:
    row = {
        "Price": "150",
        "deposit": "300",
        "Bedrooms": "2",
        "Bathrooms": "2",
        "type": "House",
        "address": "Hyde Park, Leeds, LS6 1AA",
    }

    cleaned = clean_listing_row(row)

    assert cleaned.valid_price is True
    assert cleaned.valid_bedrooms is True
    assert cleaned.valid_bathrooms is True
    assert cleaned.is_ensuite_proxy is True
    assert cleaned.house_size_bucket == "medium"
    assert cleaned.city == "Leeds"
    assert cleaned.area == "Hyde Park"
