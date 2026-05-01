# Contract: Command-Line Interface

The CLI is the single externally visible interface. This contract is binding; tests in
`test_cli_integration.py` enforce every clause below.

## Invocation

```text
python -m pbir_validator <subcommand> [options]
# After PyInstaller build:
pbir_validator.exe   <subcommand> [options]
```

## Subcommands

Exactly one of `learn`, `validate`, `fix` MUST be supplied. They are mutually exclusive
and each is a distinct argparse sub-parser.

### `learn`

Derive spacing rules from a single reference page and write `conf.md`.

| Flag | Required | Default | Description |
|---|---|---|---|
| `--report PATH` | yes | — | Path to the `.Report` folder. |
| `--out PATH` | no | `<report>/conf.md` | Output path for the rules file. |
| `--page ID` | no | _interactive_ | Page id to use as reference; if omitted, the tool prints a numbered list of pages and prompts. |
| `--force` | no | `False` | Overwrite existing output file without prompting. |
| `--no-color` | no | `False` | Disable ANSI colors. (Also auto-disabled by `NO_COLOR` env var or non-TTY stdout.) |

**Exit codes**

- `0` — `conf.md` written successfully.
- `2` — Report folder is not a valid PBIR report (no `definition/pages/`).
- `3` — User cancelled the page-selection prompt.
- `4` — Output path exists and `--force` was not supplied (and user answered "n").
- `5` — Internal I/O or parse failure (path printed in the error message).

### `validate`

Check every page against `conf.md`. Read-only — never writes any file.

| Flag | Required | Default | Description |
|---|---|---|---|
| `--report PATH` | yes | — | Path to the `.Report` folder. |
| `--conf PATH` | no | `<report>/conf.md` | Path to the rules file. |
| `--no-color` | no | `False` | Disable ANSI colors. |

**Output (stdout)**

1. A header line naming the report and the rules file in use.
2. A single tabular block of violations with columns:
   `Page | From | To | Expected | Actual | Deviation`.
3. A separate "Unknown pairs" section listing pairs not found in `conf.md` (warnings, not
   violations).
4. A footer line: `<N> violation(s) across <M> page(s)` or `OK — no violations`.

**Exit codes**

- `0` — Zero violations. Unknown-pair warnings do NOT change the exit code.
- `1` — One or more violations.
- `2` — Report folder is not a valid PBIR report.
- `5` — `conf.md` missing or unparseable (path and reason printed).

### `fix`

Apply Y-coordinate shifts to bring gaps into compliance. Writes to disk only when both
`--apply` is supplied AND every planned shift on a given page is fixable (or the user
accepts the interactive `y/N` prompt).

| Flag | Required | Default | Description |
|---|---|---|---|
| `--report PATH` | yes | — | Path to the `.Report` folder. |
| `--conf PATH` | no | `<report>/conf.md` | Path to the rules file. |
| `--dry-run` | no | `False` | Print the plan; do not write any file. |
| `--apply` | no | `False` | Write changes without an interactive prompt. Required for non-interactive use (CI). |
| `--no-color` | no | `False` | Disable ANSI colors. |

**Default behavior** (neither `--dry-run` nor `--apply`): print the plan, then prompt
`Apply N change(s) across M page(s)? [y/N]`. Empty input or `n`/`N` → no writes,
exit code `0`.

**Output (stdout)**

1. The same header + violations table as `validate`.
2. A "Planned changes" tabular block with columns:
   `Page | Visual | Old Y | New Y | Δ | Note` where `Note` is empty, `(group)`, or
   `UNFIXABLE: <reason>`.
3. After write (if applied): per-page summary `Wrote N file(s) on page <name>`.
4. Footer: `Applied N change(s)` or `Dry-run — no files modified` or `Cancelled`.

**Exit codes**

- `0` — All planned, fixable changes applied (or dry-run completed) with no errors.
- `1` — At least one violation was unfixable (page boundary). Other fixable changes are
  still applied unless `--dry-run`.
- `2` — Report folder is not a valid PBIR report.
- `5` — `conf.md` missing/unparseable, or a `visual.json` write failed mid-run (the path
  is printed; per-file atomicity guarantees that file is either old or new content,
  never partial).
- `6` — User cancelled the interactive prompt.

## Global behaviors (all subcommands)

- `--help` / `-h` produces the standard argparse help and exits `0`.
- `--version` prints `pbir_validator <semver>` and exits `0`.
- Unhandled exceptions print a one-line summary `ERROR: <type>: <msg>` and exit `5`.
  Stack traces are suppressed unless `PBIR_VALIDATOR_DEBUG=1` is set.
- Color rules: per `research.md` §3 — `NO_COLOR`, non-TTY stdout, or Windows VT-mode
  failure all disable color. `--no-color` is an explicit override.
- The tool MUST NOT make network calls under any circumstance (Constitution: Out of
  Scope; tests assert this by running with a sandboxed environment in CI).
