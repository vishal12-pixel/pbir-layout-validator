# Research: Horizontal Spacing Auto-Fix

## R1: How does the existing Y-shift planning work, and how should X-shifts integrate?

**Decision**: X-shift planning is a separate pass that runs after Y-shift
planning within `plan_fixes()`. H-spacing issues are independent of vertical
gap violations — they operate within a single row, not between rows.

**Rationale**: The existing `plan_fixes()` iterates violations per page and
plans cumulative Y-deltas. H-spacing issues are intra-row (same row, same
type) and only affect `position.x`. Keeping them as a separate pass avoids
entangling two orthogonal concerns. The function returns a unified `Shift`
list containing both Y-only and X-only (or combined) shifts.

**Alternatives considered**:
- Interleaving X and Y shifts in a single loop: rejected because Y-shifts
  cascade downward across rows while X-shifts are row-local. Mixing them
  adds complexity for no benefit.
- A separate `plan_hspacing_fixes()` function called independently: adopted
  as the internal structure, but the outer `plan_fixes()` orchestrates both.

## R2: How should cumulative X-shifts work within a row?

**Decision**: For each deviant gap in a row (left-to-right), shift the right
visual and all same-type peers further right in the row by `-deviation_px`.
Process gaps left-to-right so shifts accumulate correctly.

**Rationale**: The spec (FR-001) says "shift the right-side visual and all
same-type peers to its right." Processing left-to-right means a visual
shifted by gap #1's correction will also be shifted by gap #2's correction
if it is to the right of gap #2. This naturally equalizes all gaps to the
modal value.

**Algorithm**:
1. For each row, bucket visuals by `visual_type`.
2. For each type-bucket with ≥3 peers, sort by `x`.
3. Compute gaps: `gap[i] = peers[i+1].x - (peers[i].x + peers[i].width)`.
4. Compute modal gap (same logic as `find_row_hspacing_issues`).
5. For each gap deviating from modal: `correction = -(actual - modal)`.
6. Apply correction to peers[i+1] and all peers to the right (cumulative).
7. Emit `Shift` objects with `old_x`, `new_x`, `delta_x` populated.

**Alternatives considered**:
- Recompute all positions from scratch (fixed starting x, modal gap):
  rejected because it would move ALL visuals, not just the deviant ones,
  causing unnecessary file writes and potentially breaking intentional
  x-offsets.

## R3: How should `write_visual_json` handle combined X+Y shifts?

**Decision**: Add an optional `new_x: float | None = None` parameter to
`write_visual_json`. When `new_x is not None`, mutate `position.x` in the
same atomic write as `position.y`. When only `new_x` is provided (no Y
change), `new_y` uses the visual's current `y`.

**Rationale**: FR-004 requires combined X+Y writes in a single atomic
operation. Making `new_x` optional preserves backward compatibility — all
existing callers pass only `new_y` and see no behavior change (FR-013).

**Alternatives considered**:
- Separate `write_visual_json_x` function: rejected (violates DRY; two
  near-identical atomic-write routines).
- A `mutations: dict` parameter: rejected (over-engineering for 2 fields).

## R4: How should the undo backup store X coordinates?

**Decision**: Extend the backup entry dict with optional `old_x` and `new_x`
keys. When restoring, if `old_x` is present, pass it to `write_visual_json`
as `new_x` to restore the original X coordinate.

**Rationale**: FR-007/FR-008 require byte-for-byte restoration of both
coordinates. The backup already stores `old_y`/`new_y`; adding `old_x`/`new_x`
is a minimal schema extension. Omitting the keys for Y-only shifts preserves
backward compatibility with existing backups.

**Alternatives considered**:
- Backup the entire visual JSON file: rejected (disk-heavy for large reports;
  overkill when only 1-2 fields change).

## R5: How should profile gating work for h-spacing fixes?

**Decision**: Add a `hspacing_fix` flag to profile metadata. Parse it from
profile `.md` files as a header comment (`hspacing_fix = true`). Default to
`false` when absent. The Strict profile sets it to `true`.

**Rationale**: FR-011/FR-012 require profile gating. The existing profiles
are `.md` files with gap rules; metadata is in the header comments. Adding a
key-value flag in the header comment section follows the existing pattern
(comments already contain descriptive metadata like `gap = 8 px`).

**Parsing approach**: Scan header lines (lines starting with `#`) for a
pattern like `hspacing_fix = true`. The `profiles.py` module already reads
profile files; it can extract this flag before passing to `parse_conf`.

**Alternatives considered**:
- YAML/TOML metadata block: rejected (adds parsing complexity for one boolean;
  profile files are simple `.md` with comments + rules).
- Hardcode per profile name: rejected (prevents Report-default profiles from
  opting in via `conf.md`).

## R6: Boundary checks for X-shifts

**Decision**: Before applying any X-shift in a row, check:
1. `new_x >= 0` for all affected visuals (FR-006).
2. `new_x + width <= page.width` for all affected visuals (FR-005).

If any visual fails either check, the entire row's h-spacing issue is marked
unfixable. Other rows/pages are unaffected.

**Rationale**: Consistent with the existing Y-shift boundary checking pattern
in `plan_fixes()`, which marks violations unfixable when `y + height > page.height`.

**Alternatives considered**:
- Partial fix (fix only some gaps in the row): rejected (would leave the row
  in an inconsistent state — some gaps equalized, others not).

## R7: Dependency on feature 005-power-features

**Decision**: This feature depends on 005-power-features for `profile_flags`
parameter in `plan_fixes()`, `HeightResize` model, and the GUI `fix_plan()`
controller's profile-aware planning. If 005 is not yet merged, the X-shift
planning function should be designed to work with or without `profile_flags`
(defaulting `hspacing_fix` to `false` when flags are absent).

**Rationale**: The GUI controller already references `profile_flags` in its
`fix_plan()` call. The X-shift feature should integrate with this existing
pattern rather than introducing a parallel mechanism.

**Alternatives considered**:
- Implement profile gating independently: rejected (would create merge
  conflicts with 005 and duplicate the profile-flags pattern).
