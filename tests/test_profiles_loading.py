"""Tests for ``profiles.list_profiles`` and ``profiles.load_profile`` (T033)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.gui import profiles


def test_list_profiles_default_three_keys() -> None:
    out = profiles.list_profiles(None)
    assert list(out.keys()) == ["Standard", "Strict", "Relaxed"]
    for path in out.values():
        assert path.is_file()


def test_list_profiles_adds_report_default_when_conf_md_exists(
    tmp_path: Path,
) -> None:
    (tmp_path / "conf.md").write_text("card -> card: 8px\n", encoding="utf-8")
    out = profiles.list_profiles(tmp_path)
    assert list(out.keys()) == ["Standard", "Strict", "Relaxed", "Report-default"]
    assert out["Report-default"] == tmp_path / "conf.md"


def test_list_profiles_no_report_default_when_conf_missing(tmp_path: Path) -> None:
    out = profiles.list_profiles(tmp_path)
    assert "Report-default" not in out


def test_load_profile_standard_gap_8() -> None:
    rules = profiles.load_profile("Standard")
    # At least one rule encodes the Standard gap of 8 px.
    assert any(rule.gap_px == 8 for rule in rules.values())


def test_load_profile_strict_halves_to_4() -> None:
    rules = profiles.load_profile("Strict")
    # Strict halves Standard tolerances; every rule's gap_px must be 4.
    assert all(rule.gap_px == 4 for rule in rules.values())


def test_load_profile_relaxed_doubles_to_16() -> None:
    rules = profiles.load_profile("Relaxed")
    assert all(rule.gap_px == 16 for rule in rules.values())


def test_load_profile_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        profiles.load_profile("DoesNotExist")


def test_load_profile_report_default_uses_report_root(tmp_path: Path) -> None:
    (tmp_path / "conf.md").write_text("card -> card: 7px\n", encoding="utf-8")
    rules = profiles.load_profile("Report-default", tmp_path)
    # Project-default conf has gap_px=7
    assert rules[("card", "card")].gap_px == 7
