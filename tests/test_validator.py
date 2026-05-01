"""Tests for pbir_validator.validator."""

from __future__ import annotations

from pathlib import Path

from pbir_validator.conf import parse_conf
from pbir_validator.learner import learn
from pbir_validator.reader import iter_pages, load_report
from pbir_validator.validator import validate_report


def _learn_from_a(sample_report: Path) -> dict:
    report = load_report(sample_report)
    page_a = next(p for p in iter_pages(report) if p.id == "pageA")
    learn(report, page_a, sample_report / "conf.md", force=True)
    return parse_conf(sample_report / "conf.md")


def test_clean_page_a_passes(sample_report: Path) -> None:
    """If we point validate at a report whose only page is pageA, no violations."""
    rules = _learn_from_a(sample_report)
    # Hide pageB and pageC by renaming
    pages_dir = sample_report / "definition" / "pages"
    (pages_dir / "pageB").rename(pages_dir / "_pageB_hidden_subdir")
    (pages_dir / "_pageB_hidden_subdir" / "page.json").unlink()  # invalidate
    (pages_dir / "pageC").rename(pages_dir / "_pageC_hidden_subdir")
    (pages_dir / "_pageC_hidden_subdir" / "page.json").unlink()
    report = load_report(sample_report)
    violations, unknowns, _ = validate_report(report, rules)
    assert violations == []
    assert unknowns == []


def test_pageb_violation_detected(sample_report: Path) -> None:
    rules = _learn_from_a(sample_report)
    report = load_report(sample_report)
    violations, _, _ = validate_report(report, rules)
    page_b_violations = [v for v in violations if v.page_id == "pageB"]
    assert len(page_b_violations) == 1
    v = page_b_violations[0]
    assert v.from_type == "card"
    assert v.to_type == "actionButton"
    assert v.expected_px == 9
    assert v.actual_px == 14
    assert v.deviation_px == 5


def test_unknown_pair_does_not_count_as_violation(
    sample_report: Path, tmp_path: Path
) -> None:
    """Custom rules that don't cover all pairs → unknowns reported separately."""
    conf = sample_report / "conf.md"
    conf.write_text(
        "# only one rule\n"
        "card -> actionButton: 9px\n",
        encoding="utf-8",
    )
    rules = parse_conf(conf)
    report = load_report(sample_report)
    violations, unknowns, _ = validate_report(report, rules)
    # All non-(card→actionButton) pairs become unknowns
    assert any(
        u.from_type == "actionButton" and u.to_type == "tableEx" for u in unknowns
    )
    # unfixable_reason is left None on freshly produced violations
    for v in violations:
        assert v.unfixable_reason is None


def test_zero_visual_page_passes(sample_report: Path) -> None:
    """An empty page contributes no violations."""
    empty = sample_report / "definition" / "pages" / "pageEmpty"
    empty.mkdir()
    (empty / "page.json").write_text(
        '{"name":"pageEmpty","displayName":"Empty","height":720,"width":1280}',
        encoding="utf-8",
    )
    rules = _learn_from_a(sample_report)
    report = load_report(sample_report)
    violations, unknowns, _ = validate_report(report, rules)
    assert all(v.page_id != "pageEmpty" for v in violations)
    assert all(u.page_id != "pageEmpty" for u in unknowns)


def test_validate_does_not_mutate_files(sample_report: Path) -> None:
    """Validate is read-only."""
    rules = _learn_from_a(sample_report)
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v02_actionButton"
        / "visual.json"
    )
    before = target.stat().st_mtime_ns
    before_text = target.read_text(encoding="utf-8")
    report = load_report(sample_report)
    validate_report(report, rules)
    after = target.stat().st_mtime_ns
    after_text = target.read_text(encoding="utf-8")
    assert before == after
    assert before_text == after_text
