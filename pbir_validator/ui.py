"""ANSI color, headers, tables, prompts.

Color is auto-disabled when ``NO_COLOR`` is set, when stdout is not a TTY, or when
Windows VT-mode cannot be enabled. ``--no-color`` is a hard override (handled by
``cli`` calling :func:`disable_color`).
"""

from __future__ import annotations

import os
import sys
from typing import Iterable, Sequence


RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
BOLD = "\x1b[1m"


_color_enabled: bool = False


def enable_color() -> None:
    """Enable ANSI color if the environment supports it.

    Honours ``NO_COLOR`` and ``sys.stdout.isatty()``. On Windows, attempts to
    switch the console to Virtual Terminal mode; falls back to plain text on
    failure.
    """
    global _color_enabled

    if os.environ.get("NO_COLOR") is not None:
        _color_enabled = False
        return
    if not getattr(sys.stdout, "isatty", lambda: False)():
        _color_enabled = False
        return

    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                _color_enabled = False
                return
            ENABLE_VT = 0x0004
            if not kernel32.SetConsoleMode(handle, mode.value | ENABLE_VT):
                _color_enabled = False
                return
        except Exception:
            _color_enabled = False
            return

    _color_enabled = True


def disable_color() -> None:
    """Hard-disable color output (e.g., from ``--no-color``)."""
    global _color_enabled
    _color_enabled = False


def is_color_enabled() -> bool:
    return _color_enabled


def colored(text: str, code: str) -> str:
    """Return ``text`` wrapped in ``code`` + RESET, or unchanged when disabled."""
    if not _color_enabled:
        return text
    return f"{code}{text}{RESET}"


def header(text: str) -> None:
    print(colored(text, BOLD + CYAN))


def warn(text: str) -> None:
    print(colored(f"WARN: {text}", YELLOW), file=sys.stderr)


def error(text: str) -> None:
    print(colored(f"ERROR: {text}", RED), file=sys.stderr)


def success(text: str) -> None:
    print(colored(text, GREEN))


def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt for ``y/N`` (or ``Y/n`` if ``default=True``)."""
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(question + suffix).strip().lower()
    except (EOFError, OSError):
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def print_table(rows: Sequence[Sequence[object]], headers: Sequence[str]) -> None:
    """Print a simple aligned table to stdout. Plain ASCII, terminal-friendly."""
    cols = list(headers)
    widths = [len(h) for h in cols]
    str_rows: list[list[str]] = []
    for row in rows:
        cells = [str(c) for c in row]
        str_rows.append(cells)
        for i, cell in enumerate(cells):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))

    def fmt(cells: Sequence[str]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    print(colored(fmt(cols), BOLD))
    print(colored("  ".join("-" * w for w in widths), BOLD))
    for r in str_rows:
        print(fmt(r))


def print_violations_table(violations: Iterable[object]) -> None:
    """Render a Violations table.

    Accepts an iterable of objects exposing ``page_display_name``, ``from_type``,
    ``to_type``, ``expected_px``, ``actual_px``, ``deviation_px``.
    """
    rows = []
    for v in violations:
        dev = getattr(v, "deviation_px")
        sign = "+" if dev > 0 else ""
        rows.append(
            (
                getattr(v, "page_display_name"),
                getattr(v, "from_type"),
                getattr(v, "to_type"),
                f"{getattr(v, 'expected_px')}px",
                f"{getattr(v, 'actual_px'):g}px",
                f"{sign}{dev:g}px",
            )
        )
    print_table(rows, ["Page", "From", "To", "Expected", "Actual", "Deviation"])


def print_unknown_pairs(pairs: Iterable[object]) -> None:
    pairs = list(pairs)  # type: ignore[assignment]
    if not pairs:
        return
    print()
    print(colored("Unknown pairs (not counted as violations):", BOLD + YELLOW))
    rows = [
        (
            getattr(p, "page_display_name"),
            getattr(p, "from_type"),
            getattr(p, "to_type"),
            f"{getattr(p, 'actual_px'):g}px",
        )
        for p in pairs
    ]
    print_table(rows, ["Page", "From", "To", "Actual"])


def print_misalignments_table(misalignments: Iterable[object]) -> None:
    """Render a Row Misalignments table.

    Accepts objects exposing ``page_display_name``, ``visual_type``,
    ``visual_id``, ``actual_y``, ``expected_y``, ``deviation_px``.
    """
    misalignments = list(misalignments)  # type: ignore[assignment]
    if not misalignments:
        return
    print()
    print(colored("Row misalignments (visuals out of row Y):", BOLD + RED))
    rows = []
    for m in misalignments:
        dev = getattr(m, "deviation_px")
        sign = "+" if dev > 0 else ""
        rows.append(
            (
                getattr(m, "page_display_name"),
                getattr(m, "visual_type"),
                getattr(m, "visual_id"),
                f"{getattr(m, 'expected_y'):g}",
                f"{getattr(m, 'actual_y'):g}",
                f"{sign}{dev:g}px",
            )
        )
    print_table(rows, ["Page", "Type", "Visual ID", "Expected Y", "Actual Y", "Deviation"])


def print_shift_plan(shifts: Iterable[object]) -> None:
    rows = []
    for s in shifts:
        note = "(group)" if getattr(s, "group_member", False) else ""
        rows.append(
            (
                getattr(s, "page_id"),
                getattr(s, "visual_id"),
                f"{getattr(s, 'old_y'):g}",
                f"{getattr(s, 'new_y'):g}",
                f"{getattr(s, 'delta_y'):+g}",
                note,
            )
        )
    print_table(rows, ["Page", "Visual", "Old Y", "New Y", "Delta", "Note"])


def print_unfixable(violations: Iterable[object]) -> None:
    violations = list(violations)  # type: ignore[assignment]
    unfixable = [v for v in violations if getattr(v, "unfixable_reason", None)]
    if not unfixable:
        return
    print()
    print(colored("Unfixable violations:", BOLD + RED))
    rows = [
        (
            getattr(v, "page_display_name"),
            getattr(v, "from_type"),
            getattr(v, "to_type"),
            getattr(v, "unfixable_reason"),
        )
        for v in unfixable
    ]
    print_table(rows, ["Page", "From", "To", "Reason"])
