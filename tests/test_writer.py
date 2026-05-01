"""Tests for pbir_validator.writer — atomic write preserves all unrelated keys."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from pbir_validator.errors import WriteError
from pbir_validator.reader import parse_visual
from pbir_validator.writer import write_visual_json


def test_round_trip_preserves_keys_order_indent(sample_report: Path) -> None:
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageA"
        / "visuals"
        / "v01_card"
        / "visual.json"
    )
    original_text = target.read_text(encoding="utf-8")
    original_data = json.loads(original_text)

    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    write_visual_json(visual, new_y=42)
    new_text = target.read_text(encoding="utf-8")
    new_data = json.loads(new_text)

    # Only position.y changed
    assert new_data["position"]["y"] == 42
    new_data["position"]["y"] = original_data["position"]["y"]
    assert new_data == original_data

    # Trailing newline preserved
    assert new_text.endswith("\n") == original_text.endswith("\n")
    # Indentation preserved (sniffed indent=2 in fixture)
    assert "  \"position\"" in new_text


def test_write_preserves_top_level_key_order(sample_report: Path) -> None:
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v04_shape1"
        / "visual.json"
    )
    original_keys = list(json.loads(target.read_text(encoding="utf-8")).keys())
    visual = parse_visual(target, page_id="pageB")
    assert visual is not None
    write_visual_json(visual, new_y=370)
    new_keys = list(json.loads(target.read_text(encoding="utf-8")).keys())
    assert new_keys == original_keys


def test_write_failure_raises_writeerror(sample_report: Path) -> None:
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageA"
        / "visuals"
        / "v01_card"
        / "visual.json"
    )
    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    with mock.patch("pbir_validator.writer.os.replace", side_effect=OSError("boom")):
        with pytest.raises(WriteError) as excinfo:
            write_visual_json(visual, new_y=99)
    assert "boom" in str(excinfo.value)
    # Original file untouched
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["position"]["y"] == 10  # unchanged


def test_failed_write_leaves_no_temp_file(sample_report: Path) -> None:
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageA"
        / "visuals"
        / "v01_card"
        / "visual.json"
    )
    visual = parse_visual(target, page_id="pageA")
    assert visual is not None

    with mock.patch("pbir_validator.writer.os.replace", side_effect=OSError("nope")):
        with pytest.raises(WriteError):
            write_visual_json(visual, new_y=99)

    # No leftover .tmp-pbir-* sibling
    leftovers = list(target.parent.glob(".tmp-pbir-*"))
    assert leftovers == []
