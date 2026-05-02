"""Tests for ``undo.record_pre_fix`` and ``undo.restore_last_fix`` (T040)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from pbir_validator.gui import undo


@dataclass
class _FakeShift:
    visual_id: str
    path: Path
    old_y: float
    new_y: float


def _build_pbir(report_root: Path, *, visuals: list[tuple[str, str, float]]) -> None:
    """Create a minimal PBIR layout under ``report_root``.

    ``visuals`` is a list of ``(page_id, visual_id, y)`` tuples.
    """
    (report_root / "definition.pbir").write_text(
        json.dumps({"version": "4.0"}), encoding="utf-8"
    )
    pages_dir = report_root / "definition" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    pages: dict[str, list[tuple[str, float]]] = {}
    for page_id, visual_id, y in visuals:
        pages.setdefault(page_id, []).append((visual_id, y))
    for page_id, items in pages.items():
        page_dir = pages_dir / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "page.json").write_text(
            json.dumps({"name": page_id, "displayName": page_id, "height": 1000, "width": 1280}),
            encoding="utf-8",
        )
        visuals_dir = page_dir / "visuals"
        visuals_dir.mkdir(parents=True, exist_ok=True)
        for visual_id, y in items:
            v_dir = visuals_dir / visual_id
            v_dir.mkdir(parents=True, exist_ok=True)
            (v_dir / "visual.json").write_text(
                json.dumps(
                    {
                        "name": visual_id,
                        "visual": {"visualType": "card"},
                        "position": {"x": 0, "y": y, "z": 1, "width": 100, "height": 50},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )


def test_record_pre_fix_writes_schema_conformant_json(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    shift = _FakeShift("v1", visual_path, 100.0, 105.0)
    written = undo.record_pre_fix(p, [shift])
    assert written == p / ".pbir_validator_undo" / "last_fix.json"
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert "applied_at" in payload
    assert isinstance(payload["shifts"], list)
    assert payload["shifts"][0]["visual_id"] == "v1"
    assert payload["shifts"][0]["old_y"] == 100.0
    assert payload["shifts"][0]["new_y"] == 105.0
    assert "/" in payload["shifts"][0]["path"]
    assert "\\" not in payload["shifts"][0]["path"]


def test_record_pre_fix_creates_parent_dir(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    assert not (p / ".pbir_validator_undo").exists()
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    undo.record_pre_fix(p, [_FakeShift("v1", visual_path, 1.0, 2.0)])
    assert (p / ".pbir_validator_undo").is_dir()


def test_record_pre_fix_overwrites_prior_backup(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    undo.record_pre_fix(p, [_FakeShift("v1", visual_path, 1.0, 2.0)])
    undo.record_pre_fix(p, [_FakeShift("v2", visual_path, 3.0, 4.0)])
    payload = json.loads(undo.backup_path(p).read_text(encoding="utf-8"))
    assert payload["shifts"][0]["visual_id"] == "v2"
    assert len(payload["shifts"]) == 1


def test_restore_last_fix_restores_position_y(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    _build_pbir(p, visuals=[("page1", "v1", 105.0)])  # mutated state on disk
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    # Record that we shifted from 100 -> 105
    shift = _FakeShift("v1", visual_path, old_y=100.0, new_y=105.0)
    undo.record_pre_fix(p, [shift])
    ok, msg, modified = undo.restore_last_fix(p)
    assert ok, msg
    assert len(modified) == 1
    after = json.loads(visual_path.read_text(encoding="utf-8"))
    assert after["position"]["y"] == 100  # restored to old_y


def test_restore_last_fix_deletes_backup_on_success(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    _build_pbir(p, visuals=[("page1", "v1", 105.0)])
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    undo.record_pre_fix(p, [_FakeShift("v1", visual_path, 100.0, 105.0)])
    assert undo.has_backup(p)
    undo.restore_last_fix(p)
    assert not undo.has_backup(p)
    assert not (p / ".pbir_validator_undo").exists()


def test_restore_last_fix_missing_backup_returns_false(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    _build_pbir(p, visuals=[("page1", "v1", 100.0)])
    ok, msg, modified = undo.restore_last_fix(p)
    assert ok is False
    assert "no backup" in msg
    assert modified == []


def test_restore_last_fix_unreadable_backup_returns_false(tmp_path: Path) -> None:
    p = tmp_path / "report"
    p.mkdir()
    _build_pbir(p, visuals=[("page1", "v1", 100.0)])
    backup = undo.backup_path(p)
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("{not valid json", encoding="utf-8")
    ok, msg, modified = undo.restore_last_fix(p)
    assert ok is False


def test_restore_last_fix_per_file_failure_keeps_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-065 — abort on per-file failure; backup file stays."""
    p = tmp_path / "report"
    p.mkdir()
    _build_pbir(p, visuals=[("page1", "v1", 105.0)])
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    undo.record_pre_fix(p, [_FakeShift("v1", visual_path, 100.0, 105.0)])
    assert undo.has_backup(p)

    def boom(*_a, **_kw):
        raise OSError("simulated permission error")

    monkeypatch.setattr("pbir_validator.writer.write_visual_json", boom)
    ok, msg, modified = undo.restore_last_fix(p)
    assert ok is False
    assert undo.has_backup(p)  # backup left untouched per FR-065


def test_record_pre_fix_atomic_via_tempfile(tmp_path: Path) -> None:
    """Verify the temp file pattern doesn't leave artifacts on success."""
    p = tmp_path / "report"
    p.mkdir()
    visual_path = p / "definition" / "pages" / "page1" / "visuals" / "v1" / "visual.json"
    undo.record_pre_fix(p, [_FakeShift("v1", visual_path, 1.0, 2.0)])
    backup_dir = p / ".pbir_validator_undo"
    files = list(backup_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "last_fix.json"
