"""MRU recents store for the GUI File menu (US6).

Persists the last 5 successfully-loaded report paths to a per-user JSON
file. Stdlib-only; safe to import on a headless host.

Schema (also in `specs/004-gui-quick-wins/contracts/recents-schema.json`):
    {"recent": ["<path1>", "<path2>", ...]}  # MRU at index 0, max 5

Read failures (FileNotFoundError, JSONDecodeError, KeyError, OSError)
all return [] — the app must never crash because of a missing or
corrupt recents file (FR-019).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MAX_ENTRIES = 5
_FILE_NAME = "recents.json"
_DIR_NAME = "pbir_validator"


def recents_path() -> Path:
    """Return the OS-conventional location for the recents file.

    Windows: ``%APPDATA%\\pbir_validator\\recents.json``
    POSIX:   ``~/.config/pbir_validator/recents.json``

    Ensures the parent directory exists; creation failures are silent
    (the caller will handle the subsequent read/write failure).
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"
    target = root / _DIR_NAME / _FILE_NAME
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return target


def load() -> list[str]:
    """Return up to MAX_ENTRIES recent paths, MRU-first.

    Returns ``[]`` on any read or parse failure (FR-019).
    """
    path = recents_path()
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    recent = data.get("recent")
    if not isinstance(recent, list):
        return []
    return [str(p) for p in recent[:MAX_ENTRIES] if isinstance(p, str) and p]


def record(path: str) -> list[str]:
    """De-dup, push ``path`` to front, truncate to MAX_ENTRIES, persist.

    Always returns the new in-memory list, even if disk write fails.
    """
    if not path:
        return load()
    current = load()
    deduped = [p for p in current if p != path]
    new_list = [path, *deduped][:MAX_ENTRIES]
    target = recents_path()
    try:
        target.write_text(
            json.dumps({"recent": new_list}, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return new_list
