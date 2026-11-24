# COMPILER-IR-035 — Explicit typed-IR optimizer stage and canonical opcodes

**Status (2026-11-23/24): IMPLEMENTED; NATIVE SEMANTIC GATE ACCEPTED. Performance gain NOT established; no production promotion.** Research branch `work/compiler-coverage`, draft PR #10. The typed-IR optimization pipeline is now explicitly
`validated Brigadier commands → TypedScoreIR.Program → TypedIROptimizer.Plan → interpreter/ASM code generation`.
No engine-level Mixin or event-specific behavior was introduced, and no default compiler flag changed.

## Motivation and scope

The previous optimizer investigations increasingly targeted expensive Minecraft internals without demonstrating a reusable compiler transformation. IR-034 safely hoisted immutable instruction arrays in the two existing typed-IR backends. IR-035 adds an explicit **compiler pass** instead of adding another special-case engine hook.

A typed command is an observable boundary (per-source command position, scoreboard mutation and listeners, command quota, trace, feedback, exception/fallback, and optional reentrantly enqueued work). Even adjacent apparently redundant commands must not be removed, reordered, folded into one write, or assigned a cross-command cached scoreboard value without a stronger whole-runtime proof. Accordingly, IR-035 introduces **single-instruction, structure-only canonicalization**.

## Implementation

- New `TypedIROptimizer` consumes a fully validated `TypedScoreIR.Program` and returns an immutable `Plan` containing **exactly one Step per original instruction**, in the same identity and order. Its constructor rejects count mismatch, replacement/reordering, unsupported terminals and unproved non-observable boundaries. Each Step retains its exact original source Instruction for runtime fallback and feedback.
- Mutations `add amount` and `remove amount` become the canonical `ADD_LITERAL` opcode with signed 32-bit delta `amount` / `-amount`; `set amount` becomes `SET_LITERAL`. Java 32-bit signed overflow semantics are preserved. Importantly, REMOVE remains REMOVE in the **original** instruction used for command-specific feedback and error behavior.
- Supported binary score operations `=`, `+=`, `-=`, `*=` become `ASSIGN_SCORE`, `ADD_SCORE`, `SUBTRACT_SCORE`, `MULTIPLY_SCORE`. No source scoreboard values are constant-folded or cached. This is type/opcode predecoding, not algebraic removal of commands.
- A `Conditional` is admitted as **one original command** with its preclassified terminal; native guard checking and the original quota/trace semantics remain in `TypedScoreIRRuntime.State.begin`. A false guard still has its original observable behavior.
- Both backends consume **the same optimized Plan**, after lowering and before emitted execution. `Interpreted` allocates its plan vector once at function construction and executes preclassified opcodes. `TypedScoreIRBytecode` emits the same direct ScoreAccess JVM operations using plan opcodes, without inspecting the original terminal shape for each bytecode instruction during compilation. The already implemented IR-034 hoisting remains.
- Runtime `State.begin/finish`, `QueuedTail`, original vanilla fallbacks and `MixedFunctionIR` opaque barriers are unchanged. A reentrant callback still yields onto the exact original source Instruction chain, rather than forcing optimized execution across callback work.

These transformations are deliberately modest; they establish a correct **analysis/optimize/emit separation** with an identity-preserving pass, not a guaranteed CPU improvement. They do not claim that signed-delta canonicalization is faster than the previous ASM-generated code (which already used a signed constant).

## Semantic admission gates

1. Java 25 Minecraft 26.3 Fabric build and `tests/test_typed_ir035.py` optimizer contracts, plus IR-034/008/013 regression contracts, pass.
2. The native IR-008 suite completes all four original/legacy-fused/typed-interpreter/typed-bytecode JVM modes with exact scoreboard, guarded condition, missing/read-only objective, overflow and partial command-quota parity.
3. The native IR-013 suite completes all six JVM modes: guarded bytecode/interpreter/direct scheduling must match vanilla's reentrant queue order and low-quota state, with deliberately unsafe controls still diverging where predeclared.
4. Original command source positions, count, feedback, quota, trace, errors, and fallback must be preserved. Generated JVM instructions must still invoke ScoreAccess directly instead of the original Brigadier callback for accepted terminals.

**No CPU performance promotion** occurs in IR-035. IR-033's failed A/A qualification bars causal claims for small runtime differences from the existing noisy host/fixture. No optimizer or production-default promotion is authorized even if semantic tests pass. Keep PR #10 draft/unmerged.

## Results: native semantic parity accepted (2026-11-23/24)

The bounded [native IR-035 run #45298944493](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45298944493) completed successfully against real Java 25 / Minecraft 26.3 Fabric. The original per-JVM state, command-quota and server logs are retained in [artifact 14878231005](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45298944493/artifacts/14878231005).

| Gate | Actual result | Disposition |
| --- | --- | --- |
| Optimizer/source contracts | IR-035, IR-034, IR-008 and IR-013 tests passed, including order and effect-boundary assertions | ACCEPT |
| Java / Minecraft build | Java 25 Fabric mod compiled and packaged | ACCEPT |
| IR-008 | Four fresh native/fused/interpreted/bytecode JVMs; **62 original-state/quota cases**, complete equality to vanilla (`native_parity=true`) | ACCEPT |
| IR-013 | Six fresh JVMs, **85 cases per mode**; guarded interpreter, guarded ASM and guarded direct scheduling all had **zero differences** from vanilla | ACCEPT |
| IR-013 unsafe negative controls | Both unsafe bytecode and unsafe direct modes diverged from vanilla in **46 cases**, as expected | ACCEPT |
| Causal CPU gain or promotion | Not measured; `causal_speedup_established=false`, `compiler_production_promotion=false` | NOT CLAIMED |

The cases include score mutations, binary arithmetic and aliases, conditional branches, missing/read-only objectives, original-command fallback, limited quotas and reentrant scoreboard callbacks. These bounded fixtures do **not** prove arbitrary third-party mod compatibility or that every possible datapack command is optimized. The original source command remains the fallback and effect boundary.

**Acceptance:** IR-035 complete as an explicit, working optimizing-compiler pipeline stage. The first pass performs narrow single-instruction canonicalization and predecoding. It is deliberately not constant propagation, dead-store removal, command elimination, selector caching or a general scheduler replacement. Further optimization passes will need separate proofs of their effect and interleaving boundaries.

**No speedup claim:** IR-035 introduces a Plan object and compile-time classification that may affect compilation overhead and memory footprint; the new ASM output largely performs the same direct operations as IR-034. Whether these changes improve runtime throughput is not established, and no production default is changed. The prior failed IR-033 A/A infrastructure gate remains relevant.

**Final state:** PR #10 stays draft and unmerged on `work/compiler-coverage`; the IR-035 native workflow was restored to manual-only after its single bounded run. A future compiler milestone should build reusable static analysis and cost-based decisions on this Plan representation rather than new Minecraft-engine-specific patches.
