# Phase 1 Data Model

All entities are implemented as **frozen `@dataclass`** types in `pbir_validator/models.py`.
Frozen because every value object is read-only after construction; mutation happens only
through builder functions in `fixer.py` that return new instances.

## Entity: `Report`

Represents the top-level `.Report` folder loaded by the tool.

| Field | Type | Notes |
|---|---|---|
| `root` | `pathlib.Path` | Absolute path to the `.Report` folder. |
| `pages_dir` | `pathlib.Path` | `root / "definition" / "pages"`. Validated to exist at load. |

**Invariants**

- `pages_dir.is_dir()` MUST be true; otherwise `reader.load_report` raises `NotAPbirError`.
- `Report` does NOT eagerly hold a list of pages. Pages are produced by
  `reader.iter_pages(report)` as a generator (Principle IV).

## Entity: `Page`

A single page subdirectory under `definition/pages/<page-id>/`.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Folder name (e.g., `ReportSection1a2b3c`). |
| `display_name` | `str` | From `page.json` `displayName`. Used in user-facing tables. |
| `height` | `float` | From `page.json` `height`. Used for boundary checks. |
| `width` | `float` | From `page.json` `width`. Stored for completeness. |
| `path` | `pathlib.Path` | Absolute path to the page folder. |
| `visuals_dir` | `pathlib.Path` | `path / "visuals"`. May not exist (zero-visual page). |

**Methods (module-level functions)**

- `reader.iter_visuals(page) -> Iterator[Visual]` — yields each `Visual` lazily;
  malformed `visual.json` files are skipped with a warning (spec edge case).

**Invariants**

- `display_name` is non-empty; if absent, fall back to `id` and warn.

## Entity: `Visual`

A single `visual.json` file under `<page>/visuals/<visual-id>/`.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Folder name. |
| `page_id` | `str` | Parent page id (for error messages). |
| `visual_type` | `str` | From `visual.visualType`. `"unknown"` when missing. |
| `x` | `float` | From `position.x`. |
| `y` | `float` | From `position.y`. |
| `width` | `float` | From `position.width`. |
| `height` | `float` | From `position.height`. |
| `parent_group_name` | `str \| None` | From `parentGroupName` if present. |
| `path` | `pathlib.Path` | Absolute path to the `visual.json` file. |
| `raw` | `dict[str, Any]` | The full parsed JSON, preserved verbatim for round-trip writes. |
| `indent` | `int` | Detected indentation width for round-trip writes (default 2). |

**Validation** (in `reader.parse_visual`)

- `position` object MUST be present and contain numeric `x`, `y`, `width`, `height`.
- Missing `visual.visualType` → set to `"unknown"` and emit a UI warning. Per spec edge case
  the visual is still included in row analysis.
- Malformed JSON → log path and skip (do not raise to caller).

## Entity: `Row`

A derived grouping of visuals on a single page whose Y coordinates are within tolerance.

| Field | Type | Notes |
|---|---|---|
| `page_id` | `str` | Owning page. |
| `y_min` | `float` | Minimum `y` among the row's visuals. |
| `y_max` | `float` | Maximum `y` among the row's visuals (within `±ROW_TOLERANCE_PX` of `y_min`). |
| `bottom` | `float` | `max(v.y + v.height for v in visuals)`. Used for gap calculation. |
| `representative_type` | `str` | Deterministic single label (most-frequent, ties → lexicographic). |
| `visuals` | `tuple[Visual, ...]` | Members of the row. Order: ascending `x`. |
| `is_mixed` | `bool` | `True` if the row contains >1 distinct `visual_type`. |

**Construction** (in `analyzer.group_into_rows`)

- Input: iterable of `Visual` for one page.
- Sort by `y` ascending. Greedy bucket: visual joins the current row if
  `abs(v.y - current_row.y_min) <= ROW_TOLERANCE_PX`; otherwise start a new row.
- Output rows are sorted by `y_min` ascending.

## Entity: `GapRule`

One spacing rule from `conf.md`.

| Field | Type | Notes |
|---|---|---|
| `from_type` | `str` | Visual type of the upper row. |
| `to_type` | `str` | Visual type of the lower row. |
| `gap_px` | `int` | Required vertical gap in pixels. |

**Equality / hashing**: keyed on `(from_type, to_type)` only.

**Source**: produced by `conf.parse_conf(path) -> dict[tuple[str, str], GapRule]` and
consumed by `validator` and `fixer`.

## Entity: `Violation`

A computed mismatch between an actual gap and the rule for the involved type pair.

| Field | Type | Notes |
|---|---|---|
| `page_id` | `str` | |
| `page_display_name` | `str` | For tabular output. |
| `from_type` | `str` | |
| `to_type` | `str` | |
| `expected_px` | `int` | From the matching `GapRule`. |
| `actual_px` | `float` | Computed `next_row.y_min - current_row.bottom`. |
| `deviation_px` | `float` | `actual_px - expected_px` (signed). |
| `from_row_index` | `int` | Index of the upper row on the page. |
| `to_row_index` | `int` | `from_row_index + 1`. |
| `unfixable_reason` | `str \| None` | Set by `fixer` when a planned shift would exceed page bounds. |

**Lifecycle**

1. `validator.validate_report(report, rules)` returns `list[Violation]` with
   `unfixable_reason=None`.
2. `fixer.plan_fixes(violations, ...)` may set `unfixable_reason` when the shift would
   push the row past page height.

## Entity: `UnknownPair` (warning, not violation)

Reported separately so it does not affect the validate exit code.

| Field | Type | Notes |
|---|---|---|
| `page_id` | `str` | |
| `from_type` | `str` | |
| `to_type` | `str` | |
| `actual_px` | `float` | Recorded for the developer's reference. |

## Entity: `Shift` (fix-mode plan record)

| Field | Type | Notes |
|---|---|---|
| `visual_id` | `str` | |
| `page_id` | `str` | |
| `path` | `pathlib.Path` | `visual.json` path. |
| `old_y` | `float` | |
| `new_y` | `float` | |
| `delta_y` | `float` | `new_y - old_y`. |
| `group_member` | `bool` | `True` if shifted because a sibling group member is being shifted. |

`fixer.plan_fixes(...)` returns `list[Shift]`; in dry-run, this is printed and no file is
touched. In apply mode, `writer.write_shifts(shifts)` performs atomic per-file writes.

## Relationships

```text
Report (1) ──< Page (N) ──< Visual (N)
                Page    ──> Row (N, derived)        ──< Visual (N, by membership)
                Row[i]  ──> gap with Row[i+1]       ──> Violation (when gap ≠ rule)
GapRule (N, from conf.md) ──> matches (from_type, to_type) of an adjacent row pair
Violation ──> Shift (N) when fix mode plans correction
            ──> at least one shift on the lower row; may include sibling rows below;
                may include group members via parent_group_name
```

## State Transitions

The only mutable state is **on disk**; in-memory dataclasses are frozen.

```text
visual.json (on disk):  original  ──[fixer.apply]──>  same JSON, only position.y changed
                                                     (atomic via tempfile + os.replace)
conf.md   (on disk):    absent    ──[learner.write]─> rules file
                        existing  ──[learner.write]─> overwritten (after confirmation)
```

No other files are ever created, deleted, or renamed by the tool.
