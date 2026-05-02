"""Watch-mode helpers (US3, FR-021/FR-025).

Pure data; ``Tk.after()`` orchestration lives in :mod:`pbir_validator.gui.app`.
This module is exhaustively unit-tested via headless-friendly fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class WatchState:
    """Snapshot of watched files' mtimes at a point in time."""

    mtimes: Mapping[Path, float]
    last_check: float


def _iter_watch_paths(report_root: Path) -> list[Path]:
    paths: list[Path] = []
    pbir = report_root / "definition.pbir"
    if pbir.is_file():
        paths.append(pbir)
    # Sibling .pbip files in the report root.
    try:
        for entry in sorted(report_root.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_file() and entry.suffix.lower() == ".pbip":
                paths.append(entry)
    except OSError:
        pass
    # Standard PBIP layout: definition/pages/<page-id>/visuals/<visual-id>/visual.json
    pages_dir = report_root / "definition" / "pages"
    if pages_dir.is_dir():
        # Use rglob with a precise pattern to root the search under definition/.
        try:
            for visual_json in pages_dir.glob("*/visuals/*/visual.json"):
                if visual_json.is_file():
                    paths.append(visual_json)
        except OSError:
            pass
    return paths


def snapshot_mtimes(report_root: Path) -> dict[Path, float]:
    """Return {absolute_path: st_mtime} for every watched file.

    Files that disappear mid-walk are silently skipped (FR-025).
    """
    out: dict[Path, float] = {}
    for path in _iter_watch_paths(Path(report_root)):
        try:
            out[path.resolve()] = path.stat().st_mtime
        except (FileNotFoundError, OSError):
            continue
    return out


def diff_mtimes(
    previous: Mapping[Path, float],
    current: Mapping[Path, float],
) -> bool:
    """Return True iff any path's mtime advanced or any path is new.

    Disappearing files do NOT count as a change, so renames don't double-fire
    after the next snapshot.
    """
    for path, mtime in current.items():
        prev = previous.get(path)
        if prev is None:
            return True
        if mtime > prev:
            return True
    return False
