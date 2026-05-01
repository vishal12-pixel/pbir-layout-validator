# Phase 0 Research: Tkinter Desktop GUI

**Feature**: 002-tkinter-gui
**Date**: 2026-05-01
**Status**: Complete — all `NEEDS CLARIFICATION` markers from the spec have been resolved (5 questions answered in [spec.md § Clarifications](spec.md#clarifications)).

This document records the technology and structural decisions taken before implementation. Each entry follows the **Decision / Rationale / Alternatives considered** template.

---

## 1. UI toolkit

**Decision**: Use **Tkinter + ttk** (Python standard library) with no third-party widget toolkit.

**Rationale**:
- Constitution Principle I forbids new runtime dependencies; FR-021 restates this for the GUI.
- `tkinter` ships with CPython on Windows, macOS, and Linux distributions Python is officially packaged for, so `pip install pbir_validator` continues to work with zero extra wheels.
- `ttk.Notebook`, `ttk.Treeview`, and `ttk.Checkbutton` cover every widget the spec calls for (tabs, scrollable result tables, per-shift checkboxes).
- Honors system theme out of the box (relevant for SC-007 / dark-mode legibility).

**Alternatives considered**:
- **PySide6 / PyQt** — richer widgets but adds a ~50 MB Qt runtime dependency; rejected on Principle I.
- **Textual / Rich (TUI)** — stdlib-friendly but the spec asks for a *desktop* GUI with file dialogs and OS-native editor handoff; a TUI would not satisfy FR-008 ("open in OS default editor").
- **wxPython** — third-party, not stdlib; rejected.

---

## 2. Threading model

**Decision**: One **background `threading.Thread`** per action (Learn / Validate / Fix). Worker pushes structured result messages into a `queue.Queue`. The Tk main loop drains the queue via `root.after(50, drain)` and dispatches to UI updaters on the main thread. No locks, because analyzer/validator/fixer modules already operate on frozen dataclasses with no shared mutable state.

**Rationale**:
- Tk is not thread-safe; touching widgets from any thread other than the one that called `mainloop()` causes intermittent crashes. `queue.Queue` + `root.after()` is the canonical Python recipe.
- FR-023 explicitly mandates this pattern.
- Matches constitution Principle IV ("lazy iteration"): the worker can stream `Violation`/`Misalignment` results into the queue as they're produced rather than waiting for the full set.
- Buttons disabled while a worker is running guarantees at most one in-flight action per controller, eliminating cancellation/race-condition complexity.

**Alternatives considered**:
- **`asyncio` + `asyncio-tkinter` bridge** — overkill for at-most-one in-flight task; introduces an event-loop integration layer and is harder to test.
- **`multiprocessing`** — needed only if we wanted to bypass the GIL, but our work is I/O-bound (file reads) plus modest JSON parsing; the GIL is not the bottleneck. Rejected for added IPC complexity.
- **Synchronous calls on the Tk thread** — would freeze the UI on large reports, violating FR-023 and SC-006. Rejected.

---

## 3. Headless / no-display detection

**Decision**: At GUI startup (`pbir_validator.gui.app.main`), wrap the very first `tk.Tk()` call in `try / except tk.TclError`. On exception, print a single-line, ANSI-free message (`"pbir_validator-gui: no display available; use the CLI 'pbir_validator' instead."`) to `stderr` and exit with code 2.

**Rationale**:
- FR-025 mandates fast, friendly failure on headless boxes (CI containers, SSH sessions without X11 forwarding).
- `Tk()` raises `tk.TclError` ("no display name and no $DISPLAY environment variable") immediately on Linux when there's no display server; on Windows the call works on any session that can show a window. This single-point check covers all real-world headless cases without adding platform-specific imports.
- Exit code 2 distinguishes "couldn't start UI" from a normal CLI error (1) so CI can branch on it if needed.

**Alternatives considered**:
- **Probe `os.environ.get("DISPLAY")` on Linux** — too narrow (misses Wayland's `WAYLAND_DISPLAY`, misses Windows-without-session edge cases) and Linux-specific.
- **Catch `tk.TclError` deep inside `mainloop()`** — too late; the user has already seen a partially-constructed window or a Tk error popup.

---

## 4. Opening `conf.md` in the OS default editor

**Decision**: A small stdlib helper `pbir_validator.gui.app.open_in_default_editor(path: pathlib.Path) -> None` dispatches per platform:

| Platform        | Call                                              |
|-----------------|---------------------------------------------------|
| Windows         | `os.startfile(str(path))`                         |
| macOS (`darwin`)| `subprocess.run(["open", str(path)], check=False)`|
| Linux / other   | `subprocess.run(["xdg-open", str(path)], check=False)` |

Detection uses `sys.platform` (returns `"win32"`, `"darwin"`, `"linux"`, etc.).

**Rationale**:
- Stdlib-only (`os`, `subprocess`, `sys`).
- These three commands are the documented, stable mechanisms each OS exposes for "open this file with whatever the user has registered for its extension".
- `check=False` is deliberate: if no editor is registered, we surface the failure as a friendly in-window message (FR-024) rather than crashing on `CalledProcessError`. The helper returns `None` and the caller checks the file's existence beforehand (FR-009).

**Alternatives considered**:
- **`webbrowser.open(path)`** — works for HTML and is sometimes hijacked for files, but for `.md` it routinely opens a browser instead of the user's chosen editor. Rejected.
- **A dedicated config-driven editor command** (`EDITOR` env var) — adds configuration surface the spec doesn't ask for. The OS-default behavior is what FR-008 requires.

---

## 5. GUI sub-package layout

**Decision**: Create a new sub-package `pbir_validator/gui/` with the following modules:

| Module             | Responsibility                                                                                       |
|--------------------|------------------------------------------------------------------------------------------------------|
| `__init__.py`      | Empty marker; documents that `gui` is opt-in and not imported by the CLI.                            |
| `app.py`           | `main()` entry point, `Tk()` bootstrap, headless detection, top-level layout, button wiring, `open_in_default_editor` helper. |
| `widgets.py`       | `ResultTable` (a thin wrapper around `ttk.Treeview` with scrollbars + "No issues found" empty state) and `ShiftChecklist` (scrollable frame of `ttk.Checkbutton` rows).      |
| `workers.py`       | `run_in_background(target, on_message, on_done)` — spawns the daemon thread and arranges the `queue.Queue` + `root.after()` drain loop.                                  |
| `controllers.py`   | `LearnController`, `ValidateController`, `FixController` — pure-Python orchestration of `reader`/`analyzer`/`validator`/`learner`/`fixer` calls. Receive a `Path`, return result objects. **No Tk imports here** — this is the unit-test surface. |
| `export.py`        | `to_csv(rows, headers, file)` and `to_json(rows, headers, file)` — given `ResultTable`'s in-memory rows, write them to disk via `csv.writer` / `json.dump`.                |

**Rationale**:
- **Separation of concerns**: `controllers.py` and `export.py` import nothing from `tkinter`, so they're trivially unit-testable in CI without a display (constitution Principle II).
- **One module per spec section**: matches the way the spec is structured (Learn / Validate / Fix / Export), making code review easier.
- **CLI insulation**: `pbir_validator/__init__.py`, `cli.py`, and `__main__.py` are not changed at all. Importing `pbir_validator` does NOT import `pbir_validator.gui`, so CLI startup time and import surface are unchanged (constitution Principle IV: cold-start budget).
- **Future-proof**: if a `pbir_validator-tui` or `pbir_validator-web` is ever added, the `controllers.py` layer is reusable verbatim.

**Alternatives considered**:
- **Single-file `gui.py`** — fine for a 100-line prototype but the spec mandates four tabs, three controllers, two export formats, threading plumbing, and a headless probe; one file would breach the 40-line-per-function guideline in the constitution. Rejected.
- **Top-level `pbir_validator_gui/` package** — duplicates packaging metadata and complicates relative imports of core modules. Rejected.
- **Inlining the GUI inside `cli.py`** — couples GUI concerns to the CLI's argparse layer and makes FR-022 (CLI must keep working unchanged if GUI is removed) harder to verify. Rejected.

---

## 6. Export format defaults

**Decision**: CSV is the **default** suggested format in the save-file dialog (`*.csv`); JSON is offered as an alternative (`*.json`). CSV writer uses `csv.writer` with `lineterminator='\n'` and `QUOTE_MINIMAL`. JSON output is a list of objects keyed by the same column headers shown in the table, written with `json.dump(..., indent=2, ensure_ascii=False)`.

**Rationale**:
- FR-013a explicitly names CSV as default ("opens in Excel directly") and JSON as the alternative.
- `csv` and `json` are stdlib.
- `lineterminator='\n'` keeps diffs clean across platforms; `QUOTE_MINIMAL` avoids over-quoting that confuses spreadsheet imports.
- JSON `indent=2` keeps exported files human-readable (this matches the existing `conf.md` ergonomic philosophy).

**Alternatives considered**:
- **TSV / Markdown table export** — neither is in the spec; YAGNI.
- **Excel `.xlsx`** — would require `openpyxl`, a third-party dep. Forbidden by Principle I.

---

## Summary

All five clarification questions in the spec have been answered by the user; this research document records the seven concrete technical decisions that flow from those answers (toolkit, threading, headless detection, OS-editor handoff, sub-package layout, export defaults, and the relationship to existing modules). No `NEEDS CLARIFICATION` markers remain anywhere in `plan.md` or this file.
