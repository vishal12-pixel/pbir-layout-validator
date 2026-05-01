# Phase 1 Data Model: Tkinter Desktop GUI

**Feature**: 002-tkinter-gui
**Date**: 2026-05-01
**Status**: Complete

## Scope

This feature **introduces no new domain entities**. All domain types (`Report`, `Page`, `Visual`, `Row`, `GapRule`, `Violation`, `UnknownPair`, `Misalignment`, `HSpacingIssue`, `Shift`) are already defined in [`pbir_validator/models.py`](../../pbir_validator/models.py) and documented in [specs/001-pbir-layout-validator/data-model.md](../001-pbir-layout-validator/data-model.md). The GUI consumes them read-only.

What this document captures is the **GUI-local view-state types** — small, presentation-only structures that wrap the existing entities with the extra UI-only fields (a "checked" boolean, a list of column header strings, etc.) that don't belong on the domain models.

These types live in `pbir_validator/gui/widgets.py` (where the widgets that consume them live). They are **not exported** from the package's public `__init__.py` and are not part of any contract a CLI user could depend on.

---

## View-state types

### `ShiftCheckboxRow`

One row in the Fix dry-run checklist (FR-016, FR-017).

**Fields**:

| Field      | Type                       | Source                              | Mutable? |
|------------|----------------------------|-------------------------------------|----------|
| `shift`    | `pbir_validator.models.Shift` | Fixer dry-run output                | No (frozen dataclass) |
| `checked`  | `tkinter.BooleanVar`       | Initialized to `True` per FR-016    | Yes — toggled by user clicking the `ttk.Checkbutton` |
| `display_label` | `str`                 | Derived once at construction: `f"{shift.page_name} / {shift.visual_id}: dy={shift.delta_y}"` | No |

**Lifecycle**:
1. `FixController.dry_run()` returns `list[Shift]`.
2. The Fix Plan tab maps each `Shift` to one `ShiftCheckboxRow` with `checked = BooleanVar(value=True)`.
3. On **Apply selected fixes**, `FixController.apply([row.shift for row in rows if row.checked.get()])` is called.
4. After Apply, the entire `list[ShiftCheckboxRow]` is discarded (FR-019: "the original checklist rows MUST be invalidated").

**Validation rules**: None at the view layer — `Shift` itself is already validated upstream by `fixer.py`.

---

### `ResultTableModel`

Backing data for one `ttk.Treeview`-based `ResultTable` widget (one per result tab: Gap Violations, Row Misalignments, Horizontal Spacing, Fix Plan).

**Fields**:

| Field     | Type                  | Description                                                                |
|-----------|-----------------------|----------------------------------------------------------------------------|
| `headers` | `tuple[str, ...]`     | Column headers, e.g. `("Page", "Visual A", "Visual B", "Expected", "Actual")` |
| `rows`    | `list[tuple[str, ...]]` | One tuple per finding, in the same column order as `headers`.            |
| `empty_message` | `str`           | Shown when `rows` is empty (FR-013), e.g. `"No issues found"` or `"No fixes needed"`. |

**Construction**: One factory function per finding type lives on the corresponding controller:

```python
# in pbir_validator/gui/controllers.py (signatures only — implementation deferred to /speckit.tasks)
def gap_violations_to_table(violations: Iterable[Violation]) -> ResultTableModel: ...
def misalignments_to_table(misalignments: Iterable[Misalignment]) -> ResultTableModel: ...
def hspacing_issues_to_table(issues: Iterable[HSpacingIssue]) -> ResultTableModel: ...
def shifts_to_fix_plan_table(shifts: Iterable[Shift]) -> ResultTableModel: ...
```

These factories are pure functions over the existing domain models — they're the **unit-test surface** for "GUI shows the same data the CLI prints" (SC-002, SC-003).

**Lifecycle**:
- Built once per Validate/Fix run on the worker thread.
- Pushed through the `queue.Queue` to the UI thread.
- The Tk thread calls `result_table.set_model(model)` which clears the `Treeview` and re-inserts rows.
- Lives until the next run for that tab (so users can cross-reference Gap vs. Misalignment after running Validate, per FR-012).

**Validation rules**:
- `len(headers) == len(row)` for every `row in rows` (asserted at construction; bug if violated).
- `headers` MUST match the column set the CLI prints for that finding type (SC-002).

**Export**: `pbir_validator.gui.export.to_csv(model, file)` and `to_json(model, file)` consume a `ResultTableModel` directly — no per-tab special-casing (FR-013a).

---

## Relationship to existing 001 entities

```text
┌────────────────────────────────────────────────────────────────────┐
│  pbir_validator.models  (existing — unchanged)                     │
│    Report, Page, Visual, Row, GapRule, Violation, UnknownPair,     │
│    Misalignment, HSpacingIssue, Shift                              │
└──────────────┬─────────────────────────────────────────────────────┘
               │ consumed read-only by
               ▼
┌────────────────────────────────────────────────────────────────────┐
│  pbir_validator.gui.controllers  (new)                             │
│    LearnController, ValidateController, FixController              │
│    + table-factory functions that produce ResultTableModel         │
└──────────────┬─────────────────────────────────────────────────────┘
               │ produces
               ▼
┌────────────────────────────────────────────────────────────────────┐
│  pbir_validator.gui.widgets  (new — view-state)                    │
│    ResultTableModel, ShiftCheckboxRow                              │
└────────────────────────────────────────────────────────────────────┘
```

Domain entities flow strictly outward. View-state types are never persisted to disk and never re-enter the domain layer.

---

## State transitions

The only stateful types are `ShiftCheckboxRow.checked` (a `BooleanVar` the user toggles) and `ResultTableModel` (replaced wholesale on each run). There are no multi-step state machines at the data-model layer; user-facing state machines are documented in [contracts/gui-flows.md](contracts/gui-flows.md).

---

## Summary

- **Zero** new domain entities.
- **Two** GUI-local view-state types (`ShiftCheckboxRow`, `ResultTableModel`), both presentation-only and not exported.
- **Four** factory functions that turn existing domain iterables into `ResultTableModel` instances — these are the seam where the GUI proves it shows the same data the CLI prints (SC-002, SC-003).
