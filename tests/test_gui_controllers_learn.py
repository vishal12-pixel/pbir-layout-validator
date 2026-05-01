"""Unit tests for pbir_validator.gui.controllers learn (T028)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.gui import controllers
from pbir_validator.reader import iter_pages, load_report


def test_list_pages_returns_display_name_and_id(sample_report: Path) -> None:
    pages = controllers.list_pages(sample_report)
    assert pages, "fixture has at least one page"
    assert all(isinstance(name, str) and isinstance(pid, str) for name, pid in pages)


def test_list_pages_invalid_report_raises_learn_error(tmp_path: Path) -> None:
    bogus = tmp_path / "not_a_report"
    bogus.mkdir()
    with pytest.raises(controllers.LearnError):
        controllers.list_pages(bogus)


def test_learn_manual_mode_returns_path_without_calling_learner(
    sample_report: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Manual mode must NOT invoke the underlying learner."""
    called: dict[str, bool] = {}

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["yes"] = True
        raise RuntimeError("learner.learn must not be called in manual mode")

    monkeypatch.setattr("pbir_validator.learner.learn", boom)

    conf = sample_report / "conf.md"
    result = controllers.learn(sample_report, conf, "manual", page_id=None)
    assert result.mode == "manual"
    assert result.rule_count == 0
    assert result.conf_path == conf
    assert "yes" not in called


def test_learn_auto_mode_writes_conf(sample_report: Path) -> None:
    report = load_report(sample_report)
    page_id = next(iter_pages(report)).id

    conf = sample_report / "conf.md"
    result = controllers.learn(sample_report, conf, "auto", page_id=page_id)
    assert result.mode == "auto"
    assert result.rule_count >= 1
    assert result.conf_path.exists()


def test_learn_auto_without_page_id_raises(sample_report: Path) -> None:
    conf = sample_report / "conf.md"
    with pytest.raises(controllers.LearnError, match="page_id"):
        controllers.learn(sample_report, conf, "auto", page_id=None)


def test_learn_auto_unknown_page_id_raises(sample_report: Path) -> None:
    conf = sample_report / "conf.md"
    with pytest.raises(controllers.LearnError, match="page id not found"):
        controllers.learn(sample_report, conf, "auto", page_id="no-such-page")
