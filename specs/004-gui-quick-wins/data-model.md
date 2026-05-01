# Phase 1 — Data Model

Date: 2026-05-01
Spec: [spec.md](spec.md) | Research: [research.md](research.md)

This feature introduces **two** new domain entities (`DuplicateLayer`,
`SeverityBand`) and **three** new UI-state entities (`TabState`,
`RecentsStore`, `ContextMenuAction`). All are stdlib dataclasses or
plain values — no ORM, no third-party validation framework.

---

## Domain Entities

### `DuplicateLayer` (new — `pbir_validator/models.py`)

Frozen dataclass emitted by `analyzer.group_into_rows()` when two or
more visuals of the **same type** share a row-y bucket within tolerance.

| Field | Type | Notes |
|---|---|---|
| `page` | `str` | Page display name (matches existing models). |
| `visual_type` | `str` | e.g. `"pivotTable"`, `"card"`. |
| `visual_a_id` | `str` | First visual's id (lower y or stable sort). |
| `visual_a_title` | `str` | Display title (`""` if none). |
| `visual_b_id` | `str` | Second visual's id. |
| `visual_b_title` | `str` | Display title. |
| `delta_y_px` | `float` | Absolute y-coordinate difference in pixels. |

Validation rules:

- `visual_a_id != visual_b_id` (no self-pair).
- `delta_y_px >= 0`.
- For N visuals at the same y, emit `N choose 2` pairs.

Frozen + slots, like existing `Violation` and `Misalignment`.

### `SeverityBand` (new — `pbir_validator/gui/severity.py`)

Not a dataclass — three string constants used as Treeview tag names:

```python
SEV_GREEN = "sev_green"
SEV_YELLOW = "sev_yellow"
SEV_RED = "sev_red"
```

Plus pure function `band(value: float, *, kind: str) -> str` where
`kind ∈ {"deviation", "overlap"}`. Returns one of the three constants
per thresholds in research D5.

---

## UI State Entities

### `TabState` (new — `pbir_validator/gui/controllers.py`)

Holds per-tab view state. One instance per result tab (5 tabs total
that get sort+filter; Fix Plan tab is excluded).

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | `str` | required | e.g. `"Gap Violations"`. |
| `columns` | `tuple[str, ...]` | required | Column header labels. |
| `numeric_columns` | `frozenset[int]` | `frozenset()` | Indices that sort numerically. |
| `rows` | `list[tuple[str, ...]]` | `[]` | Source rows (immutable cells). |
| `sort` | `tuple[int, bool] \| None` | `None` | (col_index, descending). |
| `filter_text` | `str` | `""` | Lower-cased substring. |

Pure function `visible_rows(state: TabState) -> list[tuple[str, ...]]`
returns `sort(filter(state.rows))` without mutating state.

State transitions:

- `set_rows(rows)` — replaces `rows`, clears `filter_text`, leaves `sort`.
- `set_filter(text)` — sets `filter_text` (lower-cased).
- `toggle_sort(col)` — cycles None → asc → desc → asc → ...

### `RecentsStore` (new — `pbir_validator/gui/recents.py`)

Stateless module with three functions (no class needed):

| Function | Signature | Behavior |
|---|---|---|
| `recents_path()` | `() -> pathlib.Path` | Returns OS-appropriate path; ensures parent dir exists. |
| `load()` | `() -> list[str]` | Returns up-to-5 paths; `[]` on any read/parse failure. |
| `record(path)` | `(str) -> list[str]` | De-dup + MRU-push + truncate(5) + persist; returns new list. |

JSON schema enforced: `{"recent": [str, ...]}`. Foreign keys: none.
See `contracts/recents-schema.json`.

### `ContextMenuAction` (new — `pbir_validator/gui/controllers.py`)

Not a class — small helpers:

```python
def open_in_power_bi(report_root: Path) -> tuple[bool, str]:
    """Returns (ok, message). Calls os.startfile(report_root/'definition.pbir')."""

def row_to_clipboard_text(cells: tuple[str, ...]) -> str:
    """Returns tab-separated string."""
```

---

## Existing Entities — Modifications

### `analyzer` module

Add field/return: `group_into_rows()` now returns
`tuple[list[Row], list[DuplicateLayer]]` instead of `list[Row]`.
Existing call sites updated to destructure.

### `controllers.ValidateResult`

Add field:

| Field | Type | Default |
|---|---|---|
| `duplicate_layers` | `list[DuplicateLayer]` | `[]` |

Frozen dataclass; default via `field(default_factory=list)` keeps
existing call sites compatible.

### Coverage configuration

`pyproject.toml` `[tool.coverage.run] omit` list **adds**:
nothing. Both `recents.py` and `severity.py` are pure-Python helpers
that should count toward the gate.

---

## Entity Relationship Summary

```text
                           ┌──────────────────────┐
                           │   ValidateResult     │
                           │  (existing, +1 field)│
                           └──────────┬───────────┘
                                      │ 1..*
                                      ▼
        ┌─────────────┬──────────────┬─────────────┬─────────────────┐
        │             │              │             │                 │
        ▼             ▼              ▼             ▼                 ▼
   Violation     Overlap     DuplicateLayer    Misalignment    HSpacingIssue
   (existing)   (existing)      (NEW)          (existing)        (existing)
        │             │              │             │                 │
        └─────────────┴──────────────┴─────────────┴─────────────────┘
                                      │
                                      │ rendered as rows
                                      ▼
                              TabState (NEW)
                              ├── rows
                              ├── sort
                              └── filter_text

   (independent of validate flow)
   RecentsStore (NEW)  ──────────► recents.json on disk
```
