"""End-to-end CLI test for `fix`."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pbir_validator", *args],
        capture_output=True,
        text=True,
    )


def _learn(sample_report: Path) -> None:
    r = _run(
        [
            "learn",
            "--report",
            str(sample_report),
            "--page",
            "pageA",
            "--force",
            "--no-color",
        ]
    )
    assert r.returncode == 0, r.stderr


def test_dry_run_makes_no_writes(sample_report: Path) -> None:
    _learn(sample_report)
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v02_actionButton"
        / "visual.json"
    )
    mtime_before = target.stat().st_mtime_ns
    bytes_before = target.read_bytes()
    result = _run(
        ["fix", "--report", str(sample_report), "--dry-run", "--no-color"]
    )
    # exit 1 because pageC has unfixable; planned changes printed
    assert result.returncode in (0, 1), result.stdout + result.stderr
    assert "Planned changes" in result.stdout or "Dry-run" in result.stdout
    assert target.stat().st_mtime_ns == mtime_before
    assert target.read_bytes() == bytes_before


def test_apply_changes_only_y(sample_report: Path) -> None:
    _learn(sample_report)
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v02_actionButton"
        / "visual.json"
    )
    before = json.loads(target.read_text(encoding="utf-8"))
    result = _run(["fix", "--report", str(sample_report), "--apply", "--no-color"])
    # exit 1 because pageC's unfixable violation remains
    assert result.returncode == 1, result.stdout + result.stderr
    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["position"]["y"] == 99  # was 104, shifted by -5
    # Other fields preserved
    assert after["name"] == before["name"]
    assert after["visual"] == before["visual"]
    other_pos_before = {k: v for k, v in before["position"].items() if k != "y"}
    other_pos_after = {k: v for k, v in after["position"].items() if k != "y"}
    assert other_pos_after == other_pos_before


def test_revalidate_after_apply_pageb_clean(
    tmp_path: Path, sample_report_src: Path
) -> None:
    """A report containing only fixable pages (A + B) → after fix, validate exits 0."""
    only_ab = tmp_path / "AB.Report"
    only_ab.mkdir()
    (only_ab / "definition" / "pages").mkdir(parents=True)
    shutil.copytree(
        sample_report_src / "definition" / "pages" / "pageA",
        only_ab / "definition" / "pages" / "pageA",
    )
    shutil.copytree(
        sample_report_src / "definition" / "pages" / "pageB",
        only_ab / "definition" / "pages" / "pageB",
    )
    _learn(only_ab)
    fix = _run(["fix", "--report", str(only_ab), "--apply", "--no-color"])
    assert fix.returncode == 0, fix.stdout + fix.stderr
    val = _run(["validate", "--report", str(only_ab), "--no-color"])
    assert val.returncode == 0, val.stdout + val.stderr


def test_unfixable_does_not_block_other_pages(sample_report: Path) -> None:
    _learn(sample_report)
    pageb_target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v02_actionButton"
        / "visual.json"
    )
    before = json.loads(pageb_target.read_text(encoding="utf-8"))["position"]["y"]
    result = _run(["fix", "--report", str(sample_report), "--apply", "--no-color"])
    assert result.returncode == 1  # unfixable on pageC
    after = json.loads(pageb_target.read_text(encoding="utf-8"))["position"]["y"]
    assert after != before  # pageB still got fixed
    assert "Unfixable" in result.stdout
