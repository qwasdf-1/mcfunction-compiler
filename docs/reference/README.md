# Function Compiler Reference Documentation (v1.0)

This directory contains curated, authoritative reference documentation for the
Modern Minecraft Function Compiler on Minecraft Java Edition 26.3 Fabric dedicated servers.

Runtime artifacts, JVM execution traces, bytecode inspection, Mixin contracts, and
differential test traces remain implementation truth when prose disagrees.

---

## Reference Layers

| Document | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Technical architecture, compilation pipeline, hook ownership, and memory invariants. |
| [`configuration.md`](configuration.md) | Production JSON configuration schema (`config/function-compiler.json`) and `/functioncompiler` admin commands. |
| [`benchmarks/README.md`](benchmarks/README.md) | Authoritative benchmark hub: adversarial red-teaming, memory footprint, extreme 5-datapack stress tests, and comparative mod matrix. |
| [`features/inventory.md`](features/inventory.md) | Repo-wide maintained feature inventory covering optimizations, hooks, and verification status. |
| [Typed compiler](features/typed-compiler.md) | Opt-in profile, typed mixed IR and effect-bounded reuse. |
| [`features/fused-regions.md`](features/fused-regions.md) | Multi-command queue compaction, Stage 1A–1D specializations, and error continuation. |
| [`features/selective-macro-arguments.md`](features/selective-macro-arguments.md) | Selective argument extraction for entity and storage macros, bypassing full compound serialization. |
| [`features/emitted-bytecode.md`](features/emitted-bytecode.md) | Parameterized hidden ASM classes, `CONSTRUCTOR_CACHE`, tiered JIT engine, and Metaspace lifecycle. |
| [`features/scoreboard-specialization.md`](features/scoreboard-specialization.md) | Objective pre-resolution, arithmetic mutations, operations, predicates, and store redirection. |
| [`features/command-quota-and-scheduler.md`](features/command-quota-and-scheduler.md) | Exact 26.3 `ExecutionContext` queue model, fork limits 1–12, sequence limits 0–16, and frame discards. |
| [`features/lifecycle-and-reload.md`](features/lifecycle-and-reload.md) | Datapack reload generations, `#minecraft:load`, `#minecraft:tick`, and failed reload rollback. |

---

## Authority Rules

1. **Evidence-backed claims:** All feature documentation must link to exact
   source classes, Mixins, test fixtures, and verified runtime reports.
2. **Present-tense status:** Descriptions reflect currently verified behavior.
   Proposals and roadmap items belong in `docs/v1/plans/`.
3. **Strict Parity Gate:** Optimizations must preserve 100% exact differential
   parity against vanilla Minecraft across all tested configurations.
