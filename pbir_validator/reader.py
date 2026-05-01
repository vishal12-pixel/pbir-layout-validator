"""Lazy PBIR reader.

Reads only the JSON paths defined in ``contracts/pbir-paths.md``. All iteration is
generator-based to satisfy Constitution Principle IV (no full-report load).

Also exposes :func:`resolve_report_path` which accepts either a ``.pbip`` file or
a ``.Report`` folder and returns the resolved ``.Report`` directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from . import ui
from .errors import NotAPbirError
from .models import Page, Report, Visual


def resolve_report_path(path_in: Path) -> Path:
    """Resolve ``path_in`` to a ``.Report`` folder.

    Accepts:
      * A path to a ``.pbip`` file. Parses JSON, reads
        ``artifacts[0].report.path`` (relative to the ``.pbip`` file's parent),
        and returns the resolved sibling ``.Report`` directory.
      * A direct path to a ``.Report`` folder.

    Raises :class:`NotAPbirError` on any failure.
    """
    p = Path(path_in)
    if not p.exists():
        raise NotAPbirError(f"path does not exist: {p}")

    if p.is_file() and p.suffix.lower() == ".pbip":
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise NotAPbirError(f"could not read .pbip file {p}: {exc}") from exc
        artifacts = data.get("artifacts") if isinstance(data, dict) else None
        if not isinstance(artifacts, list) or not artifacts:
            raise NotAPbirError(
                f".pbip file has no 'artifacts' array: {p}"
            )
        # Look for the first artifact with a `.report.path`
        rel: str | None = None
        for art in artifacts:
            if isinstance(art, dict):
                rep = art.get("report")
                if isinstance(rep, dict) and isinstance(rep.get("path"), str):
                    rel = rep["path"]
                    break
        if rel is None:
            raise NotAPbirError(
                f".pbip file has no artifacts[].report.path entry: {p}"
            )
        candidate = (p.parent / rel).resolve()
        if not candidate.is_dir():
            raise NotAPbirError(
                f".pbip references missing report folder: {candidate}"
            )
        return candidate

    if p.is_dir():
        return p.resolve()

    raise NotAPbirError(
        f"unsupported path: expected .pbip file or .Report folder, got: {p}"
    )


def load_report(path: Path | str) -> Report:
    """Load a PBIR report.

    ``path`` can be either a ``.pbip`` file or a ``.Report`` folder; the input is
    resolved via :func:`resolve_report_path`. Raises :class:`NotAPbirError` if the
    folder is missing the ``definition/pages`` subtree.
    """
    root = resolve_report_path(Path(path))
    pages_dir = root / "definition" / "pages"
    if not pages_dir.is_dir():
        raise NotAPbirError(
            f"not a PBIR report (missing definition/pages): {root}"
        )
    return Report(root=root, pages_dir=pages_dir)


def iter_pages(report: Report) -> Iterator[Page]:
    """Yield each :class:`Page` under ``report.pages_dir`` lazily.

    Pages with no ``page.json`` are skipped with a warning. Page order is the
    sorted order of folder names (deterministic but not necessarily display
    order; ``pages.json`` is intentionally not consulted in v1 per
    ``contracts/pbir-paths.md``).
    """
    if not report.pages_dir.is_dir():
        return
    for entry in sorted(report.pages_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        page_json = entry / "page.json"
        if not page_json.is_file():
            ui.warn(f"page folder has no page.json: {entry}")
            continue
        try:
            data = json.loads(page_json.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            ui.warn(f"malformed page.json: {page_json} ({exc})")
            continue
        display_name = data.get("displayName") if isinstance(data, dict) else None
        if not isinstance(display_name, str) or not display_name:
            ui.warn(f"page.json missing displayName: {page_json}")
            display_name = entry.name
        height = _as_float(data.get("height") if isinstance(data, dict) else None, page_json, "height")
        width = _as_float(data.get("width") if isinstance(data, dict) else None, page_json, "width")
        yield Page(
            id=entry.name,
            display_name=display_name,
            height=height,
            width=width,
            path=entry,
            visuals_dir=entry / "visuals",
        )


def _as_float(v: object, source: Path, key: str) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    ui.warn(f"page.json missing/non-numeric {key}: {source}")
    return 0.0


def iter_visuals(page: Page) -> Iterator[Visual]:
    """Yield each :class:`Visual` under ``page.visuals_dir`` lazily.

    Malformed JSON files are skipped with a warning (per spec edge case + FR-023).
    """
    visuals_dir = page.visuals_dir
    if not visuals_dir.is_dir():
        return
    for entry in sorted(visuals_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        visual_json = entry / "visual.json"
        if not visual_json.is_file():
            continue
        try:
            v = parse_visual(visual_json, page_id=page.id)
        except (OSError, ValueError) as exc:
            ui.warn(f"skipping malformed visual.json: {visual_json} ({exc})")
            continue
        if v is not None:
            yield v


def parse_visual(path: Path, *, page_id: str) -> Visual | None:
    """Parse one ``visual.json`` into a :class:`Visual`.

    Returns ``None`` if the file is unusable for layout analysis (missing
    ``position`` block or non-numeric coordinates) — caller emits a warning.
    """
    raw_text = path.read_text(encoding="utf-8-sig")
    data = json.loads(raw_text)
    if not isinstance(data, dict):
        ui.warn(f"visual.json root is not an object: {path}")
        return None

    indent = _detect_indent(raw_text)
    trailing_newline = raw_text.endswith("\n")

    position = data.get("position")
    if not isinstance(position, dict):
        ui.warn(f"visual.json missing position object: {path}")
        return None

    try:
        x = float(position["x"])
        y = float(position["y"])
        width = float(position["width"])
        height = float(position["height"])
    except (KeyError, TypeError, ValueError):
        ui.warn(f"visual.json has missing/non-numeric position fields: {path}")
        return None

    visual_block = data.get("visual")
    visual_type: str = "unknown"
    if isinstance(visual_block, dict):
        vt = visual_block.get("visualType")
        if isinstance(vt, str) and vt:
            visual_type = vt
        else:
            ui.warn(f"visual.json missing visual.visualType, using 'unknown': {path}")
    else:
        ui.warn(f"visual.json missing visual block, using 'unknown' type: {path}")

    parent_group_name = data.get("parentGroupName")
    if parent_group_name is not None and not isinstance(parent_group_name, str):
        parent_group_name = None

    return Visual(
        id=path.parent.name,
        page_id=page_id,
        visual_type=visual_type,
        x=x,
        y=y,
        width=width,
        height=height,
        parent_group_name=parent_group_name,
        path=path,
        raw=data,
        indent=indent,
        trailing_newline=trailing_newline,
    )


def _detect_indent(text: str) -> int:
    """Detect indentation width by inspecting the first indented line."""
    for line in text.splitlines():
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0 and stripped:
            return leading
    return 2
