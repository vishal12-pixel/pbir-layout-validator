# Phase 0 — Research: GUI Power Features Bundle

All Technical Context items were specified by the author (Python 3.14.3,
stdlib-only, Tkinter+ttk, pytest ≥80%/≥90%). No NEEDS CLARIFICATION
markers remain. The research below captures the *why* behind each
implementation decision so reviewers can audit it against the
constitution.

---

## R1. Watch-mode poll mechanism — `Tk.after()` vs `threading.Thread`

- **Decision**: Use `Tk.after(2000, self._watch_tick)` reschedule pattern.
  The tick callback runs on the Tk main thread, takes a fresh
  `dict[Path, float]` mtime snapshot via `watch.snapshot_mtimes()`,
  diffs against the previous snapshot, and calls
  `controllers.validate()` directly when any mtime advanced. The next
  `after()` call is scheduled at the **end** of the tick — and skipped
  entirely when the toggle is OFF — so toggling Off naturally stops the
  loop within ≤2 s (FR-024).
- **Rationale**: Tk widgets are not thread-safe; cross-thread widget
  mutation routinely deadlocks `mainloop()`. A worker thread would
  require a `queue.Queue` plus a separate Tk poll consumer — adding a
  thread *and* a queue *and* a poll. `after()` already gives us the
  poll for free, runs on the right thread, and is trivially testable
  by stubbing the callback in unit tests (no real Tk loop needed).
- **Alternatives considered**:
  - `threading.Thread` + `queue.Queue`: rejected — extra moving parts,
    needs explicit shutdown signaling, and Tk-thread crossings would
    surface as Heisenbugs.
  - `watchdog`/`inotify`: rejected — third-party dependency violates
    Constitution Principle I.
  - `asyncio` + `tkasync`: rejected — third-party + over-engineered for
    a 2 s poll on ≤500 files.

## R2. Profile shipping — package data via `importlib.resources`

- **Decision**: Ship the three markdown profiles as ordinary package
  data under `pbir_validator/profiles/`. `profiles.list_profiles()`
  uses `importlib.resources.files("pbir_validator.profiles")` to
  enumerate `.md` siblings, returning a `dict[str, Path]` keyed by
  display name (`Strict`, `Standard`, `Relaxed`). The combobox appends
  `Report-default` only when `<report_root>/conf.md` exists.
- **Rationale**: `importlib.resources` is stdlib and survives both
  source checkouts and zipped wheels; package-data discovery degrades
  to file-system traversal for source trees, which is what tests will
  exercise. Bundling the files inside the package guarantees the
  feature works after `pip install` without separate config.
- **Alternatives considered**:
  - User-config dir (`~/.config/pbir_validator/profiles/`): rejected —
    users would have to seed the files; ships an empty combobox on
    first run.
  - Hard-coded `dict[str, Rules]` literal in Python: rejected — locks
    profile thresholds into source, denies users the easy win of
    `cat profiles/strict.md` to inspect what `Strict` means.

## R3. Undo backup format and write strategy

- **Decision**: One JSON file per report at
  `<report_root>/.pbir_validator_undo/last_fix.json`. Schema:
  ```json
  {
    "applied_at": "2026-05-02T14:15:30Z",
    "shifts": [
      {"path": "definition/pages/<id>/visuals/<vid>/visual.json",
       "visual_id": "<vid>",
       "old_y": 120.0,
       "new_y": 132.0}
    ]
  }
  ```
  `fixer.apply_plan` writes this file **before** the first
  `writer.write_visual_json` call. `undo.restore_last_fix` reads the
  file, calls `writer.write_visual_json(visual, old_y)` per entry
  (reusing the byte-preserving writer per FR-062), then deletes the
  backup file. Each Apply overwrites the file, giving exactly one
  level of undo (FR-064).
- **Rationale**: A single flat JSON is trivially testable, byte-stable
  across runs (sorted keys, indent=2), and uses the same atomic-write
  pattern (`tempfile` → `os.replace`) the existing writer uses for
  durability. Storing both `old_y` and `new_y` lets tests assert that
  Apply set the file to `new_y` and Undo set it back to `old_y`.
- **Alternatives considered**:
  - Multi-level undo stack: rejected — FR-064 mandates one level; a
    stack would invite UI complexity (Undo×N) for negligible value.
  - Storing whole-file snapshots: rejected — bloats disk by 100×;
    only `position.y` ever changes, so a y-delta record is sufficient.

## R4. Side panel widget choice — `ttk.PanedWindow` vs custom layout

- **Decision**: Wrap the existing notebook in a horizontal
  `ttk.PanedWindow`; left pane = current notebook, right pane = a
  `ttk.Frame` that hosts the drill-down `Text` widget. Default sash
  position = window-width − 360 px on first launch (FR-040).
  Visibility (boolean) is persisted in `recents.json`; the sash pixel
  position is **not** persisted (per spec clarification 5).
- **Rationale**: `PanedWindow` is stdlib, drag-resizable for free, and
  natively keeps right-pane pixel width on window resize when sash
  position is left untouched. Switching from `pack`-only to
  `PanedWindow` is a five-line change in `app.py`.
- **Alternatives considered**:
  - Floating `Toplevel` window: rejected — clarification 5 mandated an
    embedded right pane attached to the main window.
  - Two `Frame`s with manual `place()`: rejected — re-implements what
    `PanedWindow` already does and breaks resize behavior.

## R5. Grade computation — pure function with table lookup

- **Decision**: `grade.compute(counts: dict[str, int]) -> tuple[str, int]`
  computes `score = 3·gaps + 5·overlaps + 4·duplicate_layers + 2·misalignments + 2·h_spacing`
  then maps `score` to a letter via a hard-coded threshold table (`0→A`,
  `1–10→B`, `11–25→C`, `26–60→D`, `61+→F`) per FR-031. Returns
  `(letter, score)`.
- **Rationale**: A 5-row threshold table beats a math formula for
  reviewability and matches the spec's exact thresholds. Pure-function
  shape lets tests exhaust the boundary cases (`score=0/1/10/11/25/26/60/61`)
  without instantiating Tk.
- **Alternatives considered**:
  - Logarithmic mapping: rejected — non-trivial to audit and not what
    the spec specifies.
  - Storing thresholds in a JSON file: rejected — over-engineered for
    five constants.

## R6. Profile rules override — controller signature change

- **Decision**: Extend `controllers.validate()` to accept an optional
  `rules: Mapping | None = None` keyword argument. When `rules is None`
  (the existing default), behavior is byte-identical to today (load
  `<report>/conf.md`). When `rules` is a non-`None` mapping, that
  mapping is used directly and disk lookup is skipped. The GUI passes
  `profiles.load_profile(name)` whenever the combobox is non-default.
- **Rationale**: Additive keyword-only argument preserves every
  existing call site (CLI byte-equivalence per FR-070). Lets the
  profile feature ship without forking the validate code path or
  duplicating fixture loading. Tests cover (a) rules=None → reads
  conf.md, (b) rules=mapping → skips conf.md.
- **Alternatives considered**:
  - Writing the chosen profile into a temp `conf.md` and passing its
    path: rejected — silently mutates the user's working tree if the
    temp file leaks; harder to test.
  - A second function `validate_with_rules()`: rejected — code
    duplication, two surface areas to maintain.

## R7. Drill-down panel: split pure data from Tk widgets

- **Decision**: `gui/panel.py` exposes only Tk-free helpers
  (`extract_visual_context(visual) → dict` and
  `find_visual_for_row(rows, idx, columns, visuals_by_id) → list[Visual]`).
  The actual `Text` widget creation, `state="disabled"` toggling, and
  selection-change binding live in `app.py`, which is already excluded
  from coverage. This keeps `panel.py` 100 % unit-testable on a
  headless host while still delivering the spec-required UI.
- **Rationale**: Mirrors the existing pattern from feature 004
  (`gui/severity.py` is pure-data, `app.py` paints the result). Keeps
  the ≥90% coverage bar reachable on `panel.py` because no Tk
  instantiation is needed in tests.
- **Alternatives considered**:
  - Single Tk-aware module: rejected — pushes logic into
    `app.py`/`widgets.py` (omit'd from coverage), erasing the
    coverage gate's value.

## R8. ZIP export — streaming bytes, not buffering

- **Decision**: New `controllers.export_all_zip(result, fix_plan, dest_path)`
  opens `zipfile.ZipFile(dest_path, "w", ZIP_DEFLATED)` and writes
  one entry per non-empty tab using the **same** per-tab CSV-bytes
  helper the existing per-tab Export buttons already call (FR-013,
  FR-014). Fixed entry names per FR-012: `gaps.csv`, `overlaps.csv`,
  `duplicate_layers.csv`, `misalignments.csv`, `h_spacing.csv`,
  `fix_plan.csv`. Empty tabs are skipped — no zero-byte CSVs land in
  the archive.
- **Rationale**: Reusing the existing helper guarantees byte-identical
  output to the per-tab buttons (testable via SC-005). `ZIP_DEFLATED`
  keeps archive size sensible without a third-party dep.
- **Alternatives considered**:
  - Re-running validators per tab: rejected — duplicates work and
    risks divergence from per-tab CSV bytes.
  - Letting the GUI loop and call per-tab export functions: rejected —
    forces Tk-aware code into the export path; harder to test.

---

## Open questions

None. All clarifications were resolved in `spec.md` § Clarifications.
