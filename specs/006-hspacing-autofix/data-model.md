# Data Model: Horizontal Spacing Auto-Fix

## Entity Changes

### Shift (MODIFY — `models.py`)

Extended with optional X-coordinate fields. Backward-compatible: all new fields
default to `None`, so existing Y-only consumers see no change.

```python
@dataclass(frozen=True)
class Shift:
    visual_id: str
    page_id: str
    path: Path
    old_y: float
    new_y: float
    delta_y: float
    group_member: bool = False
    # --- New X-shift fields (FR-016) ---
    old_x: float | None = None
    new_x: float | None = None
    delta_x: float | None = None
```

**Fields**:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `old_x` | `float \| None` | `None` | Original `position.x` before shift |
| `new_x` | `float \| None` | `None` | Target `position.x` after shift |
| `delta_x` | `float \| None` | `None` | `new_x - old_x` |

**Invariants**:
- When `old_x is not None`, all three X fields are populated.
- When `old_x is None`, this is a Y-only shift (existing behavior).
- A shift may have both Y and X mutations (combined shift).

### HSpacingIssue (READ-ONLY — `models.py`)

Existing entity. No changes. Consumed as input to X-shift planning.

```python
@dataclass(frozen=True)
class HSpacingIssue:
    page_id: str
    page_display_name: str
    visual_type: str
    left_visual_id: str
    right_visual_id: str
    expected_gap_px: float
    actual_gap_px: float
    deviation_px: float
    row_index: int
```

### Undo Backup Entry (MODIFY — `gui/undo.py`)

Extended JSON schema for backup shift entries:

```json
{
  "path": "definition/pages/<page_id>/visuals/<visual_id>/visual.json",
  "visual_id": "abc123",
  "old_y": 100.0,
  "new_y": 108.0,
  "old_x": 200.0,   // NEW — present only when X was shifted
  "new_x": 198.0    // NEW — present only when X was shifted
}
```

**Rules**:
- `old_x` and `new_x` are omitted for Y-only shifts (backward-compatible
  with existing backups).
- When present, both `old_x` and `new_x` must be set.

### Profile Flag (NEW — profile `.md` files)

A metadata flag in the profile header comments:

```markdown
# Strict profile — half the Standard tolerances
# hspacing_fix = true
```

**Parsing**: `profiles.py` scans header comment lines for
`hspacing_fix = true|false`. Default: `false` when absent.

## Relationships

```
Profile (hspacing_fix flag)
    │
    ▼
plan_fixes() ──────────────────────────────► Shift[] (with old_x/new_x/delta_x)
    │                                              │
    ├── validate_report() → HSpacingIssue[]        │
    │                                              ▼
    ├── plan_hspacing_fixes()                write_visual_json(v, new_y, new_x=...)
    │       │                                      │
    │       ├── boundary checks (x<0, x+w>page_w)  │
    │       └── cumulative left-to-right shifts     ▼
    │                                         visual.json (atomic write)
    ▼
Undo Backup (old_x/new_x in entries)
    │
    ▼
restore_last_fix() → write_visual_json(v, old_y, new_x=old_x)
```

## State Transitions

### H-Spacing Issue Lifecycle

```
DETECTED (by find_row_hspacing_issues)
    │
    ▼
PLANNED (X-shifts computed, boundary-checked)
    │
    ├── FIXABLE → shifts emitted → APPLIED (JSON written)
    │                                  │
    │                                  ▼
    │                              UNDONE (undo restores old_x)
    │
    └── UNFIXABLE (x<0 or x+w>page_w) → reported, no write
```

### Profile Gate

```
profile_flags is None OR hspacing_fix absent OR hspacing_fix=false
    → skip h-spacing fix planning entirely
    → return Y-only shifts (existing behavior)

hspacing_fix=true
    → run plan_hspacing_fixes()
    → merge X-shifts into unified Shift list
```

## Validation Rules

1. `new_x >= 0` for all affected visuals in a row (FR-006).
2. `new_x + width <= page.width` for all affected visuals (FR-005).
3. Both checks apply to ALL visuals shifted by a single h-spacing correction;
   if any fails, the entire row's h-spacing fix is marked unfixable.
4. X-shifts are row-local — no cascading to other rows or pages (FR-002).
5. Only same-type peers with ≥3 members in a row are eligible (inherits from
   `find_row_hspacing_issues` detection threshold).
