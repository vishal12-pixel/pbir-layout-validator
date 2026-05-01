"""Fix-mode logic: plan and apply Y-coordinate shifts.

For each violation, shift the lower row (and every row below it on the same
page) by the deviation. When any visual being shifted has a ``parent_group_name``,
every other visual on the page sharing that group name is shifted by the same
delta — even if it's in a row that wouldn't otherwise move (per FR-025).

Page-boundary refusal: if the resulting ``y + height`` would exceed the page's
height, the violation is marked unfixable and **no shifts** are emitted for it.
Other violations on the same page are still planned.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from . import ui
from .analyzer import compute_gaps, group_into_rows
from .errors import WriteError
from .models import GapRule, Page, Report, Shift, Violation
from .reader import iter_pages, iter_visuals
from .validator import validate_report
from .writer import write_visual_json


def plan_fixes(
    report: Report,
    rules: dict[tuple[str, str], GapRule],
) -> tuple[list[Shift], list[Violation]]:
    """Plan all shifts for ``report`` against ``rules``.

    Returns ``(shifts, violations)`` where each ``Violation`` may have
    ``unfixable_reason`` set when its planned shift would push a visual past
    the page boundary.
    """
    all_shifts: list[Shift] = []
    final_violations: list[Violation] = []

    # Build a per-page map for boundary checks and group lookups.
    pages_by_id: dict[str, Page] = {p.id: p for p in iter_pages(report)}
    visuals_by_page: dict[str, list] = {}
    for page in pages_by_id.values():
        visuals_by_page[page.id] = list(iter_visuals(page))

    violations, _unknowns, misalignments = validate_report(report, rules)
    by_page: dict[str, list[Violation]] = defaultdict(list)
    for v in violations:
        by_page[v.page_id].append(v)

    # Pre-compute per-page misalignment shifts: each misaligned visual gets a
    # delta to bring it to its row's expected y. These deltas are applied
    # before gap fixes so subsequent gap calculations see the aligned layout.
    misalign_deltas_by_page: dict[str, dict[str, float]] = defaultdict(dict)
    for m in misalignments:
        misalign_deltas_by_page[m.page_id][m.visual_id] = m.expected_y - m.actual_y

    for page_id, page_violations in by_page.items():
        page = pages_by_id.get(page_id)
        if page is None:
            continue
        page_visuals = visuals_by_page.get(page_id, [])
        rows = group_into_rows(page_visuals)
        if len(rows) < 2:
            for v in page_violations:
                final_violations.append(v)
            continue

        # Per-visual cumulative delta on this page. Seed with misalignment
        # corrections so individual visuals are nudged onto their row's Y.
        deltas: dict[str, float] = {v.id: 0.0 for v in page_visuals}
        for vid, d in misalign_deltas_by_page.get(page_id, {}).items():
            if vid in deltas:
                deltas[vid] = d

        # Group membership map (page-local).
        groups: dict[str, list[str]] = defaultdict(list)
        for v in page_visuals:
            if v.parent_group_name:
                groups[v.parent_group_name].append(v.id)

        # Sort violations by from_row_index ascending so each violation operates
        # on the freshly shifted layout from prior violations on the same page.
        page_violations.sort(key=lambda v: v.from_row_index)
        page_unfixable: list[Violation] = []
        page_resolved: list[Violation] = []

        for viol in page_violations:
            # Lower row plus every row below it = rows[viol.to_row_index:].
            # Identify visuals to shift in this step.
            shift_visual_ids: set[str] = set()
            for row in rows[viol.to_row_index:]:
                for v in row.visuals:
                    shift_visual_ids.add(v.id)

            # Group expansion: if any shifted visual belongs to a group, every
            # other group member on this page is also shifted.
            for v in page_visuals:
                if v.id in shift_visual_ids and v.parent_group_name:
                    for sibling_id in groups.get(v.parent_group_name, []):
                        shift_visual_ids.add(sibling_id)

            # The required delta for this violation: actual=expected+dev →
            # we want to bring actual to expected → shift lower row by -dev.
            # If actual > expected (dev>0), gap is too big → shift up (delta<0).
            # If actual < expected (dev<0), gap is too small → shift down (delta>0).
            step_delta = -viol.deviation_px

            # Boundary check: would any shifted visual go past page bounds?
            unfixable_reason: str | None = None
            if page.height > 0:
                for v in page_visuals:
                    if v.id not in shift_visual_ids:
                        continue
                    new_y = v.y + deltas[v.id] + step_delta
                    if new_y < 0:
                        unfixable_reason = (
                            f"shift would push '{v.id}' past top "
                            f"(y={new_y:g})"
                        )
                        break
                    if new_y + v.height > page.height:
                        unfixable_reason = (
                            f"shift would push '{v.id}' past page bottom "
                            f"({new_y + v.height:g} > {page.height:g})"
                        )
                        break

            if unfixable_reason is not None:
                page_unfixable.append(
                    Violation(
                        **{**viol.__dict__, "unfixable_reason": unfixable_reason}
                    )
                )
                continue

            # Apply the step delta to cumulative per-visual deltas.
            for vid in shift_visual_ids:
                deltas[vid] = deltas[vid] + step_delta
            page_resolved.append(viol)

        # Emit shifts for every visual whose cumulative delta != 0.
        page_shifts: list[Shift] = []
        for v in page_visuals:
            d = deltas[v.id]
            if d == 0:
                continue
            new_y = v.y + d
            page_shifts.append(
                Shift(
                    visual_id=v.id,
                    page_id=page.id,
                    path=v.path,
                    old_y=v.y,
                    new_y=new_y,
                    delta_y=d,
                    group_member=v.parent_group_name is not None,
                )
            )
        all_shifts.extend(page_shifts)
        final_violations.extend(page_resolved)
        final_violations.extend(page_unfixable)

    # Also include violations on pages with no shifts planned (e.g., trivial pages).
    seen_page_ids = set(by_page.keys())
    for v in violations:
        if v.page_id not in seen_page_ids:
            final_violations.append(v)

    # Plan misalignment-only shifts for pages with no gap violations.
    for page_id, vid_to_delta in misalign_deltas_by_page.items():
        if page_id in seen_page_ids:
            continue  # already handled above
        page = pages_by_id.get(page_id)
        if page is None:
            continue
        for v in visuals_by_page.get(page_id, []):
            d = vid_to_delta.get(v.id, 0.0)
            if d == 0:
                continue
            new_y = v.y + d
            all_shifts.append(
                Shift(
                    visual_id=v.id,
                    page_id=page.id,
                    path=v.path,
                    old_y=v.y,
                    new_y=new_y,
                    delta_y=d,
                    group_member=v.parent_group_name is not None,
                )
            )

    return all_shifts, final_violations


def apply_shifts(shifts: Iterable[Shift], visual_lookup: dict[Path, object]) -> None:
    """Apply each shift via :func:`writer.write_visual_json`.

    ``visual_lookup`` maps each shift's path to its original :class:`Visual`,
    needed because the writer mutates a copy of ``visual.raw``.
    """
    for s in shifts:
        v = visual_lookup.get(s.path)
        if v is None:
            raise WriteError(
                f"no Visual found for shift target {s.path}", path=s.path
            )
        write_visual_json(v, s.new_y)  # type: ignore[arg-type]


def build_visual_lookup(report: Report) -> dict[Path, object]:
    """Build a ``{visual.path: Visual}`` map for the entire report."""
    lookup: dict[Path, object] = {}
    for page in iter_pages(report):
        for v in iter_visuals(page):
            lookup[v.path] = v
    return lookup
