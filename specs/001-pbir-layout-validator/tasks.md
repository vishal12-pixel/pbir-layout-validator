# Tasks: PBIR Layout Validator & Fixer

**Input**: Design documents from `/specs/001-pbir-layout-validator/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (cli.md, conf-format.md, pbir-paths.md), quickstart.md

**Tests**: Included — Constitution Principle II (Testing Standards) is NON-NEGOTIABLE for this project. Pytest unit + integration tests are required, with ≥80% coverage gate on `analyzer.py`, `validator.py`, `fixer.py`, `reader.py`, `conf.py`.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps task to a user story (US1, US2, US3, US4)
- File paths are absolute within the repo root `pbib validator tool/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, tooling, and packaging metadata.

- [x] T001 Create top-level project structure: `pbir_validator/`, `tests/`, `tests/fixtures/`, `.github/workflows/` per [plan.md](plan.md) "Source Code (repository root)"
- [x] T002 [P] Create [pyproject.toml](pyproject.toml) with package metadata, `requires-python = ">=3.11"`, console script `pbir_validator = "pbir_validator.cli:main"`, `[project.optional-dependencies] dev = ["pytest", "pytest-cov"]`, and pytest config including `--cov=pbir_validator --cov-fail-under=80` and a `benchmark` marker
- [x] T003 [P] Create [.gitignore](.gitignore) excluding `__pycache__/`, `*.egg-info/`, `build/`, `dist/`, `.pytest_cache/`, `.coverage`
- [x] T004 [P] Create empty package init files: [pbir_validator/__init__.py](pbir_validator/__init__.py) (with `__version__` constant only, no heavy imports) and [pbir_validator/__main__.py](pbir_validator/__main__.py) that calls `from .cli import main; raise SystemExit(main())`
- [x] T005 [P] Create [README.md](README.md) skeleton with sections: Overview, Install, Usage (learn/validate/fix), Build Windows .exe, Troubleshooting (placeholder content; final content filled in Polish phase)
- [x] T006 [P] Create [tests/__init__.py](tests/__init__.py) and empty [tests/conftest.py](tests/conftest.py) placeholder

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models, reader, writer, and UI primitives that every user story depends on. **No US work may begin until this phase is complete.**

- [x] T007 [P] Implement frozen dataclasses in [pbir_validator/models.py](pbir_validator/models.py): `Report`, `Page`, `Visual`, `Row`, `GapRule`, `Violation`, `UnknownPair`, `Shift` per [data-model.md](data-model.md). Include `ROW_TOLERANCE_PX = 2` constant.
- [x] T008 [P] Implement ANSI color + UI primitives in [pbir_validator/ui.py](pbir_validator/ui.py): constants (`RESET`, `RED`, `GREEN`, `YELLOW`, `CYAN`, `BOLD`), `colored(text, code)`, `enable_color()` (honors `NO_COLOR`, checks `sys.stdout.isatty()`, calls `SetConsoleMode` on Windows), `header()`, `warn()`, `error()`, `success()`, `prompt_yes_no()`, `print_table(rows, headers)` per [research.md](research.md) §3
- [x] T009 Implement PBIR reader in [pbir_validator/reader.py](pbir_validator/reader.py): `load_report(path) -> Report` (raises `NotAPbirError` if `definition/pages/` missing), `iter_pages(report) -> Iterator[Page]` (lazy generator), `iter_visuals(page) -> Iterator[Visual]` (lazy generator, skips malformed JSON with UI warning), `parse_visual(path) -> Visual` (validates `position.x/y/width/height` numeric, defaults missing `visualType` to `"unknown"` with warning, detects indent and stores raw dict). Depends on T007, T008. Reads only paths defined in [contracts/pbir-paths.md](contracts/pbir-paths.md).
- [x] T010 Implement atomic JSON writer in [pbir_validator/writer.py](pbir_validator/writer.py): `write_visual_json(visual, new_y) -> None` mutates only `position.y` in `visual.raw`, serializes with detected indent + trailing newline, writes via `tempfile.NamedTemporaryFile(dir=parent, delete=False)` + `fsync` + `os.replace`. Preserves all other keys and order. Depends on T007.
- [x] T011 Implement custom exceptions in [pbir_validator/errors.py](pbir_validator/errors.py): `NotAPbirError`, `ConfParseError`, `WriteError`. Used by reader, conf, writer, fixer.
- [x] T012 [P] Build sample PBIR fixture at [tests/fixtures/sample-report/](tests/fixtures/sample-report/) — 3 pages: (a) "good" reference page with mixed visual types and consistent gaps, (b) page with one fixable gap violation, (c) page with one unfixable (page-boundary) violation; include one mixed-type row and one grouped pair (`parentGroupName`). Per [research.md](research.md) §17.
- [x] T013 [P] Tests: [tests/test_models.py](tests/test_models.py) — frozen dataclass immutability, equality semantics, `GapRule` hashing on `(from_type, to_type)` only
- [x] T014 [P] Tests: [tests/test_reader.py](tests/test_reader.py) — `load_report` raises on non-PBIR folder; `iter_pages` lazy; `iter_visuals` skips malformed visual.json with warning; missing `visualType` → `"unknown"`; correct `position` parsing; uses `tests/fixtures/sample-report/`
- [x] T015 [P] Tests: [tests/test_writer.py](tests/test_writer.py) — round-trip preserves unrelated keys, key order, indent, trailing newline; only `position.y` changes; interrupted write leaves no partial file (simulate via mock); cross-drive replace not attempted
- [x] T016 [P] Tests: [tests/test_ui.py](tests/test_ui.py) — `colored` is no-op when `NO_COLOR` set; no-op when not TTY; `print_table` formats columns

**Checkpoint**: Foundation ready — all user story phases may now begin in parallel.

---

## Phase 3: User Story 1 — Learn spacing rules from a reference page (Priority: P1) 🎯 MVP

**Goal**: A developer points the tool at a `.Report` folder, picks one reference page from a numbered list, and gets a human-readable `conf.md` containing one rule per adjacent row pair (`<from_type> -> <to_type>: <gap>px`).

**Independent Test**: Run `python -m pbir_validator learn --report tests/fixtures/sample-report` and select the "good" page. Assert `conf.md` exists at the report root, parses cleanly, and contains the expected (from-type, to-type, gap) rules with mixed-type warning emitted to stderr for the mixed row.

### Tests for User Story 1

- [x] T017 [P] [US1] [tests/test_analyzer.py](tests/test_analyzer.py) — `group_into_rows`: ±2 px tolerance bucketing; rows sorted by `y_min`; `representative_type` = most-frequent (lex tie-break); `is_mixed` flag; `compute_gaps`: `next_row.y_min - current_row.bottom`; mixed-type row warning emitted exactly once per occurrence
- [x] T018 [P] [US1] [tests/test_conf.py](tests/test_conf.py) — `parse_conf`: valid file → `dict[(from,to), GapRule]`; comments (`#`) ignored; whitespace around `->` and `:` permitted; malformed line raises `ConfParseError` with line number; per [contracts/conf-format.md](contracts/conf-format.md). `write_conf` round-trips through `parse_conf`
- [x] T019 [P] [US1] [tests/test_learner.py](tests/test_learner.py) — `learn(report, page_id, out_path)`: produces expected rules from sample-report good page; conflicting gaps for same pair → most-frequent wins, ties → smallest, warning emitted listing all observed gaps; existing `conf.md` overwritten only after confirmation/`--force`

### Implementation for User Story 1

- [x] T020 [P] [US1] Implement [pbir_validator/analyzer.py](pbir_validator/analyzer.py): `group_into_rows(visuals: Iterable[Visual]) -> list[Row]` (greedy bucket, ±2 px), `compute_gaps(rows) -> list[tuple[Row, Row, float]]`, `pick_representative_type(visuals) -> tuple[str, bool]` (most-frequent, lex tie-break, `is_mixed` flag, single warning per mixed row). Depends on T007.
- [x] T021 [P] [US1] Implement [pbir_validator/conf.py](pbir_validator/conf.py): `parse_conf(path) -> dict[tuple[str,str], GapRule]` (skip blank/comment lines, raise `ConfParseError` with line context), `write_conf(rules, path, header_lines=None)` (deterministic ordering: sort by `(from_type, to_type)`). Per [contracts/conf-format.md](contracts/conf-format.md). Depends on T007, T011.
- [x] T022 [US1] Implement [pbir_validator/learner.py](pbir_validator/learner.py): `list_pages(report) -> list[Page]`, `prompt_page_selection(pages) -> Page` (numbered list, validate input), `learn(report, page, out_path, force=False) -> Path` (group rows, compute gaps, resolve conflicts via most-frequent + smallest tie-break, emit warning per conflict, call `conf.write_conf`). Depends on T009, T020, T021.
- [x] T023 [US1] Wire `learn` sub-command into [pbir_validator/cli.py](pbir_validator/cli.py): argparse subparser with `--report`, `--page` (optional, skips prompt), `--out` (defaults to `<report>/conf.md`), `--force` (overwrite without prompt), `--no-color`. Exit codes per [contracts/cli.md](contracts/cli.md). Depends on T022.
- [x] T024 [US1] [tests/test_cli_learn.py](tests/test_cli_learn.py) — end-to-end `subprocess.run([sys.executable, "-m", "pbir_validator", "learn", ...])` against `tmp_path` copy of sample-report, assert exit 0, assert `conf.md` written and parseable, assert non-interactive `--page` flow works

**Checkpoint**: US1 fully functional — developer can produce a `conf.md` from any reference page.

---

## Phase 4: User Story 2 — Validate all pages against learned rules (Priority: P1)

**Goal**: A single command scans every page, computes gaps, compares to rules, and prints a tabular block of every violation. Exit non-zero if any violations found. Read-only.

**Independent Test**: With a `conf.md` produced from US1 and `tests/fixtures/sample-report/` (which has one deliberately misaligned page), run `python -m pbir_validator validate --report ...`. Assert non-zero exit, assert table shows the expected page/from-type/to-type/expected/actual/deviation row, assert "unknown pair" warnings appear in their own section, assert no file modified.

### Tests for User Story 2

- [x] T025 [P] [US2] [tests/test_validator.py](tests/test_validator.py) — `validate_report(report, rules) -> tuple[list[Violation], list[UnknownPair]]`: correct violation detection on sample-report; pages with 0/1 visual pass trivially; unknown pair → `UnknownPair`, NOT `Violation`; `unfixable_reason` left `None`

### Implementation for User Story 2

- [x] T026 [US2] Implement [pbir_validator/validator.py](pbir_validator/validator.py): `validate_report(report, rules) -> tuple[list[Violation], list[UnknownPair]]` — for each page: `iter_visuals` → `group_into_rows` → for each adjacent row pair, look up `(from_type, to_type)` in rules; mismatch → `Violation`; missing rule → `UnknownPair`. Depends on T009, T020, T021.
- [x] T027 [US2] Implement validate output rendering in [pbir_validator/ui.py](pbir_validator/ui.py): extend with `print_violations_table(violations)` (columns: page, from-type, to-type, expected px, actual px, deviation px-signed) and `print_unknown_pairs(pairs)` separate section. Depends on T008.
- [x] T028 [US2] Wire `validate` sub-command into [pbir_validator/cli.py](pbir_validator/cli.py): `--report` (required), `--conf` (optional, defaults to `<report>/conf.md`), `--no-color`. Exit codes per [contracts/cli.md](contracts/cli.md): 0 = clean, 1 = violations, 5 = config problem (missing/unparseable conf.md or non-PBIR folder). Read-only — assert no file mutation occurs. Depends on T026, T027.
- [x] T029 [US2] [tests/test_cli_validate.py](tests/test_cli_validate.py) — end-to-end: clean report → exit 0 + success message; sample-report → exit 1 + table; missing conf.md → exit 5 + clear error; unknown pair → warning section, NOT counted toward exit code; verify no mtime change on any visual.json/page.json after run

**Checkpoint**: US1 + US2 both work independently. MVP-shippable.

---

## Phase 5: User Story 3 — Auto-fix gap violations (Priority: P2)

**Goal**: For each violation, plan a Y-shift on the lower row (and all rows below it on the page); shift entire group when any group member is shifted; refuse shifts that exceed page height. Support `--dry-run`. Atomic per-file writes preserving all unrelated JSON.

**Independent Test**: Against sample-report with known violations, `fix --dry-run` prints planned (page, visual_id, old_y, new_y, delta) without touching files. `fix --apply` writes shifts; re-running validate immediately reports zero violations; every other field in affected `visual.json` is preserved byte-for-byte aside from `position.y`. The unfixable-violation page is reported and skipped.

### Tests for User Story 3

- [x] T030 [P] [US3] [tests/test_fixer.py](tests/test_fixer.py) — `plan_fixes(report, violations) -> list[Shift]`: shifts lower row + all rows below by deviation; group members on same page all shifted by same delta when any member shifts; `new_y + height > page.height` → `Violation.unfixable_reason` set, no `Shift` emitted for that violation, others on same page still planned; dry-run does not call writer

### Implementation for User Story 3

- [x] T031 [US3] Implement [pbir_validator/fixer.py](pbir_validator/fixer.py): `plan_fixes(report, violations) -> tuple[list[Shift], list[Violation]]` (returns updated violations with `unfixable_reason` set where applicable; plans per-page in memory before any write per [research.md](research.md) §13; expands group membership via `parent_group_name` map), `apply_shifts(shifts) -> None` (calls `writer.write_visual_json` per shift, halts on first write error and surfaces failing path). Depends on T009, T010, T026.
- [x] T032 [US3] Implement fix-mode rendering in [pbir_validator/ui.py](pbir_validator/ui.py): `print_shift_plan(shifts)` (columns: page, visual_id, old_y, new_y, delta), `print_unfixable(violations)` separate block. Depends on T008.
- [x] T033 [US3] Wire `fix` sub-command into [pbir_validator/cli.py](pbir_validator/cli.py): `--report`, `--conf`, `--dry-run`, `--apply` (skip interactive confirmation), `--no-color`. Default behavior (no `--dry-run`, no `--apply`) prompts y/N before writing. Exit codes per [contracts/cli.md](contracts/cli.md): 0 = all fixed (or dry-run completed), 1 = some unfixable, 2 = write error mid-run, 5 = config problem. Depends on T031, T032.
- [x] T034 [US3] [tests/test_cli_fix.py](tests/test_cli_fix.py) — end-to-end: `--dry-run` modifies no files (verify mtimes); `--apply` mutates only `position.y`, preserves all other keys + order + indent (byte-compare around the changed value); re-running `validate` after `--apply` returns exit 0; unfixable violation reported and skipped while other pages still get fixed; simulated write failure leaves already-written files valid JSON

**Checkpoint**: US1 + US2 + US3 all work independently and compose end-to-end (learn → validate → fix → validate).

---

## Phase 6: User Story 4 — Use a shared `conf.md` across reports (Priority: P3)

**Goal**: `--conf` accepts any filesystem path, validates existence and parseability up-front, and applies the shared rules to validate/fix runs against any report folder.

**Independent Test**: Place a `conf.md` outside any report. Run `validate --report A.Report --conf shared/conf.md` and `validate --report B.Report --conf shared/conf.md`. Assert both runs use the shared rules. Run with a non-existent `--conf` path → exit 5 with the bad path named, before any report file is read.

### Tests for User Story 4

- [x] T035 [P] [US4] [tests/test_cli_shared_conf.py](tests/test_cli_shared_conf.py) — validate against two different report copies in `tmp_path` with `--conf` pointing at a third location; both runs apply same rules; non-existent `--conf` → exit 5 + path-named error before report walk; unparseable `--conf` → exit 5 with line-number context

### Implementation for User Story 4

- [x] T036 [US4] Harden conf-loading order in [pbir_validator/cli.py](pbir_validator/cli.py): when `--conf` is supplied, ignore any `<report>/conf.md` entirely; resolve path; validate existence and parse before doing any report I/O; raise the same `ConfParseError` → exit 5 path. Depends on T028, T033.
- [x] T037 [US4] Update [README.md](README.md) Usage section with shared-conf workflow example matching [quickstart.md](quickstart.md) §4 ("Use a shared rules file")

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance budget, packaging, CI, docs. Affects all stories.

- [x] T038 [P] Generator script [tests/_gen_benchmark.py](tests/_gen_benchmark.py) that produces a synthetic 50-page PBIR at [tests/fixtures/benchmark-report/](tests/fixtures/benchmark-report/) (committed but not auto-run)
- [x] T039 [P] [tests/test_benchmark.py](tests/test_benchmark.py) marked `@pytest.mark.benchmark` — runs `validate` against `benchmark-report`, asserts wall-clock <5 s; runs `learn` <10 s on 40-page slice; runs `validate` <15 s on 40-page slice. Per SC-001/002 and [research.md](research.md) §18.
- [x] T040 [P] Cold-start budget assertion in [tests/test_cli_integration.py](tests/test_cli_integration.py) — `python -m pbir_validator --help` cold-start <200 ms (timer around `subprocess.run`); confirms `cli.py` defers heavy imports behind sub-command dispatch (per Principle IV)
- [x] T041 [P] CI workflow [.github/workflows/test.yml](.github/workflows/test.yml) — `on: [push, pull_request]`, matrix `os: [windows-latest, ubuntu-latest]` × `python: ['3.11', '3.12']`; steps: checkout → setup-python → `pip install -e .[dev]` → `pytest --cov` → upload coverage. Per [research.md](research.md) §15.
- [x] T042 [P] CI workflow [.github/workflows/release.yml](.github/workflows/release.yml) — `on: push: tags: ['v*']`, `windows-latest` only; steps: checkout → setup-python → `pip install pyinstaller -e .` → `pyinstaller --onefile --name pbir_validator pbir_validator/__main__.py` → upload `dist\pbir_validator.exe` to GitHub Release. Per [research.md](research.md) §14.
- [x] T043 [P] Finalize [README.md](README.md) with full Install / Usage / Build .exe / Troubleshooting sections matching [quickstart.md](quickstart.md)
- [x] T044 Verify quickstart.md walkthrough end-to-end against current code: `python -m pbir_validator --help`, `learn`, `validate`, `fix --dry-run`, `fix --apply`, `pyinstaller` build all work as documented in [quickstart.md](quickstart.md)
- [x] T045 Coverage gate verification — confirm `pytest --cov` reports ≥80% on `analyzer.py`, `validator.py`, `fixer.py`, `reader.py`, `conf.py` (per Constitution Principle II); add targeted unit tests for any uncovered branches
- [x] T046 Code review pass: confirm no third-party imports anywhere under `pbir_validator/`, all dataclasses are `frozen=True`, no class hierarchies introduced, error messages always include the offending file path (per Principle I + III)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup; **BLOCKS all user stories**
- **User Stories (Phases 3–6)**: All depend on Phase 2; can proceed in parallel
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1) Learn**: Depends only on Phase 2. Independently shippable.
- **US2 (P1) Validate**: Depends on Phase 2. Functionally independent of US1 in code (consumes any `conf.md`), but practically tested using a `conf.md` produced by US1. Either order is fine.
- **US3 (P2) Fix**: Depends on Phase 2; reuses `validator.validate_report` from US2 (T026) for its violation set. If US2 is not yet built, T031 must be sequenced after T026.
- **US4 (P3) Shared conf**: Depends on US2 (T028) and US3 (T033) CLI subparsers existing.

### Within Each User Story

- Models / fixtures (Phase 2) before story logic
- Story tests written first; **must FAIL** before story implementation lands
- Pure-function modules (analyzer, conf, validator, fixer) before CLI wiring
- CLI integration tests last in each story phase

### Parallel Opportunities

- All [P] tasks in Phase 1 → run concurrently (T002, T003, T004, T005, T006)
- All [P] tasks in Phase 2 → run concurrently (T007, T008, T012, T013, T014, T015, T016 — different files)
- Once Phase 2 complete: US1, US2, US3, US4 can be staffed to four developers in parallel
- Within US1: T017, T018, T019 (tests) parallel; T020, T021 (analyzer + conf) parallel
- All [P] tasks in Phase 7 (T038–T043) parallel

---

## Parallel Example: Phase 2 Foundational

```text
# Run together (different files, no inter-deps):
Task T007: Implement frozen dataclasses in pbir_validator/models.py
Task T008: Implement ANSI UI primitives in pbir_validator/ui.py
Task T012: Build sample PBIR fixture at tests/fixtures/sample-report/
Task T013: Tests for models in tests/test_models.py
Task T016: Tests for UI in tests/test_ui.py

# Then sequence T009 (reader) after T007+T008,
# then T010 (writer) after T007,
# then T014 (reader tests) after T009+T012,
# then T015 (writer tests) after T010.
```

## Parallel Example: User Story 1

```text
# Tests first (must fail):
Task T017 [US1]: tests/test_analyzer.py
Task T018 [US1]: tests/test_conf.py
Task T019 [US1]: tests/test_learner.py

# Implementation (T020 + T021 parallel; T022 then T023 then T024 sequential):
Task T020 [US1]: pbir_validator/analyzer.py
Task T021 [US1]: pbir_validator/conf.py
```

---

## Implementation Strategy

### MVP First (US1 + US2)

Both `learn` and `validate` are P1. Recommended MVP scope is **US1 + US2**:

1. Phase 1 Setup
2. Phase 2 Foundational (CRITICAL — blocks everything)
3. Phase 3 US1 (Learn) → STOP and validate independently
4. Phase 4 US2 (Validate) → STOP and validate independently
5. Ship MVP — read-only workflow is complete and useful even without `fix`

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. + US1 → demo: `learn` produces `conf.md`
3. + US2 → demo: `validate` reports violations (MVP shippable)
4. + US3 → demo: `fix --dry-run` and `fix --apply`
5. + US4 → demo: shared team `conf.md`
6. Polish → benchmarks pass, CI green, .exe built

### Parallel Team Strategy

After Phase 2:

- Dev A: US1 (Learn)
- Dev B: US2 (Validate)
- Dev C: US3 (Fix) — can stub the violation list from a fixture until US2 lands
- Dev D: US4 (Shared conf) — small; can pair with B/C and merge after their CLI subparsers exist

---

## Notes

- [P] tasks operate on different files with no incomplete-task dependencies
- [Story] label maps each task to its user story for traceability and independent shipping
- Tests must be written and confirmed failing before the corresponding implementation
- Atomic write-then-rename is non-negotiable for every `visual.json` mutation (FR-023 / SC-004)
- Stdlib-only at runtime — PyInstaller is build-time only
- Commit after each task or logical group; the `after_tasks` git hook will offer to commit this tasks.md

## Extension Hooks

**Optional Hook**: git
Command: `/speckit.git.commit`
Description: Auto-commit after task generation

Prompt: Commit task changes?
To execute: `/speckit.git.commit`


---

## Phase 8: Post-MVP enhancements (delivered after initial release)

These tasks were not in the original generated plan. They were added based on real-world
testing of the v1 tool against production reports. All are complete.

- [x] T046 Add `dedupe_stacked_visuals` to [pbir_validator/analyzer.py](pbir_validator/analyzer.py): collapses same-type visuals stacked at the same canvas position (≥50% horizontal-bounding-box overlap and Y delta < 50% of min height). Prevents bookmark-driven alternate visuals from triggering false-positive misalignments and gap violations. Wired into `iter_visuals` consumers in validator/fixer/learner. (FR-029)
- [x] T047 Add `Misalignment` frozen dataclass to [pbir_validator/models.py](pbir_validator/models.py) and `find_row_misalignments` to [pbir_validator/analyzer.py](pbir_validator/analyzer.py): flags any visual whose Y differs from the row's modal Y by more than `DEFAULT_ALIGNMENT_TOLERANCE_PX` (0.5 px). (FR-026)
- [x] T048 Update [pbir_validator/validator.py](pbir_validator/validator.py) to surface misalignments and update [pbir_validator/fixer.py](pbir_validator/fixer.py) to pre-apply each misalignment delta to the visual before computing adjacent-row gap shifts, so row-gap fixes layer on an aligned baseline. (FR-026, FR-028)
- [x] T049 Add `HSpacingIssue` frozen dataclass to [pbir_validator/models.py](pbir_validator/models.py) and `find_row_hspacing_issues` to [pbir_validator/analyzer.py](pbir_validator/analyzer.py): for each row containing ≥3 visuals of the same `visual_type`, computes consecutive horizontal gaps (sorted by X) and flags any gap deviating from the row's modal gap by more than `DEFAULT_HSPACING_TOLERANCE_PX` (0.5 px). Detection-only in v1 (no auto-fix). (FR-027, FR-028)
- [x] T050 Update [pbir_validator/validator.py](pbir_validator/validator.py) to return a 4-tuple `(violations, unknowns, misalignments, hspacing_issues)`; add `print_misalignments_table` and `print_hspacing_table` to [pbir_validator/ui.py](pbir_validator/ui.py); update [pbir_validator/cli.py](pbir_validator/cli.py) to render the two new tables and include both new categories in the non-zero exit code summary. (FR-028)
- [x] T051 Tests: extend [tests/test_analyzer.py](tests/test_analyzer.py) with bookmark-stack dedupe cases, intra-row misalignment cases, and four horizontal-spacing cases (consistent row, off-gap detected, <3 peers ignored, mixed types ignored). Update [tests/test_validator.py](tests/test_validator.py), [tests/test_fixer.py](tests/test_fixer.py), and [tests/test_benchmark.py](tests/test_benchmark.py) for the new validator return arity. **All 120 tests pass.**
