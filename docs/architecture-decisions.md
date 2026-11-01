# Architecture decisions

No production architecture decisions have been accepted yet.

## Correctness contract

Vanilla Minecraft 26.3 behavior is the semantic reference for every
optimization. An optimization must preserve observable results, command
ordering, return values, failures, quota boundaries, callbacks, and reload
behavior. On modded stacks, compiler-on must also match compiler-off on that
same stack; a compatibility adapter must preserve the vanilla outcome for the
operation it adapts. A mod's existing divergence from vanilla is recorded as a
compatibility defect, not as permission for the compiler to introduce another
behavior.

## Proposed decisions

| ID | Proposal | Status | Evidence required |
|---|---|---|---|
| ADR-001 | Wrap an ordinary function near construction, preserve the original action for fallback, and retain vanilla scheduling. | Provisional | Static 26.3 descriptors, five sequential changed-body/tag reloads, wrapper/tag identity, 16 direct-function state/RCON fixtures (including bounded recursion through fused and bytecode regions), fork sweeps, and flat/nested debug trace parity are verified. Compatibility-mod semantic execution, untested error/callback paths, concurrent/removing reloads, and wrapper-overhead measurement remain. |
| Backend | Compare specialized entries, resumable interpreted regions, and JVM bytecode. | Open | Controlled correctness and performance comparison. |

The detailed proposal and ADR template are in the [research and implementation
plan](v1/plans/minecraft-function-compiler-research-and-implementation-spec-v0.1.md).
Do not treat a proposal as an accepted implementation decision. Record future
decisions with target versions, alternatives, invariants, tests, benchmark data,
rollback strategy, and remaining risks.
