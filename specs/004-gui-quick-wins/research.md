# Phase 0 — Research & Design Decisions

Date: 2026-05-01
Spec: [spec.md](spec.md)

All NEEDS CLARIFICATION items were resolved in `/speckit.clarify`
(see Clarifications section in spec.md). This document captures the
remaining design decisions, each in the standard
**Decision / Rationale / Alternatives** format.

---

## D1. Row-grouping hotfix (US1)

**Decision**: In `analyzer.group_into_rows()`, change the row-key
algorithm from "exact y bucket → single row entry" to "exact y bucket →
list of visuals". After grouping, walk each row's visual list and emit:

- 1 visual → existing single-visual row behavior, unchanged.
- ≥2 visuals of **different** types at the same y → existing multi-type
  row, unchanged (Row Misalignment when type-set is heterogeneous).
- ≥2 visuals of **same** type at the same y → emit one
  `DuplicateLayer(page, visual_type, visual_a, visual_b, delta_y)` per
  pair (or N choose 2 pairs if more than 2).

**Rationale**: The current bug is that the row dict uses the first
visual's id as the value, silently dropping subsequent visuals that hash
to the same y bucket. Switching the value to a list preserves all
visuals; downstream emission decides classification. Minimal blast
radius — gap and h-spacing pipelines that already iterate `row.visuals`
will see the extra visual transparently.

**Alternatives considered**:

- *Detect duplicates at read time in `reader.py`*: rejected — reader's
  job is faithful one-visual-per-file emission, not classification.
- *Loosen the row-y tolerance*: rejected — would invent fake rows
  on legitimately-stacked visuals.
- *Surface duplicates as overlaps*: rejected per Q1 clarification (user
  chose Option B — dedicated tab).

---

## D2. `definition.pbir` launch mechanism (US2)

**Decision**: `os.startfile(report_root / "definition.pbir")` invoked on
the Tk main thread inside the context-menu callback. Wrapped in
`try/except OSError` to render an informational `messagebox.showinfo`
when the file is missing or no association exists.

**Rationale**: `os.startfile` is the Windows idiomatic API for "open as
if double-clicked", uses the registered file association, returns
immediately, and requires no shell quoting. Power BI Desktop's `.pbir`
association handles the rest. Confirmed by Q2 clarification.

**Alternatives considered**:

- `subprocess.Popen(["start", "", path], shell=True)` — works but
  introduces shell-quoting risk and a transient `cmd.exe`.
- `webbrowser.open("file://...")` — unreliable for non-HTML extensions.
- Cross-platform `xdg-open`/`open` dispatch — YAGNI; user is Windows-only
  per `Target Platform`.

---

## D3. Sort & filter state model (US3, US4)

**Decision**: Each result tab owns a `TabState` dataclass with three
fields: `rows: list[tuple]` (source-of-truth, never mutated by view),
`sort: tuple[int, bool] | None` (column index + descending flag),
`filter_text: str`. View materializes `visible = sort(filter(rows))`
on demand. `controllers.refresh_tab(state)` returns the visible rows.

**Rationale**: Pure function from state to view rows is trivially
testable without Tk. Filter resets on Validate (FR-013) by setting
`state.filter_text = ""`. Sort persists across Validate (FR-013a) by
preserving `state.sort`. No mutation of the underlying `Violation`
objects (frozen dataclasses).

**Alternatives considered**:

- *Maintain visible list directly inside Treeview* — couples logic to Tk,
  blocks unit testing.
- *Re-run validation on every keystroke* — wasteful; rows don't change
  between validations.

---

## D4. Filter latency strategy (US4)

**Decision**: Synchronous, no debounce. On `<KeyRelease>` in the filter
Entry, call `controllers.refresh_tab(state)` and replace Treeview
children. With 500 rows this completes in well under 100 ms (target per
SC-003a) on Python 3.14 — measured by `len(rows) * O(columns)` substring
checks.

**Rationale**: Debounce adds complexity with no measurable user benefit
at this scale. PBIR reports cap at ~200–300 violations in practice;
500 is generous headroom.

**Alternatives considered**:

- 50 ms debounce via `widget.after(50, ...)`: rejected as premature
  optimization.
- Background thread + queue: rejected; filter is CPU-bound and trivial.

---

## D5. Severity tag values & colors (US5)

**Decision**: Pure function `severity.band(deviation_px) -> str` returns
one of `"sev_green" | "sev_yellow" | "sev_red"`. Thresholds:

| Tab | Green | Yellow | Red |
|---|---|---|---|
| Gap Violations | `\|dev\| ≤ 2` | `2 < \|dev\| ≤ 10` | `\|dev\| > 10` |
| Overlapping Visuals | (n/a) | `0 < overlap_px ≤ 50` | `overlap_px > 50` |
| Duplicate Layer | (n/a) | always yellow | (n/a) |
| Row Misalignment | `dev ≤ 2` | `2 < dev ≤ 10` | `dev > 10` |
| Horizontal Spacing | `\|dev\| ≤ 2` | `2 < \|dev\| ≤ 10` | `\|dev\| > 10` |

Tag styles configured once in `app._configure_tags()`:

| Tag | Background | Foreground |
|---|---|---|
| `sev_green` | `#d1f7c4` | `#1b5e20` |
| `sev_yellow` | `#fff3cd` | `#664d03` |
| `sev_red` | `#f8d7da` | `#842029` |

**Rationale**: Threshold values match user's existing mental model from
the dashboard. RGB values are taken from Bootstrap-5 alert palette,
which is legible on both light and dark Tk themes (verified manually).
Tag-based styling lets us toggle without redrawing widgets.

**Alternatives considered**:

- Configurable thresholds via JSON: YAGNI for v1, can be added later.
- Per-cell color (only the deviation column): rejected — Treeview's
  ttk theming makes per-cell tags unreliable; whole-row tag works
  consistently.

---

## D6. Recents storage & schema (US6)

**Decision**: Module `pbir_validator.gui.recents` exposes:

- `recents_path() -> Path` → `%APPDATA%\pbir_validator\recents.json` on
  Windows, `~/.config/pbir_validator/recents.json` elsewhere.
- `load() -> list[str]` → reads JSON, returns `data["recent"]`, or `[]`
  on FileNotFoundError / JSONDecodeError / KeyError.
- `record(path: str) -> list[str]` → de-dup + push-to-front + truncate
  to 5, write back, return new list.

Schema (also captured in `contracts/recents-schema.json`):

```json
{
  "type": "object",
  "properties": {
    "recent": {
      "type": "array",
      "maxItems": 5,
      "items": {"type": "string"}
    }
  },
  "required": ["recent"]
}
```

**Rationale**: `%APPDATA%` is the standard Windows per-user mutable
location; survives uninstall/reinstall; never collides with system
state. Per-platform path mirrors stdlib conventions used by `pip`,
`black`, and others. Single-key schema gives us room to add fields
later (e.g., last-used filters) without migration.

**Alternatives considered**:

- `~/.pbir_validator.json` — pollutes `$HOME` and confuses dotfile
  managers.
- `winreg` — overkill for a 5-string list.
- TOML/YAML — no stdlib YAML; TOML is read-only in stdlib until 3.11,
  and we need write.

---

## D7. Context-menu architecture (US2)

**Decision**: One module-level `tk.Menu` per tab built lazily in
`app._build_context_menu(tree, columns)`. Bind `<Button-3>` (Windows
right-click) to a handler that selects the row under the cursor and
posts the menu. Menu items:

- "Open page in Power BI Desktop" — calls `_open_in_pbi(report_root)`.
- "Copy row" — joins selected row cells with `\t` and writes to
  clipboard via `widget.clipboard_clear() + widget.clipboard_append()`.

**Rationale**: One menu instance reused across right-clicks is the
idiomatic Tk pattern. Cell-tab-separated clipboard format is paste-ready
into Excel/Notion/Slack tables.

**Alternatives considered**:

- A single global menu with conditional disable: rejected — items differ
  per tab in future (we don't add per-tab items now, but the structure
  is open).
- Custom popup window: rejected — `tk.Menu` is built for this.

---

## D8. Test fixture for US1 hotfix

**Decision**: Create `tests/fixtures/duplicate-layer-page.Report/`
containing `definition.pbir`, `pages/page-with-duplicates/page.json`,
and two same-type `visual.json` files at y=322.7 and y=343.0 (same x,
both pivotTables). Regression test loads this report and asserts (a)
both visuals appear in analyzer output and (b) at least one
`DuplicateLayer` row is emitted with `delta_y` ≈ 20.3.

**Rationale**: A concrete, committed fixture future-proofs against
regressions. Synthetic data avoids licensing concerns of using the
user's real FY26 report in tests.

**Alternatives considered**:

- Mock the reader: rejected — analyzer and reader are tightly coupled
  by design; integration test gives more confidence.
- Use real FY26 report: rejected — too large, internal data, version-
  control hostile.

---

## Open Items

None. All clarifications resolved (5 questions answered in spec).

## Ready for Phase 1

Constitution Check passed. Proceeding to data-model, contracts, and
quickstart.
