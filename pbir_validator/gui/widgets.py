"""Reusable Tk widgets for the pbir_validator GUI.

Imports :mod:`tkinter` lazily; this module is safe to import on a headless
host so long as no factory function is actually called.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Sequence

from . import export


class ResultTable(ttk.Frame):
    """A ``ttk.Treeview`` wrapping a list of homogeneous rows.

    When the row list is empty, an "empty-state" label is shown instead of
    the (empty) tree. Calling :meth:`set_rows` swaps between the two states.
    """

    def __init__(
        self,
        parent: tk.Misc,
        columns: Sequence[str],
        *,
        empty_message: str = "No issues found",
    ) -> None:
        super().__init__(parent)
        self._columns = tuple(columns)
        self._empty_message = empty_message
        self._rows: list[tuple[object, ...]] = []

        # Empty-state label (shown when rows == [])
        self._empty_label = ttk.Label(
            self, text=empty_message, anchor="center", padding=24
        )

        # Tree + scrollbar (shown when rows != [])
        self._tree_frame = ttk.Frame(self)
        self._tree = ttk.Treeview(
            self._tree_frame,
            columns=self._columns,
            show="headings",
            height=12,
        )
        for col in self._columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(
            self._tree_frame, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Default: empty state
        self._empty_label.pack(fill="both", expand=True)

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def get_rows(self) -> list[tuple[object, ...]]:
        return list(self._rows)

    def set_rows(self, rows: Sequence[Sequence[object]]) -> None:
        self._rows = [tuple(r) for r in rows]
        # Clear current tree contents
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        if self._rows:
            self._empty_label.pack_forget()
            self._tree_frame.pack(fill="both", expand=True)
            for row in self._rows:
                self._tree.insert("", "end", values=row)
        else:
            self._tree_frame.pack_forget()
            self._empty_label.pack(fill="both", expand=True)

    def clear(self) -> None:
        self.set_rows([])


def show_error(parent: tk.Misc, title: str, message: str) -> None:
    """Display a readable error dialog (FR-024)."""
    messagebox.showerror(title=title, message=message, parent=parent)


def make_export_button(
    parent: tk.Misc,
    *,
    get_table: Callable[[], ResultTable],
    label: str = "Export…",
) -> ttk.Button:
    """Create a button that exports the current rows of ``get_table()``.

    The save-file dialog defaults to CSV and offers JSON via the file-type
    dropdown (FR-013a). Disabled state is managed by the caller; this factory
    returns the button widget so callers can ``.state(["disabled"])`` etc.
    """

    def _on_click() -> None:
        table = get_table()
        rows = table.get_rows()
        path_str = filedialog.asksaveasfilename(
            parent=parent,
            title="Export to file",
            defaultextension=".csv",
            filetypes=[("CSV (Excel)", "*.csv"), ("JSON", "*.json")],
            initialfile="pbir_validator_export.csv",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            if path.suffix.lower() == ".json":
                export.write_json(table.columns, rows, path)
            else:
                export.write_csv(table.columns, rows, path)
        except OSError as exc:
            show_error(parent, "Export failed", f"{path}: {exc}")
            return
        messagebox.showinfo(
            title="Export complete",
            message=f"Wrote {len(rows)} row(s) to {path}",
            parent=parent,
        )

    return ttk.Button(parent, text=label, command=_on_click)


# ---------------------------------------------------------------------------
# Learn (US2) dialogs
# ---------------------------------------------------------------------------


def ask_manual_or_auto(parent: tk.Misc) -> str:
    """Show the FR-007 yes/no/cancel prompt. Returns 'manual', 'auto', or 'cancel'."""
    answer = messagebox.askyesnocancel(
        title="Learn — manual or auto?",
        message=(
            "Do you want to manually edit conf.md instead?\n\n"
            "Yes → open conf.md in your default editor.\n"
            "No  → pick a source page and regenerate conf.md.\n"
            "Cancel → do nothing."
        ),
        parent=parent,
    )
    if answer is None:
        return "cancel"
    return "manual" if answer else "auto"


class _PagePickerDialog:
    """Modal Toplevel with a Combobox of pages.

    Stores the chosen ``page_id`` on ``self.result`` (or ``None`` on cancel).
    """

    def __init__(
        self, parent: tk.Misc, pages: list[tuple[str, str]]
    ) -> None:
        self.result: str | None = None
        self._pages = pages

        top = tk.Toplevel(parent)
        top.title("Pick a reference page")
        top.transient(parent)
        top.grab_set()
        top.resizable(False, False)
        self._top = top

        ttk.Label(
            top,
            text="Select the page whose layout will define the spacing rules:",
            padding=10,
        ).pack()

        labels = [name for name, _ in pages]
        self._var = tk.StringVar(value=labels[0] if labels else "")
        combo = ttk.Combobox(
            top, values=labels, textvariable=self._var, state="readonly", width=50
        )
        combo.pack(padx=12, pady=4)

        btns = ttk.Frame(top, padding=8)
        btns.pack()
        ttk.Button(btns, text="Confirm", command=self._on_ok).pack(
            side="left", padx=4
        )
        ttk.Button(btns, text="Cancel", command=self._on_cancel).pack(
            side="left", padx=4
        )
        top.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _on_ok(self) -> None:
        chosen_label = self._var.get()
        for name, pid in self._pages:
            if name == chosen_label:
                self.result = pid
                break
        self._top.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self._top.destroy()


def ask_source_page(
    parent: tk.Misc, pages: list[tuple[str, str]]
) -> str | None:
    """Show a modal page-picker dialog. Returns the chosen ``page_id`` or ``None``."""
    if not pages:
        show_error(parent, "No pages found", "The report has no pages to learn from.")
        return None
    dlg = _PagePickerDialog(parent, pages)
    parent.wait_window(dlg._top)
    return dlg.result


# ---------------------------------------------------------------------------
# Fix (US3) per-shift checkbox row
# ---------------------------------------------------------------------------


class ShiftCheckboxRow(ttk.Frame):
    """One row in the Fix Plan checklist (FR-016, FR-017)."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        shift_id: str,
        page_id: str,
        visual_id: str,
        delta_y: float,
        old_y: float,
        new_y: float,
        group_member: bool,
        on_toggle: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.shift_id = shift_id
        self._var = tk.BooleanVar(value=True)
        self._on_toggle = on_toggle

        cb = ttk.Checkbutton(self, variable=self._var, command=self._fire_toggle)
        cb.pack(side="left", padx=(4, 8))

        group_tag = "  [group]" if group_member else ""
        label_text = (
            f"{page_id} / {visual_id}: y {old_y:g} → {new_y:g} "
            f"(Δ {delta_y:+g}px){group_tag}"
        )
        ttk.Label(self, text=label_text, anchor="w").pack(
            side="left", fill="x", expand=True
        )

    @property
    def selected(self) -> bool:
        return bool(self._var.get())

    def set_enabled(self, enabled: bool) -> None:
        for child in self.winfo_children():
            try:
                child.state(["!disabled" if enabled else "disabled"])
            except Exception:  # ttk widgets only
                pass

    def _fire_toggle(self) -> None:
        if self._on_toggle is not None:
            self._on_toggle()
