"""Tk main window for pbir_validator-gui (FR-001, FR-002, FR-005, FR-012).

Headless detection (FR-025) probes Tk before any window is shown.
Long-running operations run on a background thread via :mod:`.workers`
so the main loop never blocks (FR-023).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import controllers, editor, recents, widgets, workers


_TAB_GAPS = "Gap Violations"
_TAB_OVERLAPS = "Overlapping Visuals"
_TAB_DUPLICATES = "Duplicate Layer"
_TAB_MISALIGN = "Row Misalignments"
_TAB_HSPACING = "Horizontal Spacing"
_TAB_FIX_PLAN = "Fix Plan"


def _detect_headless() -> str | None:
    """Try to construct a Tk root; on failure return a readable error message.

    Returns ``None`` when Tk works (display available); otherwise returns the
    error string the launcher should print to stderr before exiting (FR-025).
    """
    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover — stdlib should always import
        return f"tkinter is unavailable: {exc}"

    try:
        probe = tk.Tk()
    except tk.TclError as exc:
        return (
            f"no display available ({exc}). "
            f"Use the 'pbir_validator' CLI instead."
        )
    probe.destroy()
    return None


class App:
    """Owns the main window, toolbar state, and result-table tabs.

    Construction does NOT call mainloop — callers (or :func:`main`) decide
    when to start the event loop so tests can construct the App and inspect
    its widgets without entering an event loop.
    """

    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import filedialog, ttk

        self._tk = tk
        self._ttk = ttk
        self._filedialog = filedialog

        self.report_path: Path | None = None
        self.conf_path: Path | None = None
        self.last_result: controllers.ValidateResult | None = None

        self.root = tk.Tk()
        self.root.title("pbir-validator")
        self.root.geometry("960x600")

        self._build_menubar()
        self._build_toolbar()
        self._build_notebook()
        self._build_statusbar()

        self._set_action_buttons_enabled(False)
        self._set_status("Ready — pick a .pbip file or .Report folder to begin.")

    # -- Menu bar (US6) ---------------------------------------------------

    def _build_menubar(self) -> None:
        tk = self._tk
        self._menu = tk.Menu(self.root)
        self.root.config(menu=self._menu)
        file_menu = tk.Menu(self._menu, tearoff=False)
        self._menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open .pbip…", command=self._on_browse_pbip)
        file_menu.add_command(label="Open .Report folder…", command=self._on_browse_report)
        file_menu.add_separator()
        self._recents_menu = tk.Menu(file_menu, tearoff=False)
        file_menu.add_cascade(label="Recent reports", menu=self._recents_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        self._refresh_recents_menu()

    def _refresh_recents_menu(self) -> None:
        menu = self._recents_menu
        menu.delete(0, "end")
        entries = recents.load()
        if not entries:
            menu.add_command(label="(no recent reports)", state="disabled")
            return
        for path_str in entries:
            menu.add_command(
                label=path_str,
                command=lambda p=path_str: self._on_recent_chosen(p),
            )

    def _on_recent_chosen(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            widgets.show_error(
                self.root,
                "Report not found",
                f"This recent entry no longer exists:\n{path_str}\n\nIt has been removed from the list.",
            )
            # Removing = recording all *other* entries fresh.
            remaining = [p for p in recents.load() if p != path_str]
            from . import recents as _rec
            target = _rec.recents_path()
            try:
                import json as _json
                target.write_text(
                    _json.dumps({"recent": remaining}, indent=2), encoding="utf-8"
                )
            except OSError:
                pass
            self._refresh_recents_menu()
            return
        self.set_report(path)

    # -- Toolbar ----------------------------------------------------------

    def _build_toolbar(self) -> None:
        ttk = self._ttk
        bar = ttk.Frame(self.root, padding=(8, 6))
        bar.pack(side="top", fill="x")

        ttk.Button(bar, text="Browse .pbip…", command=self._on_browse_pbip).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(
            bar, text="Browse .Report folder…", command=self._on_browse_report
        ).pack(side="left", padx=4)

        self._path_label_var = self._tk.StringVar(value="(no report selected)")
        ttk.Label(bar, textvariable=self._path_label_var, foreground="#444").pack(
            side="left", padx=12
        )

        action_bar = ttk.Frame(self.root, padding=(8, 0))
        action_bar.pack(side="top", fill="x")
        self._btn_learn = ttk.Button(
            action_bar, text="Learn", command=self._on_learn
        )
        self._btn_validate = ttk.Button(
            action_bar, text="Validate", command=self._on_validate
        )
        self._btn_fix = ttk.Button(action_bar, text="Fix", command=self._on_fix)
        for b in (self._btn_learn, self._btn_validate, self._btn_fix):
            b.pack(side="left", padx=4, pady=(0, 6))

    # -- Notebook (6 tabs seeded up-front per FR-012) ---------------------

    def _build_notebook(self) -> None:
        ttk = self._ttk
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="both", expand=True, padx=8, pady=4)

        # Numeric column indices per tab (used for natural-numeric sort).
        # Severity column index: the cell whose absolute value drives the
        # row's green/yellow/red tag.
        self._gaps_table = self._build_tab(
            label=_TAB_GAPS,
            columns=controllers.GAP_COLUMNS,
            empty_message="No issues found",
            numeric_columns=frozenset({3, 4, 5}),  # expected/actual/deviation
            severity_kind="deviation",
            severity_column_index=5,  # deviation_px
        )
        self._overlaps_table = self._build_tab(
            label=_TAB_OVERLAPS,
            columns=controllers.OVERLAP_COLUMNS,
            empty_message="No overlapping visuals",
            numeric_columns=frozenset({3}),  # overlap_px
            severity_kind="overlap",
            severity_column_index=3,
        )
        self._duplicates_table = self._build_tab(
            label=_TAB_DUPLICATES,
            columns=controllers.DUPLICATE_COLUMNS,
            empty_message="No duplicate layers detected",
            numeric_columns=frozenset({4}),  # delta_y_px
            severity_kind=None,  # always-yellow tag set by caller below
            severity_column_index=None,
        )
        self._misalign_table = self._build_tab(
            label=_TAB_MISALIGN,
            columns=controllers.MISALIGNMENT_COLUMNS,
            empty_message="No issues found",
            numeric_columns=frozenset({1, 4, 5, 6}),
            severity_kind="deviation",
            severity_column_index=6,
        )
        self._hspacing_table = self._build_tab(
            label=_TAB_HSPACING,
            columns=controllers.HSPACING_COLUMNS,
            empty_message="No issues found",
            numeric_columns=frozenset({1, 5, 6, 7}),
            severity_kind="deviation",
            severity_column_index=7,
        )
        self._build_fix_plan_tab()

        # Right-click context menu binding for each result table.
        for table in (
            self._gaps_table,
            self._overlaps_table,
            self._duplicates_table,
            self._misalign_table,
            self._hspacing_table,
        ):
            self._bind_context_menu(table)

    def _build_tab(
        self,
        *,
        label: str,
        columns: tuple[str, ...],
        empty_message: str,
        numeric_columns: frozenset[int] = frozenset(),
        severity_kind: str | None = None,
        severity_column_index: int | None = None,
    ) -> widgets.ResultTable:
        ttk = self._ttk
        tab = ttk.Frame(self.notebook)
        table = widgets.ResultTable(
            tab,
            columns,
            empty_message=empty_message,
            sortable=True,
            filterable=True,
            numeric_columns=numeric_columns,
            severity_kind=severity_kind,
            severity_column_index=severity_column_index,
        )
        table.pack(side="top", fill="both", expand=True)
        export_bar = ttk.Frame(tab, padding=(4, 4))
        export_bar.pack(side="bottom", fill="x")
        widgets.make_export_button(
            export_bar, get_table=(lambda t=table: t)
        ).pack(side="right")
        self.notebook.add(tab, text=label)
        return table

    # -- Context menu (US2) ----------------------------------------------

    def _bind_context_menu(self, table: widgets.ResultTable) -> None:
        tk = self._tk
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(
            label="Open page in Power BI Desktop",
            command=lambda t=table: self._on_menu_open_in_pbi(t),
        )
        menu.add_command(
            label="Copy row",
            command=lambda t=table: self._on_menu_copy_row(t),
        )

        def on_right_click(event: object, t: widgets.ResultTable = table, m: object = menu) -> None:
            tree = t.tree
            iid = tree.identify_row(event.y)  # type: ignore[attr-defined]
            if iid:
                tree.selection_set(iid)
                m.tk_popup(event.x_root, event.y_root)  # type: ignore[attr-defined]

        table.tree.bind("<Button-3>", on_right_click)

    def _on_menu_open_in_pbi(self, table: widgets.ResultTable) -> None:
        if self.report_path is None:
            widgets.show_error(
                self.root, "No report loaded", "Load a report first."
            )
            return
        ok, msg = controllers.open_in_power_bi(self.report_path)
        if not ok:
            from tkinter import messagebox

            messagebox.showinfo(
                title="Cannot open in Power BI Desktop",
                message=msg,
                parent=self.root,
            )

    def _on_menu_copy_row(self, table: widgets.ResultTable) -> None:
        row = table.get_selected_row()
        if row is None:
            return
        text = controllers.row_to_clipboard_text(row)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _build_fix_plan_tab(self) -> None:
        """Fix Plan tab: scrollable list of ShiftCheckboxRow + summary + Apply.

        Stays empty until the user clicks Fix and a dry-run completes.
        """
        ttk = self._ttk
        tk = self._tk
        tab = ttk.Frame(self.notebook)

        # Top: summary label
        self._fix_summary_var = tk.StringVar(
            value="No fix plan yet — click Fix to compute one."
        )
        ttk.Label(
            tab, textvariable=self._fix_summary_var, padding=(8, 6), anchor="w"
        ).pack(side="top", fill="x")

        # Middle: scrollable canvas of ShiftCheckboxRow widgets
        scroll_holder = ttk.Frame(tab)
        scroll_holder.pack(side="top", fill="both", expand=True)
        self._fix_canvas = tk.Canvas(
            scroll_holder, highlightthickness=0, borderwidth=0
        )
        vsb = ttk.Scrollbar(
            scroll_holder, orient="vertical", command=self._fix_canvas.yview
        )
        self._fix_canvas.configure(yscrollcommand=vsb.set)
        self._fix_canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._fix_rows_frame = ttk.Frame(self._fix_canvas)
        self._fix_canvas_window = self._fix_canvas.create_window(
            (0, 0), window=self._fix_rows_frame, anchor="nw"
        )
        self._fix_rows_frame.bind(
            "<Configure>",
            lambda _e: self._fix_canvas.configure(
                scrollregion=self._fix_canvas.bbox("all")
            ),
        )

        # Bottom: Apply button + Export
        bottom = ttk.Frame(tab, padding=(4, 4))
        bottom.pack(side="bottom", fill="x")
        self._btn_apply = ttk.Button(
            bottom, text="Apply selected fixes", command=self._on_apply
        )
        self._btn_apply.pack(side="left", padx=4)
        self._btn_apply.state(["disabled"])

        # Export button uses a virtual ResultTable view of the current plan rows.
        self._fix_export_table = widgets.ResultTable(
            bottom, controllers.FIX_PLAN_COLUMNS, empty_message=""
        )
        # Don't pack — it's only used as a row provider for the export button.
        widgets.make_export_button(
            bottom,
            get_table=(lambda: self._fix_export_table),
            label="Export plan…",
        ).pack(side="right", padx=4)

        self._fix_rows: list = []  # list[ShiftCheckboxRow]
        self._fix_plan: controllers.FixPlan | None = None
        self.notebook.add(tab, text=_TAB_FIX_PLAN)

    # -- Status bar -------------------------------------------------------

    def _build_statusbar(self) -> None:
        ttk = self._ttk
        self._status_var = self._tk.StringVar(value="")
        bar = ttk.Frame(self.root, padding=(8, 4), relief="sunken")
        bar.pack(side="bottom", fill="x")
        ttk.Label(bar, textvariable=self._status_var, anchor="w").pack(
            side="left", fill="x", expand=True
        )

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)

    # -- Report selection (FR-002, FR-003, FR-004) ------------------------

    def _on_browse_pbip(self) -> None:
        path_str = self._filedialog.askopenfilename(
            parent=self.root,
            title="Select .pbip file",
            filetypes=[("Power BI Project", "*.pbip"), ("All files", "*.*")],
        )
        if path_str:
            self.set_report(Path(path_str))

    def _on_browse_report(self) -> None:
        path_str = self._filedialog.askdirectory(
            parent=self.root, title="Select .Report folder"
        )
        if path_str:
            self.set_report(Path(path_str))

    def set_report(self, path: Path) -> None:
        """Validate the user's selection and toggle action buttons (FR-004/005)."""
        from ..errors import NotAPbirError
        from ..reader import load_report

        try:
            report = load_report(path)
        except NotAPbirError as exc:
            self.report_path = None
            self.conf_path = None
            self._path_label_var.set("(no report selected)")
            self._set_action_buttons_enabled(False)
            widgets.show_error(self.root, "Invalid report", str(exc))
            self._set_status(f"Error: {exc}")
            return

        self.report_path = report.root
        self.conf_path = report.root / "conf.md"
        self._path_label_var.set(str(report.root))
        self._set_action_buttons_enabled(True)
        self._set_status(f"Loaded {report.root}. Click Validate to run checks.")
        # US6: record this path in the recents file and rebuild the menu.
        try:
            recents.record(str(report.root))
            self._refresh_recents_menu()
        except Exception:  # noqa: BLE001 — recents must never break the app
            pass

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        state = "!disabled" if enabled else "disabled"
        for b in (self._btn_learn, self._btn_validate, self._btn_fix):
            b.state([state])

    # -- Validate (T024) --------------------------------------------------

    def _on_validate(self) -> None:
        if self.report_path is None:
            widgets.show_error(
                self.root, "No report selected", "Pick a .pbip or .Report folder first."
            )
            return
        self._set_action_buttons_enabled(False)
        self._set_status("Validating…")

        report = self.report_path
        conf = self.conf_path

        workers.run_in_background(
            controllers.validate,
            report,
            conf,
            on_done=self._on_validate_done,
            on_error=self._on_validate_error,
            root=self.root,
        )

    def _on_validate_done(self, result: controllers.ValidateResult) -> None:
        self.last_result = result
        self._gaps_table.set_rows(controllers.gap_rows(result.gaps))
        self._overlaps_table.set_rows(controllers.overlap_rows(result.overlaps))
        self._duplicates_table.set_rows(
            controllers.duplicate_rows(result.duplicate_layers)
        )
        # Duplicate-layer rows are always tagged yellow regardless of values.
        from . import severity as _sev
        for iid in self._duplicates_table.tree.get_children():
            self._duplicates_table.tree.item(iid, tags=(_sev.SEV_YELLOW,))
        self._misalign_table.set_rows(
            controllers.misalignment_rows(result.misalignments)
        )
        self._hspacing_table.set_rows(controllers.h_spacing_rows(result.h_spacing))
        # Switch focus to Gap Violations tab
        self.notebook.select(0)
        self._set_action_buttons_enabled(True)
        self._set_status(
            f"Done — {len(result.gaps)} gaps, "
            f"{len(result.overlaps)} overlaps, "
            f"{len(result.duplicate_layers)} duplicates, "
            f"{len(result.misalignments)} misalignments, "
            f"{len(result.h_spacing)} h-spacing issues."
        )

    def _on_validate_error(self, exc: BaseException) -> None:
        self._set_action_buttons_enabled(True)
        widgets.show_error(self.root, "Validate failed", str(exc))
        self._set_status(f"Error: {exc}")

    # -- Learn (US2) ------------------------------------------------------

    def _on_learn(self) -> None:
        if self.report_path is None or self.conf_path is None:
            widgets.show_error(
                self.root, "No report selected", "Pick a .pbip or .Report folder first."
            )
            return

        choice = widgets.ask_manual_or_auto(self.root)
        if choice == "cancel":
            return

        if choice == "manual":
            # FR-008/FR-009: open existing conf.md, or surface "nothing to edit"
            if not self.conf_path.exists():
                widgets.show_error(
                    self.root,
                    "Nothing to edit",
                    f"No conf.md exists yet at:\n{self.conf_path}\n\n"
                    "Run Learn → No to generate one first.",
                )
                self._set_status("Manual edit cancelled — conf.md not found.")
                return
            try:
                editor.open_in_default_editor(self.conf_path)
            except editor.EditorLaunchError as exc:
                widgets.show_error(self.root, "Editor failed", str(exc))
                return
            self._set_status(
                f"Opened {self.conf_path} in default editor. "
                "Re-run Validate after saving."
            )
            return

        # auto mode → enumerate pages, pick one, regenerate conf.md
        try:
            pages = controllers.list_pages(self.report_path)
        except controllers.LearnError as exc:
            widgets.show_error(self.root, "Learn failed", str(exc))
            return

        page_id = widgets.ask_source_page(self.root, pages)
        if page_id is None:
            self._set_status("Learn cancelled.")
            return

        self._set_action_buttons_enabled(False)
        self._set_status("Learning…")
        report = self.report_path
        conf = self.conf_path

        workers.run_in_background(
            controllers.learn,
            report,
            conf,
            "auto",
            page_id,
            on_done=self._on_learn_done,
            on_error=self._on_learn_error,
            root=self.root,
        )

    def _on_learn_done(self, result: controllers.LearnResult) -> None:
        self._set_action_buttons_enabled(True)
        self._set_status(
            f"Wrote {result.rule_count} rule(s) to {result.conf_path}. "
            "Click Validate to check the report."
        )
        try:
            editor.open_in_default_editor(result.conf_path)
        except editor.EditorLaunchError:
            pass  # not fatal — user will see the status bar

    def _on_learn_error(self, exc: BaseException) -> None:
        self._set_action_buttons_enabled(True)
        widgets.show_error(self.root, "Learn failed", str(exc))
        self._set_status(f"Error: {exc}")

    # -- Fix (US3) --------------------------------------------------------

    def _on_fix(self) -> None:
        if self.report_path is None or self.conf_path is None:
            widgets.show_error(
                self.root, "No report selected", "Pick a .pbip or .Report folder first."
            )
            return
        if not self.conf_path.exists():
            widgets.show_error(
                self.root,
                "No conf.md",
                f"conf.md is required for Fix. Run Learn first.\nExpected at: {self.conf_path}",
            )
            return

        self._set_action_buttons_enabled(False)
        self._set_status("Planning fixes (dry-run)…")
        report = self.report_path
        conf = self.conf_path

        workers.run_in_background(
            controllers.fix_plan,
            report,
            conf,
            on_done=self._on_fix_plan_done,
            on_error=self._on_fix_error,
            root=self.root,
        )

    def _on_fix_plan_done(self, plan: controllers.FixPlan) -> None:
        self._set_action_buttons_enabled(True)
        self._fix_plan = plan
        # Repopulate scrollable list
        for row in self._fix_rows:
            row.destroy()
        self._fix_rows = []

        if not plan.shifts:
            self._fix_summary_var.set(
                f"No fixes needed. {len(plan.unfixable)} unfixable violation(s)."
            )
            self._btn_apply.state(["disabled"])
            self._fix_export_table.set_rows([])
            self.notebook.select(5)
            self._set_status("Done — no fixes needed.")
            return

        for ps in plan.shifts:
            row = widgets.ShiftCheckboxRow(
                self._fix_rows_frame,
                shift_id=ps.id,
                page_id=ps.shift.page_id,
                visual_id=ps.shift.visual_id,
                delta_y=ps.shift.delta_y,
                old_y=ps.shift.old_y,
                new_y=ps.shift.new_y,
                group_member=ps.shift.group_member,
                on_toggle=self._refresh_fix_summary,
            )
            row.pack(fill="x", anchor="w", padx=4, pady=1)
            self._fix_rows.append(row)

        self._fix_export_table.set_rows(controllers.fix_plan_rows(plan))
        self._btn_apply.state(["!disabled"])
        self.notebook.select(5)
        self._refresh_fix_summary()
        self._set_status(
            f"Fix dry-run complete — {len(plan.shifts)} shift(s). "
            "Uncheck any that are intentional, then click Apply."
        )

    def _refresh_fix_summary(self) -> None:
        if self._fix_plan is None:
            return
        total = len(self._fix_rows)
        selected = sum(1 for r in self._fix_rows if r.selected)
        unfix = len(self._fix_plan.unfixable)
        self._fix_summary_var.set(
            f"{total} proposed shift(s), {selected} selected"
            + (f"; {unfix} unfixable" if unfix else "")
        )
        if selected:
            self._btn_apply.state(["!disabled"])
        else:
            self._btn_apply.state(["disabled"])

    def _on_apply(self) -> None:
        if self._fix_plan is None or self.report_path is None:
            return
        selected_ids = {r.shift_id for r in self._fix_rows if r.selected}
        if not selected_ids:
            widgets.show_error(
                self.root, "Nothing to apply", "All shifts are unchecked."
            )
            return

        total = len(self._fix_rows)
        chosen = len(selected_ids)
        skipped = total - chosen

        self._set_action_buttons_enabled(False)
        self._btn_apply.state(["disabled"])
        self._set_status(f"Applying {chosen} of {total} shift(s)…")

        report = self.report_path
        plan = self._fix_plan

        def _on_apply_done(applied: int) -> None:
            # FR-019 invalidation: clear the checklist, post summary, re-validate
            for row in self._fix_rows:
                row.destroy()
            self._fix_rows = []
            self._fix_export_table.set_rows([])
            self._fix_plan = None
            self._fix_summary_var.set(
                f"{applied} applied, {skipped} skipped, "
                "0 remaining (re-run Fix for a fresh plan)."
            )
            self._set_status("Re-validating after fix…")
            # Auto-rerun validate (FR-019)
            workers.run_in_background(
                controllers.validate,
                report,
                self.conf_path,
                on_done=self._on_validate_done,
                on_error=self._on_validate_error,
                root=self.root,
            )

        def _on_apply_err(exc: BaseException) -> None:
            self._set_action_buttons_enabled(True)
            self._btn_apply.state(["!disabled"])
            widgets.show_error(self.root, "Apply failed", str(exc))
            self._set_status(f"Error: {exc}")

        workers.run_in_background(
            controllers.fix_apply,
            report,
            plan,
            selected_ids,
            on_done=_on_apply_done,
            on_error=_on_apply_err,
            root=self.root,
        )

    def _on_fix_error(self, exc: BaseException) -> None:
        self._set_action_buttons_enabled(True)
        widgets.show_error(self.root, "Fix failed", str(exc))
        self._set_status(f"Error: {exc}")


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``pbir_validator-gui`` console script."""
    headless_msg = _detect_headless()
    if headless_msg is not None:
        print(f"pbir_validator-gui: {headless_msg}", file=sys.stderr)
        return 2

    app = App()
    app.root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


# Public re-export so ``from pbir_validator.gui.app import _Any`` is unnecessary.
__all__ = ["App", "main"]
