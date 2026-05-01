# Contract: Console Script Entry Points

**Feature**: 002-tkinter-gui
**Date**: 2026-05-01

This contract documents the **delta** that feature 002 introduces over the existing CLI contract in [specs/001-pbir-layout-validator/contracts/cli.md](../../001-pbir-layout-validator/contracts/cli.md). The 001 CLI contract is unchanged in every respect.

---

## Existing entry point — UNCHANGED

```toml
# pyproject.toml (existing — DO NOT MODIFY)
[project.scripts]
pbir_validator = "pbir_validator.cli:main"
```

- All subcommands (`learn`, `validate`, `fix`) keep their current arguments, exit codes, color rules, and output format.
- Importing `pbir_validator` continues to NOT import `tkinter` (the `gui` sub-package is loaded only when explicitly imported).
- All 120 existing tests remain green.

---

## NEW entry point: `pbir_validator-gui`

```toml
# pyproject.toml — NEW LINE TO ADD under [project.scripts]
pbir_validator-gui = "pbir_validator.gui.app:main"
```

After `pip install -e .` (or any install that re-runs entry-point generation), this creates:

| Platform | Generated artifact                                          |
|----------|-------------------------------------------------------------|
| Windows  | `<venv>\Scripts\pbir_validator-gui.exe` (a Python launcher shim) |
| macOS    | `<venv>/bin/pbir_validator-gui` (a `#!`-prefixed Python script)  |
| Linux    | `<venv>/bin/pbir_validator-gui` (a `#!`-prefixed Python script)  |

### Invocation

```text
pbir_validator-gui          # opens main window — no other args
```

### Arguments

**None.** The GUI takes zero command-line arguments. Report selection happens through the in-window Browse buttons (FR-002). Any positional arguments or unknown flags are reserved for a future MINOR version and currently ignored without error to keep the launcher idempotent (`os.startfile` on Windows occasionally appends a working-directory token).

### Exit codes

| Code | Meaning                                                                                 |
|------|-----------------------------------------------------------------------------------------|
| `0`  | The Tk main loop ran and the user closed the window normally.                           |
| `2`  | Headless environment detected (FR-025): `Tk()` raised `tk.TclError`. A single-line message is written to `stderr` directing the user to the `pbir_validator` CLI. |
| `1`  | Reserved for unexpected uncaught exceptions during bootstrap. Should not occur in practice; if it does, an exception traceback is printed to `stderr` (this is a developer-visible last-resort path; in normal operation, errors are surfaced via `messagebox` per FR-024). |

### `stdout` / `stderr` contract

- **Normal launch**: nothing written to `stdout` or `stderr`. The GUI is the user-visible surface.
- **Headless failure**: one line on `stderr`: `pbir_validator-gui: no display available; use the CLI 'pbir_validator' instead.` Exit code 2.
- The GUI MUST NOT write logs to `stdout`/`stderr` during normal operation (avoids polluting terminals when launched from a shortcut that nonetheless inherits a console).

### Module-form invocation

```text
python -m pbir_validator.gui.app   # equivalent to running the entry point
```

This works because `app.py` ends with the standard guard:

```python
if __name__ == "__main__":
    main()
```

It is provided as a fallback for environments where `pip` could not install the entry-point shim (e.g., zipapp / PEP 582 layouts), but the documented user-facing launch is the `pbir_validator-gui` script.

---

## CLI / GUI separation guarantees

These guarantees are enforced by the project structure and verified by tests:

1. **`pbir_validator.cli` does not import `pbir_validator.gui`**. Verified by `tests/test_cli_inprocess.py`-style import-time assertions that `tkinter` is not in `sys.modules` after `import pbir_validator`.
2. **Removing `pbir_validator/gui/` MUST NOT break any CLI command** (FR-022). Verified manually in CI by running the CLI test suite with the `gui/` folder absent.
3. **No CLI command silently invokes the GUI**. Verified by `tests/test_cli_integration.py` — the existing 120 tests already establish the CLI's complete output surface; any new GUI-triggered output would break them.
4. **The new entry point name (`pbir_validator-gui`) does not collide with any existing subcommand** (the existing CLI's subcommands are `learn`, `validate`, `fix`).

---

## Summary

| Change                                                  | Where                                                  |
|---------------------------------------------------------|--------------------------------------------------------|
| Add one line under `[project.scripts]`                  | `pyproject.toml`                                       |
| Add a `main()` function                                 | `pbir_validator/gui/app.py`                            |
| Document headless-exit-2 behavior                       | This file (above) and `quickstart.md`                  |
| (Nothing changes in the existing CLI contract)          | `specs/001-pbir-layout-validator/contracts/cli.md`     |
