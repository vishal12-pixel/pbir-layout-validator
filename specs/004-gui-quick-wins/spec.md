# Feature Specification: GUI Quick Wins (Reader Hotfix + Click-to-Open + Sort + Filter + Severity + Recents)

**Feature Branch**: `004-gui-quick-wins`
**Created**: 2026-05-01
**Status**: Draft
**Input**: User description: "lets do all the high value and small efforts in one branch — items #1 #2 #3 #4 #5 #6 from the backlog"

## Clarifications

### Session 2026-05-01

- Q: How should two same-type visuals at the same y-bucket be classified after the reader hotfix? → A: New "Duplicate Layer" tab — flag any pair of same-type visuals within row tolerance as suspicious overlap candidates.
- Q: Which file should "Open page in Power BI Desktop" launch, and how? → A: `os.startfile(<report>/definition.pbir)` — always present inside the loaded `.Report` folder, no `.pbip` fallback path needed.
- Q: Where should the recents file live and what schema? → A: `%APPDATA%\pbir_validator\recents.json` (Windows) / `~/.config/pbir_validator/recents.json` (other), schema `{"recent": ["path1", "path2", …]}` MRU-first, max 5 entries.
- Q: What happens to per-tab sort and filter state when Validate runs again? → A: Filter resets to empty; sort (column + direction) persists per tab.
- Q: Filter latency target and at what row count? → A: ≤100 ms to update visible rows for tables up to 500 rows on the dev machine; no debounce required.

## Summary

Six small, independently-shippable improvements to the Tkinter GUI plus one
correctness hotfix that the rest depend on, packaged as a single feature so
the user lifecycle (browse → validate → triage → fix → re-validate) becomes
materially faster on real reports with 50–500 violations.

The bundle deliberately does **not** introduce new validation logic, new
fixers, new file formats, or new third-party runtime dependencies. Every
story below is implementable in stdlib-only Python with the existing
ttk widgets.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Validator stops silently dropping visuals (Priority: P1) 🐛 hotfix

When a `.Report` page contains two visuals at near-identical y-coordinates
(e.g., bookmark-layered pivot tables, banner-layered shapes), the current
analyzer collapses them into a single "row" and reports a count smaller than
the number of `visual.json` files on disk. Users running Validate then see
results that don't match what Power BI Desktop's Selection pane shows,
breaking trust in every other number the tool produces.

**Why this priority**: Correctness bug. Until this is fixed, every other
quick win amplifies misleading data. P1.

**Independent Test**: Build a synthetic `.Report` with two pivot tables at
y=322.7 and y=343.0 (same x, different heights). Run Validate. Assert that
both visual ids appear in the analyzer's output and at least one of the
gap-or-overlap reports references each id.

**Acceptance Scenarios**:

1. **Given** a page on disk with N visual.json files, **When** Validate runs,
   **Then** every one of the N visuals is represented in at least one of:
   the row-grouping output, the misalignment list, or the overlap list.
2. **Given** two same-type visuals at y-deltas under the row tolerance,
   **When** Validate runs, **Then** they appear in a new **Duplicate Layer**
   tab (not silently merged, not as Row Misalignment).
3. **Given** the FY26 Q1 M365 E3 page from the user's reference report
   (6 pivot tables in 3 stacked pairs), **When** Validate runs, **Then** the
   GUI's Duplicate Layer tab lists all 3 pairs by their visible titles.

---

### User Story 2 — Right-click a row → open the page in Power BI Desktop (Priority: P1)

Today, after Validate surfaces a violation, the user must alt-tab, open
Power BI Desktop manually, locate the right page in the bottom tab bar, and
hunt for the visual. We close that loop with a context menu.

**Why this priority**: Single biggest UX win in the bundle — turns
"found a bug" into "I'm in PBI Desktop fixing the bug" in one click.

**Independent Test**: Right-click a row on Gap Violations / Overlapping
Visuals / Duplicate Layer / Row Misalignments / Horizontal Spacing
tabs. The menu offers "Open page in Power BI Desktop". Selecting it
launches the `.pbip` associated with the loaded report.

**Acceptance Scenarios**:

1. **Given** a report has been loaded and Validate has populated rows,
   **When** the user right-clicks any row on any of the five result tabs,
   **Then** a context menu appears with at minimum "Open page in Power BI
   Desktop" and "Copy row".
2. **Given** the user clicks "Open page in Power BI Desktop", **When**
   `definition.pbir` exists at the root of the loaded `.Report` folder
   (always true for valid PBIR reports), **Then** `os.startfile` is
   invoked against that path and the OS launches Power BI Desktop.
3. **Given** the loaded folder is missing `definition.pbir` (corrupt or
   non-PBIR input), **When** the user clicks "Open page in Power BI
   Desktop", **Then** an informational message explains the file is
   missing. Validate still works without the launch capability.
4. **Given** the user clicks "Copy row", **When** the clipboard is
   inspected, **Then** it contains a tab-separated representation of the
   selected row's columns.

---

### User Story 3 — Click a column header to sort (Priority: P1)

The Treeview already supports column sorting via Tkinter built-ins. Users
expect to click "Deviation Px" and see the worst offenders at the top.
Today the table is presented in validator-emit order.

**Why this priority**: Tiny code, large payoff for triage on long lists.

**Independent Test**: After Validate populates rows, click any column
header. The rows reorder ascending. Click again — descending. A small
arrow indicator on the active column shows direction.

**Acceptance Scenarios**:

1. **Given** rows are present in the Gap Violations table, **When** the
   user clicks the "Deviation Px" header, **Then** rows reorder by that
   column ascending and the header shows ▲.
2. **Given** the column is already sorted ascending, **When** the user
   clicks it again, **Then** rows reorder descending and the header
   shows ▼.
3. **Given** numeric columns ("Expected Px", "Actual Px", "Deviation Px",
   "Overlap Px"), **When** sorted, **Then** sort order is numeric (e.g.
   `9 < 10 < 17`), not lexical (e.g. not `10 < 17 < 9`).
4. **Given** text columns ("Page", "From", "To"), **When** sorted, **Then**
   sort order is case-insensitive lexical.

---

### User Story 4 — Filter box at the top of each result tab (Priority: P2)

A free-text filter box at the top of each result tab narrows visible rows
to those containing the typed substring (case-insensitive) in any column.
Empty filter shows everything. Filtering is live (per keystroke) but cheap.

**Why this priority**: On reports with 200+ violations, scanning is slow.
Filtering by visual type ("actionButton") or page name ("FY26") shrinks
the workload to seconds.

**Independent Test**: Type "card" in the filter box on Gap Violations.
Only rows mentioning "card" remain. Clear the filter — all rows return.

**Acceptance Scenarios**:

1. **Given** rows are present, **When** the user types text in the filter
   box, **Then** only rows where any cell contains that substring
   (case-insensitive) remain visible.
2. **Given** a filter is active, **When** the user clears the filter,
   **Then** all original rows return in their previous sort order.
3. **Given** a filter and a column sort are both active, **When** the user
   types or sorts, **Then** both transformations compose (sort applies to
   the filtered subset).
4. **Given** the user runs Validate while a filter is active, **When**
   results arrive, **Then** the filter is reset to empty so the user sees
   all new findings.

---

### User Story 5 — Severity color on numeric deviation columns (Priority: P2)

Color tags applied to row-cells (or whole rows) on numeric severity
columns: green for ≤ 2 px deviation, yellow for 3–10 px, red for > 10 px
or any overlap > 0 px. Lets users scan a long table at a glance.

**Why this priority**: Visual triage is faster than reading numbers. Pairs
naturally with sort/filter. P2 because not strictly required to use the
tool.

**Independent Test**: Load a report with mixed deviations. Visually
confirm green/yellow/red bands. Programmatically: Treeview row tags
should match the expected band per row.

**Acceptance Scenarios**:

1. **Given** a Gap Violations row with `|deviation_px| ≤ 2`, **When**
   rendered, **Then** the row has a "green" tag.
2. **Given** a row with `2 < |deviation_px| ≤ 10`, **When** rendered,
   **Then** the row has a "yellow" tag.
3. **Given** a row with `|deviation_px| > 10`, **When** rendered, **Then**
   the row has a "red" tag.
4. **Given** an Overlapping Visuals row, **When** rendered, **Then** the
   row has at least the "yellow" tag (any overlap is concerning), with
   "red" applied for overlap_px > 50.
5. **Given** the user's OS theme is dark, **When** colors are picked,
   **Then** the chosen RGB values remain legible in dark mode (high
   contrast against the Treeview background).

---

### User Story 6 — Recent reports menu (Priority: P3)

A "Recent reports" dropdown remembers the last 5 successful report paths
in a per-user JSON file. Selecting one re-loads it without using the
Browse buttons.

**Why this priority**: Convenience win during iterative work where the
user runs Validate dozens of times against the same report.

**Independent Test**: Open report A, then B, then C. The dropdown shows
[C, B, A]. Click A — the report loads.

**Acceptance Scenarios**:

1. **Given** the user successfully loads a report, **When** the next
   GUI launch happens, **Then** that path appears in the Recent dropdown.
2. **Given** the dropdown contains 5 entries, **When** the user opens a
   6th distinct report, **Then** the oldest entry is evicted (FIFO).
3. **Given** a recent entry no longer exists on disk, **When** the user
   selects it, **Then** an informational message explains the path is
   missing and the entry is removed from the list.
4. **Given** no recent reports exist (first launch), **When** the user
   opens the dropdown, **Then** it shows a single placeholder item
   "(no recent reports)" and is disabled.
5. **Given** any platform, **When** the recent file is written, **Then**
   the user-config location is OS-conventional (`%APPDATA%` on Windows,
   `~/.config/pbir_validator` on Linux/macOS).

---

### Edge Cases

- **No `definition.pbir`**: launching the page in Power BI Desktop must
  fail gracefully (informational message) rather than crashing.
- **Recent file corrupted JSON**: the app must start with an empty
  recents list rather than crashing.
- **Filter regex characters**: filter input is treated as a plain
  substring; users typing `(` or `*` see no error.
- **Sort on heterogeneous column**: numeric sort attempted on a column
  containing a mix (shouldn't happen in current data, but if it does)
  must fall back to string sort silently.
- **Reader hotfix scope**: must not introduce new violations on existing
  reports that today validate successfully (no new false positives).
- **Disk-permission failure on recent-reports file**: the app must
  continue to function without persistence (next session forgets).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analyzer's row grouper MUST preserve every `Visual`
  instance produced by the reader (one per `visual.json` file in a
  page's `visuals/` directory).
- **FR-002**: The row grouper MUST NOT discard visuals that share or
  near-share a y-coordinate with a previously processed visual.
- **FR-003**: When two same-type visuals share the same y bucket (within
  row tolerance), the analyzer MUST surface them in a new **Duplicate
  Layer** result category (a 5th GUI tab), not collapse them and not
  conflate them with Row Misalignment or Overlap.
- **FR-003a**: The GUI MUST add a "Duplicate Layer" tab adjacent to
  "Overlapping Visuals". Columns: Page, Visual Type, Visual A, Visual B,
  Δy Px. All other quick-win features (sort, filter, severity, context
  menu) MUST apply to this new tab on equal footing.
- **FR-004**: Right-clicking a row on any of the **five** result tabs
  (Gap Violations, Overlapping Visuals, Duplicate Layer, Row
  Misalignments, Horizontal Spacing) MUST display a context menu with
  at least these items: "Open page in Power BI Desktop" and "Copy row".
- **FR-005**: "Open page in Power BI Desktop" MUST invoke
  `os.startfile(<report_root>/definition.pbir)` to launch the report via
  the OS file association. When `definition.pbir` is missing, clicking
  the menu item MUST display an informational message identifying the
  missing path; the application MUST NOT crash.
- **FR-006**: "Copy row" MUST place a tab-separated string of the row's
  cells onto the system clipboard.
- **FR-007**: Clicking a Treeview column header MUST sort the visible
  rows by that column.
- **FR-008**: Sorting MUST toggle ascending → descending → ascending on
  repeated clicks of the same header.
- **FR-009**: Numeric columns MUST be sorted by numeric value, not
  lexically.
- **FR-010**: Each result tab MUST display a single-line filter box
  above its table.
- **FR-011**: Typing in the filter box MUST hide rows whose concatenated
  cell strings do not contain the filter text (case-insensitive).
- **FR-012**: When sorting and filtering are both active, the visible
  rows MUST be the result of filter-then-sort.
- **FR-013**: Running Validate MUST clear all filter boxes.
- **FR-013a**: Running Validate MUST preserve each tab's active sort
  state (column index + direction) and re-apply it to the new rows.
- **FR-014**: Each row in Gap Violations, Overlapping Visuals, Row
  Misalignments, Horizontal Spacing, and Duplicate Layer MUST carry a
  severity tag (`sev_green`, `sev_yellow`, or `sev_red`) per the
  thresholds in research D5. Duplicate Layer rows are always tagged
  `sev_yellow`.
- **FR-015**: Severity colors MUST remain legible against the active
  Treeview background regardless of the OS theme.
- **FR-016**: The application MUST persist the last 5 successful report
  paths to `%APPDATA%\pbir_validator\recents.json` on Windows (or
  `~/.config/pbir_validator/recents.json` on POSIX) using the schema
  `{"recent": ["<path1>", "<path2>", …]}` with MRU at index 0.
- **FR-017**: The Recent menu MUST evict the oldest entry when a 6th
  distinct path is loaded.
- **FR-018**: Selecting a recent entry MUST attempt to load that path
  via the same code path as Browse buttons; on failure the entry MUST be
  removed from the list and an informational message shown.
- **FR-019**: A missing or unreadable recents file MUST NOT crash the
  application; the list MUST start empty in that case.
- **FR-020**: All new code MUST remain stdlib-only at runtime
  (constitution Principle I).
- **FR-021**: The CLI surface (entry points, output, exit codes) MUST be
  unchanged by this feature.

### Key Entities

- **VisualReader output**: an iterable of `Visual` instances; the
  invariant "one per visual.json" is the heart of FR-001.
- **ContextMenu**: a `tk.Menu` populated per-tab with bindings to the
  selected Treeview row.
- **SortState**: per-tab record `(column_index, direction)`; plus
  per-row index so filtering preserves identity.
- **FilterState**: per-tab `tk.StringVar` driving a trace callback that
  hides/shows rows.
- **SeverityBand**: enum-like constants used as Treeview tag names so
  styling can be configured once at app construction time.
- **RecentsStore**: read/write helper around the JSON file under the
  user-config dir; bounded to 5 entries; FIFO eviction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the reader hotfix, the FY26 Q1 M365 E3 reference
  page shows 6 pivot tables (matching its 6 `visual.json` files) instead
  of 4 (today's count).
- **SC-002**: On a 200-row Gap Violations table, time to locate the
  worst-deviation row drops from "scan all 200" to "click header once"
  (one-click sort).
- **SC-003**: On a 200-row Gap Violations table, time to filter to a
  single visual type drops to under 3 seconds (type 4 letters → done).
- **SC-003a**: Filter input updates the visible row set within 100 ms
  for tables up to 500 rows (measured on the dev machine, no debounce).
- **SC-004**: After right-clicking a row and choosing "Open page in
  Power BI Desktop", the user reaches the page in PBI Desktop in under
  5 seconds with no terminal commands.
- **SC-005**: 100% of new GUI tests pass headlessly on Windows; the smoke
  test (display-required) passes locally on the user's dev machine.
- **SC-006**: 100% of pre-existing tests (166 currently passing) remain
  passing — feature is fully backward-compatible.
- **SC-007**: Coverage gate stays ≥ 80%; targeted modules
  (`analyzer.py`, `controllers.py`, new `recents.py`, new `severity.py`)
  reach ≥ 90%.

## Assumptions

- Power BI Desktop is the OS default handler for `.pbir` files (true on
  any developer machine where Power BI Desktop is installed). On
  machines without it, US2 falls back to "show informational message".
- Tkinter Treeview's tag-coloring works on all three target platforms
  (Windows, macOS, Linux). On Linux, ttk-themed Treeview honors row
  background tags only with the default theme; we accept this trade-off.
- Filter performance is acceptable up to 500 rows per tab without
  debouncing (target: ≤100 ms per keystroke). Beyond 500 rows we'd
  need debouncing, but no real PBIR report produces that many
  violations.
- Recents file path collision (multiple users on a shared machine) is
  resolved by living under per-user `%APPDATA%`/`~/.config`, not the
  system-wide install location.
- The reader hotfix does not require changing `Visual` or `Page`
  dataclasses; the bug is in the analyzer's row-grouping logic.
- No new third-party runtime dependencies. Stdlib only (`json`,
  `pathlib`, `os`, `tkinter`).
- The CLI must remain byte-identical in output and exit codes; the
  reader hotfix is a strict superset of today's behavior.
