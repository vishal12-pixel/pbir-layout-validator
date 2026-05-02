"""Tests for undo round-trip with X coordinates (T024, FR-007/008, SC-002)."""

from __future__ import annotations

import json
from pathlib import Path

from pbir_validator.fixer import (
    apply_shifts,
    build_visual_lookup,
    plan_fixes,
)
from pbir_validator.gui import undo as undo_mod
from pbir_validator.gui.profiles import load_profile_flags
from pbir_validator.models import Shift
from pbir_validator.reader import iter_pages, iter_visuals, load_report
from pbir_validator.conf import parse_conf


def _strict_rules() -> dict:
    return parse_conf(Path("pbir_validator/profiles/strict.md"))


def test_undo_after_xshift_restores_position_x(hspacing_report: Path) -> None:
    """Apply X-shifts, undo, verify each visual's position.x is restored (FR-008, SC-002)."""
    report = load_report(hspacing_report)
    rules = _strict_rules()
    flags = load_profile_flags("Strict")
    shifts, _ = plan_fixes(report, rules, profile_flags=flags)
    slicer_shifts = [s for s in shifts if s.page_id == "slicerRow"]
    assert slicer_shifts

    # Capture pre-fix x values per visual id.
    pre_x: dict[str, float] = {}
    for page in iter_pages(report):
        for v in iter_visuals(page):
            pre_x[v.id] = v.x

    # Record backup, then apply.
    undo_mod.record_pre_fix(report.root, slicer_shifts)
    apply_shifts(slicer_shifts, build_visual_lookup(report))

    # Sanity: x changed.
    report_mid = load_report(hspacing_report)
    mid_x = {v.id: v.x for p in iter_pages(report_mid) for v in iter_visuals(p)}
    assert mid_x["v4_slicer"] == pre_x["v4_slicer"] - 2

    # Undo and verify restoration.
    ok, msg, paths = undo_mod.restore_last_fix(report.root)
    assert ok, msg

    report_after = load_report(hspacing_report)
    for page in iter_pages(report_after):
        for v in iter_visuals(page):
            assert v.x == pre_x[v.id], f"{v.id}: {v.x} != {pre_x[v.id]}"


def test_record_pre_fix_omits_x_keys_for_y_only_shift(tmp_path: Path) -> None:
    """A Y-only Shift (no old_x) must NOT add X keys to the backup (FR-007 backward compat)."""
    fake_path = tmp_path / "fake.json"
    s = Shift(
        visual_id="v1",
        page_id="pX",
        path=fake_path,
        old_y=10,
        new_y=20,
        delta_y=10,
    )
    backup = undo_mod.record_pre_fix(tmp_path, [s])
    payload = json.loads(backup.read_text(encoding="utf-8"))
    entry = payload["shifts"][0]
    assert "old_x" not in entry
    assert "new_x" not in entry


def test_record_pre_fix_writes_x_keys_for_xshift(tmp_path: Path) -> None:
    """A Shift with old_x set writes both old_x and new_x to the backup entry (FR-007)."""
    fake_path = tmp_path / "fake.json"
    s = Shift(
        visual_id="v1",
        page_id="pX",
        path=fake_path,
        old_y=10,
        new_y=10,
        delta_y=0,
        old_x=100,
        new_x=98,
        delta_x=-2,
    )
    backup = undo_mod.record_pre_fix(tmp_path, [s])
    payload = json.loads(backup.read_text(encoding="utf-8"))
    entry = payload["shifts"][0]
    assert entry["old_x"] == 100
    assert entry["new_x"] == 98


def test_undo_handles_legacy_backup_without_x_keys(sample_report: Path) -> None:
    """A backup file lacking old_x keys (pre-feature schema) restores Y-only without error."""
    # Pre-mutate a single visual with a Y-only shift.
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageA"
        / "visuals"
        / "v01_card"
        / "visual.json"
    )
    pre_data = json.loads(target.read_text(encoding="utf-8"))
    pre_y = pre_data["position"]["y"]

    from pbir_validator.writer import write_visual_json
    from pbir_validator.reader import parse_visual

    visual = parse_visual(target, page_id="pageA")
    assert visual is not None
    write_visual_json(visual, new_y=pre_y + 7)

    # Hand-craft a legacy backup file (no old_x/new_x keys).
    backup_dir = sample_report / ".pbir_validator_undo"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / "last_fix.json"
    backup_file.write_text(
        json.dumps(
            {
                "applied_at": "2026-05-02T00:00:00Z",
                "shifts": [
                    {
                        "path": "definition/pages/pageA/visuals/v01_card/visual.json",
                        "visual_id": "v01_card",
                        "old_y": float(pre_y),
                        "new_y": float(pre_y + 7),
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ok, msg, _ = undo_mod.restore_last_fix(sample_report)
    assert ok, msg
    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["position"]["y"] == pre_y
