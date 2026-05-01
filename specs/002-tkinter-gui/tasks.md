---
description: "Task list for feature 002-tkinter-gui (Tkinter GUI for pbir-validator)"
---

# Tasks: Tkinter GUI for pbir-validator

**Input**: Design documents from `specs/002-tkinter-gui/`
**Prerequisites**: plan.md, spec.md (5 clarifications resolved), research.md, data-model.md, contracts/cli.md, contracts/gui-flows.md, quickstart.md
**Branch**: `002-tkinter-gui`

**Tests**: Included for non-GUI modules only (workers, export, editor, controllers). GUI rendering is exercised by a single headless-aware smoke test (`pytest.importorskip("tkinter")`, skip when no display).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different files, no dependencies on incomplete tasks → can run in parallel
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish phases have no story label)
- All paths are relative to repo root (`pbib validator tool/`)

## Path Conventions

- Source package: `pbir_validator/` (existing) and new sub-package `pbir_validator/gui/`
- Tests: `tests/` (pytest)
- Config: `pyproject.toml` at repo root
- Specs/docs: `specs/002-tkinter-gui/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the GUI sub-package skeleton and register the new console script entry point. No behavior yet.

- [X] T001 Add `pbir_validator-gui = "pbir_validator.gui.app:main"` to `[project.scripts]` in `pyproject.toml`
- [X] T002 [P] Create empty package init at `pbir_validator/gui/__init__.py` exposing `__all__ = ["app"]`
- [X] T003 [P] Create empty module stub `pbir_validator/gui/app.py` with a `def main() -> int:` placeholder returning `0`
- [X] T004 [P] Create empty module stub `pbir_validator/gui/widgets.py`
- [X] T005 [P] Create empty module stub `pbir_validator/gui/workers.py`
- [X] T006 [P] Create empty module stub `pbir_validator/gui/controllers.py`
- [X] T007 [P] Create empty module stub `pbir_validator/gui/export.py`
- [X] T008 [P] Create empty module stub `pbir_validator/gui/editor.py`
- [X] T009 Run `pip install -e .` (or equivalent) and confirm both `pbir_validator` and `pbir_validator-gui` console scripts resolve; record outcome in commit message

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared GUI infrastructure (headless detection, threading/queue plumbing, base widgets, export, editor handoff) that all three user stories depend on.

**⚠️ CRITICAL**: No user-story phase can begin until Phase 2 is complete.

- [X] T010 Implement headless detection in `pbir_validator/gui/app.py` (FR-025): probe `tkinter.Tk()` inside try/except, on failure print a one-line readable message to stderr and `return 2` from `main()` before any window is shown
- [X] T011 Implement main window factory in `pbir_validator/gui/app.py`: create `Tk` root, set title `pbir-validator`, build top toolbar (Browse `.pbip` file, Browse `.Report` folder, three action buttons Learn/Validate/Fix), and a `ttk.Notebook` seeded with all **four** tabs (Gap Violations, Row Misalignments, Horizontal Spacing, Fix Plan) per FR-012, each tab initially showing an empty-state label. Expose `App` class holding state (`report_path`, `conf_path`, last results) and an `App.set_report(path)` method that validates the selection via `pbir_validator.reader.load_report` (FR-003, FR-004) and toggles the three action buttons enabled/disabled accordingly (FR-005); validation errors are surfaced via `widgets.show_error`
- [X] T012 [P] Implement threading + queue plumbing in `pbir_validator/gui/workers.py` (FR-023): `run_in_background(target, *args, on_done, on_error, queue, root)` using `threading.Thread`, `queue.Queue`, and `root.after(50, drain)`; ensure exceptions in worker thread are funneled to `on_error` on the Tk thread
- [X] T013 [P] Implement export module in `pbir_validator/gui/export.py`: `write_csv(rows, path)` and `write_json(rows, path)` accepting list-of-dicts; CSV is the default (FR-013a). Pure stdlib (`csv`, `json`); no Tk imports so it is unit-testable
- [X] T014 [P] Implement editor handoff in `pbir_validator/gui/editor.py`: `open_in_default_editor(path)` using `os.startfile` on Windows, `subprocess.run(["open", path])` on Darwin, `subprocess.run(["xdg-open", path])` elsewhere; raise `EditorLaunchError` (defined here) on failure
- [X] T015 [P] Implement base result-table widget in `pbir_validator/gui/widgets.py`: `ResultTable(parent, columns)` wrapping `ttk.Treeview` with vertical scrollbar, `set_rows(rows)`, `clear()`, and an empty-state label ("No issues found") swapped in when `rows == []`
- [X] T016 [P] Implement error-display helper in `pbir_validator/gui/widgets.py`: `show_error(parent, title, message)` thin wrapper over `tkinter.messagebox.showerror` plus a status-bar label setter on the main window
- [X] T017 [P] Implement export-button factory in `pbir_validator/gui/widgets.py`: `make_export_button(parent, get_rows, default_format="csv")` that opens an `asksaveasfilename` dialog filtered to `*.csv` / `*.json`, dispatches to `pbir_validator.gui.export`, and reports success via the status bar
- [X] T018 [P] Unit tests for workers in `tests/test_gui_workers.py`: assert that a successful target invokes `on_done` with its return value, an exception target invokes `on_error` with the exception, and the Tk thread is never blocked (use a fake `root` that records `after` calls)
- [X] T019 [P] Unit tests for export in `tests/test_gui_export.py`: round-trip CSV and JSON for sample rows; verify CSV header order is stable and JSON is `indent=2` UTF-8
- [X] T020 [P] Unit tests for editor handoff in `tests/test_gui_editor.py`: monkeypatch `os.startfile`/`subprocess.run` per platform and assert correct dispatch; assert `EditorLaunchError` raised when underlying call fails

**Checkpoint**: Foundation ready — user-story phases can now begin.

---

## Phase 3: User Story 1 — Validate a report and review issues visually (Priority: P1) 🎯 MVP

**Goal**: User launches the GUI, browses to a `.Report` folder, clicks **Validate**, and sees three populated result tabs (Gaps, Misalignments, Horizontal Spacing) plus per-tab Export buttons. Read-only.

**Independent Test**: Run `pbir_validator-gui`, browse to `M365 E3 Targeted Promo Tenants Dashboard Channel.Report`, click Validate, confirm three tabs render rows for the known report and clicking Export… on each tab writes a CSV file matching the row count.

### Tests for User Story 1

- [X] T021 [P] [US1] Unit tests for validate controller in `tests/test_gui_controllers_validate.py`: mock `analyzer`/`validator` calls, assert returned payload has the three result lists keyed `gaps`, `misalignments`, `h_spacing`, and that any underlying exception is re-raised as `ValidateError` carrying the original message

### Implementation for User Story 1

- [X] T022 [US1] Implement `validate(report_path: Path, conf_path: Path | None) -> ValidateResult` in `pbir_validator/gui/controllers.py`: dataclass `ValidateResult` with `gaps`, `misalignments`, `h_spacing` lists; reuses `pbir_validator.reader`, `pbir_validator.analyzer`, `pbir_validator.validator`; pure function, no Tk imports
- [X] T023 [US1] Wire **Browse `.pbip` file** and **Browse `.Report` folder** dialogs in `pbir_validator/gui/app.py` per FR-002: use `filedialog.askopenfilename(filetypes=[("Power BI Project", "*.pbip")])` for the `.pbip` button and `filedialog.askdirectory()` for the `.Report` button; both feed into `App.set_report(path)` (T011) which auto-detects the input type and resolves a `.pbip` selection to its sibling `.Report` folder via existing reader logic (FR-003); persist the resolved report path and update the toolbar label. The conf.md path is derived as `<report>/conf.md` by default — no separate Browse-conf button
- [X] T024 [US1] Wire **Validate** button in `pbir_validator/gui/app.py` to dispatch `controllers.validate` through `workers.run_in_background`; on success populate three notebook tabs, on error call `widgets.show_error`
- [X] T025 [US1] Populate the three Validate tabs (already seeded by T011) in `pbir_validator/gui/app.py` using `widgets.ResultTable`: tab "Gap Violations" (columns: page, visual_a, visual_b, axis, gap_px), tab "Row Misalignments" (columns: page, group, visual, axis, delta_px), tab "Horizontal Spacing" (columns: page, row, visuals, expected, actual_px); show "No issues found" empty-state when list is empty. The Fix Plan tab is left in its empty state until US3 ships
- [X] T026 [US1] Attach per-tab **Export…** buttons in `pbir_validator/gui/app.py` using `widgets.make_export_button` (CSV default, JSON optional via the save-dialog filter) — **four** buttons, one per tab including Fix Plan, each bound to its own `get_rows`. The Fix Plan tab's Export button is disabled until that tab has rows (US3 wires the row source in T038)
- [X] T027 [US1] Add a status-bar line at the bottom of the main window in `pbir_validator/gui/app.py` showing "Ready" / "Validating…" / "Done — N gaps, M misalignments, K h-spacing issues" / error text

**Checkpoint**: US1 fully functional — MVP can ship here.

---

## Phase 4: User Story 2 — Generate or hand-edit conf.md via Learn mode (Priority: P2)

**Goal**: User clicks **Learn**, is asked whether they want to hand-edit the conf first; "Yes" opens conf.md in the OS default editor and waits for the user to confirm; "No" reveals a page dropdown so the user picks the source page, then `learner.learn()` runs and the resulting conf.md is opened for review.

**Independent Test**: Click Learn on a fresh report, choose "Yes" → confirm conf.md opens in Notepad/VS Code and the dialog stays modal; close, click Learn again, choose "No" → dropdown lists discoverable pages, pick one, click Confirm → conf.md is regenerated and opened.

### Tests for User Story 2

- [X] T028 [P] [US2] Unit tests for learn controller in `tests/test_gui_controllers_learn.py`: mock `learner.learn`; assert "manual" mode short-circuits without calling `learner.learn`, "auto" mode passes the chosen `page_id` through, and a missing report path raises `LearnError`

### Implementation for User Story 2

- [X] T029 [US2] Implement `learn(report_path: Path, conf_path: Path, mode: Literal["manual","auto"], page_id: str | None) -> Path` in `pbir_validator/gui/controllers.py`: in "manual" mode just returns the conf path; in "auto" mode calls `pbir_validator.learner.learn` and returns the written conf path; raises `LearnError` on failure
- [X] T030 [US2] Implement manual-edit prompt dialog in `pbir_validator/gui/widgets.py`: `ask_manual_or_auto(parent) -> Literal["manual","auto","cancel"]` using a `Toplevel` modal with three buttons (Yes / No / Cancel) and the prompt text from contracts/gui-flows.md
- [X] T031 [US2] Implement page-dropdown sub-dialog in `pbir_validator/gui/widgets.py`: `ask_source_page(parent, pages: list[tuple[str,str]]) -> str | None` showing a `ttk.Combobox` of `display_name → page_id`, returns selected `page_id` or `None` on cancel; only invoked when the user picked "No" in T030
- [X] T032 [US2] Wire **Learn** button in `pbir_validator/gui/app.py`: validate report path is set; call T030; if "manual" → check `conf_path.exists()` first — if missing, route through `widgets.show_error` with the FR-009 "nothing to edit" message and return to Idle without crashing; if present, call `editor.open_in_default_editor(conf_path)` and show a follow-up "Done editing?" confirm dialog; if "auto" → enumerate pages via `pbir_validator.reader`, call T031, then dispatch `controllers.learn` through `workers.run_in_background`; on completion open conf.md in the default editor and refresh status bar

**Checkpoint**: US2 functional independently of US3.

---

## Phase 5: User Story 3 — Apply fixes selectively with a dry-run checklist (Priority: P3)

**Goal**: User clicks **Fix**, sees a "Fix Plan" tab with one row per proposed shift (visual, axis, delta_px, reason), each row has a checkbox (default checked, FR per clarification: per-shift opt-out). User unchecks unwanted shifts, clicks **Apply selected fixes**; the button is disabled when zero rows are checked. After Apply, validate is automatically re-run and the three US1 tabs refresh.

**Independent Test**: With a known report having ≥3 fixable shifts, click Fix → Fix Plan tab populates with 3 checked rows + summary line; uncheck one; Apply selected fixes → only 2 shifts written, post-apply re-validate shows the unchecked issue still present and the two fixed issues gone.

### Tests for User Story 3

- [X] T033 [P] [US3] Unit tests for fix controller dry-run in `tests/test_gui_controllers_fix_dryrun.py`: mock `fixer.plan`; assert `controllers.fix_plan(report_path, conf_path)` returns a `FixPlan` dataclass listing all proposed shifts with stable IDs and a `summary` string
- [X] T034 [P] [US3] Unit tests for fix controller apply in `tests/test_gui_controllers_fix_apply.py`: mock `fixer.apply`; assert `controllers.fix_apply(plan, selected_ids)` filters the plan to only the selected IDs, returns the count of applied shifts, and raises `FixError` when `selected_ids` is empty

### Implementation for User Story 3

- [X] T035 [US3] Implement `fix_plan(report_path: Path, conf_path: Path) -> FixPlan` in `pbir_validator/gui/controllers.py` calling `pbir_validator.fixer` in dry-run mode; `FixPlan` dataclass holds `shifts: list[ProposedShift]` and `summary: str`; each `ProposedShift` carries a stable `id`
- [X] T036 [US3] Implement `fix_apply(plan: FixPlan, selected_ids: set[str]) -> int` in `pbir_validator/gui/controllers.py`: validates non-empty, calls `pbir_validator.fixer` apply path on the filtered subset, returns count of applied shifts
- [X] T037 [US3] Implement `ShiftCheckboxRow` widget in `pbir_validator/gui/widgets.py`: a `ttk.Frame` row with a `ttk.Checkbutton` (default selected) plus labels for visual/axis/delta/reason; exposes `selected: bool` and an `on_toggle` callback
- [X] T038 [US3] Add **Fix Plan** tab to the notebook in `pbir_validator/gui/app.py`: scrollable container of `ShiftCheckboxRow`s plus a top summary line ("N proposed shifts, X selected") that updates live as the user toggles checkboxes
- [X] T039 [US3] Add **Apply selected fixes** button in `pbir_validator/gui/app.py` on the Fix Plan tab: enabled only when ≥1 row is checked; on click dispatch `controllers.fix_apply` through `workers.run_in_background`; on success show status "Applied X of N shifts"
- [X] T040 [US3] Implement post-Apply auto re-validate in `pbir_validator/gui/app.py` (FR-019): after `fix_apply` succeeds, (a) clear the Fix Plan tab's `ShiftCheckboxRow` list and disable the **Apply selected fixes** button so the same shifts cannot be applied a second time without a fresh dry-run, (b) replace the checklist with a one-line summary `"X applied, Y skipped, Z remaining (re-run Fix)"`, (c) immediately reuse the US1 validate dispatch (T024) so Gap Violations/Row Misalignments/Horizontal Spacing tabs refresh without user action; status bar reads "Re-validating after fix…" then "Done — N gaps, M misalignments, K h-spacing issues"
- [X] T041 [US3] Wire **Fix** button in `pbir_validator/gui/app.py` to dispatch `controllers.fix_plan` through `workers.run_in_background` and populate the Fix Plan tab on completion; show error dialog via `widgets.show_error` if conf.md is missing

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, smoke test, packaging hint.

- [X] T042 [P] Update `README.md` with a "Graphical UI" section: install instructions, `pbir_validator-gui` command, screenshot placeholder, headless-mode caveat
- [X] T043 [P] Update `specs/002-tkinter-gui/quickstart.md` with the final launch command and a step-by-step walkthrough of US1 → US2 → US3 matching the shipped UI
- [X] T044 [P] Add a Windows shortcut hint (`.lnk` creation note) to `README.md` so non-CLI users can double-click to launch
- [X] T045 [P] Update `pbir-validator.spec` (PyInstaller) to add a second entry for `pbir_validator-gui` so a future v0.2.0 build can ship a GUI `.exe` once code-signing is available; keep the GUI build commented-out by default
- [X] T046 GUI smoke-launch test in `tests/test_gui_smoke.py`: `pytest.importorskip("tkinter")`, skip on missing display (`os.environ.get("DISPLAY")` empty on non-Windows), construct `App`, assert the notebook has exactly 4 tabs (Gaps, Misalignments, Horizontal Spacing, Fix Plan), then `root.destroy()`
- [X] T047 Run full test suite (`pytest`) and confirm pre-existing 120 tests still pass plus the new GUI tests; record final count in commit message

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Phase 1 — BLOCKS all user stories
- **User Story 1 (Phase 3)**: depends on Phase 2; no dependency on US2/US3
- **User Story 2 (Phase 4)**: depends on Phase 2; independent of US1/US3
- **User Story 3 (Phase 5)**: depends on Phase 2 AND on US1's validate dispatch (T024) being callable, because post-Apply auto re-validate (T040) reuses it
- **Polish (Phase 6)**: depends on whichever stories you want to ship

### User Story Dependencies

- US1 (P1): foundation only
- US2 (P2): foundation only — fully independent of US1
- US3 (P3): foundation + US1's `validate` dispatch (one cross-story call: T040 → T024)

### Within Each User Story

- Tests (where listed) can be authored alongside or before implementation
- Controllers (pure logic) before widgets that consume them
- Widgets before the `app.py` wiring that places them on the notebook
- Wiring last — depends on both controllers and widgets

### Parallel Opportunities

- Phase 1: T002–T008 are all `[P]` (different files, all stubs)
- Phase 2: T012–T017 are all `[P]` (different modules); T018–T020 are `[P]` (different test files)
- Phase 3: T021 (test) parallel to T022 (controller); T025 tabs are sequential since they share `app.py`
- Phase 4: T028 parallel to T029; T030 parallel to T031 (different functions in `widgets.py` — pair-wise OK if authored carefully, otherwise sequential)
- Phase 5: T033 and T034 are `[P]`; T035 and T036 share `controllers.py` so sequential
- Phase 6: T042–T045 are `[P]` (documentation/spec edits in different files)

---

## Parallel Example: Phase 2 Foundational

```text
# Launch in parallel (different files, no shared state):
T012  pbir_validator/gui/workers.py
T013  pbir_validator/gui/export.py
T014  pbir_validator/gui/editor.py
T015  pbir_validator/gui/widgets.py  (ResultTable)
T018  tests/test_gui_workers.py
T019  tests/test_gui_export.py
T020  tests/test_gui_editor.py
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 (T001–T009)
2. Phase 2 (T010–T020)
3. Phase 3 (T021–T027)
4. **STOP and VALIDATE**: launch `pbir_validator-gui`, run quickstart US1 walkthrough
5. Tag `v0.2.0-rc1`, demo

### Incremental Delivery

1. MVP ships → demo
2. Add US2 (Phase 4) → demo Learn flow
3. Add US3 (Phase 5) → demo Fix dry-run + selective apply
4. Phase 6 polish → tag `v0.2.0`

### Parallel Team Strategy

After Phase 2 completes, three developers can pick up US1, US2, US3 simultaneously. The only cross-story coupling is T040 (US3) calling into the validate dispatch produced by T024 (US1), so US3 dev should sync with US1 dev once T024 lands.

---

## Notes

- `[P]` = different files, no incomplete dependencies
- Tk-rendering is exercised only by T046 smoke test; all other GUI tests target pure-logic modules (`workers`, `export`, `editor`, `controllers`)
- Headless detection (T010) is mandatory before any Tk window is constructed (FR-025)
- CSV is the default export format per FR-013a; JSON is selected via the save-dialog filter
- Per-shift opt-out (T037) and post-Apply auto re-validate (T040) come from the resolved clarifications in spec.md
- Constitutional constraint: stdlib-only at runtime — no new third-party dependencies are introduced by any task above
