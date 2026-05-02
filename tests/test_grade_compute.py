"""Tests for ``grade.compute`` and ``grade.color_for`` (T023)."""

from __future__ import annotations

import pytest

from pbir_validator.gui import grade


def test_zero_counts_returns_a() -> None:
    assert grade.compute({}) == ("A", 0)
    assert grade.compute(
        {"gaps": 0, "overlaps": 0, "duplicate_layers": 0, "misalignments": 0, "h_spacing": 0}
    ) == ("A", 0)


def test_score_boundaries() -> None:
    # score=0 -> A
    assert grade.compute({"gaps": 0})[0] == "A"
    # score=1 (1*gaps_weight not possible; smallest positive is gaps=1 -> 3)
    # boundary 1..10 -> B
    assert grade.compute({"misalignments": 1})[0] == "B"  # score=2
    assert grade.compute({"gaps": 1})[0] == "B"  # score=3
    assert grade.compute({"gaps": 3, "misalignments": 0})[0] == "B"  # score=9
    assert grade.compute({"misalignments": 5})[0] == "B"  # score=10
    # 11..25 -> C
    assert grade.compute({"misalignments": 6})[0] == "C"  # score=12
    assert grade.compute({"overlaps": 5})[0] == "C"  # score=25
    # 26..60 -> D
    assert grade.compute({"overlaps": 6})[0] == "D"  # score=30
    assert grade.compute({"overlaps": 12})[0] == "D"  # score=60
    # >=61 -> F
    assert grade.compute({"overlaps": 13})[0] == "F"  # score=65


def test_negative_count_raises_value_error() -> None:
    with pytest.raises(ValueError):
        grade.compute({"gaps": -1})


def test_color_for_each_letter() -> None:
    assert grade.color_for("A") == "#1b5e20"
    assert grade.color_for("B") == "#558b2f"
    assert grade.color_for("C") == "#f9a825"
    assert grade.color_for("D") == "#ef6c00"
    assert grade.color_for("F") == "#c62828"


def test_color_for_neutral_empty_string() -> None:
    assert grade.color_for("") == "#757575"


def test_color_for_unknown_raises() -> None:
    with pytest.raises(ValueError):
        grade.color_for("Z")


def test_score_formula_weights() -> None:
    # 3*1 + 5*2 + 4*1 + 2*1 + 2*1 = 3+10+4+2+2 = 21 -> C
    letter, score = grade.compute(
        {
            "gaps": 1,
            "overlaps": 2,
            "duplicate_layers": 1,
            "misalignments": 1,
            "h_spacing": 1,
        }
    )
    assert score == 21
    assert letter == "C"
