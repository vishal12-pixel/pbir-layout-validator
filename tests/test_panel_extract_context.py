"""Tests for ``panel.extract_visual_context`` and ``panel.find_visual_for_row`` (T027)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pbir_validator.gui import controllers, panel


@dataclass
class _FakeVisual:
    id: str
    page_id: str
    visual_type: str
    x: float
    y: float
    width: float
    height: float
    parent_group_name: str | None
    raw: dict[str, Any]
    page_display_name: str = ""


def _make(id: str = "v1") -> _FakeVisual:
    return _FakeVisual(
        id=id,
        page_id="p1",
        visual_type="card",
        x=10,
        y=20,
        width=100,
        height=50,
        parent_group_name="grp1",
        raw={"id": id, "name": "Test", "position": {"x": 10, "y": 20}},
        page_display_name="Page One",
    )


def test_extract_visual_context_returns_required_keys() -> None:
    v = _make()
    ctx = panel.extract_visual_context(v)
    assert set(ctx.keys()) == {
        "id",
        "page_id",
        "page_display_name",
        "visual_type",
        "x",
        "y",
        "width",
        "height",
        "parent_group",
        "raw_json",
    }


def test_extract_visual_context_raw_json_is_pretty_printed() -> None:
    import json

    v = _make()
    ctx = panel.extract_visual_context(v)
    assert ctx["raw_json"] == json.dumps(v.raw, indent=2, ensure_ascii=False)


def test_extract_visual_context_unicode_preserved() -> None:
    v = _make()
    v.raw["title"] = "café"
    ctx = panel.extract_visual_context(v)
    assert "café" in ctx["raw_json"]


def test_find_visual_for_row_pair_for_overlap() -> None:
    rows = [("Page", "card-a", "card-b", 5)]
    cols = controllers.OVERLAP_COLUMNS
    visuals = {"card-a": _make("card-a"), "card-b": _make("card-b")}
    found = panel.find_visual_for_row(rows, 0, cols, visuals)
    assert len(found) == 2
    assert found[0].id == "card-a"
    assert found[1].id == "card-b"


def test_find_visual_for_row_pair_for_misalignment() -> None:
    """I1 fix: misalignment rows should resolve via single visual_id column."""
    rows = [("Page", 0, "v1", "card", 100, 105, 5)]
    cols = controllers.MISALIGNMENT_COLUMNS
    visuals = {"v1": _make("v1")}
    found = panel.find_visual_for_row(rows, 0, cols, visuals)
    assert len(found) >= 1
    assert found[0].id == "v1"


def test_find_visual_for_row_two_for_h_spacing() -> None:
    rows = [("Page", 0, "card", "card-a", "card-b", 8, 16, 8)]
    cols = controllers.HSPACING_COLUMNS
    visuals = {"card-a": _make("card-a"), "card-b": _make("card-b")}
    found = panel.find_visual_for_row(rows, 0, cols, visuals)
    assert len(found) == 2


def test_find_visual_for_row_two_for_duplicate_pair() -> None:
    rows = [("Page", "card", "Title (card-a)", "Title (card-b)", 0)]
    cols = controllers.DUPLICATE_COLUMNS
    visuals = {"card-a": _make("card-a"), "card-b": _make("card-b")}
    found = panel.find_visual_for_row(rows, 0, cols, visuals)
    assert len(found) == 2
    assert {f.id for f in found} == {"card-a", "card-b"}


def test_find_visual_for_row_returns_empty_when_no_id_resolves() -> None:
    rows = [("Page", "missing-a", "missing-b", 0)]
    cols = controllers.OVERLAP_COLUMNS
    found = panel.find_visual_for_row(rows, 0, cols, {})
    assert found == []


def test_find_visual_for_row_out_of_range() -> None:
    rows: list[tuple[object, ...]] = []
    found = panel.find_visual_for_row(rows, 0, ("a",), {})
    assert found == []


def test_find_visual_for_row_negative_idx() -> None:
    rows = [("a",)]
    found = panel.find_visual_for_row(rows, -1, ("a",), {})
    assert found == []


def test_extract_visual_context_handles_missing_attributes() -> None:
    """Robust against duck-typed visuals lacking some fields."""

    class Bare:
        id = "x"
        raw: dict[str, Any] = {}

    ctx = panel.extract_visual_context(Bare())
    assert ctx["id"] == "x"
    assert ctx["raw_json"] == "{}"


def test_extract_visual_context_unserializable_raw_falls_back_to_repr() -> None:
    class Bare:
        id = "x"
        raw = {"unhashable": object()}  # not JSON-serializable

    ctx = panel.extract_visual_context(Bare())
    # Either repr-style or empty-dict-ish; just verify it's a string.
    assert isinstance(ctx["raw_json"], str)
