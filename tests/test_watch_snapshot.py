"""Tests for ``watch.snapshot_mtimes`` and ``watch.diff_mtimes`` (T019)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from pbir_validator.gui import watch


def _touch(p: Path, *, mtime: float | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def test_snapshot_includes_definition_pbir(tmp_path: Path) -> None:
    pbir = _touch(tmp_path / "definition.pbir")
    snap = watch.snapshot_mtimes(tmp_path)
    assert pbir.resolve() in snap


def test_snapshot_includes_pbip_siblings(tmp_path: Path) -> None:
    _touch(tmp_path / "definition.pbir")
    p1 = _touch(tmp_path / "report.pbip")
    p2 = _touch(tmp_path / "another.pbip")
    snap = watch.snapshot_mtimes(tmp_path)
    assert p1.resolve() in snap
    assert p2.resolve() in snap


def test_snapshot_includes_visual_jsons(tmp_path: Path) -> None:
    _touch(tmp_path / "definition.pbir")
    v = _touch(
        tmp_path / "definition" / "pages" / "p1" / "visuals" / "v1" / "visual.json"
    )
    snap = watch.snapshot_mtimes(tmp_path)
    assert v.resolve() in snap


def test_snapshot_glob_rooted_under_definition_pages(tmp_path: Path) -> None:
    """I3 fix — visual.json hidden outside definition/pages MUST NOT match."""
    _touch(tmp_path / "definition.pbir")
    inside = _touch(
        tmp_path / "definition" / "pages" / "p1" / "visuals" / "v1" / "visual.json"
    )
    # Files outside the canonical layout are NOT picked up.
    outside = _touch(tmp_path / "definition" / "decoy" / "visual.json")
    other = _touch(tmp_path / "elsewhere" / "visual.json")
    snap = watch.snapshot_mtimes(tmp_path)
    assert inside.resolve() in snap
    assert outside.resolve() not in snap
    assert other.resolve() not in snap


def test_snapshot_silent_on_missing_root(tmp_path: Path) -> None:
    snap = watch.snapshot_mtimes(tmp_path / "does-not-exist")
    assert snap == {}


def test_snapshot_skips_disappearing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """File vanishes between iter and stat — must NOT raise."""
    import errno

    pbir = _touch(tmp_path / "definition.pbir")
    real_stat = Path.stat

    def flaky_stat(self: Path):
        if self.name == "definition.pbir":
            # errno=ENOENT is required so pathlib's Path.is_file() recognises
            # this as a "vanished" file and silently returns False on Python
            # 3.11/3.12 (where is_file delegates to self.stat()).
            raise FileNotFoundError(errno.ENOENT, "vanished")
        return real_stat(self)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    snap = watch.snapshot_mtimes(tmp_path)
    assert pbir.resolve() not in snap  # silently skipped


def test_diff_mtimes_returns_true_on_advance() -> None:
    p = Path("/fake/p")
    assert watch.diff_mtimes({p: 1.0}, {p: 2.0}) is True


def test_diff_mtimes_returns_false_when_unchanged() -> None:
    p = Path("/fake/p")
    assert watch.diff_mtimes({p: 1.0}, {p: 1.0}) is False


def test_diff_mtimes_returns_true_when_new_path_appears() -> None:
    p = Path("/fake/p")
    q = Path("/fake/q")
    assert watch.diff_mtimes({p: 1.0}, {p: 1.0, q: 0.5}) is True


def test_diff_mtimes_disappearing_path_is_not_a_change() -> None:
    """FR-025: renames shouldn't double-fire. Disappearing path = False."""
    p = Path("/fake/p")
    q = Path("/fake/q")
    assert watch.diff_mtimes({p: 1.0, q: 1.0}, {p: 1.0}) is False


def test_watch_state_dataclass_is_frozen() -> None:
    state = watch.WatchState(mtimes={}, last_check=time.time())
    with pytest.raises(Exception):
        state.last_check = 0  # type: ignore[misc]
