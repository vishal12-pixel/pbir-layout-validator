"""MRU recents store + GUI session state for the File menu and toolbar.

Persists the last 5 successfully-loaded report paths plus two GUI session
keys (``side_panel_visible``, ``profile``) to a per-user JSON file.
Stdlib-only; safe to import on a headless host.

Schema (extends `specs/004-gui-quick-wins/contracts/recents-schema.json`):
    {
      "recent": ["<path1>", "<path2>", ...],   # MRU at index 0, max 5
      "side_panel_visible": true,                # FR-044, default true
      "profile": "Standard"                      # FR-054, default "Standard"
    }

Read failures (FileNotFoundError, JSONDecodeError, KeyError, OSError)
all return safe defaults — the app must never crash because of a
missing or corrupt recents file (FR-019).

Backward compatibility (FR-072): older recents files lacking the new
keys load unchanged; missing keys default to ``True`` and ``"Standard"``
respectively. The original ``load() -> list[str]`` shape is preserved
so all pre-existing call sites and tests stay green;
:func:`load_state` exposes the full dict; :func:`load_paths` is a
contract-faithful alias for :func:`load`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

MAX_ENTRIES = 5
_FILE_NAME = "recents.json"
_DIR_NAME = "pbir_validator"

DEFAULT_SIDE_PANEL_VISIBLE = True
DEFAULT_PROFILE = "Standard"


def recents_path() -> Path:
    """Return the OS-conventional location for the recents file."""
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


def _read_raw() -> dict[str, Any]:
    path = recents_path()
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def load_state() -> dict[str, Any]:
    """Return the full dict {recent, side_panel_visible, profile}.

    Missing keys default to ``True`` and ``"Standard"`` respectively
    (FR-072). Always returns a dict.
    """
    data = _read_raw()
    recent_list = data.get("recent")
    if not isinstance(recent_list, list):
        recent_list = []
    cleaned = [str(p) for p in recent_list[:MAX_ENTRIES] if isinstance(p, str) and p]
    side = data.get("side_panel_visible")
    if not isinstance(side, bool):
        side = DEFAULT_SIDE_PANEL_VISIBLE
    profile = data.get("profile")
    if not isinstance(profile, str) or not profile:
        profile = DEFAULT_PROFILE
    return {
        "recent": cleaned,
        "side_panel_visible": side,
        "profile": profile,
    }


def load() -> list[str]:
    """Return up to MAX_ENTRIES recent paths, MRU-first.

    Backward-compatible shape from feature 004 — preserved so existing
    File→Recent submenu code keeps working unchanged. New session-state
    keys are read via :func:`load_state` instead.
    """
    return load_state()["recent"]


def load_paths() -> list[str]:
    """Contract-faithful alias for :func:`load` (FR-072 / contract)."""
    return load()


def _persist(state: dict[str, Any]) -> None:
    target = recents_path()
    try:
        target.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def record(path: str | None = None, **updates: Any) -> Any:
    """De-dup, push ``path`` to front of the MRU list, persist updates.

    Backward-compatible shape: returns the **MRU list** when called with
    only a ``path`` argument (no kwargs) so existing call sites that did
    ``recents.record(str(report.root))`` keep working byte-identically.
    Returns the full **state dict** when any keyword update is supplied.
    """
    state = load_state()
    if path:
        deduped = [p for p in state["recent"] if p != path]
        state["recent"] = [path, *deduped][:MAX_ENTRIES]

    has_kw_update = False
    for key, value in updates.items():
        if key == "side_panel_visible":
            state[key] = bool(value)
        elif key == "profile":
            state[key] = str(value)
        else:
            state[key] = value
        has_kw_update = True

    _persist(state)
    if has_kw_update:
        return state
    return state["recent"]
