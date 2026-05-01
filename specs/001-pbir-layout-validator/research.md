# Phase 0 Research: PBIR Layout Validator & Fixer

All Technical Context fields were resolved in the user-supplied tech direction. The items
below capture the decisions, the rationale, and the alternatives considered so future
maintainers do not have to re-derive them.

## 1. Python version: 3.11+

- **Decision**: Require Python 3.11+ as the minimum runtime.
- **Rationale**: The constitution mandates Python 3.11+. Although the user's plan brief
  said "3.10+", the constitution wins per Governance. 3.11 also gives us faster startup
  (PEP 657 / specializing adaptive interpreter) which helps the <200 ms cold-start budget,
  and `tomllib` if we ever want it.
- **Alternatives considered**: 3.10 (rejected — conflicts with constitution); 3.12-only
  (rejected — narrows the install base for no concrete benefit here).

## 2. Zero runtime dependencies / stdlib only

- **Decision**: Use only `argparse`, `json`, `pathlib`, `os`, `sys`, `dataclasses`, `enum`,
  `typing`, `tempfile`, `shutil` at runtime. No `colorama`, no `rich`, no `pydantic`, no
  `click`.
- **Rationale**: Constitution Principle I + Additional Constraints forbid runtime
  third-party deps. Stdlib is sufficient for every requirement: `argparse` covers CLI;
  `json` handles PBIR I/O; `pathlib` covers cross-platform paths; ANSI escape codes
  cover color; `tempfile` + `os.replace` give atomic writes.
- **Alternatives considered**: `rich` for tables/colors (rejected — runtime dep);
  `pydantic` for model validation (rejected — runtime dep, also overkill for ~6 dataclasses).

## 3. Colored terminal output via raw ANSI

- **Decision**: Define a small set of ANSI constants in `ui.py`
  (`RESET="\x1b[0m"`, `RED="\x1b[31m"`, `GREEN="\x1b[32m"`, `YELLOW="\x1b[33m"`,
  `CYAN="\x1b[36m"`, `BOLD="\x1b[1m"`). Wrap output via `ui.colored(text, code)` that
  returns `text` unchanged when color is disabled.
- **Color enable/disable rule**:
  1. If `NO_COLOR` env var is set (any value) → disabled.
  2. Else if `sys.stdout.isatty()` is `False` → disabled.
  3. Else on Windows: enable Virtual Terminal Processing once at startup via
     `ctypes.windll.kernel32.SetConsoleMode`. If that call fails → disabled.
  4. Else → enabled.
- **Rationale**: Modern Windows 10+ terminals (Windows Terminal, VS Code terminal,
  pwsh 7) support VT sequences. Legacy `cmd.exe` may not — graceful fallback to plain
  text covers it. `NO_COLOR` honors the de-facto standard <https://no-color.org/>.
- **Alternatives considered**: `colorama` (rejected — runtime dep); detecting
  `WT_SESSION` env var (rejected — too narrow, misses VS Code terminal).

## 4. Atomic file writes (write-then-rename)

- **Decision**: For every `visual.json` mutation, write the new content to a sibling
  temp file via `tempfile.NamedTemporaryFile(dir=parent, delete=False)`, `fsync` it,
  then `os.replace(tmp_path, target_path)`. `os.replace` is atomic on both POSIX and
  Windows (NTFS) for same-filesystem replacements.
- **Rationale**: FR-023 + SC-004 forbid leaving half-written JSON on disk even if the
  process is killed mid-fix. Same-directory temp + `os.replace` is the standard
  cross-platform pattern.
- **Alternatives considered**: `tempfile.NamedTemporaryFile` in system temp dir
  (rejected — `os.replace` across drives is not atomic); locking + in-place write
  (rejected — leaves a partial file window).

## 5. JSON read/write that preserves unrelated fields and key order

- **Decision**: Read each `visual.json` with `json.load(..., object_pairs_hook=None)`
  (default), which since Python 3.7 preserves insertion order in `dict`. Mutate only the
  exact key path that holds the Y coordinate. Re-serialize with
  `json.dumps(data, indent=<detected>, ensure_ascii=False)` and a trailing newline if
  the original had one.
- **Indentation detection**: When loading, sniff the first nested indent (count leading
  spaces of the first non-`{` line). Default to `indent=2` if undetectable. Store
  per-file indent on the `Visual` model so the writer reproduces it.
- **Rationale**: FR-010 + FR-023 require that re-saved files differ minimally from the
  original (only the Y value). Python's stdlib `json` preserves dict order from 3.7+;
  no third-party JSON-with-comments parser is needed because PBIR `visual.json` is
  strict JSON.
- **Alternatives considered**: `json.JSONDecoder` with custom hook (rejected —
  unnecessary complexity); writing only fields we own (rejected — destroys unrelated
  visual properties, violates FR-010).

## 6. Y-coordinate JSON path inside `visual.json`

- **Decision**: PBIR `visual.json` stores position under `position.y` (and `position.x`,
  `position.height`, `position.width`). The reader treats any deviation (missing
  `position` object or non-numeric `y`) as an error for that visual: warn with the file
  path, skip it for analysis, and refuse to write it in fix mode (per spec edge case).
- **Rationale**: Spec Assumptions: "the Y-coordinate field path within `visual.json` is
  stable … the implementation will document the exact JSON path it reads/writes and
  treat any deviation as an error rather than silently guessing." This is documented in
  `contracts/pbir-paths.md`.
- **Alternatives considered**: Searching multiple candidate paths (rejected — silent
  guessing forbidden by spec).

## 7. Row grouping tolerance

- **Decision**: Hard-code `ROW_TOLERANCE_PX = 2` as a module-level constant in
  `analyzer.py`. Two visuals are in the same row when `abs(v1.y - v2.y) <= 2`.
  Rows are sorted by their minimum Y.
- **Rationale**: FR-007 fixes the value at ±2 px in v1; spec Assumptions explicitly
  state it is not user-configurable in v1. Keeping it a named constant (not a CLI flag)
  prevents drift while staying easy to change in v2.

## 8. Mixed-type row representative label

- **Decision**: When a row contains visuals of >1 distinct `visual.visualType`, the
  representative type is computed as: most-frequent type, ties broken by lexicographic
  order of the type string. Emit a single warning per occurrence: page name, row
  Y-min, the set of types encountered, and the chosen representative.
- **Rationale**: Spec FR-009 + Edge Case + Assumption require deterministic, repeatable
  selection. Lexicographic tie-break is deterministic and stable across runs.

## 9. Conflicting rule resolution in learn mode

- **Decision**: When a (from-type, to-type) pair appears multiple times on the
  reference page with different gaps, pick the **most frequent** value; ties broken by
  the **smallest** gap. Emit one warning per conflicting pair listing all observed
  gaps.
- **Rationale**: Spec Assumptions and FR-014 specify exactly this rule.

## 10. `conf.md` format

- **Decision**: One rule per non-blank, non-comment line in the form:
  `<from_type> -> <to_type>: <gap>px`. Lines starting with `#` are comments and
  ignored. Header section optional. Whitespace around `->` and `:` is permitted.
- **Rationale**: Human-readable per FR-012 and Key Entities; trivial to parse with
  `str.split` and `int()`. See `contracts/conf-format.md` for the formal grammar.
- **Alternatives considered**: YAML (rejected — would need PyYAML); JSON (rejected —
  spec requires "Markdown" / human-readable file); INI via `configparser` (rejected —
  awkward for the `from -> to` keying).

## 11. Group handling (`parentGroupName`)

- **Decision**: Pre-pass during fix planning: build a map `group_name -> [visual_ids]`.
  When a visual that belongs to a group is shifted, every other visual sharing the same
  `parentGroupName` on the same page is shifted by the same delta.
- **Rationale**: FR-025 + spec Assumptions mandate the "shift entire group as one
  unit" strategy in v1.

## 12. Page-boundary refusal

- **Decision**: After computing each planned shift, check
  `new_y + visual.height <= page.height`. If false, mark the violation as
  `unfixable`, log it (page, visual id, reason), and continue with the rest of the
  page. Other unaffected violations on the same page still get fixed.
- **Rationale**: Spec Edge Case + FR-024 require this exact behavior.

## 13. Fix-mode atomicity per page

- **Decision**: Plan the entire page's shifts in memory first; only after the plan is
  complete and free of unfixable violations do we begin writing files for that page.
  If any write fails mid-page, abort further pages, surface the failing path, and
  leave already-written files (which are atomic per file) intact and valid.
- **Rationale**: SC-004 + FR-023. Per-file atomicity is enforced by `os.replace`;
  per-page batching prevents partial-page inconsistencies; whole-run rollback is
  explicitly out of scope per Acceptance Scenario 5 (US3) which says "leaves the
  report in a state where already-written changes are valid JSON" — i.e., individual
  files must be valid, not the whole batch reverted.

## 14. PyInstaller packaging (build-time only)

- **Decision**: PyInstaller is a **build-time** dependency, never imported by the tool
  itself. Build command documented in README:
  `pyinstaller --onefile --name pbir_validator pbir_validator/__main__.py`.
  CI builds the `.exe` on `windows-latest` runner only on tagged releases and
  uploads the artifact to the GitHub Release.
- **Rationale**: SC-005. Keeping PyInstaller out of `pyproject.toml`'s runtime deps
  preserves stdlib-only runtime guarantee.
- **Alternatives considered**: `nuitka` (rejected — heavier toolchain, less common);
  `zipapp` / `pex` (rejected — Windows users still need Python installed; user wants a
  true `.exe`).

## 15. CI workflow split

- **Decision**: Two GitHub Actions workflows.
  - `.github/workflows/test.yml`: `on: [push, pull_request]`, matrix
    `os: [windows-latest, ubuntu-latest]`, `python: ['3.11', '3.12']`. Steps:
    checkout → setup-python → `pip install -e .[dev]` → `pytest --cov` →
    upload coverage.
  - `.github/workflows/release.yml`: `on: push: tags: ['v*']`, single `windows-latest`
    job. Steps: checkout → setup-python → `pip install pyinstaller -e .` →
    `pyinstaller --onefile ...` → `actions/upload-release-asset` to attach
    `dist/pbir_validator.exe` to the release.
- **Rationale**: User's plan brief explicitly requested this split.

## 16. Lazy iteration / memory budget

- **Decision**: `reader.iter_pages(report_root)` is a generator yielding `Page`
  records; each `Page` exposes `iter_visuals()` which is itself a generator that
  loads one `visual.json` at a time, parses it, yields the `Visual`, and lets the
  parsed dict be GC'd before the next file. Validate/fix consume one page at a time.
- **Rationale**: Constitution Principle IV explicitly forbids loading the entire
  report up-front. Generator pipelines satisfy this with no extra machinery.

## 17. Testing strategy

- **Decision**:
  - Unit tests per module (`test_reader.py`, `test_analyzer.py`, …) hit pure
    functions with small handcrafted dicts and `tmp_path` fixtures.
  - `tests/fixtures/sample-report/` is a real PBIR mini-report with 3 pages: one
    "good" reference page, one with a fixable gap violation, one with an unfixable
    (page-boundary) violation, plus one mixed-type row and one grouped pair.
  - `test_cli_integration.py` invokes `python -m pbir_validator …` via
    `subprocess.run` against a `tmp_path` copy of the fixture, asserts exit codes
    and stdout substrings.
  - Coverage gate enforced in `pyproject.toml`: `--cov=pbir_validator --cov-fail-under=80`.
- **Rationale**: Constitution Principle II — required.

## 18. Performance benchmark fixture

- **Decision**: `tests/fixtures/benchmark-report/` is generated by a small
  `tests/_gen_benchmark.py` helper script (committed but not auto-run) that
  produces a synthetic 50-page report. A pytest test marked
  `@pytest.mark.benchmark` runs validate against it and asserts wall-clock
  <5 s. The marker is opt-in via `pytest -m benchmark`.
- **Rationale**: Constitution Principle IV requires a runnable benchmark; opt-in
  marker keeps the default test run fast.
