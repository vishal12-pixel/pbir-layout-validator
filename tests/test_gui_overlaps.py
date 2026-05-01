"""Tests for the gap/overlap split in the GUI controllers."""

from __future__ import annotations

from pbir_validator.gui import controllers
from pbir_validator.models import Violation


def _viol(actual: float, *, dev: float = 0.0) -> Violation:
    return Violation(
        page_id="p",
        page_display_name="Page",
        from_type="card",
        to_type="actionButton",
        expected_px=9,
        actual_px=actual,
        deviation_px=dev,
        from_row_index=0,
        to_row_index=1,
    )


def test_split_partitions_by_actual_sign() -> None:
    gaps, overlaps = controllers._split_gaps_and_overlaps(
        [_viol(10), _viol(-5), _viol(0), _viol(-254)]
    )
    assert [v.actual_px for v in gaps] == [10, 0]
    assert [v.actual_px for v in overlaps] == [-5, -254]


def test_validate_result_has_overlaps_field() -> None:
    r = controllers.ValidateResult()
    assert r.overlaps == []
    assert r.gaps == []


def test_overlap_columns_count_matches_rows() -> None:
    rows = controllers.overlap_rows([_viol(-33.5), _viol(-254)])
    assert len(rows) == 2
    for row in rows:
        assert len(row) == len(controllers.OVERLAP_COLUMNS)


def test_overlap_rows_report_positive_overlap_px() -> None:
    rows = controllers.overlap_rows([_viol(-33.5)])
    # column index 3 is overlap_px = -actual_px
    assert rows[0][3] == 33.5


def test_overlap_rows_sorted_largest_first() -> None:
    rows = controllers.overlap_rows([_viol(-5), _viol(-254), _viol(-33.5)])
    overlap_px = [r[3] for r in rows]
    assert overlap_px == [254, 33.5, 5]


def test_gap_rows_only_show_positive_actual() -> None:
    """After split, gap_rows() never receives negative actual_px values."""
    gaps, _ = controllers._split_gaps_and_overlaps([_viol(10), _viol(-5)])
    rows = controllers.gap_rows(gaps)
    # column 4 is actual_px
    assert all(row[4] >= 0 for row in rows)
