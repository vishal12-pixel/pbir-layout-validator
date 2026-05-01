# Feature Specification: Tkinter Desktop GUI for pbir_validator

**Feature Branch**: `002-tkinter-gui`
**Created**: 2026-05-01
**Status**: Draft
**Input**: User description: "Add an optional Tkinter-based desktop GUI to pbir_validator. The user picks either a .pbip file or a .Report folder via Browse buttons (auto-detect). The window offers three actions — Learn, Validate, Fix — and renders results in scrollable panes. Learn mode optionally opens conf.md in the system editor or shows a page dropdown. Validate renders gap/row/h-spacing tables. Fix runs as a dry-run first, exposing each planned Shift as a checkbox so users can opt-out of intentional offsets before applying. Stdlib-only (tkinter); CLI remains the primary interface."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate a report and review issues visually (Priority: P1)

A Power BI report author with a `.pbip` or `.Report` folder on disk launches the GUI, browses to the report, clicks **Validate**, and immediately sees three scrollable result panes — one each for gap-rule violations, row misalignments, and horizontal-spacing issues — without leaving the application.

**Why this priority**: Validation is the most frequent use of the tool and the primary reason a non-CLI user would open a GUI. Delivering this alone (with a working Browse-and-Validate flow) is a viable MVP because it provides immediate read-only value without any risk to the report files.

**Independent Test**: Open the GUI, browse to a known-bad fixture report, click **Validate**, and confirm that violations appear in the appropriate result panes with the same content the CLI `validate` command produces for the same input.

**Acceptance Scenarios**:

1. **Given** the GUI is open and no report has been chosen, **When** the user clicks **Validate**, **Then** the GUI surfaces a clear, non-fatal message that a report must be selected first.
2. **Given** the user has browsed to a `.pbip` file, **When** they click **Validate**, **Then** the GUI resolves the sibling `.Report` folder using the same logic the CLI uses (reading `artifacts[].report.path`) and displays results.
3. **Given** the user has browsed to a `.Report` folder directly, **When** they click **Validate**, **Then** the GUI auto-detects the input type and displays results without requiring a different button.
4. **Given** validation produces violations, **When** results are rendered, **Then** each of the three result panes (gap violations, row misalignments, h-spacing issues) is independently scrollable and shows one row per finding with the same fields the CLI reports.
5. **Given** validation produces zero issues, **When** results are rendered, **Then** each pane clearly indicates "No issues found" rather than appearing empty or broken.

---

### User Story 2 - Generate or hand-edit conf.md via Learn mode (Priority: P2)

The same user wants to (a) generate `conf.md` for a specific page they care about, or (b) skip generation entirely and edit the existing `conf.md` by hand in their preferred editor.

**Why this priority**: Learn is a prerequisite for meaningful validation, but most users will already have a `conf.md` from prior CLI runs. P2 covers the case where they want to refresh it or hand-tune it without dropping back to the terminal.

**Independent Test**: With a report selected, click **Learn**, choose "Yes" at the manual-edit prompt and confirm `conf.md` opens in the system default editor; repeat with "No" and confirm the page-picker dropdown appears, lists pages by their `displayName`, and writing `conf.md` succeeds for the selected page.

**Acceptance Scenarios**:

1. **Given** a report is selected and `conf.md` exists, **When** the user clicks **Learn**, **Then** the GUI first asks "Do you want to manually edit conf.md instead?" before showing any other Learn UI.
2. **Given** the manual-edit prompt appears, **When** the user answers **Yes**, **Then** the existing `conf.md` opens in the operating system's default editor and no page dropdown is shown.
3. **Given** the manual-edit prompt appears, **When** the user answers **No**, **Then** the GUI presents a dropdown of all pages in the report, each labeled by `displayName`, and a confirm button.
4. **Given** the page dropdown is shown, **When** the user picks a page and confirms, **Then** `conf.md` is generated for that page using the existing learner logic and a success message names the file written.
5. **Given** the report has no `conf.md` yet, **When** the user clicks **Learn**, **Then** the manual-edit prompt still appears and answering **Yes** is treated as an error/warning (nothing to edit) without crashing.

---

### User Story 3 - Apply fixes selectively with a dry-run checklist (Priority: P3)

After reviewing validation results, the user clicks **Fix**, sees the planned shifts as a checklist (all checked by default), unchecks one or two visuals whose offsets are intentional, and clicks **Apply selected fixes** to write only the remaining shifts to disk.

**Why this priority**: Fix mutates report files. It is the highest-risk action and depends on Validate (P1) being trustworthy. P3 reflects that the user must already know what Validate found before they can responsibly apply fixes, and the safety mechanism (per-shift checkboxes) is what makes a GUI fix workflow worthwhile over the existing CLI `--apply` flag.

**Independent Test**: Run **Fix** against a report with at least three known shifts; confirm all rows appear checked, uncheck one, click **Apply selected fixes**, and verify on disk that only the remaining shifts were written and the unchecked visual is unchanged.

**Acceptance Scenarios**:

1. **Given** validation has identified shifts to apply, **When** the user clicks **Fix**, **Then** the GUI runs the fixer in dry-run mode first and renders one row per planned `Shift` in a scrollable checklist with all rows checked by default.
2. **Given** the dry-run checklist is shown, **When** the user unchecks one or more rows, **Then** those rows are visually marked as skipped and **Apply selected fixes** remains enabled.
3. **Given** the user clicks **Apply selected fixes**, **When** the action runs, **Then** only the checked shifts are written to disk and a confirmation summarizes how many were applied and how many were skipped.
4. **Given** every shift is unchecked, **When** the user clicks **Apply selected fixes**, **Then** the GUI declines to mutate the report and shows a "no shifts selected" notice instead of writing an empty change.
5. **Given** the dry-run produces zero shifts, **When** results render, **Then** the checklist clearly states "No fixes needed" and **Apply selected fixes** is disabled.

---

### Edge Cases

- **Wrong file picked**: The user browses to a file that is neither a `.pbip` nor a `.Report` folder (e.g., a `.pbix` binary or an unrelated folder). The GUI MUST surface a clear error and refuse to run any of the three actions.
- **`.pbip` with broken artifacts**: The `.pbip` file does not list a resolvable `report.path`. The GUI MUST report the resolution failure with the same wording the CLI uses, not a Python traceback.
- **Long-running operations**: A large report makes Validate or Fix take noticeably long. The GUI MUST remain responsive (not freeze) and MUST indicate that work is in progress.
- **External edit during session**: The user opens `conf.md` in the system editor (Learn → Yes) and then runs Validate. The GUI MUST re-read `conf.md` from disk for the new run rather than caching a stale copy.
- **Permission / read-only files**: Writing `conf.md` (Learn) or applying fixes (Fix) fails because the target file is read-only or locked. The GUI MUST report the OS error verbatim and MUST NOT leave the report in a half-written state.
- **No display server / headless environment**: The user attempts to launch the GUI on a system without a display (CI, SSH session). The launcher MUST exit with a clear "no display available" message and a hint to use the CLI.
- **Color/contrast accessibility**: Result tables MUST remain legible under the user's OS theme (light or dark) without the GUI overriding system colors.

## Requirements *(mandatory)*

### Functional Requirements

#### Launching and report selection

- **FR-001**: The tool MUST expose an optional GUI launch path (a subcommand or flag on the existing CLI entry point) that opens a single main window; invoking it MUST NOT change the behavior of any existing CLI subcommand.
- **FR-002**: The main window MUST present two Browse buttons — one for picking a `.pbip` file and one for picking a `.Report` folder — and MUST display the resolved report path once a selection is made.
- **FR-003**: The GUI MUST auto-detect whether the user picked a `.pbip` file or a `.Report` folder and MUST resolve a `.pbip` selection to its sibling `.Report` folder using the same logic the CLI already uses (reading `artifacts[].report.path`).
- **FR-004**: If the resolved path is not a valid PBIR report folder, the GUI MUST display an error message in the window (not a console traceback) and MUST disable the three action buttons until a valid report is selected.

#### Action buttons

- **FR-005**: The window MUST offer exactly three primary action buttons labeled **Learn**, **Validate**, and **Fix**, each enabled only when a valid report is selected.
- **FR-006**: All three actions MUST delegate to the existing analyzer, validator, learner, and fixer modules; the GUI MUST NOT reimplement any parsing, layout calculation, or file-writing logic.

#### Learn mode

- **FR-007**: Clicking **Learn** MUST first display a yes/no prompt asking "Do you want to manually edit conf.md instead?" before any other Learn UI is shown.
- **FR-008**: If the user answers **Yes** and `conf.md` exists, the GUI MUST open the existing `conf.md` in the operating system's default editor and take no further Learn action.
- **FR-009**: If the user answers **Yes** and `conf.md` does not yet exist, the GUI MUST surface a clear message that there is nothing to edit and return to the main window without crashing.
- **FR-010**: If the user answers **No**, the GUI MUST show a dropdown listing every page in the report by its `displayName`, plus a confirm control.
- **FR-011**: When the user confirms a page selection, the GUI MUST invoke the existing learner to (re)generate `conf.md` for that page and MUST report success or failure inside the window.

#### Validate mode

- **FR-012**: Clicking **Validate** MUST run the existing validator against the selected report and render its findings in three independently scrollable result panes: gap-rule violations, row misalignments, and horizontal-spacing issues.
- **FR-013**: Each result pane MUST present one row per finding with the fields the CLI already reports for that finding type (e.g., page, visual identifier, expected vs. actual values), and MUST clearly state "No issues found" when its category is empty.
- **FR-014**: Validation MUST be read-only: running it MUST NOT modify any file under the report folder.

#### Fix mode

- **FR-015**: Clicking **Fix** MUST always perform a dry-run first; the GUI MUST NOT write any change at this stage.
- **FR-016**: The dry-run result MUST be rendered as a scrollable checklist with one row per planned `Shift`, every row pre-checked, and each row showing enough information for the user to identify the affected visual and the proposed offset.
- **FR-017**: The user MUST be able to uncheck any individual row to exclude that shift from being applied.
- **FR-018**: The window MUST include an **Apply selected fixes** button that writes only the currently checked shifts to disk via the existing fixer; rows that are unchecked MUST NOT be written.
- **FR-019**: After applying, the GUI MUST display a summary of how many shifts were applied and how many were skipped, and MUST refresh or invalidate the checklist so the same shifts cannot be applied twice in one session.
- **FR-020**: If the dry-run produces zero shifts, the GUI MUST show "No fixes needed" and **Apply selected fixes** MUST be disabled.

#### Cross-cutting

- **FR-021**: The GUI MUST be implemented using only the Python standard library (specifically `tkinter` and `tkinter.ttk`); adding any new third-party runtime dependency is prohibited.
- **FR-022**: The CLI MUST remain the primary, equally-supported interface; every GUI capability MUST already be reachable from the CLI, and removing the GUI MUST NOT break any CLI command.
- **FR-023**: Long-running operations (Validate, Learn, Fix) MUST NOT freeze the window; the GUI MUST indicate work is in progress and MUST remain interactable enough for the user to see the progress indicator.
- **FR-024**: Any error raised by the underlying modules MUST be displayed inside the GUI as a readable message (including the offending file path where the CLI provides one); raw Python tracebacks MUST NOT be the only feedback the user sees.
- **FR-025**: Launching the GUI in a headless environment (no display server available) MUST fail fast with a clear message directing the user to the CLI, rather than hanging or producing a Tk error dialog the user cannot read.

### Key Entities *(include if feature involves data)*

The GUI does not introduce new domain entities. It consumes the existing model defined in [specs/001-pbir-layout-validator/data-model.md](../001-pbir-layout-validator/data-model.md):

- **Report / Page / Visual**: Surfaced when listing pages in Learn mode and when labeling rows in result panes.
- **GapRule / Violation / UnknownPair**: Rows in the gap-violation result pane.
- **Row / Misalignment**: Rows in the row-misalignment result pane.
- **HSpacingIssue**: Rows in the horizontal-spacing result pane.
- **Shift**: One checklist row in the Fix dry-run; the unit a user can opt in or out of.

The GUI MUST treat all of these as read-only views over data produced by the existing modules; it MUST NOT redefine their fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has never opened the CLI can select a report, run Validate, and read the findings in three scrollable panes within 60 seconds of launching the GUI.
- **SC-002**: For any given report, the GUI's Validate output contains exactly the same findings (same count, same affected visuals) as the CLI `validate` command run against the same input.
- **SC-003**: For any given report, the GUI's Fix dry-run lists exactly the same shifts as the CLI fixer's dry-run, and applying with all rows checked produces a file-on-disk result identical to the CLI's `--apply` run.
- **SC-004**: When the user unchecks N shifts before applying, the resulting on-disk change set contains exactly (total − N) shifts and no others.
- **SC-005**: 95% of Validate runs against a 50-page report return rendered results within 5 seconds (matching the CLI performance bar in the constitution).
- **SC-006**: The window remains responsive (visible progress indicator, no "Not Responding" OS overlay) for the full duration of any operation up to and including a 50-page report.
- **SC-007**: Every error path (no report selected, invalid report, write failure, missing display) produces an in-window or in-terminal message with no raw Python traceback shown as the only output.
- **SC-008**: The GUI ships with zero new third-party runtime dependencies; the project's existing stdlib-only constraint remains satisfied.

## Assumptions

- The existing CLI in `pbir_validator/cli.py` already exposes `learn`, `validate`, and `fix` subcommands and resolves `.pbip` vs `.Report` inputs via `pbir_validator/reader.py`; the GUI wraps these and does not change them.
- The existing data model entities listed above are stable and adequate; no new entity is required for this feature.
- Tk and Ttk shipped with the user's Python 3.11+ install are available on Windows, macOS, and Linux; the project does not need to bundle Tk itself.
- "Open in system default editor" means whatever the operating system associates with `.md` files; the GUI does not select or configure an editor.
- Page identity in the Learn dropdown is the `displayName` field already produced by the analyzer; if two pages share a `displayName`, ordering by the analyzer's existing iteration order is acceptable.
- Headless detection (FR-025) is best-effort: a clean exit with a message is sufficient; the GUI is not expected to fall back to a TUI.
- Accessibility scope for v1 is limited to "use system colors and fonts and don't break under dark mode"; full screen-reader certification is out of scope.
- The GUI is opt-in: existing CLI users, scripts, and CI pipelines see no behavior change unless they explicitly invoke the GUI launcher.
