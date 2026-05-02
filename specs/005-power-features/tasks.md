---
description: "Task list for feature 005-power-features (GUI Power Features Bundle)"
---

# Tasks: GUI Power Features Bundle

**Input**: Design documents from `specs/005-power-features/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/{controller-api.md, profile-schema.md, undo-record-schema.json}, quickstart.md

**Tests**: Tests are REQUIRED for this feature per Constitution Principle II (TDD). Every new module ships behind a failing test first.

**Organization**: Tasks are grouped by user story (US1–US8) so each story can be implemented, tested, and shipped independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US7)
- Setup / Foundational / Polish phases carry no `[Story]` label
- Every task includes an exact file path

## Path Conventions

Single Python package at repo root: `pbir_validator/`, `pbir_validator/gui/`, `pbir_validator/profiles/` (new), `tests/` at repo root. New tests live directly under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the on-disk slots and packaging hooks every later phase relies on.

- [X] T001 Create new package-data directory [pbir_validator/profiles/](pbir_validator/profiles) with an empty [__init__.py](pbir_validator/profiles/__init__.py) marker so `importlib.resources.files("pbir_validator.profiles")` resolves on both source checkouts and installed wheels.
- [X] T002 [P] Add `[tool.setuptools.package-data]` block to [pyproject.toml](pyproject.toml) declaring `pbir_validator = ["profiles/*.md"]` so the three profile markdown files ship in the wheel.
- [X] T003 [P] Extend the `[tool.coverage.run] omit` list in [pyproject.toml](pyproject.toml) to keep ONLY `pbir_validator/gui/app.py` and `pbir_validator/gui/widgets.py` omitted; explicitly do NOT omit the new modules `pbir_validator/gui/{undo,profiles,watch,grade,panel}.py` so the ≥90% per-module gate bites.
- [X] T004 [P] Append the line `.pbir_validator_undo/` to [.gitignore](.gitignore) so per-report undo backups never enter version control (FR-066). (Final repo-wide verification done in Phase Polish T070.)

**Checkpoint**: Project layout, packaging, and coverage gates ready for new modules.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Land the cross-cutting controller/recents/contract changes every user story depends on. No US-specific logic yet.

**⚠️ CRITICAL**: No user story phase can start until T005–T010 are merged.

- [X] T005 Write failing test [tests/test_controllers_validate_rules_override.py](tests/test_controllers_validate_rules_override.py) covering the new `rules=` keyword on `controllers.validate()`: (a) `rules=None` reads `conf.md` from disk (today's behavior), (b) `rules={...}` skips disk lookup entirely and uses the in-memory mapping, (c) absent `conf.md` + `rules=mapping` still validates. Test MUST fail before T006.
- [X] T006 Implement the `rules: Mapping | None = None` keyword-only argument on [pbir_validator/gui/controllers.py](pbir_validator/gui/controllers.py) `validate()` per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md); preserve byte-identical behavior when `rules is None` so FR-070 / SC-007 holds. T005 must turn GREEN.
- [X] T007 [P] Write failing test [tests/test_recents_new_keys.py](tests/test_recents_new_keys.py): (a) `recents.load()` on a legacy file (list shape) returns a dict with defaults `side_panel_visible=True`, `profile="Standard"`; (b) `recents.load()` on a dict with extra keys round-trips them; (c) `recents.record(side_panel_visible=False, profile="Strict")` persists; (d) `recents.load_paths()` returns the MRU list only.
- [X] T008 Migrate [pbir_validator/gui/recents.py](pbir_validator/gui/recents.py) to dict-shape per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md): add `load_paths()`, change `load()` return type to `dict`, accept `**updates` in `record()`, default missing keys to `True` / `"Standard"` (FR-072). T007 must go GREEN.
- [X] T009 Update existing call sites in [pbir_validator/gui/app.py](pbir_validator/gui/app.py) that consume `recents.load()` as a list to use `recents.load_paths()` instead, keeping the File→Recent submenu byte-identical.
- [X] T010 Run the full existing suite (`pytest -q`) to confirm all 205 prior tests + the two new foundational tests are GREEN before any user story phase begins.

**Checkpoint**: Controller can accept in-memory rules, recents persists new keys, no regressions.

---

## Phase 3: User Story 1 — Double-click row opens report in Power BI Desktop (Priority: P1) 🎯 MVP

**Goal**: Double-clicking any row in the five issue tabs invokes the existing OS-handler call used by the right-click action; Fix Plan tab is inert.

**Independent Test**: Load a fixture report, run Validate, double-click rows in each of the five issue tabs, confirm `controllers.open_in_power_bi` is called once per double-click with the loaded report path; double-click in Fix Plan tab triggers nothing.

### Tests for User Story 1 (RED first)

- [X] T011 [P] [US1] Write failing test [tests/test_app_double_click_binding.py](tests/test_app_double_click_binding.py) — headless-safe; instantiates the result-tab Treeview factory in isolation, monkeypatches `controllers.open_in_power_bi`, fires a synthetic `<Double-Button-1>` `event_generate`, and asserts the helper was called with the loaded report path. Includes a Fix-Plan-tab variant that asserts the helper is NOT called.

### Implementation for User Story 1

- [X] T012 [US1] In [pbir_validator/gui/app.py](pbir_validator/gui/app.py) bind `<Double-Button-1>` on the five issue Treeviews (Gaps, Overlaps, Duplicate Layers, Misalignments, H-Spacing) to a single helper that calls the existing `controllers.open_in_power_bi(self._loaded_report_path)`. Reuse the same error-path branches as the right-click "Open page in Power BI Desktop" action so messagebox text is byte-identical (FR-003). Do NOT bind on the Fix Plan tab (FR-002).

### UI tests for User Story 1

- [X] T013 [US1] Extend [tests/test_app_double_click_binding.py](tests/test_app_double_click_binding.py) with the missing-file and non-Windows error-path assertions, confirming the same `messagebox` text used by the right-click handler is surfaced (FR-003 acceptance scenarios 2 and 3). Verify GREEN.

**Checkpoint**: US1 fully functional — MVP slice is shippable on its own.

---

## Phase 4: User Story 2 — Export all tabs as a single ZIP of CSVs (Priority: P2)

**Goal**: One toolbar click writes a ZIP archive containing one CSV per non-empty tab whose bytes match the per-tab export.

**Independent Test**: With every tab populated, click "Export all (CSV ZIP)", confirm the archive contains the six expected entries (or fewer when tabs are empty) and each CSV is byte-identical to the corresponding per-tab export.

### Tests for User Story 2 (RED first)

- [X] T014 [P] [US2] Write failing test [tests/test_controllers_export_zip.py](tests/test_controllers_export_zip.py) covering FR-010…FR-016: (a) all-tabs-populated case writes exactly the six fixed entry names, (b) empty tabs are skipped — no zero-byte CSVs land, (c) each archived CSV is `==` (bytes) to the existing per-tab export helper's output for the same data, (d) `OSError` on write is propagated, (e) zero-non-empty-tabs case raises a sentinel the GUI converts to "nothing to export".

### Implementation for User Story 2

- [X] T015 [US2] Implement `controllers.export_all_zip(result, fix_plan, dest_path)` in [pbir_validator/gui/controllers.py](pbir_validator/gui/controllers.py) per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md), using `zipfile.ZipFile(..., "w", ZIP_DEFLATED)` and reusing the existing per-tab CSV-bytes helper from [pbir_validator/gui/export.py](pbir_validator/gui/export.py) so per-tab parity is structural, not duplicated. T014 must go GREEN.
- [X] T016 [US2] Add the default-filename builder `<report_root_basename>_validation_<YYYYMMDD-HHMMSS>.zip` either in [pbir_validator/gui/controllers.py](pbir_validator/gui/controllers.py) or a small helper in [pbir_validator/gui/export.py](pbir_validator/gui/export.py); cover with a unit test in [tests/test_controllers_export_zip.py](tests/test_controllers_export_zip.py) using a frozen `datetime`.

### GUI wiring for User Story 2

- [X] T017 [US2] Add the "Export all (CSV ZIP)" toolbar button in [pbir_validator/gui/app.py](pbir_validator/gui/app.py) wired to `filedialog.asksaveasfilename` (suggested filename from T016), then `controllers.export_all_zip`, with retry-on-error via `widgets.show_error` (FR-015) and a "nothing to export" messagebox path. Per-tab Export buttons remain unchanged (FR-014).

### UI tests for User Story 2

- [X] T018 [US2] Add a headless-safe smoke test [tests/test_app_export_zip_button.py](tests/test_app_export_zip_button.py) that monkeypatches `filedialog.asksaveasfilename` and `controllers.export_all_zip`, asserts the dialog default filename matches the contract, and verifies cancel-on-dialog writes nothing.

**Checkpoint**: US2 shippable; per-tab and ZIP exports both function.

---

## Phase 5: User Story 3 — Watch mode auto-revalidates on file change (Priority: P2)

**Goal**: A toolbar toggle drives a 2 s `Tk.after()` poll over `definition.pbir`, `*.pbip`, and `pages/*/visuals/*/visual.json` mtimes; any change re-runs Validate exactly once.

**Independent Test**: Load a report, toggle Watch ON, `os.utime` a watched file, confirm Validate runs once on the next tick; toggle OFF and modify another file, confirm no run.

### Tests for User Story 3 (RED first)

- [X] T019 [P] [US3] Write failing test [tests/test_watch_snapshot.py](tests/test_watch_snapshot.py) covering `watch.snapshot_mtimes(root)`: (a) returns absolute Path → mtime mapping for `<root>/definition.pbir`, every `<root>/*.pbip`, and every `<root>/definition/pages/*/visuals/*/visual.json` (the standard PBIP layout, FR-021); (b) silently skips files that disappear mid-walk (no `FileNotFoundError`); (c) `diff_mtimes(prev, current)` returns True only on advancing or new keys, False on disappearing keys (FR-025).

### Implementation for User Story 3

- [X] T020 [US3] Implement [pbir_validator/gui/watch.py](pbir_validator/gui/watch.py) per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md): `WatchState` frozen dataclass, `snapshot_mtimes(report_root) -> dict[Path, float]`, `diff_mtimes(previous, current) -> bool`. Tk-free, pure-data. T019 must go GREEN with ≥90% module coverage.

### GUI wiring for User Story 3

- [X] T021 [US3] In [pbir_validator/gui/app.py](pbir_validator/gui/app.py) add a "Watch" `ttk.Checkbutton`/toggle (disabled until a report loads — FR-020), the `_watch_tick` callback that calls `watch.snapshot_mtimes` + `watch.diff_mtimes` and invokes `controllers.validate()` exactly once on change, and the `Tk.after(2000, self._watch_tick)` self-rescheduling loop that stops within ≤2 s when the toggle goes OFF (FR-024). After every Validate run (manual, watch-driven, profile-change, or undo) the watch baseline MUST be re-snapshotted so the Validate's own writes do not re-fire the next tick (FR-026). Update status bar each tick to show `Watching: ON (last check N seconds ago)` (FR-023).

### UI tests for User Story 3

- [X] T022 [US3] Add headless-safe test [tests/test_app_watch_toggle.py](tests/test_app_watch_toggle.py) that constructs only the toggle + tick callback (no `mainloop()`), monkeypatches `controllers.validate`, simulates one tick with a changed mtime and asserts validate ran once, simulates a no-change tick and asserts it did NOT run, and confirms a poll exception logs a warning without raising (FR-025).

**Checkpoint**: US3 shippable; Watch coexists with manual Validate.

---

## Phase 6: User Story 4 — Severity grade in summary (Priority: P3)

**Goal**: After every Validate, compute `score = 3·gaps + 5·overlaps + 4·duplicate_layers + 2·misalignments + 2·h_spacing`, derive a letter A–F, render in the status bar and a colored label.

**Independent Test**: Stub `controllers.validate` to return known counts; verify the displayed letter matches the threshold table and the color flips by grade.

### Tests for User Story 4 (RED first)

- [X] T023 [P] [US4] Write failing test [tests/test_grade_compute.py](tests/test_grade_compute.py) exhausting the boundary cases for `grade.compute()`: scores `0, 1, 10, 11, 25, 26, 60, 61` map to `A, B, B, C, C, D, D, F`; missing keys default to 0; negative values raise `ValueError`. Also covers `grade.color_for("A".."F")` returning the documented palette and `""` for the neutral state; unknown letter raises `ValueError`.

### Implementation for User Story 4

- [X] T024 [US4] Implement [pbir_validator/gui/grade.py](pbir_validator/gui/grade.py) per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md): `compute(counts) -> (letter, score)` and `color_for(letter) -> str`. Pure-data; no Tk. T023 must go GREEN with ≥90% coverage.

### GUI wiring for User Story 4

- [X] T025 [US4] In [pbir_validator/gui/app.py](pbir_validator/gui/app.py) add a `ttk.Label` next to the action buttons that shows the grade letter colored via `grade.color_for(letter)`; append `[<letter>]` to the status-bar summary (FR-032). Reset the label to neutral state on report-load and clear-results events (FR-033 acceptance scenario 5).

### UI tests for User Story 4

- [X] T026 [US4] Add headless-safe smoke test [tests/test_app_grade_label.py](tests/test_app_grade_label.py) that constructs only the grade label + the post-validate update routine, feeds known counts via a stubbed `controllers.validate` result, and asserts the label `text` and `foreground` match `grade.compute` + `grade.color_for` outputs.

**Checkpoint**: US4 shippable; grade visible after every Validate.

---

## Phase 7: User Story 5 — Per-row drill-down side panel (Priority: P3)

**Goal**: A right-side `ttk.PanedWindow` pane shows the focused row's visual metadata + raw JSON; rows referencing two visuals show both stacked; visibility persists in `recents.json`.

**Independent Test**: With results loaded, single-click a row in each tab and confirm the panel shows the matching fields; toggle Hide/Show panel; restart the app and confirm visibility persists.

### Tests for User Story 5 (RED first)

- [X] T027 [P] [US5] Write failing test [tests/test_panel_extract_context.py](tests/test_panel_extract_context.py) covering `panel.extract_visual_context(visual)`: dict keys exactly `id, page_id, page_display_name, visual_type, x, y, width, height, parent_group, raw_json`; `raw_json` equals `json.dumps(visual.raw, indent=2, ensure_ascii=False)`. Plus `panel.find_visual_for_row(rows, idx, columns, visuals_by_id)` returns 1 visual for gap-violation single-visual rows and duplicate-canonical rows, **2 stacked visuals for overlap, misalignment, h-spacing, and duplicate-pair rows (FR-042)**, and `[]` when no id resolves. The Fix Plan tab is out of scope.

### Implementation for User Story 5

- [X] T028 [US5] Implement [pbir_validator/gui/panel.py](pbir_validator/gui/panel.py) per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md): `extract_visual_context(visual) -> dict`, `find_visual_for_row(rows, idx, columns, visuals_by_id) -> list[Visual]`. Tk-free. T027 must go GREEN with ≥90% coverage.

### GUI wiring for User Story 5

- [X] T029 [US5] In [pbir_validator/gui/app.py](pbir_validator/gui/app.py) wrap the existing notebook in a horizontal `ttk.PanedWindow`, add a right pane hosting a read-only `Text` widget; on `<<TreeviewSelect>>` for **each of the five issue tabs (Gap Violations, Overlapping Visuals, Duplicate Layer, Row Misalignments, Horizontal Spacing) — Fix Plan is excluded per FR-041**, call `panel.find_visual_for_row` + `panel.extract_visual_context` and render fields stacked when two visuals are returned. Default sash placed so the right pane is 360 px wide on first launch (FR-040). Drive selection from `Treeview.focus()` only (spec clarification 2).
- [X] T030 [US5] Add "Show panel" / "Hide panel" toolbar buttons in [pbir_validator/gui/app.py](pbir_validator/gui/app.py) that call `recents.record(side_panel_visible=…)` and `paned.forget()` / `paned.add(...)` to collapse/restore. On startup, read `recents.load()["side_panel_visible"]` to set initial visibility (FR-044).
- [X] T031 [US5] Add a small Tk-bound factory in [pbir_validator/gui/widgets.py](pbir_validator/gui/widgets.py) that returns a configured read-only `Text` widget (state cycling between `"normal"` for write and `"disabled"` for view) so `app.py` only orchestrates and `panel.py` stays Tk-free.

### UI tests for User Story 5

- [X] T032 [US5] Add headless-safe test [tests/test_app_side_panel_visibility.py](tests/test_app_side_panel_visibility.py) that monkeypatches `recents.load` / `recents.record`, constructs only the panel-visibility toggle handlers (no `mainloop`), and asserts persistence round-trip plus initial-visibility branching from `recents.json`.

**Checkpoint**: US5 shippable; panel visible/hidden state persists across restarts.

---

## Phase 8: User Story 6 — Rule profiles dropdown (Priority: P3)

**Goal**: A toolbar combobox switches the active rules between `Standard`, `Strict`, `Relaxed`, and (when present) `Report-default`; selection persists in `recents.json`; selecting a profile re-runs Validate when a report is loaded.

**Independent Test**: Launch the app, change the dropdown to each value, verify the next Validate uses the chosen profile, the choice persists across restart, and `Report-default` only appears when the report root has a `conf.md`.

### Profile content (RED first)

- [X] T033 [P] [US6] Write failing test [tests/test_profiles_loading.py](tests/test_profiles_loading.py) covering: (a) `profiles.list_profiles(None)` returns the three packaged keys in order `Standard, Strict, Relaxed`; (b) `profiles.list_profiles(report_root)` adds `Report-default` only when `report_root/conf.md` exists; (c) `profiles.load_profile("Standard")` parses to the current built-in defaults (gap=8, overlap_tolerance=0, h_spacing_min=8, row_align_tolerance=2); (d) `Strict` halves them; (e) `Relaxed` doubles them; (f) unknown name raises `KeyError`.

### Implementation for User Story 6

- [X] T034 [US6] Author [pbir_validator/profiles/standard.md](pbir_validator/profiles/standard.md) using the existing `conf.md` markdown grammar, encoding the built-in defaults (gap=8 px, overlap_tolerance=0 px, h_spacing_min=8 px, row_align_tolerance=2 px). MUST parse via `pbir_validator.conf.parse_conf` to a rules dict byte-equivalent to the current built-in defaults.
- [X] T035 [P] [US6] Author [pbir_validator/profiles/strict.md](pbir_validator/profiles/strict.md) (gap=4, overlap_tolerance=0, h_spacing_min=4, row_align_tolerance=1).
- [X] T036 [P] [US6] Author [pbir_validator/profiles/relaxed.md](pbir_validator/profiles/relaxed.md) (gap=16, overlap_tolerance=2, h_spacing_min=16, row_align_tolerance=4).
- [X] T037 [US6] Implement [pbir_validator/gui/profiles.py](pbir_validator/gui/profiles.py) per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md): `list_profiles(report_root=None)` via `importlib.resources.files("pbir_validator.profiles")` returning insertion-ordered dict (`Standard, Strict, Relaxed[, Report-default]`); `load_profile(name, report_root=None)` delegates to `pbir_validator.conf.parse_conf`. T033 must go GREEN with ≥90% coverage.

### GUI wiring for User Story 6

- [X] T038 [US6] Add a `ttk.Combobox` "Profile" to the toolbar in [pbir_validator/gui/app.py](pbir_validator/gui/app.py); populate from `profiles.list_profiles(self._loaded_report_root)`; on change, call `recents.record(profile=value)` and (if a report is loaded) invoke `controllers.validate(..., rules=profiles.load_profile(value, report_root))` (FR-052, FR-053). Initial value comes from `recents.load()["profile"]` defaulting to `"Standard"` (FR-054). Re-populate the dropdown on report load so `Report-default` appears/disappears correctly (FR-055).

### UI tests for User Story 6

- [X] T039 [US6] Add headless-safe test [tests/test_app_profile_combobox.py](tests/test_app_profile_combobox.py) that monkeypatches `controllers.validate`, `recents.record`, and `profiles.load_profile`; constructs only the combobox + change handler; asserts (a) initial value pulled from recents, (b) selecting `Strict` calls `validate(..., rules=<strict mapping>)` once, (c) `Report-default` is added/removed when toggling whether a report root has `conf.md`, (d) profile change without a loaded report does NOT call `validate` but still records (FR-053 acceptance scenario 6).

**Checkpoint**: US6 shippable; profile drives session-level rule source.

---

## Phase 9: User Story 7 — Undo last fix (Priority: P3)

**Goal**: Apply now writes a backup record before mutating; a toolbar Undo button restores `position.y` byte-for-byte via `writer.write_visual_json`, deletes the backup, disables itself, and re-runs Validate.

**Independent Test**: Run Apply, confirm the backup file exists and the button enables; click Undo, confirm each touched `visual.json` is byte-restored in the y bytes, backup is deleted, button is disabled, Validate ran once.

### Tests for User Story 7 (RED first)

- [X] T040 [P] [US7] Write failing test [tests/test_undo_record_and_restore.py](tests/test_undo_record_and_restore.py) covering [contracts/undo-record-schema.json](specs/005-power-features/contracts/undo-record-schema.json): (a) `record_pre_fix(report_root, plan)` writes the schema-conformant JSON with one entry per shift, parent dir is created, atomic-write via tempfile+os.replace; (b) overwriting an existing backup keeps only the latest plan (FR-064); (c) `restore_last_fix` returns `(True, msg, modified_paths)` and each `visual.json`'s `position.y` is byte-restored to `old_y`; (d) on success, the backup file AND the empty `.pbir_validator_undo/` dir are deleted; (e) missing/unreadable backup returns `(False, msg, [])`; (f) per-file write failure aborts and leaves the backup untouched (FR-065).
- [X] T041 [P] [US7] Write failing test [tests/test_fixer_writes_undo_backup.py](tests/test_fixer_writes_undo_backup.py): `fixer.apply_plan(report, shifts)` calls `undo.record_pre_fix(report.root, shifts)` BEFORE the first `writer.write_visual_json` call, asserted via call-order capture (monkeypatch + ordered list).

### Implementation for User Story 7

- [X] T042 [US7] Implement [pbir_validator/gui/undo.py](pbir_validator/gui/undo.py) per [contracts/controller-api.md](specs/005-power-features/contracts/controller-api.md) and [contracts/undo-record-schema.json](specs/005-power-features/contracts/undo-record-schema.json): `record_pre_fix(report_root, plan) -> Path` (atomic write, sorted keys, indent=2, POSIX-style `path` field, UTC `applied_at`); `restore_last_fix(report_root) -> (ok, message, modified_paths)` reusing `writer.write_visual_json` for byte-preserving y restores (FR-062). T040 must go GREEN with ≥90% coverage.
- [X] T043 [US7] Modify [pbir_validator/fixer.py](pbir_validator/fixer.py) `apply_plan` to call `undo.record_pre_fix(report.root, shifts)` BEFORE the first `writer.write_visual_json` call (FR-060). Signature unchanged. T041 must go GREEN.

### GUI wiring for User Story 7

- [X] T044 [US7] In [pbir_validator/gui/app.py](pbir_validator/gui/app.py) add the "Undo last fix" toolbar button. Initial enabled state computed from `<report_root>/.pbir_validator_undo/last_fix.json` existence; re-evaluated on every report-load and after every Apply / Undo (FR-061). Click handler calls `undo.restore_last_fix(report_root)`, surfaces failure via `widgets.show_error` (FR-065), then disables the button and invokes `controllers.validate()` (FR-063). Loading a different report re-evaluates state immediately and never touches the previous report's backup (FR-061 spec clarification 4).

### UI tests for User Story 7

- [X] T045 [US7] Add headless-safe test [tests/test_app_undo_button.py](tests/test_app_undo_button.py): monkeypatch `undo.restore_last_fix` + `controllers.validate`; assert (a) button is disabled when no backup exists, (b) becomes enabled after Apply, (c) becomes disabled after a successful Undo and Validate ran exactly once, (d) on `restore_last_fix` returning `ok=False` an error messagebox is shown and the button stays enabled.

**Checkpoint**: US7 shippable; one-level undo is safe and self-contained.

---

## Phase 10: User Story 8 — Integration: Watch + Profile change + Undo together (Priority: P3)

**Goal**: Confirm Watch / Profile / Undo coexist without state leakage across one end-to-end session.

**Independent Test**: Load a report, toggle Watch ON, change profile from Standard to Strict (auto-validate fires once), `os.utime` a watched file (validate fires again), Apply, Undo, confirm Watch still ON, profile still Strict, backup gone, next mtime change still triggers validate.

### Integration tests for User Story 8 (RED first)

- [X] T046 [P] [US8] Write failing integration test [tests/test_integration_watch_profile_undo.py](tests/test_integration_watch_profile_undo.py) — headless-safe: instantiates only the toolbar handlers and tick callbacks (no `mainloop`), monkeypatches `controllers.validate`, simulates the full sequence in §US8 acceptance scenarios 1–3, asserts: (a) profile change while Watch ON re-validates once and Watch stays ON, (b) Apply + Undo both succeed and the next watched mtime advance still triggers validate exactly once, (c) `recents.json` after restart reflects both `side_panel_visible: false` and `profile: "Strict"`.

### Implementation for User Story 8

- [X] T047 [US8] In [pbir_validator/gui/app.py](pbir_validator/gui/app.py) confirm the profile-change handler, Apply handler, Undo handler, and `_watch_tick` all share a single `_run_validate(rules=…)` entry point so a Validate triggered by Undo coexists with the watch baseline snapshot (no double-validate on the next tick — Edge Cases bullet 4). Add a small reset of the `WatchState` snapshot after every manual Validate so the next watch tick measures from the post-Validate mtimes.
- [X] T048 [US8] Verify queueing semantics: profile combobox change while a Validate is already running queues the change and the next Validate uses the new profile (Edge Cases bullet 5). Implement via a `self._pending_profile` slot consumed at the top of `_run_validate`. T046 must go GREEN.

**Checkpoint**: All eight user stories pass in concert.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: README updates, packaging finalization, gates, manual smoke, CLI parity.

- [X] T049 [P] Update [README.md](README.md) with a "GUI Power Features" section enumerating the seven new toolbar items (Double-click row, Export all CSV ZIP, Watch, Grade label, Side panel, Profile combobox, Undo last fix), screenshot placeholders, and notes on `recents.json` keys + `.pbir_validator_undo/`.
- [X] T050 [P] Document the new profile authoring workflow at the bottom of [README.md](README.md): pointer to `pbir_validator/profiles/*.md`, the existing `conf.md` grammar reference, and the `Report-default` discovery rule.
- [X] T051 Verify [pyproject.toml](pyproject.toml) `[tool.setuptools.package-data]` includes `pbir_validator = ["profiles/*.md"]` (T002) AND that `[tool.coverage.run] omit` keeps ONLY `pbir_validator/gui/app.py` and `pbir_validator/gui/widgets.py` (T003) — explicitly NOT omitting `grade.py`, `profiles.py`, `undo.py`, `watch.py`, `panel.py` since those are pure or near-pure and must hit ≥90% coverage. Run `pip install -e .` once and import `pbir_validator.profiles` to confirm package-data ships.
- [X] T052 Confirm [.gitignore](.gitignore) contains `.pbir_validator_undo/` from T004; if missing, add it. Final repo-wide check.
- [X] T053 [P] Run the full `pytest -q --cov=pbir_validator --cov-report=term-missing` suite and verify: (a) all 205 prior tests + every new test from Phases 2–10 are GREEN, (b) project total coverage ≥80% (FR-074, SC-003), (c) per-module coverage ≥90% on each of `pbir_validator/gui/{undo,profiles,watch,grade,panel}.py` (FR-074, SC-003), (d) `pbir_validator/gui/app.py` and `pbir_validator/gui/widgets.py` remain `omit`'d.
- [X] T054 [P] Execute the manual quickstart at [specs/005-power-features/quickstart.md](specs/005-power-features/quickstart.md) end-to-end against a fixture report: every step in Stories 1–8 must pass; record outcomes in a checklist (success criteria SC-001).
- [X] T055 Run the CLI parity gate: `python -m pbir_validator <fixture_report> --validate > out.txt 2>&1` and `fc /N out.txt baseline.txt` against the pre-feature baseline; verify zero diff in stdout, stderr, AND exit code (FR-070, SC-007). If any byte drifts, file a fix before declaring the feature done.

**Checkpoint**: All 8 user stories pass acceptance scenarios; coverage gates green; CLI byte-identical to pre-feature `main`.

---

## Dependencies

```text
Setup (T001-T004)
   └─→ Foundational (T005-T010)
          ├─→ US1 (T011-T013)            # MVP — independently shippable
          ├─→ US2 (T014-T018)            # independent of US1
          ├─→ US3 (T019-T022)            # independent of US1/US2
          ├─→ US4 (T023-T026)            # independent
          ├─→ US5 (T027-T032)            # independent
          ├─→ US6 (T033-T039)            # depends on T006 rules-override
          ├─→ US7 (T040-T045)            # touches fixer.py — independent of US1-US6 logic
          └─→ US8 (T046-T048)            # requires US3 + US6 + US7
                 └─→ Polish (T049-T055)
```

## Parallel Execution Examples

Once Foundational is complete, all of these can run in parallel because they touch independent files:

- T011 (`tests/test_app_double_click_binding.py`) ‖ T014 (`tests/test_controllers_export_zip.py`) ‖ T019 (`tests/test_watch_snapshot.py`) ‖ T023 (`tests/test_grade_compute.py`) ‖ T027 (`tests/test_panel_extract_context.py`) ‖ T033 (`tests/test_profiles_loading.py`) ‖ T040 (`tests/test_undo_record_and_restore.py`) ‖ T041 (`tests/test_fixer_writes_undo_backup.py`).
- After their RED tests are written, the implementation modules are independent files and can also be implemented in parallel: T020 (`watch.py`) ‖ T024 (`grade.py`) ‖ T028 (`panel.py`) ‖ T037 (`profiles.py`) ‖ T042 (`undo.py`).
- Within US6, the three profile markdown files are independent: T034 (`standard.md`) ‖ T035 (`strict.md`) ‖ T036 (`relaxed.md`).
- Within Polish, T049, T050, T053, T054 are all independent.

GUI-wiring tasks (T012, T017, T021, T025, T029, T030, T038, T044, T047, T048) all touch [pbir_validator/gui/app.py](pbir_validator/gui/app.py) so they MUST be serialized within each story but stories themselves can interleave by merging in priority order.

## Implementation Strategy

1. **MVP first**: Land Setup + Foundational + US1, ship as the smallest valuable increment (double-click open).
2. **Incremental delivery, priority order**: Add US2 (P2 ZIP), US3 (P2 Watch), then the four P3 stories US4 / US5 / US6 / US7 in any order — they are file-independent. Save US8 for last because it integrates US3 + US6 + US7.
3. **TDD discipline**: Every new module's failing test (T005, T011, T014, T019, T023, T027, T033, T040, T041, T046) must be merged RED before its matching implementation task. This is non-negotiable per Constitution Principle II.
4. **Coverage gate**: After every story phase, run `pytest --cov` to confirm the project total stays ≥80% and any new module reaches ≥90%; if not, expand the story's pure-data module rather than relaxing the gate.
5. **CLI parity gate**: T055 is the last gate; do not declare the feature complete if `fc /N` shows any byte diff against the pre-feature baseline.

---

## Format Validation

All 55 tasks above conform to the strict checklist format `- [ ] <TaskID> [P?] [Story?] <description with file path>`:

- Every line starts with `- [ ]`.
- Every task has a sequential ID `T001`…`T055`.
- `[P]` appears only on tasks that touch independent files with no incomplete dependency.
- `[US1]`–`[US8]` appears only on user-story-phase tasks; Setup, Foundational, and Polish phases carry no story label.
- Every task description includes an exact workspace-relative file path (or paths) the agent will create or edit.

## Extension Hooks

**Optional Hook**: git
Command: `/speckit.git.commit`
Description: Auto-commit after task generation

Prompt: Commit task generation output?
To execute: `/speckit.git.commit`
