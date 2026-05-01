"""Tests for analyzer.find_duplicate_layers (US1)."""

from __future__ import annotations

from pathlib import Path

from pbir_validator.analyzer import find_duplicate_layers
from pbir_validator.models import Visual


def _v(
    vid: str,
    *,
    y: float,
    x: float = 0.0,
    visual_type: str = "pivotTable",
    page_id: str = "p1",
) -> Visual:
    return Visual(
        id=vid,
        page_id=page_id,
        visual_type=visual_type,
        x=x,
        y=y,
        width=200.0,
        height=100.0,
        parent_group_name=None,
        path=Path("dummy.json"),
        raw={},
    )


def test_no_duplicates_when_visuals_far_apart() -> None:
    visuals = [_v("a", y=0), _v("b", y=500), _v("c", y=1000)]
    assert find_duplicate_layers(visuals) == []


def test_returns_pair_for_same_type_same_position() -> None:
    visuals = [_v("a", y=322.7), _v("b", y=343.0)]
    out = find_duplicate_layers(visuals, page_display_name="My Page")
    assert len(out) == 1
    d = out[0]
    assert d.page_display_name == "My Page"
    assert d.visual_type == "pivotTable"
    # topmost first (smallest y → "a" at 322.7)
    assert d.visual_a_id == "a"
    assert d.visual_b_id == "b"
    assert d.delta_y_px == 343.0 - 322.7


def test_different_types_at_same_position_do_not_pair() -> None:
    visuals = [
        _v("a", y=300, visual_type="pivotTable"),
        _v("b", y=300, visual_type="card"),
    ]
    assert find_duplicate_layers(visuals) == []


def test_three_overlapping_emits_three_pairs() -> None:
    visuals = [_v("a", y=300), _v("b", y=305), _v("c", y=310)]
    out = find_duplicate_layers(visuals)
    pairs = {(d.visual_a_id, d.visual_b_id) for d in out}
    assert pairs == {("a", "b"), ("a", "c"), ("b", "c")}


def test_empty_input_returns_empty() -> None:
    assert find_duplicate_layers([]) == []


def test_single_visual_returns_empty() -> None:
    assert find_duplicate_layers([_v("solo", y=100)]) == []
