"""Tests for plan_hspacing_fixes() and the X-shift integration in plan_fixes()."""

from __future__ import annotations

import json
from pathlib import Path

from pbir_validator.analyzer import group_into_rows
from pbir_validator.conf import parse_conf
from pbir_validator.fixer import (
    apply_shifts,
    build_visual_lookup,
    plan_fixes,
    plan_hspacing_fixes,
)
from pbir_validator.gui.profiles import load_profile_flags
from pbir_validator.reader import iter_pages, iter_visuals, load_report
from pbir_validator.validator import validate_report


def _strict_rules() -> dict:
    return parse_conf(Path("pbir_validator/profiles/strict.md"))


def _build_indices(report):
    pages_by_id = {p.id: p for p in iter_pages(report)}
    visuals_by_page = {p.id: list(iter_visuals(p)) for p in pages_by_id.values()}
    return pages_by_id, visuals_by_page


def _hspacing_issues_for(report, page_id: str):
    rules = _strict_rules()
    _, _, _, hspacing, _ = validate_report(report, rules)
    return [h for h in hspacing if h.page_id == page_id]


# ---------------------------------------------------------------------------
# T021 — plan_hspacing_fixes() unit tests
# ---------------------------------------------------------------------------


def test_six_slicers_one_deviation_emits_three_shifts(hspacing_report: Path) -> None:
    """6 slicers with one 2-px deviation → v4,v5,v6 shifted left by 2 (FR-001)."""
    report = load_report(hspacing_report)
    pages_by_id, visuals_by_page = _build_indices(report)
    issues = _hspacing_issues_for(report, "slicerRow")
    assert len(issues) == 1

    shifts, unfixable = plan_hspacing_fixes(pages_by_id, visuals_by_page, issues)

    assert unfixable == []
    assert len(shifts) == 3
    by_id = {s.visual_id: s for s in shifts}
    assert set(by_id) == {"v4_slicer", "v5_slicer", "v6_slicer"}
    for s in shifts:
        assert s.delta_x == -2
        assert s.delta_y == 0
        assert s.old_x is not None
        assert s.new_x == s.old_x - 2


def test_zero_issues_emits_zero_shifts(sample_report: Path) -> None:
    """No h-spacing issues → no shifts (SC-003)."""
    report = load_report(sample_report)
    pages_by_id, visuals_by_page = _build_indices(report)
    shifts, unfixable = plan_hspacing_fixes(pages_by_id, visuals_by_page, [])
    assert shifts == []
    assert unfixable == []


def test_shift_attributes_have_expected_shape(hspacing_report: Path) -> None:
    """Emitted Shifts have populated old_x/new_x/delta_x and zero Y change (C1)."""
    report = load_report(hspacing_report)
    pages_by_id, visuals_by_page = _build_indices(report)
    issues = _hspacing_issues_for(report, "slicerRow")
    shifts, _ = plan_hspacing_fixes(pages_by_id, visuals_by_page, issues)

    for s in shifts:
        assert s.old_x is not None and s.new_x is not None and s.delta_x is not None
        assert s.old_y == s.new_y
        assert s.delta_y == 0
        assert s.path.name == "visual.json"


# ---------------------------------------------------------------------------
# T022 — Integration test: end-to-end via plan_fixes() and re-validation
# ---------------------------------------------------------------------------


def test_apply_resolves_hspacing_issue_full_cycle(hspacing_report: Path) -> None:
    """Plan + apply via plan_fixes(strict) → re-validate finds zero issues on slicerRow (SC-001, SC-004)."""
    report = load_report(hspacing_report)
    rules = _strict_rules()
    flags = load_profile_flags("Strict")
    assert flags.get("hspacing_fix") is True

    shifts, _violations = plan_fixes(report, rules, profile_flags=flags)
    # boundary page should NOT contribute shifts (unfixable).
    slicer_shifts = [s for s in shifts if s.page_id == "slicerRow"]
    boundary_shifts = [s for s in shifts if s.page_id == "boundary"]
    assert len(slicer_shifts) == 3
    assert boundary_shifts == []

    lookup = build_visual_lookup(report)
    apply_shifts(slicer_shifts, lookup)

    # Re-validate — slicerRow has zero h-spacing issues now.
    report2 = load_report(hspacing_report)
    issues_after = _hspacing_issues_for(report2, "slicerRow")
    assert issues_after == []

    # Verify v4 actual position.x == 410 (was 412).
    v4_path = (
        hspacing_report
        / "definition"
        / "pages"
        / "slicerRow"
        / "visuals"
        / "v4_slicer"
        / "visual.json"
    )
    data = json.loads(v4_path.read_text(encoding="utf-8"))
    assert data["position"]["x"] == 410


def test_no_op_when_no_hspacing_issues_in_strict_profile(sample_report: Path) -> None:
    """plan_fixes with Strict on a clean report yields no X-shifts (FR-013)."""
    report = load_report(sample_report)
    rules = _strict_rules()
    flags = load_profile_flags("Strict")
    shifts, _ = plan_fixes(report, rules, profile_flags=flags)
    x_shifts = [s for s in shifts if s.delta_x is not None]
    assert x_shifts == []


# ---------------------------------------------------------------------------
# T023 — Boundary refusal tests (FR-005, FR-006)
# ---------------------------------------------------------------------------


def test_right_edge_boundary_marks_group_unfixable(hspacing_report: Path) -> None:
    """boundary page has a card whose fix would push it past page width → unfixable (FR-005)."""
    report = load_report(hspacing_report)
    pages_by_id, visuals_by_page = _build_indices(report)
    issues = _hspacing_issues_for(report, "boundary")
    assert len(issues) >= 1

    shifts, unfixable = plan_hspacing_fixes(pages_by_id, visuals_by_page, issues)

    assert shifts == []
    assert len(unfixable) == len(issues)
    for issue, reason in unfixable:
        assert issue.page_id == "boundary"
        assert "page right" in reason or "right" in reason


def test_unfixable_group_does_not_block_fixable_group_on_other_page(
    hspacing_report: Path,
) -> None:
    """A boundary failure on page B leaves page A's fixable group intact (FR-005)."""
    report = load_report(hspacing_report)
    pages_by_id, visuals_by_page = _build_indices(report)
    rules = _strict_rules()
    _, _, _, all_issues, _ = validate_report(report, rules)

    shifts, unfixable = plan_hspacing_fixes(pages_by_id, visuals_by_page, all_issues)

    # slicerRow is fixable; boundary is not.
    fix_pages = {s.page_id for s in shifts}
    unfix_pages = {iss.page_id for iss, _ in unfixable}
    assert "slicerRow" in fix_pages
    assert "boundary" in unfix_pages
    assert "boundary" not in fix_pages


# ---------------------------------------------------------------------------
# T025 — Profile-gating tests (FR-011, FR-012)
# ---------------------------------------------------------------------------


def test_strict_profile_enables_hspacing_fix() -> None:
    flags = load_profile_flags("Strict")
    assert flags.get("hspacing_fix") is True


def test_standard_profile_does_not_enable_hspacing_fix() -> None:
    flags = load_profile_flags("Standard")
    assert flags.get("hspacing_fix", False) is False


def test_relaxed_profile_does_not_enable_hspacing_fix() -> None:
    flags = load_profile_flags("Relaxed")
    assert flags.get("hspacing_fix", False) is False


def test_plan_fixes_skips_xshifts_when_flag_false(hspacing_report: Path) -> None:
    """plan_fixes with hspacing_fix=False emits zero X-shifts even when issues exist (FR-013)."""
    report = load_report(hspacing_report)
    rules = _strict_rules()
    shifts, _ = plan_fixes(report, rules, profile_flags={"hspacing_fix": False})
    x_shifts = [s for s in shifts if s.delta_x is not None and s.delta_x != 0]
    assert x_shifts == []


def test_plan_fixes_skips_xshifts_when_flags_none(hspacing_report: Path) -> None:
    """plan_fixes with no profile_flags is byte-equivalent to pre-feature behavior."""
    report = load_report(hspacing_report)
    rules = _strict_rules()
    shifts, _ = plan_fixes(report, rules)
    x_shifts = [s for s in shifts if s.delta_x is not None and s.delta_x != 0]
    assert x_shifts == []


def test_plan_fixes_emits_xshifts_when_flag_true(hspacing_report: Path) -> None:
    """plan_fixes with hspacing_fix=True emits X-shifts for fixable groups (FR-011)."""
    report = load_report(hspacing_report)
    rules = _strict_rules()
    shifts, _ = plan_fixes(report, rules, profile_flags={"hspacing_fix": True})
    x_shifts = [s for s in shifts if s.delta_x is not None and s.delta_x != 0]
    assert len(x_shifts) == 3
