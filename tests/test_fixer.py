"""Tests for pbir_validator.fixer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbir_validator.conf import parse_conf
from pbir_validator.fixer import apply_shifts, build_visual_lookup, plan_fixes
from pbir_validator.learner import learn
from pbir_validator.reader import iter_pages, load_report
from pbir_validator.validator import validate_report


def _setup_with_conf(sample_report: Path) -> Path:
    report = load_report(sample_report)
    page_a = next(p for p in iter_pages(report) if p.id == "pageA")
    learn(report, page_a, sample_report / "conf.md", force=True)
    return sample_report / "conf.md"


def test_plan_shifts_lower_row_and_below(sample_report: Path) -> None:
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    shifts, _violations = plan_fixes(report, rules)

    # On pageB: actionButton (y=104), tableEx (y=160), shape1+shape2 (y=372) all
    # shift by -5 so the gap from card row equals 9.
    page_b_shifts = {s.visual_id: s for s in shifts if s.page_id == "pageB"}
    assert page_b_shifts["v02_actionButton"].delta_y == -5
    assert page_b_shifts["v03_tableEx"].delta_y == -5
    assert page_b_shifts["v04_shape1"].delta_y == -5
    assert page_b_shifts["v05_shape2"].delta_y == -5
    assert "v01_card" not in page_b_shifts  # row 1 is unchanged


def test_group_members_marked(sample_report: Path) -> None:
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    shifts, _ = plan_fixes(report, rules)
    page_b_shifts = {s.visual_id: s for s in shifts if s.page_id == "pageB"}
    assert page_b_shifts["v04_shape1"].group_member is True
    assert page_b_shifts["v05_shape2"].group_member is True
    # actionButton has no parentGroupName
    assert page_b_shifts["v02_actionButton"].group_member is False


def test_unfixable_marked_when_off_page(sample_report: Path) -> None:
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    _shifts, violations = plan_fixes(report, rules)
    page_c_violations = [v for v in violations if v.page_id == "pageC"]
    # At least one violation on pageC is unfixable (page boundary).
    assert any(v.unfixable_reason for v in page_c_violations)


def test_apply_shifts_changes_only_y(sample_report: Path) -> None:
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v02_actionButton"
        / "visual.json"
    )
    before = json.loads(target.read_text(encoding="utf-8"))

    shifts, _ = plan_fixes(report, rules)
    lookup = build_visual_lookup(report)
    apply_shifts(shifts, lookup)

    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["position"]["y"] == 99  # was 104, shifted by -5
    # All other top-level keys preserved
    assert after["name"] == before["name"]
    assert after["visual"] == before["visual"]
    assert {k: after["position"][k] for k in after["position"] if k != "y"} == {
        k: before["position"][k] for k in before["position"] if k != "y"
    }


def test_revalidate_after_fix_clean_for_pageb_only(sample_report: Path) -> None:
    """After fixing, pageB has no violations (pageC still does because unfixable)."""
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    shifts, _ = plan_fixes(report, rules)
    lookup = build_visual_lookup(report)
    apply_shifts(shifts, lookup)

    # Re-load and validate
    report2 = load_report(sample_report)
    violations, _, _ = validate_report(report2, rules)
    page_b_violations = [v for v in violations if v.page_id == "pageB"]
    assert page_b_violations == []


def test_dry_run_makes_no_writes(sample_report: Path) -> None:
    """plan_fixes alone (without apply_shifts) doesn't touch any file."""
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    pageb = sample_report / "definition" / "pages" / "pageB"
    mtimes_before = {
        p: p.stat().st_mtime_ns for p in pageb.rglob("visual.json")
    }
    plan_fixes(report, rules)
    mtimes_after = {
        p: p.stat().st_mtime_ns for p in pageb.rglob("visual.json")
    }
    assert mtimes_before == mtimes_after


def test_unfixable_does_not_block_other_pages(sample_report: Path) -> None:
    """Unfixable on pageC must not prevent pageB shifts from being planned."""
    conf = _setup_with_conf(sample_report)
    rules = parse_conf(conf)
    report = load_report(sample_report)
    shifts, _ = plan_fixes(report, rules)
    pageb_shifts = [s for s in shifts if s.page_id == "pageB"]
    assert pageb_shifts  # not empty
