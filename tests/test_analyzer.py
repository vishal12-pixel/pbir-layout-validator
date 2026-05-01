"""Tests for pbir_validator.analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.analyzer import (
    compute_gaps,
    dedupe_stacked_visuals,
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
    # Different x so dedup_stacked_visuals doesn't merge them.
    vs = [_v("a", "card", 0, 10), _v("b", "card", 200, 13)]  # diff=3 > 2
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


def test_dedupe_collapses_same_type_stack() -> None:
    # Two pivotTables at the same x/width but slightly different y/h — a
    # bookmark-toggled stack. Should collapse to the topmost.
    vs = [
        _v("a", "pivotTable", 20, 301, w=1560, h=510),
        _v("b", "pivotTable", 20, 343, w=1560, h=620),
    ]
    deduped = dedupe_stacked_visuals(vs)
    assert len(deduped) == 1
    assert deduped[0].id == "a"  # smallest y wins


def test_dedupe_keeps_distant_same_type_visuals() -> None:
    # Two pivotTables far apart vertically — different visible rows, not a stack.
    vs = [
        _v("a", "pivotTable", 20, 100, w=1560, h=200),
        _v("b", "pivotTable", 20, 500, w=1560, h=200),
    ]
    deduped = dedupe_stacked_visuals(vs)
    assert len(deduped) == 2


def test_dedupe_keeps_different_types_at_same_position() -> None:
    # A card and a button at the same position should NOT be merged.
    vs = [
        _v("a", "card", 0, 100, w=200, h=80),
        _v("b", "actionButton", 0, 110, w=200, h=40),
    ]
    deduped = dedupe_stacked_visuals(vs)
    assert len(deduped) == 2


def test_dedupe_keeps_side_by_side_same_type() -> None:
    # Two cards at the same y but different x (no horizontal overlap) — both kept.
    vs = [
        _v("a", "card", 0, 100, w=200, h=80),
        _v("b", "card", 300, 100, w=200, h=80),
    ]
    deduped = dedupe_stacked_visuals(vs)
    assert len(deduped) == 2


def test_dedupe_collapses_chain_of_three_alternates() -> None:
    # Three alternates all stacked at the same slot — collapse to one.
    vs = [
        _v("a", "pivotTable", 20, 300, w=1560, h=500),
        _v("b", "pivotTable", 20, 320, w=1560, h=500),
        _v("c", "pivotTable", 20, 340, w=1560, h=500),
    ]
    deduped = dedupe_stacked_visuals(vs)
    assert len(deduped) == 1
    assert deduped[0].id == "a"

def test_hspacing_consistent_row_no_issues() -> None:
    from pbir_validator.analyzer import find_row_hspacing_issues, group_into_rows
    # 4 slicers at y=10, width=100, gaps of 20px each.
    vs = [
        _v("s1", "slicer", 0,   10, w=100, h=50),
        _v("s2", "slicer", 120, 10, w=100, h=50),
        _v("s3", "slicer", 240, 10, w=100, h=50),
        _v("s4", "slicer", 360, 10, w=100, h=50),
    ]
    rows = group_into_rows(vs)
    assert find_row_hspacing_issues(rows) == []


def test_hspacing_detects_off_gap_in_row() -> None:
    from pbir_validator.analyzer import find_row_hspacing_issues, group_into_rows
    # 4 slicers; gaps are 20, 22, 20 → one outlier on the middle gap.
    vs = [
        _v("s1", "slicer", 0,   10, w=100, h=50),
        _v("s2", "slicer", 120, 10, w=100, h=50),
        _v("s3", "slicer", 242, 10, w=100, h=50),  # 22px gap (off by 2)
        _v("s4", "slicer", 362, 10, w=100, h=50),
    ]
    rows = group_into_rows(vs)
    issues = find_row_hspacing_issues(rows)
    assert len(issues) == 1
    row_idx, left, right, ref_gap, dev = issues[0]
    assert left.id == "s2"
    assert right.id == "s3"
    assert round(ref_gap) == 20
    assert round(dev) == 2


def test_hspacing_ignores_rows_with_fewer_than_three_peers() -> None:
    from pbir_validator.analyzer import find_row_hspacing_issues, group_into_rows
    # Only 2 slicers — cannot establish a modal pattern.
    vs = [
        _v("s1", "slicer", 0,   10, w=100, h=50),
        _v("s2", "slicer", 130, 10, w=100, h=50),
    ]
    rows = group_into_rows(vs)
    assert find_row_hspacing_issues(rows) == []


def test_hspacing_ignores_mixed_types() -> None:
    from pbir_validator.analyzer import find_row_hspacing_issues, group_into_rows
    # 2 slicers + 1 card — buckets all have <3 peers.
    vs = [
        _v("s1", "slicer", 0,   10, w=100, h=50),
        _v("s2", "slicer", 120, 10, w=100, h=50),
        _v("c1", "card",   240, 10, w=100, h=50),
    ]
    rows = group_into_rows(vs)
    assert find_row_hspacing_issues(rows) == []
