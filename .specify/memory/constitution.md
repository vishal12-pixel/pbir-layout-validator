<!--
SYNC IMPACT REPORT
==================
Version change: (initial) → 1.0.0
Bump rationale: Initial ratification of project constitution (MAJOR baseline).

Modified principles: N/A (initial creation)
Added sections:
  - Core Principles (4): Code Quality, Testing Standards, User Experience
    Consistency, Performance Requirements
  - Additional Constraints (Stack & Scope)
  - Development Workflow & Quality Gates
  - Governance

Removed sections: None

Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (Constitution Check section is
        principle-agnostic and remains compatible; no edits required)
  - ✅ .specify/templates/spec-template.md (no constitution-specific clauses;
        compatible)
  - ✅ .specify/templates/tasks-template.md (task categories already cover
        setup/test/implementation; compatible — testing tasks must be
        treated as REQUIRED for this project per Principle II)
  - ✅ .specify/templates/checklist-template.md (generic; compatible)

Follow-up TODOs: None
-->

# PBIR Layout Validator & Fixer Constitution

## Core Principles

### I. Code Quality (Pythonic & Minimal)

Code MUST be idiomatic Python and optimized for readability over cleverness.

- The tool MUST run on the Python standard library only. No third-party
  runtime dependencies are permitted; `pytest` is allowed as a development-
  only dependency.
- Functions MUST follow single-responsibility: one function, one purpose.
  Functions exceeding ~40 lines or mixing parsing, calculation, and I/O
  MUST be decomposed.
- Names MUST be explicit and domain-aligned (e.g., `compute_vertical_gap`,
  `parse_visual_container`). Abbreviations and one-letter names are
  prohibited outside tight local scopes.
- Over-engineering is forbidden: no speculative abstractions, no plugin
  frameworks, no class hierarchies where a function suffices. YAGNI is
  enforced at review time.

**Rationale**: PBIR validation is a focused, file-system-bound task. A
small, dependency-free CLI is faster to install, easier to audit, and
avoids supply-chain risk in enterprise Power BI environments.

### II. Testing Standards (NON-NEGOTIABLE)

All parsing and calculation logic MUST be covered by automated tests
before merge.

- Unit tests MUST be written with `pytest` for every function that parses
  PBIR JSON or computes layout metrics (positions, gaps, alignments).
- Integration tests MUST exercise the CLI end-to-end against committed
  sample PBIR fixture data stored under `tests/fixtures/`.
- Core logic (parsing, gap calculation, fix generation) MUST maintain
  ≥80% line coverage. Coverage below this threshold blocks merge.
- Bug fixes MUST add a regression test that fails before the fix and
  passes after.

**Rationale**: PBIR files are structurally complex and silently break
reports when malformed. Tests with realistic fixtures are the only
reliable defense against shipping report-corrupting changes.

### III. User Experience Consistency

Every user-facing surface MUST present a predictable, unambiguous
experience across all operations.

- **Terminal/CLI surfaces**: Output MUST use colored terminal status:
  green for success, yellow for warnings, red for errors. Color MUST
  auto-disable when stdout is not a TTY or when `NO_COLOR` is set.
- **Terminal/CLI surfaces**: Commands MUST follow the consistent flag
  structure: `--validate`, `--fix`, `--learn`. New top-level CLI
  operations MUST extend this pattern.
- **Graphical (GUI) surfaces**: MUST preserve the *spirit* of the CLI
  conventions — predictable layout, dry-run-first mutation, errors that
  include the offending file path — but are not bound to flag syntax or
  ANSI colors. Every GUI capability MUST already be reachable from the
  CLI; the CLI remains the primary, equally-supported interface.
- Error messages (CLI or GUI) MUST include the offending file path and,
  where applicable, the JSON pointer or line number, plus a one-line
  remediation hint.
- Any operation that mutates files MUST support `--dry-run` and MUST
  default to a preview when `--fix` is invoked without explicit
  confirmation (`--apply` or interactive `y/N`).

**Rationale**: Users run this tool against authored reports they cannot
afford to lose. Predictable flags, clear diagnostics, and dry-run-first
defaults make the tool safe to use in CI and on local machines alike.

### IV. Performance Requirements

The CLI MUST remain fast enough for interactive use on realistic reports.

- Validating a 50-page PBIR report MUST complete in under 5 seconds on a
  developer-class laptop (measured wall-clock, warm filesystem cache).
- JSON files MUST be opened and parsed lazily on a per-file basis.
  Loading the entire report into memory up front is prohibited; iterate
  pages and visuals on demand.
- Cold CLI startup (entry point to first log line) MUST stay under
  200 ms. Heavy imports MUST be deferred behind the subcommand that
  needs them.
- Performance regressions MUST be caught: a benchmark fixture exercising
  the 50-page target MUST exist under `tests/` and be runnable via a
  documented command.

**Rationale**: Layout validation is most useful when developers run it
repeatedly while iterating on a report. Slow startup or memory bloat
would push it out of the inner loop.

## Additional Constraints

**Stack & Scope**

- Language: Python 3.11+ (standard library only at runtime).
- Packaging: Single CLI entry point exposed via `python -m pbir_validator`
  and a console script.
- Platform: MUST run on Windows, macOS, and Linux without code branching
  beyond `pathlib` and `os` portability.
- Out of scope: editing PBIX binaries, rendering reports, and network
  calls of any kind.

## Development Workflow & Quality Gates

- Every change MUST pass: unit tests, integration tests, coverage
  threshold (≥80% on core logic), and a `--dry-run` smoke test against
  the bundled fixture report.
- Pull requests MUST state which principle(s) the change touches and how
  compliance was verified. Violations MUST be justified in a "Complexity
  Tracking" section of the plan and approved before merge.
- Any new external runtime dependency requires a constitution amendment
  (MAJOR bump) — it is not a routine review decision.

## Governance

- This constitution supersedes ad-hoc conventions. When guidance elsewhere
  conflicts with this document, this document wins.
- Amendments require: (1) a PR editing this file, (2) an updated Sync
  Impact Report at the top, (3) propagation to dependent templates under
  `.specify/templates/`, and (4) approval from a project maintainer.
- Versioning policy (semantic):
  - **MAJOR**: Removing a principle, redefining it incompatibly, or
    adding a runtime dependency.
  - **MINOR**: Adding a new principle or materially expanding an existing
    one.
  - **PATCH**: Wording, clarifications, or non-semantic refinements.
- Compliance reviews: every PR reviewer MUST verify the change against
  the Core Principles checklist before approval.

**Version**: 1.0.0 | **Ratified**: 2026-05-01 | **Last Amended**: 2026-05-01
