# COMPILER-IR-031 — Marker entity result-store writeback feasibility

**Status (2026-11-23): GATE A EXACT 26.3 BYTECODE AUDIT ACCEPTED; GATE B EXACT-SOURCE ENTITY.LOAD CPU ATTRIBUTION ACCEPTED. STOP — NO CANDIDATE IMPLEMENTED.** The original vm:queue/append_here x/y/z execute-store sites invoke Entity.load 5,820 times, but the measured Entity.load body accounts for only **4.14%** of the original event's Server-thread CPU. This is below the predeclared **5% candidate-development screen**, before accounting for any lifecycle behavior that a direct custom-data update would need to preserve. Runtime optimization remains absent; draft PR #10 remains open and unmerged.

## 1. Hypothesis

IR-030 preserved the native outer execute-store callback and optimized only the inner data-get entity Pos[i] terminal. Its second, separate hypothesis was a typed per-axis entity result-store writeback that could avoid reloading unrelated entity fields after each coordinate assignment.

The original native callback invokes DataAccessor.setData after applying the result to the NBT path. For EntityDataAccessor, the exact 26.3 implementation creates a TagValueInput, calls Entity.load, restores the entity UUID, and calls postDataManipulated. A direct CustomData component replacement might avoid the full entity reload, but would also skip the other state-restoration operations performed by Entity.load.

The candidate under consideration was deliberately narrow: exact, unmounted vanilla Marker entities, only the three original data.frontier[-1].{x,y,z} result-store paths in vm:queue/append_here, no datapack changes, and no general entity-data accessor replacement. This document records feasibility only; it does not authorize that candidate.

## 2. Gate A — exact mapped Minecraft 26.3 bytecode

The [mapped-bytecode workflow #45128918107](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45128918107) passed against the fingerprinted 26.3 mapped classfile JAR. Its [raw classfile and lifecycle inventory](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45128918107/artifacts/14796144176) covers EntityDataAccessor, Entity, Marker, CustomData, DataComponents, TagValueInput, and TagValueOutput.

### Exact setter contract

EntityDataAccessor.setData:
1. Refuses player destinations.
2. Creates a ProblemReporter scope and a TagValueInput from the supplied compound.
3. Invokes entity.load(input).
4. Restores the UUID saved before loading.
5. Calls entity.postDataManipulated().

The original ExecuteCommand.lambda$storeData$0 callback independently obtains destination data, applies NbtPath.set, invokes DataAccessor.setData, and preserves the original callback/result/exception boundary. IR-031 did not change this callback or any native operation.

### Direct component path exists, but is not equivalent by inspection alone

The mapped Entity class exposes setComponent(DataComponents.CUSTOM_DATA, value). Its implicit component handler writes the custom-data field directly. CustomData.of(tag) creates a deep copy, so the ownership/copy behavior is suitable for a possible narrow replacement.

The exact Marker class declares addAdditionalSaveData and readAdditionalSaveData, but both are no-ops. It does not override postDataManipulated or repositionEntityAfterLoad; the inherited postDataManipulated is a no-op. This removes subclass-specific save/load hooks from the target case, but does **not** make the full reload redundant: base Entity.load also reapplies position, movement, rotation, flags, tags, team state, and post-load positioning. A direct component write would skip those operations. Their observable side effects were not proven equivalent, so no setter replacement was implemented.

### Bellows compatibility exclusion

Bellows 1.1.3 already has a path-filtered NBT accessor:
- Its DataCommandsMixin filters getData and setData for DataCommands.manipulateData.
- Its ExecuteCommandMixin filters the outer result-store setter.
- Its entity "data" branch reads/writes CustomData directly rather than calling the full Entity.load path.

The reviewed [Bellows 1.1.3 source revision](https://github.com/Smithed-MC/Bellows/tree/7c53a5cde1baa8a3eccf1d208d0828a66b880965) already addresses this category of writeback. IR-031's timing run therefore uses vanilla Fabric only. A future candidate must decline when Bellows is present unless a separately measured incremental benefit and safe mixin composition are demonstrated. Bellows-side savings are not compiler savings.

**Gate A decision:** a direct component write is mechanically possible, but the base-entity side effects remain unproven. Continue only if source-specific CPU exposure is material enough to justify the semantic work.

## 3. Gate B — exact source-site Entity.load CPU attribution

The [PLAIN / EMPTY / TIMED original-publisher run #45130178777](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45130178777) completed three fresh Java 25 / Minecraft 26.3 Fabric wrapper events against the unchanged SHA-pinned Vein Miner 5.3.0+26.3 archive. The [three event manifests and exact timing streams](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45130178777/artifacts/14797528667) are retained.

Only the exact Entity.load invocation nested in EntityDataAccessor.setData was timed. A synchronous context from the original ExecuteCommand.lambda$storeData$0 setter identifies the path and entity; timing is enabled only for the same exact, unmounted Marker. The x, y, and z paths are disjoint. The diagnostic did not change the native setter, NBT compound, callback, command result, feedback, or world state.

All three modes passed the original workload and host gates:
- 215 original work units and 1,952 queue-head increments.
- 1,940 exact calls per axis; 5,820 total.
- Every call targeted an exact vanilla Marker, unmounted.
- All 5,820 outer setter calls completed and invoked exactly one Entity.load; all load calls completed.
- Zero mounted or other-entity calls, zero invalid clock samples, stable pre-event host, and zero cgroup throttling.
- IR-030 getter candidate, selective macro arguments, JFR, Spark, CPU004/005, macro006, callback counters, and other research profilers were disabled. The macro setting matches the earlier IR-030 CPU baseline.

### Clock-corrected result

| Axis | Entity.load calls | Corrected mean per call | Projected CPU across axis |
| --- | ---: | ---: | ---: |
| x | 1,940 | 91.83 µs | 178.15 ms |
| y | 1,940 | 88.18 µs | 171.07 ms |
| z | 1,940 | 88.44 µs | 171.56 ms |
| **Total** | **5,820** | — | **520.78 ms** |

The empty clock-pair means were 1.06–1.77 µs; corrected method means were 51.9–83.4 times those empty-clock values. The PLAIN event's Server-thread CPU denominator was **12.5923 s**. The signed projected Entity.load body share was therefore **4.1357%** of the original event.

The predeclared candidate-development screen was at least **5%** projected event CPU and at least **3×** the empty-clock floor on every axis. The clock-floor condition passed; the materiality condition did not. The measurement is the inclusive Entity.load invocation span for these exact setter calls, not a causal speedup and not proof that every part of the method body is avoidable. A component-only replacement would still need to preserve any required entity lifecycle effects, so the safe savings would be no greater than this measured span and likely smaller.

**Gate B decision: STOP.** Do not implement the typed per-axis entity result store. The 4.14% result is below the predeclared 5% development screen and far below the 15% full-event promotion bar. Do not relax either threshold after seeing the result.

## 4. Explicitly excluded adjacent paths

- **Macro argument construction:** the selective macro-argument fast path is already default-enabled and was independently measured in earlier work. Do not duplicate it.
- **data modify entity @s data.frontier append:** CPU005 measured the complete append command at approximately 5.08% inclusive. That span includes the actual list mutation, entity-data access, result/feedback handling, and native command work; it is not an estimate of removable compiler overhead. Bellows already path-filters DataCommands.manipulateData for this kind of access. It is not admitted as a free or automatically worthwhile optimization.
- **General entity NBT serialization or a global Entity.load shortcut:** rejected. The observed JFR serialization frames span many unrelated commands and entity operations, and no global cache or replacement is justified by these source-specific results.

## 5. Final decision and next direction

IR-031 closes the second IR-030 hypothesis without an implementation. The exact setter path is measurable, but its Entity.load body is too small in this original workload to warrant a specialized compiler action under the predeclared screen, and the skipped lifecycle behavior creates a substantial semantic burden.

Do not continue tuning Vein Miner's coordinate writeback or broaden this into generic NBT mutation. The next investigation should start from a **different real workload and a separately identified hot path**, with evidence of removable compiler/runtime overhead before implementation. Keep all IR-031 diagnostic code and workflows research-only/manual; no runtime feature is enabled, and PR #10 remains draft and unmerged.
