# Repository Feature Inventory (Prototype + Specialized Handlers)

**Target Environment:** Minecraft 26.3 Java Edition · Fabric Loader · Dedicated Server  
**Primary Verification Harness:** [`scripts/run_compatibility_probe.py`](../../../scripts/run_compatibility_probe.py)  
**Status Authority:** [`docs/current-state.md`](../../current-state.md)  
**Roadmap Specification:** [`docs/v1/plans/v1-production-roadmap.md`](../../v1/plans/v1-production-roadmap.md)

This inventory separates three different maturity levels:
1. **Core hooks/fallback:** wrapper identity, delegated execution, reload/scoping.
2. **Specialized handler compilation:** narrow command-shape replacements that delegate to vanilla command semantics.
3. **Prototype execution paths:** fused interpreted region, tiered ASM bytecode, and selective macro arguments. They are instrumentation/proof paths and remain gated by config and environment.

This inventory indexes all implemented compiler components, production optimizations, runtime hooks, and administrative interfaces.

---

## 1. Production Optimization Engines

| Optimization Pass | Source Components | Configuration Key | Default Posture | Verification Status |
|---|---|---|---|---|
| **Fused Region Specialization** | [`FusedRegionPrototype.java`](../../../src/main/java/dev/functioncompiler/FusedRegionPrototype.java), [`FusableCommand.java`](../../../src/main/java/dev/functioncompiler/FusableCommand.java) | `fused_regions` | **Experimental/opt-in (default currently enabled in `CompilerConfig`; AGENTS says leave disabled until gates close)** | Prototype execution path. Fuses contiguous commands that implement `FusableCommand` into one scheduler entry while preserving callbacks/cost/quota and retaining original queue entries as fallback. Real-world adjacent-region workload coverage remains open. |
| **Selective Macro Arguments** | [`SelectiveMacroArgumentPrototype.java`](../../../src/main/java/dev/functioncompiler/SelectiveMacroArgumentPrototype.java) | `selective_macros` | **Experimental/opt-in (default currently enabled in `CompilerConfig`; AGENTS says leave disabled until gates close)** | Prototype argument extraction for top-level keys. Falls back to vanilla `FunctionCommand` argument construction for nested paths, unsupported providers, non-present parameters, or excluded namespaces. Supporting evidence is screening-only, not a promotion gate. |
| **Tiered JIT Bytecode Backend** | [`BytecodeRegionPrototype.java`](../../../src/main/java/dev/functioncompiler/BytecodeRegionPrototype.java), [`BytecodeRegionEmitter.java`](../../../src/main/java/dev/functioncompiler/BytecodeRegionEmitter.java), [`TieredRegionAction.java`](../../../src/main/java/dev/functioncompiler/TieredRegionAction.java) | `tiered_bytecode` | **Opt-In** (Disabled) | Unrolls hot regions ($K \ge 5$) into hidden JVM classes parameterized strictly by command count. Metaspace evidence is limited to the pinned 25-cycle/reload-failure runs. |

---

## 2. Specialized Command Handlers (Narrow Parsed Shapes, Not General Compilation)

These handlers replace specific Brigadier command shapes after parsing. They retain the original command for fallback, but broad world-command semantics still go through vanilla execution. Do not describe this list as evidence that the repository compiles arbitrary Minecraft commands.

| Handler Class | Target Syntax Patterns | Optimization Mechanism |
|---|---|---|
| [`ScoreAddCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreAddCommand.java) | `scoreboard players <add\|set\|remove> <holder> <obj> <val>` | Pre-resolves objective and holder; executes zero-allocation integer mutations. |
| [`ScoreOperationCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreOperationCommand.java) | `scoreboard players operation <target> <tObj> <op> <src> <sObj>` | Directly executes 9 binary operators (`+=`, `-=`, `*=`, `/=`, `%=`, `=`, `<`, `>`, `><`) with exact 32-bit wrapping and divide-by-zero checks. |
| [`ScoreResetCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreResetCommand.java) | `scoreboard players reset <holder> [<obj>]` | Direct score removal and scoreboard tracking updates. |
| [`ScoreConditionCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreConditionCommand.java) | `execute if/unless score <target> <tObj> <op> <source> <sObj>`, `matches <range>` | Direct condition evaluation in fused regions with zero intermediate scheduler steps. |
| [`ScoreStoreCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreStoreCommand.java) | `execute store result/success score <holder> <obj> run ...` | Intercepts returned score or success flags directly to destination objective without intermediate observers. |
| [`ContextModifierCommand.java`](../../../src/main/java/dev/functioncompiler/ContextModifierCommand.java) | `execute as @s at @s positioned ... rotated ... anchored ... in <dim> align <axes> facing <pos>` | Folds chained context modifications into a single in-memory source transformation, eliminating frame splits. |
| [`DataStorageCommand.java`](../../../src/main/java/dev/functioncompiler/DataStorageCommand.java) | `data modify storage <id> <path> set value <val>`, `data remove storage <id> <path>` | Inlined storage data manipulation avoiding command dispatch overhead. |
| [`DataCopyCommand.java`](../../../src/main/java/dev/functioncompiler/DataCopyCommand.java) | `data modify storage <id> <path> set from storage <src> <srcPath>` | Direct in-memory compound/tag transfer between NBT storage paths without full serialization. |
| [`DataStoreCommand.java`](../../../src/main/java/dev/functioncompiler/DataStoreCommand.java) | `execute store (result\|success) storage <id> <path> <type> <scale> run ...` | Captures command return results or success codes directly into numeric NBT tags in storage. |
| [`DataGetCommand.java`](../../../src/main/java/dev/functioncompiler/DataGetCommand.java) | `data get (storage\|entity\|block) <target> [<path>] [<scale>]` | Fusable fast-path for NBT data reading and redirection into scoreboards or storage. |
| [`PredicateConditionCommand.java`](../../../src/main/java/dev/functioncompiler/PredicateConditionCommand.java) | `execute if/unless entity @e[...]`, `execute if/unless predicate <id>`, `block <pos> <block>`, `items ...` | Direct entity counting, loot predicate evaluations, block state/tag checks, and modern item predicates without sub-frame allocation. |
| [`InlinedForkingCommand.java`](../../../src/main/java/dev/functioncompiler/InlinedForkingCommand.java) | `execute (as\|at) @e[...] run ...`, `execute on <relation> run ...` | Evaluates multi-entity selectors and relational navigation in-process, debits command quota per entity, and executes terminal actions without queue task overhead. |
| [`StateMachineCommand.java`](../../../src/main/java/dev/functioncompiler/StateMachineCommand.java) | `tag ...`, `tp/teleport ...`, `kill ...`, `setblock ...`, `particle ...`, `playsound ...`, `bossbar ...`, `effect ...`, `title ...`, `item ...` | Fuses common entity state mutations, block placement, audio/visual packet emissions, bossbars, status effects, titles, and item mutations directly as terminal executables. |
| [`InlinedFunctionCommand.java`](../../../src/main/java/dev/functioncompiler/InlinedFunctionCommand.java) | `function <id>` (leaf calls $\le 64$ entries) | Inlines non-recursive, pure leaf sub-functions directly with accurate quota debiting, eliminating `CallFunction` frame allocation. |
| [`TailCallLoopCommand.java`](../../../src/main/java/dev/functioncompiler/TailCallLoopCommand.java) | `function <self>` (self-tail-recursive calls) | Replaces repetitive `CallFunction` self-recursion with in-place loop execution and strict per-iteration quota debiting. |
| [`MacroTemplateCompiler.java`](../../../src/main/java/dev/functioncompiler/MacroTemplateCompiler.java) | `function <macro_id> with storage/entity <args>` | Pre-extracts macro parameters, maintains an expanded 256-entry LRU parameterized cache, and compiles instantiated plain-text functions into bytecode. |

---

## 3. Runtime Hooks & Interception Points

| Hook Target | Mixin / Adapter | Purpose | Evidence |
|---|---|---|---|
| `FunctionBuilder.build` | [`FunctionBuilderMixin.java`](../../../src/main/java/dev/functioncompiler/mixin/FunctionBuilderMixin.java) | Captures parsed functions at construction time, wraps in [`ProbeFunctionWrapper.java`](../../../src/main/java/dev/functioncompiler/ProbeFunctionWrapper.java), and triggers compilation. | 100% exact parity across 25+ reloads. |
| `ExecutionContext.runCommandQueue` | [`ExecutionContextMixin.java`](../../../src/main/java/dev/functioncompiler/mixin/ExecutionContextMixin.java), [`ExecutionContextBridge.java`](../../../src/main/java/dev/functioncompiler/ExecutionContextBridge.java) | Thread-safe re-entrant tracking of active server thread `ExecutionContext` stack for inlined forking quota accounting. | Exact stopping parity across quota sweeps 0–8. |
| `CommandFunction` delegation | [`ProbeFunctionWrapper.java`](../../../src/main/java/dev/functioncompiler/ProbeFunctionWrapper.java) | Preserves original plain-text functions for fallback, manages macro compilation LRU cache, and respects namespace exclusions. | Verified in `HOOK-001` through `HOOK-010`. |
| `FunctionCommand` argument resolution | [`FunctionCommandInvoker.java`](../../../src/main/java/dev/functioncompiler/mixin/FunctionCommandInvoker.java) | Intercepts macro argument resolution for selective extraction candidate. | Verified in `MACRO-001` through `MACRO-010`. |
| Bellows entity data compatibility | [`BellowsHomePosAdapterMixin.java`](../../../src/main/java/dev/functioncompiler/mixin/BellowsHomePosAdapterMixin.java) | Restores vanilla `home_pos` entity NBT behavior under Bellows optimization. | Verified in init, merge, modify, and remove paths. |

---

## 4. Production Configuration & Administration (Milestone 4)

| Interface | Component | Purpose |
|---|---|---|
| `config/function-compiler.json` | [`CompilerConfig.java`](../../../src/main/java/dev/functioncompiler/CompilerConfig.java) | Granular toggles (`fused_regions`, `selective_macros`, `tiered_bytecode`, `tiered_threshold`, `excluded_namespaces`). |
| In-Game Admin Commands | [`ProbeCommands.java`](../../../src/main/java/dev/functioncompiler/ProbeCommands.java), [`ProbeStatus.java`](../../../src/main/java/dev/functioncompiler/ProbeStatus.java) | Operator commands: `/functioncompiler status`, `/functioncompiler metrics`, and `/functioncompiler reload`. |

---

## 5. Detailed Component Specifications

- [Architecture Reference](../architecture.md): Full technical architecture, execution model, and compilation pipeline.
- [Configuration Reference](../configuration.md): `config/function-compiler.json` schema and operator commands.
- [Fused Interpreted Regions](fused-regions.md): Multi-command queue compaction, Stage 1A–1D specializations, and error continuation.
- [Selective Macro Arguments](selective-macro-arguments.md): Fast-path argument extraction for entity and storage macros.
- [Emitted ASM Bytecode](emitted-bytecode.md): Parameterized hidden classes, `CONSTRUCTOR_CACHE`, tiered JIT engine, and Metaspace lifecycle.
- [Literal Scoreboard Specialization](scoreboard-specialization.md): Integer arithmetic and operation optimization.
- [Command Quota and Scheduler](command-quota-and-scheduler.md): 26.3 `ExecutionContext`, fork/sequence limits, frame discards.
- [Lifecycle and Datapack Reload](lifecycle-and-reload.md): Load tags, tick tags, concurrent publication, and rollback.
