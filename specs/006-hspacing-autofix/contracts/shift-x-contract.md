# Contract: X-Shift Planning & Application

## C1 — `plan_hspacing_fixes()` Function Contract

```python
def plan_hspacing_fixes(
    report: Report,
    pages_by_id: dict[str, Page],
    visuals_by_page: dict[str, list[Visual]],
    hspacing_issues: list[HSpacingIssue],
) -> tuple[list[Shift], list[HSpacingIssue]]:
```

**Inputs**:
- `report`: the loaded report object.
- `pages_by_id`: pre-built page lookup (shared with Y-shift planning).
- `visuals_by_page`: pre-built visual lists per page (shared with Y-shift planning).
- `hspacing_issues`: output from `validate_report()` — the h-spacing issues
  detected by `find_row_hspacing_issues`.

**Outputs**:
- `shifts`: list of `Shift` objects with `old_x`, `new_x`, `delta_x` populated.
  `old_y == new_y == visual.y` and `delta_y == 0` for pure X-shifts.
- `unfixable_issues`: `HSpacingIssue` objects that failed boundary checks, each
  annotated (via a wrapper or separate tracking) with a reason string.

**Behavior**:
1. Groups `hspacing_issues` by `(page_id, row_index, visual_type)`.
2. For each group, reconstructs the sorted peer list and gap sequence.
3. Walks gaps left-to-right; for each deviant gap, computes
   `correction = -(actual_gap - modal_gap)` and applies it cumulatively to
   all peers to the right.
4. After all corrections, boundary-checks every affected visual:
   - `new_x < 0` → mark group unfixable.
   - `new_x + width > page.width` → mark group unfixable.
5. Emits `Shift` objects for all visuals with non-zero `delta_x`.

**Invariants**:
- No cascading across rows or pages.
- Visuals not in the affected type-bucket are never shifted.
- When a group is unfixable, zero shifts are emitted for that group.

---

## C2 — `write_visual_json()` Extended Signature

```python
def write_visual_json(
    visual: Visual,
    new_y: float,
    *,
    new_x: float | None = None,
) -> None:
```

**Behavior when `new_x is not None`**:
- Mutate `position.x` in addition to `position.y`.
- Preserve int-ness: if `float(new_x).is_integer()`, write `int(new_x)`.
- Single atomic write (tempfile + `os.replace`).
- Key order, indentation, trailing newline preserved (FR-014, FR-015).

**Behavior when `new_x is None`** (default):
- Identical to current behavior — only `position.y` is mutated.

---

## C3 — Undo Backup Extended Schema

```json
{
  "applied_at": "2026-05-02T14:30:00Z",
  "shifts": [
    {
      "path": "definition/pages/abc/visuals/v1/visual.json",
      "visual_id": "v1",
      "old_y": 100.0,
      "new_y": 100.0,
      "old_x": 200.0,
      "new_x": 198.0
    },
    {
      "path": "definition/pages/abc/visuals/v2/visual.json",
      "visual_id": "v2",
      "old_y": 50.0,
      "new_y": 58.0
    }
  ]
}
```

**Rules**:
- `old_x` and `new_x` are OPTIONAL. Omitted for Y-only shifts.
- `record_pre_fix()` writes `old_x`/`new_x` when `shift.old_x is not None`.
- `restore_last_fix()` passes `old_x` as `new_x=` kwarg to `write_visual_json()`
  when the backup entry contains `old_x`. When absent, restores Y only.

---

## C4 — GUI Fix Plan Tab X-Shift Row Format

X-shift rows in the Fix Plan tab use a distinct action label so users can
differentiate Y-shifts from X-shifts at a glance.

| Column | Y-shift row | X-shift row |
|--------|-------------|-------------|
| `action` | `"shift-y"` | `"shift-x"` |
| `page_id` | page ID | page ID |
| `visual_id` | visual ID | visual ID |
| `old_value` | `old_y` | `old_x` |
| `new_value` | `new_y` | `new_x` |
| `delta` | `delta_y` | `delta_x` |

**Implementation**: `fix_plan_rows()` in `controllers.py` emits both
Y-shift and X-shift rows from the same `FixPlan.shifts` list. A `Shift`
with `delta_x != None and delta_x != 0` produces an X-shift row. A shift
may produce both a Y-shift and X-shift row if both coordinates changed.

---

## C5 — CLI Fix Summary X-Shift Format

The `print_shift_plan()` function in `ui.py` adds an "Action" column to
distinguish Y-shifts from X-shifts:

```
Action   Page    Visual   Old     New     Delta   Note
shift-y  page1   v1       100     108     +8
shift-x  page1   v2       200     198     -2
shift-x  page1   v3       420     418     -2
```

---

## C6 — Profile `hspacing_fix` Flag Parsing

Profile `.md` files may contain a metadata flag in their header comments:

```markdown
# hspacing_fix = true
```

**Parsing** (in `profiles.py` or a shared utility):
- Scan all comment lines (starting with `#`) for the pattern:
  `hspacing_fix\s*=\s*(true|false)` (case-insensitive).
- Return `True` if matched with value `true`, `False` otherwise.
- Default to `False` when the flag is absent.

**Profile defaults**:
- `strict.md`: `hspacing_fix = true`
- `standard.md`: absent (defaults to `false`)
- `relaxed.md`: absent (defaults to `false`)
- Report-default (`conf.md`): user may add `# hspacing_fix = true` to opt in.
