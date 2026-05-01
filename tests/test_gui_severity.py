"""Tests for the pure severity-band classifier (US5)."""

from __future__ import annotations

import pytest

from pbir_validator.gui import severity


class TestDeviation:
    def test_zero_is_green(self) -> None:
        assert severity.band(0, kind="deviation") == severity.SEV_GREEN

    def test_under_two_is_green(self) -> None:
        assert severity.band(1.999, kind="deviation") == severity.SEV_GREEN
        assert severity.band(-1.999, kind="deviation") == severity.SEV_GREEN

    def test_at_two_is_green(self) -> None:
        assert severity.band(2.0, kind="deviation") == severity.SEV_GREEN
        assert severity.band(-2.0, kind="deviation") == severity.SEV_GREEN

    def test_under_ten_is_yellow(self) -> None:
        assert severity.band(9.99, kind="deviation") == severity.SEV_YELLOW
        assert severity.band(-9.99, kind="deviation") == severity.SEV_YELLOW

    def test_at_ten_is_yellow(self) -> None:
        assert severity.band(10.0, kind="deviation") == severity.SEV_YELLOW
        assert severity.band(-10.0, kind="deviation") == severity.SEV_YELLOW
        assert severity.band(50, kind="deviation") == severity.SEV_RED


class TestOverlap:
    def test_zero_is_green(self) -> None:
        assert severity.band(0, kind="overlap") == severity.SEV_GREEN

    def test_positive_under_50_is_yellow(self) -> None:
        assert severity.band(1, kind="overlap") == severity.SEV_YELLOW
        assert severity.band(49, kind="overlap") == severity.SEV_YELLOW
        assert severity.band(50, kind="overlap") == severity.SEV_YELLOW

    def test_above_50_is_red(self) -> None:
        assert severity.band(50.01, kind="overlap") == severity.SEV_RED
        assert severity.band(120, kind="overlap") == severity.SEV_RED


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValueError):
        severity.band(0, kind="bogus")  # type: ignore[arg-type]
