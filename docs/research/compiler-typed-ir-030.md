# COMPILER-IR-030 — Vein Miner coordinate-result-store specialization feasibility

**Status (2026-11-21): GATE A VERIFIED; GATE B TWO ORIGINAL-EVENT JFR PROFILES ACCEPTED (DESCRIPTIVE ONLY).** No runtime replacement semantics or CPU gain demonstrated. Work remains on `work/compiler-coverage`, draft PR #10. The research compiler, IR-025 fork, and new NBT specializations remain disabled by default. Do not merge research instrumentation or promote an optimizer based on this document.

## 1. Why change targets after IR-029?

IR-027 established a controlled original Blastback complete-restoration oracle. IR-028 ran four uninstrumented A–B–B–A Java 25 / Minecraft 26.3 events; compiled-fork CPU was **0.137%** lower with **4.804%** plan-only A/A spread and opposite-signed adjacent differences. IR-029 found the generated action in sampled stacks but confirmed that entity selection, predicate filtering and score access remain in the native selector path; profile arms had unequal capture populations. **STOP IR-025 performance tuning.** A global tag index is not permitted: IR-023 demonstrated direct mutation through the backing `Entity.entityTags()` set outside the partial invalidation hooks.

The earlier SHA-pinned, genuine Vein Miner 5.3.0+26.3 event gives a more substantial *native operation* to investigate, without pretending that its entire cost is removable compiler overhead.

| Previously accepted source-specific observation | Original native event evidence | Interpretation |
| --- | ---: | --- |
| `execute positioned … run function` entry | CPU004 ~0.142% projected Server CPU | Small synchronous path; not a priority |
| `vm:queue/enqueue_match` predicate `BuildContexts` | CPU005 ~0.0963% projected | Small synchronous path; repeated macro reparsing already eliminated |
| `vm:queue/append_here` entity `data modify` append | CPU005 ~5.0822% projected | Stateful NBT mutation, not compiler overhead |
| Three `execute store result entity ... run data get entity ... Pos[i]` commands | CPU005 **26.2341% inclusive** projected | Largest candidate path; includes real NBT reads/writes and native task execution |
| Inner `data get entity` callback | CPU005 **11.1527% inclusive** projected | **Nested in** the three stores; must not be added to their 26.2341% |

These CPU005 fractions come from a single separately booted PLAIN/EMPTY/TIMED sparse-clock diagnostic (fixed 1/16 samples), not a paired optimization trial or a precise exclusive breakdown. The estimated residual between nested observations is **not** an established avoidable fraction. The PLAIN, EMPTY and TIMED whole-event CPU denominators differ. No speedup is claimed here. The 215-mined-block, 1,952-queue-head event and original publisher ZIP SHA remain the reproducible control.

The pinned, unchanged publisher ZIP is `VeinMiner-5.3.0+26.3.zip`, SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. Existing `scripts/ci_queue_cpu005.py::verify_original_source` already verifies the five expected command texts occur uniquely in the specified original function files; it does **not** independently prove command ordering or that no additional lines were inserted. A new admission test must also verify ordered source indices and the parsed command graph.

## 2. Exact candidate source path

```mcfunction
# vm:queue/append_here — unchanged publisher source
tp @s ~ ~ ~
data modify entity @s data.frontier append value {x:0,y:0,z:0}
execute store result entity @s data.frontier[-1].x int 1 run data get entity @s Pos[0]
execute store result entity @s data.frontier[-1].y int 1 run data get entity @s Pos[1]
execute store result entity @s data.frontier[-1].z int 1 run data get entity @s Pos[2]
```

The pinned event reached this function **1,940** times, for **5,820** original store/result-get command entries. The currently present `DataGetCommand` wrapper delegates directly to the captured vanilla `DataCommands` callback; it is **not** specialized entity position access. `DataStoreParser` only accepts `execute store ... storage ...`, **not** `execute store ... entity ...`. Therefore the current legacy storage-lowering path does not already optimize these three entity stores. MixedFunctionIR's typed scoreboard backend likewise does not lower these commands. These are specific compiler coverage gaps, not proof that optimized execution is feasible.

## 3. Candidate mechanisms, in increasing semantic risk

**First hypothesis (preferred feasibility test): a narrow typed inner `data get entity @s Pos[axis]` specialization.** Admit only after normal Brigadier parse, with the exact entity-selector, path, scale and result-bearing action verified. Keep the original `execute store` redirect, CommandSourceStack, callback consumer, native queue tasks and per-source quota behavior intact. Replace only the leaf getter *if* official mapped Minecraft behavior proves that a direct live coordinate read can produce exactly the same command result, exception/feedback and NBT-visible value as the vanilla entity-data-accessor read. Otherwise decline or delegate unchanged. This hypothesis targets redundant entity NBT snapshot materialization, not the necessary result-store mutation.

**Second hypothesis (separate milestone only if first is viable): specialized typed per-axis entity result store.** Preserve a distinct original command action, original source index, mutation boundary, callback, result, exception, quota debit and failure state for **each** x/y/z assignment. Determine whether a carefully bounded data-accessor operation can avoid redundant serialization/writeback of unrelated entity fields. Do not assume direct mutation of `customData` is equivalent to the `DataCommands` entity-data accessor.

**Not admitted:** collapsing all three commands into one blind `{x,y,z}` write, caching a mutable entity NBT compound across commands, rewriting the original publisher datapack, a general global NBT accessor Mixin, or reusing a selector/tag index. A single fused write would silently change intermediate state visibility, callback counts, command quota truncation and error handling. This is a compiler-pattern hypothesis, not a license to replace global Minecraft entity serialization.

## 4. IR-030 investigation gates

### Gate A — original 26.3 method-contract audit, no optimizer

**Existing verified partial evidence:** `docs/research/26.3-internals.md` inspected the exact mapped 26.3 entity macro-argument path and found `EntityDataAccessor.getData()` calls `NbtPredicate.getEntityTagToCompare`, which constructs a `TagValueOutput` and invokes `Entity.saveWithoutId` **before** projecting the requested NBT path. That is evidence of full entity NBT materialization in a **macro argument** path, not yet proof that the `data get entity @s Pos[i]` command uses exactly the same execution path, or that any direct position getter matches its numeric, feedback and callback semantics.

Inspect the exact Loom-mapped Minecraft 26.3 server bytecode (fingerprint in `docs/research/source-versions.lock`) for `DataCommands`, entity data accessors, `execute store result entity`'s callback factory, `NbtPathArgument`, CommandSourceStack result consumers and native queued execution. Record method descriptors and control flow, not third-party decompiled source. Establish:

1. How `data get entity @s Pos[axis]` obtains the selected entity NBT; whether `Pos[axis]` always reflects live entity position at that command boundary.
2. Numeric conversion and rounding for positive, negative, fractional and out-of-range values; success and return result; handling of absent/malformed paths and malformed entity data.
3. Required permission checks; whether original command feedback, trace, callbacks or error reporting would be affected by a direct inner getter.
4. Actual entity-data `setData` behavior of the outer result-store stage; whether a write serializes/restores unrelated fields and whether Bellows changes this path.

**Hard STOP** if the exact native contract cannot be matched by an explicitly narrow, fall-through-safe compiler action. A plausible Java field read is not semantic equivalence.

### Gate B — prove an avoidable cost before code generation

Reuse the unchanged original Vein Miner event and source pin. Distinguish three costs: native `data get` source/entity snapshot materialization, outer result-store write/feedback, and essential world state mutation. Prefer a separate JFR stack-attribution or carefully controlled, non-mutating method-boundary census to identify whether a sizeable cost actually lies in repeated *read* work. Report overlapping stack fractions and population/host quality explicitly; never interpret the 11.15% callback projection as wholly eliminable.

The existing Bellows 1.1.3 compatibility and path-filtered NBT optimizations are important controls: measure the candidate in vanilla-Fabric first, and later on the known compatible Bellows stack. Do not duplicate an existing optimized accessor for no demonstrable incremental benefit. If the avoidable read portion is small or invisible against noise, **STOP** and record a negative finding.

### Gate C — differential semantics before performance

A future opt-in research implementation must compare **native vanilla command**, native Fabric wrapper, and specialized path on exact parsed original commands, including:

- Missing `@s`, wrong entity type, permission failure, missing or malformed `Pos`/frontier data, negative and fractional coordinates, results of zero, nonzero, and failure.
- Literal entity selector parsing, exact three-axis order, unchanged per-command feedback and result forwarding, exception behavior, and any loaded-world/entity-data side effects.
- Command quotas around every stage (including cuts between x, y and z), nested and reentrant callbacks, scoreboard/data updates during execution, `/return`, function nesting, reload and ordinary fallback behavior.
- Intermediate NBT snapshots **after each original command**, not just final frontier entries, plus exact original-world ore/queue/end-state conservation.

No observer may silently change scheduler order or omit an original quota charge. If the safe implementation has to call the same expensive original getter anyway, reject the specialization rather than claiming it compiled meaningful work.

### Gate D — uninstrumented A/A and A/B only after Gate C

Use fresh Minecraft 26.3/Java25 JVMs; keep actual publisher ZIP, 6×6×6 survival mining, 215 work units, 1,952 queue-head increments, final marker/source state, compiler flags and host-quality gates fixed. Control A must use the **same installed research jar** with the fast inner getter disabled; B changes only the proposed lowering gate, leaving the original outer store native. Do not mix JFR, CPU probes or diagnostic counters into the measured arms. Preregister order, host A/A gate, workload parity and acceptable confidence interval before observing effect. Report both Linux Server-thread running CPU and whole-event completion, and run an independent replication before promotion. A negative or noisy result is acceptable.

The overall project policy continues to require a material real-workload improvement and exact semantic parity; passing a narrow microbenchmark is insufficient.

## 5. Decision and next action

**IR-030 target selected for feasibility inspection, not implementation:** read-side specialization of the **inner** `data get entity @s Pos[i]` executed by the three original entity result-store commands. It is worth studying because CPU005 measured a much larger inclusive native hot path than IR-025, and current parser/IR coverage does not optimize it. The unresolved question is whether **avoidable** repeated entity-NBT read work is appreciable once real world mutation and feedback semantics are preserved.

**Immediate next executable stage:** exact mapped 26.3 method inspection (Gate A), then cost attribution (Gate B). No new compiler bytecode, NBT cache, native benchmark result or production-default change has yet occurred. Keep prior IR-023–029 workflows archived/manual-only, and retain draft PR #10.

## Related evidence

- [CPU005 native source and cost](compiler-queue-cpu-005.md)
- [IR023 direct tag-set mutation invalidation failure](compiler-typed-ir-023.md)
- [IR025–029 completed fork, restoration, CPU and JFR follow-ups](compiler-typed-ir-025.md)
- [IR029 descriptive JFR](compiler-typed-ir-029.md)
- [Bellows 1.1.3 native data-accessor comparison](bellows-audit.md)


## 6. Gate A verification — native command contracts (2026-11-21)

The [original source-order gate #44962242736](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44962242736) passed publisher SHA-256 verification of the exact original Vein Miner ZIP and proved all five non-comment `vm:queue/append_here` lines occur in original order at zero-based source indices 0–4, uniquely across the publisher functions. Five source-parser unit tests also passed. This is a source-order proof, **not** an independent parsed Brigadier or gameplay semantic proof.

The [mapped Java25/Minecraft26.3 inspection #44962539874](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44962539874) succeeded with the explicit observed Loom artifact SHA-256 `cde5273d134d4e1914a563552ab1b3e0e478dc11bb62730b9aedb7c0da2fd042` (provenance separately recorded in `source-versions.lock`). Its method inventory and original javap bytecode text are in the CI artifact, including **both distinct native ExecuteCommand classes** and the nested `NbtPathArgument$NbtPath`. Current mapped `NbtPredicate` is `net.minecraft.advancements.predicates.NbtPredicate`. This derived mapped artifact's SHA is not the official Mojang server SHA.

### Mapped method facts

- `DataCommands.getSingleTag(path, accessor)` invokes `DataAccessor.getData()` **before** `NbtPath.get(compound)`, then rejects multiple matches; missing path nodes throw a command exception. In the unscaled `DataCommands.getData(source, accessor, path)`, numeric results are **`Mth.floor(NumericTag.doubleValue())`**, not truncating Java casts. It emits its original success feedback with `sendSuccess(..., false)`. Non-numeric tags have different result rules; a direct read cannot presume a numeric tag without admission/fallback.
- `EntityDataAccessor.getData()` delegates to `NbtPredicate.getEntityTagToCompare`, constructing a `TagValueOutput`, invoking `Entity.saveWithoutId`, and building a complete `CompoundTag`. That is an expensive-looking native snapshot operation, **not yet a measured avoidable CPU fraction**.
- **Mounted-entity counterexample:** `Entity.saveWithoutId` writes ordinary `Pos` from `entity.position()` if not riding. If the entity has a vehicle, it writes the **vehicle X and Z** with the **passenger Y**. Therefore the tempting replacement `entity.getX()/getZ()` is not generally semantically equivalent, independent of any possible modded serialization.
- `net.minecraft.server.commands.ExecuteCommand.storeData` installs a callback using `CommandSourceStack.withCallback`. The callback `lambda$storeData$0` **independently reads destination NBT**, computes the result-versus-success integer, invokes `NbtPath.set`, and then `DataAccessor.setData` even when the setter's return count is not used. It catches `CommandSyntaxException`. `EntityDataAccessor.setData` refuses player destinations, creates `TagValueInput`, invokes `Entity.load`, restores UUID and calls `postDataManipulated`. This mutable state work cannot be bypassed by optimizing the inner getter alone.
- `DataGetCommand` in the current compiler is a wrapper that delegates the original callback. Its legacy outer `DataStoreParser` accepts storage destinations, not `execute store ... entity`, so it does not compile away this native entity store.

**Gate A decision:** Static native path inspection is accepted. A naïve unguarded coordinate getter is **rejected**. A future bounded specialization would need to preserve native flooring, NBT-path errors, feedback, per-command quota/result callbacks and passenger positioning; decline to native when the source or serialization semantics are not demonstrably identical. Do not merge x/y/z stores or bypass `Entity.load` as an untested shortcut.

## 7. Gate B separate attribution (accepted, descriptive)

The [original-event JFR workflow](../../.github/workflows/research-typed-ir030-jfr.yml) runs the unchanged SHA-pinned publisher in two independent compiler-off Fabric/Minecraft 26.3 servers, requiring 215 original work units, 1,952 queue steps, host-quality gates and real Server-thread ExecutionSample stacks. It reports **overlapping inclusive** read-command, entity-serialization, outer-store, and full entity-write stack presence; these must never be summed or interpreted as a speedup. The prior CPU005 ~11.15% inclusive inner `data get` estimate, already below the project's ≥15% full-event promotion bar, is a warning to measure genuinely removable read cost before building any optimizer. No treatment path or production change is active.


### Gate B two-original-JVM JFR results — 2026-11-21

The [accepted original-publisher JFR workflow #44962701664](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44962701664) completed with [raw JFR, original-event manifests, and parsed results](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44962701664/artifacts/14730685562). Both Java25/Minecraft26.3 Fabric arms ran the **unchanged pinned publisher with compiler off**, no Spark or callback metrics. Each completed 215 ore work units, exactly 1,952 queue-head increments, with zero remaining source/ore/markers, valid idle/host-quality gates, zero throttling. Separately measured original Server-thread running CPU was 14.034s and 13.352s, **not** a treatment comparison.

| Inclusive JFR runnable Server-thread frame presence | Original 1 (1,254 samples) | Original 2 (1,195 samples) |
| --- | ---: | ---: |
| Original DataCommands inner read | **21.61%** | **16.99%** |
| Inner read with entity snapshot serialization | **21.45%** | **16.99%** |
| Native outer result-store callback | **13.80%** | **12.72%** |
| Outer store with entity serialization | **8.37%** | **7.20%** |
| Any entity snapshot serialization | **51.75%** | **45.69%** |
| EntityDataAccessor.setData | **7.74%** | **8.95%** |
| Entity.load | **7.50%** | **8.95%** |

**Interpretation and nonclaims.** All fractions are inclusive, may overlap and must not be added. The ~46–52% entity-serialization presence covers many original event commands, macro activity and NBT operations, not just the three coordinate getter sites. Even the ~17–22% original read-path presence applies to **all** matching DataCommands read callsites in the event; JFR stack frame alone does not identify which specific mcfunction line initiated it. The earlier CPU005 original five-command site-specific sparse-clock projection (11.15% inclusive in nested getter) is distinct and cannot be subtracted from or replaced by this profile. None of these observations is a demonstrated avoidable cost or speedup.

Observed read-path innermost frames most often included CompoundTag copying, ListTag copying, HashMap iteration/insertion, and DelegatingOps map creation. This is concrete evidence for expensive entity NBT materialization, but leaves uncertain the safely eliminable part. The prior bytecode audit separately proved that an unconditional direct entity coordinate getter is incorrect when an entity is riding a vehicle.

**Gate B decision: ACCEPTED as descriptive mechanism attribution.** Follow with exact *source-site* exposure attribution and focused native semantic fixtures for a **narrow conditional getter** (entity type, no vehicle, exact parsed path, numeric flooring, native feedback, quota and error behavior). Preserve outer native result-store callback and entity write/reload, and fall back under any unproved condition. Do not implement or promote a general entity NBT cache or replacement. Only after semantic Gate C passes is an uninstrumented causal A/A–A/B compiler CPU pilot justified.
