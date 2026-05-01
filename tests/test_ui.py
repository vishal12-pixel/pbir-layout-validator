"""Tests for pbir_validator.ui — color, prompts, table formatting."""

from __future__ import annotations

import io
import sys

import pytest

from pbir_validator import ui


@pytest.fixture(autouse=True)
def _reset_color() -> None:
    ui.disable_color()


def test_colored_no_op_when_disabled() -> None:
    ui.disable_color()
    assert ui.colored("hello", ui.RED) == "hello"


def test_colored_wraps_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force enable manually by toggling the module flag, since enable_color() is
    # gated on isatty() / NO_COLOR / Windows VT.
    monkeypatch.setattr(ui, "_color_enabled", True)
    out = ui.colored("hello", ui.RED)
    assert out.startswith(ui.RED) and out.endswith(ui.RESET)


def test_no_color_env_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    # Pretend we have a TTY
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    ui.enable_color()
    assert not ui.is_color_enabled()


def test_disabled_when_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
    ui.enable_color()
    assert not ui.is_color_enabled()


def test_print_table_aligns_columns(capsys: pytest.CaptureFixture[str]) -> None:
    ui.disable_color()
    ui.print_table([("a", "1"), ("bb", "22")], ["X", "Y"])
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert lines[0].startswith("X ")  # left-aligned, padded
    assert "bb" in lines[-1] and "22" in lines[-1]


def test_prompt_yes_no_default_no(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert ui.prompt_yes_no("ok?") is False


def test_prompt_yes_no_y(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert ui.prompt_yes_no("ok?") is True


def test_warn_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    ui.warn("hi")
    err = capsys.readouterr().err
    assert "hi" in err
