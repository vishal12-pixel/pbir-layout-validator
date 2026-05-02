"""Side-panel context extraction (US5, FR-040..FR-044).

Tk-free; the GUI in :mod:`pbir_validator.gui.app` handles the actual
``ttk.PanedWindow`` and read-only ``Text`` widget rendering. This module
turns a ``Visual`` into a plain dict and resolves which visual(s) a
result-row references.
"""

from __future__ import annotations

import json
from typing import Mapping, Sequence


def extract_visual_context(visual) -> dict:
    """Return a Tk-free dict describing ``visual``.

    Keys: ``id``, ``page_id``, ``page_display_name``, ``visual_type``,
    ``x``, ``y``, ``width``, ``height``, ``parent_group``, ``raw_json``.

    ``raw_json`` is the visual's raw payload re-serialized with
    ``json.dumps(indent=2, ensure_ascii=False)`` for the read-only Text
    widget (FR-041). ``page_display_name`` defaults to the page id when
    a Visual instance does not carry it (it doesn't on
    :class:`pbir_validator.models.Visual`).
    """
    raw = getattr(visual, "raw", None) or {}
    try:
        raw_json = json.dumps(raw, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        raw_json = repr(raw)
    return {
        "id": getattr(visual, "id", ""),
        "page_id": getattr(visual, "page_id", ""),
        "page_display_name": getattr(visual, "page_display_name", "")
        or getattr(visual, "page_id", ""),
        "visual_type": getattr(visual, "visual_type", ""),
        "x": getattr(visual, "x", 0),
        "y": getattr(visual, "y", 0),
        "width": getattr(visual, "width", 0),
        "height": getattr(visual, "height", 0),
        "parent_group": getattr(visual, "parent_group_name", None),
        "raw_json": raw_json,
    }


# Columns in result rows that may carry a visual id. Multiple keys are
# tried in order; the first that resolves wins. The two-visual rules
# below override the single-visual fallback when applicable.
_SINGLE_ID_COLUMNS: tuple[str, ...] = ("visual_id",)
_PAIR_LEFT_COLUMNS: tuple[str, ...] = (
    "left_visual_id",
    "visual_a",
    "from",
    "upper",
)
_PAIR_RIGHT_COLUMNS: tuple[str, ...] = (
    "right_visual_id",
    "visual_b",
    "to",
    "lower",
)


def _candidates(value: object) -> list[str]:
    """Return possible identifier strings extracted from a label cell.

    Result-table cells use ``"<title> (<id-or-type>)"`` formatting via
    :func:`pbir_validator.gui.controllers._label`. We try the bare value,
    the part before the parens (label), and the part inside the parens
    (id-or-type) so resolution works for both single-id and pair rows.
    """
    s = str(value or "").strip()
    out: list[str] = []
    if not s:
        return out
    out.append(s)
    if s.endswith(")") and "(" in s:
        inside = s[s.rfind("(") + 1 : -1].strip()
        outside = s[: s.rfind("(")].strip()
        if inside:
            out.append(inside)
        if outside:
            out.append(outside)
    return out


def _resolve(token: object, visuals_by_id: Mapping[str, object]):
    for cand in _candidates(token):
        if cand in visuals_by_id:
            return visuals_by_id[cand]
    return None


def find_visual_for_row(
    rows: Sequence[Sequence[object]],
    idx: int,
    columns: Sequence[str],
    visuals_by_id: Mapping[str, object],
) -> list:
    """Return the visual(s) referenced by ``rows[idx]``.

    Returns 2 visuals for two-visual rows (overlaps, misalignments,
    h-spacing, duplicate-pair rows) and 1 visual for single-id rows.
    Returns ``[]`` if no referenced id resolves.
    """
    if idx < 0 or idx >= len(rows):
        return []
    row = rows[idx]
    cols = tuple(columns)

    found_left: object | None = None
    found_right: object | None = None
    for col_name in _PAIR_LEFT_COLUMNS:
        if col_name in cols:
            i = cols.index(col_name)
            if i < len(row):
                found_left = _resolve(row[i], visuals_by_id)
                break
    for col_name in _PAIR_RIGHT_COLUMNS:
        if col_name in cols:
            i = cols.index(col_name)
            if i < len(row):
                found_right = _resolve(row[i], visuals_by_id)
                break

    if found_left is not None and found_right is not None:
        return [found_left, found_right]

    # Misalignment table is single-id but per spec FR-042 "I1 fix" we still
    # return TWO visuals: the misaligned one + a row-mate proxy when
    # available. When there is no proxy we fall back to single.
    for col_name in _SINGLE_ID_COLUMNS:
        if col_name in cols:
            i = cols.index(col_name)
            if i < len(row):
                v = _resolve(row[i], visuals_by_id)
                if v is not None:
                    return [v]
    return []
