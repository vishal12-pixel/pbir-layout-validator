"""Tests for TabState, sort, filter, duplicate_rows, and context-menu helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pbir_validator.gui import controllers
from pbir_validator.models import DuplicateLayer


# ---------------------------------------------------------------------------
# duplicate_rows
# ---------------------------------------------------------------------------


def test_duplicate_rows_formats_pair_with_titles_and_ids() -> None:
    d = DuplicateLayer(
        page_id="p1",
        page_display_name="Page 1",
        visual_type="pivotTable",
        visual_a_id="vA",
        visual_a_title="Top Visual",
        visual_b_id="vB",
        visual_b_title="",
        delta_y_px=20.3,
    )
    rows = controllers.duplicate_rows([d])
    assert rows == [
        ("Page 1", "pivotTable", "Top Visual (vA)", "vB", 20.3)
    ]


def test_duplicate_rows_handles_empty_list() -> None:
    assert controllers.duplicate_rows([]) == []


# ---------------------------------------------------------------------------
# TabState / set_rows / set_filter / toggle_sort / visible_rows
# ---------------------------------------------------------------------------


def _state() -> controllers.TabState:
    s = controllers.TabState(
        name="t",
        columns=("a", "b", "c"),
        numeric_columns=frozenset({1}),
    )
    controllers.set_rows(
        s,
        [
            ("alpha", 3, "x"),
            ("Beta", 12, "y"),
            ("gamma", -1, "z"),
        ],
    )
    return s


def test_visible_rows_returns_all_when_no_filter_or_sort() -> None:
    s = _state()
    assert controllers.visible_rows(s) == [
        ("alpha", 3, "x"),
        ("Beta", 12, "y"),
        ("gamma", -1, "z"),
    ]


def test_filter_is_case_insensitive_substring_across_columns() -> None:
    s = _state()
    controllers.set_filter(s, "BETA")
    assert controllers.visible_rows(s) == [("Beta", 12, "y")]
    controllers.set_filter(s, "y")  # matches col c
    assert ("Beta", 12, "y") in controllers.visible_rows(s)


def test_sort_text_column_ascending_then_descending() -> None:
    s = _state()
    controllers.toggle_sort(s, 0)  # asc
    rows = controllers.visible_rows(s)
    assert [r[0] for r in rows] == ["alpha", "Beta", "gamma"]
    controllers.toggle_sort(s, 0)  # desc
    rows = controllers.visible_rows(s)
    assert [r[0] for r in rows] == ["gamma", "Beta", "alpha"]


def test_sort_numeric_column_uses_natural_order() -> None:
    s = _state()
    controllers.toggle_sort(s, 1)  # numeric col
    rows = controllers.visible_rows(s)
    assert [r[1] for r in rows] == [-1, 3, 12]


def test_switching_columns_resets_to_ascending() -> None:
    s = _state()
    controllers.toggle_sort(s, 0)
    controllers.toggle_sort(s, 0)  # now desc
    controllers.toggle_sort(s, 1)  # different col → asc
    assert s.sort == (1, False)


def test_set_rows_clears_filter_but_keeps_sort() -> None:
    s = _state()
    controllers.toggle_sort(s, 1)
    controllers.set_filter(s, "alpha")
    assert s.filter_text == "alpha"
    controllers.set_rows(s, [("z", 9, "q")])
    assert s.filter_text == ""
    assert s.sort == (1, False)


# ---------------------------------------------------------------------------
# row_to_clipboard_text
# ---------------------------------------------------------------------------


def test_row_to_clipboard_text_is_tab_separated() -> None:
    assert controllers.row_to_clipboard_text(("a", 1, "b")) == "a\t1\tb"


# ---------------------------------------------------------------------------
# open_in_power_bi
# ---------------------------------------------------------------------------


def test_open_in_power_bi_missing_definition(tmp_path: Path) -> None:
    ok, msg = controllers.open_in_power_bi(tmp_path)
    assert ok is False
    assert "not found" in msg.lower()


def test_open_in_power_bi_calls_startfile(tmp_path: Path) -> None:
    pbir = tmp_path / "definition.pbir"
    pbir.write_text("{}", encoding="utf-8")
    with patch("os.startfile", create=True) as mock_start:
        ok, msg = controllers.open_in_power_bi(tmp_path)
    assert ok is True
    assert msg == ""
    mock_start.assert_called_once_with(str(pbir))


def test_open_in_power_bi_handles_oserror(tmp_path: Path) -> None:
    pbir = tmp_path / "definition.pbir"
    pbir.write_text("{}", encoding="utf-8")
    with patch("os.startfile", create=True, side_effect=OSError("no app")):
        ok, msg = controllers.open_in_power_bi(tmp_path)
    assert ok is False
    assert "could not open" in msg.lower()
