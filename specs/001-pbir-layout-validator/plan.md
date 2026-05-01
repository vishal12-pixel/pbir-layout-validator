# Implementation Plan: PBIR Layout Validator & Fixer

**Branch**: `001-pbir-layout-validator` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-pbir-layout-validator/spec.md`

## Summary

A standalone Python CLI that helps Power BI report developers maintain consistent vertical
spacing between visuals across all pages of a PBIR-format report. Three modes — `learn`,
`validate`, `fix` — derive spacing rules from a reference page, check every page against
those rules, and auto-correct violations by shifting visual `Y` coordinates while preserving
all other `visual.json` content.

**Technical approach**: Single Python package (`pbir_validator/`) with one module per
concern (reader, analyzer, validator, fixer, learner, conf, writer, ui). Standard library
only at runtime; ANSI escape codes for color; atomic write-then-rename for safe mutations;
lazy per-page iteration to satisfy the 50-page <5 s performance bar. Distributed as a
single-file Windows `.exe` via PyInstaller (build-time only).

## Technical Context

**Language/Version**: Python 3.11+ (per constitution; uses `match`, `pathlib`, dataclasses, type hints)
**Primary Dependencies**: None at runtime — Python standard library only (`argparse`, `json`, `pathlib`, `os`, `sys`, `dataclasses`, `enum`, `typing`, `tempfile`, `shutil`)
**Storage**: Filesystem only — reads/writes PBIR `.Report` folders and a Markdown rules file (`conf.md`)
**Testing**: `pytest` (dev dependency); fixtures under `tests/fixtures/sample-report/`
**Target Platform**: Windows (primary, via `.exe`), macOS, Linux (developer machines)
**Project Type**: Single-project CLI / desktop tool
**Performance Goals**: 50-page validate <5 s; cold start <200 ms; 40-page learn <10 s; 40-page validate <15 s
**Constraints**: Zero runtime third-party deps; lazy per-file JSON parsing (no full-report load); atomic file writes; preserve all unrelated JSON fields and key order
**Scale/Scope**: Reports up to ~100 pages, ~50 visuals/page; ~8 source modules; ~6 test modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|---|---|---|
| **I. Code Quality (Pythonic & Minimal)** | PASS | Stdlib-only runtime; one module per concern; no class hierarchies — frozen dataclasses + module-level functions; no plugin abstractions. |
| **II. Testing Standards (NON-NEGOTIABLE)** | PASS | Pytest unit tests per module, integration tests via CLI invocation against `tests/fixtures/sample-report/`, ≥80% coverage on `analyzer.py`, `validator.py`, `fixer.py`, `reader.py`, `conf.py`. Regression tests required for bug fixes. |
| **III. UX Consistency** | PASS | ANSI color with TTY/`NO_COLOR` auto-disable; flags `learn`/`validate`/`fix` (mutually exclusive sub-commands); errors include file path; `--dry-run` supported by `fix`; `fix` requires explicit `--apply` (or interactive y/N) before writing. |
| **IV. Performance** | PASS | Lazy generator-based page/visual iteration (`reader.iter_pages()`); JSON parsed per file on demand; entry point defers heavy imports behind sub-command dispatch in `cli.py`; benchmark fixture in `tests/fixtures/` with a documented `pytest -m benchmark` invocation. |

**Result**: No violations. No entries required in Complexity Tracking.

**Post-design re-check** (after Phase 1): No new violations introduced. Data model uses
plain frozen dataclasses; contracts are filesystem layouts and CLI signatures, not network
APIs. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-pbir-layout-validator/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli.md           # CLI command contracts (flags, exit codes, output)
│   ├── conf-format.md   # conf.md file format contract
│   └── pbir-paths.md    # PBIR JSON paths the tool reads/writes
├── checklists/
│   └── requirements.md  # (existing)
└── tasks.md             # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
pbib validator tool/
├── pbir_validator/                  # Main package (stdlib only)
│   ├── __init__.py                  # Version constant; no heavy imports
│   ├── __main__.py                  # `python -m pbir_validator` → cli.main()
│   ├── cli.py                       # argparse setup, sub-command dispatch
│   ├── models.py                    # Frozen dataclasses: Visual, Page, Report, GapRule, Violation, Row, Shift
│   ├── reader.py                    # Lazy load PBIR folder → iter_pages() / iter_visuals()
│   ├── writer.py                    # Atomic write of modified visual.json (preserve fields & key order)
│   ├── analyzer.py                  # Row grouping (±2px tolerance), gap computation, type-label resolution
│   ├── validator.py                 # Validate mode: compare gaps to rules, build Violation list
│   ├── fixer.py                     # Fix mode: plan & apply Y-coordinate shifts (with dry-run)
│   ├── learner.py                   # Learn mode: page picker → conf.md generator
│   ├── conf.py                      # Parse/write conf.md (human-readable rule file)
│   └── ui.py                        # ANSI color, headers, tables, prompts; auto-disable when not TTY
├── tests/
│   ├── conftest.py                  # Shared fixtures (sample-report path, tmp report copies)
│   ├── fixtures/
│   │   ├── sample-report/           # Mini PBIR (3 pages, mixed visuals, one deliberately broken)
│   │   └── benchmark-report/        # 50-page synthetic PBIR for perf budget check
│   ├── test_reader.py
│   ├── test_analyzer.py
│   ├── test_validator.py
│   ├── test_fixer.py
│   ├── test_learner.py
│   ├── test_conf.py
│   ├── test_writer.py
│   ├── test_ui.py
│   └── test_cli_integration.py      # End-to-end CLI invocations
├── pyproject.toml                   # Package metadata, console script, pytest & coverage config
├── README.md                        # Install, usage, build .exe, troubleshooting
├── .github/workflows/
│   ├── test.yml                     # pytest + coverage on push/PR (Windows + Linux matrix)
│   └── release.yml                  # PyInstaller build on tagged release; upload .exe to GitHub Releases
└── .gitignore                       # __pycache__, *.egg-info, build/, dist/, .pytest_cache, .coverage
```

**Structure Decision**: Single-project CLI (Option 1). One Python package
`pbir_validator/` with module-per-concern layout, one `tests/` tree mirroring it, plus
`.github/workflows/` for CI. No web/mobile/multi-app split is justified — this is a
focused, file-system-bound tool. The chosen split (reader/analyzer/validator/fixer/learner/
conf/writer/ui/cli) directly satisfies Principle I (single responsibility per function and
per module) and lets each test module target one concern.

## Complexity Tracking

> No constitutional violations. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | — | — |
