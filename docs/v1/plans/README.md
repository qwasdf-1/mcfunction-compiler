# Registered Plans & Specifications

This index registers active planning artifacts and validation matrices for the
Modern Minecraft Function Compiler.

## Active Specifications

| Specification | Version | Status | Primary Focus |
|---|---|---|---|
| [`minecraft-function-compiler-research-and-implementation-spec-v0.1.md`](minecraft-function-compiler-research-and-implementation-spec-v0.1.md) | 0.1 | Active / Prototype | Comprehensive source investigation, architecture decision record, verification plan, and roadmap for Minecraft 26.3 Fabric server-side. |
| [`minecraft-function-compiler-test-matrix-v0.1.csv`](minecraft-function-compiler-test-matrix-v0.1.csv) | 0.1 | Active / In Progress | 84 test cases tracking semantic equivalence, frame discards, command quotas, reloads, and benchmark gates. |
| [`v1-production-roadmap.md`](v1-production-roadmap.md) | 1.0 | Complete / Verified | Production 1.0 roadmap covering tiered JIT amortization, parameterized macro bytecode, multi-hour server stress benchmarks, and promotion gates. |
| [`v1-production-validation-and-benchmarking-plan.md`](v1-production-validation-and-benchmarking-plan.md) | 1.0 | Complete / Verified | Comprehensive post-1.0 campaign: independent adversarial red-teaming, load/memory footprint analysis, extreme 5-datapack low-RAM stress testing, and comparative multi-mod benchmarks. |
| [`coverage-expansion-multi-entity-forking-spec.md`](coverage-expansion-multi-entity-forking-spec.md) | 1.1 | Complete / Verified | Post-1.0 coverage expansion: multi-entity selector inlined forking (`execute as @e[...] run <cmd>`) collapsing scheduler queue churn. |
| [`track-a-selector-forking-and-relational-traversal-spec.md`](track-a-selector-forking-and-relational-traversal-spec.md) | 1.1 | Complete / Verified | Track A coverage expansion: unified selector forking (`execute at @e[...]`) and entity relational traversal (`execute on <relation>`). |
| [`track-b-predicates-and-existence-checks-spec.md`](track-b-predicates-and-existence-checks-spec.md) | 1.0 | Complete / Verified | Track B coverage expansion: multi-entity existence checks (`execute if/unless entity`) and custom loot condition predicates (`execute if/unless predicate`). |
| [`track-c-common-state-machine-commands-spec.md`](track-c-common-state-machine-commands-spec.md) | 1.0 | Complete / Verified | Track C coverage expansion: common state machine commands as terminal executables (`tag`, `tp` / `teleport`, `kill`). |
| [`track-d-data-copying-and-compound-transfer-spec.md`](track-d-data-copying-and-compound-transfer-spec.md) | 1.0 | Complete / Verified | Track D coverage expansion: compound transfer (`data modify storage set from`) and numeric capture (`execute store storage`). |
| [`track-e-direct-function-inlining-spec.md`](track-e-direct-function-inlining-spec.md) | 1.0 | Complete / Verified | Track E coverage expansion: direct function inlining and leaf call compaction. |
| [`track-f-macro-ast-pre-tokenization-and-template-compilation-spec.md`](track-f-macro-ast-pre-tokenization-and-template-compilation-spec.md) | 1.0 | Complete / Verified | Track F coverage expansion: macro AST pre-tokenization, expanded parameter LRU caching, and template compilation. |
| [`track-g-data-query-and-redirection-spec.md`](track-g-data-query-and-redirection-spec.md) | 1.0 | Complete / Verified | Track G coverage expansion: data query (`data get`) and scoreboard/storage redirection fast-path. |
| [`track-h-block-world-interaction-and-state-predicates-spec.md`](track-h-block-world-interaction-and-state-predicates-spec.md) | 1.0 | Complete / Verified | Track H coverage expansion: block state/tag predicates and fast inlined `setblock`. |
| [`track-i-modern-item-predicates-spec.md`](track-i-modern-item-predicates-spec.md) | 1.0 | Complete / Verified | Track I coverage expansion: modern item and equipment predicates (`execute if/unless items`). |
| [`track-j-visual-and-sound-event-batching-spec.md`](track-j-visual-and-sound-event-batching-spec.md) | 1.0 | Complete / Verified | Track J coverage expansion: visual and sound event batching (`particle`, `playsound`). |
| [`track-k-tail-call-recursive-loop-compaction-spec.md`](track-k-tail-call-recursive-loop-compaction-spec.md) | 1.0 | Complete / Verified | Track K coverage expansion: tail-call recursive loop compaction and in-place iteration. |
| [`track-l-bossbar-management-and-redirection-spec.md`](track-l-bossbar-management-and-redirection-spec.md) | 1.0 | Complete / Verified | Track L coverage expansion: bossbar management and redirection. |
| [`track-m-entity-status-effects-spec.md`](track-m-entity-status-effects-spec.md) | 1.0 | Complete / Verified | Track M coverage expansion: entity status effects (`effect give/clear`). |
| [`track-n-spatial-context-modifiers-spec.md`](track-n-spatial-context-modifiers-spec.md) | 1.0 | Complete / Verified | Track N coverage expansion: spatial context modifiers (`in`, `align`, `facing`). |
| [`track-o-player-hud-and-title-dispatch-spec.md`](track-o-player-hud-and-title-dispatch-spec.md) | 1.0 | Complete / Verified | Track O coverage expansion: player HUD and title dispatch (`title`). |
| [`track-p-item-component-and-inventory-mutation-spec.md`](track-p-item-component-and-inventory-mutation-spec.md) | 1.0 | Complete / Verified | Track P coverage expansion: item component and inventory mutation (`item replace/modify`). |

| [`compiler-coverage-widening-proposal-v0.1.md`](compiler-coverage-widening-proposal-v0.1.md) | 0.1 | Proposal / Awaiting decision | Scoping for a second promoted optimization: the four mechanisms' recorded verdicts, the diagnosis that the specializers do not fire on real-pack shapes, and candidate hypotheses (metrics-only inventory, selective-macro extension, fork-interior fusion, storage-holder ScoreAdd) each with a falsifiable prediction, code surface, and validating campaign. |

## Retirement & Compaction Policy

When a specification is superseded:
1. Extract any remaining unverified hypotheses, permanent decisions, or known gaps into `docs/reference/` and `docs/architecture-decisions.md`.
2. Move the retired plan draft to `docs/archive/plans/`.
3. Update this index to point to the active successor.
