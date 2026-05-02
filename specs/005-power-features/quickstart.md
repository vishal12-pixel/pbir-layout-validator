# Quickstart — Validating Feature 005 Manually

This recipe walks a developer through a single end-to-end smoke pass
covering all seven new GUI features. It assumes a checkout of branch
`005-power-features` with the implementation merged.

## Prerequisites

- Python 3.14.3 on your `PATH`.
- A clone of the repo at the workspace root.
- A sample report that produces issues in every tab — the easiest is
  the bundled fixture at
  `tests/fixtures/sample_report_with_issues.Report/` (or any of the
  user-supplied reports in the workspace).
- Power BI Desktop installed (Windows only) for Story 1's
  double-click test.

## Setup (once)

```pwsh
cd "C:\Users\v-vsethi\Pictures\pbib validator tool"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q                # baseline: all 205 + new tests green, ≥80 % coverage
```

## Story 1 — Double-click opens in Power BI Desktop

1. `python -m pbir_validator.gui.app`
2. **File → Open Report…** → pick the sample report root.
3. Click **Validate**. Confirm rows appear in Gaps / Overlaps /
   Duplicates / Misalignments / H-Spacing.
4. Double-click any row in each of the five issue tabs.
   **Expected**: Power BI Desktop launches once per double-click on
   the loaded `definition.pbir` (or `.pbip`).
5. Switch to the **Fix Plan** tab and double-click any row.
   **Expected**: nothing happens (FR-002).

## Story 2 — Export all (CSV ZIP)

1. With results loaded, click **Export all (CSV ZIP)** in the toolbar.
2. Accept the suggested filename
   (`<basename>_validation_<YYYYMMDD-HHMMSS>.zip`) and pick a
   destination.
3. Open the resulting archive.
   **Expected** entries: `gaps.csv`, `overlaps.csv`,
   `duplicate_layers.csv`, `misalignments.csv`, `h_spacing.csv`,
   `fix_plan.csv` — one per non-empty tab. Empty tabs ⇒ no CSV.
4. Diff each CSV against the corresponding per-tab Export-button
   output. **Expected**: byte-identical (SC-005).

## Story 3 — Watch mode

1. Click the **Watch** toggle.
   **Expected**: status bar shows `Watching: ON (last check 0 s ago)`.
2. In a second terminal:
   ```pwsh
   $f = "<report_root>\definition\pages\<page>\visuals\<vid>\visual.json"
   (Get-Item $f).LastWriteTime = Get-Date
   ```
3. Wait ≤2 s.
   **Expected**: result tabs refresh exactly once.
4. Without further changes wait another 6 s.
   **Expected**: tabs do not refresh again (FR-022).
5. Click **Watch** again to toggle OFF.
   **Expected**: poller stops within ≤2 s; status-bar message
   disappears.

## Story 4 — Severity grade

1. With a Validate run already complete, look at the status bar and
   the new label widget next to the action buttons.
   **Expected**: status bar contains `[<letter>]`; label shows the
   same letter colored per the palette in `data-model.md` § 4.
2. Apply a fix that drops the count to zero.
   **Expected**: grade flips to `A` (green) on the next Validate.
3. Click **Open Report…** to load a new report.
   **Expected**: grade label resets to neutral until the next
   Validate completes (FR-033).

## Story 5 — Drill-down side panel

1. Click **Show panel** in the toolbar (if not already visible).
2. Single-click a row in **Gaps**.
   **Expected**: right pane shows id, pageId, page display name, type,
   x, y, width, height, parent group, plus the raw JSON in a
   read-only `Text` widget.
3. Single-click a row in **Overlapping Visuals**.
   **Expected**: both visuals' details stack in the panel
   (FR-042).
4. Multi-select two rows (Ctrl+Click).
   **Expected**: the panel tracks the **last-clicked** row only
   (spec clarification 2).
5. Click **Hide panel**.
   **Expected**: panel collapses; left pane absorbs the width.
6. Restart the GUI.
   **Expected**: panel starts collapsed because
   `recents.json["side_panel_visible"]` is `false`.

## Story 6 — Profile dropdown

1. Open the toolbar **Profile** combobox.
   **Expected** options: `Standard`, `Strict`, `Relaxed`. Plus
   `Report-default` only when the loaded report root contains
   `conf.md`.
2. Select **Strict**.
   **Expected**: Validate re-runs within 1 s (SC-008); finding counts
   typically increase because tolerances halved.
3. Restart the GUI.
   **Expected**: combobox starts on `Strict`
   (`recents.json["profile"] == "Strict"`).

## Story 7 — Undo last fix

1. Click **Fix** to compute a plan, then **Apply**.
   **Expected**:
   - Toolbar **Undo last fix** button enables.
   - File `<report_root>/.pbir_validator_undo/last_fix.json` exists
     with one entry per touched visual.
2. Click **Undo last fix**.
   **Expected**:
   - Each affected `visual.json` has its `position.y` byte-restored
     to the pre-Apply value (diff with `git diff` or `fc /B`).
   - The backup file is deleted; the `.pbir_validator_undo/` dir is
     removed if empty.
   - Validate re-runs automatically.
   - Undo button disables.
3. Apply twice in a row.
   **Expected**: `last_fix.json` records only the second Apply's
   pre-shift state (FR-064).

## Story 8 — Watch + Profile + Undo together

1. Toggle **Watch** ON.
2. Switch profile from `Standard` → `Strict`.
   **Expected**: Validate runs once with the Strict profile; Watch
   stays ON.
3. `os.utime` a watched file via the second terminal.
   **Expected**: Validate runs again on the next watch tick.
4. Click **Apply**, then **Undo last fix**.
   **Expected**: both succeed; Watch is still ON; profile is still
   `Strict`; backup file is gone.

## CLI parity check (regression gate)

```pwsh
python -m pbir_validator <report_root> --validate > out.txt 2>&1
git fetch origin main
git show origin/main:tests/fixtures/baseline_validate_stdout.txt | Out-File -Encoding utf8 baseline.txt
fc /N out.txt baseline.txt
```

**Expected**: zero diff (FR-070, SC-007).

## Coverage gate

```pwsh
pytest -q --cov=pbir_validator --cov-report=term-missing
```

**Expected**:

- Project total ≥ 80 %.
- `pbir_validator/gui/undo.py` ≥ 90 %.
- `pbir_validator/gui/profiles.py` ≥ 90 %.
- `pbir_validator/gui/watch.py` ≥ 90 %.
- `pbir_validator/gui/grade.py` ≥ 90 %.
- `pbir_validator/gui/panel.py` ≥ 90 %.
