"""Tests for the new ``rules=`` kwarg on ``controllers.validate`` (T005)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbir_validator.gui import controllers


def _conf(path: Path) -> Path:
    path.write_text(
        "card -> actionButton: 9px\n"
        "actionButton -> tableEx: 16px\n"
        "tableEx -> shape: 8px\n",
        encoding="utf-8",
    )
    return path


def test_validate_default_reads_conf_md(sample_report: Path) -> None:
    conf = _conf(sample_report / "conf.md")
    result = controllers.validate(sample_report, conf)
    assert isinstance(result, controllers.ValidateResult)


def test_validate_with_rules_skips_disk_lookup(
    sample_report: Path, tmp_path: Path
) -> None:
    """When rules= is supplied the conf path is ignored entirely."""
    from pbir_validator.models import GapRule

    rules = {
        ("card", "actionButton"): GapRule("card", "actionButton", 9),
        ("actionButton", "tableEx"): GapRule("actionButton", "tableEx", 16),
        ("tableEx", "shape"): GapRule("tableEx", "shape", 8),
    }
    # Pass a non-existent conf path; rules= must override and prevent error.
    bogus_conf = tmp_path / "does-not-exist.md"
    result = controllers.validate(sample_report, bogus_conf, rules=rules)
    assert isinstance(result, controllers.ValidateResult)


def test_validate_without_conf_md_uses_rules(sample_report: Path) -> None:
    """No conf.md on disk + rules=mapping must validate without error."""
    from pbir_validator.models import GapRule

    rules = {("card", "actionButton"): GapRule("card", "actionButton", 9)}
    # sample_report has no conf.md by default
    assert not (sample_report / "conf.md").exists()
    result = controllers.validate(sample_report, None, rules=rules)
    assert isinstance(result, controllers.ValidateResult)


def test_validate_rules_none_falls_back_to_disk(sample_report: Path) -> None:
    conf = _conf(sample_report / "conf.md")
    # rules=None is equivalent to omitting the kwarg.
    result = controllers.validate(sample_report, conf, rules=None)
    assert isinstance(result, controllers.ValidateResult)
