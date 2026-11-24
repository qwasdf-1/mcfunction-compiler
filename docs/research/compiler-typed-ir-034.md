# COMPILER-IR-034 — Immutable typed instruction-vector hoisting

**Status: implementation committed, native semantic gate pending.** Branch `work/compiler-coverage`, draft PR #10. This milestone returns to reusable compiler backend code-generation work after the IR-032 Gate C and IR-033 A/A CPU-noise failures. It is **not a native-engine optimization**, a datapack-specific special case, or a performance promotion.

## Compiler target and repeated costs

`TypedScoreIR.Program` owns an immutable `List<Instruction>` of two to 64 already Brigadier-validated scoreboard mutations, scoreboard operations and optional score guards. `MixedFunctionIR` retains source indices and opaque vanilla barriers. Interpreter and ASM bytecode backend both use `TypedScoreIRRuntime.State.begin/finish` to preserve per-command semantics and native fallback.

Before IR-034:

- Every invocation of a typed interpreted region executed `program.instructions().toArray(Instruction[]::new)`, allocating a new array of instruction references per invocation, despite the source function and validated instructions being unchanged until a new function is constructed on resource reload.
- The generated JVM hidden-class `execute` loaded its final `steps` field into the constructor for State, then loaded the same field again for each original source command before passing `steps[index]` to `State.begin`. The vector is immutable during a region execution and already holds the original per-command fallback actions.

This is a local loop-invariant optimization of *compiled program metadata*, not cross-command mutation elimination. It makes no assumptions about scoreboard values or gameplay state.

## Implemented transformations

1. **Interpreter:** `Interpreted` materializes an `Instruction[]` once in its constructor, stores it in a private final field and reuses the same array for every `State` and every loop iteration. No array is created by `Interpreted.execute` anymore. Each invocation still gets a fresh runtime State with its own scoreboard, quota, trace and fallback context.
2. **ASM:** the generated hidden class still owns the private final `steps` array. At the start of `execute`, the code generator emits one `GETFIELD steps` to JVM local 9. The same reference is passed to the fresh State and loaded for every indexed `begin`. The region emits exactly the same original instruction sequence, direct score operations, guarded branches, fallback, result handling and quota logic as before.
3. **Safety:** neither path caches an Objective, ScoreAccess, scoreboard value, mutable entity selector, or a per-invocation State. The shared vector is compile-time-owned source metadata, not gameplay data. `QueuedTail` still receives this vector in the existing reentrancy escape path; individual queued actions retain their own invocation State. Reload creates new compiled region instances with new vectors and does not mutate old ones. No runtime toggle or production default was changed.

## Static tests and native semantic qualification

- `tests/test_typed_ir034.py` asserts interpreted allocation placement, a single generated `GETFIELD` in the new execute method, branch/fallback/score-operation boundaries and the unchanged reentrancy vector handoff.
- Native semantic workflow `.github/workflows/research-typed-ir034-native.yml` is bounded to **two existing differential oracles** (not a speed study):
  - `scripts/ci_typed_ir008.py`: four independent Fabric JVMs comparing vanilla, fused, interpreted and bytecode typed execution, including missing/read-only objectives, conditional success/failure, binary self-alias, overflow, and low quota cutoffs.
  - `scripts/ci_typed_ir013.py`: six native/unsafe/guarded JVMs comparing queued scoreboard callbacks and command order for both typed backends, including 64-entry region boundary cases, low quotas and direct-scheduling continuation. Unsafe negative controls are expected to diverge where applicable; guarded paths must match native.
- These oracles retain full state comparisons and source coverage. Their CPU screen outputs, if any, are descriptive and **explicitly not** optimization acceptance evidence. Do not compare separate JFR windows or claim a 5–15% CPU improvement. IR-033 established that this host/fixture cannot currently reliably detect a 5% change.

**Semantic acceptance gate:** Java 25 / Minecraft 26.3 builds; source tests pass; all four IR-008 and all six IR-013 JVM arms complete with the previously defined state, quota, error and reentrant-order correctness oracles. If any gate fails, retain logs and artifacts, do not enable more transformations.

**Benchmark and release gate:** none proposed in this milestone. This small allocation/bytecode improvement remains opt-in within typed IR mode; no global runtime flag or promotion. The next *distinct* compiler milestone should use the existing typed effect model to broaden the reusable optimization pipeline without moving across observable per-command or opaque barriers.

## Results

Pending native run and build results. Append exact run identifiers, artifact references and pass/fail disposition only after observation.
