"""Unit tests for affordability scoring helpers."""

import pytest
from fastapi import HTTPException

from app.routers.affordability import (
    _combine_component_scores,
    _resolve_requested_weights,
    _score_component,
)


def test_score_component_is_bounded() -> None:
    assert _score_component(50.0, floor=80.0, ceiling=300.0) == 100.0
    assert _score_component(1000.0, floor=80.0, ceiling=300.0) == 0.0


def test_combine_component_scores_weighted_average() -> None:
    score, effective = _combine_component_scores(
        selected_components=["rent", "pint", "takeaway"],
        requested_weights={"rent": 0.6, "pint": 0.2, "takeaway": 0.2},
        component_scores={"rent": 50.0, "pint": 100.0, "takeaway": 0.0},
    )

    assert score == 50.0
    assert effective == {"rent": 0.6, "pint": 0.2, "takeaway": 0.2}


def test_combine_component_scores_reweights_when_one_component_missing() -> None:
    score, effective = _combine_component_scores(
        selected_components=["rent", "pint"],
        requested_weights={"rent": 0.6, "pint": 0.2, "takeaway": 0.2},
        component_scores={"rent": 50.0, "pint": None},
    )

    assert score == 50.0
    assert effective == {"rent": 1.0, "pint": 0.0}


def test_weight_validation_rejects_negative_values() -> None:
    with pytest.raises(HTTPException) as exc:
        _resolve_requested_weights(rent_weight=-0.1, pint_weight=0.2, takeaway_weight=0.2)

    assert exc.value.status_code == 422


def test_monotonic_component_scoring_for_costs() -> None:
    low_cost_score = _score_component(5.0, floor=2.0, ceiling=10.0)
    high_cost_score = _score_component(8.0, floor=2.0, ceiling=10.0)

    assert low_cost_score is not None
    assert high_cost_score is not None
    assert low_cost_score > high_cost_score


def test_monotonic_overall_score_when_component_improves() -> None:
    baseline, _ = _combine_component_scores(
        selected_components=["rent", "pint"],
        requested_weights={"rent": 0.6, "pint": 0.4, "takeaway": 0.0},
        component_scores={"rent": 40.0, "pint": 50.0},
    )
    improved, _ = _combine_component_scores(
        selected_components=["rent", "pint"],
        requested_weights={"rent": 0.6, "pint": 0.4, "takeaway": 0.0},
        component_scores={"rent": 60.0, "pint": 50.0},
    )

    assert baseline is not None
    assert improved is not None
    assert improved > baseline
