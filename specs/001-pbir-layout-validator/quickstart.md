# Quickstart

Five-minute path from clean checkout to first successful run.

## Prerequisites

- Python 3.11 or newer on `PATH` (`python --version`).
- A Power BI report saved in **PBIR** format (a folder ending in `.Report` that contains
  a `definition/pages/` subtree).

No `pip install` of third-party packages is required to run the tool. `pytest` is needed
only if you intend to run the test suite.

## 1. Get the code

```pwsh
git clone <repo-url>
cd "pbib validator tool"
```

## 2. Run the tool from source

The package is runnable as a module — no install needed:

```pwsh
python -m pbir_validator --help
```

(Optional) install in editable mode so you also get the `pbir_validator` console script:

```pwsh
pip install -e .
pbir_validator --help
```

## 3. Learn rules from a reference page

```pwsh
python -m pbir_validator learn --report "C:\path\to\MyReport.Report"
```

The tool prints a numbered list of pages; pick the page whose vertical layout you
consider correct. A `conf.md` is written to the report root.

Non-interactive variant:

```pwsh
python -m pbir_validator learn --report "C:\path\to\MyReport.Report" `
                              --page ReportSection1a2b3c --force
```

## 4. Validate the whole report

```pwsh
python -m pbir_validator validate --report "C:\path\to\MyReport.Report"
```

Exit code `0` = clean, `1` = one or more violations (printed as a table), `5` = config
problem.

Use a shared rules file:

```pwsh
python -m pbir_validator validate --report "C:\path\to\MyReport.Report" `
                                  --conf  "C:\team-standards\conf.md"
```

## 5. Auto-fix violations (always preview first)

Preview only — no files touched:

```pwsh
python -m pbir_validator fix --report "C:\path\to\MyReport.Report" --dry-run
```

Apply (interactive confirmation):

```pwsh
python -m pbir_validator fix --report "C:\path\to\MyReport.Report"
```

Apply non-interactively (CI):

```pwsh
python -m pbir_validator fix --report "C:\path\to\MyReport.Report" --apply
```

Re-running `validate` immediately after a successful `fix` should report zero
violations.

## 6. Run the test suite (contributors)

```pwsh
pip install -e ".[dev]"
pytest                          # unit + integration; default
pytest --cov                    # with coverage; CI gate is ≥80% on core modules
pytest -m benchmark             # opt-in 50-page perf budget check
```

## 7. Build a single-file Windows `.exe` (release)

PyInstaller is **not** a runtime dependency; install it only when you build:

```pwsh
pip install pyinstaller
pyinstaller --onefile --name pbir_validator pbir_validator/__main__.py
# Result:  dist\pbir_validator.exe
```

CI does this automatically on tagged releases (`v*`) and attaches the artifact to the
GitHub Release — see `.github/workflows/release.yml`.

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `not a PBIR report` | `--report` points at the `.pbix` file, not the `.Report` folder | Pass the unzipped `*.Report` directory. |
| `conf.md not found` | Default location empty and no `--conf` given | Run `learn` first, or pass `--conf`. |
| Garbled escape sequences in `cmd.exe` | Legacy console without VT support | Add `--no-color`, or use Windows Terminal / VS Code terminal. |
| `unfixable` violations after `fix` | Shift would push a visual off the page | Manually move that visual or shrink the page; tool refuses to truncate by design. |
| Validate is slow on a huge report | Cold filesystem cache | Re-run; warm cache is the budgeted scenario per Principle IV. |
