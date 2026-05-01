# Contract: PBIR Filesystem & JSON Paths

The exact paths the tool reads from and writes to. Any deviation in a target report is
treated as an error (per spec Assumptions), not silently guessed.

## Filesystem layout (input)

```text
<report>.Report/                                  # passed via --report
└── definition/
    └── pages/                                    # MUST exist; otherwise NotAPbirError
        ├── pages.json                            # not read in v1 (page order is by folder)
        └── <page-id>/                            # one folder per page
            ├── page.json                         # READ for displayName, height, width
            └── visuals/                          # may be absent (= zero-visual page)
                └── <visual-id>/
                    ├── visual.json               # READ for position.* and visualType
                    └── (other files)             # ignored
```

## JSON paths read (consumed)

### `page.json`

| JSON pointer | Type | Used as |
|---|---|---|
| `/displayName` | string | `Page.display_name` |
| `/height` | number | `Page.height` (page-boundary check) |
| `/width` | number | `Page.width` |

Any of these missing → warn, fall back (`displayName` → folder id; `height`/`width` → 0,
which disables the boundary check for that page and triggers a non-fatal warning).

### `visual.json`

| JSON pointer | Type | Used as |
|---|---|---|
| `/position/x` | number | `Visual.x` |
| `/position/y` | number | `Visual.y` |
| `/position/width` | number | `Visual.width` |
| `/position/height` | number | `Visual.height` |
| `/visual/visualType` | string | `Visual.visual_type` |
| `/parentGroupName` | string \| absent | `Visual.parent_group_name` |

Missing `position` object, or non-numeric `position.y` / `position.height` →
the visual is **skipped for analysis** with a warning naming the file path; in fix mode
the writer **refuses** to touch a file it could not first parse cleanly (FR-023, edge
case).

Missing `/visual/visualType` → `Visual.visual_type = "unknown"` and a single warning is
emitted naming the page and visual id (spec edge case). The visual still participates in
row grouping.

## JSON paths written (produced)

The fix mode writes to **exactly one** field per visual it shifts:

| JSON pointer | Operation |
|---|---|
| `/position/y` | replaced with the new float value |

**No other field is ever read-then-rewritten** by the writer. The writer:

1. Reads the original `visual.json` bytes.
2. Parses to a `dict` (preserving insertion order — Python 3.7+ guarantee).
3. Replaces `data["position"]["y"]`.
4. Re-serializes with `json.dumps(data, indent=<detected>, ensure_ascii=False)`.
5. Restores the original trailing newline (or its absence).
6. Writes via `tempfile.NamedTemporaryFile(dir=<same dir>, delete=False)`,
   `f.flush()`, `os.fsync(f.fileno())`, then `os.replace(tmp_path, target_path)`.

This sequence guarantees:

- Every key not at `/position/y` is byte-identical to the original (FR-010).
- Key insertion order is preserved (Principle II diff-friendliness).
- A killed process never leaves a partial file (FR-023, SC-004).

## Filesystem writes

The tool ever writes only these locations:

- The `visual.json` files identified by the fix plan (in-place, atomic).
- The single `conf.md` rules file at `--out` (default `<report>/conf.md`) — only in
  `learn` mode.

The tool **never**:

- Creates new directories under the report.
- Deletes any file.
- Renames any file other than the temp-→-target step of `os.replace`.
- Touches `pages.json`, `page.json`, or any non-`visual.json` file.
