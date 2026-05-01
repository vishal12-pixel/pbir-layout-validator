"""Tests for pbir_validator.learner."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.conf import parse_conf
from pbir_validator.learner import derive_rules, learn
from pbir_validator.reader import iter_pages, iter_visuals, load_report


def _page_a(report_path: Path):
    report = load_report(report_path)
    return report, next(p for p in iter_pages(report) if p.id == "pageA")


def test_learn_writes_expected_rules(sample_report: Path) -> None:
    report, page = _page_a(sample_report)
    out = sample_report / "conf.md"
    learn(report, page, out, force=True)
    rules = parse_conf(out)
    assert rules[("card", "actionButton")].gap_px == 9
    assert rules[("actionButton", "tableEx")].gap_px == 16
    assert rules[("tableEx", "shape")].gap_px == 12


def test_derive_rules_handles_conflict(
    sample_report: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two card->actionButton row pairs with different gaps -> conflict warning."""
    from pbir_validator.models import Visual

    report, page = _page_a(sample_report)

    def mk(vid: str, vt: str, x: float, y: float, h: float = 50) -> Visual:
        return Visual(
            id=vid,
            page_id=page.id,
            visual_type=vt,
            x=x,
            y=y,
            width=100,
            height=h,
            parent_group_name=None,
            path=Path(f"/syn/{vid}"),
            raw={},
            indent=2,
        )

    # Two adjacent card->actionButton row pairs with different gaps.
    visuals = [
        # First pair: gap 9
        mk("c1", "card", 0, 0, h=10),
        mk("b1", "actionButton", 0, 19, h=10),
        # Second pair: gap 11 (different from 9 -> conflict)
        mk("c2", "card", 0, 100, h=10),
        mk("b2", "actionButton", 0, 121, h=10),
    ]

    rules, warnings = derive_rules(page, visuals)
    pairs = {(r.from_type, r.to_type): r.gap_px for r in rules}
    # Both gaps freq=1 -> ties broken by smallest -> 9.
    assert pairs[("card", "actionButton")] == 9
    assert any("conflicting gaps" in w for w in warnings)


def test_learn_overwrite_protection(sample_report: Path) -> None:
    report, page = _page_a(sample_report)
    out = sample_report / "conf.md"
    out.write_text("# pre-existing\nfoo -> bar: 1px\n", encoding="utf-8")
    # Without force and no input → should not overwrite (input EOFs to default=False)
    result = learn(report, page, out, force=False)
    assert result is None
    assert "pre-existing" in out.read_text(encoding="utf-8")


def test_learn_force_overwrites(sample_report: Path) -> None:
    report, page = _page_a(sample_report)
    out = sample_report / "conf.md"
    out.write_text("# pre-existing\n", encoding="utf-8")
    result = learn(report, page, out, force=True)
    assert result == out
    text = out.read_text(encoding="utf-8")
    assert "card -> actionButton: 9px" in text
