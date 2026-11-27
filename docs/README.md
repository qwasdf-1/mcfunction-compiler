# Function Compiler Documentation

This directory contains the human-readable documentation for the Modern Minecraft
Function Compiler. Runtime truth still lives in code, bytecode inspection,
Mixins, server logs, differential traces, and verified benchmark results.

## Start Here

| Document | Purpose |
|---|---|
| [`project-reference.md`](project-reference.md) | Scope, target, evidence labels, and source-of-truth map. |
| [`current-state.md`](current-state.md) | Present prototype behavior, verified evidence, and matrix status. |
| [`architecture.md`](architecture.md) | Provisional runtime path, ownership, and invariants. |
| [`architecture-decisions.md`](architecture-decisions.md) | Durable architectural decisions and tradeoffs. |
| [`verification.md`](verification.md) | Development loop, testing evidence, and parity gates. |
| [`benchmarking.md`](benchmarking.md) | Shared performance experiment protocol and reporting contract. |
| [`documentation-layout.md`](documentation-layout.md) | Canonical documentation taxonomy, authority order, and lifecycle rules. |
| [`reference/features/inventory.md`](reference/features/inventory.md) | Repo-wide maintained feature and prototype inventory. |
| [`reference/stack-aliases.md`](reference/stack-aliases.md) | Abbreviated Fabric mod-stack labels used by benchmark and compatibility evidence. |

## Documentation Layers

- **[`reference/`](reference/README.md):** Curated, present-tense feature and system references.
  - [`reference/features/`](reference/features/inventory.md): Maintained specifications for literal ScoreAdd, fused interpreted regions, ASM bytecode emission, selective macro arguments, command quota scheduling, and reload lifecycle.
- **[`v1/`](v1/README.md):** Version 1 milestone planning, roadmap, and active specifications.
  - [`v1/plans/`](v1/plans/README.md): Active implementation specifications and companion test matrix.
- **[`external_repo_research/`](external_repo_research/README.md):** Feature-oriented donor research and external mod investigations (Bellows, Vein Miner, MCFC, Mercury, etc.).
- **[`research/`](research/README.md):** Evidence, research methods and the [compiler research history](research/compiler-history.md).
- **[`archive/`](archive/README.md):** Canonical categorized historical records, audit snapshots, and prior proposals.
- **[`generated/`](generated/documentation-index.md):** Programmatically generated structure, symbol navigation, feature index, and link verification aids.

## Update Order

When a pass changes repo behavior:
1. Update component reference in `docs/reference/features/` and verified status in `docs/current-state.md`.
2. Update active plan or test matrix in `docs/v1/plans/`.
3. Record progress milestones in `CHANGELOG.md`.
4. Run `python3 scripts/doc_hygiene/generate_repo_truth.py` to regenerate programmatic navigation aids.
5. Verify documentation boundaries with `python3 scripts/check_doc_boundary.py`.
