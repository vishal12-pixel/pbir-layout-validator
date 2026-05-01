# Contract: GUI User Flows

**Feature**: 002-tkinter-gui
**Date**: 2026-05-01

This contract specifies the user-visible state machines for each of the three primary actions. Each flow is presented as a state diagram followed by the transition table that implementations MUST honor. These flows are the testable surface for SC-001, SC-005, SC-006, and FR-019.

Common notation:
- `Idle` — no worker thread running; action buttons enabled (subject to "valid report selected" gate from FR-005); main loop free.
- `Working` — worker thread alive; all three action buttons disabled; progress indicator visible (FR-023).
- `ResultsRendered` — worker finished, queue drained, the corresponding tab populated; main loop free.

---

## 1. Validate flow

**Trigger**: User clicks **Validate** while a valid report is selected.

```text
        ┌──────┐  click Validate    ┌─────────┐  worker emits results   ┌──────────────────┐
   ───▶ │ Idle │ ─────────────────▶ │ Working │ ──────────────────────▶ │ ResultsRendered │
        └──────┘                    └─────────┘                         └──────────────────┘
            ▲                            │                                       │
            │                            │ worker raises exception               │ click Validate again
            │                            ▼                                       │
            │                       ┌──────────┐                                 │
            └───────────────────────│  Error   │ ◀───────────────────────────────┘
                                    └──────────┘
```

| From            | Event                                  | Guard                             | To              | Side effects                                                        |
|-----------------|----------------------------------------|-----------------------------------|-----------------|---------------------------------------------------------------------|
| Idle            | click **Validate**                     | report selected and valid (FR-004)| Working         | disable all three action buttons; show progress indicator           |
| Idle            | click **Validate**                     | no/invalid report                 | Idle            | show error message inside window (FR-001 of validate scenarios)     |
| Working         | worker emits `ValidateResult`          | —                                 | ResultsRendered | populate Gap Violations, Row Misalignments, H-Spacing tabs; switch focus to Gap Violations; re-enable buttons |
| Working         | worker raises exception                | —                                 | Error           | show readable error in window (FR-024); re-enable buttons; switch focus to the tab the user was on |
| ResultsRendered | click **Validate** again               | report still valid                | Working         | clear the three Validate tabs' contents; same as initial transition |
| Error           | click **Validate** (or Learn / Fix)    | —                                 | Working         | dismiss error indicator; same as initial transition                 |

**Read-only invariant**: Validate MUST NOT write to disk in any state (FR-014). Worker thread is only allowed to call `analyzer.*` and `validator.*`; `writer.*` and `fixer.apply()` MUST NOT be reachable from the Validate code path.

---

## 2. Learn flow

**Trigger**: User clicks **Learn** while a valid report is selected.

```text
                                                                 ┌─────────┐
   ┌──────┐  click Learn  ┌────────────────────┐  Yes + exists   │ Editor  │  user closes editor
   │ Idle │ ───────────▶ │ AwaitingUserAnswer │ ──────────────▶ │ Opened  │ ───────────────────▶ Idle
   └──────┘               └────────────────────┘                 └─────────┘
                              │   │                              (no Tk-side state change;
                              │   │ Yes + missing                 user is "external")
                              │   ▼
                              │  ┌──────────────────────┐
                              │  │ ShowMissingConfMsg   │ ──────────────────▶ Idle
                              │  └──────────────────────┘
                              │ No
                              ▼
                       ┌─────────────────────┐  user picks page    ┌─────────┐  worker writes conf.md   ┌──────────────────┐
                       │ ShowingPageDropdown │ ──────────────────▶ │ Working │ ──────────────────────▶ │ ResultsRendered │ ──▶ Idle
                       └─────────────────────┘                     └─────────┘                         └──────────────────┘
                                                                                  │                                  
                                                                                  │ worker raises                    
                                                                                  ▼                                  
                                                                              ┌──────┐                               
                                                                              │ Error │                              
                                                                              └──────┘                               
```

| From                  | Event                              | Guard                                 | To                    | Side effects                                                         |
|-----------------------|------------------------------------|---------------------------------------|-----------------------|----------------------------------------------------------------------|
| Idle                  | click **Learn**                    | report valid                          | AwaitingUserAnswer    | show yes/no `messagebox` per FR-007                                  |
| AwaitingUserAnswer    | user answers **Yes**               | `conf.md` exists                      | EditorOpened          | call `open_in_default_editor(conf_path)` (FR-008); GUI returns to Idle as soon as the call returns (the editor itself runs out-of-process) |
| AwaitingUserAnswer    | user answers **Yes**               | `conf.md` missing                     | ShowMissingConfMsg    | show in-window message per FR-009; transition immediately to Idle    |
| AwaitingUserAnswer    | user answers **No**                | —                                     | ShowingPageDropdown   | render page dropdown via `analyzer.list_pages()`; show Confirm button (FR-010) |
| ShowingPageDropdown   | click **Confirm** with page picked | —                                     | Working               | disable action buttons; spawn worker that calls `learner.learn(report, page)` |
| Working               | worker emits `LearnResult.success` | —                                     | ResultsRendered       | show success message naming the file written (FR-011); re-enable buttons |
| Working               | worker raises exception            | —                                     | Error                 | show readable error per FR-024; re-enable buttons                    |
| EditorOpened          | (out-of-process)                   | —                                     | Idle                  | none                                                                 |

**Stale-conf invariant**: When a Validate or Fix is subsequently triggered, controllers MUST re-read `conf.md` from disk rather than caching the in-memory copy from any prior run (Edge case "External edit during session" in spec). Implementation: `LearnController.read_conf` MUST NOT memoize; it returns a fresh `conf.Conf` per call.

---

## 3. Fix flow

**Trigger**: User clicks **Fix** while a valid report is selected.

```text
   ┌──────┐  click Fix    ┌─────────┐  worker emits dry-run plan   ┌─────────────────┐
   │ Idle │ ───────────▶ │ Working │ ──────────────────────────▶ │ AwaitingApply   │
   └──────┘               └─────────┘                             └─────────────────┘
                                                                      │       │
                                                            no shifts │       │ click Apply selected fixes (≥1 checked)
                                                                      ▼       ▼
                                                           ┌─────────────┐  ┌─────────┐  worker writes shifts   ┌─────────┐  auto-rerun Validate
                                                           │ NoFixesNeeded│  │ Working │ ──────────────────────▶ │ Applied │ ────────────────────▶ AutoValidating
                                                           └─────────────┘  └─────────┘                          └─────────┘
                                                                                                                           │
                                                                                                                           │ Validate worker emits results
                                                                                                                           ▼
                                                                                                                  ┌──────────────────┐
                                                                                                                  │ ResultsRendered │ ──▶ Idle
                                                                                                                  └──────────────────┘
```

| From            | Event                                 | Guard                                       | To              | Side effects                                                                                  |
|-----------------|---------------------------------------|---------------------------------------------|-----------------|-----------------------------------------------------------------------------------------------|
| Idle            | click **Fix**                         | report valid                                | Working         | disable action buttons; worker calls `fixer.dry_run(report)` (FR-015)                         |
| Working         | worker emits dry-run with ≥1 shift    | —                                           | AwaitingApply   | populate Fix Plan tab as `ShiftChecklist` with all rows pre-checked (FR-016); enable **Apply selected fixes** |
| Working         | worker emits dry-run with 0 shifts    | —                                           | NoFixesNeeded   | Fix Plan tab shows "No fixes needed"; **Apply selected fixes** disabled (FR-020)              |
| Working         | worker raises exception               | —                                           | Error           | show readable error; re-enable action buttons                                                  |
| AwaitingApply   | user toggles a checkbox               | —                                           | AwaitingApply   | the affected `ShiftCheckboxRow.checked.set(...)` mutates; **Apply** stays enabled while ≥1 row is still checked (FR-017) |
| AwaitingApply   | click **Apply selected fixes**        | ≥1 row checked                              | Working         | disable action buttons; worker calls `fixer.apply(selected_shifts)` (FR-018)                  |
| AwaitingApply   | click **Apply selected fixes**        | 0 rows checked                              | AwaitingApply   | show "no shifts selected" notice; do NOT call fixer (FR-018 negative case in scenarios)        |
| Working (apply) | worker reports apply success          | —                                           | Applied         | record `(applied=N, skipped=M)`; immediately transition to AutoValidating                      |
| Applied         | (immediate)                           | —                                           | AutoValidating  | spawn a Validate worker (FR-019); buttons remain disabled                                      |
| AutoValidating  | Validate worker emits results         | —                                           | ResultsRendered | refresh Gap Violations / Row Misalignments / H-Spacing tabs; Fix Plan tab shows summary line `"X applied, Y skipped, Z remaining (re-run Fix)"`; invalidate the old `ShiftCheckboxRow` list (FR-019); re-enable buttons; transition to Idle |
| AutoValidating  | Validate worker raises exception      | —                                           | Error           | show error; tabs are NOT refreshed; the Fix succeeded but auto-revalidate failed — message must say so (per FR-024) |
| NoFixesNeeded   | click **Fix** again                   | —                                           | Working         | same as initial Fix transition                                                                 |

**Mutation invariant**: Only the path `AwaitingApply --click Apply--> Working --apply success--> Applied` is allowed to write to disk. Every other Fix-path state MUST be read-only (FR-015).

**Single-apply invariant**: Once a `ShiftChecklist` is in the `Applied` state, its `ShiftCheckboxRow` instances MUST be discarded and the user MUST click **Fix** again to obtain a fresh dry-run before any further Apply (FR-019 last sentence).

---

## Cross-cutting contracts

### Threading
- All `Working` states are entered by spawning **one** background `threading.Thread`. The Tk thread polls the worker's `queue.Queue` via `root.after(50, drain)` until the worker emits a terminal message (`*Result.success` or `*Result.error`). No state outside `Working` may have a worker thread alive.

### Button gating
The three primary action buttons (Learn / Validate / Fix) and the secondary **Apply selected fixes** button follow a single rule: **disabled iff** any of:
- a worker thread is alive (states `Working`, `AutoValidating`),
- no valid report is selected (FR-005),
- the button is **Apply selected fixes** AND zero rows are checked (FR-018, FR-020).

### Per-tab Export
The **Export…** button on each result tab is **enabled iff** that tab's `ResultTableModel.rows` is non-empty (FR-013a). Clicking it opens `tk.filedialog.asksaveasfilename` with `filetypes=[("CSV", "*.csv"), ("JSON", "*.json")]` and a default extension of `.csv`. The export runs **synchronously on the Tk thread** because writing a few hundred rows is sub-millisecond and a worker thread would add complexity for no measurable benefit.

### Error messaging
Every transition into the `Error` pseudo-state MUST surface the error via either `messagebox.showerror` (for blocking errors that need acknowledgement) or an inline label inside the affected tab (for advisory errors that don't block the user). Raw Python tracebacks are NEVER the only feedback (FR-024, SC-007).

---

## Test surface

These flows are tested at three levels:

1. **`tests/gui/test_controllers.py`** — controllers are exercised without Tk; transitions Idle → Working → ResultsRendered are verified by feeding fake `Path`s through `LearnController` / `ValidateController` / `FixController` and asserting on the result objects.
2. **`tests/gui/test_workers.py`** — the `run_in_background` helper is exercised by enqueuing synthetic messages and asserting `root.after`-style callbacks fire in order. A real `Tk()` is created with `withdraw()` so no window is shown.
3. **`tests/gui/test_app_smoke.py`** — full GUI smoke test that constructs the main window, programmatically clicks each button via `widget.invoke()`, and asserts the resulting tab contents match what `ValidateController` would produce for the same fixture report. Skipped on CI runners with no display.
