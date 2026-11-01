# Documentation Layout

This is the canonical documentation taxonomy for the Modern Minecraft Function
Compiler project. Runtime artifacts, Minecraft 26.3 server traces, bytecode
verification, Mixin inspection, and differential test results remain
implementation truth when prose disagrees.

## Authority Order

1. **Runtime truth:** `build/reports/runtime-probe/` artifacts, server logs,
   differential `/debug function` traces, bytecode class analysis, Mixin
   inspection, unit tests, and accepted benchmark results.
2. **Current reference:** `docs/project-reference.md`, `docs/current-state.md`,
   `docs/architecture.md`, `docs/architecture-decisions.md`,
   `docs/verification.md`, `docs/benchmarking.md`, and `docs/reference/`.
3. **Product/planning intent:** `docs/v1/README.md`, active plans and test
   matrices in `docs/v1/plans/`.
4. **Donor & external research:** `docs/external_repo_research/` (reports and
   indexes on Bellows, Brigadier, Mercury, Lithium, Moonrise, and third-party
   datapacks) and `docs/research/`.
5. **Generated aids and projections:** `docs/generated/`, structure maps, symbol
   navigation indexes, and verification crosswalks.
6. **Historical context:** `docs/archive/` and historical snapshots.

## Canonical Structure

```text
README.md                         repo entrypoint and read-next map
CHANGELOG.md                      readable closed-work timeline
CONTRIBUTING.md                   contribution and verification guidelines

docs/
  README.md                       documentation map
  documentation-layout.md         taxonomy, lifecycle, archive/delete rules
  current-state.md                compact present-tense repo reality
  project-reference.md            feature inventory with evidence refs
  architecture.md                 current architecture and authority model
  architecture-decisions.md       durable decisions and tradeoffs
  verification.md                 bounded evidence loop and verification protocol
  benchmarking.md                 performance experiment protocol and report contract
  reference/                      current feature and system references
    features/                     maintained feature inventory and component docs
      inventory.md                repo-wide feature inventory
      scoreboard-specialization.md literal ScoreAdd prototype specification
      fused-regions.md            interpreted fused region execution specification
      emitted-bytecode.md         ASM emitted bytecode region specification
      selective-macro-arguments.md custom entity data macro argument specification
      command-quota-and-scheduler.md 26.3 ExecutionContext and quota model
      lifecycle-and-reload.md     datapack reload and failure rollback semantics
  v1/                             milestone charter, roadmap, active plans, audits
    plans/                        active specifications and test matrices
  external_repo_research/         feature-oriented donor research and reports
    reports/                      maintained donor and compatibility reports
  archive/                        canonical categorized historical records
    audits/                       historical audit snapshots
    plans/                        superseded plan drafts
    benchmarks/                   prior exploratory benchmark runs
  generated/                      regenerated navigation and structure aids
```

## Document States

- **Current truth** belongs in `project-reference.md`, `current-state.md`,
  `architecture.md`, `verification.md`, and `docs/reference/`. Maintained feature
  inventories and detailed component specifications live in `docs/reference/features/`.
- **Durable decisions** belong in `architecture-decisions.md`.
- **Planning intent** belongs in `docs/v1/` and `docs/v1/plans/`; it is not
  implementation proof until verified by runtime differential tests.
- **Donor research** belongs in `docs/external_repo_research/`; it is advisory and
  explains third-party mod patterns or datapack quirks, but does not prove compiler
  behavior.
- **Historical snapshots** belong in `docs/archive/`.
- **Generated aids** live under `docs/generated/` and are produced programmatically
  by doc-generation tooling.

## Archive Categories

Use the narrowest category:

- `audits/`: historical audit snapshots and point-in-time sanity scans.
- `plans/`: superseded milestone plans, initial proposals, and draft specs.
- `benchmarks/`: historical exploratory benchmark runs prior to calibration.
- `reviews/`: historical third-party review notes and audit run logs.

## Placement Rules

- Feature specifications go in `docs/reference/features/` and are indexed in
  `docs/reference/features/inventory.md`.
- Present implementation status lives in `docs/current-state.md`.
- Durable architectural decisions live in `docs/architecture-decisions.md`.
- Active plans and the companion test matrix live in `docs/v1/plans/`.
- Maintained donor/mod research lives in `docs/external_repo_research/`.
- Generated structural and symbol inventories live in `docs/generated/`.
- Local scratch and operator logs remain git-ignored and boundary-checked.

## Lifecycle Rules

1. Update the narrowest current authority document first: component spec for
   feature mechanics, `current-state.md` for verified status, `verification.md`
   for probe commands.
2. Before archiving, extract still-current behavior, decisions, blockers, or
   test claims into the active reference layer.
3. Archive unique historical evidence before compaction.
4. Delete only generated caches, temporary server test runs, scratch logs, and
   exact duplicates.
5. Keep active docs present-tense. Progress chronology belongs in `CHANGELOG.md`
   or archive records.
6. Regenerate `docs/generated/` after path, structure, or tooling changes.

## Maintenance Commands

```bash
# Generate ground-truth documentation aids
python3 scripts/doc_hygiene/generate_repo_truth.py

# Verify documentation boundaries (no local-only references)
python3 scripts/check_doc_boundary.py

# Run unit tests
python3 -m unittest discover -s tests -p 'test_*.py'
```
