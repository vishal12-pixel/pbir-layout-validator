"""Rule-profile loading for the toolbar combobox (US6, FR-050..FR-055).

Profiles are read from ``pbir_validator/profiles/*.md`` via
``importlib.resources`` so they ship with the wheel. ``Report-default``
is added dynamically when the report root contains a ``conf.md``.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Mapping


# Fixed insertion order per FR-055.
_PACKAGED: tuple[tuple[str, str], ...] = (
    ("Standard", "standard.md"),
    ("Strict", "strict.md"),
    ("Relaxed", "relaxed.md"),
)
_REPORT_DEFAULT = "Report-default"


def _packaged_path(filename: str) -> Path:
    """Return the absolute path of a packaged profile file."""
    ref = resources.files("pbir_validator.profiles") / filename
    # ``resources.files`` returns Traversable; ``Path(str(...))`` works on
    # source checkouts and unpacked wheels alike.
    return Path(str(ref))


def list_profiles(report_root: Path | None = None) -> dict[str, Path]:
    """Return ``{display_name: profile_path}`` in insertion order.

    Always contains ``Standard``, ``Strict``, ``Relaxed``. Adds
    ``Report-default`` -> ``<report_root>/conf.md`` only when that file
    exists on disk (FR-055).
    """
    out: dict[str, Path] = {}
    for display, filename in _PACKAGED:
        out[display] = _packaged_path(filename)
    if report_root is not None:
        candidate = Path(report_root) / "conf.md"
        if candidate.is_file():
            out[_REPORT_DEFAULT] = candidate
    return out


def load_profile(name: str, report_root: Path | None = None) -> Mapping:
    """Resolve ``name`` via :func:`list_profiles` then parse via
    :func:`pbir_validator.conf.parse_conf`.

    Raises :class:`KeyError` for unknown names.
    """
    profiles = list_profiles(report_root)
    if name not in profiles:
        raise KeyError(name)
    # Lazy import keeps cold-start cheap and avoids a circular import.
    from ..conf import parse_conf

    return parse_conf(profiles[name])


# Match a header comment of the form ``# <flag_name> = true|false`` (case-insensitive).
_FLAG_RE = re.compile(
    r"^\s*#\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>true|false)\s*$",
    re.IGNORECASE,
)


def load_profile_flags(
    name: str, report_root: Path | None = None
) -> dict[str, bool]:
    """Parse boolean feature flags from a profile's header comment lines.

    Profile files may include comment lines of the form
    ``# <flag> = true|false`` to opt into optional fixer behaviors. This
    function scans the file's comment lines and returns a
    ``{flag_name: bool}`` map. Flags absent from the file are simply absent
    from the result (callers default unknown flags to ``False``).

    Returns an empty dict when the profile cannot be loaded — flags are
    purely optional and never raise.
    """
    profiles = list_profiles(report_root)
    if name not in profiles:
        return {}
    path = profiles[name]
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    flags: dict[str, bool] = {}
    for raw in text.splitlines():
        m = _FLAG_RE.match(raw)
        if not m:
            continue
        flags[m.group("key").lower()] = m.group("val").lower() == "true"
    return flags
