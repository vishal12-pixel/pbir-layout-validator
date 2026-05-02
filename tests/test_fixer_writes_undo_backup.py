"""Test that ``fixer.apply_plan`` writes the undo backup BEFORE mutating (T041)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pbir_validator import fixer


@dataclass
class _FakeShift:
    visual_id: str
    path: Path
    old_y: float
    new_y: float


@dataclass
class _FakeReport:
    root: Path


def test_apply_plan_records_backup_before_first_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "report"
    p.mkdir()
    visual_path = p / "definition" / "pages" / "p" / "visuals" / "v1" / "visual.json"
    visual_path.parent.mkdir(parents=True, exist_ok=True)
    visual_path.write_text("{}", encoding="utf-8")
    shift = _FakeShift("v1", visual_path, 100.0, 105.0)

    call_order: list[str] = []

    def fake_record(report_root, plan):
        call_order.append("record")
        return Path(report_root) / ".pbir_validator_undo" / "last_fix.json"

    def fake_apply_shifts(shifts, lookup):
        call_order.append("apply")

    def fake_build_lookup(report):
        return {}

    monkeypatch.setattr("pbir_validator.gui.undo.record_pre_fix", fake_record)
    monkeypatch.setattr(fixer, "apply_shifts", fake_apply_shifts)
    monkeypatch.setattr(fixer, "build_visual_lookup", fake_build_lookup)

    fixer.apply_plan(_FakeReport(root=p), [shift])
    assert call_order == ["record", "apply"]
