# Tasks: Horizontal Spacing Auto-Fix

**Input**: Design documents from `/specs/006-hspacing-autofix/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/shift-x-contract.md, research.md, quickstart.md

**Tests**: Constitution Principle II (NON-NEGOTIABLE) requires all parsing and calculation logic to be covered by automated tests before merge. Test tasks are included in each phase after the corresponding implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend foundational models and create test fixture data shared by all user stories

- [X] T001 Extend `Shift` dataclass with optional `old_x`, `new_x`, `delta_x` fields (all defaulting to `None`) in pbir_validator/models.py
- [X] T002 [P] Create h-spacing test fixture report directory at tests/fixtures/hspacing_report/ with a realistic PBIR structure: page.json defining page width (e.g., 1280), 6 same-type slicer visual directories each with visual.json containing `position.x`, `position.y`, `width`, `height` — one slicer with a 2 px gap deviation from the modal gap. Include a second page with a visual near the right edge (x=1245, width=40) for boundary-refusal testing.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core writer and profile infrastructure that MUST be complete before any user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Extend `write_visual_json()` in pbir_validator/writer.py to accept optional `new_x: float | None = None` keyword argument — when provided, mutate `position.x` in the same atomic write as `position.y`, preserving int-ness, key order, indentation, and trailing newline (FR-003, FR-004, FR-014, FR-015)
- [X] T004 [P] Add `# hspacing_fix = true` comment line to pbir_validator/profiles/strict.md header
- [X] T005 [P] Add `hspacing_fix` flag parsing in pbir_validator/gui/profiles.py — scan profile header comment lines for `hspacing_fix\s*=\s*(true|false)`, return `True`/`False`, default `False` when absent (C6)

**Checkpoint**: Foundation ready — writer supports X+Y atomic writes, profile gating is parseable

### Tests for Phase 2

- [X] T020 [P] Create tests/test_writer_x.py — unit tests for `write_visual_json()` with `new_x`: (1) X-only write mutates `position.x` and preserves `position.y`, (2) combined X+Y write mutates both in single atomic op, (3) `new_x=None` leaves `position.x` unchanged, (4) int-vs-float preservation for X, (5) key order and indentation preserved (byte-conservative round-trip)

---

## Phase 3: User Story 1 — CLI Auto-Fix of Uneven Horizontal Gaps (Priority: P1) 🎯 MVP

**Goal**: The fixer detects h-spacing issues, plans X-shifts to equalize all gaps to the modal value, writes corrected `position.x` values, and reports a summary of changes.

**Independent Test**: Run `pbir_validator fix <report>` with Strict profile against the fixture report with known 2 px h-spacing deviation; verify visual JSON files have corrected `position.x` values and gaps are equalized.

### Implementation for User Story 1

- [X] T006 [US1] Implement `plan_hspacing_fixes()` function in pbir_validator/fixer.py — group issues by `(page_id, row_index, visual_type)`, reconstruct sorted peer list, walk gaps left-to-right computing cumulative corrections `-(actual_gap - modal_gap)`, emit `Shift` objects with `old_x`/`new_x`/`delta_x` populated and `delta_y=0` (C1, FR-001, FR-002)
- [X] T007 [US1] Integrate `plan_hspacing_fixes()` into `plan_fixes()` in pbir_validator/fixer.py — when `profile_flags` includes `hspacing_fix=True`, call `plan_hspacing_fixes()` after Y-shift planning and merge X-shifts into the unified `Shift` list (FR-011)
- [X] T008 [US1] Update the shift application loop in pbir_validator/fixer.py (or the caller that invokes `write_visual_json`) to pass `new_x=shift.new_x` when `shift.old_x is not None`

**Checkpoint**: CLI fix with Strict profile corrects h-spacing deviations end-to-end

### Tests for Phase 3

- [X] T021 Create tests/test_hspacing_fix.py — unit tests for `plan_hspacing_fixes()`: (1) 6 same-type slicers with one 2 px deviation → correct X-shifts emitted, (2) cumulative left-to-right correction when multiple gaps deviate, (3) row with zero deviations → zero shifts, (4) row with <3 same-type visuals → no fix attempted, (5) multi-page report → page-independent fixes, (6) shift objects have correct `old_x`/`new_x`/`delta_x` and `delta_y=0`
- [X] T022 [P] Add integration test in tests/test_hspacing_fix.py — run fixer end-to-end against fixture report, verify visual JSON files have corrected `position.x` values and re-validation shows zero h-spacing issues (SC-001, SC-004)

---

## Phase 4: User Story 2 — Page-Width Boundary Refusal (Priority: P1)

**Goal**: X-shifts that would push a visual out of bounds (`x < 0` or `x + width > page.width`) are marked unfixable and skipped; other fixable issues still apply.

**Independent Test**: Create a visual near the right page edge such that the shift would exceed `page.width`; verify the issue is skipped and no X-shift is written.

### Implementation for User Story 2

- [X] T009 [US2] Add boundary checks to `plan_hspacing_fixes()` in pbir_validator/fixer.py — after computing all cumulative corrections for a type-group, verify `new_x >= 0` and `new_x + width <= page.width` for every affected visual; if any fails, mark the entire group unfixable with a reason string and emit zero shifts for it (FR-005, FR-006)
- [X] T010 [US2] Return unfixable issues from `plan_hspacing_fixes()` as the second element of the return tuple, each annotated with a descriptive reason (C1 output contract)

**Checkpoint**: Boundary violations are safely refused; fixable issues on the same page still proceed

### Tests for Phase 4

- [X] T023 Add boundary-refusal tests in tests/test_hspacing_fix.py — (1) visual at right edge where shift would cause `x + width > page_width` → marked unfixable, (2) shift producing `x < 0` → marked unfixable, (3) one unfixable + one fixable group on same page → only fixable group gets shifts (FR-005, FR-006)

---

## Phase 5: User Story 3 — Undo Restores X Changes (Priority: P1)

**Goal**: After an h-spacing fix, undo restores all changed `position.x` values byte-for-byte.

**Independent Test**: Apply an h-spacing fix, invoke undo, verify each affected visual JSON file is byte-identical to its pre-fix state.

### Implementation for User Story 3

- [X] T011 [US3] Extend `record_pre_fix()` in pbir_validator/gui/undo.py to write `old_x` and `new_x` keys in the backup entry dict when `shift.old_x is not None` (FR-007, C3)
- [X] T012 [US3] Extend `restore_last_fix()` in pbir_validator/gui/undo.py to pass `new_x=entry["old_x"]` to `write_visual_json()` when `old_x` is present in the backup entry, restoring the original X coordinate (FR-008, C3)

**Checkpoint**: Undo round-trips both Y and X coordinates correctly

### Tests for Phase 5

- [X] T024 Create tests/test_undo_x.py — (1) undo after X-only fix restores `position.x` byte-for-byte, (2) undo after combined X+Y fix restores both coordinates, (3) undo entry without `old_x` key is handled gracefully (backward compat with pre-X backups) (SC-002, FR-007, FR-008)

---

## Phase 6: User Story 4 — Profile-Gated H-Spacing Fixes (Priority: P2)

**Goal**: H-spacing auto-fix only runs when the active profile enables it via `hspacing_fix` flag. Strict enables it; Standard and Relaxed do not.

**Independent Test**: Run fix under Standard profile with h-spacing issues present; verify zero X-shifts are planned. Switch to Strict; verify X-shifts appear.

### Implementation for User Story 4

- [ ] T013 [US4] Wire the parsed `hspacing_fix` flag from `profiles.py` into the `profile_flags` dict passed to `plan_fixes()` — ensure the flag flows from profile loading through to the fixer in pbir_validator/gui/profiles.py and pbir_validator/cli.py
- [X] T014 [US4] Verify `plan_fixes()` in pbir_validator/fixer.py skips `plan_hspacing_fixes()` entirely when `hspacing_fix` is `False` or absent from `profile_flags`, producing zero X-shifts and byte-identical output to current behavior (FR-013)

**Checkpoint**: Standard/Relaxed profiles produce no X-shifts; Strict profile triggers X-shift planning

### Tests for Phase 6

- [X] T025 Add profile-gating tests in tests/test_hspacing_fix.py — (1) Strict profile parses `hspacing_fix=True`, (2) Standard profile returns `hspacing_fix=False` (absent flag), (3) Relaxed profile returns `hspacing_fix=False`, (4) `plan_fixes()` with `hspacing_fix=False` produces zero X-shifts, (5) `plan_fixes()` with `hspacing_fix=True` produces X-shifts (FR-011, FR-012)

---

## Phase 7: User Story 5 — GUI Fix Plan Shows X-Shifts (Priority: P2)

**Goal**: The Fix Plan tab in the GUI shows X-shift rows alongside existing Y-shift rows with action label "shift-x".

**Independent Test**: Load a report with h-spacing issues in the GUI with Strict profile, validate, view Fix Plan tab; verify X-shift rows appear with correct data.

### Implementation for User Story 5

- [X] T015 [US5] Extend `fix_plan_rows()` in pbir_validator/gui/controllers.py to emit X-shift rows with action `"shift-x"` for each `Shift` where `delta_x is not None and delta_x != 0`, showing `old_x`, `new_x`, `delta_x` — a shift with both Y and X changes produces two rows (C4)

**Checkpoint**: GUI Fix Plan tab displays both Y-shift and X-shift rows

---

## Phase 8: User Story 6 — CLI Fix Summary Includes X-Shifts (Priority: P3)

**Goal**: The CLI fix plan summary table includes X-shift entries with a distinct action label.

**Independent Test**: Run fix in CLI mode with h-spacing issues; verify the printed summary contains X-shift lines with action "shift-x".

### Implementation for User Story 6

- [X] T016 [US6] Extend `print_shift_plan()` in pbir_validator/ui.py to add an "Action" column distinguishing `shift-y` from `shift-x` rows — emit an X-shift row for each `Shift` with non-zero `delta_x`, and a Y-shift row for each `Shift` with non-zero `delta_y` (C5)

**Checkpoint**: CLI summary shows both Y-shift and X-shift actions

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Validation, regression checks, and documentation

- [X] T017 Verify no-op regression: run the fixer on a report with zero h-spacing issues and confirm output is byte-identical to current behavior (FR-013, SC-003)
- [X] T018 [P] Run quickstart.md validation end-to-end against the fixture report to confirm the documented workflow works
- [X] T019 [P] Run full test suite (`python -m pytest tests/ -q --no-header -m "not benchmark"`) and confirm no regressions
- [X] T026 Run coverage check (`python -m pytest tests/ --cov=pbir_validator --cov-branch -q`) and verify ≥80% line coverage and ≥90% branch coverage on new modules (SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on T001 (Shift model extension) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (T003, T004, T005) — core fix logic
- **US2 (Phase 4)**: Depends on T006 (plan_hspacing_fixes exists) — adds boundary checks to it
- **US3 (Phase 5)**: Depends on T003 (writer supports new_x) — extends undo to store/restore X
- **US4 (Phase 6)**: Depends on T005 (profile parsing) and T007 (plan_fixes integration) — wires gating end-to-end
- **US5 (Phase 7)**: Depends on T001 (Shift has X fields) — GUI display only
- **US6 (Phase 8)**: Depends on T001 (Shift has X fields) — CLI display only
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only — MVP, no other story dependencies
- **US2 (P1)**: Depends on US1 (T006) — extends the same function with boundary checks
- **US3 (P1)**: Depends on Foundational (T003) — independent of US1/US2 implementation
- **US4 (P2)**: Depends on Foundational (T005) and US1 (T007) — wires profile flag to fixer
- **US5 (P2)**: Independent of other stories after Foundational — reads Shift objects only
- **US6 (P3)**: Independent of other stories after Foundational — reads Shift objects only

### Parallel Opportunities

- T002, T004, T005 can all run in parallel (different files, no dependencies on each other)
- US3 (undo) and US5 (GUI display) and US6 (CLI display) can run in parallel after Foundational
- T017, T018, T019 can all run in parallel in the Polish phase

### Within Each User Story

- Models before services/functions
- Core logic before integration
- Story complete before moving to next priority

---

## Parallel Example: After Foundational

```
                  ┌── US1 (T006→T007→T008) ──→ US2 (T009→T010)
Foundational ─────┤
(T003, T004, T005)├── US3 (T011→T012)
                  ├── US5 (T015)
                  └── US6 (T016)
                                              US4 (T013→T014) ← after US1 T007
```

---

## Implementation Strategy

- **MVP**: Phase 1 + Phase 2 + Phase 3 (User Story 1) — delivers the core CLI auto-fix
- **Safety**: Phase 4 (US2, boundary checks) and Phase 5 (US3, undo) — critical safety features
- **Visibility**: Phase 6 (US4, profile gating) + Phase 7 (US5, GUI) + Phase 8 (US6, CLI summary) — user-facing polish
- **Delivery**: Incremental — each phase is a testable increment that can be validated independently
