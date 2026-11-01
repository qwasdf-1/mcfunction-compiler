# Version 1 (v1) Planning & Specifications

This directory contains version 1 planning artifacts, specifications, and
test matrices for the Modern Minecraft Function Compiler.

## Directory Layout

| Path | Purpose |
|---|---|
| [`plans/README.md`](plans/README.md) | Registered plan index tracking active specifications and matrices. |
| [`plans/minecraft-function-compiler-research-and-implementation-spec-v0.1.md`](plans/minecraft-function-compiler-research-and-implementation-spec-v0.1.md) | Architectural specification, research baseline, and phased roadmap (Version 0.1). |
| [`plans/minecraft-function-compiler-test-matrix-v0.1.csv`](plans/minecraft-function-compiler-test-matrix-v0.1.csv) | 84-case machine-readable test matrix covering P0 semantic and P1 performance gates. |
| [`plans/v1-production-roadmap.md`](plans/v1-production-roadmap.md) | Production 1.0 roadmap covering tiered JIT amortization, parameterized macro bytecode, multi-hour server stress benchmarks, and promotion gates. |

## Relationship to Current Truth

Specifications and test matrices represent **research baselines and testing
plans**. They do not constitute implementation proof until differential
runtime evidence is verified and documented in `docs/current-state.md` and
`docs/reference/`.
