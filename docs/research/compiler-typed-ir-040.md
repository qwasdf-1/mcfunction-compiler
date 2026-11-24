# IR-040 — Predicate dataflow, complete scoreboard operation representation, and first CPU crossover

**Status: native semantic acceptance passed; synthetic CPU pilot completed but failed its preregistered stability gate (2026-11-24).** Research branch `work/compiler-coverage`, draft PR #10. Production defaults unchanged.

## Compiler design

An ordered forward abstract interpreter models possible signed 32-bit values as unions of closed intervals plus an explicit absent-score state. Positive range predicates intersect with the range and remove absence; unless predicates intersect with the complement including absence. An empty accepted domain proves failure; an empty rejected domain proves success. Arithmetic bounds use longs for endpoint adjustment; no overflow at MIN/MAX. Comparison relations use LT/EQ/GT/ABSENT masks, canonical operand ordering and swapped relation masks. Earlier successful predicates constrain the pair, and successful positive comparisons establish presence. No transitive comparison graph or arbitrary arithmetic propagation is claimed.

The compound plan retains original stage order and quota accounting, including IR039's empty-source suffix debits. A per-command bitset plus integer array caches existence and values only during pure score predicate reads. It resets at every compound start and does not supply terminal operands. Exact symbolic slots intern @s separately from fake holders. ASM reuses IR039's explicit branches for known pass/fail results; the interpreter consumes the same plan. `FC_TYPED_IR_DATAFLOW=true` gates new dataflow and read caching.

The remaining scoreboard arithmetic is represented as typed DIVIDE, MODULO and SWAP instructions with canonical opcodes. `FC_TYPED_IR_ARITHMETIC=true` admits bare and compound terminals only. Single-guard exceptional arithmetic and unsupported selectors/modifiers remain native. The runtime uses the original Brigadier-validated OperationArgument.Operation on the already resolved score accesses, preserving native floor arithmetic, zero-divisor exception, swap write order and same-slot behavior; this is compiled orchestration, not yet direct IDIV/IREM bytecode. SWAP effects include both written slots. Errors are handled once, never replayed after row creation or mutation. Tracer and nonempty callback paths fall back before effects for exceptional arithmetic. Native oracle remains required.

## Correctness gate

Independent Java abstract-domain checks, inherited source contracts, full IR039 native regression and nine additional functions for implication, intersection, absence, comparison normalization, dynamic holders, signed arithmetic, missing divisor rows, zero errors, same-slot swap, guarded arithmetic and swap callback ordering. Native vs IR039 feature-off bytecode (other flags held fixed), IR040 interpreter, bytecode and direct. All source cutoff budgets 1–40, 48, 64 and full quota, plus entity/no-entity for four dynamic fixtures. The earlier IR039 quota-12 assertion remains. State snapshots and actual lowering/optimization counters are required, not merely successful compilation.

## CPU pilot — separate from correctness

First measure a deliberately synthetic but real Minecraft workload, not an inferred speedup from counters. Three identical 64-line functions in one JVM: native namespace (uncompiled), IR039-style compiled twin (new dataflow disabled by exact benchmark-only path), IR040 compiled twin. Same function scheduler, direct off, exact native batch call harness scoped to three known fixture IDs. Only a separate diagnostic preflight uses counters and proves all 64 commands lower in both compiled twins, native does not, and dataflow counters rise only in IR040. Timed JVMs disable diagnostics and the test observer. Each 64-call batch has 3,072 successful increments, identical final scores across arms. Each window has eight batches (32,768 source lines); warm up eight batches per arm in two independently booted JVMs. External Linux /proc Server-thread schedstat running CPU nanoseconds, with wall time archived separately; setup/snapshot outside windows. Same-JVM measurements include scheduler, RCON overhead and incidental server work. They are not per-predicate clocks.

Pre-registered counterbalanced ABBA/BAAB blocks for native vs IR040, IR039-style vs IR040, native/native A/A and IR039-style/IR039-style A/A. Pilot claim only if all four paired treatment reductions positive, both boot medians at least max(5%, twice maximum absolute A/A), and max absolute A/A <=5%. Otherwise report descriptive numbers and reject a speedup claim. Native correctness must also pass. No extrapolation to real datapacks or production defaults. The first test is a bounded pilot; use a real datapack crossover only after this gate, not another large undirected study.

## Limits

The read-purity and effect assumptions from IR039 remain. No arbitrary modded read effects or callback/fork-limit coverage claim. Range/comparison reasoning is intracommand only; exact pair relations are not transitive across different pairs. The same-JVM benchmark base twin runs the shared implementation with IR040 dataflow off, not a historical binary. Arithmetic uses the native operation leaf and is not the workload being timed. Performance claims require measured results.

## Results

### Native semantic acceptance — passed

[Run 45464991546](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45464991546) passed both jobs. [Ordinary CI on the restored manual-only workflow](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45465053337) passed. The [native evidence archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45464991546/artifacts/14955660174) contains the full snapshots and logs.

- Independent abstract-domain oracle: 813 checks passed.
- Five native modes: 1,161 state observations each, 5,805 total, exact native parity. This includes the full accepted IR039 fixture corpus and quota-12 regression.
- New nine-fixture typed coverage: 46/72 with IR040 disabled; 72/72 with IR040 enabled in interpreter, bytecode and direct.
- Each enabled mode: 752 additional dataflow proofs exercised, 509 operand reads reused, 695 exceptional-arithmetic steps (including 142 handled errors), 1,722 total compound predicate computations eliminated, 471 compound native fallbacks and 232 reentrant yields. All four IR040-specific counters were zero in the feature-off control.

### CPU pilot — measured signal, stability gate failed

[CPU evidence archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45464991546/artifacts/14955306595). Diagnostic path preflight and exact completed-work validation passed; two uninstrumented JVMs completed all 64 timed windows (2,097,152 source-command visits). The following values are descriptive reductions of Server-thread running CPU per source line, not accepted causal estimates.

| Comparison | Four paired reductions, chronological within each boot | Median | Boot 0 median | Boot 1 median | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| Native vs IR040 | 80.90%, 79.70%, 61.71%, 80.52% | 80.11% | 80.30% | 71.12% | Failed stability |
| IR039-style vs IR040 | 16.40%, -22.59%, 29.94%, 18.21% | 17.31% | -3.09% | 24.08% | Failed stability and consistency |

Maximum absolute A/A placebo reduction: **28.39%** (preregistered maximum 5%). Both pilot gates are false. Native-vs-flow was positive in every block, with much larger observed reductions than the incremental dataflow comparison, but the protocol does not permit a causal speedup claim. The incremental comparison also reversed direction in one block and had a negative boot-0 median. Raw per-line CPU costs change substantially over a boot, including identical-arm blocks; insufficient steady-state warmup, JIT transitions and other time-varying effects are hypotheses, not established causes. Do not remove early blocks post hoc or revise the threshold to accept this experiment.

**Disposition:** IR040 native semantic milestone accepted for the tested scope. No CPU speedup gate passed. Next performance experiment should qualify a steady-state same-JVM protocol using longer warmup, longer measurement windows and interleaved A/A controls before interpreting treatment comparisons; retain this first pilot unchanged. Arithmetic compilation is not part of the timed workload, and no general datapack speedup or production promotion follows. Single-guard exceptional arithmetic and restrictive fork-limit dedicated tests remain outside demonstrated coverage.
