"""Tests for ``controllers.export_all_zip`` and ``default_zip_filename`` (T014, T016)."""

from __future__ import annotations

import datetime as _dt
import io
import zipfile
from pathlib import Path

import pytest

from pbir_validator.gui import controllers
from pbir_validator.gui.export import _table_to_csv_bytes
from pbir_validator.models import (
    DuplicateLayer,
    HSpacingIssue,
    Misalignment,
    Violation,
)


def _viol(**kw) -> Violation:
    base = dict(
        page_id="p1",
        page_display_name="Page 1",
        from_type="card",
        to_type="actionButton",
        expected_px=8,
        actual_px=10.0,
        deviation_px=2.0,
        from_row_index=0,
        to_row_index=1,
        from_name="A",
        to_name="B",
    )
    base.update(kw)
    return Violation(**base)


def _result_full() -> controllers.ValidateResult:
    return controllers.ValidateResult(
        gaps=[_viol()],
        overlaps=[_viol(actual_px=-3.0, deviation_px=-3.0)],
        duplicate_layers=[
            DuplicateLayer(
                page_id="p1",
                page_display_name="Page 1",
                visual_type="card",
                visual_a_id="a",
                visual_a_title="A",
                visual_b_id="b",
                visual_b_title="B",
                delta_y_px=0.0,
            )
        ],
        misalignments=[
            Misalignment(
                page_id="p1",
                page_display_name="Page 1",
                visual_id="v1",
                visual_type="card",
                actual_y=105.0,
                expected_y=100.0,
                deviation_px=5.0,
                row_index=0,
                path=Path("x"),
            )
        ],
        h_spacing=[
            HSpacingIssue(
                page_id="p1",
                page_display_name="Page 1",
                visual_type="card",
                left_visual_id="a",
                right_visual_id="b",
                expected_gap_px=8,
                actual_gap_px=16,
                deviation_px=8,
                row_index=0,
            )
        ],
    )


def test_export_all_zip_full_set(tmp_path: Path) -> None:
    result = _result_full()
    fix_plan = controllers.FixPlan(shifts=[], summary="", unfixable=[])  # empty
    dest = tmp_path / "out.zip"
    written = controllers.export_all_zip(result, None, dest)
    assert sorted(written) == [
        "duplicate_layers.csv",
        "gaps.csv",
        "h_spacing.csv",
        "misalignments.csv",
        "overlaps.csv",
    ]
    with zipfile.ZipFile(dest) as zf:
        assert sorted(zf.namelist()) == sorted(written)


def test_export_all_zip_skips_empty_tabs(tmp_path: Path) -> None:
    result = controllers.ValidateResult(
        gaps=[_viol()],
        overlaps=[],
        duplicate_layers=[],
        misalignments=[],
        h_spacing=[],
    )
    dest = tmp_path / "out.zip"
    written = controllers.export_all_zip(result, None, dest)
    assert written == ["gaps.csv"]
    with zipfile.ZipFile(dest) as zf:
        assert zf.namelist() == ["gaps.csv"]


def test_export_all_zip_csv_bytes_match_per_tab_helper(tmp_path: Path) -> None:
    """Bytes archived MUST equal the per-tab CSV helper output (FR-013)."""
    result = _result_full()
    dest = tmp_path / "out.zip"
    controllers.export_all_zip(result, None, dest)
    with zipfile.ZipFile(dest) as zf:
        gaps_bytes = zf.read("gaps.csv")
    expected = _table_to_csv_bytes(
        controllers.GAP_COLUMNS, controllers.gap_rows(result.gaps)
    )
    assert gaps_bytes == expected


def test_export_all_zip_raises_on_empty(tmp_path: Path) -> None:
    result = controllers.ValidateResult()
    dest = tmp_path / "out.zip"
    with pytest.raises(controllers.NothingToExportError):
        controllers.export_all_zip(result, None, dest)
    assert not dest.exists()


def test_export_all_zip_propagates_oserror(tmp_path: Path) -> None:
    result = _result_full()
    # Destination directory does not exist → OSError on open.
    dest = tmp_path / "missing-dir" / "out.zip"
    with pytest.raises(OSError):
        controllers.export_all_zip(result, None, dest)


def test_default_zip_filename_uses_frozen_datetime() -> None:
    when = _dt.datetime(2026, 5, 2, 14, 15, 30)
    name = controllers.default_zip_filename("/some/MyReport.Report", now=when)
    assert name == "MyReport.Report_validation_20260502-141530.zip"


def test_default_zip_filename_handles_root_basename() -> None:
    when = _dt.datetime(2026, 1, 1, 0, 0, 0)
    name = controllers.default_zip_filename("ReportFolder", now=when)
    assert name == "ReportFolder_validation_20260101-000000.zip"


def test_export_all_zip_includes_fix_plan_when_provided(tmp_path: Path) -> None:
    from pbir_validator.models import Shift

    result = controllers.ValidateResult(gaps=[_viol()])
    shifts = [
        Shift(
            visual_id="v1",
            page_id="p1",
            path=Path("x"),
            old_y=100,
            new_y=105,
            delta_y=5,
        )
    ]
    dest = tmp_path / "out.zip"
    written = controllers.export_all_zip(result, shifts, dest)
    assert "fix_plan.csv" in written
