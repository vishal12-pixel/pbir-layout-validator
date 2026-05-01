"""Atomic JSON writer for ``visual.json`` mutations.

Mutates only ``position.y`` per :class:`models.Visual`. All other keys, key order,
indentation, and trailing newline are preserved (Principle II + FR-010).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .errors import WriteError
from .models import Visual


def write_visual_json(visual: Visual, new_y: float) -> None:
    """Atomically write ``visual.path`` with ``position.y = new_y``.

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
