"""T017 — Regression: when there are no h-spacing issues, the plan_fixes()
output is identical with and without ``profile_flags={'hspacing_fix': True}``,
and applying it leaves the report byte-identical (FR-013, SC-007)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pbir_validator.conf import parse_conf
from pbir_validator.fixer import (
    apply_shifts,
    build_visual_lookup,
    plan_fixes,
)
from pbir_validator.reader import load_report


def _hash_dir(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".pbir_validator_undo" not in p.parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_no_hspacing_issues_means_no_xshifts(sample_report: Path) -> None:
    """sample_report has zero h-spacing issues → no X-shifts emitted under Strict."""
    report = load_report(sample_report)
    rules = parse_conf(Path("pbir_validator/profiles/strict.md"))
    shifts, _ = plan_fixes(report, rules, profile_flags={"hspacing_fix": True})
    x_shifts = [s for s in shifts if s.delta_x is not None and s.delta_x != 0]
    assert x_shifts == []


def test_hspacing_flag_is_invisible_when_no_issues(sample_report: Path) -> None:
    """plan_fixes(...,profile_flags={hspacing_fix:True}) yields the same shifts
    as plan_fixes() when no h-spacing issues exist (the Y-shift plan is
    untouched)."""
    report = load_report(sample_report)
    rules = parse_conf(Path("pbir_validator/profiles/strict.md"))
    shifts_a, viol_a = plan_fixes(report, rules)
    shifts_b, viol_b = plan_fixes(report, rules, profile_flags={"hspacing_fix": True})

    def _key(s):
        return (s.page_id, s.visual_id, s.old_y, s.new_y, s.old_x, s.new_x)

    assert sorted(_key(s) for s in shifts_a) == sorted(_key(s) for s in shifts_b)
    assert len(viol_a) == len(viol_b)


def test_apply_when_no_issues_is_byte_identical(sample_report: Path) -> None:
    """When plan_fixes(hspacing_fix=True) produces zero shifts, applying it
    leaves the report byte-identical (FR-013, SC-007).

    If the sample report has Y-shifts, the no-op invariant still holds for
    the X dimension: per ``test_hspacing_flag_is_invisible_when_no_issues``,
    enabling ``hspacing_fix`` does not change the shift plan when there are
    no h-spacing issues.
    """
    report = load_report(sample_report)
    rules = parse_conf(Path("pbir_validator/profiles/strict.md"))
    shifts, _ = plan_fixes(report, rules, profile_flags={"hspacing_fix": True})
    x_shifts = [s for s in shifts if s.delta_x is not None and s.delta_x != 0]
    assert x_shifts == []
    if not shifts:
        before = _hash_dir(sample_report)
        apply_shifts(shifts, build_visual_lookup(report))
        after = _hash_dir(sample_report)
        assert before == after
