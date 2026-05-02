"""Tests for new keys ``side_panel_visible`` + ``profile`` in recents (T007)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbir_validator.gui import recents


@pytest.fixture(autouse=True)
def _isolated_recents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_load_state_defaults_when_missing() -> None:
    state = recents.load_state()
    assert state == {
        "recent": [],
        "side_panel_visible": True,
        "profile": "Standard",
    }


def test_load_state_round_trips_extra_keys() -> None:
    target = recents.recents_path()
    target.write_text(
        json.dumps(
            {
                "recent": ["a", "b"],
                "side_panel_visible": False,
                "profile": "Strict",
            }
        ),
        encoding="utf-8",
    )
    state = recents.load_state()
    assert state["recent"] == ["a", "b"]
    assert state["side_panel_visible"] is False
    assert state["profile"] == "Strict"


def test_load_state_legacy_file_uses_defaults() -> None:
    """A 004-era recents file lacking the new keys still loads cleanly."""
    target = recents.recents_path()
    target.write_text(json.dumps({"recent": ["a"]}), encoding="utf-8")
    state = recents.load_state()
    assert state["recent"] == ["a"]
    assert state["side_panel_visible"] is True
    assert state["profile"] == "Standard"


def test_record_persists_session_keys() -> None:
    recents.record(side_panel_visible=False, profile="Strict")
    state = recents.load_state()
    assert state["side_panel_visible"] is False
    assert state["profile"] == "Strict"


def test_record_with_only_path_keeps_legacy_return_shape() -> None:
    """Returns the MRU list (not the full dict) when no kwargs are given."""
    out = recents.record("some/path")
    assert out == ["some/path"]


def test_record_with_kwargs_returns_full_state() -> None:
    out = recents.record(side_panel_visible=False)
    assert isinstance(out, dict)
    assert out["side_panel_visible"] is False


def test_record_combined_path_and_kwargs() -> None:
    recents.record("first", profile="Relaxed")
    state = recents.load_state()
    assert state["recent"] == ["first"]
    assert state["profile"] == "Relaxed"


def test_load_paths_returns_only_mru_list() -> None:
    recents.record("a")
    recents.record("b", side_panel_visible=False)
    assert recents.load_paths() == ["b", "a"]
    # load_paths must NOT leak the dict shape
    assert isinstance(recents.load_paths(), list)


def test_invalid_session_values_fall_back_to_defaults() -> None:
    target = recents.recents_path()
    target.write_text(
        json.dumps(
            {"recent": [], "side_panel_visible": "yes", "profile": ""}
        ),
        encoding="utf-8",
    )
    state = recents.load_state()
    assert state["side_panel_visible"] is True
    assert state["profile"] == "Standard"
