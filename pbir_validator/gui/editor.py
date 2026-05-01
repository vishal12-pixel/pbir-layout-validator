"""Open a file in the OS default editor (FR-008).

Pure stdlib. No Tk imports.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class EditorLaunchError(RuntimeError):
    """Raised when the OS-level editor handoff fails."""


def open_in_default_editor(path: Path | str) -> None:
    """Open ``path`` in whatever editor the OS associates with the file type.

    Windows: ``os.startfile``. macOS: ``open``. Linux/other: ``xdg-open``.

    Raises :class:`EditorLaunchError` on any underlying failure so callers can
    show a readable in-window message (FR-024) instead of a raw traceback.
    """
    p = Path(path)
    if not p.exists():
        raise EditorLaunchError(f"file does not exist: {p}")

    try:
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=True)
        else:
            subprocess.run(["xdg-open", str(p)], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EditorLaunchError(
            f"could not open editor for {p}: {exc}"
        ) from exc
