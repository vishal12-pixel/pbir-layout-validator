"""Validate-mode logic: compare every adjacent-row gap against rules."""

from __future__ import annotations

from .analyzer import compute_gaps, group_into_rows
from .models import GapRule, Report, UnknownPair, Violation
from .reader import iter_pages, iter_visuals


def validate_report(
    report: Report,
    rules: dict[tuple[str, str], GapRule],
) -> tuple[list[Violation], list[UnknownPair]]:
    """Walk every page and compare adjacent-row gaps to ``rules``.

    Pages with 0 or 1 row pass trivially (no adjacent pairs). Returns a list of
    violations (rule mismatch) and a separate list of unknown pairs (no rule
    found). Unknown pairs are warnings, not violations.
    """
    violations: list[Violation] = []
    unknowns: list[UnknownPair] = []

    for page in iter_pages(report):
        visuals = list(iter_visuals(page))
        rows = group_into_rows(visuals)
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

    return violations, unknowns
