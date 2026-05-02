# Implementation Plan: Horizontal Spacing Auto-Fix

**Branch**: `main` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/006-hspacing-autofix/spec.md`

## Summary

Add auto-fix capability for horizontal spacing issues detected by
`find_row_hspacing_issues`. When a row of ≥3 same-type visuals has uneven
horizontal gaps, the fixer plans X-shifts to equalize all gaps to the modal
value. The implementation extends the existing `Shift` model with optional
`old_x`/`new_x`/`delta_x` fields, adds `new_x` support to
`write_visual_json`, extends the undo backup to store/restore X coordinates,
gates h-spacing fixes behind a profile `hspacing_fix` flag (enabled in
Strict only), and surfaces X-shift rows in both the CLI plan summary and the
GUI Fix Plan tab.

## Technical Context

**Language/Version**: Python 3.11+ (standard library only at runtime)
**Primary Dependencies**: stdlib only; `pytest` dev-only
**Storage**: PBIR visual JSON files on disk; undo backup at
`<report_root>/.pbir_validator_undo/last_fix.json`
**Testing**: `pytest` — unit + integration against fixture data under
`tests/fixtures/`
**Target Platform**: Windows, macOS, Linux (cross-platform via `pathlib` + `os`)
**Project Type**: CLI tool + Tk desktop GUI
**Performance Goals**: <5 s for 50-page report validation+fix
**Constraints**: Zero third-party runtime deps; atomic writes; byte-conservative JSON serialization
**Scale/Scope**: Single-user CLI/GUI; reports up to ~50 pages × ~30 visuals/page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality (Pythonic & Minimal) | PASS | No new dependencies; extends existing functions with optional params; no new abstractions beyond what the spec requires |
| II. Testing Standards (NON-NEGOTIABLE) | PASS | All new X-shift logic requires unit tests; integration test against fixture with known h-spacing deviation; ≥80% line coverage target |
| III. User Experience Consistency | PASS | CLI `fix` output extended with X-shift rows using same table format; GUI Fix Plan tab gains "shift-x" action rows; dry-run-first default preserved |
| IV. Performance Requirements | PASS | X-shift planning is O(visuals-per-row) per row — negligible; no new file I/O beyond the shifts themselves; lazy per-file parsing preserved |
| Stack & Scope | PASS | No new external deps; no network calls; pure file-system mutations |

**Pre-design gate: PASS — no violations.**

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality | PASS | `plan_hspacing_fixes()` is a single-purpose function (~50 lines). `write_visual_json` gains one optional kwarg. No new abstractions, no class hierarchies. |
| II. Testing Standards | PASS | New test files for X-shift planning, writer X-support, undo X round-trip. Fixture report with known deviations. ≥80% coverage target maintained. |
| III. User Experience | PASS | CLI gains "Action" column in shift plan (shift-y/shift-x). GUI Fix Plan tab gains X-shift rows with "shift-x" label. Dry-run default preserved. |
| IV. Performance | PASS | X-shift planning is O(peers-per-type × rows-per-page) — negligible. No new file reads beyond existing validation pass. |
| Stack & Scope | PASS | Zero new deps. File-system only. Cross-platform via pathlib/os. |

**Post-design gate: PASS — no violations.**

## Project Structure

### Documentation (this feature)

```text
specs/006-hspacing-autofix/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── shift-x-contract.md
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
pbir_validator/
├── models.py            # MODIFY: extend Shift with old_x/new_x/delta_x
├── fixer.py             # MODIFY: add plan_hspacing_fixes(), integrate into plan_fixes()
├── writer.py            # MODIFY: add optional new_x param to write_visual_json()
├── cli.py               # MODIFY: extend fix summary to show X-shifts
├── ui.py                # MODIFY: extend print_shift_plan() for X-shift rows
├── profiles/
│   ├── strict.md        # MODIFY: add hspacing_fix: true (or equivalent marker)
│   ├── standard.md      # NO CHANGE (hspacing_fix defaults to false)
│   └── relaxed.md       # NO CHANGE
└── gui/
    ├── controllers.py   # MODIFY: extend fix_plan_rows() for X-shift display
    ├── undo.py           # MODIFY: store/restore old_x in backup entries
    └── profiles.py       # MODIFY: parse hspacing_fix flag from profile files

tests/
├── test_hspacing_fix.py         # NEW: unit tests for X-shift planning
├── test_writer_x.py             # NEW: unit tests for write_visual_json with new_x
├── test_undo_x.py               # NEW: undo round-trip tests with X coordinates
└── fixtures/
    └── hspacing_report/         # NEW: fixture report with known h-spacing deviations
```

**Structure Decision**: Single-project layout (existing). All changes extend
existing modules. One new test file per concern area; one new fixture report.

## Complexity Tracking

> No constitution violations — table intentionally left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
