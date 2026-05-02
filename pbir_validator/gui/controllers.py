"""Pure-Python orchestration for the GUI (testable without Tk).

Each controller wraps the existing ``pbir_validator`` modules so the GUI
performs zero parsing/validation logic itself (FR-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, Sequence

from ..models import DuplicateLayer, GapRule, HSpacingIssue, Misalignment, Shift, Violation


class ValidateError(RuntimeError):
    """Raised when validation fails for any reason; carries a readable message."""


class LearnError(RuntimeError):
    """Raised when learn fails for any reason."""


class FixError(RuntimeError):
    """Raised when planning or applying fixes fails."""


@dataclass(frozen=True)
class ValidateResult:
    """Outcome of one Validate run, ready to be displayed on the four tabs.

    ``gaps`` holds true gap violations (positive ``actual_px``: real whitespace
    that drifts from the rule). ``overlaps`` holds entries where ``actual_px``
    is negative — the lower visual's top edge sits *above* the upper visual's
    bottom edge — which represents a layered/overlapping pair, not a gap.
    Surfacing them on a separate tab keeps the Gap Violations table free of
    confusing negative values.
    """

    gaps: list[Violation] = field(default_factory=list)
    overlaps: list[Violation] = field(default_factory=list)
    duplicate_layers: list[DuplicateLayer] = field(default_factory=list)
    misalignments: list[Misalignment] = field(default_factory=list)
    h_spacing: list[HSpacingIssue] = field(default_factory=list)


def _split_gaps_and_overlaps(
    violations: list[Violation],
) -> tuple[list[Violation], list[Violation]]:
    """Partition validator output: positive ``actual_px`` are gaps, negative
    are overlaps. Zero counts as a gap (visuals exactly touching)."""
    gaps: list[Violation] = []
    overlaps: list[Violation] = []
    for v in violations:
        if v.actual_px < 0:
            overlaps.append(v)
        else:
            gaps.append(v)
    return gaps, overlaps


def validate(
    report_path: Path | str,
    conf_path: Path | str | None,
    *,
    rules: Mapping[tuple[str, str], GapRule] | None = None,
) -> ValidateResult:
    """Run the existing validator against ``report_path`` and return a result.

    The conf.md path defaults to ``<report>/conf.md`` when ``conf_path`` is
    ``None``. When ``rules`` is provided, ``conf_path`` is ignored entirely
    (no disk lookup) — used by the profile dropdown (US6) to swap rule
    sources without touching the user's working tree. Any underlying
    exception is wrapped in :class:`ValidateError` with a readable message
    that the GUI surfaces via ``widgets.show_error``.
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

    if rules is not None:
        resolved_rules: Mapping[tuple[str, str], GapRule] = rules
    else:
        resolved_conf = (
            Path(conf_path) if conf_path is not None else report.root / "conf.md"
        )
        try:
            resolved_rules = parse_conf(resolved_conf)
        except ConfParseError as exc:
            raise ValidateError(str(exc)) from exc

    try:
        violations, _unknowns, misalignments, hspacing, duplicate_layers = (
            validate_report(report, resolved_rules)
        )
    except Exception as exc:  # noqa: BLE001 — present any failure to user
        raise ValidateError(f"validation failed: {exc}") from exc

    gaps, overlaps = _split_gaps_and_overlaps(list(violations))
    return ValidateResult(
        gaps=gaps,
        overlaps=overlaps,
        duplicate_layers=list(duplicate_layers),
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


OVERLAP_COLUMNS: tuple[str, ...] = (
    "page",
    "upper",
    "lower",
    "overlap_px",
)


def overlap_rows(violations: list[Violation]) -> list[tuple[object, ...]]:
    """Render rows where the lower visual's top sits above the upper's bottom.

    ``overlap_px`` is reported as a positive number (= -actual_px) so users
    don't see negative pixel values in the table. Sorted by overlap size
    (largest first) to surface the worst layering issues at the top.
    """
    rows = [
        (
            v.page_display_name,
            _label(v.from_name, v.from_type),
            _label(v.to_name, v.to_type),
            -v.actual_px,
        )
        for v in violations
    ]
    rows.sort(key=lambda r: r[3], reverse=True)
    return rows


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
# Duplicate Layer (US1, FR-003a)
# ---------------------------------------------------------------------------

DUPLICATE_COLUMNS: tuple[str, ...] = (
    "page",
    "visual_type",
    "visual_a",
    "visual_b",
    "delta_y_px",
)


def duplicate_rows(
    duplicates: list[DuplicateLayer],
) -> list[tuple[object, ...]]:
    return [
        (
            d.page_display_name,
            d.visual_type,
            _label(d.visual_a_title, d.visual_a_id),
            _label(d.visual_b_title, d.visual_b_id),
            d.delta_y_px,
        )
        for d in duplicates
    ]


# ---------------------------------------------------------------------------
# Per-tab sort/filter state (US3, US4)
# ---------------------------------------------------------------------------


@dataclass
class TabState:
    """Source-of-truth row list plus current sort/filter for one result tab."""

    name: str
    columns: tuple[str, ...]
    numeric_columns: frozenset[int] = field(default_factory=frozenset)
    rows: list[tuple[object, ...]] = field(default_factory=list)
    sort: tuple[int, bool] | None = None  # (column_index, descending)
    filter_text: str = ""


def set_rows(state: TabState, rows: list[tuple[object, ...]]) -> None:
    """Replace ``state.rows``; clear filter (FR-013); preserve sort (FR-013a)."""
    state.rows = list(rows)
    state.filter_text = ""


def set_filter(state: TabState, text: str) -> None:
    """Set ``state.filter_text`` (lower-cased)."""
    state.filter_text = (text or "").lower()


def toggle_sort(state: TabState, col: int) -> None:
    """Cycle this column's sort: None → asc → desc → asc → ...

    Selecting a different column resets to ascending on that column.
    """
    if state.sort is None or state.sort[0] != col:
        state.sort = (col, False)
        return
    _, descending = state.sort
    state.sort = (col, not descending)


def _numeric_key(cell: object) -> float:
    try:
        return float(cell)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("inf")


def visible_rows(state: TabState) -> list[tuple[object, ...]]:
    """Return rows after filter-then-sort (FR-012). Pure: no state mutation."""
    needle = state.filter_text
    if needle:
        rows = [
            r
            for r in state.rows
            if any(needle in str(cell).lower() for cell in r)
        ]
    else:
        rows = list(state.rows)
    if state.sort is None:
        return rows
    col, descending = state.sort
    if col in state.numeric_columns:
        rows.sort(key=lambda r, c=col: _numeric_key(r[c]), reverse=descending)
    else:
        rows.sort(
            key=lambda r, c=col: str(r[c]).lower(), reverse=descending
        )
    return rows


# ---------------------------------------------------------------------------
# Right-click context-menu helpers (US2)
# ---------------------------------------------------------------------------


def open_in_power_bi(report_root: Path | str) -> tuple[bool, str]:
    """Launch Power BI Desktop on ``<report_root>/definition.pbir``.

    Returns ``(True, "")`` on success, ``(False, message)`` on failure
    (missing file, no association, OS error). Never raises.
    """
    import os

    target = Path(report_root) / "definition.pbir"
    if not target.is_file():
        return (False, f"definition.pbir not found at: {target}")
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
    except OSError as exc:
        return (False, f"could not open {target}: {exc}")
    except AttributeError:
        # POSIX (non-Windows) — os.startfile doesn't exist there.
        return (False, "open-in-Power BI is supported on Windows only")
    return (True, "")


def row_to_clipboard_text(cells: tuple[object, ...]) -> str:
    """Render a Treeview row as tab-separated text for clipboard paste."""
    return "\t".join(str(c) for c in cells)


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
    "action",
    "old_y",
    "new_y",
    "delta_y",
    "old_x",
    "new_x",
    "delta_x",
    "group_member",
)


def fix_plan_rows(plan: FixPlan) -> list[tuple[object, ...]]:
    """Build display rows for the Fix Plan tab.

    A shift that mutates both Y and X (rare but possible if combined with a
    future feature) emits TWO rows: one ``shift-y`` and one ``shift-x``. A
    pure Y shift (delta_x is None or 0) emits a single ``shift-y`` row with
    empty X cells. A pure X shift emits a single ``shift-x`` row with empty
    Y cells (FR-009, C4).
    """
    rows: list[tuple[object, ...]] = []
    for ps in plan.shifts:
        sh = ps.shift
        has_y = sh.delta_y != 0
        has_x = sh.delta_x is not None and sh.delta_x != 0
        gm = "yes" if sh.group_member else "no"
        if has_y or not has_x:
            rows.append(
                (
                    sh.page_id,
                    sh.visual_id,
                    "shift-y",
                    sh.old_y,
                    sh.new_y,
                    sh.delta_y,
                    "",
                    "",
                    "",
                    gm,
                )
            )
        if has_x:
            rows.append(
                (
                    sh.page_id,
                    sh.visual_id,
                    "shift-x",
                    "",
                    "",
                    "",
                    sh.old_x,
                    sh.new_x,
                    sh.delta_x,
                    gm,
                )
            )
    return rows


def fix_plan(
    report_path: Path | str,
    conf_path: Path | str | None,
    *,
    profile_name: str | None = None,
) -> FixPlan:
    """Run the fixer in dry-run mode and return a :class:`FixPlan`.

    ``profile_name`` selects the active profile so optional behavior flags
    (currently ``hspacing_fix``) flow through to :func:`plan_fixes`. When
    ``None``, no flags are passed and the fixer behaves identically to the
    pre-feature default (FR-013).
    """
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

    flags: Mapping[str, bool] | None = None
    if profile_name is not None:
        from . import profiles as _profiles

        try:
            flags = _profiles.load_profile_flags(profile_name, report.root)
        except Exception:  # noqa: BLE001 - flags are best-effort
            flags = None

    try:
        shifts, violations = plan_fixes(report, rules, profile_flags=flags)
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
    from ..fixer import apply_plan, build_visual_lookup
    from ..reader import load_report

    try:
        report = load_report(report_path)
    except NotAPbirError as exc:
        raise FixError(str(exc)) from exc

    chosen = [ps.shift for ps in plan.shifts if ps.id in selected_ids]
    if not chosen:
        raise FixError("selected_ids matched no proposed shifts")

    try:
        apply_plan(report, chosen)
    except WriteError as exc:
        raise FixError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise FixError(f"apply failed: {exc}") from exc
    return len(chosen)


# ---------------------------------------------------------------------------
# US2 — Export all (CSV ZIP)
# ---------------------------------------------------------------------------


class NothingToExportError(Exception):
    """Raised by :func:`export_all_zip` when every result tab is empty.

    The GUI converts this into a "nothing to export" messagebox; the CLI
    never invokes this helper so byte-identity is preserved.
    """


# Fixed entry names per FR-012; alphabetical so list-comparison tests don't
# care about insertion order.
_ZIP_ENTRY_ORDER: tuple[str, ...] = (
    "duplicate_layers.csv",
    "fix_plan.csv",
    "gaps.csv",
    "h_spacing.csv",
    "misalignments.csv",
    "overlaps.csv",
)


def _zip_entries(
    result: "ValidateResult",
    fix_plan: "FixPlan | Sequence[Shift] | None",
) -> dict[str, tuple[tuple[str, ...], list[tuple[object, ...]]]]:
    from . import export as _export  # noqa: F401 — used by callers

    entries: dict[str, tuple[tuple[str, ...], list[tuple[object, ...]]]] = {}

    if result.gaps:
        entries["gaps.csv"] = (GAP_COLUMNS, gap_rows(result.gaps))
    if result.overlaps:
        entries["overlaps.csv"] = (OVERLAP_COLUMNS, overlap_rows(result.overlaps))
    if result.duplicate_layers:
        entries["duplicate_layers.csv"] = (
            DUPLICATE_COLUMNS,
            duplicate_rows(result.duplicate_layers),
        )
    if result.misalignments:
        entries["misalignments.csv"] = (
            MISALIGNMENT_COLUMNS,
            misalignment_rows(result.misalignments),
        )
    if result.h_spacing:
        entries["h_spacing.csv"] = (HSPACING_COLUMNS, h_spacing_rows(result.h_spacing))

    if fix_plan is not None:
        # Accept either a FixPlan or a raw Sequence[Shift] for flexibility.
        if isinstance(fix_plan, FixPlan):
            fp_rows = fix_plan_rows(fix_plan)
        else:
            fp_rows = [
                (
                    s.page_id,
                    s.visual_id,
                    s.old_y,
                    s.new_y,
                    s.delta_y,
                    "yes" if getattr(s, "group_member", False) else "no",
                )
                for s in fix_plan
            ]
        if fp_rows:
            entries["fix_plan.csv"] = (FIX_PLAN_COLUMNS, fp_rows)

    return entries


def export_all_zip(
    result: "ValidateResult",
    fix_plan: "FixPlan | Sequence[Shift] | None",
    dest_path: Path | str,
) -> list[str]:
    """Write a ZIP archive at ``dest_path`` with one CSV per non-empty tab.

    Returns the list of archive entry names actually written, sorted
    alphabetically. Raises :class:`NothingToExportError` when every tab
    is empty (no file is written). Raises :class:`OSError` on write
    failure (the GUI surfaces via ``widgets.show_error``).
    """
    import zipfile

    from . import export as _export

    entries = _zip_entries(result, fix_plan)
    if not entries:
        raise NothingToExportError("no non-empty result tabs")

    written: list[str] = []
    target = Path(dest_path)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries.keys()):
            headers, rows = entries[name]
            zf.writestr(name, _export._table_to_csv_bytes(headers, rows))
            written.append(name)
    return written


def default_zip_filename(
    report_root: Path | str,
    *,
    now=None,
) -> str:
    """Return ``<report_root_basename>_validation_<YYYYMMDD-HHMMSS>.zip``.

    ``now`` lets tests inject a frozen :class:`datetime.datetime`.
    """
    import datetime as _dt

    when = now if now is not None else _dt.datetime.now()
    base = Path(report_root).name or "report"
    stamp = when.strftime("%Y%m%d-%H%M%S")
    return f"{base}_validation_{stamp}.zip"
