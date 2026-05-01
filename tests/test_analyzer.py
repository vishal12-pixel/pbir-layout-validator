"""Tests for pbir_validator.analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.analyzer import (
    compute_gaps,
    group_into_rows,
    pick_representative_type,
)
from pbir_validator.models import Visual


def _v(
    vid: str, vt: str, x: float, y: float, w: float = 100, h: float = 50
) -> Visual:
    return Visual(
        id=vid,
        page_id="p1",
        visual_type=vt,
        x=x,
        y=y,
        width=w,
        height=h,
        parent_group_name=None,
        path=Path("/x"),
        raw={},
        indent=2,
    )


def test_pick_representative_most_frequent() -> None:
    vs = [_v("a", "card", 0, 0), _v("b", "card", 100, 0), _v("c", "shape", 200, 0)]
    rep, mixed = pick_representative_type(vs)
    assert rep == "card"
    assert mixed is True


def test_pick_representative_lex_tiebreak() -> None:
    vs = [_v("a", "shape", 0, 0), _v("b", "card", 100, 0)]
    rep, mixed = pick_representative_type(vs)
    assert rep == "card"  # lex first
    assert mixed is True


def test_pick_representative_single_type() -> None:
    rep, mixed = pick_representative_type([_v("a", "card", 0, 0)])
    assert rep == "card"
    assert mixed is False


def test_group_within_two_pixel_tolerance() -> None:
    vs = [_v("a", "card", 0, 10), _v("b", "card", 100, 11), _v("c", "card", 200, 12)]
    rows = group_into_rows(vs)
    assert len(rows) == 1
    assert rows[0].y_min == 10
    assert rows[0].bottom == 62  # max(y+h) = 12 + 50


def test_group_outside_tolerance_starts_new_row() -> None:
    vs = [_v("a", "card", 0, 10), _v("b", "card", 0, 13)]  # diff=3 > 2
    rows = group_into_rows(vs)
    assert len(rows) == 2


def test_rows_sorted_by_y_min() -> None:
    vs = [_v("a", "card", 0, 100), _v("b", "card", 0, 10)]
    rows = group_into_rows(vs)
    assert [r.y_min for r in rows] == [10, 100]


def test_compute_gaps_uses_bottom_of_upper_row() -> None:
    vs = [
        _v("a", "card", 0, 10, h=80),  # bottom=90
        _v("b", "actionButton", 0, 99, h=40),  # gap = 99-90 = 9
        _v("c", "tableEx", 0, 155, h=200),  # gap = 155 - (99+40) = 16
    ]
    rows = group_into_rows(vs)
    gaps = compute_gaps(rows)
    assert [g[2] for g in gaps] == [9, 16]


def test_mixed_row_warning_emitted_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    vs = [_v("a", "card", 0, 10), _v("b", "shape", 100, 10)]
    group_into_rows(vs)
    err = capsys.readouterr().err
    assert err.count("mixed-type row") == 1


def test_empty_input_yields_no_rows() -> None:
    assert group_into_rows([]) == []


def test_compute_gaps_handles_single_row() -> None:
    vs = [_v("a", "card", 0, 0)]
    rows = group_into_rows(vs)
    assert compute_gaps(rows) == []
