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


def _is_same_stack_position(a: Visual, b: Visual) -> bool:
    """True iff ``a`` and ``b`` occupy the same logical slot (bookmark stack).

    Two visuals are considered stacked alternates when:
    * their ``y`` coordinates differ by less than half the smaller height
      (i.e. they're at roughly the same vertical position, not adjacent rows),
      AND
    * their ``x`` ranges overlap by at least 50% of the smaller width (they
      occupy the same horizontal slot, not side-by-side variants).
    """
    min_h = min(a.height, b.height)
    if min_h <= 0:
        return False
    if abs(a.y - b.y) > min_h * 0.5:
        return False

    a_x0, a_x1 = a.x, a.x + a.width
    b_x0, b_x1 = b.x, b.x + b.width
    overlap_w = max(0.0, min(a_x1, b_x1) - max(a_x0, b_x0))
    min_w = min(a.width, b.width)
    if min_w <= 0:
        return False
    return overlap_w >= min_w * 0.5


def dedupe_stacked_visuals(visuals: Iterable[Visual]) -> list[Visual]:
    """Collapse same-type bookmark-stacked visuals into a single representative.

    Power BI reports often stack multiple visuals of the same ``visualType`` at
    the same position so bookmarks/buttons can toggle which one is visible. The
    JSON contains all of them, but only one is shown at a time, so for spacing
    analysis they should count as a single logical visual.

    Two visuals are merged only when they share the same ``visual_type`` AND
    occupy the same logical slot (see :func:`_is_same_stack_position`). From
    each cluster keep the one with the smallest ``y`` (topmost); ties broken by
    smallest ``x`` then by ``id`` for determinism. Visuals with no stack peer
    are passed through unchanged.
    """
    items = list(visuals)
    n = len(items)
    if n < 2:
        return items

    # Group indices by visual_type so we only do O(k²) work within each
    # same-type bucket rather than O(n²) across all visuals on the page.
    by_type: dict[str, list[int]] = {}
    for idx, v in enumerate(items):
        by_type.setdefault(v.visual_type, []).append(idx)

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for type_indices in by_type.values():
        if len(type_indices) < 2:
            continue
        for ai in range(len(type_indices)):
            for bi in range(ai + 1, len(type_indices)):
                i, j = type_indices[ai], type_indices[bi]
                if _is_same_stack_position(items[i], items[j]):
                    union(i, j)

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    kept: list[Visual] = []
    for indices in clusters.values():
        if len(indices) == 1:
            kept.append(items[indices[0]])
        else:
            best = min(indices, key=lambda k: (items[k].y, items[k].x, items[k].id))
            kept.append(items[best])
    return kept


def group_into_rows(visuals: Iterable[Visual]) -> list[Row]:
    """Bucket visuals into rows using the ROW_TOLERANCE_PX greedy strategy.

    Visuals are sorted ascending by ``y``; each visual joins the current row when
    ``abs(v.y - row.y_min) <= ROW_TOLERANCE_PX``, else starts a new row. Returned
    rows are sorted by ``y_min`` ascending.

    Same-type bookmark-stacked visuals are first collapsed via
    :func:`dedupe_stacked_visuals` so hidden alternate layouts don't produce
    spurious row pairs with negative gaps.

    Mixed-type rows emit a single warning each time, naming page id, row Y, and
    the observed type set.
    """
    deduped = dedupe_stacked_visuals(visuals)
    by_y = sorted(deduped, key=lambda v: (v.y, v.x))
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


# Default sub-pixel tolerance for intra-row alignment. Y differences below this
# threshold are considered floating-point noise from Power BI's renderer rather
# than a real misalignment.
DEFAULT_ALIGNMENT_TOLERANCE_PX: float = 0.5


def find_row_misalignments(
    rows: list[Row],
    tolerance_px: float = DEFAULT_ALIGNMENT_TOLERANCE_PX,
) -> list[tuple[int, "Visual", float, float]]:
    """Return visuals whose ``y`` differs from their row's expected ``y``.

    For each row with 2+ visuals, the most common ``y`` value (rounded to the
    nearest pixel) is treated as the row's reference. Any visual deviating from
    that reference by more than ``tolerance_px`` is reported.

    Returns a list of ``(row_index, visual, expected_y, deviation_px)``.
    """
    out: list[tuple[int, Visual, float, float]] = []
    for row_idx, row in enumerate(rows):
        if len(row.visuals) < 2:
            continue
        # Pick the modal y as the row's reference (ties → smallest y).
        y_counts = Counter(round(v.y) for v in row.visuals)
        ref_y_int, _ = sorted(y_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        # Use the actual y closest to the modal int as the precise reference.
        ref_y = min(
            (v.y for v in row.visuals if round(v.y) == ref_y_int),
            key=lambda y: abs(y - ref_y_int),
        )
        for v in row.visuals:
            dev = v.y - ref_y
            if abs(dev) > tolerance_px:
                out.append((row_idx, v, ref_y, dev))
    return out


# Default tolerance for horizontal gap consistency. Gaps within ±this many
# pixels of the row's modal gap are considered the same (sub-pixel rendering
# noise from Power BI).
DEFAULT_HSPACING_TOLERANCE_PX: float = 0.5


def find_row_hspacing_issues(
    rows: list[Row],
    tolerance_px: float = DEFAULT_HSPACING_TOLERANCE_PX,
) -> list[tuple[int, Visual, Visual, float, float]]:
    """Detect inconsistent horizontal gaps among same-type peers in a row.

    For each row containing 3+ visuals of the same ``visual_type``, the visuals
    are sorted by ``x`` and consecutive horizontal gaps are computed as
    ``next.x - (prev.x + prev.width)``. The modal gap (rounded to nearest int)
    is treated as the row's expected horizontal spacing. Any gap deviating by
    more than ``tolerance_px`` is reported.

    Returns ``[(row_index, left_visual, right_visual, expected_gap, deviation), ...]``.
    """
    out: list[tuple[int, Visual, Visual, float, float]] = []
    for row_idx, row in enumerate(rows):
        # Bucket the row's visuals by type; only check buckets with ≥3 peers
        # (need ≥2 gaps to identify a modal pattern).
        by_type: dict[str, list[Visual]] = {}
        for v in row.visuals:
            by_type.setdefault(v.visual_type, []).append(v)

        for vt, peers in by_type.items():
            if len(peers) < 3:
                continue
            peers_sorted = sorted(peers, key=lambda v: v.x)
            gaps: list[tuple[Visual, Visual, float]] = []
            for left, right in zip(peers_sorted, peers_sorted[1:]):
                gap = right.x - (left.x + left.width)
                gaps.append((left, right, gap))
            if not gaps:
                continue

            # Modal gap (rounded to nearest int) wins; ties → smallest gap.
            gap_counts = Counter(round(g) for _, _, g in gaps)
            ref_gap_int, _ = sorted(
                gap_counts.items(), key=lambda kv: (-kv[1], kv[0])
            )[0]
            ref_gap = min(
                (g for _, _, g in gaps if round(g) == ref_gap_int),
                key=lambda g: abs(g - ref_gap_int),
            )
            for left, right, gap in gaps:
                dev = gap - ref_gap
                if abs(dev) > tolerance_px:
                    out.append((row_idx, left, right, ref_gap, dev))
    return out
