"""Cross-cutting CLI integration tests: cold-start budget + smoke."""

from __future__ import annotations

import subprocess
import sys
import time


def test_help_cold_start_under_2s() -> None:
    """``--help`` must dispatch quickly. Budget per Principle IV is <200 ms but
    process spawn dominates on Windows; 2 s is a generous, non-flaky upper bound."""
    start = time.perf_counter()
    res = subprocess.run(
        [sys.executable, "-m", "pbir_validator", "--help"],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    assert res.returncode == 0
    assert elapsed < 2.0, f"--help took {elapsed:.2f}s"


def test_version_runs() -> None:
    res = subprocess.run(
        [sys.executable, "-m", "pbir_validator", "--version"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "pbir_validator" in res.stdout
