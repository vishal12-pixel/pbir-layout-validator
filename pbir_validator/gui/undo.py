"""One-level Undo for ``fixer.apply_plan`` (US7, FR-060..FR-066).

Pure file IO + JSON. Atomic write via tempfile + ``os.replace`` mirrors
:mod:`pbir_validator.writer`. Restores ``position.y`` byte-for-byte via
:func:`pbir_validator.writer.write_visual_json`.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from pathlib import Path
from typing import Sequence


_BACKUP_DIRNAME = ".pbir_validator_undo"
_BACKUP_FILENAME = "last_fix.json"


def backup_path(report_root: Path | str) -> Path:
    """Return the canonical backup file path for ``report_root``."""
    return Path(report_root) / _BACKUP_DIRNAME / _BACKUP_FILENAME


def _to_posix_relative(report_root: Path, target: Path) -> str:
    """Return ``target`` as a forward-slash relative path under ``report_root``."""
    try:
        rel = target.resolve().relative_to(Path(report_root).resolve())
    except ValueError:
        rel = Path(target).name  # fallback — shouldn't happen in practice
    return rel.as_posix()


def _utc_now_iso() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def record_pre_fix(report_root: Path | str, plan: Sequence) -> Path:
    """Write ``<report_root>/.pbir_validator_undo/last_fix.json``.

    ``plan`` is a sequence of :class:`pbir_validator.models.Shift`-like
    objects exposing ``visual_id``, ``path``, ``old_y`` and ``new_y``
    attributes. One JSON entry per shift is written. Overwrites any prior
    backup (one-level undo, FR-064). Atomic via tempfile + ``os.replace``.

    Returns the path that was written.
    """
    root = Path(report_root)
    target = backup_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)

    shifts: list[dict] = []
    for s in plan:
        entry: dict = {
            "path": _to_posix_relative(root, Path(getattr(s, "path"))),
            "visual_id": getattr(s, "visual_id"),
            "old_y": float(getattr(s, "old_y")),
            "new_y": float(getattr(s, "new_y")),
        }
        # Optional X coordinates — only emit when this shift mutated X
        # (FR-007). Pre-feature backups remain byte-identical.
        old_x = getattr(s, "old_x", None)
        new_x = getattr(s, "new_x", None)
        if old_x is not None and new_x is not None:
            entry["old_x"] = float(old_x)
            entry["new_x"] = float(new_x)
        shifts.append(entry)
    payload = {"applied_at": _utc_now_iso(), "shifts": shifts}
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    data = (text + "\n").encode("utf-8")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            delete=False,
            prefix=".tmp-undo-",
            suffix=".json",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, target)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return target


def has_backup(report_root: Path | str) -> bool:
    """Return True iff a backup file exists for ``report_root``."""
    return backup_path(report_root).is_file()


def restore_last_fix(report_root: Path | str) -> tuple[bool, str, list[str]]:
    """Restore every shift in the backup; return ``(ok, message, paths)``.

    On success the backup file AND its parent ``.pbir_validator_undo/``
    directory (when empty) are deleted. On per-file write failure the
    operation aborts immediately and the backup file is left untouched
    (FR-065).
    """
    root = Path(report_root)
    target = backup_path(root)
    if not target.is_file():
        return (False, f"no backup file at {target}", [])
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return (False, f"could not read backup {target}: {exc}", [])
    try:
        payload = json.loads(text)
    except ValueError as exc:
        return (False, f"backup {target} is not valid JSON: {exc}", [])
    shifts = payload.get("shifts") if isinstance(payload, dict) else None
    if not isinstance(shifts, list):
        return (False, f"backup {target} has no 'shifts' array", [])

    # Resolve each visual to write back its old_y via writer.write_visual_json.
    from ..reader import iter_pages, iter_visuals, load_report
    from ..writer import write_visual_json

    try:
        report = load_report(root)
    except Exception as exc:  # noqa: BLE001 — surface to user as a string
        return (False, f"could not reload report at {root}: {exc}", [])

    visual_lookup: dict[str, object] = {}
    for page in iter_pages(report):
        for v in iter_visuals(page):
            try:
                rel = v.path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                rel = v.path.as_posix()
            visual_lookup[rel] = v

    modified: list[str] = []
    for entry in shifts:
        if not isinstance(entry, dict):
            return (False, f"backup {target} has malformed shift entry", modified)
        rel_path = entry.get("path")
        old_y = entry.get("old_y")
        if not isinstance(rel_path, str) or old_y is None:
            return (
                False,
                f"backup {target} shift missing path/old_y: {entry!r}",
                modified,
            )
        v = visual_lookup.get(rel_path)
        if v is None:
            return (False, f"visual not found for backup path: {rel_path}", modified)
        # Restore X if and only if the backup recorded it (FR-008). Backups
        # without ``old_x`` were Y-only — pass ``new_x=None`` to keep
        # byte-identical behavior with pre-feature backups.
        old_x_raw = entry.get("old_x") if isinstance(entry, dict) else None
        new_x_arg: float | None = (
            float(old_x_raw) if old_x_raw is not None else None
        )
        try:
            write_visual_json(v, float(old_y), new_x=new_x_arg)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 — abort; leave backup on disk
            return (
                False,
                f"failed to restore {rel_path}: {exc}",
                modified,
            )
        modified.append(rel_path)

    # Success: delete the backup file and its parent dir if empty.
    try:
        target.unlink()
    except OSError:
        pass
    try:
        target.parent.rmdir()
    except OSError:
        pass
    return (True, f"restored {len(modified)} visual(s)", modified)
