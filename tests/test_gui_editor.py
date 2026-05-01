"""Unit tests for pbir_validator.gui.editor (T020)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from pbir_validator.gui import editor


def test_open_in_default_editor_raises_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-file.md"
    with pytest.raises(editor.EditorLaunchError, match="does not exist"):
        editor.open_in_default_editor(missing)


def test_open_in_default_editor_dispatches_per_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.md"
    target.write_text("hi", encoding="utf-8")

    calls: list[tuple[str, tuple]] = []

    def fake_startfile(p: str) -> None:
        calls.append(("startfile", (p,)))

    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        calls.append(("run", tuple(cmd)))
        return subprocess.CompletedProcess(cmd, 0)

    # Force every branch to be tested by toggling sys.platform
    monkeypatch.setattr(subprocess, "run", fake_run)
    if sys.platform == "win32":
        import os
        monkeypatch.setattr(os, "startfile", fake_startfile, raising=False)
        editor.open_in_default_editor(target)
        assert calls == [("startfile", (str(target),))]
    else:
        editor.open_in_default_editor(target)
        cmd = calls[0][1]
        assert cmd[0] in {"open", "xdg-open"}
        assert cmd[1] == str(target)


def test_open_in_default_editor_wraps_subprocess_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform == "win32":
        pytest.skip("subprocess path not exercised on Windows")
    target = tmp_path / "f.md"
    target.write_text("hi", encoding="utf-8")

    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(editor.EditorLaunchError, match="could not open editor"):
        editor.open_in_default_editor(target)
