# Feature Specification: GUI Power Features Bundle

**Feature Branch**: `005-power-features`  
**Created**: 2026-05-02  
**Status**: Draft  
**Input**: User description: "Bundle seven GUI power features into a single deliverable for the pbir_validator desktop tool: (1) double-click row to open in Power BI Desktop, (2) export all tabs as a ZIP of CSVs, (3) watch mode auto-revalidate, (4) severity grade in summary, (5) per-row drill-down side panel, (6) rule profiles dropdown, (7) undo last fix."

## Clarifications

### Session 2026-05-02

Resolved by author with sensible defaults (auto-answered per request, no user prompt):

- Q: What thresholds ship in `strict.md` / `standard.md` / `relaxed.md`? → A: `Standard` mirrors current built-in defaults (gap=8 px, overlap_tolerance=0 px, h_spacing_min=8 px, row_align_tolerance=2 px). `Strict` halves tolerances (gap=4, h_spacing_min=4, row_align_tolerance=1, overlap_tolerance=0). `Relaxed` doubles them (gap=16, h_spacing_min=16, row_align_tolerance=4, overlap_tolerance=2). All three files use the existing `conf.md` markdown grammar.
- Q: What does the side panel show when the user multi-selects rows in a result tab? → A: It shows the **last-clicked row only** (Treeview's `focus()` item). Multi-selection does not aggregate; the placeholder appears if focus is empty.
- Q: What default filename does the ZIP save dialog suggest? → A: `<report_root_basename>_validation_<YYYYMMDD-HHMMSS>.zip`, e.g. `MyReport.Report_validation_20260502-141530.zip`.
- Q: What happens to the Undo button and `last_fix.json` backup when the user loads a different report after Apply? → A: Loading a new report **disables the Undo button immediately** and the new report's `<report_root>/.pbir_validator_undo/last_fix.json` is consulted (enabled only if it exists). The previous report's backup file is left on disk untouched.
- Q: What is the default width and resize behavior of the drill-down side panel? → A: Default sash position is **360 px from the right edge** on first launch. The sash position is **not** persisted (only the visible/hidden boolean is). On window resize the panel keeps its pixel width and the left pane absorbs the delta.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Double-click row opens report in Power BI Desktop (Priority: P1)

A validator user reviewing a result row wants to jump straight into the offending report inside Power BI Desktop without using the right-click menu. Double-clicking any row in the five issue tables (Gap Violations, Overlapping Visuals, Duplicate Layer, Row Misalignments, Horizontal Spacing) launches the loaded report's `definition.pbir` (or `.pbip` if that is what was loaded) in Power BI Desktop with the same OS handler invocation and identical error handling as the existing right-click "Open page in Power BI Desktop" action.

**Why this priority**: Highest-frequency interaction during a validation session. Halves the click count to triage a finding.

**Independent Test**: Load a fixture report, run Validate, double-click a row in each of the five issue tables, and confirm the OS handler is invoked exactly once per double-click with the report file path. Verify no action occurs when double-clicking inside the Fix Plan tab.

**Acceptance Scenarios**:

1. **Given** a report is loaded and the Gap Violations tab has rows, **When** the user double-clicks any row, **Then** the application invokes the OS handler on the loaded report file and displays no error.
2. **Given** the loaded report file has been deleted from disk, **When** the user double-clicks a row in any of the five issue tables, **Then** the same error message used by the right-click action is shown via a messagebox.
3. **Given** the application is running on a non-Windows OS, **When** the user double-clicks a row, **Then** the same non-Windows guard message used by the right-click action is shown.
4. **Given** the Fix Plan tab is active, **When** the user double-clicks any row, **Then** no open action is triggered.

---

### User Story 2 - Export all tabs as a single ZIP of CSVs (Priority: P2)

A user finishing a review wants to hand off all findings in one file. A new toolbar button "Export all (CSV ZIP)" prompts for a save location and writes one ZIP archive with one CSV per non-empty result tab.

**Why this priority**: Replaces a multi-step per-tab export workflow with one click. Dependency-free (stdlib only).

**Independent Test**: With a report that produces findings in every tab, click "Export all (CSV ZIP)", choose a destination, and verify the resulting archive contains exactly the expected non-empty CSVs with the agreed filenames and the same column order as the per-tab export.

**Acceptance Scenarios**:

1. **Given** every result tab has rows, **When** the user clicks "Export all (CSV ZIP)" and confirms a path, **Then** the ZIP contains `gaps.csv`, `overlaps.csv`, `duplicate_layers.csv`, `misalignments.csv`, `h_spacing.csv`, and `fix_plan.csv`, each with headers and rows matching that tab's per-tab CSV export.
2. **Given** some tabs are empty, **When** the user exports, **Then** only non-empty tabs produce a CSV in the ZIP and no empty CSV files are written.
3. **Given** the destination path is unwritable (read-only directory, locked file), **When** the user confirms the path, **Then** the failure is surfaced via a messagebox and the user can retry.
4. **Given** the user cancels the save dialog, **When** the dialog closes, **Then** no file is written and no error is shown.
5. **Given** all per-tab export buttons exist, **When** this feature ships, **Then** those buttons remain functional and unchanged.

---

### User Story 3 - Watch mode auto-revalidates on file change (Priority: P2)

A user iterating on a report in Power BI Desktop wants the validator to re-run automatically whenever they save. A new "Watch" toggle button starts a 2-second polling loop that compares mtimes of every `definition.pbir`, `*.pbip`, and `pages/*/visuals/*/visual.json` under the loaded report root; if any mtime changed since the previous poll, the existing Validate action is invoked.

**Why this priority**: Removes the manual revalidate step during active editing. Builds on existing controllers without new validation logic.

**Independent Test**: Load a report, toggle Watch ON, modify any watched file's mtime via `os.utime`, wait one poll cycle, and confirm Validate ran exactly once. Toggle Watch OFF and modify another file; confirm no Validate runs.

**Acceptance Scenarios**:

1. **Given** no report is loaded, **When** the user inspects the Watch button, **Then** it is disabled.
2. **Given** a report is loaded and Watch is OFF, **When** the user toggles Watch ON, **Then** the status bar shows "Watching: ON (last check N seconds ago)" and updates each poll cycle.
3. **Given** Watch is ON, **When** any watched file's mtime advances, **Then** Validate is invoked exactly once on the next poll and the results tabs update.
4. **Given** Watch is ON, **When** no files change between polls, **Then** Validate is not invoked.
5. **Given** Watch is ON, **When** the user toggles Watch OFF, **Then** the poller stops within 2 seconds and the status bar no longer shows the watching message.
6. **Given** Watch is ON, **When** a watched file disappears mid-session (e.g., renamed), **Then** the poller logs a non-fatal warning and continues without crashing.

---

### User Story 4 - Severity grade in summary (Priority: P3)

After Validate completes, the user wants an at-a-glance health letter for the report. The status bar gains a single-letter grade (A / B / C / D / F) computed from a weighted issue count, and a color-coded label is shown next to the action buttons.

**Why this priority**: Pure presentation feature on top of existing counts. Low risk, high readability gain.

**Independent Test**: Stub controllers to return known counts and verify the displayed grade matches the documented thresholds; verify the color of the label widget changes by grade.

**Acceptance Scenarios**:

1. **Given** a Validate run with zero issues across all five categories, **When** the run completes, **Then** the status bar shows `[A]` and the label widget shows `A` in the green color.
2. **Given** a run with `gaps=1, overlaps=0, duplicate_layers=0, misalignments=0, h_spacing=0` (score = 3), **When** the run completes, **Then** the grade is `B`.
3. **Given** a run with `gaps=2, overlaps=2, duplicate_layers=1, misalignments=2, h_spacing=2` (score = 6+10+4+4+4 = 28), **When** the run completes, **Then** the grade is `D`.
4. **Given** a run with score ≥ 61, **When** the run completes, **Then** the grade is `F` and the label color is the failure color.
5. **Given** any prior grade is shown, **When** the user loads a new report or clears results, **Then** the grade label is hidden or reset to a neutral state.

---

### User Story 5 - Per-row drill-down side panel (Priority: P3)

A user investigating a finding wants the underlying visual details without opening the JSON manually. A right-hand collapsible panel, attached to the main window via `ttk.PanedWindow`, populates on single-row selection in any result tab with the visual's metadata and the full raw JSON in a read-only text widget. Rows referencing two visuals show both stacked.

**Why this priority**: Higher-context drill-down accelerates root-cause analysis but is not required for any other feature to ship.

**Independent Test**: With results loaded, select rows in each tab and confirm the panel shows the matching visual fields (`id`, `pageId`, page display name, type, x, y, width, height, parent group, raw JSON). Toggle "Hide panel" and "Show panel"; restart the app and confirm visibility persists from `recents.json`.

**Acceptance Scenarios**:

1. **Given** results are loaded and the side panel is visible, **When** the user single-selects a row in any of the **five issue tabs** (Gap Violations, Overlapping Visuals, Duplicate Layer, Row Misalignments, Horizontal Spacing) — the Fix Plan tab is excluded — **Then** the panel shows the visual's `id`, `pageId`, page display name, type, `x`, `y`, `width`, `height`, parent group, and the full raw JSON in a read-only text widget.
2. **Given** a selected row references two visuals (overlap, misalignment, h-spacing, duplicate), **When** the panel populates, **Then** both visuals' details are shown stacked in selection order.
3. **Given** the panel is visible, **When** the user clicks "Hide panel", **Then** the panel collapses and `recents.json` records `"side_panel_visible": false`.
4. **Given** the panel is hidden, **When** the user clicks "Show panel" in the toolbar, **Then** the panel re-expands and `recents.json` records `"side_panel_visible": true`.
5. **Given** the app starts and `recents.json` has `"side_panel_visible": false`, **When** the main window draws, **Then** the panel starts collapsed.
6. **Given** no row is selected, **When** the panel is visible, **Then** it shows a placeholder message and no visual fields.

---

### User Story 6 - Rule profiles dropdown (Priority: P3)

A user wants to switch between strictness levels without editing config. A toolbar combobox offers `Strict`, `Standard`, `Relaxed`, plus an implicit `Report-default` option shown only when the loaded report root contains a `conf.md`. The three named profiles are shipped as `pbir_validator/profiles/{strict,standard,relaxed}.md`. Selecting a profile loads it as the effective rule source for the session and re-runs Validate when a report is loaded.

**Why this priority**: Quality-of-life feature; default behavior stays compatible.

**Independent Test**: Launch the app, change the dropdown to each value, and verify (a) the next Validate run uses the chosen profile's rules, (b) the choice persists in `recents.json` under `"profile"`, (c) `Report-default` only appears when a report-root `conf.md` exists.

**Acceptance Scenarios**:

1. **Given** the app starts with no prior profile recorded, **When** the user inspects the combobox, **Then** the selected value is `Standard`.
2. **Given** a report is loaded, **When** the user changes the combobox to `Strict`, **Then** Validate is re-run using `pbir_validator/profiles/strict.md` and the results update.
3. **Given** the user picks `Relaxed`, **When** the app restarts, **Then** the combobox starts on `Relaxed` because `recents.json` recorded `"profile": "Relaxed"`.
4. **Given** the loaded report root has no `conf.md`, **When** the dropdown is opened, **Then** `Report-default` is not offered.
5. **Given** the loaded report root has a `conf.md`, **When** the user selects `Report-default`, **Then** the report-root `conf.md` is used as the rule source for the next Validate.
6. **Given** a profile is changed without a report loaded, **When** the change happens, **Then** the choice is recorded but Validate is not invoked.

---

### User Story 7 - Undo last fix (Priority: P3)

A user who applied a fix and is unhappy with the result wants a one-click undo. Apply now writes a backup at `<report_root>/.pbir_validator_undo/last_fix.json` listing the pre-shift y values for every visual it touched. A new "Undo last fix" toolbar button (disabled when no backup exists) restores those y values via byte-preserving `visual.json` edits, deletes the backup, and re-runs Validate.

**Why this priority**: Safety-net for the existing Apply Fix action. Single-level undo is sufficient.

**Independent Test**: Run Apply, confirm `.pbir_validator_undo/last_fix.json` is written and the button enables; click Undo and verify each touched `visual.json` is restored to byte-equivalent of its pre-Apply content (for the `position.y` field), the backup file is deleted, the button disables, and Validate runs.

**Acceptance Scenarios**:

1. **Given** no Apply has been run since loading the report, **When** the user inspects the toolbar, **Then** the "Undo last fix" button is disabled.
2. **Given** Apply just ran successfully, **When** the user inspects the toolbar, **Then** the "Undo last fix" button is enabled and `<report_root>/.pbir_validator_undo/last_fix.json` exists with one entry per visual the fix touched.
3. **Given** the backup file exists, **When** the user clicks Undo, **Then** every affected `visual.json` has its `position.y` restored to the pre-Apply value with byte-preserving formatting (only the y bytes change, like `writer.py`), the backup file is deleted, the button becomes disabled, and Validate is re-run.
4. **Given** Apply runs twice in a row, **When** the second Apply completes, **Then** the backup file contains only the second Apply's pre-shift state (one level of undo).
5. **Given** the backup file is missing or unreadable when the user clicks Undo, **When** the click happens, **Then** the user sees an error messagebox and no `visual.json` files are modified.
6. **Given** any affected `visual.json` is missing or unwritable when Undo is invoked, **When** the failure occurs, **Then** the user sees an error messagebox identifying the offending file and the operation aborts without partial restores leaking to disk for that file.

---

### User Story 8 - Integration: Watch + Profile change + Undo together (Priority: P3)

A user runs an end-to-end session that exercises three of the new features in sequence to confirm they coexist.

**Why this priority**: Catches state leakage between Watch polling, profile reload, and undo.

**Independent Test**: Load a report, toggle Watch ON, change profile from `Standard` to `Strict` (auto-revalidate triggers once), modify a `visual.json` mtime to trigger a watch-driven Validate, run Apply, click Undo, and confirm Watch is still ON, the profile is still `Strict`, the backup file is deleted, and the next mtime change triggers another Validate.

**Acceptance Scenarios**:

1. **Given** Watch is ON and profile is `Standard`, **When** the user picks `Strict`, **Then** Validate runs once with the `Strict` profile and Watch remains ON.
2. **Given** Watch is ON, **When** the user clicks Apply followed by Undo, **Then** both operations succeed, Watch is still ON, and the very next watched mtime change triggers Validate.
3. **Given** the user hides the side panel and changes the profile, **When** the app restarts, **Then** `recents.json` reflects both `"side_panel_visible": false` and `"profile": "Strict"`.

---

### Edge Cases

- A `.pbip` file is loaded instead of a folder containing `definition.pbir`: parsing continues to resolve to the sibling `.Report` folder; Watch and double-click both target the loaded `.pbip`/`definition.pbir` path actually used by the existing open-in-Desktop action.
- Watch poll catches a watched file mid-write (partial JSON): the poll only inspects mtimes; Validate then either succeeds or surfaces its own existing parse error — no special handling added.
- ZIP export when zero tabs have rows: a messagebox informs the user that there is nothing to export and no file is written.
- Undo is clicked while Watch is ON: the Validate triggered by Undo counts as the next watch tick (no double-validate).
- Profile combobox is changed while a Validate is in progress: change is queued; the next Validate uses the new profile.
- The `.pbir_validator_undo/` directory does not exist before the first Apply: it is created.
- Headless host imports the GUI module: no `Tk` instance is created at import time; tests that exercise UI logic must instantiate widgets explicitly.

## Requirements *(mandatory)*

### Functional Requirements

#### Feature 1 — Double-click open

- **FR-001**: The application MUST open the loaded report file in the OS default handler when the user double-clicks any row in the Gap Violations, Overlapping Visuals, Duplicate Layer, Row Misalignments, or Horizontal Spacing tabs.
- **FR-002**: The double-click MUST NOT trigger any action when issued in the Fix Plan tab.
- **FR-003**: The application MUST display the same messagebox text used by the existing right-click "Open page in Power BI Desktop" action for the missing-file and non-Windows error paths.

#### Feature 2 — Export all (CSV ZIP)

- **FR-010**: The toolbar MUST expose an "Export all (CSV ZIP)" button.
- **FR-011**: Selecting the button MUST prompt for a save path (default filename `<report_root_basename>_validation_<YYYYMMDD-HHMMSS>.zip`) and, on confirm, write a single ZIP archive containing one CSV per non-empty result tab.
- **FR-012**: CSV filenames inside the archive MUST be exactly `gaps.csv`, `overlaps.csv`, `duplicate_layers.csv`, `misalignments.csv`, `h_spacing.csv`, and `fix_plan.csv`. Empty tabs MUST be skipped.
- **FR-013**: Each CSV's columns and row order MUST match the existing per-tab CSV export for that tab.
- **FR-014**: All existing per-tab CSV export buttons MUST continue to work unchanged.
- **FR-015**: ZIP write failures MUST be surfaced via a messagebox; the user MUST be able to retry.
- **FR-016**: Implementation MUST use the standard library only (no openpyxl); ZIP generation uses `zipfile` and CSV writing uses `csv`.

#### Feature 3 — Watch mode

- **FR-020**: A "Watch" toggle button MUST be present in the toolbar and disabled until a report is loaded.
- **FR-021**: When Watch is ON, the application MUST poll every 2 seconds the mtimes of every `definition.pbir` and every `*.pbip` at the report root, plus every `visual.json` file matched by `<report_root>/definition/pages/*/visuals/*/visual.json` (the standard PBIP layout).
- **FR-026**: After every Validate run (whether triggered manually, by Watch, by profile change, or by Undo), the Watch poller MUST refresh its mtime baseline snapshot so the Validate's own writes do not re-fire the next poll.
- **FR-022**: When any polled mtime changes since the previous poll, the application MUST invoke the existing Validate action exactly once before continuing to poll.
- **FR-023**: The status bar MUST show "Watching: ON (last check N seconds ago)" while Watch is ON, updating at least once per poll cycle.
- **FR-024**: Toggling Watch OFF MUST stop the poller within 2 seconds.
- **FR-025**: A poll error (missing file, permission error) MUST be logged as a non-fatal warning and MUST NOT crash the poller or the application.

#### Feature 4 — Severity grade

- **FR-030**: After every successful Validate, the application MUST compute a weighted score: `score = 3·gaps + 5·overlaps + 4·duplicate_layers + 2·misalignments + 2·h_spacing`.
- **FR-031**: The grade MUST be derived as: `0 → A`, `1–10 → B`, `11–25 → C`, `26–60 → D`, `61+ → F`.
- **FR-032**: The status bar summary MUST include the grade in square brackets (e.g., `[B]`).
- **FR-033**: A label widget placed to the right of the action buttons MUST display the grade letter and use the following color palette: `A=#1b5e20` (green), `B=#558b2f` (lime), `C=#f9a825` (amber), `D=#ef6c00` (orange), `F=#c62828` (red), neutral=`#757575` (grey) when no run has occurred.

#### Feature 5 — Drill-down side panel

- **FR-040**: The main window MUST host a right-hand collapsible side panel via `ttk.PanedWindow`. The default sash position MUST place the panel at 360 px wide on first launch; the sash position itself MUST NOT be persisted (only `side_panel_visible` is).
- **FR-041**: On single-row selection in any of the **five issue tabs** (excluding Fix Plan), the panel MUST show: `id`, `pageId`, page display name, visual type, `x`, `y`, `width`, `height`, parent group, and the full raw JSON in a read-only `Text` widget. Selection in the Fix Plan tab MUST leave the panel unchanged. On multi-selection the panel MUST track the Treeview focus item only (last-clicked row); when focus is empty the placeholder MUST be shown.
- **FR-042**: For rows referencing two visuals (overlaps, misalignments, h-spacing, duplicates), both visuals' details MUST be shown stacked in the order they appear in the row.
- **FR-043**: A "Hide panel" button MUST collapse the panel; a "Show panel" toolbar button MUST restore it.
- **FR-044**: Panel visibility MUST persist in `recents.json` under the key `"side_panel_visible"` (boolean).

#### Feature 6 — Rule profiles dropdown

- **FR-050**: The toolbar MUST include a `ttk.Combobox` offering at minimum `Strict`, `Standard`, `Relaxed`.
- **FR-051**: The package MUST ship `pbir_validator/profiles/strict.md`, `pbir_validator/profiles/standard.md`, and `pbir_validator/profiles/relaxed.md`, each using the existing `conf.md` markdown grammar. `Standard` MUST encode the current built-in defaults (gap=8 px, overlap_tolerance=0 px, h_spacing_min=8 px, row_align_tolerance=2 px). `Strict` MUST halve those tolerances (gap=4, h_spacing_min=4, row_align_tolerance=1, overlap_tolerance=0). `Relaxed` MUST double them (gap=16, h_spacing_min=16, row_align_tolerance=4, overlap_tolerance=2).
- **FR-052**: Selecting a profile MUST load that profile's rules as the effective rule source for the current session, overriding any `conf.md` in the report root.
- **FR-053**: When a report is loaded, changing the profile MUST trigger a Validate run.
- **FR-054**: The default profile MUST be `Standard` on first launch and the choice MUST persist in `recents.json` under the key `"profile"`.
- **FR-055**: A `Report-default` option MUST appear in the dropdown only when the loaded report root contains a `conf.md`. Selecting it MUST use the report-root `conf.md` as the rule source.

#### Feature 7 — Undo last fix

- **FR-060**: `fixer.apply_plan` MUST write a backup record at `<report_root>/.pbir_validator_undo/last_fix.json` containing, for every visual it touches, the visual's identifier, file path, and pre-shift `position.y` value.
- **FR-061**: A toolbar "Undo last fix" button MUST be disabled when the currently-loaded report's `<report_root>/.pbir_validator_undo/last_fix.json` does not exist and enabled when it does. Loading a different report MUST re-evaluate this state immediately (disabling unless the new report has its own backup); the previous report's backup file MUST be left on disk untouched.
- **FR-062**: Clicking Undo MUST restore each affected `visual.json`'s `position.y` to the recorded pre-shift value using the same byte-preserving edit pathway used by `writer.py`.
- **FR-063**: After a successful Undo, the backup file MUST be deleted, the Undo button MUST disable, and Validate MUST be re-run.
- **FR-064**: Each Apply MUST overwrite the existing backup file (one level of undo only).
- **FR-065**: A missing, unreadable, or partially-restorable backup MUST surface a messagebox; on per-file failure during restore the operation MUST abort without leaving partial writes for that file.
- **FR-066**: The path `.pbir_validator_undo/last_fix.json` MUST be added to the project `.gitignore` so backups never enter version control.

#### Cross-cutting

- **FR-070**: All seven features MUST be GUI-only (except watch mode, which is allowed to invoke the existing `controllers.validate()`); the CLI's stdout, stderr, exit code, and result-table contents MUST remain byte-identical to the pre-feature baseline.
- **FR-071**: All existing GUI behaviors — keyboard shortcuts, right-click menus, table sort, table filter, severity-tag coloring, recents menu — MUST continue to work unchanged.
- **FR-072**: `recents.json` MUST gain `"side_panel_visible"` and `"profile"` keys without breaking older recents files; missing keys MUST default to `True` and `"Standard"` respectively.
- **FR-073**: The Tkinter UI module MUST remain importable on a headless host (no top-level `Tk()` creation at import time).
- **FR-074**: New modules MUST achieve ≥90% line coverage; the project total MUST stay ≥80%.
- **FR-075**: All 205 existing tests MUST remain green.

### Key Entities *(include if feature involves data)*

- **Profile** — A markdown configuration file (`strict.md`, `standard.md`, `relaxed.md`) shipped under `pbir_validator/profiles/` that defines the active rule thresholds for a session.
- **UndoRecord** — A JSON document at `<report_root>/.pbir_validator_undo/last_fix.json` listing, for each visual touched by the most recent Apply, its identifier, file path, and pre-shift `position.y` value.
- **WatchState** — In-memory mapping of watched file paths to their last observed mtimes, plus the timestamp of the most recent poll cycle.
- **GradeSummary** — Computed per-Validate object with the weighted score, derived letter grade, and per-category counts used to render the status bar and color-coded label.
- **DrillDownContext** — The currently-selected row's resolved visual(s) data (id, pageId, page display name, type, geometry, parent group, raw JSON) populating the side panel.
- **RecentsState** — Persisted JSON gaining the new keys `side_panel_visible` (bool) and `profile` (string).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 8 user stories pass their acceptance scenarios.
- **SC-002**: The 205 existing tests remain green after the feature ships.
- **SC-003**: Project pytest line coverage stays ≥ 80%; each newly-added module reaches ≥ 90% line coverage.
- **SC-004**: A Validate run started by Watch mode launches within 3 seconds of an mtime change to a watched file.
- **SC-005**: The "Export all (CSV ZIP)" action completes for a 1,000-row aggregate result set in under 2 seconds on a typical developer laptop and produces an archive whose CSVs match the per-tab exports byte-for-byte.
- **SC-006**: Undo restores every touched `visual.json` such that the file is byte-identical, in the y bytes, to the pre-Apply state for 100% of fixtures.
- **SC-007**: CLI integration tests that compare stdout/stderr/exit code against the pre-feature baseline show zero diff.
- **SC-008**: Switching profiles in the dropdown re-runs Validate within 1 second of selection on a typical fixture report.

## Assumptions

- The existing `controllers.validate()` is the single Validate entry point and accepts an in-memory rules object so the profile dropdown can override the source without touching disk.
- The right-click "Open page in Power BI Desktop" action already centralizes the OS-handler call; the double-click handler reuses the same internal helper to guarantee identical error handling.
- The current per-tab CSV export already lives in a helper that returns header + rows; the ZIP exporter calls that helper once per non-empty tab.
- `writer.py`'s byte-preserving edit pathway is reusable from a new `undo` helper without refactor.
- Tk widgets are created lazily inside the `App` class constructor so the module remains importable on a headless host.
- `recents.json` is a flat JSON object that tolerates additive keys.
- The `.specify/extensions.yml` git hook handles branch creation; this spec was authored after `005-power-features` was created by `create-new-feature.ps1`.
- Mobile and web hosting are out of scope; this is a desktop Tkinter feature set.
