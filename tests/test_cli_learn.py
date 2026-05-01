"""End-to-end CLI test for `learn`."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pbir_validator.conf import parse_conf


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pbir_validator", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_learn_writes_conf(sample_report: Path) -> None:
    result = _run(
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
    assert result.returncode == 0, result.stderr
    conf = sample_report / "conf.md"
    assert conf.exists()
    rules = parse_conf(conf)
    assert ("card", "actionButton") in rules


def test_learn_with_pbip(tmp_path: Path, sample_report_src: Path) -> None:
    """Learn accepts a .pbip path and resolves to the .Report folder."""
    dest = tmp_path / "MyReport.Report"
    shutil.copytree(sample_report_src, dest)
    pbip = tmp_path / "MyReport.pbip"
    pbip.write_text(
        '{"version":"1.0","artifacts":[{"report":{"path":"MyReport.Report"}}]}',
        encoding="utf-8",
    )
    result = _run(
        [
            "learn",
            "--report",
            str(pbip),
            "--page",
            "pageA",
            "--force",
            "--no-color",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert (dest / "conf.md").exists()


def test_learn_unknown_page_id(sample_report: Path) -> None:
    result = _run(
        ["learn", "--report", str(sample_report), "--page", "nope", "--no-color"]
    )
    assert result.returncode == 2
    assert "page id not found" in result.stderr.lower()


def test_help_runs(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pbir_validator", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "learn" in result.stdout
    assert "validate" in result.stdout
    assert "fix" in result.stdout


def test_subcommand_help_mentions_pbip() -> None:
    """Each subcommand's --help should describe the .pbip / .Report dual input."""
    for sub in ("learn", "validate", "fix"):
        result = subprocess.run(
            [sys.executable, "-m", "pbir_validator", sub, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert ".pbip" in result.stdout, f"{sub} --help missing .pbip mention"
        assert ".Report" in result.stdout, f"{sub} --help missing .Report mention"
