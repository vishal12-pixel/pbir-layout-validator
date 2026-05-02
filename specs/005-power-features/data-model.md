# Phase 1 — Data Model: GUI Power Features Bundle

This document describes every persisted or in-memory data structure
introduced by feature 005. JSON-on-disk artifacts have a matching JSON
Schema under `contracts/`; in-memory dataclasses are documented inline.

---

## 1. Profile (packaged read-only data)

Three markdown files shipped under `pbir_validator/profiles/`:

| Name (display) | File             | gap | overlap_tolerance | h_spacing_min | row_align_tolerance |
|----------------|------------------|----:|------------------:|--------------:|--------------------:|
| Standard       | `standard.md`    |   8 |                 0 |             8 |                   2 |
| Strict         | `strict.md`      |   4 |                 0 |             4 |                   1 |
| Relaxed        | `relaxed.md`     |  16 |                 2 |            16 |                   4 |

- **Format**: Identical to the existing `conf.md` markdown grammar
  parsed by `pbir_validator.conf.parse_conf` (see
  `contracts/profile-schema.md`).
- **Lifecycle**: Read-only. Bundled into the wheel via `pyproject.toml`
  `[tool.setuptools.package-data]`.
- **Discovery**: `profiles.list_profiles()` returns
  `{"Standard": Path, "Strict": Path, "Relaxed": Path}` plus
  `{"Report-default": Path}` only when `report_root/conf.md` exists.

## 2. UndoRecord (per-report on-disk artifact)

- **Path**: `<report_root>/.pbir_validator_undo/last_fix.json`
- **Schema**: see `contracts/undo-record-schema.json` (canonical).
- **Shape**:
  ```json
  {
    "applied_at": "2026-05-02T14:15:30Z",
    "shifts": [
      {
        "path": "definition/pages/<page-id>/visuals/<visual-id>/visual.json",
        "visual_id": "<visual-id>",
        "old_y": 120.0,
        "new_y": 132.0
      }
    ]
  }
  ```
- **Fields**:
  - `applied_at` — UTC ISO-8601 timestamp the backup was written.
  - `shifts[]` — one entry per visual whose `position.y` was changed by
    Apply.
    - `path` — POSIX-style relative path from report root to
      `visual.json` (slashes never backslashes, so the file is
      portable across OSes).
    - `visual_id` — the visual `id` field; redundant with `path` but
      cheap correlation aid for log readers.
    - `old_y` — pre-Apply value of `position.y` (number).
    - `new_y` — post-Apply value (number); written for audit only —
      Undo restores `old_y`.
- **Lifecycle**:
  1. `fixer.apply_plan` calls `undo.record_pre_fix(report_root, plan)`
     **before** any `writer.write_visual_json` call.
  2. The file persists across app restarts, profile changes, and
     Watch ticks.
  3. `undo.restore_last_fix(report_root)` reads it, restores each
     `old_y` via `writer.write_visual_json`, then deletes the file
     and the parent dir if empty.
  4. The next Apply overwrites the file (one-level undo, FR-064).
  5. Loading a different report immediately re-evaluates the Undo
     button against that report's own backup file (FR-061). The
     previous report's backup stays on disk.

## 3. WatchState (in-memory)

- **Defined in**: `pbir_validator/gui/watch.py`
- **Shape** (frozen dataclass):
  ```python
  @dataclass(frozen=True)
  class WatchState:
      mtimes: Mapping[Path, float]   # absolute path → st_mtime
      last_check: float              # time.time() of last poll
  ```
- **Producer**: `watch.snapshot_mtimes(root: Path) -> dict[Path, float]`
  walks `definition.pbir`, all `*.pbip` siblings, and every
  `pages/*/visuals/*/visual.json`. Files that disappear mid-walk are
  silently skipped (FR-025).
- **Consumer**: `app.py`'s `_watch_tick` compares the new snapshot to
  the previous `WatchState.mtimes`; any mismatched key triggers
  `controllers.validate()` exactly once before scheduling the next
  `Tk.after(2000, …)` call.
- **Persistence**: None. Lives only on the `App` instance.

## 4. GradeSummary (in-memory, per-Validate)

- **Defined in**: `pbir_validator/gui/grade.py`
- **Public function**: `grade.compute(counts) -> tuple[str, int]`
- **Inputs**: `counts: dict[str, int]` with keys `gaps`, `overlaps`,
  `duplicate_layers`, `misalignments`, `h_spacing`. Missing keys
  default to 0.
- **Score formula**: `3·gaps + 5·overlaps + 4·duplicate_layers
  + 2·misalignments + 2·h_spacing` (FR-030).
- **Letter mapping** (FR-031):
  | Score range | Letter |
  |-------------|--------|
  | `0`         | `A`    |
  | `1 – 10`    | `B`    |
  | `11 – 25`   | `C`    |
  | `26 – 60`   | `D`    |
  | `≥ 61`      | `F`    |
- **Color helper**: `grade.color_for(letter) -> str` returns a Tk
  color name (`"#1a7f37"` for A, `"#9a6700"` for B, `"#bf8700"` for C,
  `"#cf222e"` for D, `"#82071e"` for F, `""` for the neutral state when
  no run has occurred yet — FR-033).

## 5. DrillDownContext (in-memory, on selection)

- **Defined in**: `pbir_validator/gui/panel.py`
- **Public functions**:
  - `extract_visual_context(visual: Visual) -> dict` — returns
    `{"id", "page_id", "page_display_name", "visual_type", "x", "y",
    "width", "height", "parent_group", "raw_json"}` where `raw_json`
    is the pretty-printed (indent=2) string form of `visual.raw`.
  - `find_visual_for_row(rows, idx, columns, visuals_by_id) -> list[Visual]` —
    returns 1 visual for single-visual rows (gap-violation single-visual
    row only when applicable, duplicate-layer canonical) and 2 visuals
    for two-visual rows (overlap, **misalignment**, h-spacing,
    duplicate-layer pair). The Fix Plan tab has no binding (FR-041
    excludes it).
- **Lifecycle**: Recomputed on every Treeview `<<TreeviewSelect>>`
  event. Driven by `Treeview.focus()` (last-clicked row) per spec
  clarification 2; multi-selection does not aggregate.

## 6. RecentsState additions (persisted)

- **File**: `<user_config>/pbir_validator/recents.json` (existing).
- **New keys**:
  | Key                  | Type    | Default     | Source FR |
  |----------------------|---------|-------------|-----------|
  | `side_panel_visible` | boolean | `true`      | FR-044    |
  | `profile`            | string  | `"Standard"`| FR-054    |
- **Backward compatibility**: Older recents files lacking these keys
  load unchanged; the missing keys default to `true` and `"Standard"`
  respectively (FR-072). Unrecognized profile names fall back to
  `"Standard"` with no error.
- **Read/write API**: `recents.load()` returns a dict (was: list);
  callers that only want the MRU list use `recents.load_paths()`.
  Migration is internal — no schema bump file required.

## 7. ResultTable double-click binding (no new data, behavior only)

- The five issue tables (Gaps, Overlaps, Duplicate Layers,
  Misalignments, H-Spacing) gain a `<Double-Button-1>` binding that
  calls the existing `controllers.open_in_power_bi(report_path)`
  helper (FR-001). The Fix Plan tab is **not** bound (FR-002). No new
  state introduced.
