"""End-to-end CLI test for `validate`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pbir_validator", *args],
        capture_output=True,
        text=True,
    )


def _learn_first(sample_report: Path) -> None:
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


def test_validate_reports_violation(sample_report: Path) -> None:
    _learn_first(sample_report)
    result = _run(["validate", "--report", str(sample_report), "--no-color"])
    assert result.returncode == 1, result.stdout + result.stderr
    assert "card" in result.stdout
    assert "actionButton" in result.stdout


def test_validate_clean_exit_zero(sample_report: Path, tmp_path: Path) -> None:
    """Run against a single-page copy of just pageA → no violations."""
    only_a = tmp_path / "OnlyA.Report"
    only_a.mkdir()
    (only_a / "definition" / "pages").mkdir(parents=True)
    src_pages = sample_report / "definition" / "pages"
    import shutil

    shutil.copytree(src_pages / "pageA", only_a / "definition" / "pages" / "pageA")
    _learn_first(only_a)
    result = _run(["validate", "--report", str(only_a), "--no-color"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no violations" in result.stdout.lower()


def test_validate_missing_conf(sample_report: Path) -> None:
    result = _run(
        ["validate", "--report", str(sample_report), "--conf", "/nope.md", "--no-color"]
    )
    assert result.returncode == 5
    assert "not found" in result.stderr.lower() or "conf.md" in result.stderr.lower()


def test_validate_does_not_modify_files(sample_report: Path) -> None:
    _learn_first(sample_report)
    target = (
        sample_report
        / "definition"
        / "pages"
        / "pageB"
        / "visuals"
        / "v02_actionButton"
        / "visual.json"
    )
    before = target.read_bytes()
    _run(["validate", "--report", str(sample_report), "--no-color"])
    after = target.read_bytes()
    assert before == after
