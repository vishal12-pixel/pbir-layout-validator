"""Headless-aware smoke test for the GUI App (T046)."""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("tkinter")


def _tk_available() -> bool:
    """Return True if a Tk display is available; skip target on False."""
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter as tk

        probe = tk.Tk()
    except Exception:
        return False
    probe.destroy()
    return True


@pytest.mark.skipif(not _tk_available(), reason="No display available")
def test_app_constructs_with_five_tabs() -> None:
    from pbir_validator.gui.app import App

    app = App()
    try:
        assert app.notebook.index("end") == 5
        labels = [app.notebook.tab(i, "text") for i in range(5)]
        assert labels == [
            "Gap Violations",
            "Overlapping Visuals",
            "Row Misalignments",
            "Horizontal Spacing",
            "Fix Plan",
        ]
    finally:
        app.root.destroy()


@pytest.mark.skipif(not _tk_available(), reason="No display available")
def test_app_action_buttons_disabled_until_report_selected() -> None:
    from pbir_validator.gui.app import App

    app = App()
    try:
        for btn in (app._btn_learn, app._btn_validate, app._btn_fix):
            assert "disabled" in btn.state()
    finally:
        app.root.destroy()
