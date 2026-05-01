# Quickstart — Feature 004 GUI Quick Wins

For developers validating the feature locally.

## Prerequisites

- Python 3.14.x installed and on PATH
- `pip install -e .` already run from repo root
- Branch `004-gui-quick-wins` checked out

## 1. Run the test suite

From repo root:

```pwsh
pytest -v --cov=pbir_validator --cov-report=term-missing
```

Expected after feature:

- All pre-existing tests still pass (≥166).
- New tests pass: `test_analyzer_duplicate_layer`, `test_gui_severity`,
  `test_gui_recents`, `test_gui_controllers_sort`,
  `test_gui_controllers_filter`.
- Total coverage stays ≥80%; `recents.py` and `severity.py` ≥90%.

## 2. Verify the reader hotfix (US1)

```pwsh
python -m pbir_validator --validate tests\fixtures\duplicate-layer-page.Report
```

Expected: stderr/stdout reports the duplicate-layer page with **2**
visuals detected (not 1) and a new "Duplicate Layer" finding.

## 3. Launch the GUI

```pwsh
pbir_validator-gui
```

Verify in order:

- **Recents menu** — File menu shows "(no recent reports)" on first
  launch (or your previous reports if you've used the app before).
- Browse to a `.Report` folder, click Validate.
- **6 tabs** appear: Gap Violations, Overlapping Visuals, Duplicate
  Layer, Row Misalignments, Horizontal Spacing, Fix Plan.
- **Filter box** appears above each result table; typing narrows rows
  case-insensitively. Clear the box → all rows return.
- **Sort** — click "Deviation Px" header on Gap Violations. Rows reorder
  numerically (not lexically — `9 < 10 < 17`). Click again → descending.
- **Severity colors** — rows with `|deviation_px| > 10` are red,
  `≤ 2` are green, between are yellow.
- **Right-click any row** → context menu with "Open page in Power BI
  Desktop" and "Copy row".
  - "Open page in Power BI Desktop" launches Power BI Desktop on
    `<report>/definition.pbir`.
  - "Copy row" → paste into Notepad → tab-separated cells.
- Re-launch the GUI (`pbir_validator-gui` again). The just-loaded report
  appears at the top of the Recents menu.

## 4. Verify recents persistence

```pwsh
Get-Content "$env:APPDATA\pbir_validator\recents.json"
```

Expected: a JSON object `{"recent": ["<path you just loaded>", ...]}`
with at most 5 entries, MRU-first.

## 5. Verify CLI is unchanged

```pwsh
pbir_validator --help
pbir_validator --validate tests\fixtures\sample-report.Report
```

Expected: identical output to main branch — no new flags, no changed
exit codes, no new log lines.

## 6. Performance smoke check

Open the GUI on a report with 100+ violations. Type quickly in the
filter box — visible rows should update with no perceptible delay
(< 100 ms target per SC-003a).

## Rollback / cleanup

If anything misbehaves and you want a fresh recents file:

```pwsh
Remove-Item "$env:APPDATA\pbir_validator\recents.json" -Force
```

The app will recreate it on next successful load.
