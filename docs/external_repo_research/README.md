# External Repository & Donor Research

This directory contains feature-oriented external repository and donor research
for the Modern Minecraft Function Compiler.

Donor and external mod research is advisory: it explains how other systems
approach function optimization, entity access, and command scheduling, but
it never substitutes for differential runtime evidence against official
Minecraft 26.3.

## Directory Layout

| Path | Purpose |
|---|---|
| [`feature-index.md`](feature-index.md) | Maps compiler feature concerns to relevant external mods, donors, and datapacks. |
| [`reports/bellows-mod-investigation.md`](reports/bellows-mod-investigation.md) | Detailed analysis of Bellows 1.1.2/1.1.3 optimizations, entity NBT filtering, and adapter needs. |
| [`reports/prior-compiler-projects.md`](reports/prior-compiler-projects.md) | Comparative architecture analysis of prior compilers (MCFC, Mercury). |
| [`reports/datapack-workloads.md`](reports/datapack-workloads.md) | Workload screening and profiling of real-world datapacks (Vein Miner, etc.). |

## Maintenance Rules

- Keep donor reports separate from maintained compiler reference documentation.
- When an optimization pattern from a donor is adopted, document the compiler's
  implementation in `docs/reference/features/` and retain external analysis here.
- Any behavioral divergence introduced by third-party mods requires a verified
  adapter restoring vanilla semantics or conservative fallback.
