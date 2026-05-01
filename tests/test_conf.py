"""Tests for pbir_validator.conf."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.conf import parse_conf, write_conf
from pbir_validator.errors import ConfParseError
from pbir_validator.models import GapRule


def test_parse_simple_rules(tmp_path: Path) -> None:
    p = tmp_path / "conf.md"
    p.write_text(
        "# header\n"
        "card -> actionButton: 9px\n"
        "actionButton -> tableEx: 16px\n",
        encoding="utf-8",
    )
    rules = parse_conf(p)
    assert rules[("card", "actionButton")].gap_px == 9
    assert rules[("actionButton", "tableEx")].gap_px == 16


def test_parse_whitespace_tolerated(tmp_path: Path) -> None:
    p = tmp_path / "conf.md"
    p.write_text(
        "card    ->    actionButton  :   9px\n",
        encoding="utf-8",
    )
    rules = parse_conf(p)
    assert rules[("card", "actionButton")].gap_px == 9


def test_parse_skips_comments_and_blanks(tmp_path: Path) -> None:
    p = tmp_path / "conf.md"
    p.write_text(
        "# comment\n"
        "\n"
        "card -> shape: 5px\n"
        "    # indented comment treated as comment\n",
        encoding="utf-8",
    )
    rules = parse_conf(p)
    assert len(rules) == 1


def test_parse_malformed_skipped_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "conf.md"
    p.write_text(
        "card -> actionButton: 9px\n"
        "this is not a rule\n",
        encoding="utf-8",
    )
    rules = parse_conf(p)
    assert len(rules) == 1
    err = capsys.readouterr().err
    assert ":2:" in err
    assert "malformed" in err


def test_parse_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfParseError) as exc:
        parse_conf(tmp_path / "nope.md")
    assert "not found" in str(exc.value)


def test_parse_zero_rules_raises(tmp_path: Path) -> None:
    p = tmp_path / "conf.md"
    p.write_text("# only comments\n", encoding="utf-8")
    with pytest.raises(ConfParseError) as exc:
        parse_conf(p)
    assert "no rules" in str(exc.value)


def test_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "conf.md"
    rules = [
        GapRule("card", "actionButton", 9),
        GapRule("actionButton", "tableEx", 16),
    ]
    write_conf(rules, p)
    parsed = parse_conf(p)
    assert parsed[("card", "actionButton")].gap_px == 9
    assert parsed[("actionButton", "tableEx")].gap_px == 16


def test_write_is_deterministic_sorted(tmp_path: Path) -> None:
    p = tmp_path / "conf.md"
    write_conf(
        [
            GapRule("z", "a", 1),
            GapRule("a", "b", 2),
        ],
        p,
    )
    text = p.read_text(encoding="utf-8")
    rules_only = [
        line for line in text.splitlines() if line and not line.startswith("#")
    ]
    # Filter the blank line
    rules_only = [r for r in rules_only if r.strip()]
    assert rules_only == ["a -> b: 2px", "z -> a: 1px"]


def test_duplicate_rule_keeps_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "conf.md"
    p.write_text(
        "card -> shape: 5px\n"
        "card -> shape: 99px\n",
        encoding="utf-8",
    )
    rules = parse_conf(p)
    assert rules[("card", "shape")].gap_px == 5
    assert "duplicate" in capsys.readouterr().err
