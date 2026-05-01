# Controller API Contract — `pbir_validator.gui.controllers`

This contract documents the **new** and **changed** controller surface
introduced by feature 004. Tk-free; testable in isolation.

## New module: `pbir_validator.gui.recents`

```python
def recents_path() -> pathlib.Path: ...
def load() -> list[str]: ...
def record(path: str) -> list[str]: ...
```

| Function | Pre | Post | Failure mode |
|---|---|---|---|
| `recents_path` | — | Path object; parent dir ensured to exist. | Never raises (creates dirs as needed). |
| `load` | — | List of 0–5 strings, MRU-first. | Returns `[]` on `FileNotFoundError`, `json.JSONDecodeError`, `KeyError`, `OSError`. |
| `record` | `path` is non-empty str. | List of 1–5 strings, `path` at index 0, no duplicates. Persisted to disk. | Returns the new list even if write fails (in-memory state is authoritative for the session). |

## New module: `pbir_validator.gui.severity`

```python
SEV_GREEN: str
SEV_YELLOW: str
SEV_RED: str

def band(value: float, *, kind: typing.Literal["deviation", "overlap"]) -> str: ...
```

| `kind` | Input | Output |
|---|---|---|
| `"deviation"` | `\|value\| ≤ 2` | `SEV_GREEN` |
| `"deviation"` | `2 < \|value\| ≤ 10` | `SEV_YELLOW` |
| `"deviation"` | `\|value\| > 10` | `SEV_RED` |
| `"overlap"` | `value ≤ 0` | `SEV_GREEN` (no overlap) |
| `"overlap"` | `0 < value ≤ 50` | `SEV_YELLOW` |
| `"overlap"` | `value > 50` | `SEV_RED` |

## New helper functions in `pbir_validator.gui.controllers`

```python
@dataclass
class TabState:
    name: str
    columns: tuple[str, ...]
    numeric_columns: frozenset[int] = frozenset()
    rows: list[tuple[str, ...]] = field(default_factory=list)
    sort: tuple[int, bool] | None = None
    filter_text: str = ""

def visible_rows(state: TabState) -> list[tuple[str, ...]]: ...
def toggle_sort(state: TabState, col: int) -> TabState: ...
def set_filter(state: TabState, text: str) -> TabState: ...
def set_rows(state: TabState, rows: list[tuple[str, ...]]) -> TabState: ...
```

| Function | Behavior |
|---|---|
| `visible_rows` | Returns rows after applying filter (case-insensitive substring on any cell) then sort. Pure. |
| `toggle_sort` | Cycles col-N: None → (N, asc) → (N, desc) → (N, asc); selecting a different column resets to (M, asc). |
| `set_filter` | Returns new state with `filter_text` set (lower-cased). |
| `set_rows` | Returns new state with `rows` replaced and `filter_text` cleared. `sort` is preserved (FR-013a). |

## Right-click action helpers

```python
def open_in_power_bi(report_root: pathlib.Path) -> tuple[bool, str]: ...
def row_to_clipboard_text(cells: tuple[str, ...]) -> str: ...
```

| Function | Behavior |
|---|---|
| `open_in_power_bi` | Returns `(True, "")` after `os.startfile(report_root/'definition.pbir')`. Returns `(False, "<reason with path>")` if the file is missing or `OSError` on launch. |
| `row_to_clipboard_text` | Returns `"\t".join(cells)`. Pure. Caller writes via `widget.clipboard_append`. |

## Changed: `ValidateResult`

```python
@dataclass(frozen=True, slots=True)
class ValidateResult:
    gaps: list[Violation]
    overlaps: list[Violation]
    duplicate_layers: list[DuplicateLayer]   # NEW
    misalignments: list[Misalignment]
    h_spacing: list[HSpacingIssue]
```

`validate(report_root)` populates `duplicate_layers` from the new tuple
returned by `analyzer.group_into_rows()`.

## Changed: GUI tab labels & order

```python
_TAB_GAPS         = "Gap Violations"
_TAB_OVERLAPS     = "Overlapping Visuals"
_TAB_DUPLICATES   = "Duplicate Layer"          # NEW
_TAB_MISALIGN     = "Row Misalignments"
_TAB_HSPACING     = "Horizontal Spacing"
_TAB_FIXPLAN      = "Fix Plan"
```

Smoke test asserts `notebook.index("end") == 6` and label order above.

## Backward compatibility

- CLI surface (`pbir_validator --validate`, `--fix`, `--learn`,
  exit codes) — **unchanged**.
- All existing `Violation` / `Misalignment` / `HSpacingIssue` shapes —
  **unchanged**.
- `ValidateResult.duplicate_layers` defaults to `[]`; pre-existing
  consumers that destructure tuples by name remain compatible.
