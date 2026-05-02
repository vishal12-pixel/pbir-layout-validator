"""Rule-profile loading for the toolbar combobox (US6, FR-050..FR-055).

Profiles are read from ``pbir_validator/profiles/*.md`` via
``importlib.resources`` so they ship with the wheel. ``Report-default``
is added dynamically when the report root contains a ``conf.md``.
"""

from __future__ import annotations

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
