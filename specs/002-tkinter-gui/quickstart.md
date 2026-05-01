# Quickstart: Tkinter Desktop GUI

**Feature**: 002-tkinter-gui
**Audience**: First-time GUI user, demo presenter, peer reviewer

## What you need

- Python 3.11 or newer with the standard `tkinter` module available (it ships with the official CPython installer on Windows and macOS; on Linux install the distro's `python3-tk` package if you skipped it).
- A clone of this repo, or a published wheel.
- A `.pbip` file or a `.Report` folder you want to inspect.

## Install

From the repo root:

```powershell
pip install -e .
```

This is the same command CLI users already run. The new line in `pyproject.toml` causes pip to also generate a launcher shim:

| Platform | Generated launcher                                         |
|----------|------------------------------------------------------------|
| Windows  | `<venv>\Scripts\pbir_validator-gui.exe` (double-clickable) |
| macOS    | `<venv>/bin/pbir_validator-gui`                            |
| Linux    | `<venv>/bin/pbir_validator-gui`                            |

Verify with:

```powershell
where.exe pbir_validator-gui    # Windows
which pbir_validator-gui        # macOS / Linux
```

## Launch

```powershell
pbir_validator-gui
```

That's it — no arguments. A single window opens with:

- **Two Browse buttons** at the top: "Browse `.pbip`…" and "Browse `.Report`…"
- A read-only **Resolved report path** label below them.
- Three primary action buttons: **Learn**, **Validate**, **Fix**.
- A `ttk.Notebook` filling the rest of the window with four tabs: **Gap Violations**, **Row Misalignments**, **Horizontal Spacing**, **Fix Plan**.
- A small progress indicator (initially hidden) next to the action buttons.

If you launch in a headless environment (SSH without X11 forwarding, a CI container, etc.), the launcher exits with code 2 and prints:

```text
pbir_validator-gui: no display available; use the CLI 'pbir_validator' instead.
```

## 60-second demo script

Use this script for showing peers how the GUI complements the CLI.

1. **Pick a report** — Click **Browse `.Report`…**, navigate to one of the demo reports in this workspace (the `M365 E3 Targeted Promo Tenants Dashboard Channel.Report` folder works well). The "Resolved report path" label updates and the three action buttons enable.

2. **Validate** — Click **Validate**. The progress indicator appears. Within ~5 seconds (per SC-005), the **Gap Violations** tab populates and is brought to the foreground. Click the **Row Misalignments** and **Horizontal Spacing** tabs to see those findings.

3. **Export** — On the Gap Violations tab, click **Export…**. The save dialog suggests `gap-violations.csv`. Save it; open it in Excel; confirm the same rows you saw on screen are in the spreadsheet.

4. **Learn (manual edit)** — Click **Learn**. A dialog asks "Do you want to manually edit `conf.md` instead?". Click **Yes**. Your OS opens `conf.md` in whatever editor handles `.md` (VS Code by default on most dev machines).

5. **Learn (regenerate)** — Click **Learn** again. This time click **No**. A page dropdown appears; pick a page and click **Confirm**. A success message names the regenerated `conf.md`.

6. **Fix (dry-run)** — Click **Fix**. The **Fix Plan** tab populates with one row per planned shift, all checkboxes pre-checked. Uncheck one row whose offset you know is intentional. The **Apply selected fixes** button stays enabled.

7. **Fix (apply)** — Click **Apply selected fixes**. The progress indicator runs briefly, then the three Validate tabs auto-refresh with the post-fix state, and the Fix Plan tab shows a summary line like `3 applied, 1 skipped, 0 remaining (re-run Fix)`.

8. **Close the window** — exit code is 0.

## What's the same as the CLI?

For the same input, the GUI's Validate output contains **exactly the same findings** as `pbir_validator validate <path>` (SC-002). The Fix dry-run lists **exactly the same shifts** as `pbir_validator fix <path>` (without `--apply`) (SC-003). If you uncheck N shifts before Apply, the on-disk change set is exactly `(total − N)` shifts (SC-004).

## What's different from the CLI?

- No ANSI colors (the GUI uses your OS theme — including dark mode — instead).
- No `--apply` confirmation prompt; the GUI's safety mechanism is the per-shift checkbox list instead.
- No exit codes per finding (the GUI just shows results; CI should keep using the CLI).
- No interactive prompts in your terminal (everything is in-window).

## When to keep using the CLI

- CI / scripts.
- SSH or containers without X11.
- Bulk-validating many reports.
- When you want exit codes and machine-parseable output.

## Troubleshooting

| Symptom                                              | Cause                                              | Fix                                                                         |
|------------------------------------------------------|----------------------------------------------------|-----------------------------------------------------------------------------|
| `pbir_validator-gui: no display available; …`        | Launched in a headless shell                       | Run on a desktop session, or use the CLI.                                   |
| `ModuleNotFoundError: No module named '_tkinter'`    | Linux distro Python built without Tk               | `sudo apt install python3-tk` (Debian/Ubuntu) or equivalent.                |
| Buttons stay disabled after picking a folder         | Folder isn't a valid `.Report` PBIR layout         | Open the folder; confirm it has a `definition/report.json`. Check the in-window error message for the exact missing path. |
| "Permission denied" when applying fixes              | Report file is read-only or open in another tool   | Close Power BI Desktop / your editor; clear the read-only attribute; retry. |
| Window opens, action buttons enabled, but Validate produces nothing | Report has zero issues                | This is a successful run — each result tab will say "No issues found."      |

## For developers

- GUI code lives in `pbir_validator/gui/`. The CLI does not import this sub-package.
- Run the GUI test suite with `pytest tests/gui/ -v`.
- The smoke test in `tests/gui/test_app_smoke.py` is auto-skipped on CI runners without a display; run it locally to validate end-to-end UI behavior.
- To test headless behavior on a developer machine, unset `DISPLAY` (Linux) or run inside Windows Server Core, then launch `pbir_validator-gui` and confirm exit code 2.
