"""Tests for write_visual_json with the optional new_x kwarg (T020, FR-003/004/014/015)."""

from __future__ import annotations

import json
from pathlib import Path

from pbir_validator.reader import parse_visual
from pbir_validator.writer import write_visual_json


def _v01_path(report: Path) -> Path:
    return (
        report
        / "definition"
        / "pages"
        / "pageA"
        / "visuals"
        / "v01_card"
        / "visual.json"
    )


def test_new_x_only_mutates_x_and_y(sample_report: Path) -> None:
    """Passing new_x writes both x and y in one call (FR-003, FR-004)."""
    target = _v01_path(sample_report)
    original = json.loads(target.read_text(encoding="utf-8"))

    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    write_visual_json(visual, new_y=visual.y, new_x=99)
    after = json.loads(target.read_text(encoding="utf-8"))

    assert after["position"]["x"] == 99
    assert after["position"]["y"] == original["position"]["y"]
    # Every other position key must survive untouched.
    after["position"]["x"] = original["position"]["x"]
    assert after == original


def test_new_x_none_is_byte_identical_to_y_only_call(sample_report: Path) -> None:
    """new_x=None must produce the exact same output as not passing new_x (FR-013)."""
    target = _v01_path(sample_report)
    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    # Capture canonical y-only output.
    write_visual_json(visual, new_y=42)
    bytes_y_only = target.read_bytes()

    # Restore and re-write with new_x=None — must be identical.
    visual2 = parse_visual(target, page_id="pageA")
    assert visual2 is not None
    write_visual_json(visual2, new_y=42, new_x=None)
    bytes_with_kw = target.read_bytes()

    assert bytes_with_kw == bytes_y_only


def test_new_x_preserves_int_ness(sample_report: Path) -> None:
    """An integral new_x must serialize as int, not float (FR-014)."""
    target = _v01_path(sample_report)
    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    write_visual_json(visual, new_y=visual.y, new_x=200.0)
    text = target.read_text(encoding="utf-8")

    # No "200.0" should appear; integer literal should be written.
    assert '"x": 200' in text
    assert '"x": 200.0' not in text


def test_combined_x_and_y_write(sample_report: Path) -> None:
    """When both kwargs are provided, both coordinates are mutated atomically."""
    target = _v01_path(sample_report)
    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    write_visual_json(visual, new_y=77, new_x=88)
    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["position"]["x"] == 88
    assert after["position"]["y"] == 77


def test_new_x_preserves_key_order_and_indent(sample_report: Path) -> None:
    """Top-level and position-level key order survive an X+Y write (FR-014)."""
    target = _v01_path(sample_report)
    original = json.loads(target.read_text(encoding="utf-8"))
    original_top_keys = list(original.keys())
    original_pos_keys = list(original["position"].keys())

    visual = parse_visual(target, page_id="pageA")
    assert visual is not None
    write_visual_json(visual, new_y=visual.y, new_x=visual.x + 5)

    after_text = target.read_text(encoding="utf-8")
    after = json.loads(after_text)
    assert list(after.keys()) == original_top_keys
    assert list(after["position"].keys()) == original_pos_keys
    assert after_text.endswith("\n")
    # Indentation preserved (visual fixture uses indent=2).
    assert "  \"position\"" in after_text


def test_new_x_round_trip_byte_conservative(sample_report: Path) -> None:
    """Writing new_x then writing back the original restores semantic content.

    The writer normalizes line endings to LF (pre-feature behavior), so this
    test compares parsed JSON + key order rather than raw bytes — matching
    the existing ``test_round_trip_preserves_keys_order_indent`` contract.
    """
    target = _v01_path(sample_report)
    original_data = json.loads(target.read_text(encoding="utf-8"))
    original_top_keys = list(original_data.keys())
    original_pos_keys = list(original_data["position"].keys())

    visual = parse_visual(target, page_id="pageA")
    assert visual is not None
    original_x = visual.x
    original_y = visual.y

    # First write: a normalizing pass (LF, no key reorder) that becomes the new baseline.
    write_visual_json(visual, new_y=original_y, new_x=original_x)
    baseline_bytes = target.read_bytes()
    baseline_data = json.loads(target.read_text(encoding="utf-8"))
    assert baseline_data == original_data
    assert list(baseline_data.keys()) == original_top_keys
    assert list(baseline_data["position"].keys()) == original_pos_keys

    # Mutate.
    visual2 = parse_visual(target, page_id="pageA")
    assert visual2 is not None
    write_visual_json(visual2, new_y=original_y, new_x=original_x + 5)
    assert target.read_bytes() != baseline_bytes

    # Restore — should be byte-identical to the post-normalization baseline.
    visual3 = parse_visual(target, page_id="pageA")
    assert visual3 is not None
    write_visual_json(visual3, new_y=original_y, new_x=original_x)
    assert target.read_bytes() == baseline_bytes
