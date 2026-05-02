"""Tk main window for pbir_validator-gui (FR-001, FR-002, FR-005, FR-012).

Headless detection (FR-025) probes Tk before any window is shown.
Long-running operations run on a background thread via :mod:`.workers`
so the main loop never blocks (FR-023).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import controllers, editor, grade, panel, profiles, recents, undo, watch, widgets, workers


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

        # Power-feature state (005)
        state = recents.load_state()
        self._panel_visible: bool = bool(state.get("side_panel_visible", True))
        self._profile_name: str = str(state.get("profile") or "Standard")
        self._watch_on: bool = False
        self._watch_state: dict[Path, float] = {}
        self._watch_last_check_at: float = 0.0
        self._pending_profile: str | None = None
        self._visuals_by_id: dict[str, object] = {}
        self._current_tab_columns: tuple[str, ...] = ()
        self._current_tab_rows: list[tuple[object, ...]] = []

        self.root = tk.Tk()
        self.root.title("pbir-validator")
        self.root.geometry("1280x720")

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
        entries = recents.load_paths()
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
            # Removing = preserving the full state but rewriting "recent".
            from . import recents as _rec
            state = _rec.load_state()
            state["recent"] = [p for p in state["recent"] if p != path_str]
            target = _rec.recents_path()
            try:
                import json as _json
                target.write_text(
                    _json.dumps(state, indent=2), encoding="utf-8"
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

        # --- 005 Power Features toolbar additions ---
        self._btn_export_zip = ttk.Button(
            action_bar, text="Export all (CSV ZIP)", command=self._on_export_zip
        )
        self._btn_export_zip.pack(side="left", padx=4, pady=(0, 6))
        self._btn_export_zip.state(["disabled"])

        self._watch_var = self._tk.BooleanVar(value=False)
        self._btn_watch = ttk.Checkbutton(
            action_bar,
            text="Watch",
            variable=self._watch_var,
            command=self._on_toggle_watch,
        )
        self._btn_watch.pack(side="left", padx=4, pady=(0, 6))
        self._btn_watch.state(["disabled"])

        self._btn_undo = ttk.Button(
            action_bar, text="Undo last fix", command=self._on_undo_last
        )
        self._btn_undo.pack(side="left", padx=4, pady=(0, 6))
        self._btn_undo.state(["disabled"])

        self._btn_panel = ttk.Button(
            action_bar,
            text="Hide panel" if self._panel_visible else "Show panel",
            command=self._on_toggle_panel,
        )
        self._btn_panel.pack(side="left", padx=4, pady=(0, 6))

        # Profile combobox — populated lazily on report load.
        ttk.Label(action_bar, text="Profile:").pack(
            side="left", padx=(12, 2), pady=(0, 6)
        )
        self._profile_var = self._tk.StringVar(value=self._profile_name)
        self._profile_combo = ttk.Combobox(
            action_bar,
            textvariable=self._profile_var,
            state="readonly",
            width=16,
        )
        self._profile_combo.pack(side="left", padx=2, pady=(0, 6))
        self._profile_combo.bind(
            "<<ComboboxSelected>>", self._on_profile_changed
        )
        self._refresh_profile_combobox()

        # Grade label (FR-033)
        self._grade_var = self._tk.StringVar(value="–")
        self._grade_label = ttk.Label(
            action_bar,
            textvariable=self._grade_var,
            foreground=grade.color_for(""),
            font=("TkDefaultFont", 12, "bold"),
            padding=(8, 0),
        )
        self._grade_label.pack(side="right", padx=8, pady=(0, 6))

    # -- Notebook (6 tabs seeded up-front per FR-012) ---------------------

    def _build_notebook(self) -> None:
        ttk = self._ttk
        tk = self._tk

        # Wrap notebook + side panel in a PanedWindow (US5, FR-040).
        self._paned = ttk.PanedWindow(self.root, orient="horizontal")
        self._paned.pack(side="top", fill="both", expand=True, padx=8, pady=4)

        nb_frame = ttk.Frame(self._paned)
        self.notebook = ttk.Notebook(nb_frame)
        self.notebook.pack(fill="both", expand=True)
        self._paned.add(nb_frame, weight=3)

        # Side panel (right) — read-only Text widget for visual context.
        self._panel_frame = ttk.Frame(self._paned, width=360)
        ttk.Label(
            self._panel_frame,
            text="Visual context",
            padding=(8, 6),
            anchor="w",
        ).pack(side="top", fill="x")
        self._side_panel_text = widgets.make_readonly_text(self._panel_frame)
        self._side_panel_text.pack(side="top", fill="both", expand=True, padx=4, pady=4)
        self._side_panel_set("(select a row in any issue tab to drill in)")

        if self._panel_visible:
            self._paned.add(self._panel_frame, weight=1)
        # Default 360 px sash placement once the window has computed sizes.
        self.root.after(50, self._set_default_sash)

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

        # Right-click context menu + double-click open + side-panel select.
        for table, columns in (
            (self._gaps_table, controllers.GAP_COLUMNS),
            (self._overlaps_table, controllers.OVERLAP_COLUMNS),
            (self._duplicates_table, controllers.DUPLICATE_COLUMNS),
            (self._misalign_table, controllers.MISALIGNMENT_COLUMNS),
            (self._hspacing_table, controllers.HSPACING_COLUMNS),
        ):
            self._bind_context_menu(table)
            self._bind_double_click_open(table)
            self._bind_side_panel_select(table, columns)

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
        # 005: reset watch state, refresh profiles dropdown, refresh undo button.
        self._watch_state = {}
        try:
            self._refresh_profile_combobox()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._refresh_undo_button()
        except Exception:  # noqa: BLE001
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

        # US6: profile dropdown overrides report-root conf.md when not "Report-default".
        try:
            rules = profiles.load_profile(self._profile_name, report)
        except Exception:  # noqa: BLE001
            rules = None

        def _do_validate():
            return controllers.validate(report, conf, rules=rules)

        workers.run_in_background(
            _do_validate,
            on_done=self._on_validate_done,
            on_error=self._on_validate_error,
            root=self.root,
        )

    def _on_validate_done(self, result: controllers.ValidateResult) -> None:
        self.last_result = result
        # Refresh the visuals_by_id index for the side panel (US5).
        try:
            from ..reader import load_report
            report_obj = load_report(self.report_path) if self.report_path else None
            if report_obj is not None:
                self._visuals_by_id = {
                    v.id: v for page in report_obj.pages for v in page.visuals
                }
        except Exception:  # noqa: BLE001
            self._visuals_by_id = {}

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

        # US4: compute grade from the result.
        counts = {
            "gaps": len(result.gaps),
            "overlaps": len(result.overlaps),
            "duplicate_layers": len(result.duplicate_layers),
            "misalignments": len(result.misalignments),
            "h_spacing": len(result.h_spacing),
        }
        letter, _score = grade.compute(counts)
        self._grade_var.set(letter)
        try:
            self._grade_label.configure(foreground=grade.color_for(letter))
        except Exception:  # noqa: BLE001
            pass

        # US2: enable Export-all once we have results.
        try:
            self._btn_export_zip.state(["!disabled"])
        except Exception:  # noqa: BLE001
            pass

        # US3: now that a report is loaded, enable Watch toggle.
        try:
            self._btn_watch.state(["!disabled"])
        except Exception:  # noqa: BLE001
            pass

        # US7: refresh undo button state.
        self._refresh_undo_button()

        # FR-026: re-snapshot watch baseline so this run's writes don't re-fire.
        self._refresh_watch_baseline()

        self._set_status(
            f"Done — {len(result.gaps)} gaps, "
            f"{len(result.overlaps)} overlaps, "
            f"{len(result.duplicate_layers)} duplicates, "
            f"{len(result.misalignments)} misalignments, "
            f"{len(result.h_spacing)} h-spacing issues. [{letter}]"
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
            # US7: a fix was just applied → undo backup now exists.
            try:
                self._refresh_undo_button()
            except Exception:  # noqa: BLE001
                pass
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

    # =====================================================================
    # 005 Power Features — handlers
    # =====================================================================

    # ---- Side panel (US5) -----------------------------------------------

    def _set_default_sash(self) -> None:
        """Place the PanedWindow sash so the right pane is ~360 px wide."""
        try:
            total = self._paned.winfo_width()
            if total > 400 and self._panel_visible:
                self._paned.sashpos(0, max(total - 360, 200))
        except Exception:  # noqa: BLE001 — Tk geometry quirks are non-fatal
            pass

    def _side_panel_set(self, text: str) -> None:
        """Replace the side-panel text content (read-only Text widget)."""
        w = getattr(self, "_side_panel_text", None)
        if w is None:
            return
        try:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.insert("1.0", text)
            w.configure(state="disabled")
        except Exception:  # noqa: BLE001
            pass

    def _on_toggle_panel(self) -> None:
        self._panel_visible = not self._panel_visible
        if self._panel_visible:
            try:
                self._paned.add(self._panel_frame, weight=1)
            except Exception:  # noqa: BLE001
                pass
            self._btn_panel.configure(text="Hide panel")
            self.root.after(50, self._set_default_sash)
        else:
            try:
                self._paned.forget(self._panel_frame)
            except Exception:  # noqa: BLE001
                pass
            self._btn_panel.configure(text="Show panel")
        try:
            recents.record(side_panel_visible=self._panel_visible)
        except Exception:  # noqa: BLE001 — recents must never break the app
            pass

    def _bind_side_panel_select(
        self, table: widgets.ResultTable, columns: tuple[str, ...]
    ) -> None:
        """Populate the side panel from the focused row in this table."""
        def _on_select(_event: object, t: widgets.ResultTable = table, cols: tuple[str, ...] = columns) -> None:
            if not self._panel_visible:
                return
            tree = t.tree
            iid = tree.focus()
            if not iid:
                self._side_panel_set("(select a row in any issue tab to drill in)")
                return
            try:
                idx = tree.index(iid)
            except Exception:  # noqa: BLE001
                return
            rows = t.get_rows()
            if not (0 <= idx < len(rows)):
                return
            try:
                visuals = panel.find_visual_for_row(
                    rows, idx, cols, self._visuals_by_id
                )
            except Exception:  # noqa: BLE001
                visuals = []
            if not visuals:
                self._side_panel_set("(no underlying visual found for this row)")
                return
            blocks: list[str] = []
            for v in visuals:
                ctx = panel.extract_visual_context(v)
                lines = [
                    f"id:               {ctx['id']}",
                    f"page_id:          {ctx['page_id']}",
                    f"page_display:     {ctx['page_display_name']}",
                    f"visual_type:      {ctx['visual_type']}",
                    f"x, y:             {ctx['x']}, {ctx['y']}",
                    f"width x height:   {ctx['width']} x {ctx['height']}",
                    f"parent_group:     {ctx['parent_group']}",
                    "",
                    "raw JSON:",
                    ctx["raw_json"],
                ]
                blocks.append("\n".join(lines))
            self._side_panel_set("\n\n--- next visual ---\n\n".join(blocks))

        table.tree.bind("<<TreeviewSelect>>", _on_select, add="+")

    # ---- Double-click open (US1) ----------------------------------------

    def _bind_double_click_open(self, table: widgets.ResultTable) -> None:
        def _on_dbl(_event: object) -> None:
            if self.report_path is None:
                return
            ok, msg = controllers.open_in_power_bi(self.report_path)
            if not ok:
                from tkinter import messagebox

                messagebox.showinfo(
                    title="Cannot open in Power BI Desktop",
                    message=msg,
                    parent=self.root,
                )

        table.tree.bind("<Double-Button-1>", _on_dbl, add="+")

    # ---- Export all (CSV ZIP) (US2) -------------------------------------

    def _on_export_zip(self) -> None:
        if self.last_result is None:
            widgets.show_error(self.root, "No results", "Run Validate first.")
            return
        from datetime import datetime

        report_basename = (
            self.report_path.name if self.report_path is not None else "report"
        )
        default_name = (
            f"{report_basename}_validation_"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        )
        dest = self._filedialog.asksaveasfilename(
            parent=self.root,
            title="Export all (CSV ZIP)",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
        )
        if not dest:
            return
        try:
            controllers.export_all_zip(
                self.last_result, getattr(self, "_fix_plan", None), Path(dest)
            )
        except controllers.NothingToExportError:
            from tkinter import messagebox

            messagebox.showinfo(
                title="Nothing to export",
                message="All result tabs are empty.",
                parent=self.root,
            )
            return
        except OSError as exc:
            widgets.show_error(self.root, "Export failed", str(exc))
            return
        self._set_status(f"Exported all tabs to {dest}")

    # ---- Watch mode (US3) -----------------------------------------------

    def _on_toggle_watch(self) -> None:
        self._watch_on = bool(self._watch_var.get())
        if self._watch_on and self.report_path is not None:
            try:
                self._watch_state = watch.snapshot_mtimes(self.report_path)
            except Exception:  # noqa: BLE001
                self._watch_state = {}
            self._set_status("Watching: ON (last check just now)")
            self.root.after(2000, self._watch_tick)
        else:
            self._set_status("Watch: OFF")

    def _watch_tick(self) -> None:
        if not self._watch_on or self.report_path is None:
            return
        try:
            current = watch.snapshot_mtimes(self.report_path)
        except Exception:  # noqa: BLE001 — non-fatal per FR-025
            current = {}
        if current and watch.diff_mtimes(self._watch_state, current):
            self._watch_state = current
            self._set_status("Watching: ON (changes detected — re-validating…)")
            self._on_validate()  # _on_validate_done resets the snapshot anyway
        else:
            self._watch_state = current or self._watch_state
            self._set_status("Watching: ON (last check just now)")
        self.root.after(2000, self._watch_tick)

    def _refresh_watch_baseline(self) -> None:
        """Re-snapshot mtimes after every Validate run (FR-026)."""
        if self.report_path is None:
            return
        try:
            self._watch_state = watch.snapshot_mtimes(self.report_path)
        except Exception:  # noqa: BLE001
            pass

    # ---- Profile dropdown (US6) -----------------------------------------

    def _refresh_profile_combobox(self) -> None:
        try:
            avail = profiles.list_profiles(self.report_path)
        except Exception:  # noqa: BLE001
            avail = {"Standard": Path("standard.md")}
        # Pin order: Standard, Strict, Relaxed, Report-default (when present)
        ordered: list[str] = []
        for name in ("Standard", "Strict", "Relaxed", "Report-default"):
            if name in avail:
                ordered.append(name)
        self._profile_combo["values"] = ordered
        if self._profile_name not in ordered:
            self._profile_name = "Standard"
            self._profile_var.set("Standard")

    def _on_profile_changed(self, _event: object = None) -> None:
        new_name = self._profile_var.get()
        if not new_name:
            return
        self._profile_name = new_name
        try:
            recents.record(profile=new_name)
        except Exception:  # noqa: BLE001
            pass
        if self.report_path is not None:
            self._on_validate()

    # ---- Undo last fix (US7) --------------------------------------------

    def _on_undo_last(self) -> None:
        if self.report_path is None:
            return
        ok, msg, _modified = undo.restore_last_fix(self.report_path)
        if not ok:
            widgets.show_error(self.root, "Undo failed", msg)
            return
        self._set_status(f"Undo applied — {msg}")
        self._refresh_undo_button()
        # Re-run Validate to refresh results
        self._on_validate()

    def _refresh_undo_button(self) -> None:
        try:
            present = (
                self.report_path is not None
                and undo.has_backup(self.report_path)
            )
        except Exception:  # noqa: BLE001
            present = False
        if present:
            self._btn_undo.state(["!disabled"])
        else:
            self._btn_undo.state(["disabled"])


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
