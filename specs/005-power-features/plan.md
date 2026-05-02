# Implementation Plan: GUI Power Features Bundle

**Branch**: `005-power-features` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/005-power-features/spec.md`

## Summary

Bundle seven Tk-only quality-of-life upgrades onto the existing pbir_validator
desktop GUI: (1) double-click row → open report in Power BI Desktop, (2)
Export-all-tabs ZIP-of-CSVs, (3) Watch-mode auto-revalidate via `Tk.after()`
polling, (4) severity letter-grade A–F in the status bar, (5) right-side
collapsible drill-down panel via `ttk.PanedWindow`, (6) rule-profile combobox
shipping `strict.md` / `standard.md` / `relaxed.md` as package data, and (7)
Undo-last-fix backed by a `<report_root>/.pbir_validator_undo/last_fix.json`
backup written by `fixer.apply_plan`. All work is stdlib-only, all new
modules require failing tests first, and CLI behavior must remain
byte-identical to the pre-feature baseline.

## Technical Context

**Language/Version**: Python 3.14.3 (standard library only at runtime per
Constitution Principle I).
**Primary Dependencies**: stdlib `tkinter` + `tkinter.ttk` (existing UI),
new stdlib imports allowed: `zipfile` (export), `importlib.resources`
(profile loading), `Tk.after()` for the watch-mode poller (preferred over
`threading` for Tk thread-safety), `csv`, `json`, `datetime`.
**Storage**: Three persisted on-disk artifacts —
(a) `<user_config>/pbir_validator/recents.json` gains `side_panel_visible`
(bool) and `profile` (string) keys; (b) `<report_root>/.pbir_validator_undo/last_fix.json`
written by Apply, deleted by Undo; (c) packaged read-only data files
`pbir_validator/profiles/{strict,standard,relaxed}.md`.
**Testing**: `pytest` with `pytest-cov` (dev-only). Project total coverage
≥80% (Constitution Principle II); ≥90% on each new module
(`undo.py`, `profiles.py`, `watch.py`, `grade.py`, `panel.py`).
**Target Platform**: Windows / macOS / Linux desktop (GUI). Module must
remain importable on a headless host (FR-073) — `Tk()` constructed only
inside `App.__init__`.
**Project Type**: Desktop CLI + GUI app, single Python package.
**Performance Goals**: Watch poll cycle = 2 s; Validate runs within 3 s of
mtime change (SC-004). ZIP export ≤2 s for 1,000-row aggregate (SC-005).
Profile switch re-runs Validate ≤1 s on a typical fixture (SC-008). Cold
CLI start ≤200 ms unchanged (Constitution Principle IV).
**Constraints**: No third-party runtime dependencies. CLI stdout/stderr/
exit code MUST be byte-identical to pre-feature baseline (FR-070, SC-007).
All 205 existing tests stay green (FR-075, SC-002). `Tk.after()` poll
reschedules itself only while watch toggle is ON; OFF toggle stops within
2 s. Headless test hosts must not crash on import.
**Scale/Scope**: One desktop binary. Five new modules
(`pbir_validator/gui/{undo,profiles,watch,grade,panel}.py`) plus three
packaged profile markdown files. Touches `app.py`, `controllers.py`,
`recents.py`, `widgets.py`, `fixer.py`, `writer.py`. Eight user stories,
~75 functional requirements.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Verdict | Evidence |
|-----------|---------|----------|
| I. Code Quality (Pythonic & Stdlib-only) | **PASS** | Every new import (`zipfile`, `importlib.resources`, `Tk.after`, `csv`, `json`, `datetime`) ships in CPython 3.14 stdlib. `pyproject.toml` `dependencies = []` stays empty. Functions stay single-purpose: `grade.compute()` is pure; `undo.record_pre_fix` and `undo.restore_last_fix` are two narrow helpers; `panel.extract_visual_context` and `panel.find_visual_for_row` are Tk-free pure data. Any function risking >40 lines is decomposed before merge. |
| II. Testing Standards (NON-NEGOTIABLE) | **PASS w/ TDD note** | All five new modules ship behind failing tests **first** (RED) → implementation (GREEN) → refactor. Per-module coverage gate: ≥90% on `undo.py`, `profiles.py`, `watch.py`, `grade.py`, `panel.py`. Project gate: ≥80% (existing). `app.py` and `widgets.py` remain `omit`'d in `pyproject.toml [tool.coverage.run]` because they require a live display; logic is forced into the new pure-data modules to keep the gate meaningful. Each new bug fix lands with a regression test (Principle II). |
| III. UX Consistency | **PASS** | New surfaces are GUI-only and obey CLI parity rules: every capability either reuses an existing CLI primitive (`controllers.validate`, `fixer.apply_plan`, `writer.write_visual_json`) or is presentation-only (grade label, side panel, ZIP export — ZIP exposes the same per-tab CSV bytes the CLI already produces). FR-070 hard-pins CLI byte-equivalence; CI diff against the 004 baseline. Error paths (open-in-PBI, ZIP write, Undo restore) reuse the existing `widgets.show_error` / `messagebox` helpers and always include the offending file path (Principle III). |
| IV. Performance Requirements | **PASS** | Watch poll = single `os.stat` per watched file every 2 s; on a 50-page report the file count stays well under 500 → poll cycle <50 ms wall time, leaving the 2 s budget intact. ZIP export streams existing per-tab CSV bytes into `zipfile.ZipFile` once each (no second-pass aggregation) → meets SC-005. Cold start unchanged: GUI imports remain lazy; profiles are loaded only when the combobox is first opened. Validation budget (50-page report ≤5 s) is unaffected because no new validation logic is added. |

**No violations** — Complexity Tracking section stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-power-features/
├── plan.md                       # This file (/speckit.plan command output)
├── research.md                   # Phase 0 output
├── data-model.md                 # Phase 1 output (entity schemas)
├── quickstart.md                 # Phase 1 output (manual-test recipe)
├── contracts/
│   ├── controller-api.md         # New & changed function signatures
│   ├── undo-record-schema.json   # last_fix.json JSON Schema
│   └── profile-schema.md         # profile .md grammar (extends 001-* conf)
├── checklists/                   # (existing)
├── spec.md                       # (existing — input)
└── tasks.md                      # Phase 2 output (NOT created here)
```

### Source Code (repository root)

```text
pbir_validator/
├── fixer.py                       # MODIFY: apply_plan() writes undo backup before mutating
├── writer.py                      # UNCHANGED at signature level; reused by undo.restore_last_fix
├── gui/
│   ├── app.py                     # MODIFY: toolbar additions (Watch toggle, Export-ZIP, profile combobox, Undo, Show/Hide panel), PanedWindow wiring, double-click binding, grade-label widget
│   ├── controllers.py             # MODIFY: validate() accepts an optional in-memory rules object so the profile dropdown overrides conf.md without touching disk; add export_all_zip(), open_in_power_bi() reuse for double-click handler
│   ├── export.py                  # MODIFY: add `_table_to_csv_bytes(headers, rows)` helper used by both per-tab CSV export and the new `controllers.export_all_zip()`; pre-existing per-tab CSV path stays unchanged
│   ├── recents.py                 # MODIFY: load()/record() round-trip new keys side_panel_visible, profile (defaults True / "Standard")
│   ├── widgets.py                 # MODIFY: add Tk-bound helpers if needed (drill-down Text widget factory) — keep logic delegated to gui/panel.py
│   ├── undo.py                    # NEW: record_pre_fix(report_root, plan), restore_last_fix(report_root) → (ok, msg, modified_paths)
│   ├── profiles.py                # NEW: list_profiles() → dict[str, Path]; load_profile(name) → rules dict; integrates importlib.resources
│   ├── watch.py                   # NEW: WatchState dataclass + snapshot_mtimes(root) → dict[Path, float]; pure logic, Tk.after() lives in app.py
│   ├── grade.py                   # NEW: compute(counts) → (letter, score); color_for(letter) → str
│   └── panel.py                   # NEW: extract_visual_context(visual) → dict; find_visual_for_row(rows, idx, columns, visuals_by_id) → list[Visual]
└── profiles/                      # NEW package-data dir (shipped as resources)
    ├── __init__.py                # Empty marker so importlib.resources can locate the dir
    ├── strict.md
    ├── standard.md
    └── relaxed.md

tests/
├── test_undo_record_and_restore.py          # NEW — RED first
├── test_profiles_loading.py                 # NEW — RED first
├── test_watch_snapshot.py                   # NEW — RED first
├── test_grade_compute.py                    # NEW — RED first
├── test_panel_extract_context.py            # NEW — RED first
├── test_controllers_validate_rules_override.py  # NEW — verifies in-memory rules path
├── test_controllers_export_zip.py           # NEW — covers FR-010 … FR-016
├── test_recents_new_keys.py                 # NEW — covers FR-072
├── test_fixer_writes_undo_backup.py         # NEW — covers FR-060
├── test_app_grade_label.py                  # NEW (headless-safe; constructs widgets only when DISPLAY available)
└── (all 205 existing tests stay green)

pyproject.toml                          # MODIFY: ship pbir_validator/profiles/*.md as package data
.gitignore                              # MODIFY: add .pbir_validator_undo/ (FR-066)
```

**Structure Decision**: Single-package layout retained from feature 004.
Tk widgets stay in `app.py` so the existing `[tool.coverage.run] omit` rule
keeps working; every line of new logic lands in the five Tk-free modules
(`undo`, `profiles`, `watch`, `grade`, `panel`) where the ≥90% gate bites.

## Complexity Tracking

> *No constitution violations — table left empty intentionally.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | *(n/a)*    | *(n/a)*                              |
