# pbir_validator

A standalone Python CLI that helps Power BI report developers maintain consistent
vertical spacing between visuals across all pages of a PBIR-format report.

Three modes:

- **`learn`** — derive spacing rules from a chosen reference page, write `conf.md`.
- **`validate`** — scan every page, report gap violations as a table (read-only).
- **`fix`** — auto-correct violations by shifting Y coordinates (atomic writes,
  `--dry-run` and `--apply` flags).

Stdlib-only at runtime. Packageable as a single-file Windows `.exe` via PyInstaller.

---

## Install

Requires **Python 3.11+**. No third-party packages are needed to *run* the tool.

Run from a checkout without installing:

```pwsh
git clone https://github.com/vishal12-pixel/pbir-layout-validator
cd "pbir-layout-validator"
python -m pbir_validator --help
```

Or install in editable mode to get a `pbir_validator` console script:

```pwsh
pip install -e .
pbir_validator --help
```

For contributors, install dev extras (`pytest`, `pytest-cov`):

```pwsh
pip install -e ".[dev]"
```

---

## Input path: `.pbip` file *or* `.Report` folder

Every subcommand's `--report` flag accepts **either**:

1. A path to a `.pbip` file. The tool parses the JSON, reads
   `artifacts[0].report.path` (relative to the `.pbip`), and resolves the sibling
   `.Report` folder automatically.
2. A direct path to a `.Report` folder containing `definition/pages/`.

The tool auto-detects which kind of path was provided. You never have to
specify which is which.

```pwsh
# Both work:
python -m pbir_validator validate --report "C:\reports\Sales.pbip"
python -m pbir_validator validate --report "C:\reports\Sales.Report"
```

---

## Usage

### Learn rules from a reference page

```pwsh
python -m pbir_validator learn --report "C:\path\to\MyReport.pbip"
# (interactive: pick the reference page from a numbered list)
```

Or non-interactively:

```pwsh
python -m pbir_validator learn --report "C:\path\to\MyReport.Report" `
    --page ReportSection1a2b3c --force
```

A `conf.md` is written to the report root (override with `--out`).

### Validate the whole report

```pwsh
python -m pbir_validator validate --report "C:\path\to\MyReport.Report"
```

Exit codes: `0` = clean, `1` = violations, `5` = config problem (missing/unparseable
`conf.md` or non-PBIR folder).

Use a shared rules file:

```pwsh
python -m pbir_validator validate --report "C:\reports\A.pbip" `
                                  --conf  "C:\team-standards\conf.md"
```

### Fix violations

Always preview first:

```pwsh
python -m pbir_validator fix --report "C:\path\to\MyReport.Report" --dry-run
```

Apply (interactive `y/N` confirmation):

```pwsh
python -m pbir_validator fix --report "C:\path\to\MyReport.Report"
```

Apply non-interactively (CI):

```pwsh
python -m pbir_validator fix --report "C:\path\to\MyReport.Report" --apply
```

Re-running `validate` immediately after a successful `fix` reports zero violations.

---

## Build a single-file Windows `.exe`

PyInstaller is **not** a runtime dependency; install it only when you build:

```pwsh
pip install pyinstaller
pyinstaller --onefile --name pbir_validator pbir_validator/__main__.py
# Result: dist\pbir_validator.exe
```

CI does this automatically on tagged `v*` releases — see
[.github/workflows/release.yml](.github/workflows/release.yml). The artifact is
attached to the corresponding GitHub Release.

---

## Run tests

```pwsh
pip install -e ".[dev]"
pytest                        # unit + integration; CI gate is ≥80% coverage
pytest -m benchmark           # opt-in 50-page perf budget check
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `not a PBIR report` | `--report` points at a `.pbix` archive, not a `.Report` folder or `.pbip` | Pass the unzipped `*.Report` directory or the `.pbip` file. |
| `conf.md not found` | Default location empty and no `--conf` given | Run `learn` first, or pass `--conf`. |
| Garbled escape sequences in `cmd.exe` | Legacy console without VT support | Add `--no-color`, or use Windows Terminal / VS Code terminal. |
| `unfixable` violations after `fix` | Shift would push a visual off the page | Manually move that visual or grow the page; tool refuses to truncate by design. |
