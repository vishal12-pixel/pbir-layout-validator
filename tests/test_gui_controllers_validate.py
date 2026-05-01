"""Unit tests for pbir_validator.gui.controllers (T021)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.gui import controllers
from pbir_validator.learner import learn
from pbir_validator.reader import iter_pages, load_report


def _learn_from_a(sample_report: Path) -> Path:
    report = load_report(sample_report)
    page_a = next(p for p in iter_pages(report) if p.id == "pageA")
    learn(report, page_a, sample_report / "conf.md", force=True)
    return sample_report / "conf.md"


def test_validate_returns_three_lists(sample_report: Path) -> None:
    conf = _learn_from_a(sample_report)
    result = controllers.validate(sample_report, conf)
    assert isinstance(result, controllers.ValidateResult)
    assert isinstance(result.gaps, list)
    assert isinstance(result.misalignments, list)
    assert isinstance(result.h_spacing, list)
    # The fixture has at least one known gap violation on pageB
    assert len(result.gaps) >= 1


def test_validate_default_conf_path(sample_report: Path) -> None:
    _learn_from_a(sample_report)
    # Pass conf=None — should default to <report>/conf.md
    result = controllers.validate(sample_report, None)
    assert len(result.gaps) >= 1


def test_validate_invalid_report_raises_validate_error(tmp_path: Path) -> None:
    not_a_report = tmp_path / "not_a_report"
    not_a_report.mkdir()
    with pytest.raises(controllers.ValidateError):
        controllers.validate(not_a_report, None)


def test_validate_missing_conf_raises_validate_error(sample_report: Path) -> None:
    # No conf.md exists yet — parse_conf should raise, wrapped as ValidateError
    conf = sample_report / "conf.md"
    if conf.exists():
        conf.unlink()
    with pytest.raises(controllers.ValidateError):
        controllers.validate(sample_report, conf)


def test_gap_rows_column_count_matches_headers() -> None:
    from pbir_validator.models import Violation

    v = Violation(
        page_id="p1",
        page_display_name="Page 1",
        from_type="card",
        to_type="table",
        expected_px=16,
        actual_px=12.0,
        deviation_px=4.0,
        from_row_index=0,
        to_row_index=1,
    )
    rows = controllers.gap_rows([v])
    assert len(rows) == 1
    assert len(rows[0]) == len(controllers.GAP_COLUMNS)


def test_misalignment_rows_column_count() -> None:
    from pbir_validator.models import Misalignment

    m = Misalignment(
        page_id="p",
        page_display_name="Page",
        visual_id="v1",
        visual_type="card",
        actual_y=100.0,
        expected_y=98.0,
        deviation_px=2.0,
        row_index=1,
        path=Path("dummy"),
    )
    rows = controllers.misalignment_rows([m])
    assert len(rows[0]) == len(controllers.MISALIGNMENT_COLUMNS)


def test_h_spacing_rows_column_count() -> None:
    from pbir_validator.models import HSpacingIssue

    h = HSpacingIssue(
        page_id="p",
        page_display_name="Page",
        visual_type="slicer",
        left_visual_id="L",
        right_visual_id="R",
        expected_gap_px=8.0,
        actual_gap_px=10.0,
        deviation_px=2.0,
        row_index=0,
    )
    rows = controllers.h_spacing_rows([h])
    assert len(rows[0]) == len(controllers.HSPACING_COLUMNS)
