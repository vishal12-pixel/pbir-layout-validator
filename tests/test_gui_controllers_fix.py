"""Unit tests for pbir_validator.gui.controllers fix (T033, T034)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.gui import controllers
from pbir_validator.learner import learn
from pbir_validator.reader import iter_pages, load_report


def _setup_conf(sample_report: Path) -> Path:
    """Generate conf.md from pageA so pageB has known violations."""
    report = load_report(sample_report)
    page_a = next(p for p in iter_pages(report) if p.id == "pageA")
    learn(report, page_a, sample_report / "conf.md", force=True)
    return sample_report / "conf.md"


# -- fix_plan (T033) ---------------------------------------------------------


def test_fix_plan_returns_proposed_shifts_with_stable_ids(sample_report: Path) -> None:
    conf = _setup_conf(sample_report)
    plan = controllers.fix_plan(sample_report, conf)
    assert isinstance(plan, controllers.FixPlan)
    assert plan.shifts, "fixture has at least one fixable shift"
    ids = [ps.id for ps in plan.shifts]
    assert len(ids) == len(set(ids)), "ids must be unique"
    assert plan.summary  # non-empty


def test_fix_plan_invalid_report_raises_fix_error(tmp_path: Path) -> None:
    not_a_report = tmp_path / "no"
    not_a_report.mkdir()
    with pytest.raises(controllers.FixError):
        controllers.fix_plan(not_a_report, None)


def test_fix_plan_missing_conf_raises_fix_error(sample_report: Path) -> None:
    conf = sample_report / "conf.md"
    if conf.exists():
        conf.unlink()
    with pytest.raises(controllers.FixError):
        controllers.fix_plan(sample_report, conf)


def test_fix_plan_rows_column_count_matches(sample_report: Path) -> None:
    conf = _setup_conf(sample_report)
    plan = controllers.fix_plan(sample_report, conf)
    rows = controllers.fix_plan_rows(plan)
    if rows:
        assert len(rows[0]) == len(controllers.FIX_PLAN_COLUMNS)


# -- fix_apply (T034) --------------------------------------------------------


def test_fix_apply_empty_selection_raises(sample_report: Path) -> None:
    conf = _setup_conf(sample_report)
    plan = controllers.fix_plan(sample_report, conf)
    with pytest.raises(controllers.FixError, match="no shifts selected"):
        controllers.fix_apply(sample_report, plan, set())


def test_fix_apply_writes_only_selected(sample_report: Path) -> None:
    conf = _setup_conf(sample_report)
    plan = controllers.fix_plan(sample_report, conf)
    if not plan.shifts:
        pytest.skip("no shifts produced for this fixture")

    # Select only the first shift
    chosen_id = plan.shifts[0].id
    applied = controllers.fix_apply(sample_report, plan, {chosen_id})
    assert applied == 1


def test_fix_apply_selecting_unknown_id_raises(sample_report: Path) -> None:
    conf = _setup_conf(sample_report)
    plan = controllers.fix_plan(sample_report, conf)
    with pytest.raises(controllers.FixError, match="matched no proposed shifts"):
        controllers.fix_apply(sample_report, plan, {"id-that-does-not-exist"})


def test_fix_apply_invalid_report_raises(tmp_path: Path) -> None:
    plan = controllers.FixPlan(shifts=[], summary="empty")
    bogus = tmp_path / "no"
    bogus.mkdir()
    with pytest.raises(controllers.FixError):
        controllers.fix_apply(bogus, plan, {"x"})
