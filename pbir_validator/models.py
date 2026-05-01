"""Frozen dataclass models for pbir_validator.

All entities are immutable; mutation happens only on disk via
``writer.write_visual_json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Row grouping tolerance in PBIR pixel units (FR-007). Two visuals belong to the
# same row when their y coordinates differ by at most this many pixels.
ROW_TOLERANCE_PX: int = 2


@dataclass(frozen=True)
class Report:
    root: Path
    pages_dir: Path


@dataclass(frozen=True)
class Page:
    id: str
    display_name: str
    height: float
    width: float
    path: Path
    visuals_dir: Path


@dataclass(frozen=True)
class Visual:
    id: str
    page_id: str
    visual_type: str
    x: float
    y: float
    width: float
    height: float
    parent_group_name: str | None
    path: Path
    raw: dict[str, Any] = field(hash=False, compare=False)
    indent: int = 2
    trailing_newline: bool = True


@dataclass(frozen=True)
class Row:
    page_id: str
    y_min: float
    y_max: float
    bottom: float
    representative_type: str
    visuals: tuple[Visual, ...]
    is_mixed: bool


@dataclass(frozen=True)
class GapRule:
    from_type: str
    to_type: str
    gap_px: int

    # Equality / hashing keyed on (from_type, to_type) only — gap_px is the value.
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GapRule):
            return NotImplemented
        return (self.from_type, self.to_type) == (other.from_type, other.to_type)

    def __hash__(self) -> int:
        return hash((self.from_type, self.to_type))


@dataclass(frozen=True)
class Violation:
    page_id: str
    page_display_name: str
    from_type: str
    to_type: str
    expected_px: int
    actual_px: float
    deviation_px: float
    from_row_index: int
    to_row_index: int
    unfixable_reason: str | None = None


@dataclass(frozen=True)
class UnknownPair:
    page_id: str
    page_display_name: str
    from_type: str
    to_type: str
    actual_px: float


@dataclass(frozen=True)
class Misalignment:
    """A visual whose ``y`` differs from its row peers (intra-row drift)."""

    page_id: str
    page_display_name: str
    visual_id: str
    visual_type: str
    actual_y: float
    expected_y: float
    deviation_px: float
    row_index: int
    path: Path


@dataclass(frozen=True)
class HSpacingIssue:
    """An inconsistent horizontal gap between same-row, same-type peers.

    Reported when a row has 3+ visuals of the same type laid out side-by-side
    and at least one horizontal gap deviates from the row's modal gap.
    """

    page_id: str
    page_display_name: str
    visual_type: str
    left_visual_id: str
    right_visual_id: str
    expected_gap_px: float
    actual_gap_px: float
    deviation_px: float
    row_index: int


@dataclass(frozen=True)
class Shift:
    visual_id: str
    page_id: str
    path: Path
    old_y: float
    new_y: float
    delta_y: float
    group_member: bool = False
