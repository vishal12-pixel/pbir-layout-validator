# Implementation Plan: Tkinter Desktop GUI for pbir_validator

**Branch**: `002-tkinter-gui` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-tkinter-gui/spec.md`

## Summary

Add an opt-in desktop GUI on top of the existing `pbir_validator` CLI. The GUI is launched via a new console script `pbir_validator-gui` (registered in `pyproject.toml`) that opens a single `Tk` window. The window has a report-picker (Browse `.pbip` / Browse `.Report`), three primary action buttons (Learn, Validate, Fix), and a `ttk.Notebook` with four tabs (Gap Violations, Row Misalignments, Horizontal Spacing, Fix Plan). Long-running operations run on a background `threading.Thread` that pushes results into a `queue.Queue` drained by the Tk main loop via `root.after(0, ...)`. Fix is dry-run-first with per-`Shift` checkboxes; Apply auto-reruns Validate. Implementation reuses every existing analyzer/validator/fixer/learner/reader function — the GUI is a thin presentation layer added under a new `pbir_validator/gui/` sub-package and introduces zero new third-party runtime dependencies.

## Technical Context

**Language/Version**: Python 3.11+ (matches existing project; constitution requirement)
**Primary Dependencies**: Standard library only — `tkinter`, `tkinter.ttk`, `tkinter.filedialog`, `tkinter.messagebox`, `threading`, `queue`, `csv`, `json`, `os`, `subprocess`, `pathlib`. Reuses existing internal modules: `pbir_validator.reader`, `analyzer`, `validator`, `learner`, `fixer`, `conf`, `models`, `errors`.
**Storage**: Filesystem only — reads `.pbip` / `.Report` folders; writes `conf.md` (Learn) and visual `position.json`/equivalent shifts (Fix); writes user-chosen `.csv` / `.json` export files. No database.
**Testing**: `pytest` + `pytest-cov` (existing dev dependencies). GUI tests use `tkinter` with `Tk().withdraw()` headless-style instantiation; controller/worker/export logic is tested without rendering. Existing 120 tests must continue to pass.
**Target Platform**: Windows 10/11 (primary; pip generates `pbir_validator-gui.exe` shim), macOS 12+, Linux with X11/Wayland. Headless environments (no `DISPLAY`) exit with a friendly message per FR-025.
**Project Type**: Desktop application layered on an existing CLI library (single repo, single package).
**Performance Goals**: Validate a 50-page report and render results in ≤5 s wall-clock (matches SC-005 and constitution Principle IV). UI must remain responsive (no "Not Responding" overlay) for the entire run (SC-006). Cold launch of `pbir_validator-gui` to first-paint MUST stay under 500 ms on a developer laptop (relaxed from CLI's 200 ms because Tk import is non-trivial; still well within interactive feel).
**Constraints**: Stdlib-only at runtime (constitution Principle I, FR-021); UI thread MUST never block on I/O (FR-023); GUI MUST NOT reimplement parsing/validation/fix logic (FR-006); CLI behavior MUST be byte-identical post-change (FR-022, SC-008).
**Scale/Scope**: Same input scale as 001 — up to ~50 pages, ~2k visuals per report. Single user, single window, no multi-document UI.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality (Pythonic & Minimal)** | PASS | `tkinter` is stdlib — no new runtime dependency. New GUI code lives in a dedicated `pbir_validator/gui/` sub-package with single-responsibility modules (`app.py`, `widgets.py`, `workers.py`, `controllers.py`, `export.py`). No abstractions speculatively added; no class hierarchies beyond what Tk itself requires. |
| **II. Testing Standards (NON-NEGOTIABLE)** | PASS | Controllers, workers, and export functions are pure Python and unit-testable without a display. Each will be covered to ≥80% line coverage. View-rendering code (`app.py`, `widgets.py`) is instantiated under a `Tk().withdraw()` fixture for smoke tests; complex Tk event handling is kept thin to minimize untestable surface. Existing 120 tests remain green (no changes to core modules). |
| **III. User Experience Consistency** | PASS | The CLI's color/flag conventions don't apply to a GUI surface, but the *spirit* — predictable layout, dry-run-first mutation, error messages that include the offending file path — is honored: FR-007 (yes/no prompt before Learn), FR-015 (Fix is always dry-run first), FR-024 (errors shown as readable in-window messages), FR-019 (auto-revalidate after Apply mirrors `--apply` semantics). The CLI itself is unchanged. |
| **IV. Performance Requirements** | PASS | Long-running ops run on `threading.Thread` so the Tk main loop stays at 60 fps regardless of report size (FR-023, SC-006). Lazy iteration in `analyzer`/`validator` is preserved — the GUI consumes generators the same way the CLI does. The 5 s/50-page bar from the constitution is restated in SC-005 for the GUI. Cold-launch budget noted in Technical Context. |

**Gate result**: **PASS**. No violations; Complexity Tracking section is empty.

**Re-check after Phase 1 design**: **PASS** (see [Post-Design Re-check](#post-design-re-check) below).

## Project Structure

### Documentation (this feature)

```text
specs/002-tkinter-gui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (delta over 001)
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli.md           # New `pbir_validator-gui` entry point
│   └── gui-flows.md     # Learn / Validate / Fix state machines
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
pbir_validator/
├── __init__.py          # unchanged
├── __main__.py          # unchanged (CLI entry)
├── cli.py               # unchanged
├── models.py            # unchanged
├── reader.py            # unchanged
├── analyzer.py          # unchanged
├── validator.py         # unchanged
├── fixer.py             # unchanged
├── learner.py           # unchanged
├── conf.py              # unchanged
├── ui.py                # unchanged (CLI ANSI helpers)
├── writer.py            # unchanged
├── errors.py            # unchanged
└── gui/                 # NEW sub-package
    ├── __init__.py
    ├── app.py           # main window, Tk() bootstrap, headless detection, entry point `main()`
    ├── widgets.py       # ttk.Treeview-based ResultTable; ShiftChecklist
    ├── workers.py       # background-thread + queue plumbing; root.after() drain
    ├── controllers.py   # LearnController, ValidateController, FixController (pure logic, testable)
    └── export.py        # CSV / JSON exporters for ResultTable rows

tests/
├── (existing 120 tests — unchanged)
└── gui/                 # NEW
    ├── __init__.py
    ├── test_workers.py        # queue/thread plumbing
    ├── test_controllers.py    # learn/validate/fix orchestration without Tk
    ├── test_export.py         # CSV/JSON round-trip
    └── test_app_smoke.py      # Tk().withdraw() headless smoke (skipped if no display)

pyproject.toml           # ADD: [project.scripts] pbir_validator-gui = "pbir_validator.gui.app:main"
```

**Structure Decision**: Single-project layout (the existing one). The GUI is added as a new sub-package `pbir_validator/gui/` rather than a sibling top-level package, so it inherits the project's existing import paths, packaging metadata, and test discovery rules. CLI modules (`cli.py`, `__main__.py`) are not modified beyond `pyproject.toml` adding the new entry point — a strict guarantee against accidental CLI regression (FR-022, SC-008).

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | _(none)_ | _(none)_ |

## Post-Design Re-check

After producing Phase 0 ([research.md](research.md)) and Phase 1 ([data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)):

- **Stdlib-only preserved**: All Phase 0 decisions (Tkinter, threading+queue, `os.startfile`/`xdg-open`/`open` via `subprocess`, `csv` module) use stdlib exclusively. ✅
- **No new domain entities**: [data-model.md](data-model.md) introduces only GUI-local view-state types (`ShiftCheckboxRow`, `ResultTableModel`) wrapping the existing 001 entities. ✅
- **Tests stay testable**: Controllers, workers, and exporters in [contracts/gui-flows.md](contracts/gui-flows.md) are pure-Python and don't require a display. ✅
- **CLI unchanged**: Only `pyproject.toml` gains a new `[project.scripts]` line; no edits to `cli.py`, `__main__.py`, or any core module. ✅

**Gate result (post-design)**: **PASS**. Zero `NEEDS CLARIFICATION` markers remain.

## Phase Status

| Phase | Output | Status |
|-------|--------|--------|
| 0 — Research | [research.md](research.md) | ✅ Complete |
| 1 — Data Model | [data-model.md](data-model.md) | ✅ Complete |
| 1 — Contracts | [contracts/cli.md](contracts/cli.md), [contracts/gui-flows.md](contracts/gui-flows.md) | ✅ Complete |
| 1 — Quickstart | [quickstart.md](quickstart.md) | ✅ Complete |
| 1 — Agent context | `.github/copilot-instructions.md` updated | ✅ Complete |
| 2 — Tasks | `tasks.md` | ⏭️ Deferred to `/speckit.tasks` |
