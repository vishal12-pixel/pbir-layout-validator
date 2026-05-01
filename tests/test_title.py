"""Tests for pbir_validator.title — extract user-facing title from raw visual JSON."""

from __future__ import annotations

from pathlib import Path

from pbir_validator.models import Visual
from pbir_validator.title import _unwrap_literal, extract_title, row_title


def _make_visual(raw: dict) -> Visual:
    return Visual(
        id="v1",
        page_id="p1",
        visual_type="card",
        x=0,
        y=0,
        width=100,
        height=50,
        parent_group_name=None,
        path=Path("dummy"),
        raw=raw,
    )


def _title_raw(value: str) -> dict:
    return {
        "visualContainerObjects": {
            "title": [
                {
                    "properties": {
                        "text": {
                            "expr": {"Literal": {"Value": value}},
                        },
                    },
                },
            ],
        },
    }


def test_unwrap_literal_strips_outer_quotes() -> None:
    assert _unwrap_literal("'Hello'") == "Hello"


def test_unwrap_literal_unescapes_doubled_quotes() -> None:
    assert _unwrap_literal("'It''s mine'") == "It's mine"


def test_unwrap_literal_handles_non_string() -> None:
    assert _unwrap_literal(None) == ""
    assert _unwrap_literal(42) == ""
    assert _unwrap_literal("x") == ""  # too short, no quotes


def test_unwrap_literal_returns_unquoted_as_is() -> None:
    assert _unwrap_literal("plain") == "plain"


def test_extract_title_happy_path() -> None:
    v = _make_visual(_title_raw("'Net Seat Adds'"))
    assert extract_title(v) == "Net Seat Adds"


def test_extract_title_missing_container() -> None:
    assert extract_title(_make_visual({})) == ""


def test_extract_title_malformed_each_layer() -> None:
    # title not a list
    assert extract_title(_make_visual({"visualContainerObjects": {"title": {}}})) == ""
    # empty title list
    assert extract_title(_make_visual({"visualContainerObjects": {"title": []}})) == ""
    # title entry not a dict
    assert (
        extract_title(_make_visual({"visualContainerObjects": {"title": ["x"]}})) == ""
    )
    # missing properties
    assert (
        extract_title(_make_visual({"visualContainerObjects": {"title": [{}]}})) == ""
    )
    # text not a dict
    assert (
        extract_title(
            _make_visual(
                {"visualContainerObjects": {"title": [{"properties": {"text": "x"}}]}}
            )
        )
        == ""
    )
    # expr not a dict
    assert (
        extract_title(
            _make_visual(
                {
                    "visualContainerObjects": {
                        "title": [{"properties": {"text": {"expr": "x"}}}]
                    }
                }
            )
        )
        == ""
    )
    # Literal not a dict
    assert (
        extract_title(
            _make_visual(
                {
                    "visualContainerObjects": {
                        "title": [
                            {"properties": {"text": {"expr": {"Literal": "x"}}}}
                        ]
                    }
                }
            )
        )
        == ""
    )


def test_extract_title_non_dict_raw() -> None:
    v = Visual(
        id="v1",
        page_id="p1",
        visual_type="card",
        x=0,
        y=0,
        width=100,
        height=50,
        parent_group_name=None,
        path=Path("dummy"),
        raw="not a dict",  # type: ignore[arg-type]
    )
    assert extract_title(v) == ""


def test_row_title_joins_unique() -> None:
    v1 = _make_visual(_title_raw("'A'"))
    v2 = _make_visual(_title_raw("'B'"))
    v3 = _make_visual(_title_raw("'A'"))  # duplicate
    assert row_title((v1, v2, v3)) == "A, B"


def test_row_title_skips_empty_titles() -> None:
    v1 = _make_visual(_title_raw("'A'"))
    v2 = _make_visual({})
    assert row_title((v1, v2)) == "A"


def test_row_title_empty_when_no_titles() -> None:
    assert row_title((_make_visual({}), _make_visual({}))) == ""
