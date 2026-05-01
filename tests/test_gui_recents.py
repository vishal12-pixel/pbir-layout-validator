"""Tests for the recents MRU store (US6, T039-T041)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbir_validator.gui import recents


@pytest.fixture(autouse=True)
def _isolated_recents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect recents to a temp directory for every test."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_load_returns_empty_when_missing() -> None:
    assert recents.load() == []


def test_record_creates_file_and_returns_single_entry() -> None:
    result = recents.record(r"C:\reports\foo.Report")
    assert result == [r"C:\reports\foo.Report"]
    assert recents.load() == [r"C:\reports\foo.Report"]


def test_record_pushes_existing_entry_to_front() -> None:
    recents.record("a")
    recents.record("b")
    recents.record("c")
    assert recents.load() == ["c", "b", "a"]
    # touching "a" again moves it to the front
    recents.record("a")
    assert recents.load() == ["a", "c", "b"]


def test_record_truncates_to_max_5() -> None:
    for ch in "abcdefg":
        recents.record(ch)
    out = recents.load()
    assert len(out) == 5
    assert out[0] == "g"  # most-recent first


def test_record_dedupes_when_pushing_existing() -> None:
    recents.record("x")
    recents.record("y")
    recents.record("x")
    out = recents.load()
    assert out == ["x", "y"]
    assert out.count("x") == 1


def test_load_returns_empty_on_corrupt_json() -> None:
    target = recents.recents_path()
    target.write_text("{this is not valid json", encoding="utf-8")
    assert recents.load() == []


def test_load_returns_empty_on_unexpected_shape() -> None:
    target = recents.recents_path()
    target.write_text(json.dumps(["a", "b", "c"]), encoding="utf-8")
    assert recents.load() == []


def test_load_filters_non_string_entries() -> None:
    target = recents.recents_path()
    target.write_text(
        json.dumps({"recent": ["good", 123, None, "", "also-good"]}),
        encoding="utf-8",
    )
    assert recents.load() == ["good", "also-good"]


def test_record_empty_path_is_noop() -> None:
    recents.record("first")
    out = recents.record("")
    assert out == ["first"]


def test_recents_path_uses_xdg_on_posix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import sys as _sys

    if _sys.platform == "win32":
        pytest.skip("POSIX-only path resolution")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = recents.recents_path()
    assert str(p).startswith(str(tmp_path))
    assert p.name == "recents.json"
