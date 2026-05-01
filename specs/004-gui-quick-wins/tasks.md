# Tasks: GUI Quick Wins (Reader Hotfix + Click-to-Open + Sort + Filter + Severity + Recents)

**Input**: Design documents from `/specs/004-gui-quick-wins/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)
**Tests**: REQUIRED per constitution Principle II (NON-NEGOTIABLE).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- File paths are absolute relative to repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding shared by every story.

- [X] T001 Create `pbir_validator/gui/recents.py` skeleton (empty module + module docstring) at `pbir_validator/gui/recents.py`
- [X] T002 [P] Create `pbir_validator/gui/severity.py` skeleton (empty module + module docstring) at `pbir_validator/gui/severity.py`
- [ ] T003 [P] Create test fixture directory `tests/fixtures/duplicate-layer-page.Report/` with `definition.pbir`, `pages/page-with-duplicates/page.json`, and two same-type `visual.json` files at y=322.7 and y=343.0 (both `pivotTable`, same x, different ids)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain model changes that every downstream story depends on. **MUST complete before US2–US6.**

- [X] T004 Add `DuplicateLayer` frozen dataclass to `pbir_validator/models.py` (fields per data-model.md: page, visual_type, visual_a_id, visual_a_title, visual_b_id, visual_b_title, delta_y_px)
- [X] T005 Add `duplicate_layers: list[DuplicateLayer] = field(default_factory=list)` field to `ValidateResult` in `pbir_validator/gui/controllers.py`
- [X] T006 Add `TabState` dataclass + pure helpers (`visible_rows`, `toggle_sort`, `set_filter`, `set_rows`) to `pbir_validator/gui/controllers.py` per `contracts/controller-api.md`

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 — Reader Hotfix + Duplicate Layer Tab (Priority: P1) 🎯 MVP 🐛

**Goal**: Stop silently dropping visuals; surface same-type same-y pairs in a new "Duplicate Layer" tab.

**Independent Test**: Run Validate on `tests/fixtures/duplicate-layer-page.Report/`. Both visuals appear in analyzer output; one `DuplicateLayer` row is emitted with `delta_y_px ≈ 20.3`. GUI shows new "Duplicate Layer" tab in 3rd position.

### Tests for User Story 1

- [ ] T007 [P] [US1] Write failing unit test for analyzer hotfix in `tests/test_analyzer_duplicate_layer.py` — assert `group_into_rows()` returns both visuals (not 1) when two pivotTables share y-bucket
- [X] T008 [P] [US1] Write failing unit test in `tests/test_analyzer_duplicate_layer.py` — assert one `DuplicateLayer` is emitted per same-type pair with correct `delta_y_px`
- [X] T009 [P] [US1] Write failing test in `tests/test_analyzer_duplicate_layer.py` — assert N visuals at same y emit `N choose 2` DuplicateLayer pairs
- [X] T010 [P] [US1] Write failing test in `tests/test_gui_controllers_duplicates.py` — assert `validate()` populates `ValidateResult.duplicate_layers` from analyzer output
- [X] T011 [P] [US1] Update `tests/test_gui_smoke.py` — change `test_app_constructs_with_five_tabs` to assert `notebook.index("end") == 6` and label order [Gap Violations, Overlapping Visuals, Duplicate Layer, Row Misalignments, Horizontal Spacing, Fix Plan]

### Implementation for User Story 1

- [X] T012 [US1] Modify `pbir_validator/analyzer.py` — change `group_into_rows()` row-bucket value from single visual to list of visuals; emit `DuplicateLayer` pairs for same-type same-y groups; return tuple `(rows, duplicate_layers)`
- [X] T013 [US1] Update analyzer call sites in `pbir_validator/validator.py` to destructure the new tuple return
- [X] T014 [US1] Update `pbir_validator/gui/controllers.py` `validate()` to populate `ValidateResult.duplicate_layers` and define `DUPLICATE_COLUMNS = ("page", "visual_type", "visual_a", "visual_b", "delta_y_px")` plus `duplicate_rows()` helper
- [X] T015 [US1] Add `_TAB_DUPLICATES = "Duplicate Layer"` constant + `_duplicates_table` Treeview in `pbir_validator/gui/app.py`; insert tab between Overlapping Visuals and Row Misalignments
- [X] T016 [US1] Update `_on_validate_done` in `pbir_validator/gui/app.py` to populate `_duplicates_table` and update status bar to read "Done — N gaps, N overlaps, N duplicates, N misalignments, N h-spacing issues."

**Checkpoint**: US1 fully functional; reader correctly emits all visuals; new tab visible.

---

## Phase 4: User Story 2 — Right-Click Context Menu (Priority: P1)

**Goal**: Right-click any result row → menu with "Open page in Power BI Desktop" + "Copy row".

**Independent Test**: Right-click any row on any of the 5 result tabs; menu appears; clicking "Open page" launches Power BI Desktop on `<report>/definition.pbir`; "Copy row" puts tab-separated cells on clipboard.

### Tests for User Story 2

- [X] T017 [P] [US2] Write unit tests for `open_in_power_bi(report_root)` in `tests/test_gui_context_menu.py` — assert `(True, "")` when `definition.pbir` exists (mock `os.startfile`); `(False, msg)` when missing
- [X] T018 [P] [US2] Write unit test for `row_to_clipboard_text(cells)` in `tests/test_gui_context_menu.py` — assert tab-separated output

### Implementation for User Story 2

- [X] T019 [US2] Add `open_in_power_bi(report_root: Path) -> tuple[bool, str]` and `row_to_clipboard_text(cells: tuple[str, ...]) -> str` to `pbir_validator/gui/controllers.py`
- [X] T020 [US2] Add `_build_context_menu(tree, columns)` and `_on_right_click(event)` handlers in `pbir_validator/gui/app.py`; bind `<Button-3>` on all 5 result Treeviews; wire menu items to controller helpers
- [X] T021 [US2] In `pbir_validator/gui/app.py`, gracefully degrade "Open page in Power BI Desktop" via `tk.messagebox.showinfo` when `controllers.open_in_power_bi` returns `(False, msg)`

**Checkpoint**: US2 functional independently of US3–US6.

---

## Phase 5: User Story 3 — Sortable Column Headers (Priority: P1)

**Goal**: Click any column header to sort; numeric columns sort numerically; toggle asc/desc.

**Independent Test**: Click "Deviation Px" header on Gap Violations → rows reorder ascending, header shows ▲. Click again → descending, header shows ▼. Numeric sort: `9 < 10 < 17`, not lexical.

### Tests for User Story 3

- [X] T022 [P] [US3] Write tests for `toggle_sort(state, col)` in `tests/test_gui_controllers_sort.py` — assert cycle None → (col, False) → (col, True) → (col, False); selecting different column resets to (new_col, False)
- [X] T023 [P] [US3] Write tests for `visible_rows(state)` numeric vs string sort in `tests/test_gui_controllers_sort.py` — assert numeric columns sort by float value, others by case-insensitive string
- [X] T024 [P] [US3] Write test in `tests/test_gui_controllers_sort.py` — assert sort state is preserved when `set_rows` is called (FR-013a)

### Implementation for User Story 3

- [X] T025 [US3] Implement `toggle_sort` and numeric-aware `visible_rows` sort in `pbir_validator/gui/controllers.py` (depends on T006)
- [X] T026 [US3] In `pbir_validator/gui/widgets.py` (or new helper inside `app.py`), wire each Treeview column header `command` to call `controllers.toggle_sort` then re-populate the tree; render ▲/▼ indicator on active column
- [X] T027 [US3] Initialize one `TabState` per result tab (5 tabs) in `pbir_validator/gui/app.py` constructor; declare `numeric_columns` for each tab per `data-model.md`

**Checkpoint**: US3 functional; sort state per-tab; persists across Validate runs.

---

## Phase 6: User Story 4 — Per-Tab Filter Box (Priority: P2)

**Goal**: Free-text filter Entry above each result table; live, case-insensitive substring match across all columns.

**Independent Test**: Type "card" in filter on Gap Violations → only rows mentioning "card" remain. Clear → all rows return. Sort + filter compose. Validate clears filter (FR-013).

### Tests for User Story 4

- [X] T028 [P] [US4] Write tests for `set_filter(state, text)` in `tests/test_gui_controllers_filter.py` — assert filter is lower-cased and applied; empty filter returns all rows
- [X] T029 [P] [US4] Write tests for filter+sort composition in `tests/test_gui_controllers_filter.py` — `visible_rows` after filter+sort returns sorted subset
- [X] T030 [P] [US4] Write test in `tests/test_gui_controllers_filter.py` — `set_rows` clears `filter_text` (FR-013)

### Implementation for User Story 4

- [X] T031 [US4] Implement `set_filter` + filter step in `visible_rows` in `pbir_validator/gui/controllers.py` (depends on T006)
- [X] T032 [US4] Add `ttk.Entry` filter widget above each Treeview in `pbir_validator/gui/app.py`; bind `<KeyRelease>` to call `controllers.set_filter` and re-populate tree
- [X] T033 [US4] In `_on_validate_done` in `pbir_validator/gui/app.py`, clear all 5 filter entries and call `controllers.set_rows` (which preserves sort, clears filter)

**Checkpoint**: US4 functional; filter+sort compose correctly; filter clears on each Validate.

---

## Phase 7: User Story 5 — Severity Color Tags (Priority: P2)

**Goal**: Green/yellow/red row tags on Gap Violations, Overlapping Visuals, Row Misalignments, Horizontal Spacing per thresholds in research D5.

**Independent Test**: Load report with mixed deviations; rows with `|dev| ≤ 2` are green, `2 < |dev| ≤ 10` yellow, `> 10` red. Overlap rows yellow up to 50px, red above. Duplicate Layer rows always yellow.

### Tests for User Story 5

- [X] T034 [P] [US5] Write tests for `band(value, kind="deviation")` in `tests/test_gui_severity.py` — assert thresholds 2/10 produce SEV_GREEN/SEV_YELLOW/SEV_RED for both signs
- [X] T035 [P] [US5] Write tests for `band(value, kind="overlap")` in `tests/test_gui_severity.py` — assert ≤0 green, 0<v≤50 yellow, >50 red

### Implementation for User Story 5

- [X] T036 [P] [US5] Implement `SEV_GREEN`, `SEV_YELLOW`, `SEV_RED` constants and `band(value, *, kind)` pure function in `pbir_validator/gui/severity.py`
- [X] T037 [US5] Add `_configure_tags()` method in `pbir_validator/gui/app.py` registering tag styles (bg/fg per research D5) on every result Treeview
- [X] T038 [US5] When inserting rows in `_on_validate_done` in `pbir_validator/gui/app.py`, compute severity tag via `severity.band` and pass `tags=(tag,)` to `Treeview.insert`; Duplicate Layer rows always tagged yellow

**Checkpoint**: US5 functional; severity legible across light/dark themes.

---

## Phase 8: User Story 6 — Recent Reports Menu (Priority: P3)

**Goal**: File menu shows last 5 successfully-loaded report paths, MRU-first; selecting one re-loads it; missing entries are removed with informational message.

**Independent Test**: Open report A, B, C → menu shows [C, B, A]. Open D, E, F → A evicted. Click a recent → loads it. Delete a recent's folder, click it → message + entry removed.

### Tests for User Story 6

- [X] T039 [P] [US6] Write tests for `recents_path()` in `tests/test_gui_recents.py` — assert Windows path is `%APPDATA%\pbir_validator\recents.json`; assert parent dir is created
- [X] T040 [P] [US6] Write tests for `load()` in `tests/test_gui_recents.py` — assert returns `[]` on FileNotFoundError, JSONDecodeError, KeyError; assert returns list on valid JSON
- [X] T041 [P] [US6] Write tests for `record(path)` in `tests/test_gui_recents.py` — assert dedup, MRU push-to-front, truncate to 5, JSON written matches schema

### Implementation for User Story 6

- [X] T042 [P] [US6] Implement `recents_path`, `load`, `record` in `pbir_validator/gui/recents.py` per `contracts/controller-api.md` and `contracts/recents-schema.json`
- [X] T043 [US6] Add "File → Recent reports" submenu in `pbir_validator/gui/app.py`; rebuilt on every successful load via `recents.load()`; show "(no recent reports)" disabled item when empty
- [X] T044 [US6] On successful Validate in `pbir_validator/gui/app.py`, call `recents.record(report_root)` and refresh the menu
- [X] T045 [US6] When user selects a recent menu item, attempt to load it; on `FileNotFoundError`/`OSError`, show `messagebox.showinfo` with the path and call `recents.record` for remaining valid entries (effectively removing the broken one)

**Checkpoint**: US6 functional; recents persist across launches; corrupt/missing entries handled gracefully.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T046 [P] Update `README.md` "Graphical UI (Tkinter)" section with screenshots and the 6 new tabs / sort / filter / right-click / recents
- [X] T047 [P] Update `pyproject.toml` `[tool.coverage.run] omit` list — keep `app.py` and `widgets.py` omitted; do **not** omit `recents.py` or `severity.py` (they should count toward the 80% gate)
- [X] T048 Run `pytest -v --cov=pbir_validator --cov-report=term-missing`; confirm all tests pass and coverage ≥80% (with `recents.py` and `severity.py` ≥90%)
- [ ] T049 Run quickstart validation per [quickstart.md](quickstart.md) — manually verify all 6 GUI behaviors end-to-end on a real report
- [ ] T050 Verify CLI is byte-identical: run `pbir_validator --validate <fixture>` on this branch and on `main`; diff output must be empty

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.**
- **US1 (Phase 3)**: Depends on Foundational. Required for US5/US7 to fully test severity on duplicate-layer rows but US2–US6 GUI surfaces work without it.
- **US2 (Phase 4)**: Depends on Foundational. Independent of US1 GUI changes once tab list settled.
- **US3 (Phase 5)**: Depends on Foundational + T015 (tab existence).
- **US4 (Phase 6)**: Depends on Foundational + US3 (composition).
- **US5 (Phase 7)**: Depends on Foundational + US1 (Duplicate Layer rows need tag too).
- **US6 (Phase 8)**: Depends on Foundational. Independent of all other US.
- **Polish (Phase 9)**: Depends on all desired stories complete.

### Within Each User Story

- Tests written first → assert they fail → implement → assert they pass.
- Models/dataclasses before services before widget wiring.

### Parallel Opportunities

- Setup: T002 and T003 in parallel.
- Foundational: T004, T005, T006 must be sequential (T005 imports T004; T006 sits in same file as T005).
- Within each story, all `[P]` test tasks run in parallel.
- Across stories: US2, US3, US6 implementation phases can be parallelized after Phase 2 by different developers (different files, no overlap).
- US4 and US5 implementation depend on US3 and US1 respectively, so are not fully parallel.

---

## Parallel Example: User Story 1 Tests

```pwsh
# After T012 (analyzer change) is committed, run all US1 tests in parallel:
pytest tests/test_analyzer_duplicate_layer.py tests/test_gui_controllers_duplicates.py tests/test_gui_smoke.py -n auto
```

## Parallel Example: Polish

```pwsh
# T046 and T047 touch different files:
# Developer A: edits README.md
# Developer B: edits pyproject.toml
```

---

## Implementation Strategy

### MVP scope (suggested first delivery)

**US1 only** (Phases 1–3 plus relevant Polish).

Why: It's the only correctness fix; everything else is UX sugar. Shipping
US1 alone gives the user a trustworthy validator immediately, then US2–6
land iteratively.

### Incremental Delivery Plan

1. **MVP**: Setup → Foundational → US1 → Polish (T048, T050) → ship.
2. **v0.4.1**: + US2 + US3 (right-click + sort) — biggest UX wins.
3. **v0.4.2**: + US4 + US5 (filter + severity colors).
4. **v0.4.3**: + US6 (recents) + final Polish (T046, T049).

Each release leaves all prior tests green and ships independently.

---

## Format validation

All 50 tasks above follow the required checklist format:
`- [ ] T### [P?] [US#?] Description with file path`

- ✅ Every task starts with `- [ ]`
- ✅ Every task has a sequential `T###` ID
- ✅ Setup, Foundational, Polish phases have NO `[US#]` label
- ✅ Phases 3–8 tasks all carry `[US1]`–`[US6]` labels
- ✅ `[P]` marker only on truly parallelizable tasks (different files, no incomplete-task deps)
- ✅ Every implementation task names an exact file path
