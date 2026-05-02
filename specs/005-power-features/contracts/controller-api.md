# Contract — Controller & Helper API surface

This contract documents every public function added or changed by feature
005. Signatures are normative — TDD tests in `tests/` MUST be written
against this surface before implementation lands.

All paths are absolute or `pathlib.Path` instances; all return types are
explicit; every function is stdlib-only.

---

## `pbir_validator/gui/controllers.py`

### CHANGED — `validate(...)` gains an in-memory rules override

```python
def validate(
    report_path: Path | str,
    conf_path: Path | str | None,
    *,
    rules: Mapping[tuple[str, str], "GapRule"] | None = None,
) -> ValidateResult:
    """Run validation; identical to today when ``rules`` is None.

    When ``rules`` is provided, ``conf_path`` is ignored entirely:
    no disk lookup, no parse_conf call. Used by the profile dropdown
    (US6) to swap rule sources without touching the user's working
    tree.
    """
```

**Backward compatibility**: existing callers (CLI + every existing GUI
call site) pass `rules=None` (the default) and observe byte-identical
behavior. FR-070 is satisfied because no CLI call site is touched.

---

### NEW — ZIP-of-CSVs export

```python
def export_all_zip(
    result: ValidateResult,
    fix_plan: Sequence["Shift"] | None,
    dest_path: Path,
) -> list[str]:
    """Write one ZIP archive at ``dest_path`` containing one CSV per
    non-empty result tab.

    Returns the list of archive entry names actually written
    (alphabetical, e.g. ``["duplicate_layers.csv", "fix_plan.csv",
    "gaps.csv", "h_spacing.csv", "misalignments.csv", "overlaps.csv"]``
    minus any tab whose source list is empty).

    Raises ``OSError`` on write failure — caller surfaces via
    ``widgets.show_error``.
    """
```

- Fixed entry names per FR-012.
- Each CSV's bytes equal the bytes the existing per-tab Export button
  would produce for the same data (FR-013).

---

### EXISTING — reused for double-click

```python
def open_in_power_bi(report_path: Path) -> tuple[bool, str]:
    """Already exists in feature 004; signature unchanged.

    The new double-click handler in ``app.py`` calls this helper
    directly so error-paths (missing file, non-Windows) match the
    right-click action exactly (FR-003).
    """
```

---

## `pbir_validator/gui/undo.py` — NEW module

```python
def record_pre_fix(
    report_root: Path,
    plan: Sequence["Shift"],
) -> Path:
    """Write ``<report_root>/.pbir_validator_undo/last_fix.json`` with
    one entry per visual the plan will touch.

    Creates the parent directory if missing. Overwrites any prior
    backup (one-level undo, FR-064). Atomic write via tempfile +
    os.replace, identical to writer.py's pattern.

    Returns the path that was written.

    Raises ``OSError`` on write failure (caller is expected to abort
    the Apply before calling write_visual_json).
    """


def restore_last_fix(
    report_root: Path,
) -> tuple[bool, str, list[str]]:
    """Restore every shift recorded in last_fix.json.

    Returns ``(ok, message, modified_paths)`` where:
      * ``ok``: True only if every shift restored successfully
      * ``message``: human-readable status (success or first-error
        description including the offending file path per
        Constitution Principle III)
      * ``modified_paths``: list of POSIX-style relative paths whose
        ``position.y`` was actually written back

    On any per-file write failure the operation aborts immediately
    and the backup file is left on disk untouched (FR-065). On full
    success, the backup file AND its parent ``.pbir_validator_undo/``
    directory (if empty) are deleted.
    """
```

---

## `pbir_validator/gui/profiles.py` — NEW module

```python
def list_profiles(report_root: Path | None = None) -> dict[str, Path]:
    """Return ordered mapping of display-name → profile file path.

    Always contains keys ``Standard``, ``Strict``, ``Relaxed`` resolved
    via ``importlib.resources.files("pbir_validator.profiles")``.

    Adds ``Report-default`` → ``report_root/conf.md`` only when
    ``report_root`` is given AND ``report_root/conf.md`` exists
    (FR-055).
    """


def load_profile(name: str, report_root: Path | None = None) -> Mapping[tuple[str, str], "GapRule"]:
    """Resolve ``name`` via ``list_profiles()`` then return the parsed
    rules dict by delegating to ``pbir_validator.conf.parse_conf``.

    Raises ``KeyError`` if ``name`` is not a known profile.
    """
```

---

## `pbir_validator/gui/watch.py` — NEW module

```python
@dataclass(frozen=True)
class WatchState:
    mtimes: Mapping[Path, float]
    last_check: float


def snapshot_mtimes(report_root: Path) -> dict[Path, float]:
    """Return absolute Path → st_mtime for every watched file under
    ``report_root``: ``definition.pbir``, every ``*.pbip`` sibling, and
    every ``pages/*/visuals/*/visual.json``.

    Files that disappear mid-walk are silently skipped; the function
    never raises ``FileNotFoundError`` (FR-025).
    """


def diff_mtimes(
    previous: Mapping[Path, float],
    current: Mapping[Path, float],
) -> bool:
    """Return True iff any path's mtime advanced or any path appeared
    that wasn't in ``previous``. Disappearing files do NOT count as a
    change (so renames don't double-fire after the next snapshot)."""
```

`Tk.after()` orchestration lives in `app.py`; `watch.py` itself is
Tk-free and exhaustively unit-testable.

---

## `pbir_validator/gui/grade.py` — NEW module

```python
def compute(counts: Mapping[str, int]) -> tuple[str, int]:
    """Return ``(letter, score)`` per spec FR-030 / FR-031.

    Missing keys default to 0. Negative values raise ``ValueError`` —
    they would silently swallow data corruption.
    """


def color_for(letter: str) -> str:
    """Return a Tk color string for the grade letter; returns ``""``
    (empty) for the neutral state (no run yet). Unknown letters
    raise ``ValueError``."""
```

---

## `pbir_validator/gui/panel.py` — NEW module

```python
def extract_visual_context(visual: "Visual") -> dict:
    """Return a Tk-free dict with keys: ``id``, ``page_id``,
    ``page_display_name``, ``visual_type``, ``x``, ``y``, ``width``,
    ``height``, ``parent_group``, ``raw_json``.

    ``raw_json`` is the visual's raw payload re-serialized with
    ``json.dumps(indent=2, ensure_ascii=False)`` — pretty for the
    read-only Text widget per FR-041.
    """


def find_visual_for_row(
    rows: Sequence[tuple[object, ...]],
    idx: int,
    columns: tuple[str, ...],
    visuals_by_id: Mapping[str, "Visual"],
) -> list["Visual"]:
    """Return the visual(s) referenced by ``rows[idx]``.

    Returns one ``Visual`` for single-reference tabs and two stacked
    ``Visual`` objects for overlap / h-spacing / duplicate-layer pair
    rows (FR-042). Returns ``[]`` if no referenced id resolves —
    caller renders the placeholder.
    """
```

---

## `pbir_validator/gui/recents.py` — CHANGED

```python
def load() -> dict:
    """Now returns the whole dict, e.g.
    ``{"recent": [...], "side_panel_visible": True, "profile": "Standard"}``.

    Missing keys default to ``True`` and ``"Standard"`` respectively
    (FR-072). Always returns a dict (was: list).
    """


def load_paths() -> list[str]:
    """Convenience for the File-menu Recent submenu — returns just
    ``load()["recent"]``. Backward-compatible replacement for the old
    ``load()`` shape; existing call sites in ``app.py`` are migrated
    to this name."""


def record(path: str | None = None, **updates) -> dict:
    """Update arbitrary keys (``side_panel_visible=False``,
    ``profile="Strict"``) and/or push ``path`` to the front of the
    MRU list. Returns the updated dict."""
```

---

## `pbir_validator/fixer.py` — CHANGED

```python
def apply_plan(
    report: Report,
    shifts: Sequence[Shift],
) -> list[Path]:
    """Same signature as today. New behavior: BEFORE the first
    ``writer.write_visual_json`` call, this function calls
    ``undo.record_pre_fix(report.root, shifts)`` so the backup is on
    disk before any visual.json is mutated (FR-060).

    On a per-file write failure the partially-written shifts remain on
    disk (existing behavior) but the backup is already present, so the
    user can still Undo whatever was applied successfully.
    """
```
