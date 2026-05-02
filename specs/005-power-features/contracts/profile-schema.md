# Contract — Profile File Grammar

Every file under `pbir_validator/profiles/*.md` MUST be a valid input
to the existing `pbir_validator.conf.parse_conf` function. This contract
fixes the *content* the three shipped profiles must encode (FR-051) and
documents the parser's input grammar by reference.

---

## Grammar (by reference)

The file format is **identical to the existing `conf.md` markdown
grammar** parsed by `pbir_validator.conf.parse_conf`. Profile files do
not extend the grammar; they only constrain the *values* used by the
shipped `Strict` / `Standard` / `Relaxed` files.

A profile is a Markdown document containing one or more rule blocks of
the form already documented in `specs/001-pbir-layout-validator/`. The
parser ignores headings, paragraphs, and any text outside recognized
rule blocks, so each profile is also a readable human document.

## Required values

The three shipped profiles MUST encode the following thresholds (per
the spec clarification, session 2026-05-02):

| Profile name (display) | File             | gap (px) | overlap_tolerance (px) | h_spacing_min (px) | row_align_tolerance (px) |
|------------------------|------------------|---------:|-----------------------:|-------------------:|-------------------------:|
| Standard               | `standard.md`    |        8 |                      0 |                  8 |                        2 |
| Strict                 | `strict.md`      |        4 |                      0 |                  4 |                        1 |
| Relaxed                | `relaxed.md`     |       16 |                      2 |                 16 |                        4 |

`Standard` MUST be byte-identical (in parsed-rule terms) to the current
built-in defaults so users who never touch the dropdown observe zero
behavior change (FR-054).

## Discovery

`profiles.list_profiles()` MUST return:

- Keys are the **display names** (`Standard`, `Strict`, `Relaxed`) in
  that exact case.
- Values are absolute `Path` objects resolved through
  `importlib.resources.files("pbir_validator.profiles") / "<lower>.md"`.
- A fourth key `Report-default` → `<report_root>/conf.md` MUST be added
  when, and only when, that file exists on disk (FR-055).
- Insertion order MUST be: `Standard`, `Strict`, `Relaxed`,
  `Report-default` (when present). The combobox renders this order.

## Parsing

`profiles.load_profile(name, report_root=None)` MUST:

1. Resolve `name` via `list_profiles(report_root)`. Unknown names raise
   `KeyError`.
2. Call `pbir_validator.conf.parse_conf(profile_path)` and return the
   result unchanged. Errors propagate as today (`ConfParseError`).

## Stability

The three shipped `.md` files are part of the public contract. Changing
their threshold values is a behavior change for every user and MUST be
treated as a constitutional minor revision (Principle III: UX
consistency — predictable defaults).

## Example minimum content (`standard.md`)

```markdown
# Standard profile — pbir_validator built-in defaults

Vertical gap rule (default visual pair):

- gap: 8 px
- overlap_tolerance: 0 px

Row layout:

- row_align_tolerance: 2 px
- h_spacing_min: 8 px
```

The exact rule-block syntax is whatever `parse_conf` already accepts;
the table above is the normative content the values must encode after
parsing.
