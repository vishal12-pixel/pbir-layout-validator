"""Row grouping and gap computation."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from . import ui
from .models import ROW_TOLERANCE_PX, Row, Visual


def pick_representative_type(visuals: Iterable[Visual]) -> tuple[str, bool]:
    """Return ``(representative_type, is_mixed)``.

    Most-frequent type wins; ties broken lexicographically (deterministic).
    """
    types = [v.visual_type for v in visuals]
    if not types:
        return ("unknown", False)
    counts = Counter(types)
    is_mixed = len(counts) > 1
    # Sort by (-count, type) so ties go to lex-smallest type name.
    best_type, _ = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return (best_type, is_mixed)


def group_into_rows(visuals: Iterable[Visual]) -> list[Row]:
    """Bucket visuals into rows using the ROW_TOLERANCE_PX greedy strategy.

    Visuals are sorted ascending by ``y``; each visual joins the current row when
    ``abs(v.y - row.y_min) <= ROW_TOLERANCE_PX``, else starts a new row. Returned
    rows are sorted by ``y_min`` ascending.

    Mixed-type rows emit a single warning each time, naming page id, row Y, and
    the observed type set.
    """
    by_y = sorted(visuals, key=lambda v: (v.y, v.x))
    if not by_y:
        return []

    buckets: list[list[Visual]] = []
    current: list[Visual] = [by_y[0]]
    current_y_min = by_y[0].y
    for v in by_y[1:]:
        if abs(v.y - current_y_min) <= ROW_TOLERANCE_PX:
            current.append(v)
        else:
            buckets.append(current)
            current = [v]
            current_y_min = v.y
    buckets.append(current)

    rows: list[Row] = []
    for bucket in buckets:
        bucket_sorted = sorted(bucket, key=lambda v: v.x)
        y_min = min(v.y for v in bucket_sorted)
        y_max = max(v.y for v in bucket_sorted)
        bottom = max(v.y + v.height for v in bucket_sorted)
        repr_type, is_mixed = pick_representative_type(bucket_sorted)
        if is_mixed:
            page_id = bucket_sorted[0].page_id
            seen = sorted({v.visual_type for v in bucket_sorted})
            ui.warn(
                f"mixed-type row on page '{page_id}' at y={y_min:g}: "
                f"types={seen}, using representative '{repr_type}'"
            )
        rows.append(
            Row(
                page_id=bucket_sorted[0].page_id,
                y_min=y_min,
                y_max=y_max,
                bottom=bottom,
                representative_type=repr_type,
                visuals=tuple(bucket_sorted),
                is_mixed=is_mixed,
            )
        )
    rows.sort(key=lambda r: r.y_min)
    return rows


def compute_gaps(rows: list[Row]) -> list[tuple[Row, Row, float]]:
    """Yield ``(upper, lower, gap_px)`` for each adjacent row pair."""
    out: list[tuple[Row, Row, float]] = []
    for upper, lower in zip(rows, rows[1:]):
        out.append((upper, lower, lower.y_min - upper.bottom))
    return out
