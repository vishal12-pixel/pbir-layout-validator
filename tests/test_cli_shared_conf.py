"""End-to-end CLI test for shared `--conf` workflow (US4)."""

from __future__ import annotations

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


def test_shared_conf_applies_to_two_reports(
    tmp_path: Path, sample_report_src: Path
) -> None:
    a = tmp_path / "A.Report"
    b = tmp_path / "B.Report"
    shutil.copytree(sample_report_src, a)
    shutil.copytree(sample_report_src, b)

    # Generate a shared conf from A's pageA, place in a third location
    learn = _run(
        [
            "learn",
            "--report",
            str(a),
            "--page",
            "pageA",
            "--out",
            str(tmp_path / "shared.md"),
            "--force",
            "--no-color",
        ]
    )
    assert learn.returncode == 0, learn.stderr

    shared = tmp_path / "shared.md"
    assert shared.exists()

    # Validate A and B with the shared conf
    res_a = _run(
        ["validate", "--report", str(a), "--conf", str(shared), "--no-color"]
    )
    res_b = _run(
        ["validate", "--report", str(b), "--conf", str(shared), "--no-color"]
    )
    # Both reports include pageB violation → exit 1
    assert res_a.returncode == 1
    assert res_b.returncode == 1


def test_missing_shared_conf(tmp_path: Path, sample_report_src: Path) -> None:
    a = tmp_path / "A.Report"
    shutil.copytree(sample_report_src, a)
    res = _run(
        [
            "validate",
            "--report",
            str(a),
            "--conf",
            str(tmp_path / "missing.md"),
            "--no-color",
        ]
    )
    assert res.returncode == 5
    assert "not found" in res.stderr.lower() or "missing.md" in res.stderr


def test_unparseable_conf(tmp_path: Path, sample_report_src: Path) -> None:
    a = tmp_path / "A.Report"
    shutil.copytree(sample_report_src, a)
    bad = tmp_path / "bad.md"
    bad.write_text("# only a comment, no rules\n", encoding="utf-8")
    res = _run(
        ["validate", "--report", str(a), "--conf", str(bad), "--no-color"]
    )
    assert res.returncode == 5
