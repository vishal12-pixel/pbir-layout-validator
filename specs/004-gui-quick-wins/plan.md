# Implementation Plan: GUI Quick Wins (Reader Hotfix + Click-to-Open + Sort + Filter + Severity + Recents)

**Branch**: `004-gui-quick-wins` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-gui-quick-wins/spec.md`

## Summary

Six quick wins layered on top of the shipped Tkinter GUI (002), plus one
correctness hotfix in the analyzer's row-grouping logic. The reader hotfix
yields a new "Duplicate Layer" classification surfaced as a 5th result
tab. The remaining five stories are pure GUI affordances: per-tab sort,
per-tab filter, severity color tags, right-click context menu (copy row /
launch `definition.pbir` via `os.startfile`), and a recents menu backed
by `%APPDATA%\pbir_validator\recents.json`. Stdlib-only at runtime; all
new logic kept testable by isolating it from Tk widgets.

## Technical Context

**Language/Version**: Python 3.14.3 (constitution floor: 3.11)
**Primary Dependencies**: stdlib only (`tkinter`, `tkinter.ttk`, `json`,
`pathlib`, `os`, `dataclasses`, `threading`, `queue`); dev-only `pytest`.
**Storage**: filesystem — `%APPDATA%\pbir_validator\recents.json` on
Windows / `~/.config/pbir_validator/recents.json` on POSIX.
**Testing**: `pytest` with coverage; existing 166-test suite (85.90%
coverage) MUST stay green. New modules (reader hotfix, recents,
severity, context-menu controller) target ≥90% coverage.
**Target Platform**: Windows desktop (primary). Code paths on POSIX must
not crash; functional parity is non-goal for this feature.
**Project Type**: Desktop application (single project, package
`pbir_validator/` with `gui/` sub-package).
**Performance Goals**:

- Filter input updates visible rows ≤100 ms for tables up to 500 rows.
- Sort completes <50 ms for 500 rows (built-in `list.sort` + tuple key).
- `os.startfile` invocation returns to event loop within 200 ms.
- Cold GUI start unchanged (no heavy imports added).

**Constraints**:

- No new third-party runtime dependencies (Principle I).
- CLI surface must remain byte-identical (FR-021).
- Reader hotfix must not introduce false positives on reports that
  validate cleanly today (FR-002 is additive, FR-003 is a new category).
- Existing 5 tabs become 6; smoke test count assertions must update.

**Scale/Scope**: ~10 GUI files touched, ~5 backend files, ~6 new test
files. Estimated ~25 tasks across 6 user stories.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Evidence |
|---|---|---|
| I. Code Quality (stdlib-only, ≤40 LOC functions, no over-engineering) | PASS | All new code uses stdlib (`os.startfile`, `tkinter`, `json`). No new abstractions; recents/severity are simple modules. |
| II. Testing Standards (≥80% coverage, regression tests) | PASS | Reader hotfix has explicit regression test (FY26 fixture); recents and severity have unit tests; GUI controller logic stays in pure-Python `controllers.py`. Coverage target ≥90% on new modules. |
| III. UX Consistency (CLI primacy, dry-run-first, file-paths in errors) | PASS | Feature is GUI-only enhancement; CLI unchanged (FR-021). Error messages on missing `definition.pbir` and corrupt recents include the path. No file mutations performed. |
| IV. Performance (50-page <5s, <200ms cold start, lazy JSON) | PASS | No heavy imports added. Filter latency budget documented (≤100 ms / 500 rows). Reader hotfix is O(n) over visuals — no asymptotic regression. |

**Gate Result**: PASS — proceed to Phase 0.

**Re-check after Phase 1 (post-design)**: PASS. Design artifacts
(data-model, contracts) confirm: no new third-party deps, no file
mutations introduced, no architectural complexity added beyond two new
small modules (`recents.py`, `severity.py`) and additive analyzer logic.

## Project Structure

### Documentation (this feature)

```text
specs/004-gui-quick-wins/
├── plan.md              # This file
├── research.md          # Phase 0 — design rationale per story
├── data-model.md        # Phase 1 — entities & schemas
├── quickstart.md        # Phase 1 — dev validation steps
├── contracts/
│   ├── recents-schema.json        # JSON schema for recents.json
│   └── controller-api.md          # New controller methods
└── tasks.md             # /speckit.tasks output (NOT created here)
```

### Source Code (repository root)

```text
pbir_validator/
├── analyzer.py            # CHANGED — row-grouping hotfix (US1)
├── models.py              # CHANGED — add DuplicateLayer dataclass (US1)
├── gui/
│   ├── app.py             # CHANGED — 6th tab, context menu, recents menu
│   ├── controllers.py     # CHANGED — DuplicateLayer rows + sort/filter state
│   ├── widgets.py         # CHANGED — filter Entry, sortable headers, tag colors
│   ├── recents.py         # NEW — RecentsStore (load/save/append/evict)
│   └── severity.py        # NEW — pure function: deviation → tag name
└── (other modules unchanged)

tests/
├── test_analyzer_duplicate_layer.py    # NEW — US1 reader hotfix
├── test_gui_controllers_sort.py        # NEW — sort state per tab
├── test_gui_controllers_filter.py      # NEW — filter substring matching
├── test_gui_recents.py                 # NEW — RecentsStore round-trip
├── test_gui_severity.py                # NEW — band classification
├── test_gui_smoke.py                   # CHANGED — 6 tabs assertion
└── fixtures/
    └── duplicate-layer-page.Report/    # NEW — synthetic 2-pivot same-y page
```

**Structure Decision**: Single-project layout (existing). No new top-level
packages. Backend hotfix lives in `analyzer.py`; GUI additions live under
`pbir_validator/gui/`. Tests mirror module names. Pure-Python helpers
(`recents.py`, `severity.py`) are kept *out* of the coverage `omit` list
so they count toward the gate; `app.py` and `widgets.py` remain omitted.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
