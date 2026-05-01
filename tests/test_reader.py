"""Tests for pbir_validator.reader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbir_validator.errors import NotAPbirError
from pbir_validator.reader import (
    iter_pages,
    iter_visuals,
    load_report,
    parse_visual,
    resolve_report_path,
)


def test_load_report_raises_for_non_pbir(tmp_path: Path) -> None:
    with pytest.raises(NotAPbirError):
        load_report(tmp_path)


def test_load_report_succeeds_on_fixture(sample_report_src: Path) -> None:
    report = load_report(sample_report_src)
    assert report.pages_dir.is_dir()


def test_iter_pages_lazy_yields_three(sample_report_src: Path) -> None:
    report = load_report(sample_report_src)
    pages = list(iter_pages(report))
    assert len(pages) == 3
    names = sorted(p.display_name for p in pages)
    assert names == ["Fixable Page", "Good Reference", "Unfixable Page"]


def test_iter_visuals_skips_malformed(sample_report: Path) -> None:
    """Malformed JSON file is skipped with a warning, run continues."""
    bad = sample_report / "definition" / "pages" / "pageA" / "visuals" / "v_broken"
    bad.mkdir()
    (bad / "visual.json").write_text("{ this is not json", encoding="utf-8")

    report = load_report(sample_report)
    page_a = next(p for p in iter_pages(report) if p.id == "pageA")
    visuals = list(iter_visuals(page_a))
    # Original 4 visuals on pageA preserved; broken one skipped
    assert len(visuals) == 4


def test_parse_visual_missing_visual_type_defaults_to_unknown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    p = tmp_path / "visual.json"
    p.write_text(
        json.dumps(
            {
                "name": "v",
                "position": {"x": 0, "y": 0, "width": 10, "height": 10},
                "visual": {},
            }
        ),
        encoding="utf-8",
    )
    v = parse_visual(p, page_id="x")
    assert v is not None
    assert v.visual_type == "unknown"
    assert "missing visual.visualType" in capsys.readouterr().err


def test_parse_visual_missing_position_returns_none(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    p = tmp_path / "visual.json"
    p.write_text(
        json.dumps({"name": "v", "visual": {"visualType": "card"}}),
        encoding="utf-8",
    )
    assert parse_visual(p, page_id="x") is None
    assert "missing position" in capsys.readouterr().err


def test_parse_visual_position_parsed(sample_report_src: Path) -> None:
    p = (
        sample_report_src
        / "definition"
        / "pages"
        / "pageA"
        / "visuals"
        / "v01_card"
        / "visual.json"
    )
    v = parse_visual(p, page_id="pageA")
    assert v is not None
    assert v.visual_type == "card"
    assert (v.x, v.y, v.width, v.height) == (10.0, 10.0, 200.0, 80.0)


def test_resolve_report_path_accepts_pbip(tmp_path: Path, sample_report_src: Path) -> None:
    """resolve_report_path follows .pbip artifacts[].report.path → .Report folder."""
    # Copy the fixture into tmp + write a .pbip alongside it
    import shutil

    dest = tmp_path / "MyReport.Report"
    shutil.copytree(sample_report_src, dest)
    pbip = tmp_path / "MyReport.pbip"
    pbip.write_text(
        json.dumps(
            {
                "version": "1.0",
                "artifacts": [{"report": {"path": "MyReport.Report"}}],
            }
        ),
        encoding="utf-8",
    )
    resolved = resolve_report_path(pbip)
    assert resolved.resolve() == dest.resolve()


def test_resolve_report_path_accepts_folder(sample_report_src: Path) -> None:
    resolved = resolve_report_path(sample_report_src)
    assert resolved.resolve() == sample_report_src.resolve()


def test_resolve_report_path_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(NotAPbirError):
        resolve_report_path(tmp_path / "does-not-exist")


def test_resolve_report_path_rejects_bad_pbip(tmp_path: Path) -> None:
    pbip = tmp_path / "bad.pbip"
    pbip.write_text("{}", encoding="utf-8")
    with pytest.raises(NotAPbirError):
        resolve_report_path(pbip)


def test_load_report_via_pbip(tmp_path: Path, sample_report_src: Path) -> None:
    import shutil

    dest = tmp_path / "X.Report"
    shutil.copytree(sample_report_src, dest)
    pbip = tmp_path / "X.pbip"
    pbip.write_text(
        json.dumps({"artifacts": [{"report": {"path": "X.Report"}}]}),
        encoding="utf-8",
    )
    report = load_report(pbip)
    assert report.pages_dir.is_dir()
