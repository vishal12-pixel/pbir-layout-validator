# Feature Specification: PBIR Layout Validator & Fixer

**Feature Branch**: `001-pbir-layout-validator`  
**Created**: 2026-05-01  
**Status**: Draft  
**Input**: User description: "Build a Python CLI tool that helps Power BI report developers maintain consistent vertical spacing between visuals across all pages of a PBIR-format report. Three modes: learn (derive spacing rules from a reference page), validate (check all pages against rules), fix (auto-correct violations). Stdlib-only, packageable as a Windows .exe via PyInstaller."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learn spacing rules from a reference page (Priority: P1)

A Power BI report developer has one page in their `.Report` folder whose vertical layout they consider correct. They want the tool to read that page and produce a reusable rules file (`conf.md`) describing the vertical gaps between adjacent visual rows, keyed by the visual types involved (e.g., `card → actionButton: 9px`). They no longer want to measure pixel gaps by hand.

**Why this priority**: Without learned rules, neither validation nor fixing is possible. This is the foundational MVP slice — it converts a single "good" page into the source of truth that powers every other mode.

**Independent Test**: Run the tool against a sample `.Report` folder in learn mode, pick a page from the interactive list, and confirm a `conf.md` file is written that lists the gap (in pixels) between each adjacent row pair on that page along with the visual type labels for the rows. The file should be human-readable so the developer can sanity-check it without running anything else.

**Acceptance Scenarios**:

1. **Given** a valid `.Report` folder containing multiple pages, **When** the developer runs the tool with the learn flag and selects a page from the printed numbered list, **Then** the tool writes a `conf.md` file containing one rule per adjacent row pair on that page, each rule naming the from-row visual type, the to-row visual type, and the gap in pixels.
2. **Given** the chosen reference page contains visuals at varying Y positions, **When** the tool groups them into rows, **Then** visuals whose Y coordinates differ by no more than 2 pixels are treated as the same row and rows are sorted top-to-bottom before gaps are computed.
3. **Given** a row contains visuals of more than one type, **When** the rule for that row is being written, **Then** the tool emits a warning naming the page and row and records a representative type label (with the mixed-type situation surfaced in the warning) so the developer can decide whether to clean up the reference page.
4. **Given** the developer re-runs learn mode against the same report, **When** a `conf.md` already exists at the target path, **Then** the tool overwrites it (after confirming or via an explicit overwrite behavior) without corrupting any other files in the report folder.

---

### User Story 2 - Validate all pages against learned rules (Priority: P1)

Before publishing a 40+ page report, the developer wants a single command that scans every page, computes the gaps between adjacent visual rows, compares each gap to the rule for the matching visual-type pair, and prints every violation in a table they can scan quickly. The output must clearly show which page, which visual types, the expected gap, the actual gap, and the deviation in pixels.

**Why this priority**: Validation is the highest-frequency day-to-day workflow and the primary reason the tool exists. It must be usable independently of the fix mode — many developers will run validate, eyeball the report, and adjust manually rather than auto-fix.

**Independent Test**: Given a `conf.md` and a `.Report` folder with at least one deliberately misaligned page, running the tool in validate mode produces a non-zero exit code and a clearly formatted table of violations. Running it against a fully-conformant report produces a success message and a zero exit code.

**Acceptance Scenarios**:

1. **Given** a `conf.md` file with learned rules and a `.Report` folder, **When** the developer runs validate mode, **Then** the tool walks every page, computes adjacent-row gaps, and prints a table whose columns are: page name, from-visual-type, to-visual-type, expected gap (px), actual gap (px), and deviation (px, signed).
2. **Given** the report contains zero violations, **When** validate completes, **Then** the tool prints a success indicator and exits with code 0.
3. **Given** the report contains one or more violations, **When** validate completes, **Then** the tool exits with a non-zero code so it can be used in a pre-publish check.
4. **Given** a page contains a visual-type pair that is not present in `conf.md`, **When** validate runs, **Then** the tool skips that pair, lists it under an "unknown pair" warning section, and does not count it as a violation.
5. **Given** the developer passes a custom path to a `conf.md` shared across multiple reports, **When** validate runs, **Then** the tool loads rules from that path instead of the default location.

---

### User Story 3 - Auto-fix gap violations (Priority: P2)

After running validate and confirming the violations are real, the developer wants the tool to correct them automatically by shifting offending visuals (and every visual below them on the same page) up or down so that the actual gap matches the expected gap. Before any change is written, the developer wants the option to preview every change without modifying any file. Writes must preserve every other field in `visual.json` (so unrelated visual properties are not lost or reordered destructively).

**Why this priority**: Auto-fix is a major time-saver but depends on validate being trustworthy. It is also the riskiest mode because it mutates the report on disk, so it ships after the read-only modes are stable.

**Independent Test**: Given a report with known gap violations, running fix mode in dry-run prints the exact set of Y-coordinate changes per visual without touching any file. Running fix mode without dry-run applies those same changes; re-running validate immediately afterward reports zero violations and every previously-unrelated field in the affected `visual.json` files is byte-for-byte preserved (aside from the changed Y values).

**Acceptance Scenarios**:

1. **Given** a violation where the actual gap is smaller or larger than the expected gap, **When** fix mode runs without dry-run, **Then** the tool shifts the lower row's visuals (and all rows below them on the same page) by the deviation amount so the gap equals the expected value, and writes updated Y coordinates back to each affected `visual.json`.
2. **Given** the developer runs fix mode with the dry-run flag, **When** the tool finishes, **Then** no `visual.json` file is modified and the tool prints, per planned change, the page, visual identifier, old Y, new Y, and delta.
3. **Given** a `visual.json` contains fields beyond position/size (e.g., visual-specific properties, query bindings, formatting), **When** the tool writes the file after a fix, **Then** all those fields remain present and unchanged and only the Y position is updated.
4. **Given** a visual belongs to a group (has a `parentGroupName`), **When** the tool encounters it during fix, **Then** the tool either shifts the whole group consistently or skips the group with an explicit warning (see Assumptions) so layouts inside groups are never partially shifted.
5. **Given** any error occurs while writing a `visual.json`, **When** fix mode is running, **Then** the tool stops before processing further pages, surfaces the error with the offending file path, and leaves the report in a state where already-written changes are valid JSON (no half-written or corrupted files).

---

### User Story 4 - Use a shared `conf.md` across reports (Priority: P3)

A team lead maintains one canonical `conf.md` that captures the team's spacing standard. Individual developers want to validate or fix any of their reports against that shared file by pointing the tool at it explicitly, rather than copying the file into every report folder.

**Why this priority**: Important for team adoption and standardization but not required for a single developer to get value from the tool on their own report.

**Independent Test**: With a shared `conf.md` stored outside the report folder, run validate and fix modes against multiple different `.Report` folders, each time passing the shared file's path via a command-line option, and confirm the same rule set is applied in each run.

**Acceptance Scenarios**:

1. **Given** a `conf.md` stored at any filesystem path, **When** validate or fix mode is run with an explicit conf path option, **Then** the tool loads rules from that path and ignores any `conf.md` that may exist alongside the report.
2. **Given** the explicit path does not exist or cannot be parsed, **When** the tool starts, **Then** it exits with a non-zero code and a clear message naming the bad path before touching any report file.

---

### Edge Cases

- A page has zero or one visual: there are no adjacent row pairs to check; the tool reports the page as trivially passing and does not crash.
- A visual is missing the `visual.visualType` field: the tool labels its row as `unknown` and emits a warning naming the page and visual; it does not abort the run.
- Two adjacent rows contain visuals of different types (mixed-type row): the tool warns once per occurrence, names the page and rough Y position, and uses a deterministic representative type when emitting/comparing rules so behavior is repeatable across runs.
- The same visual-type pair appears multiple times on the reference page with different gap values: the tool picks one canonical value (most frequent, ties broken by smallest gap) and warns that the reference page is internally inconsistent so the developer can clean it up.
- A `visual.json` file is malformed JSON: the tool reports the file path and skips that visual; in fix mode it must not write a file it could not first parse cleanly.
- A page folder exists with no `visuals/` subfolder, or `visuals/` is empty: treat as zero-visual page, do not crash.
- The user runs the tool against a folder that is not a PBIR report (no `definition/pages` subtree): the tool exits with a clear "this does not look like a PBIR report" message and a non-zero code.
- Visuals belong to a group (`parentGroupName` set): the tool handles them per the rule chosen in Assumptions and never partially shifts a group's contents.
- Fix mode would push a visual off the bottom of the page (Y + height > page height): the tool refuses to apply that specific fix, reports it as an unfixable violation, and continues with the rest.
- The developer cancels (Ctrl+C) mid-fix: any `visual.json` files already written remain valid JSON; in-progress writes use a write-then-replace pattern so partial files cannot be left behind.

## Requirements *(mandatory)*

### Functional Requirements

#### Common to all modes

- **FR-001**: The tool MUST be a single Python CLI program that can run on Windows from a command prompt and MUST be packageable as a standalone Windows executable using PyInstaller.
- **FR-002**: The tool MUST use only the Python standard library at runtime (no third-party dependencies installed via pip).
- **FR-003**: The tool MUST accept a path to a Power BI `.Report` folder (PBIR format) as its primary input and MUST validate that the folder contains a `definition/pages/` subtree before doing any work.
- **FR-004**: The tool MUST expose three operating modes selectable via mutually exclusive command-line flags: a learn mode, a validate mode, and a fix mode. Exactly one mode MUST be active per invocation.
- **FR-005**: The tool MUST print colored terminal output for headers, warnings, errors, and success indicators, and MUST gracefully degrade to plain text when the terminal does not support color.
- **FR-006**: The tool MUST exit with code 0 on full success, and a non-zero code when any violation is detected (validate), any fix is refused or fails (fix), or any input is invalid (all modes).
- **FR-007**: The tool MUST treat two visuals as belonging to the same row when their Y coordinates differ by no more than 2 pixels (the row-grouping tolerance).
- **FR-008**: For any pair of adjacent rows (after sorting top-to-bottom), the tool MUST compute the vertical gap as `next_row.y - (current_row.y + current_row.height)`.
- **FR-009**: The tool MUST identify each row by a visual-type label drawn from the `visual.visualType` field of its visuals; when a row's visuals have differing types it MUST warn and use a deterministic representative label.
- **FR-010**: The tool MUST never delete files, never remove keys from existing JSON files, and MUST preserve every field in `visual.json` and `page.json` other than the specific Y coordinates it is intentionally updating.

#### Learn mode

- **FR-011**: In learn mode, the tool MUST list every page found under `definition/pages/` with a numeric index and the page's `displayName`, then prompt the user to select one by number.
- **FR-012**: After a valid selection, the tool MUST analyze the chosen page, compute every adjacent-row gap, and write a `conf.md` rules file that records each rule as a from-type, to-type, and gap in pixels in a human-readable format.
- **FR-013**: In learn mode, the default output location for `conf.md` MUST be the report folder root, and the user MUST be able to override the output path via a command-line option.
- **FR-014**: When the chosen page contains the same from-type/to-type pair more than once with conflicting gaps, the tool MUST warn and record a single canonical value (deterministically chosen) so downstream modes have one rule per pair.

#### Validate mode

- **FR-015**: In validate mode, the tool MUST load rules from `conf.md` (default location: alongside the report; configurable via a command-line option) and MUST exit non-zero with a clear error if the file is missing or unparseable.
- **FR-016**: The tool MUST iterate every page in the report and, for every adjacent row pair on each page, look up the matching rule in `conf.md` and compare the actual gap to the expected gap.
- **FR-017**: The tool MUST report violations as a single tabular block whose columns are: page name, from visual type, to visual type, expected gap (px), actual gap (px), and deviation (px, signed).
- **FR-018**: The tool MUST report visual-type pairs that have no rule in `conf.md` separately as warnings (not violations) and MUST NOT count them in the failure exit code.
- **FR-019**: Validate mode MUST NOT modify any file in the report folder under any circumstances.
- **FR-026**: For every page, the tool MUST detect intra-row Y misalignments — visuals whose Y coordinate drifts from the row's modal Y by more than 0.5 pixels — and MUST report each such visual as a row misalignment with page name, visual type, visual identifier, expected Y, actual Y, and signed deviation.
- **FR-027**: For every page, when a row contains three or more visuals of the same `visual.visualType`, the tool MUST compute the consecutive horizontal gaps between those peers (sorted by X) and MUST report any gap that deviates from the row's modal horizontal gap by more than 0.5 pixels as a horizontal-spacing issue with page name, visual type, left and right visual identifiers, expected gap, actual gap, and signed deviation.
- **FR-028**: Row misalignments and horizontal-spacing issues MUST contribute to the validate-mode non-zero exit code (treated as violations for exit-code purposes) and MUST be rendered as their own tabular blocks separate from the adjacent-row gap violations table.
- **FR-029**: Same-type visuals stacked at substantially the same position (≥50 % horizontal-bounding-box overlap and Y delta < 50 % of the smaller visual's height) MUST be treated as a single visual for row grouping, gap computation, misalignment detection, and horizontal-spacing detection — preventing false positives from bookmark-driven alternate visuals.

#### Fix mode

- **FR-020**: In fix mode, the tool MUST first compute the same set of violations as validate mode and then, for each violation, plan a Y-coordinate shift that brings the actual gap to the expected gap.
- **FR-021**: When applying a shift to a row, the tool MUST also shift every row positioned below it on the same page by the same delta, so that gaps below the corrected pair are preserved relative to each other.
- **FR-022**: Fix mode MUST support a dry-run flag that prints every planned change (page, visual identifier, old Y, new Y, delta) without writing any file.
- **FR-023**: When writing back a `visual.json`, the tool MUST update only the Y position field(s) it intends to change, MUST preserve all other fields, and MUST use a write-then-rename (atomic-replace) pattern so a partially-written file can never be left on disk if the process is interrupted.
- **FR-024**: When a planned shift would push a visual past the page boundary, the tool MUST refuse that specific fix, log it as unfixable with the page and visual identifier, and continue processing remaining pages.
- **FR-025**: The tool MUST handle visuals with a `parentGroupName` (group members) using a single, documented strategy — shift the entire group as a unit when any group member would be shifted — so groups are never partially shifted.

### Key Entities *(include if feature involves data)*

- **Report folder**: A directory in PBIR format containing a `definition/pages/` subtree. The unit of input to the tool.
- **Page**: A subdirectory under `definition/pages/<page-id>/` containing a `page.json` (with at least `displayName`, `height`, `width`) and a `visuals/` subfolder. Has zero or more visuals.
- **Visual**: A `visual.json` file under a page's `visuals/<visual-id>/` describing one visible element. Carries position (X, Y), size (width, height), a `visual.visualType` label, and optionally a `parentGroupName` linking it to a group.
- **Row**: A derived grouping of visuals on a single page whose Y coordinates differ by no more than the row-grouping tolerance. Rows on a page are ordered top-to-bottom and used as the unit for gap measurement.
- **Spacing rule**: A triple of (from-type, to-type, expected gap in pixels) describing the required vertical gap between two adjacent rows of the named visual types.
- **`conf.md` rules file**: A human-readable Markdown file containing the full set of spacing rules learned from a reference page or hand-edited by a developer. Default location is alongside the report; can be overridden via CLI.
- **Violation**: A computed mismatch between an actual adjacent-row gap on some page and the expected gap from the matching rule. Carries page name, from-type, to-type, expected, actual, deviation.
- **Misalignment**: A visual whose Y coordinate differs from the modal Y of its row peers by more than the alignment tolerance. Carries page name, visual type, visual identifier, expected Y (row modal), actual Y, and signed deviation.
- **Horizontal-spacing issue**: An inconsistent horizontal gap between two same-type peers within a row of three or more such peers, where the gap deviates from the row's modal horizontal gap. Carries page name, visual type, left and right visual identifiers, expected gap, actual gap, and signed deviation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with a 40-page report can produce a `conf.md` from a chosen reference page in a single tool invocation that completes in under 10 seconds on a typical developer laptop.
- **SC-002**: Running validate against a 40-page report completes in under 15 seconds on a typical developer laptop and prints every violation in a single, non-paginated tabular block.
- **SC-003**: After running fix (without dry-run) against a report whose only issues are vertical-gap violations, re-running validate immediately afterward reports zero violations.
- **SC-004**: Across 100% of fix-mode runs, every `visual.json` and `page.json` file in the report folder remains valid JSON, retains every field that was present before the run (other than intentionally updated Y values), and is never left in a half-written state — even if the process is interrupted mid-run.
- **SC-005**: The tool builds into a single Windows executable using PyInstaller from a clean checkout with no third-party Python packages installed beyond PyInstaller itself.
- **SC-006**: A developer who has never seen the tool before can read its `--help` output and successfully run learn → validate → fix on a sample report without consulting any other documentation.
- **SC-007**: At least 90% of vertical-gap inconsistencies that a developer would catch by manual visual inspection of a published report are reported as violations by validate, when measured against an internal test corpus of representative pages.

## Assumptions

- The report is in PBIR format with the directory layout described in the feature input (`definition/pages/<page-id>/page.json` and `definition/pages/<page-id>/visuals/<visual-id>/visual.json`); legacy `.pbix` archives and other formats are out of scope.
- Visual position and size in `visual.json` are expressed in the same pixel units as page `height`/`width`, and all coordinates are non-negative numbers; no unit conversion or coordinate-system transformation is required.
- The Y-coordinate field path within `visual.json` is stable across the reports the tool will run on; the implementation will document the exact JSON path it reads/writes and treat any deviation as an error rather than silently guessing.
- Row grouping uses a fixed tolerance of ±2 pixels as stated in the feature description; this value is not user-configurable in v1.
- Visual-type comparison is case-sensitive on the value of `visual.visualType` exactly as it appears in the file; no synonym mapping (e.g., "Card" vs "card") is performed.
- Group handling strategy: when any visual in a `parentGroupName` group would be shifted by fix mode, the entire group is shifted together by the same delta. (This is the documented v1 behavior.)
- When a reference page contains conflicting gaps for the same visual-type pair, the canonical value chosen for the rule is the **most frequent** value (ties broken by the smallest gap), and the inconsistency is surfaced as a warning during learn mode.
- Colored output uses ANSI escape codes; on terminals where ANSI is not supported the tool prints plain text with no fallback library required.
- The tool runs locally on the developer's machine; no network access, telemetry, or cloud service is required or attempted.
- Row-misalignment tolerance and horizontal-spacing tolerance default to **0.5 px**; values within tolerance are considered consistent. Tolerances are constants in v1, not user-configurable.
- Bookmark-stacked visuals: Power BI reports often stack alternate same-type visuals at the same canvas position so bookmarks can toggle visibility. Such stacks are detected by ≥50 % horizontal-bounding-box overlap plus Y delta < 50 % of the smaller visual's height, and are collapsed to a single representative (smallest Y wins) before any gap or alignment analysis.
- Out of scope for this spec (deferred to a future feature): auto-positioning of new visuals from scratch, auto-fix of horizontal-spacing issues (detection only in v1), and any graphical user interface.
