"""Parse and write the human-readable ``conf.md`` rules file.

Format (per ``contracts/conf-format.md``):

    <from_type> -> <to_type>: <gap>px

Lines starting with ``#`` are comments. Blank lines are allowed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from . import ui
from .errors import ConfParseError
from .models import GapRule


_RULE_RE = re.compile(
    r"""^
    \s*
    (?P<from>[A-Za-z_][A-Za-z0-9_-]*)
    \s* -> \s*
    (?P<to>[A-Za-z_][A-Za-z0-9_-]*)
    \s* : \s*
    (?P<gap>-?\d+)
    \s* px
    \s*$
    """,
    re.VERBOSE,
)


def parse_conf(path: Path | str) -> dict[tuple[str, str], GapRule]:
    """Parse ``conf.md`` and return a dict keyed on ``(from_type, to_type)``.

    Raises :class:`ConfParseError` when the file does not exist or contains zero
    valid rules. Individual malformed rule lines emit a warning and are skipped.
    """
    p = Path(path)
    if not p.exists():
        raise ConfParseError(f"conf.md not found at {p}")

    text = p.read_text(encoding="utf-8-sig")
    rules: dict[tuple[str, str], GapRule] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _RULE_RE.match(raw)
        if not m:
            ui.warn(f"{p}:{lineno}: malformed rule line, skipping: {raw!r}")
            continue
        from_t = m.group("from")
        to_t = m.group("to")
        gap = int(m.group("gap"))
        if gap < 0:
            ui.warn(f"{p}:{lineno}: negative gap {gap}px is unusual")
        key = (from_t, to_t)
        if key in rules:
            ui.warn(
                f"{p}:{lineno}: duplicate rule for {from_t} -> {to_t}; "
                f"keeping first occurrence"
            )
            continue
        rules[key] = GapRule(from_type=from_t, to_type=to_t, gap_px=gap)

    if not rules:
        raise ConfParseError(f"conf.md at {p} contains no rules")

    return rules


def write_conf(
    rules: Iterable[GapRule],
    path: Path | str,
    *,
    header_lines: list[str] | None = None,
) -> None:
    """Write ``rules`` deterministically (sorted by ``(from_type, to_type)``)."""
    p = Path(path)
    sorted_rules = sorted(rules, key=lambda r: (r.from_type, r.to_type))
    lines: list[str] = []
    if header_lines:
        lines.extend(header_lines)
    else:
        lines.append("# PBIR Layout spacing rules")
        lines.append("# Format: <from_type> -> <to_type>: <gap>px")
        lines.append("# Edit by hand if needed; comments start with #.")
    lines.append("")
    for r in sorted_rules:
        lines.append(f"{r.from_type} -> {r.to_type}: {r.gap_px}px")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
