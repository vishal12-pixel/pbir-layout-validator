"""Pure-Python orchestration for the GUI (testable without Tk).

Each controller wraps the existing ``pbir_validator`` modules so the GUI
performs zero parsing/validation logic itself (FR-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..models import HSpacingIssue, Misalignment, Shift, Violation


class ValidateError(RuntimeError):
    """Raised when validation fails for any reason; carries a readable message."""


class LearnError(RuntimeError):
    """Raised when learn fails for any reason."""


class FixError(RuntimeError):
    """Raised when planning or applying fixes fails."""


@dataclass(frozen=True)
class ValidateResult:
    """Outcome of one Validate run, ready to be displayed on the three tabs."""

    gaps: list[Violation] = field(default_factory=list)
    misalignments: list[Misalignment] = field(default_factory=list)
    h_spacing: list[HSpacingIssue] = field(default_factory=list)


def validate(report_path: Path | str, conf_path: Path | str | None) -> ValidateResult:
    """Run the existing validator against ``report_path`` and return a result.

    The conf.md path defaults to ``<report>/conf.md`` when ``conf_path`` is
    ``None``. Any underlying exception is wrapped in :class:`ValidateError`
    with a readable message that the GUI surfaces via ``widgets.show_error``.
    """
    # Lazy imports keep import-time cheap and avoid pulling parsing modules
    # into the GUI smoke test.
    from ..conf import parse_conf
    from ..errors import ConfParseError, NotAPbirError
    from ..reader import load_report
    from ..validator import validate_report

    try:
        report = load_report(report_path)
    except NotAPbirError as exc:
        raise ValidateError(str(exc)) from exc

    resolved_conf = (
        Path(conf_path) if conf_path is not None else report.root / "conf.md"
    )
    try:
        rules = parse_conf(resolved_conf)
    except ConfParseError as exc:
        raise ValidateError(str(exc)) from exc

    try:
        violations, _unknowns, misalignments, hspacing = validate_report(
            report, rules
        )
    except Exception as exc:  # noqa: BLE001 — present any failure to user
        raise ValidateError(f"validation failed: {exc}") from exc

    return ValidateResult(
        gaps=list(violations),
        misalignments=list(misalignments),
        h_spacing=list(hspacing),
    )


# ---------------------------------------------------------------------------
# Row-builders: turn domain objects into the (header, row-tuple) pairs the
# ResultTable widget expects. Pure functions, exercised by SC-002.
# ---------------------------------------------------------------------------


GAP_COLUMNS: tuple[str, ...] = (
    "page",
    "from",
    "to",
    "expected_px",
    "actual_px",
    "deviation_px",
)


def _label(name: str, type_: str) -> str:
    """Render '<title> (<type>)' if a title exists, else just '<type>'."""
    name = (name or "").strip()
    return f"{name} ({type_})" if name else type_


def gap_rows(violations: list[Violation]) -> list[tuple[object, ...]]:
    return [
        (
            v.page_display_name,
            _label(v.from_name, v.from_type),
            _label(v.to_name, v.to_type),
            v.expected_px,
            v.actual_px,
            v.deviation_px,
        )
        for v in violations
    ]


MISALIGNMENT_COLUMNS: tuple[str, ...] = (
    "page",
    "row_index",
    "visual_id",
    "visual_type",
    "expected_y",
    "actual_y",
    "deviation_px",
)


def misalignment_rows(
    misalignments: list[Misalignment],
) -> list[tuple[object, ...]]:
    return [
        (
            m.page_display_name,
            m.row_index,
            m.visual_id,
            m.visual_type,
            m.expected_y,
            m.actual_y,
            m.deviation_px,
        )
        for m in misalignments
    ]


HSPACING_COLUMNS: tuple[str, ...] = (
    "page",
    "row_index",
    "visual_type",
    "left_visual_id",
    "right_visual_id",
    "expected_gap_px",
    "actual_gap_px",
    "deviation_px",
)


def h_spacing_rows(
    issues: list[HSpacingIssue],
) -> list[tuple[object, ...]]:
    return [
        (
            h.page_display_name,
            h.row_index,
            h.visual_type,
            h.left_visual_id,
            h.right_visual_id,
            h.expected_gap_px,
            h.actual_gap_px,
            h.deviation_px,
        )
        for h in issues
    ]


# ---------------------------------------------------------------------------
# Learn (US2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearnResult:
    conf_path: Path
    rule_count: int  # 0 for "manual" mode
    mode: Literal["manual", "auto"]


def list_pages(report_path: Path | str) -> list[tuple[str, str]]:
    """Return ``[(display_name, page_id), ...]`` for the Learn dropdown."""
    from ..errors import NotAPbirError
    from ..learner import list_pages as _list
    from ..reader import load_report

    try:
        report = load_report(report_path)
    except NotAPbirError as exc:
        raise LearnError(str(exc)) from exc
    return [(p.display_name, p.id) for p in _list(report)]


def learn(
    report_path: Path | str,
    conf_path: Path | str,
    mode: Literal["manual", "auto"],
    page_id: str | None,
) -> LearnResult:
    """Run Learn for the GUI.

    - ``mode="manual"``: do not regenerate ``conf.md``; just return its path.
      The caller is responsible for opening it in the OS editor.
    - ``mode="auto"``: invoke the existing :func:`pbir_validator.learner.learn`
      against ``page_id`` and return how many rules were written.
    """
    from ..errors import NotAPbirError
    from ..learner import learn as _learn
    from ..reader import load_report

    if mode == "manual":
        return LearnResult(conf_path=Path(conf_path), rule_count=0, mode="manual")

    if page_id is None:
        raise LearnError("auto mode requires a page_id")

    try:
        report = load_report(report_path)
    except NotAPbirError as exc:
        raise LearnError(str(exc)) from exc

    page = next((p for p in report_pages(report) if p.id == page_id), None)
    if page is None:
        raise LearnError(f"page id not found: {page_id}")

    out = Path(conf_path)
    try:
        result = _learn(report, page, out, force=True)
    except Exception as exc:  # noqa: BLE001
        raise LearnError(f"learn failed: {exc}") from exc

    if result is None:
        raise LearnError("learn produced no rules (page needs >= 2 rows of visuals)")

    # rule_count: re-parse to count
    from ..conf import parse_conf

    rules = parse_conf(out)
    return LearnResult(conf_path=out, rule_count=len(rules), mode="auto")


def report_pages(report):
    """Tiny wrapper for the unit tests."""
    from ..reader import iter_pages

    return list(iter_pages(report))


# ---------------------------------------------------------------------------
# Fix (US3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedShift:
    """One row in the Fix Plan tab. ``id`` is stable across the dry-run session."""

    id: str
    shift: Shift


@dataclass(frozen=True)
class FixPlan:
    shifts: list[ProposedShift] = field(default_factory=list)
    summary: str = ""
    unfixable: list[Violation] = field(default_factory=list)


FIX_PLAN_COLUMNS: tuple[str, ...] = (
    "page_id",
    "visual_id",
    "old_y",
    "new_y",
    "delta_y",
    "group_member",
)


def fix_plan_rows(plan: FixPlan) -> list[tuple[object, ...]]:
    return [
        (
            ps.shift.page_id,
            ps.shift.visual_id,
            ps.shift.old_y,
            ps.shift.new_y,
            ps.shift.delta_y,
            "yes" if ps.shift.group_member else "no",
        )
        for ps in plan.shifts
    ]


def fix_plan(report_path: Path | str, conf_path: Path | str | None) -> FixPlan:
    """Run the fixer in dry-run mode and return a :class:`FixPlan`."""
    from ..conf import parse_conf
    from ..errors import ConfParseError, NotAPbirError
    from ..fixer import plan_fixes
    from ..reader import load_report

    try:
        report = load_report(report_path)
    except NotAPbirError as exc:
        raise FixError(str(exc)) from exc

    resolved_conf = (
        Path(conf_path) if conf_path is not None else report.root / "conf.md"
    )
    try:
        rules = parse_conf(resolved_conf)
    except ConfParseError as exc:
        raise FixError(str(exc)) from exc

    try:
        shifts, violations = plan_fixes(report, rules)
    except Exception as exc:  # noqa: BLE001
        raise FixError(f"fix planning failed: {exc}") from exc

    proposed = [
        ProposedShift(id=f"{s.page_id}::{s.visual_id}::{i}", shift=s)
        for i, s in enumerate(shifts)
    ]
    unfixable = [v for v in violations if v.unfixable_reason]
    summary = (
        f"{len(proposed)} proposed shift(s); "
        f"{len(unfixable)} unfixable; "
        f"all rows pre-checked"
    )
    return FixPlan(shifts=proposed, summary=summary, unfixable=unfixable)


def fix_apply(
    report_path: Path | str,
    plan: FixPlan,
    selected_ids: set[str],
) -> int:
    """Apply only the shifts whose ``id`` is in ``selected_ids``.

    Returns the number of shifts written. Raises :class:`FixError` when
    ``selected_ids`` is empty or any underlying write fails.
    """
    if not selected_ids:
        raise FixError("no shifts selected")

    from ..errors import NotAPbirError, WriteError
    from ..fixer import apply_shifts, build_visual_lookup
    from ..reader import load_report

    try:
        report = load_report(report_path)
    except NotAPbirError as exc:
        raise FixError(str(exc)) from exc

    chosen = [ps.shift for ps in plan.shifts if ps.id in selected_ids]
    if not chosen:
        raise FixError("selected_ids matched no proposed shifts")

    lookup = build_visual_lookup(report)
    try:
        apply_shifts(chosen, lookup)
    except WriteError as exc:
        raise FixError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise FixError(f"apply failed: {exc}") from exc
    return len(chosen)
