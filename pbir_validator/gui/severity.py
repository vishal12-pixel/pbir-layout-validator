"""Severity classification for GUI row tags (T036, US5).

Pure function `band(value, *, kind)` maps a numeric measurement to one of
three Treeview tag names. Stdlib-only; safe to import on a headless host.
"""

from __future__ import annotations

from typing import Literal

SEV_GREEN = "sev_green"
SEV_YELLOW = "sev_yellow"
SEV_RED = "sev_red"

Kind = Literal["deviation", "overlap"]


def band(value: float, *, kind: Kind) -> str:
    """Return the severity tag name for ``value`` under the given ``kind``.

    ``kind="deviation"`` (signed, in pixels):
        |value| <= 2  -> SEV_GREEN
        |value| <= 10 -> SEV_YELLOW
        otherwise     -> SEV_RED

    ``kind="overlap"`` (positive overlap depth, in pixels):
        value <= 0  -> SEV_GREEN  (no overlap)
        value <= 50 -> SEV_YELLOW
        otherwise   -> SEV_RED
    """
    if kind == "deviation":
        magnitude = abs(value)
        if magnitude <= 2:
            return SEV_GREEN
        if magnitude <= 10:
            return SEV_YELLOW
        return SEV_RED
    if kind == "overlap":
        if value <= 0:
            return SEV_GREEN
        if value <= 50:
            return SEV_YELLOW
        return SEV_RED
    raise ValueError(f"unknown kind: {kind!r}")
