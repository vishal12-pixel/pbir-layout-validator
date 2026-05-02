"""Atomic JSON writer for ``visual.json`` mutations.

Mutates ``position.y`` (always) and optionally ``position.x`` per :class:`models.Visual`.
All other keys, key order, indentation, and trailing newline are preserved
(Principle II + FR-010, FR-014).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .errors import WriteError
from .models import Visual


def write_visual_json(
    visual: Visual,
    new_y: float,
    *,
    new_x: float | None = None,
) -> None:
    """Atomically write ``visual.path`` with ``position.y = new_y``.

    When ``new_x`` is provided, ``position.x`` is mutated in the same atomic
    write (FR-003, FR-004). When ``new_x is None`` (default), only
    ``position.y`` is touched — byte-identical to the pre-feature behavior
    so existing Y-only callers see no change (FR-013).

    Strategy: copy of ``visual.raw`` → mutate → serialize → temp file in the same
    directory → ``fsync`` → ``os.replace``. ``os.replace`` is atomic on POSIX and
    on NTFS for same-filesystem moves (see ``research.md`` §4).
    """
    target = visual.path
    parent = target.parent

    # Defensive deep-ish copy of the position dict so we never mutate the
    # frozen-dataclass-shared raw payload.
    data = dict(visual.raw)
    position = dict(data.get("position", {}))
    position["y"] = new_y
    data["position"] = position

    # Preserve int-ness when new_y is integral so we don't churn `100` → `100.0`.
    if float(new_y).is_integer():
        position["y"] = int(new_y)

    # Optional X mutation — preserve int-ness identically to Y (FR-014).
    if new_x is not None:
        position["x"] = new_x
        if float(new_x).is_integer():
            position["x"] = int(new_x)

    text = json.dumps(data, indent=visual.indent, ensure_ascii=False)
    if visual.trailing_newline:
        text += "\n"
    payload = text.encode("utf-8")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=parent,
            delete=False,
            prefix=".tmp-pbir-",
            suffix=target.name,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, target)
        tmp_path = None
    except OSError as exc:
        raise WriteError(f"failed to write {target}: {exc}", path=target) from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
