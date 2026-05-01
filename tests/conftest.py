"""Shared pytest fixtures for pbir_validator tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_REPORT = FIXTURES_DIR / "sample-report"


@pytest.fixture
def sample_report_src() -> Path:
    """Return the read-only path of the committed sample-report fixture."""
    assert SAMPLE_REPORT.is_dir(), f"Missing fixture: {SAMPLE_REPORT}"
    return SAMPLE_REPORT


@pytest.fixture
def sample_report(tmp_path: Path, sample_report_src: Path) -> Path:
    """Return a writable, per-test copy of the sample-report fixture."""
    dest = tmp_path / "sample-report"
    shutil.copytree(sample_report_src, dest)
    return dest
