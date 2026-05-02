"""Severity grade computation for the GUI summary (US4, FR-030/FR-031/FR-033).

Pure-data; no Tk imports. The ``compute`` and ``color_for`` helpers are
exhaustively unit-tested against their boundary cases.
"""

from __future__ import annotations

from typing import Mapping


# Fixed palette per spec FR-033 (I5 remediation).
_COLORS: dict[str, str] = {
    "A": "#1b5e20",  # green
    "B": "#558b2f",  # lime
    "C": "#f9a825",  # amber
    "D": "#ef6c00",  # orange
    "F": "#c62828",  # red
}
_NEUTRAL = "#757575"

# Issue-category weights (FR-030).
_WEIGHTS: dict[str, int] = {
    "gaps": 3,
    "overlaps": 5,
    "duplicate_layers": 4,
    "misalignments": 2,
    "h_spacing": 2,
}


def compute(counts: Mapping[str, int]) -> tuple[str, int]:
    """Return ``(letter, score)`` per FR-030 / FR-031.

    Missing keys default to 0; negative values raise :class:`ValueError`.
    """
    score = 0
    for key, weight in _WEIGHTS.items():
        value = counts.get(key, 0)
        if value < 0:
            raise ValueError(
                f"grade.compute: negative count for {key!r}: {value}"
            )
        score += weight * value
    if score == 0:
        return ("A", 0)
    if score <= 10:
        return ("B", score)
    if score <= 25:
        return ("C", score)
    if score <= 60:
        return ("D", score)
    return ("F", score)


def color_for(letter: str) -> str:
    """Return the Tk color string for a letter grade.

    ``""`` (empty string) means "neutral / no run yet". Pass an empty
    string to retrieve the neutral color; pass a known letter to get
    its palette color. Any unknown non-empty letter raises
    :class:`ValueError`.
    """
    if letter == "":
        return _NEUTRAL
    if letter not in _COLORS:
        raise ValueError(f"grade.color_for: unknown letter {letter!r}")
    return _COLORS[letter]
