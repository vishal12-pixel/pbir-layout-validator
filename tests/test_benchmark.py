"""Performance budget tests (opt-in via ``-m benchmark``).

Generates the 50-page benchmark report on demand if not already present, then
asserts wall-clock budgets per SC-001/002 and research.md §18.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import pytest

from pbir_validator.conf import parse_conf, write_conf
from pbir_validator.fixer import plan_fixes
from pbir_validator.learner import learn
from pbir_validator.models import GapRule
from pbir_validator.reader import iter_pages, load_report
from pbir_validator.validator import validate_report


BENCH_DIR = Path(__file__).parent / "fixtures" / "benchmark-report"


def _ensure_benchmark_fixture() -> Path:
    if not BENCH_DIR.exists():
        gen = importlib.util.spec_from_file_location(
            "_gen", Path(__file__).parent / "_gen_benchmark.py"
        )
        assert gen and gen.loader
        mod = importlib.util.module_from_spec(gen)
        gen.loader.exec_module(mod)
        mod.main()
    return BENCH_DIR


@pytest.mark.benchmark
def test_validate_50_pages_under_5s() -> None:
    root = _ensure_benchmark_fixture()
    report = load_report(root)
    rules = {
        ("card", "actionButton"): GapRule("card", "actionButton", 10),
        ("actionButton", "tableEx"): GapRule("actionButton", "tableEx", 10),
        ("tableEx", "shape"): GapRule("tableEx", "shape", 10),
        ("shape", "slicer"): GapRule("shape", "slicer", 10),
        ("slicer", "card"): GapRule("slicer", "card", 10),
    }
    start = time.perf_counter()
    validate_report(report, rules)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"50-page validate took {elapsed:.2f}s (>5s)"


@pytest.mark.benchmark
def test_learn_40_page_slice_under_10s(tmp_path: Path) -> None:
    root = _ensure_benchmark_fixture()
    report = load_report(root)
    pages = list(iter_pages(report))
    out = tmp_path / "conf.md"
    page = pages[0]
    start = time.perf_counter()
    learn(report, page, out, force=True)
    elapsed = time.perf_counter() - start
    assert elapsed < 10.0, f"learn took {elapsed:.2f}s (>10s)"


@pytest.mark.benchmark
def test_validate_40_page_slice_under_15s(tmp_path: Path) -> None:
    root = _ensure_benchmark_fixture()
    report = load_report(root)
    out = tmp_path / "conf.md"
    pages = list(iter_pages(report))
    learn(report, pages[0], out, force=True)
    rules = parse_conf(out)
    start = time.perf_counter()
    validate_report(report, rules)
    elapsed = time.perf_counter() - start
    assert elapsed < 15.0, f"validate took {elapsed:.2f}s (>15s)"
