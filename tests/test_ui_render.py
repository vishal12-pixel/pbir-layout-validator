"""Extra ui coverage — exercise rendering helpers."""

from __future__ import annotations

import pytest

from pbir_validator import ui
from pbir_validator.models import Shift, UnknownPair, Violation
from pathlib import Path


@pytest.fixture(autouse=True)
def _no_color() -> None:
    ui.disable_color()


def test_header_success_error_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    ui.header("HEAD")
    ui.success("YAY")
    ui.error("BAD")
    out = capsys.readouterr()
    assert "HEAD" in out.out
    assert "YAY" in out.out
    assert "BAD" in out.err


def test_print_violations_table(capsys: pytest.CaptureFixture[str]) -> None:
    v = Violation(
        page_id="p",
        page_display_name="Page 1",
        from_type="card",
        to_type="shape",
        expected_px=10,
        actual_px=12,
        deviation_px=2,
        from_row_index=0,
        to_row_index=1,
    )
    ui.print_violations_table([v])
    out = capsys.readouterr().out
    assert "Page 1" in out
    assert "card" in out
    assert "+2px" in out


def test_print_unknown_pairs(capsys: pytest.CaptureFixture[str]) -> None:
    p = UnknownPair("p", "Page 1", "card", "card", actual_px=15)
    ui.print_unknown_pairs([p])
    assert "card" in capsys.readouterr().out


def test_print_unknown_pairs_empty_no_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ui.print_unknown_pairs([])
    assert capsys.readouterr().out == ""


def test_print_shift_plan_with_group(capsys: pytest.CaptureFixture[str]) -> None:
    s = Shift(
        visual_id="v1",
        page_id="p1",
        path=Path("/x"),
        old_y=10,
        new_y=15,
        delta_y=5,
        group_member=True,
    )
    ui.print_shift_plan([s])
    out = capsys.readouterr().out
    assert "v1" in out
    assert "(group)" in out


def test_print_unfixable(capsys: pytest.CaptureFixture[str]) -> None:
    v = Violation(
        page_id="p",
        page_display_name="Page 1",
        from_type="a",
        to_type="b",
        expected_px=10,
        actual_px=20,
        deviation_px=10,
        from_row_index=0,
        to_row_index=1,
        unfixable_reason="off page",
    )
    ui.print_unfixable([v])
    out = capsys.readouterr().out
    assert "off page" in out


def test_print_unfixable_skips_fixable(capsys: pytest.CaptureFixture[str]) -> None:
    v = Violation(
        page_id="p",
        page_display_name="P",
        from_type="a",
        to_type="b",
        expected_px=1,
        actual_px=2,
        deviation_px=1,
        from_row_index=0,
        to_row_index=1,
    )
    ui.print_unfixable([v])
    assert capsys.readouterr().out == ""
