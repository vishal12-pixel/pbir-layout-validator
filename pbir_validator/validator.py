"""Validate-mode logic: compare every adjacent-row gap against rules."""

from __future__ import annotations

from .analyzer import (
    compute_gaps,
    find_row_hspacing_issues,
    find_row_misalignments,
    group_into_rows,
)
from .models import (
    GapRule,
    HSpacingIssue,
    Misalignment,
    Report,
    UnknownPair,
    Violation,
)
from .reader import iter_pages, iter_visuals


def validate_report(
    report: Report,
    rules: dict[tuple[str, str], GapRule],
) -> tuple[
    list[Violation], list[UnknownPair], list[Misalignment], list[HSpacingIssue]
]:
    """Walk every page and compare adjacent-row gaps to ``rules``.

    Returns ``(violations, unknowns, misalignments, hspacing_issues)``.

    * ``violations``     -- adjacent-row vertical gap mismatches.
    * ``unknowns``       -- adjacent-row pairs with no rule (warnings only).
    * ``misalignments``  -- visuals whose Y drifts from row peers.
    * ``hspacing_issues`` -- inconsistent horizontal gaps among same-type
      peers within a row (e.g., 6 slicers with one gap off by 2px).
    """
    violations: list[Violation] = []
    unknowns: list[UnknownPair] = []
    misalignments: list[Misalignment] = []
    hspacing_issues: list[HSpacingIssue] = []

    for page in iter_pages(report):
        visuals = list(iter_visuals(page))
        rows = group_into_rows(visuals)
        if not rows:
            continue

        for row_idx, visual, expected_y, dev in find_row_misalignments(rows):
            misalignments.append(
                Misalignment(
                    page_id=page.id,
                    page_display_name=page.display_name,
                    visual_id=visual.id,
                    visual_type=visual.visual_type,
                    actual_y=visual.y,
                    expected_y=expected_y,
                    deviation_px=dev,
                    row_index=row_idx,
                    path=visual.path,
                )
            )

        for row_idx, left, right, ref_gap, dev in find_row_hspacing_issues(rows):
            hspacing_issues.append(
                HSpacingIssue(
                    page_id=page.id,
                    page_display_name=page.display_name,
                    visual_type=left.visual_type,
                    left_visual_id=left.id,
                    right_visual_id=right.id,
                    expected_gap_px=ref_gap,
                    actual_gap_px=ref_gap + dev,
                    deviation_px=dev,
                    row_index=row_idx,
                )
            )

        if len(rows) < 2:
            continue

        for i, (upper, lower, gap) in enumerate(compute_gaps(rows)):
            key = (upper.representative_type, lower.representative_type)
            rule = rules.get(key)
            if rule is None:
                unknowns.append(
                    UnknownPair(
                        page_id=page.id,
                        page_display_name=page.display_name,
                        from_type=upper.representative_type,
                        to_type=lower.representative_type,
                        actual_px=gap,
                    )
                )
                continue
            if int(round(gap)) != rule.gap_px:
                violations.append(
                    Violation(
                        page_id=page.id,
                        page_display_name=page.display_name,
                        from_type=upper.representative_type,
                        to_type=lower.representative_type,
                        expected_px=rule.gap_px,
                        actual_px=gap,
                        deviation_px=gap - rule.gap_px,
                        from_row_index=i,
                        to_row_index=i + 1,
                    )
                )

    return violations, unknowns, misalignments, hspacing_issues
