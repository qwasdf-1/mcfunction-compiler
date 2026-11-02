# Fused Interpreted Regions (`FusedRegionPrototype`)

**Status:** Disabled by default; experimental. Semantic matrices, quota/trace parity, and static-fixture timings pass, but no screened datapack supplies an adjacent-eligible region, so the real-world performance gate remains open.  
**Configuration Key:** `"fused_regions": false` (in `config/function-compiler.json`)  
**Owner Classes:** [`FusedRegionPrototype.java`](../../../src/main/java/dev/functioncompiler/FusedRegionPrototype.java), [`FusableCommand.java`](../../../src/main/java/dev/functioncompiler/FusableCommand.java)  
**Test IDs:** [`CTRL-005`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L46), [`CTRL-007`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L48), [`SCORE-014`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L90), [`SCORE-015`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L91), [`MACRO-009`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L71), [`PERF-012`](../../../benchmarks/PERF-012-macro-region-compilation.md)

---

## 1. Design & Purpose

Minecraft 26.3 executes functions by enqueuing each command as an independent entry in `ExecutionContext.runCommandQueue`. Each entry incurs dequeue overhead, frame activation, dispatcher re-resolution, and sequence limit decrementing.

The **Fused Region Engine** groups consecutive eligible commands implementing [`FusableCommand.java`](../../../src/main/java/dev/functioncompiler/FusableCommand.java) into a single unrolled `UnboundEntryAction`:
1. The entire fused region claims exactly one queue slot in `ExecutionContext`.
2. Contiguous commands execute sequentially in an internal in-memory interpretation loop.
3. If an error, return, or quota exhaustion occurs mid-sequence, execution cleanly falls back or aborts according to exact vanilla control flow semantics.

---

## 2. Expanded Specialization Passes (Milestone 1)

In addition to basic arithmetic mutations, the engine fuses the following command patterns:

### Stage 1A: Scoreboard Predicates & Store Redirection
- **Conditions ([`ScoreConditionCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreConditionCommand.java)):** Specializes `execute if/unless score <targets> <targetObjective> <op> <source> <sourceObjective>` and `matches <range>`. Evaluates comparisons directly against `ServerScoreboard` with 0 scheduler steps.
- **Store Redirection ([`ScoreStoreCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreStoreCommand.java)):** Directs `execute store result/success score` return values directly to the destination score holder without intermediate observer objects.

### Stage 1B: Context Modifier Folding
- **Folding ([`ContextModifierCommand.java`](../../../src/main/java/dev/functioncompiler/ContextModifierCommand.java)):** Folds chained context modifiers (e.g. `execute as @s at @s positioned ~ ~1.5 ~ rotated ~ 0 run ...`) into a single in-memory source mutation, eliminating intermediate `CommandSourceStack` allocations and frame splits.

### Stage 1C: Storage Operations & Storage Macros
- **Storage Mutations ([`DataStorageCommand.java`](../../../src/main/java/dev/functioncompiler/DataStorageCommand.java)):** Fuses `data modify storage ... set value` and `data remove storage` operations directly within contiguous regions.

### Stage 1D: Entity & Block Predicates
- **Predicates ([`PredicateConditionCommand.java`](../../../src/main/java/dev/functioncompiler/PredicateConditionCommand.java)):** Inlines `execute if/unless entity @s` and `execute if/unless block <pos> <block>` checks with zero frame allocation.

---

## 3. Contiguity & Region Boundaries

A fused region terminates and yields back to standard queue scheduling whenever:
- An unrecognized command appears (e.g. `say`, modded commands, complex selectors).
- A control-flow altering command is reached (`return`, `return run`, `execute if/unless`).
- A sequence limit or command quota boundary requires yielding.

When an unrecognized command appears between eligible regions (e.g., `ScoreAdd -> ModLeaf -> ScoreAdd`), the compiler emits two distinct fused regions around the unrecognized leaf. This was verified with `fc_probe_leaf` storing result 7 and executing two separate fused regions with exact total score 15.

Furthermore, `CTRL-008` verified custom mod commands implementing `CustomCommandExecutor` across normal continuation (`step`), frame discard (`discard`), and value/failure returns (`return_value`, `return_fail`). In all cases, mod commands execute exactly once without double execution; upon frame discard or return, trailing compiled regions are safely discarded.

---

## 4. Macro Region Fusing & Metaspace Safety

In addition to static plain-text functions, `FusedRegionPrototype` is hooked into [`ProbeFunctionWrapper.java`](../../../src/main/java/dev/functioncompiler/ProbeFunctionWrapper.java) to fuse expanded macro functions upon instantiation:
- Contiguous specialized commands within expanded macro functions are grouped into interpreted `FusedScoreAddRegion` instances.
- Instantiated compiled functions are cached in a 16-entry synchronized LRU cache (`macroCompilationCache`), matching and extending vanilla's 8-entry tuple cache.
- Interpreted fused regions operate entirely on heap structures, guaranteeing **zero Metaspace growth and zero class-unloading pressure** even under millions of dynamic parameter combinations.

---

## 5. Performance Measurements

1. **Static Workload (PERF-004):** On a static 5,000-add fixture, fused interpreted regions achieved a median queue execution time of 1.537 ms (compared to 2.500 ms for vanilla delegate and 2.784 ms for ScoreAdd), a 38.5% queue speedup.
2. **Macro Workload ([PERF-012](../../../benchmarks/PERF-012-macro-region-compilation.md)):** On an 11-operation macro sequence across 300 invocations, fused interpretation reduced queue dispatches by 90.9% and achieved a **+37.17% median speedup** ($0.4428\ \text{ms} \to 0.2782\ \text{ms}$) and a **+74.28% mean speedup** ($1.2109\ \text{ms} \to 0.3115\ \text{ms}$) with 86.4% tail jitter reduction over vanilla `fabric-off`.
3. **Multi-Mod Server Campaigns ([PERF-015](../../../benchmarks/PERF-015-multi-mod-endurance-campaigns.md)):** Those campaigns are 3-pair **screening** evidence for selective macro arguments, not for fusion: Vein Miner 5.3.0 has no adjacent eligible fused commands, so it supplies no fused-region workload. The fused engine's real-world gate stays open until an adjacent-eligible workload is screened (see the [benchmarking protocol](../../benchmarking.md)).
