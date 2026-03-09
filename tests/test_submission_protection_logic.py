"""Unit tests for submission protection helpers."""

from decimal import Decimal

from app.services.submission_protections import build_duplicate_fingerprint, run_plausibility_checks


def test_duplicate_fingerprint_is_deterministic() -> None:
    a = build_duplicate_fingerprint(
        contributor_user_id=None,
        contributor_api_key_id=10,
        city="Leeds",
        area="Hyde Park",
        submission_type_code="PINT",
        amount_gbp=Decimal("5.55"),
    )
    b = build_duplicate_fingerprint(
        contributor_user_id=None,
        contributor_api_key_id=10,
        city="Leeds",
        area="Hyde Park",
        submission_type_code="PINT",
        amount_gbp=Decimal("5.55"),
    )

    assert a == b


def test_duplicate_fingerprint_changes_for_different_bucket_or_type() -> None:
    base = build_duplicate_fingerprint(
        contributor_user_id=None,
        contributor_api_key_id=10,
        city="Leeds",
        area="Hyde Park",
        submission_type_code="PINT",
        amount_gbp=Decimal("5.54"),
    )
    changed_amount = build_duplicate_fingerprint(
        contributor_user_id=None,
        contributor_api_key_id=10,
        city="Leeds",
        area="Hyde Park",
        submission_type_code="PINT",
        amount_gbp=Decimal("5.65"),
    )
    changed_type = build_duplicate_fingerprint(
        contributor_user_id=None,
        contributor_api_key_id=10,
        city="Leeds",
        area="Hyde Park",
        submission_type_code="TAKEAWAY",
        amount_gbp=Decimal("5.54"),
    )

    assert base != changed_amount
    assert base != changed_type


def test_plausibility_for_pint_and_takeaway() -> None:
    pint_ok = run_plausibility_checks("PINT", Decimal("5.20"))
    pint_hard_fail = run_plausibility_checks("PINT", Decimal("30.00"))
    takeaway_suspicious = run_plausibility_checks("TAKEAWAY", Decimal("40.00"))

    assert pint_ok.hard_valid is True
    assert pint_ok.suspicious is False

    assert pint_hard_fail.hard_valid is False
    assert "pint_amount_outside_hard_bounds" in pint_hard_fail.hard_fail_reasons

    assert takeaway_suspicious.hard_valid is True
    assert takeaway_suspicious.suspicious is True
    assert "takeaway_amount_outside_typical_range" in takeaway_suspicious.suspicious_reasons
