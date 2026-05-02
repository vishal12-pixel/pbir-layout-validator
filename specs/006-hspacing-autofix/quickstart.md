# Quickstart: Horizontal Spacing Auto-Fix

## Prerequisites

- Python 3.11+
- `pbir_validator` installed (`pip install -e .` from repo root)
- A Power BI PBIR-format report with known h-spacing deviations

## Quick Verification

### 1. Validate to see h-spacing issues

```bash
python -m pbir_validator validate --report path/to/MyReport.Report
```

Look for "h-spacing issue(s)" in the output.

### 2. Fix with Strict profile (CLI)

```bash
# Dry-run first (default behavior):
python -m pbir_validator fix --report path/to/MyReport.Report --dry-run

# Apply with Strict profile (h-spacing fix enabled):
python -m pbir_validator fix --report path/to/MyReport.Report --apply
```

> Note: H-spacing fixes only run when the active profile has `hspacing_fix = true`.
> The Strict profile enables this by default. Standard and Relaxed do not.

### 3. Undo if needed

In the GUI: click the **Undo** button after applying.

Both Y-shifts and X-shifts are restored to their original values.

### 4. Run tests

```bash
python -m pytest tests/ -q --no-header -m "not benchmark"
```

## Key Files to Modify

| File | Change |
|------|--------|
| `pbir_validator/models.py` | Add `old_x`, `new_x`, `delta_x` to `Shift` |
| `pbir_validator/fixer.py` | Add `plan_hspacing_fixes()`, integrate into `plan_fixes()` |
| `pbir_validator/writer.py` | Add `new_x` param to `write_visual_json()` |
| `pbir_validator/gui/undo.py` | Store/restore `old_x` in backup |
| `pbir_validator/ui.py` | Add action column to `print_shift_plan()` |
| `pbir_validator/gui/controllers.py` | Extend `fix_plan_rows()` for X-shifts |
| `pbir_validator/profiles/strict.md` | Add `# hspacing_fix = true` |
| `pbir_validator/gui/profiles.py` | Parse `hspacing_fix` flag |

## Architecture at a Glance

```
Profile (hspacing_fix=true?)
    ↓
plan_fixes()
    ├── Y-shift planning (existing)
    └── plan_hspacing_fixes() (NEW)
            ├── group issues by (page, row, type)
            ├── compute cumulative X-corrections left→right
            ├── boundary check (0 ≤ x, x+w ≤ page_w)
            └── emit Shift(old_x, new_x, delta_x)
                    ↓
            write_visual_json(v, new_y, new_x=shift.new_x)
                    ↓
            undo backup stores old_x/new_x
```
