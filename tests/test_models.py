"""Tests for pbir_validator.models — frozen dataclass invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.models import (
    GapRule,
    Page,
    Report,
    ROW_TOLERANCE_PX,
    Shift,
    UnknownPair,
    Violation,
    Visual,
)


def test_row_tolerance_is_two_pixels() -> None:
    assert ROW_TOLERANCE_PX == 2


def test_report_is_frozen(tmp_path: Path) -> None:
    r = Report(root=tmp_path, pages_dir=tmp_path / "definition" / "pages")
    with pytest.raises(Exception):
        r.root = tmp_path / "other"  # type: ignore[misc]


def test_visual_is_frozen(tmp_path: Path) -> None:
    v = Visual(
        id="v1",
        page_id="p1",
        visual_type="card",
        x=1.0,
        y=2.0,
        width=10.0,
        height=20.0,
        parent_group_name=None,
        path=tmp_path / "visual.json",
        raw={"a": 1},
        indent=2,
    )
    with pytest.raises(Exception):
        v.y = 99  # type: ignore[misc]


def test_gap_rule_equality_keyed_on_pair_only() -> None:
    a = GapRule("card", "actionButton", 9)
    b = GapRule("card", "actionButton", 11)
    c = GapRule("card", "tableEx", 9)
    assert a == b  # gap_px ignored for equality
    assert hash(a) == hash(b)
    assert a != c


def test_gap_rule_can_be_dict_key() -> None:
    rules: dict[GapRule, int] = {}
    rules[GapRule("card", "actionButton", 9)] = 9
    rules[GapRule("card", "actionButton", 11)] = 11
    # Same hash → second insert overwrites first
    assert len(rules) == 1


def test_violation_defaults_unfixable_reason_none() -> None:
    v = Violation(
        page_id="p",
        page_display_name="P",
        from_type="a",
        to_type="b",
        expected_px=10,
        actual_px=12,
        deviation_px=2,
        from_row_index=0,
        to_row_index=1,
    )
    assert v.unfixable_reason is None


def test_unknown_pair_holds_actual() -> None:
    p = UnknownPair("p", "Page 1", "card", "card", actual_px=15)
    assert p.actual_px == 15


def test_shift_delta_field(tmp_path: Path) -> None:
    s = Shift(
        visual_id="v1",
        page_id="p1",
        path=tmp_path / "v.json",
        old_y=10.0,
        new_y=14.0,
        delta_y=4.0,
    )
    assert s.delta_y == 4.0
    assert s.group_member is False


def test_page_basic(tmp_path: Path) -> None:
    p = Page(
        id="p1",
        display_name="Page 1",
        height=720,
        width=1280,
        path=tmp_path,
        visuals_dir=tmp_path / "visuals",
    )
    assert p.display_name == "Page 1"
