# Feature Specification: Horizontal Spacing Auto-Fix

**Feature Branch**: `006-hspacing-autofix`  
**Created**: 2026-05-02  
**Status**: Draft  
**Input**: User description: "Add auto-fixer for horizontal spacing issues detected by find_row_hspacing_issues — adjust position.x to equalize gaps to modal gap, with undo, boundary checks, profile gating, GUI Fix Plan tab, and CLI support."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CLI Auto-Fix of Uneven Horizontal Gaps (Priority: P1)

A Power BI report author runs the validator CLI in `fix` mode against a report where a row of 6 slicers has one slicer offset by 2 px, creating an uneven horizontal gap. The fixer detects the h-spacing issue, plans X-shifts to equalize all gaps to the modal value, writes the corrected `position.x` values, and reports a summary of changes.

**Why this priority**: The CLI fix is the core deliverable — without it no horizontal spacing correction happens. All other stories layer on top.

**Independent Test**: Run `pbir_validator fix <report>` with a Strict profile against a report with a known 2 px h-spacing deviation; verify the visual JSON files have corrected `position.x` values and gaps are equalized.

**Acceptance Scenarios**:

1. **Given** a report with 6 same-type slicers in one row and one gap deviating by 2 px from the modal gap, **When** the user runs the fix command with a profile that enables h-spacing fixes, **Then** the deviant visual and all same-type peers to its right in the row are shifted left by 2 px, and all horizontal gaps in that row become equal to the modal gap.
2. **Given** a report with h-spacing issues on multiple pages, **When** the user runs the fix command, **Then** each page's issues are fixed independently with no cross-page cascading.
3. **Given** a report with no h-spacing issues, **When** the user runs the fix command, **Then** no X-shifts are emitted and existing Y-gap fix output remains byte-identical to current behavior.

---

### User Story 2 - Page-Width Boundary Refusal (Priority: P1)

When a planned X-shift would push a visual's right edge (`x + width`) past the page width, the fix is marked as unfixable and skipped. Other fixable h-spacing issues on the same page are still applied.

**Why this priority**: Without boundary checks the fixer could produce invalid layouts that break rendering. This is a safety requirement co-equal with the core fix.

**Independent Test**: Create a test visual positioned near the right page edge such that the required shift would push `x + width` past `page.width`; verify the issue is marked unfixable and no X-shift is written.

**Acceptance Scenarios**:

1. **Given** a visual at `x=1240, width=40` on a page of width `1280` and a required shift of `+5 px`, **When** the fixer plans the shift, **Then** the issue is marked unfixable with a reason string and no write occurs for that visual.
2. **Given** one unfixable and one fixable h-spacing issue on the same page, **When** the fixer runs, **Then** only the fixable issue produces X-shifts; the unfixable issue is reported but not applied.

---

### User Story 3 - Undo Restores X Changes (Priority: P1)

After an h-spacing fix, the undo mechanism must be able to restore all changed `position.x` values byte-for-byte, just as it does for `position.y` today.

**Why this priority**: Undo is a safety net. Without it users cannot revert accidental or unwanted fixes, making the feature too risky to ship.

**Independent Test**: Apply an h-spacing fix, then invoke undo; verify each affected visual JSON file is byte-identical to its pre-fix state.

**Acceptance Scenarios**:

1. **Given** an h-spacing fix was just applied that shifted 3 visuals' X positions, **When** the user invokes undo, **Then** all 3 visuals' `position.x` values are restored to their original values and the files are byte-identical to their pre-fix content.
2. **Given** a fix that applied both Y-shifts and X-shifts, **When** the user invokes undo, **Then** both Y and X coordinates are restored for all affected visuals.

---

### User Story 4 - Profile-Gated H-Spacing Fixes (Priority: P2)

The h-spacing auto-fix only runs when the active profile enables it. The Strict profile enables h-spacing fixes; Standard and Relaxed profiles do not.

**Why this priority**: Profile gating keeps the fix opt-in for cautious users and prevents unwanted X mutations under the default profile.

**Independent Test**: Run fix under Standard profile with h-spacing issues present; verify zero X-shifts are planned. Switch to Strict profile; verify X-shifts appear.

**Acceptance Scenarios**:

1. **Given** a report with h-spacing issues and the Standard profile active, **When** the user runs the fix command, **Then** no X-shifts are planned or applied.
2. **Given** the same report with the Strict profile active, **When** the user runs the fix command, **Then** X-shifts are planned and applied to equalize horizontal gaps.
3. **Given** a Report-default profile with `hspacing_fix: true` specified, **When** the user runs the fix command, **Then** X-shifts are planned and applied.

---

### User Story 5 - GUI Fix Plan Shows X-Shifts (Priority: P2)

The Fix Plan tab in the GUI shows X-shift rows alongside existing Y-shift rows. Each X-shift row displays the action label "shift-x", the affected visual, the old and new X coordinates, and the delta.

**Why this priority**: GUI visibility ensures users can review X-shifts before applying, maintaining the existing review-then-apply workflow.

**Independent Test**: Load a report with h-spacing issues in the GUI with Strict profile, click Validate, then view the Fix Plan tab; verify X-shift rows appear with correct data.

**Acceptance Scenarios**:

1. **Given** a validated report with h-spacing issues under Strict profile, **When** the user views the Fix Plan tab, **Then** X-shift rows with action "shift-x" are displayed showing visual ID, page, old X, new X, and delta.
2. **Given** a validated report with both Y-gap and h-spacing issues, **When** the user views the Fix Plan tab, **Then** both Y-shift and X-shift rows are displayed with their respective action labels.

---

### User Story 6 - CLI Fix Summary Includes X-Shifts (Priority: P3)

The CLI `fix` command's plan summary table includes X-shift entries alongside Y-shift entries, with a distinct action label.

**Why this priority**: CLI parity with the GUI — lower priority because CLI users can also inspect the JSON output directly.

**Independent Test**: Run fix in CLI mode with h-spacing issues; verify the printed summary contains X-shift lines.

**Acceptance Scenarios**:

1. **Given** a report with h-spacing issues, **When** the user runs the CLI fix command, **Then** the plan summary includes lines showing X-shift actions with visual IDs, page names, old X, new X, and delta values.

---

### Edge Cases

- What happens when a row has exactly 2 same-type visuals? No h-spacing issue is detected (requires ≥3), so no fix is attempted.
- What happens when all gaps in a row are already equal? No h-spacing issue exists, no fix is planned.
- What happens when the shift would move a visual to a negative X coordinate? The visual's `x` coordinate must remain ≥ 0; if the shift would produce `x < 0`, the issue is marked unfixable.
- What happens when multiple h-spacing issues exist in the same row (multiple gaps deviate)? Each deviant gap produces a shift; visuals to the right of each deviation are shifted cumulatively to equalize all gaps left-to-right.
- What happens when a row contains visuals of mixed types? H-spacing analysis is per-type within a row, so only same-type peer groups with ≥3 members are evaluated.
- What happens when h-spacing fix is disabled in the profile but Y-gap fix is enabled? Only Y-shifts are planned and applied; X-shifts are skipped entirely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The fixer MUST plan X-shifts for each `HSpacingIssue` detected by `find_row_hspacing_issues`, shifting the right-side visual and all same-type peers to its right in the row by `-deviation_px` to equalize the gap to the modal value.
- **FR-002**: X-shifts MUST be row-local — no cascading to visuals in other rows or on other pages.
- **FR-003**: `writer.write_visual_json` MUST accept an optional `new_x` parameter to mutate `position.x` using the same atomic write pattern (tempfile + `os.replace`) as `new_y`.
- **FR-004**: When both `new_x` and `new_y` are provided to `write_visual_json`, both coordinates MUST be written in a single atomic operation.
- **FR-005**: If a planned X-shift would cause `x + width > page.width` for any affected visual, that issue MUST be marked unfixable with a descriptive reason and no X-writes emitted for it.
- **FR-006**: If a planned X-shift would cause `x < 0` for any affected visual, that issue MUST be marked unfixable.
- **FR-007**: The undo backup MUST store `old_x` alongside `old_y` for every shift that modifies `position.x`, enabling byte-for-byte restoration of both coordinates.
- **FR-008**: When restoring from undo, `write_visual_json` MUST restore `position.x` if `old_x` is present in the backup entry.
- **FR-009**: The Fix Plan tab in the GUI MUST display X-shift rows with action label "shift-x" alongside existing Y-shift rows.
- **FR-010**: The CLI fix command MUST include X-shifts in the plan summary output.
- **FR-011**: H-spacing auto-fix MUST only be applied when the active profile enables it via a `hspacing_fix` flag.
- **FR-012**: The Strict profile MUST enable h-spacing fixes (`hspacing_fix: true`). Standard and Relaxed profiles MUST NOT enable h-spacing fixes.
- **FR-013**: When no h-spacing issues exist, the Y-gap fix flow MUST produce byte-identical output to current behavior (no regressions).
- **FR-014**: X-shift writes MUST preserve key order, indentation, trailing newline, and int-vs-float formatting (byte-conservative writes).
- **FR-015**: X-shift writes MUST use atomic writes via tempfile + `os.replace`.
- **FR-016**: The `Shift` model MUST be extended to carry `old_x`, `new_x`, and `delta_x` fields (defaulting to `None` for backward compatibility with Y-only shifts).

### Key Entities

- **Shift**: Extended with optional `old_x`, `new_x`, `delta_x` fields to represent X-coordinate mutations alongside existing Y-coordinate fields.
- **HSpacingIssue**: Existing entity — the input signal that triggers X-shift planning. Contains `deviation_px`, `expected_gap_px`, `actual_gap_px`, left/right visual IDs, and row index.
- **Undo Backup**: Extended from `{path, visual_id, old_y, new_y}` to include `old_x` and `new_x` when an X-shift was applied.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any report with ≥1 horizontal spacing deviation, running the fixer with Strict profile eliminates 100% of fixable h-spacing issues as measured by a re-validation pass.
- **SC-002**: Undo after an h-spacing fix restores all affected visual JSON files to byte-identical pre-fix content in 100% of cases.
- **SC-003**: Running the fixer on a report with zero h-spacing issues produces zero file changes compared to current behavior.
- **SC-004**: The canonical test case (6 slicers in a row, one with 2 px gap deviation) is resolved in a single fix invocation.
- **SC-005**: New code achieves ≥80% line coverage and ≥90% branch coverage.
- **SC-006**: No runtime dependencies beyond the Python standard library are introduced.

## Assumptions

- The existing `find_row_hspacing_issues` detection in `analyzer.py` is correct and complete — this feature consumes its output without modifying detection logic.
- The modal gap value computed by `find_row_hspacing_issues` is the correct target for equalization (most-common gap among same-type peers in the row).
- The `Shift` dataclass can be extended with optional fields (`old_x`, `new_x`, `delta_x`) defaulting to `None` without breaking existing Y-only shift consumers.
- Profile `hspacing_fix` flag defaults to `false` when not explicitly specified in a profile configuration.
- The existing atomic write pattern (tempfile + `os.replace`) is sufficient for X-coordinate writes — no new IO patterns are needed.
- Report-default profiles (`conf.md`) can opt into h-spacing fixes by adding `hspacing_fix: true` to their configuration.
- The visual's `x` coordinate in the JSON is always an integer or float at the top level of `position.x` (same structure as `position.y`).
