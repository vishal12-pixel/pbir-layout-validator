"""Command-line interface for pbir_validator.

Heavy imports are deferred behind sub-command dispatch so ``--help`` and
``--version`` cold-start within the <200 ms budget.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__


_REPORT_HELP = (
    "Path to a Power BI .pbip file OR a .Report folder. The tool auto-detects "
    "which kind of path was given. .pbip files are read for "
    "artifacts[].report.path to locate the sibling .Report folder."
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pbir_validator",
        description=(
            "Validate and fix vertical spacing between visuals in Power BI "
            "PBIR-format reports."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pbir_validator {__version__}",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="{learn,validate,fix}")

    p_learn = sub.add_parser("learn", help="Derive spacing rules from a reference page.")
    p_learn.add_argument("--report", required=True, help=_REPORT_HELP)
    p_learn.add_argument(
        "--out",
        default=None,
        help="Output path for conf.md (default: <report>/conf.md).",
    )
    p_learn.add_argument(
        "--page",
        default=None,
        help="Page id to use (skips interactive prompt).",
    )
    p_learn.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file without prompting.",
    )
    p_learn.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    p_learn.set_defaults(func=_run_learn)

    p_val = sub.add_parser(
        "validate", help="Check every page against conf.md (read-only)."
    )
    p_val.add_argument("--report", required=True, help=_REPORT_HELP)
    p_val.add_argument(
        "--conf",
        default=None,
        help="Path to conf.md (default: <report>/conf.md).",
    )
    p_val.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    p_val.set_defaults(func=_run_validate)

    p_fix = sub.add_parser("fix", help="Auto-apply Y-coordinate shifts to fix violations.")
    p_fix.add_argument("--report", required=True, help=_REPORT_HELP)
    p_fix.add_argument(
        "--conf",
        default=None,
        help="Path to conf.md (default: <report>/conf.md).",
    )
    p_fix.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan; do not modify any file.",
    )
    p_fix.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes without an interactive prompt.",
    )
    p_fix.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    p_fix.set_defaults(func=_run_fix)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Best-effort: ensure stdout/stderr can encode any text we emit, even when
    # the parent shell uses a legacy code page (e.g., Windows cp1252).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError, OSError):
            pass

    # Initialize color: enable_color first (env+TTY+VT), then honour --no-color.
    from . import ui

    ui.enable_color()
    if getattr(args, "no_color", False):
        ui.disable_color()

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        ui.error("interrupted")
        return 6
    except Exception as exc:  # pragma: no cover (only as a last resort)
        from .errors import ConfParseError, NotAPbirError, WriteError

        if os.environ.get("PBIR_VALIDATOR_DEBUG") == "1":
            raise
        if isinstance(exc, NotAPbirError):
            ui.error(str(exc))
            return 2
        if isinstance(exc, ConfParseError):
            ui.error(str(exc))
            return 5
        if isinstance(exc, WriteError):
            ui.error(str(exc))
            return 5
        ui.error(f"{type(exc).__name__}: {exc}")
        return 5


# ---------------------------------------------------------------------------
# Sub-command runners (heavy imports happen inside)
# ---------------------------------------------------------------------------


def _run_learn(args: argparse.Namespace) -> int:
    from . import ui
    from .errors import NotAPbirError
    from .learner import learn, list_pages, prompt_page_selection
    from .reader import load_report

    try:
        report = load_report(args.report)
    except NotAPbirError as exc:
        ui.error(str(exc))
        return 2

    pages = list_pages(report)
    if not pages:
        ui.error("no pages found in report")
        return 2

    if args.page:
        page = next((p for p in pages if p.id == args.page), None)
        if page is None:
            ui.error(f"page id not found: {args.page}")
            return 2
    else:
        page = prompt_page_selection(pages)
        if page is None:
            ui.warn("cancelled")
            return 3

    out_path = Path(args.out) if args.out else report.root / "conf.md"
    result = learn(report, page, out_path, force=args.force)
    if result is None:
        return 4
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    from . import ui
    from .conf import parse_conf
    from .errors import ConfParseError, NotAPbirError
    from .reader import load_report
    from .validator import validate_report

    try:
        report = load_report(args.report)
    except NotAPbirError as exc:
        ui.error(str(exc))
        return 2

    conf_path = Path(args.conf) if args.conf else report.root / "conf.md"
    try:
        rules = parse_conf(conf_path)
    except ConfParseError as exc:
        ui.error(str(exc))
        return 5

    ui.header(f"Validating {report.root}")
    print(f"Using rules from: {conf_path}")
    print()

    violations, unknowns, misalignments, hspacing_issues = validate_report(
        report, rules
    )

    if violations:
        ui.print_violations_table(violations)
    if misalignments:
        ui.print_misalignments_table(misalignments)
    if hspacing_issues:
        ui.print_hspacing_table(hspacing_issues)
    ui.print_unknown_pairs(unknowns)

    print()
    pages_affected = len(
        {v.page_id for v in violations}
        | {m.page_id for m in misalignments}
        | {h.page_id for h in hspacing_issues}
    )
    total_issues = len(violations) + len(misalignments) + len(hspacing_issues)
    if total_issues:
        bits: list[str] = []
        if violations:
            bits.append(f"{len(violations)} gap violation(s)")
        if misalignments:
            bits.append(f"{len(misalignments)} row misalignment(s)")
        if hspacing_issues:
            bits.append(f"{len(hspacing_issues)} h-spacing issue(s)")
        ui.error(f"{' + '.join(bits)} across {pages_affected} page(s)")
        return 1
    ui.success("OK — no violations")
    return 0


def _run_fix(args: argparse.Namespace) -> int:
    from . import ui
    from .conf import parse_conf
    from .errors import ConfParseError, NotAPbirError, WriteError
    from .fixer import apply_shifts, build_visual_lookup, plan_fixes
    from .reader import load_report

    if args.dry_run and args.apply:
        ui.error("--dry-run and --apply are mutually exclusive")
        return 5

    try:
        report = load_report(args.report)
    except NotAPbirError as exc:
        ui.error(str(exc))
        return 2

    conf_path = Path(args.conf) if args.conf else report.root / "conf.md"
    try:
        rules = parse_conf(conf_path)
    except ConfParseError as exc:
        ui.error(str(exc))
        return 5

    ui.header(f"Fixing {report.root}")
    print(f"Using rules from: {conf_path}")
    print()

    shifts, violations = plan_fixes(report, rules)

    if violations:
        ui.print_violations_table(violations)

    if shifts:
        print()
        ui.header("Planned changes:")
        ui.print_shift_plan(shifts)

    ui.print_unfixable(violations)

    has_unfixable = any(v.unfixable_reason for v in violations)

    if not shifts:
        print()
        if has_unfixable:
            ui.error("nothing to apply; all remaining violations are unfixable")
            return 1
        ui.success("OK — nothing to fix")
        return 0

    if args.dry_run:
        print()
        ui.success("Dry-run — no files modified")
        return 1 if has_unfixable else 0

    if not args.apply:
        if not ui.prompt_yes_no(
            f"Apply {len(shifts)} change(s) across "
            f"{len({s.page_id for s in shifts})} page(s)?",
            default=False,
        ):
            print()
            ui.warn("Cancelled")
            return 6

    lookup = build_visual_lookup(report)
    try:
        apply_shifts(shifts, lookup)
    except WriteError as exc:
        ui.error(str(exc))
        return 5

    print()
    ui.success(f"Applied {len(shifts)} change(s)")
    return 1 if has_unfixable else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
