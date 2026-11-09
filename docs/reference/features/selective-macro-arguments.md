# Selective Macro Arguments (`SelectiveMacroArgumentPrototype`)

**Status:** Supported — promoted to default-enabled (`selective_macros: true`); see the [promotion table](../../../README.md#promotion-status-current-evidence).  
**Configuration Key:** `"selective_macros": true` (in `config/function-compiler.json`)  
**Owner Class:** [`SelectiveMacroArgumentPrototype.java`](../../../src/main/java/dev/functioncompiler/SelectiveMacroArgumentPrototype.java)  
**Test IDs:** [`MACRO-001`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L61) through [`MACRO-010`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L70), [`PERF-011`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L80), [`PERF-015`](../../../benchmarks/PERF-015-multi-mod-endurance-campaigns.md)

---

## 1. Motivation & Bottleneck Analysis

In Minecraft 26.3, invoking a macro function using `function <id> with entity <selector> data` or `function <id> with storage <storage> <path>` triggers full entity/storage NBT serialization (`Entity.saveWithoutId` or `CommandStorage.get`) followed by deep NBT path navigation, even when the macro template only requires a few specific fields (e.g. `amount`, `x`, `y`, `z`).

Profiling real-world datapacks (such as Vein Miner 5.3.0) revealed that entity and storage serialization accounted for over **80% of macro invocation overhead**.

`SelectiveMacroArgumentPrototype` intercepts macro argument resolution and extracts the requested top-level parameters directly from the entity's custom data component or target storage compound, completely bypassing full NBT compound serialization.

---

## 2. Fast-Path Eligibility & Fallback Rules

The selective extraction fast path is active for both entity and storage data sources:

1. **Entity Data Accessor:**
   - Targets a single entity via `EntityDataAccessor`.
   - Accesses the entity's `custom_data` component.
   - The custom data component exists and contains all required macro parameter keys.
2. **Storage Data Accessor:**
   - Targets a named command storage resource (`CommandStorage`).
   - Retrieves the root compound directly and extracts only the declared macro parameter keys without cloning or traversing unrequested sub-structures.

### Fallback to Vanilla Native Resolution

The prototype immediately returns `null` and delegates to vanilla's `FunctionCommandInvoker.functionCompiler$getArgumentTag` under any of these conditions:
- **Block Data Providers:** e.g., `with block <pos> data`. Verified to preserve vanilla error feedback with zero candidate fast-path increments.
- **Deeply Nested Entity Paths:** e.g., `with entity ... data.custom_args.nested`. Verified to fall back and return nested values via native navigation.
- **Missing or Wrong-Typed Fields:** Fallback produces exact vanilla `CommandSyntaxException` and execution stops without side effects.

---

## 3. LRU Macro Cache Parity

Vanilla Minecraft maintains an equality-aware eight-entry LRU cache for expanded macro functions (`MacroFunction.cache`). The selective candidate adheres to this contract:
- **10-Tuple Churn (MACRO-005):** Ten distinct argument compounds churn through the 8-entry cache with exact match against vanilla eviction counts.
- **Hash Collisions (MACRO-004):** Distinct parameter compounds `{a:0, c:1}` and `{a:1, c:0}` share Java hash 195; verified to produce independent, correct expansions without hash-aliasing.
- **Staged Datapack Reloads (MACRO-007):** Re-specializes upon publication of changed macro bodies, retains old expansions during preparation, and rolls back cleanly on failed reload.

---

## 4. Multi-Mod Endurance Results (`PERF-015` and confirmatory campaigns)

Vein Miner 5.3.0 ($6 \times 6 \times 6 = 216$ blocks, 1,952 queue increments per event):

- **Screening (3 pairs, [`PERF-015`](../../../benchmarks/PERF-015-multi-mod-endurance-campaigns.md)):** Fabric -22.25% median event completion with `>6.5x` average-tick ratios, and `lbm113120` -28.40% with -35.21% P95 MSPT. Three pairs reach at most 93.75% exact median coverage, so these are screening observations only.
- **Confirmatory (6 pairs):** Fabric -22.34% and Lithium -22.06% median event completion each met the pre-declared 15% gate; the Lithium+Bellows 1.1.3 nested-source run measured -22.17% at 95% confidence. Synthetic sustained macro fixtures measured -80.49% (`lb113`) and -83.22% (`lbm113120`) active-tick averages.
- **Workload Integrity:** exact parity across all recorded arms (215/215 blocks mined, $\Delta\text{\#head} = 1,952$).

Batch 23 measured the addressable pool on the same pack with the compiler off:
macro argument construction is 27.4% of sampled server-thread wall time and
29.4% of active tick time, and a selective-macro diagnostic used the fast path
on 11,701/11,701 attempted calls with zero unsupported providers, entity paths,
storage sources, missing custom data, resolution fallbacks, or missing keys
(215/215 blocks). This establishes coverage and pool size, not a timing
comparison; the real-workload promotion campaign is pending a predeclared
threshold, pair count, and seed. See the
[attribution record](../../../benchmarks/README.md#time-share-attribution-and-the-h4-decision-2026-11-09).
