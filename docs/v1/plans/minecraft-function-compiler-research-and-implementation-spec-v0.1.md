# Modern Minecraft Function Compiler
## Source Investigation, Architecture Decision Record, Validation Plan, and Implementation Specification

**Status:** Research baseline and gated prototype plan — **not** an approved production design. Prototype implementation and testing are in progress; no optimization is approved for default use.  
**Version:** 0.1 · **Prepared:** 2026-10-26  
**Primary target:** Minecraft Java Edition **26.3**, Fabric, server-side  
**Related systems:** Minecraft command engine, Brigadier, Mercury, MCFC, Bellows  
**Primary purpose:** A durable starting point for source verification, benchmarking, prototyping, architecture decisions, and regression testing.  
**Companion artifact:** [`minecraft-function-compiler-test-matrix-v0.1.csv`](minecraft-function-compiler-test-matrix-v0.1.csv) (80 test IDs, phase, priority, oracle, dependencies and run status).

> **Critical interpretation rule:** An attractive source-level integration point is not evidence of a speedup or semantic correctness. Treat both as independently testable hypotheses. Do not implement the full compiler until the foundational hypotheses have been tested.

> **Evidence update (2026-10-28):** The pinned 26.3 Fabric build now has a
> mod-free vanilla differential harness and disabled prototypes for literal
> ScoreAdd, macro expansion specialization, fused interpreted regions, and
> emitted bytecode. The full runtime suite has eight arms: vanilla plus seven
> Fabric modes, including emitted bytecode. It covers 16 direct-function
> fixtures, quota and scoreboard cases, fork limits 1–12, macros, lifecycle,
> and debug traces. A separate injected compile-failure run observes 30 failed
> bytecode compilations, zero emitted/executed regions, and successful fallback
> through the retained original actions. A Fabric-only modded Brigadier leaf
> also runs once between eligible regions in wrapper-off, wrapper-on, ScoreAdd,
> fused, and bytecode arms; it stores result 7, preserves total score 15, and
> matches the compiler-off control. The emitted entry implements the exact
> erased `UnboundEntryAction.execute(Object, ExecutionContext, Frame)V`
> interface descriptor. A 25-cycle changed-body/tag reload run retains 15 live
> generated classes after each GC with stable defining classloader identity and
> about 1.03 MiB maximum metaspace growth. Focused runtime probes now cover
> malformed ordinary-function and macro-template parsing plus a failed
> whole-resource reload; a six-request out-of-order publication also matches
> vanilla in all nine Fabric runtime modes. Seven-or-more-request interleavings and other macro failure shapes
> remain open. The focused macro differential preserves vanilla's equality-aware
> eight-entry LRU and checks tuple churn, storage changes, hash collision, and
> invalid-argument cases across seven arms. A Bellows 1.1.2 adapter restores
> vanilla mob `home_pos` values in the tested init/merge/modify/remove paths;
> other filtered NBT paths remain unsupported until verified.
>
> **Control-flow update (2026-10-29):** The full ten-arm 26.3 run now includes
> an `execute if function` child that adds 1, returns failure, and has a
> pending fused `+100/+100` tail. The failed callback skips the branch's
> `+1000`, then resumes the parent's pending `+10/+20` tail exactly once. All
> nine Fabric modes match mod-free vanilla at score 31 with the exact
> five-event trace; fused and bytecode each execute exactly one parent-tail
> region. An inverse `execute unless function` child also returns failure,
> takes the `+1000` branch, discards its child tail, and resumes the parent
> tail once. All ten arms reach score 1032 with the exact six-event trace; the
> parent region executes once in fused and bytecode. The full run compares 83
> debug traces per arm. A second isolated call uses `execute store success`; its failed
> child stores 0, discards its pending `+100/+100` tail, and resumes the
> parent's `+10/+20` tail once at score 32. The exact six-event trace matches
> vanilla in all ten arms, with one parent continuation region in fused and
> bytecode. A paired `execute store result` call returns 7 from the child,
> stores that value, discards the child's pending `+100/+100` tail, and resumes
> the parent's tail once at score 32. All ten arms match the exact six-event
> trace, with one parent region in fused and bytecode. A failed `execute store result` child stores 0,
> discards its pending `+100/+100` tail, and resumes the parent's tail once at
> score 32; all ten arms match the six-event trace and execute one parent
> region in each optimized backend. A successful `execute store success` child
> that returns 7 stores success value 1, discards its pending `+100/+100` tail,
> and resumes the parent's `+10/+20` tail once at score 32. All ten arms match
> the exact six-event trace; fused and bytecode each execute one parent region.
> A nested `execute store result` case calls a wrapper that uses `return run function`
> to invoke a child returning 7 with pending child and wrapper `+100/+100` tails;
> stored result receives 7, both tails are discarded, and the parent `+10/+20`
> continuation resumes once at score 37. Paired nested `execute store success`
> calls around the same wrapper shape store 1 when the child returns 7 and 0 when
> the child returns failure, discard both pending tails, and resume the parent
> tail once at score 37. All ten arms match the exact eight-event traces; fused
> and bytecode each execute one parent continuation region per case.
> The current full run compares 88 debug traces per arm. See the maintained
> verification workflow and CTRL-007 matrix row.
>
> PERF-004 completed five server-thread full-function timing trials per arm for
> the vanilla delegate, ScoreAdd, fused interpretation, and emitted bytecode.
> Median queue times were 2.500 ms, 2.784 ms, 1.537 ms, and 1.890 ms on the
> static 5,000-add fixture. Bytecode was 23.0% slower than fused interpretation
> and is not selected on this evidence. ScoreAdd was 11.4% slower than the
> delegate. Earlier ten-trial fused timing showed 40.8% lower median than the
> delegate and 36.0% lower than ScoreAdd on the same fixture. Timer overhead
> remains uncalibrated. PERF-011 exercises eligible direct ScoreAdd work in
> Vein Miner 5.3.0: five Fabric pairs show no reliable gain, while five
> Fabric+Lithium and five Fabric+Lithium+Moonrise 1.2.1 pairs have slower
> medians with wide ranges and no reliable causal result. The Moonrise campaign
> carried a temporary dormant diagnostic mixin in both arms. No tested stack
> demonstrates a real-world ScoreAdd speedup. No screened datapack has an
> adjacent eligible pair for real-world fused or bytecode measurements.
> Compiler-off Vein Miner controls fail workload integrity on Bellows 1.1.2,
> Lithium+Bellows, and Lithium+Bellows+Moonrise 1.2.0, so these are invalid
> datapack/mod workload comparisons, not compiler comparisons; use a separate
> workload for those stacks. All optimization prototypes remain disabled. Vanilla
> behavior parity is the acceptance contract; mod-specific divergence requires
> a verified adapter restoring vanilla behavior or fallback to vanilla for the
> affected path. See [`current-state.md`](../../current-state.md) and
> [`26.3-internals.md`](../../research/26.3-internals.md). Statements below
> describing the initial no-build baseline refer to the plan's preparation
> state.


> **PERF-005/006 evidence update (2026-10-28):** Five randomized trials per arm
> compared vanilla, Fabric/compiler-off, Bellows/compiler-off, fused
> interpretation, and Bellows plus fused interpretation on controlled selector
> and entity-NBT tick fixtures. All 20 non-vanilla arm/trial normalized outputs
> matched vanilla. Bellows lowered the paired median `ServerFunctionManager`
> sample share by 67.6% on the NBT fixture. The fused compiler showed no
> repeatable sample reduction; whole-server tick timing was variable. Keep
> compiler prototypes disabled. This synthetic fixture does not close PERF-007;
> see [`PERF-005/006 report`](../../../benchmarks/PERF-005-006-bellows-selector-nbt.md).
---

## 0. Executive summary

### 0.1 Key conclusions

1. **Ordinary functions are already parsed at reload time.** Minecraft does not reparse the text of every ordinary `.mcfunction` command on each invocation. Replacing Brigadier *parsing* is therefore unlikely to be the major source of steady-state speedups; eliminating general-purpose **runtime context handling and command dispatch**, reducing redundant world lookups, and specializing macros are stronger hypotheses.
2. **Vanilla's function scheduler is not a naive recursive interpreter.** It uses an `ExecutionContext`, queue entries, frames, and incremental continuation scheduling. Its function invocation and queue machinery should be kept intact in the initial prototype.
3. **The observed charging sites are `CallFunction`, `BuildContexts`, and `ExecuteCommand`, not an unconditional cost per function line.** The queue driver checks exhaustion before dispatching each queued entry. The difference between a *cost event* and a *yield/check boundary* is essential for fused-code correctness.
4. **A custom `UnboundEntryAction` is technically plausible; a custom `CommandFunction`/`InstantiatedFunction` wrapper is also plausible.** Neither is itself an optimization. Both are ways to install a specialized executor. A wrapper around the original function plus a guarded compiled procedure is a leading integration candidate, not yet a proven 26.3 hook.
5. **The least invasive candidate is around function construction**, specifically `FunctionBuilder.build(...)` returning an ordinary function, or another narrow post-parse/pre-publication hook. This avoids overwriting `ServerFunctionLibrary.reload()` and leaves `ExecutionContext.runCommandQueue()` alone. **It must be tested against function tags and reload lifecycle.**
6. **Whole-region compilation with suspension/resumption is demonstrably implementable on older Minecraft.** Mercury uses a compiled function wrapper, compiled action, fallback action and continuation mechanism, with scoreboard-slot promotion, inlining, and macro specializations. This is a source-backed precedent, **not** a 26.3 compatibility or performance result.
7. **The pinned MCFC development snapshot is newer and deeper than the previously discussed published 0.3.x release.** Commit `15ca1db` contains an **in-development `0.4.0-alpha.1`** branch targeting **Minecraft 26.1.2 / Java 25**, with a separate command parser, typed intermediate instructions, optimizer passes, and class-file generation. It intercepts manager and `CallFunction` execution; its README explicitly says compiled code does not honor the historical command-chain limit. The [curated MCFC audit](../../research/mcfc-audit.md) records source findings and limits; this remains a reference, not a semantic-correctness blueprint.
8. **Bellows overlaps predominantly at the runtime/world-operation layer.** Its actual Mixins index entity types/tags and optimize selected NBT access paths. A compiler should not duplicate those indexes, but should also avoid bypassing the Minecraft methods Bellows patches without proving that its replacement is faster and interoperable.
9. **No optimization has demonstrated a general or real-world 26.3 speedup.** PERF-002's narrow ScoreAdd prototype is effectively tied with vanilla on median RCON-driven throughput, and its one-per-arm allocation samples estimate more allocation than vanilla. A five-trial callback timer showed a 41% lower ScoreAdd `Command.run` median but excluded scheduling; the earlier full-function timer measured ScoreAdd 14.8% slower by median in the fixed fixture. A separate fused-region queue timer then completed ten trials per arm across two randomized sets and measured fused 40.8% lower than the instrument-only delegate and 36.0% lower than ScoreAdd by combined median on that same static fixture. These results support further measurement of the fused path but do not close real-world workload, memory/reload, or full parity gates. All optimizations remain disabled, and no execution backend is selected.

### 0.2 Provisional architecture recommendation

```text
Source data packs
  -> vanilla resource resolution and Brigadier parsing
  -> capture validated parsed command/actions plus source provenance
  -> immutable, reload-scoped semantic IR
  -> conservative recognition and effect analysis
  -> [vanilla action | specialized entry | resumable compiled region]
  -> vanilla CallFunction + ExecutionContext + Frame scheduling
  -> vanilla Minecraft world APIs, retaining Bellows interception where applicable
```

**Backend decision:** The first controlled comparison is complete for the
static 5,000-add fixture. Emitted bytecode was slower than fused interpreted
by median, so it is not selected on current evidence. Keep it as a disabled
prototype until allocation, larger compilation, and a real-world eligible
region workload establish whether it adds enough value to justify its lifecycle
cost.

**Initial implementation policy:** Fall back to vanilla at a **function boundary** when any correctness invariant cannot be established. Fine-grained fallback inside a compiled function may be enabled later, after continuation ordering is verified.

### 0.3 Priority order

**P0 / semantic baseline before enabling optimizations:** exact Minecraft 26.3 classfile inspection and static cost/reload inventory are recorded. The target toolchain and mod-free vanilla harness are verified. Sixteen direct function fixtures, scoreboard edge cases, zero/one/two/four fork-match cases across limits 1–12, and a four-target execute followed by a queued action across sequence limits 0–16; all eight modes match vanilla, with the follow-up stopped through limit 7 and executed at limit 8. Macro hash collisions and argument errors, fallback resumption, and flat/nested debug traces match across vanilla plus seven Fabric arms. Five changed-body/tag generations, removal/re-addition, and a separate 25-cycle bytecode retention check pass; a same-argument macro body reload also changes its marker from 1 to 10 in vanilla and all seven Fabric modes, with specialization counts advancing once in each of the five macro-specializing modes. Malformed-function parse and failed whole-resource reload cases now have
focused runtime evidence. A held background reload preserves old direct, tag,
and macro behavior during preparation and publishes the complete new generation
in all seven Fabric modes. The six-request overlap probe matches vanilla in all
nine runtime modes: generations B, C, D, E, and F publish while A is held, then
A publishes last. Seven-or-more-request interleavings and macro failure shapes
beyond the staged-body/selective-argument path remain open. Injected
backend compile failures fall back to original actions. Fused and bytecode fixtures preserve tested post-mutation continuation, quota, and trace behavior, including nested calls and frame-discard paths. The 2026-10-28 full eight-arm rerun also matches exact vanilla traces for stored function results, success/failure `execute if/unless function`, and `return run` callbacks. Nested syntax-error cases match all eight runtime modes: `return run function` preserves the child's post-error `+2` and discards the parent's trailing `+4`; `execute if function` preserves the child effect but evaluates false, skipping its `+10` branch before the outer `+1`; and `execute unless function` takes the inverted branch after the same error and reaches score 14. The unless map and all 17 per-limit debug traces match vanilla across all seven Fabric modes for limits 0–16. Its state map and high-quota trace also match in the full 16-arm compatibility run `20261029T014306`. Paired `execute store result/success` calls around the same erroring child preserve completed side effects but leave both store destinations unchanged; the 0–16 map and six-event trace match all eight runtime modes and all 16 compatibility arms in run `20261029T020726`. The other nested maps remain `0,0,1,1,1,3…` for `return run function` and `0,0,0,0,2,3…` for `execute if function`. Focused selector/NBT probes cover the nine-arm interpreted matrix, while selected bytecode compatibility checks add a five-arm subset. The Bellows `home_pos` adapter restores the exact vanilla values for verified init/merge/modify/remove cases. A modded unknown Brigadier leaf also passes same-stack fallback checks between optimized regions. PERF-011 now provides native, real-datapack direct ScoreAdd coverage on Vein Miner. Five-pair campaigns on Fabric, Fabric+Lithium, and Fabric+Lithium+Moonrise 1.2.1 show no reliable gain; the latter two trend slower by median with wide ranges, and the Moonrise campaign included a temporary dormant diagnostic mixin in both arms. The Bellows 1.1.2 Vein Miner controls fail workload integrity and remain invalid comparisons. Bellows 1.1.3 + Moonrise 1.2.0 now passes the native 6×6×6 workload and a five-pair selective-macro screen with exact parity; Moonrise 1.2.1 still fails Bellows mixin startup. No screened datapack has an adjacent eligible pair for real-world fused/bytecode testing. Call-path analysis of all 15 valid compiler-off Vein Miner profiles finds macro argument construction followed by full entity serialization in `Entity.saveWithoutId`; the pack repeatedly passes entity data to macros that consume only a few values. This is a profile-backed candidate for a selective argument prototype, not an implemented optimization or exact timer. An opt-in ordinary leaf-callback diagnostic now counts generic and optimized callbacks on a native Vein Miner event; one 4×4×4 Lithium run recorded 7,116 generic and 1,122 optimized callbacks, with the latter matching the independent ScoreAdd counter. The diagnostic excludes execute modifiers and custom executors and is not timing evidence. Prioritize validating the entity-argument serialization lead before expanding the ScoreAdd target or backend variants. Remaining P0 work includes other selector-shape combinations and mod-specific fork failure paths, other callback cases, seven-or-more-request reload interleavings and macro failure shapes beyond the staged-body/selective-argument path, broader compatibility semantics, filtered-NBT paths beyond this adapter, timer calibration, and selected compatibility profiles. No optimization may be enabled until the remaining semantic, compatibility, and performance gates are addressed.

PERF-005/006 now have five randomized matched timing/profile repetitions across
the vanilla, Fabric, Bellows, fused, and combined arms. The exact checked
selector counts and NBT state match the vanilla oracle in all 20 non-vanilla
arm/trial comparisons. Bellows reduced sampled function share on the selected
entity-NBT fixture; fused interpretation showed no repeatable reduction and
remains disabled. These controlled measurements do not close PERF-007 or the
remaining semantic, compatibility, reload, and callback gates.

**P1 / feasibility:** narrow function-construction wrapper and tag/reload correctness; instrumentation-only execution path; quantify overhead.  
**P2 / compilation baseline:** typed scoreboard specialization, cost-equivalent single-command entries, robust fallback.  
**P3 / throughput:** budget-aware resumable regions; differential tests; actual speedup results.  
**P4 / advanced optimization:** cross-command and cross-function analyses, dynamic macros, bytecode backends, selective integration with Bellows.

---

## 1. Scope, non-goals, constraints, and evidence status

### 1.1 Scope

- Understand Minecraft **26.3** function parsing, command execution, function calls, forks, returns, budgets, callbacks and traces.
- Identify the **least invasive possible implementation hook** for a Fabric server-side optimizing function compiler.
- Evaluate the real designs and limitations of **Mercury**, pinned **MCFC** source and **Bellows**.
- Define a **versioned optimization IR and execution contract**, without prematurely committing to a bytecode backend.
- Produce executable research questions, prototype acceptance criteria, an experiment matrix, compatibility checks and phase completion gates.

### 1.2 Non-goals in the initial implementation

- Replacing Brigadier grammar or all of Minecraft's command infrastructure.
- Replacing the global scheduler, `Frame`, or `CallFunction` merely to avoid method calls.
- Complete coverage of every vanilla/modded command at the outset.
- World-state optimizations that duplicate Bellows' entity indices or general NBT read filtering.
- Changing command limits, results, errors, tag ordering, function returns or visible world behavior as a performance tradeoff.
- Publishing redistributed decompiled Mojang source or assuming Minecraft internal APIs remain stable across versions.
- Depending on the prospective compiler for Minecraft Recrafted's core gameplay behavior.

### 1.3 Evidence labels and standards

Throughout this document:

- **[V-MCFC]** — static review of pinned commit `15ca1db`, targeting Minecraft 26.1.2; see [`mcfc-audit.md`](../../research/mcfc-audit.md).
- **[V-MERCURY]** — static review of pinned commit `193d65b`, targeting Minecraft 1.21.4; see [`mercury-audit.md`](../../research/mercury-audit.md).
- **[V-BELLOWS]** — static review of release 1.1.0, commit `59f6e80`, targeting Minecraft 26.3; see [`bellows-audit.md`](../../research/bellows-audit.md).
- **[V-26.3]** — static inspection of the fingerprinted official Minecraft 26.3 server artifact and Loom-produced classfiles; see [`26.3-internals.md`](../../research/26.3-internals.md) and [`source-versions.lock`](../../research/source-versions.lock).
- **[RUNTIME-PROTOTYPE]** — behavior observed in the wrapper-only Fabric 26.3 probe; see [`26.3-internals.md`](../../research/26.3-internals.md). It does not imply a mod-free vanilla comparison or full semantic parity.
- **[V-COMPARE]** — static `javap` comparison of selected 26.1.2, 26.2, and 26.3 classes recorded in [`26.3-internals.md`](../../research/26.3-internals.md).
- **[R-26.3]** — third-party source-oriented documentation or API references; secondary evidence only, not a replacement for the exact artifact.
- **[HYP]** — design hypothesis; needs experiment or proof.
- **[OPEN]** — not yet verified, or a specific risk requiring investigation.

A finding can have more than one label. Source-code evidence proves a code path exists; it does **not** prove that the project successfully compiles, runs, preserves vanilla semantics, scales, or produces speedups.

### 1.4 Research and reproducibility limitations

- At plan preparation, the official Minecraft 26.3 server bundle and Loom-produced merged classfile artifact were fingerprinted, but no Fabric mod had been built or run. The later wrapper-only runtime result is recorded in [`26.3-internals.md`](../../research/26.3-internals.md); it does not close the compiler's semantic, reload, compatibility, or performance gates.
- MCFC, Mercury, and Bellows source snapshots are pinned in [`reference-sources.lock`](../../research/reference-sources.lock); the static findings and scope limits are in the corresponding audit pages. No external project was built or run for this review.
- Focused runtime probes for Bellows 1.1.2 found no selector AABB/order divergence in the tested cases, confirmed entity-tag index updates after NBT tag writes, and reproduced a `home_pos` write/remove divergence from vanilla. A Bellows-specific adapter now restores vanilla results for the tested `home_pos` init/merge/modify/remove cases. The related source audit is pinned to Bellows 1.1.0, so runtime findings are scoped to 1.1.2 while code explanations remain revision-specific.
- The best estimate of optimization opportunities remains **qualitative**. A profiler and controlled benchmarks must decide which optimizations to ship.

---

## 2. Source inventory and reproducibility manifest

### 2.1 Pinned external sources

Exact repositories, revisions, target versions, and licenses are recorded in
[`reference-sources.lock`](../../research/reference-sources.lock). Curated
findings and source links are maintained separately:

| Review | Pinned snapshot | Scope |
|---|---|---|
| [MCFC](../../research/mcfc-audit.md) | `15ca1db43556999ff29619ed0e41c971b66aae3e` | Minecraft 26.1.2 development branch; custom parser, typed IR, code generation, runtime interception, test scope. |
| [Mercury](../../research/mercury-audit.md) | `193d65bd031debf6539136427339f9ce1619696c` | Minecraft 1.21.4; parse capture, reload integration, compiled actions, fallback, macros, tests and benchmark tooling. |
| [Bellows](../../research/bellows-audit.md) | tag `1.1.0`, commit `59f6e80514da6022aa4d2afd87bab201c2ed94fd` | Minecraft 26.3; selector and NBT interception paths compared to the exact target artifact. |

These are static source reviews. Their build, test, benchmark, and runtime
claims were not reproduced here. Each audit separates code observations from
runtime questions and candidate defects.

### 2.2 Exact Minecraft source artifacts [V-26.3] [V-COMPARE]

The official server bundles and Loom-produced classfile artifact fingerprints
for Minecraft 26.1.2, 26.2, and 26.3 are recorded in
[`source-versions.lock`](../../research/source-versions.lock). The 26.3 bundle
SHA-1 matches Mojang's version metadata. Static inspection used `javap` and
Vineflower against the fingerprinted merged-deobfuscated classfiles; temporary
decompilation output was not added to the project.

Exact method descriptors, queue and quota behavior, function construction,
reload and tag publication, and the selected cross-version comparison are
documented in [`26.3-internals.md`](../../research/26.3-internals.md). This
confirms static source behavior only. Fabric Mixin application, low-quota
runtime traces, wrapper identity, differential correctness, and performance
remain open. The project's Fabric Loader, API, Loom, and Java build lock is not
configured.

---

## 3. Vanilla execution pipeline: observed behavior and optimization consequences

### 3.1 Reload-time function construction [V-26.3]

`ServerFunctionLibrary.reload` discovers resources, builds the function compilation source, prepares `CommandFunction.fromLines(...)` tasks, waits for completion and publishes the resulting functions and resolved function tags. This takes place within the Minecraft datapack/resource reload mechanism; function compilation can be performed concurrently.

`CommandFunction.fromLines` normalizes lines, rejects invalid leading slashes, handles continuation lines and macro markers, and routes ordinary commands through `parseCommand(...)`. `parseCommand` performs Brigadier parsing, validates the result, flattens the context chain and constructs **`BuildContexts.Unbound`**.

`FunctionBuilder.build` yields a `PlainTextFunction` for macro-free definitions, or a `MacroFunction` when macro templates exist. `PlainTextFunction` is essentially an immutable identifier plus `List<UnboundEntryAction<T>>`; it is also an `InstantiatedFunction` and returns itself from `instantiate`.

**Consequence:** Brigadier parsing of ordinary functions already happens off the hot execution path. Replacing vanilla parsing with a second parser would add a version-maintenance burden unless it unlocks demonstrable compilation benefits unavailable from Brigadier's parse structures.

**Exception — macros:** `MacroFunction.instantiate` constructs a parameter tuple, checks a small equality-aware LRU (8 entries in the inspected 26.3 artifact), and substitutes/parses commands on misses. Real workloads with changing macro parameters are a legitimate dynamic parsing/specialization target.

### 3.2 Runtime invocation and scheduling [V-26.3]

```text
ServerFunctionManager / FunctionCommand
          |
          v
CommandFunction.instantiate(arguments, dispatcher)
          |
          v
ExecutionContext.queueInitialFunctionCall(...)
          |
          v
CallFunction.execute(sender, context, frame)
    |    |     |
    |    |     +-- trace function entry when active
    |    +-------- charge function-call cost (1)
    +------------- create nested Frame; schedule entries
          |
          v
ContinuationTask.schedule(...)
          |
          v
BuildContexts.Unbound.execute(...)
    |  trace original command start
    |  process already-parsed modifiers
    |  produce source set(s)
    +-- schedule command leaf or call custom executor
          |
          v
ExecuteCommand.execute(...) [ordinary Brigadier leaf]
    |-- charge leaf cost (1)
    |-- run executable against source / context
    +-- report callbacks, result, error, trace
```

**Important qualification:** `FunctionCommand` and control-flow-aware/custom executors do not necessarily pass through `ExecuteCommand` as a normal leaf. A text line is not a reliable unit of execution cost. Static path tracing of the exact 26.3 artifact confirms that a normal `function` call is charged on entry in `CallFunction` without an assumed extra ordinary-leaf charge. Direct ordinary-function runtime state now matches that model at limits 0–7; exact vanilla per-cost traces and other executor paths remain open.

### 3.3 Queue implementation [V-26.3]

`ExecutionContext` keeps a `Deque<CommandQueueEntry<T>>` and a staging collection (`newTopCommands`) for entries scheduled during execution. The queue driver merges staged work at the front in a defined order, then executes a popped entry. `Frame` carries depth, return callbacks and discard behavior. `ContinuationTask` schedules 0, 1 or 2 items specially and uses a reusable continuation for longer sequences.

**Consequence:** The scheduler already avoids eager whole-function queue expansion and recursive JVM stack calls. It may still have nonzero overhead, but no claim of a significant queue bottleneck is justified without profiling.

### 3.4 Where the general runtime overhead remains [V-26.3] [HYP]

The hot execution chain of an ordinary command can include entry binding, queue dispatch, command-source lists, Brigadier context-stage traversal, command modifiers, an `ExecuteCommand` entry, reconstruction/binding of the final executable `CommandContext`, profiling/callback logic, and the underlying operation (scoreboard, NBT, entity lookup, etc.).

Conceptual accounting (not measured):

`T_function = T_invocation + T_scheduling + T_context + T_leaf_dispatch + T_world_operations + T_callbacks + T_gc`.

**Do not infer percentages from the number of method calls.** HotSpot may inline or eliminate some allocations; actual world operations may dominate. Benchmarks must separate at least dispatch overhead from world-operation cost and allocations.

---

## 4. Execution-cost and scheduling semantics: precise working model

### 4.1 Configured limits [V-26.3]

In 26.3, relevant game rule identifiers are **`minecraft:max_command_sequence_length`** and **`minecraft:max_command_forks`**, represented by `GameRules.MAX_COMMAND_SEQUENCE_LENGTH` and `GameRules.MAX_COMMAND_FORKS`, respectively. Their documented defaults are **65,536**. The older names `maxCommandChainLength` and `maxCommandForkCount` are historical; they must not be used as the default 26.3 command syntax.

These represent **separate mechanisms**: a quota for an outermost command-execution context and a bound on a modifier stage's source expansion. They are not interchangeable.

### 4.2 Cost debit sites [V-26.3]

| Site | Charging behavior | Interpretation |
|---|---|---|
| `CallFunction.execute` | `incrementCost()` once when entering the function | Counts function invocation; it does not itself parse/execute every entry. |
| `BuildContexts.execute` | `incrementCost()` for a non-null non-custom redirect modifier stage | One debit per processed stage, **not automatically per resulting source**. |
| `ExecuteCommand.execute` | `incrementCost()` per executed normal leaf | With multiple selected sources, each scheduled leaf can independently charge. |
| `ContinuationTask` | No independent charge observed | Scheduling/bookkeeping is not a vanilla cost unit. |
| `Frame` creation | No independent charge observed | Frame lifecycle is not a command. |
| Queue insertion | No independent charge observed | Insertions are not cost units; queue overflow is separately guarded. |

**Special executors:** The exact-source path inventory includes custom function, return, and conditional-function paths in [`26.3-internals.md`](../../research/26.3-internals.md). Runtime traces for these paths are still required before treating the source model as observed behavior.

### 4.3 Budget check boundary [V-26.3]

In the exact 26.3 artifact, `ExecutionContext.incrementCost()` simply decrements `commandQuota`. The driver checks whether quota is exhausted **at the top of its queue-processing loop**, before executing the next entry. A multi-stage `BuildContexts` entry can debit several times without a scheduler check between each debit. The queue can therefore end an action in an exhausted state before stopping further queued work.

**Two different invariants:**

- **Charge equivalence:** The compiled path charges the same cost at the same semantic operations as vanilla.
- **Yield equivalence:** Compiled execution stops/returns to the queue at the same effective boundaries relevant to quota exhaustion and cancellation.

Neither invariant implies the other. **Never implement fused execution by only subtracting N once at block end.** Likewise, an eager check before every single charge may change vanilla behavior within a multi-modifier entry.

### 4.4 Worked reference examples [R-26.3; preconditions apply]

- Plain function with three successful scoreboard leaves: initial `CallFunction` **1** + three `ExecuteCommand` leaves **3**, total **4** units.
- `execute as @a at @s run say hi`, with exactly four eligible players and no failures: modifier stages **2** + successful `say` leaves **4**, total **6** units, plus any containing function-call cost.
- Outer function calling inner, each body containing one ordinary scoreboard leaf: outer call **1**, inner call **1**, two ordinary leaves **2**, total **4**. Do not add an assumed extra “function command leaf” charge without checking the custom-executor path.

These are **normal-path cost derivations**, not asserted behavior for every failure, early exit, permission change, or custom command.

### 4.5 Compiler obligations

Any compiled operation or region must implement an auditable **cost and yield contract**:

```text
CostEvent:
    kind: FUNCTION_CALL | MODIFIER_STAGE | NORMAL_LEAF | OTHER_EXPLICIT
    origin: function / line / context stage
    multiplicity: once | per executed source | dynamic
    eligibleQueueBoundary: semantic queue boundary before next dispatch

ExecutionOutcome:
    COMPLETED | SUSPENDED | RETURNED | ABORTED | FALLBACK
```

**[HYP]** A budget-aware fused region may inspect remaining quota through a narrowly scoped Mixin accessor while charging through vanilla's own `incrementCost()`. It must never independently reset or silently extend the quota. An alternative is continuation splitting before the point where vanilla would have returned to the queue. The implementation is subject to black-box differential tests, not just local code review.

### 4.6 Additional scheduling/correctness invariants

- Preserve current `Frame` identity/depth and callback relationships where observable.
- Preserve `queueNext` ordering, staging insertion order, and function continuations across nested calls.
- Preserve cancellation/discard behavior for `/return`, `/return run`, early failures and isolated function conditions.
- Preserve command-success and return-value contracts, including `execute store result/success`.
- Preserve total modifier/fork behavior and fork limits, not just leaf operations.
- Preserve tracer start/end, function entry, errors and command counts, or force a fully correct vanilla trace mode.
- Preserve interpretation of invalid/missing objectives, holders, NBT paths and entity targets.
- Handle reentrancy and commands that indirectly trigger more commands in the same context.
- Preserve the captured command-limit values across a command context even if game rules later change.

---

## 5. Integration options and preliminary architecture decision

### 5.1 Evaluation criteria

Score each candidate for **semantic fidelity, interception surface, compatibility, reload safety, tag identity, performance potential, observability, and ongoing maintenance burden**. Do not use “less code” as a substitute for all criteria.

| Approach | Where it acts | Strength | Main risk | Status |
|---|---|---|---|---|
| **A: Replace individual `UnboundEntryAction`** | Function entry list | Preserves vanilla queue boundaries; incremental command support | Scheduling overhead remains, and specialized action must charge/trace correctly | Feasible API shape; untested 26.3 |
| **B: Wrap `CommandFunction` / `InstantiatedFunction`** | Function construction or pre-publication | Retains original fallback, enables whole-region output | Tag/reference identity, trace-size mismatch, lifecycle complexity | **Preferred initial integration hypothesis** |
| **C: Custom `CallFunction` hook** | Runtime function entry | Easy place to decide compiled vs vanilla; MCFC precedent | Highly invasive semantics: nested scheduling, callbacks, cost and return behavior | Defer |
| **D: Replace function loader/reload body** | `ServerFunctionLibrary.reload` | Access to all sources and parse metadata | Conflicts with other reload transformations; fragile across versions | Avoid overwrite |
| **E: Replace `ExecutionContext` scheduler** | Queue driver | Maximum control | Major risk and maintenance, no measured justification | Out of scope |

### 5.2 Leading hook: `FunctionBuilder.build(...)` [HYP]

In nearby vanilla, `FunctionBuilder.build` is a package-private builder method constructing `PlainTextFunction` or `MacroFunction`. A Mixin at its return is a plausible place to preserve the original function and substitute a `CommandFunction` wrapper before the function is published/resolved in tags.

**Benefits:** narrow injection, no parser replacement, no queue changes, no function-loader overwrite, correct early wrapper identity *if every publication path uses that builder*.

**Open risks:** `FunctionBuilder` is not a public extension contract; method descriptors may change; builder is invoked asynchronously; the wrapper needs to retain macro semantics; tracing and indirect held references may require alternate paths; some mods may replace the builder or function definitions; compiled artifacts cannot be installed until cross-function analysis finishes.

**Required first test:** Fabric 26.3 mod wraps one known plain function while *executing its original entries unchanged*. Verify explicit `/function`, `#minecraft:load`, `#minecraft:tick`, custom function tags, `/reload`, and nested calls. This is a hook and identity experiment, **not** an optimization experiment.

### 5.3 Alternative hook: parse result interception [HYP]

Intercept the return from `CommandFunction.fromLines` or its invocation in `ServerFunctionLibrary.reload`; wrap the parsed function before map publication. This may be easier to bind to a stable public class than `FunctionBuilder`, but lambda method injection is often version-sensitive.

**Do not** blindly replace the published `functions` map *after* tag resolution: tags can hold references to previously published objects. Either wrap before tag building or provide a verified indirection mechanism shared by both map and tag views.

### 5.4 Wrapper lifecycle contract

```text
FunctionWrapper(id, original, generationToken)
    baseline = original function (always retained)
    artifact = atomically published, nullable
    on instantiate(arguments, dispatcher):
        if generation inactive -> original.instantiate(...)
        if macro unsupported -> original.instantiate(...)
        if artifact valid + mode permits -> compiled instantiated representation
        otherwise -> original.instantiate(...)
```

**Generation guarantee:** Artifacts and caches are scoped to a single immutable reload generation. Completion of a background compilation may not mutate a retired generation. Publishing a new generation must not leave tag references resolving old mutable artifacts. World-state-dependent compilation decisions cannot be made off-thread without safe snapshots.

**Trace guarantee:** A compiled representation with 1 entry is not necessarily trace-equivalent to 500 original entries. Investigate a tracing-aware wrapper or correctly reported source-level events. A global “disable compilation when tracing” command is insufficient unless it can select the original representation *before* the relevant function is queued.

### 5.5 Current ADR-001 (provisional)

**Decision:** Prototype wrapper-at-construction with immutable captured parse results and retained vanilla fallback. Preserve vanilla `CallFunction`, `Frame`, `ExecutionContext.runCommandQueue`, `ContinuationTask` and Brigadier parsing. Implement a single-command specialized-entry baseline before resumable fusion.  
**Not decided:** Exact Fabric Mixin target; whether a specialized interpreted or bytecode backend wins; when/how tracer fallback is selected; whether region fusion can preserve all command quota semantics.  
**Reversal condition:** Wrapper or identity tests fail, conflicts with common mods, or profiling reveals that all meaningful speedups require another less-compatible intervention.

---

---

## 6. MCFC deep audit [V-MCFC]

The pinned `0.4.0-alpha.1` development snapshot targets Minecraft 26.1.2 and
Java 25. It has an independent command parser, typed high-level instructions,
control-flow optimization, bytecode generation, and a function classloader.
Its Fabric hooks capture source during reload and intercept both manager-level
execution and `CallFunction` after the vanilla function-call cost debit.

The README explicitly states that compiled code does not respect
`maxCommandChainLength`. The current 26.3 rule identifier is
`minecraft:max_command_sequence_length`; exact target quota and queue behavior
is recorded in [`26.3-internals.md`](../../research/26.3-internals.md). The
current implementation also uses custom source parsing rather than compiling
vanilla's parsed Brigadier action objects. Its visible GameTest harness compares
compiled and vanilla state, but the three checked-in `.mctest` fixtures cover
scoreboard-player assignment and do not prove quota, trace, callback, frame,
macro, or error parity.

The useful lessons are typed IR, explicit command support limits, and
differential testing. The synchronous whole-function execution and quota policy
are not candidates for adoption without a separate 26.3 semantic proof. See the
[full MCFC audit](../../research/mcfc-audit.md) and pinned revision in
[`reference-sources.lock`](../../research/reference-sources.lock).

## 7. Mercury deep audit [V-MERCURY]

The pinned source targets Minecraft 1.21.4. It captures parsed command
structure and builds compiler IR, but also overwrites the function reload
method and a builder method, giving it a broad, version-sensitive integration
surface. Compiled functions retain vanilla actions as fallback and use queued
compiled actions with completion, return, suspension, and macro-prefetch
outcomes. The source contains scoreboard-slot caching with selected mutation
hooks, reflective command fallback, macro prefetch, guarded macro
specialization, and hot-caller Tier 2 recompilation.

Quota and tracing parity must be checked path by path: the explicit debit is in
the bound-command helper, while specialized lowering may bypass that helper.
This is a source-level question, not a runtime-confirmed defect. Its macro
materialization cache uses a rolling 32-bit argument hash in the key without a
full tuple comparison on lookup, making collisions a correctness review target.
The integration script tests selected features, and the benchmark script
compares Mercury on/off for one workload with a raised command-chain limit;
neither establishes comprehensive parity or a general performance claim.

The useful lessons are guarded specialization, preserving vanilla fallback,
resumable queue boundaries, and staged compilation. Avoid transferring 1.21.4
class names or scheduler assumptions to 26.3. See the [full Mercury audit](../../research/mercury-audit.md).

## 8. Bellows audit and interoperability requirements [V-BELLOWS]

Bellows 1.1.0 targets Minecraft 26.3 and optimizes selector candidate lookup
and selected entity NBT paths. Focused runtime checks with Bellows 1.1.2 found
that positive-tag `dx/dy/dz` selection, two tested boxes, nearest `limit=1`,
and nearest-sorted order-dependent effects matched vanilla. This does not
close the broader selector matrix. NBT tag modifications and removals also
kept the Bellows entity-tag index current for the tested entity.

Bellows 1.1.2 previously reported success for `home_pos` modify/remove while
leaving the mob position unchanged. The adapter in
`BellowsHomePosAdapterMixin` now handles the filtered `data modify` and
`data remove` helper for mob `home_pos`: it merges Bellows' partial update into
a full vanilla entity snapshot before invoking the original setter. `data merge`
has a separate Bellows path that falls back when filtered loading
declines; a direct merge case verifies that behavior. The expanded seven-arm
matrix asserts vanilla's exact init/merge/modify/remove values and confirms
parity for Bellows wrapper-off, wrapper-on, and Bellows+ScoreAdd. It also
retains the tag-index and unrelated-NBT preservation checks. This closes only
the focused `home_pos` cases for Bellows 1.1.2; broader filtered-NBT and
selector coverage remain open. A separate passenger nested-tag write remains
a no-op in vanilla and all tested mod arms. See the
[full Bellows audit](../../research/bellows-audit.md).

The literal fake-holder add compiles, executes, and matches state/feedback in
both ScoreAdd-enabled stacks, while selector, NBT, and tag-index outcomes
match the corresponding compiler-off stack.

The compiler should remain correct without Bellows. Runtime compatibility work
must compare vanilla, Bellows-only, compiler-only, and combined behavior. For
each optimization, record the native call path retained, candidate/order
semantics, other mod interception, fallback, and performance evidence. Keep
selectors and NBT commands on vanilla actions until their exact behavior and
interoperability are tested.

## 9. Comparative design synthesis

| Characteristic | Vanilla 26.3 | MCFC pinned 0.4 alpha / 26.1.2 | Mercury pinned / 1.21.4 | Bellows 1.1.0 / 26.3 | Candidate design |
|---|---|---|---|---|---|
| Command grammar | Brigadier | Independent/generated command parser | Captures Brigadier-parsed commands | Vanilla parsing, selector enrichments | Vanilla Brigadier + typed recognizers |
| Steady-state execution | Parsed action/context chain | Direct compiled methods | Compiled entry/region or fallback | Native engine hooks | Hybrid, guarded compiled regions |
| Semantic IR | Vanilla contexts, not an optimization IR | Typed high-level IL | Parse/semantic/baseline/lowered IR | No general function IR | Stable semantic IR + effects |
| Cross-command optimization | Limited | Multiple high-level passes | Inlining/slot promotion/etc. | Runtime operation optimization | Staged; prove safety first |
| Bytecode generation | Not datapack-specific | Java class-file pipeline | ASM | Not function bytecode | Optional backend after benchmarks |
| Fallback | N/A | Uncompiled functions keep vanilla path | Original procedure and individual action bridges | Targeted path fallbacks | Explicit fallback + generation guards |
| Main integration | Native | Manager + CallFunction Mixins | Builder/reload overwrites + wrapper | Selector/NBT/storage Mixins | Narrow builder/parse-return hook |
| Command quota | Static behavior verified; runtime traces open | README says compiled path does not honor old command-chain rule | Parity unresolved for specialized paths | Vanilla engine with targeted selector/NBT paths | Non-negotiable parity gate |
| Macro strategy | 8-entry argument-tuple LRU | Custom macro compiler subset | FastMacro/cache/prefetch/tier 2 | Native macro handling | Vanilla initially; guarded specialization later |
| Interop posture | Baseline | Distinct interception risks | Broad reload hook and runtime bridges | Moonrise compatibility | Minimal patch surface + matrix |
| 26.3 performance evidence here | Reference baseline | None | None | No independent measurement | Not yet measured |

### 9.1 What is actually novel or worth improving?

“Compiling `.mcfunction` to bytecode” and “optimizing scoreboards” are **already implemented ideas** in the inspected ecosystem. A new project should aim for demonstrably better **semantic fidelity, selective integration, safe reload lifecycle, diagnostics, coverage of modern commands, reproducible speedups and interoperability**.

A significant differentiator would be **proof-friendly optimization**: every IR transform declares read/write/visibility/cost effects, every optimization has a fallback, and every release ships differential performance-and-correctness results on the exact target version.

---

## 10. Proposed IR and compiler specification

### 10.1 Distinguish three representations

1. **Parse capture / provenance layer:** Validated Brigadier contexts, original `UnboundEntryAction`, command text, function ID, logical line number, macro expansion context, command-tree identity and target version/generation. Reuses Minecraft grammar and preserves a concrete fallback.
2. **Semantic IR:** Domain-specific operations plus explicit control-flow, context, state, observable-effect and cost metadata. Not tied directly to a particular Minecraft class's fields.
3. **Executable IR / lowering:** Entry objects or resumable region bytecode, containing materialized references, guarded fast paths, continuation states and fallback boundaries.

A semantic IR that directly stores mutable Minecraft objects must be treated as **generation scoped**. Avoid accidentally holding entity/world/registry references across reloads.

### 10.2 Suggested instruction taxonomy

- `VanillaAction(original, sourceLocation, reason)`: exact fallback; maximally conservative effects.
- `ScoreRead`, `ScoreWrite`, `ScoreAdd`, `ScoreRemove`, `ScoreReset`, `ScoreOperation`: typed scoreboard semantics, including missing-score/objective cases.
- `ContextModifier`: typed `execute` transformation (executor, position, dimension, rotation, anchor, result handler, permission/callback context).
- `SelectorQuery`: parameterized entity query; return order/cardinality and snapshot/requery policy explicit.
- `Conditional`: predicate with true/false/failure exits and possible continuation.
- `CallFunction`: target set, optional arguments, return/failure callbacks and scheduling behavior.
- `Return`, `ReturnRun`, `IsolatedFunctionTest`: explicit frame semantics; initially barriers/fallbacks.
- `DataOperation`: NBT/storage command; initially fallback until native-call-path contract is understood.
- `MacroTemplate` / `MacroInstantiation`: dynamic parse and cache identity; deferred optimization.
- `ExternalCommand`: unknown modded command; original action and unknown effects.

### 10.3 Instruction metadata and side-effect lattice

Each operation should carry:

```text
InstructionMeta
  SourceRef(functionId, logicalLine, rawText, expansionSource)
  ParseBinding(commandNodeIdentity, parsedArguments, generation)
  Reads       : Set<StateRegion>
  Writes      : Set<StateRegion>
  ContextReads: executor|position|dimension|rotation|anchor|permissions|callbacks
  ContextWrites: the same fields / fork count
  Effects     : SuccessResult|FailureResult|Messages|Tracing|Scheduling|
                Return|EntityEvents|NBTSerialization|Randomness|Unknown
  CostShape   : charge events and original queue/yield boundaries
  Fallback    : original UnboundEntryAction
  SafetyProof : guard set and assumptions
```

State regions should initially be coarse, e.g. `ScoreboardAll`, `EntityAll`, `NBTAll`, `WorldAll`, `ScheduledTasks`, and `Unknown`. Specialization can refine `ScoreboardAll` to `(objective,holder)` or `EntityAll` to a query predicate only with sufficient alias/invalidation rules. **Unknown aliases conflict with everything they might access.**

### 10.4 Control-flow and compilation regions

Start with **straight-line non-forking single-source instructions**. End a candidate region at:

- any unsupported or effect-unknown command;
- `/function`, `/return`, `/return run`, `execute if function`, arbitrary custom executors;
- any fork/position/executor-context transformation not explicitly supported;
- callbacks/tracing points for which a compiled equivalent is unavailable;
- command-budget yield boundaries which cannot be preserved.

Later, allow **resumable regions** that return an execution status and `nextProgramCounter`. Suspension installs vanilla action and continuation entries in the correct queue order. Tests must prove that no resumed action runs after its frame is discarded.

### 10.5 Runtime and backend interfaces (conceptual)

```java
record CompiledArtifact(
    FunctionId functionId,
    ReloadGeneration generation,
    CompilationFingerprint fingerprint,
    CompiledExecutor executor,
    FallbackFunction original,
    CompilationDiagnostics diagnostics
) {}

interface CompiledExecutor {
    ExecutionOutcome execute(Source source,
                             VanillaExecutionContext context,
                             VanillaFrame frame,
                             int programCounter);
}

sealed interface ExecutionOutcome {
    record Complete() implements ExecutionOutcome {}
    record Suspend(int resumeAt, VanillaAction action) implements ExecutionOutcome {}
    record Return(int value, boolean success) implements ExecutionOutcome {}
    record Fallback(String reason) implements ExecutionOutcome {}
}
```

These are **illustrative interfaces**, not classes known to compile against 26.3. Actual types must follow Fabric/Minecraft method signatures and thread confinement rules.

### 10.6 Optimize in monotonic stages

**Level 0:** parse/provenance capture only; no runtime changes.  
**Level 1:** individual specialized entries (cost equivalent).  
**Level 2:** interpreted block with shared immutable lookups but separate logical command boundaries.  
**Level 3:** resumable compiled region with guarded fusion.  
**Level 4:** ASM/JVM bytecode version of the same executable IR.  
**Level 5:** cross-function inlining and effect-certified transformations.  
**Level 6:** macros, profile-guided specialization and advanced NBT/selectors if measurable.

### 10.7 Strictly prohibited early transformations

Do not initially reorder, combine or delete commands based only on the final scoreboard/NBT state. In particular, two consecutive `scoreboard add` commands are **not** automatically equivalent to one combined `add` because command cost, success/result callbacks, tracer events, intermediate visibility and failures can differ. Likewise, duplicate selector expressions must not be cached across a world mutation or a potentially effectful command.

### 10.8 Command adapter requirements

Each specialized operation needs a short, versioned **semantic contract** containing: accepted Brigadier command-node signatures, argument extraction, permission and source assumptions, resolved Minecraft APIs, success/failure/result behavior, exception handling, objective existence/deletion behavior, charge/yield obligations, original fallback and compatibility intercepts. Avoid a single global command-recognition regex registry without such contracts.

---

---

## 11. Testability and correctness specification

### 11.1 Correctness objective

For a given legal initial state, command source, function registry, game rules, installed compatible mod set and replayable random input, the compiler should produce an **observationally equivalent execution** to vanilla. Equivalence is stronger than matching the final score of one scoreboard holder.

Define the observable trace vector:

`O = (worldChanges, scoreState, entityState, storageState, scheduling, results, callbacks, messages, errors, tracing, quotaStop, forkBehavior, reloadState)`.

**Initial delivery gate:** Each supported operation matches all relevant elements of `O`. For trace fields impossible to reconstruct in compiled mode, run a verified vanilla tracing path. Treat “debug mode differs” as a disclosed limitation until explicitly waived; the intended product goal is full parity.

### 11.2 Differential reference harness

The harness must run identical input scenarios against **vanilla 26.3** and **compiler-enabled 26.3** in isolated copies of the same initial world, same game rules, same datapacks and compatible mod set. Collect machine-readable results. Do not run optimized and vanilla phases sequentially in the same mutable world without resetting state.

Recommended topology:

```text
Fixture generator  -> save immutable world template
       |
       +--> vanilla server instance ---> structured observation log
       |
       +--> compiler server instance --> structured observation log
                                          |
                                          v
                                semantic diff + failure artifact
```

Artifacts for a failed case should include seed, game version/build hash, loader/mod list, datapack hash, gamerules, source function, command-level trace (when safe), serialized relevant state, error logs, compiled IR dump, and generated class hash when applicable. Avoid collecting player data or automatically uploading private datapack contents.

**Current prototype scope:** `scripts/run_runtime_probe.py` implements the first
small comparison using a temporary mod-free vanilla world and the same direct
`/function` command in vanilla and wrapper-off/on Fabric servers. It compares
RCON feedback and scoreboard state for empty, one-entry, three-entry,
two-stage/four-source execute, and nested-call fixtures at limits 0–7. This is
a narrow baseline, not the complete harness specified above; the vanilla
process has no per-cost instrumentation, and return/condition/fork control
flow, callback, reload, and mod cases remain open.

**Execution-reference discipline:** Sometimes console/RCON return text differs without implying a game-state difference, and sometimes equal text hides a difference. Use both **in-world assertions** and engine-level capture of callbacks/results. Do not make RCON text the only oracle.

### 11.3 Semantic test categories

| Category | Essential cases | Assertion |
|---|---|---|
| Scoreboard basics | `set/add/remove/get/reset`, repeated operations, negative/overflow, missing holder | score **existence** as well as numeric value; callbacks and result |
| Objective lifecycle | absent objective, objective removed/recreated between calls | correct error and no stale reference reuse |
| Holder forms | fake player, literal name, selector-backed holders, wildcard `*` | correct cardinality and selection failures |
| Command quota | budget 0/1/2/3/4, just below/at/above exhaustion, nested and modifier paths | last completed effect and stop boundary identical |
| Fork limit | no matches, one match, many matches, threshold equal/overflow | same source expansion/failures/order |
| Execution contexts | `as`, `at`, `positioned`, `in`, `anchored`, `rotated`, nested modifiers | same source fields and context-dependent operations |
| Control flow | function direct/tag calls, recursion, `return`, `return run`, isolated function test | same frame discard/callback/order |
| Results/callbacks | `execute store result/success score/storage` for successful/failed command | same stored values and when stores occur |
| Errors | syntax invalid at reload, runtime missing target/objective, mod command exception | same rejection/continuation/trace |
| Macros | cache hit/miss, missing field, varying arguments, long args, tuple collision | same expansion, errors, cache identity correctness |
| NBT | storage/entity/block paths, empty/multiple path matches, mutable serialization | same values/results/side effects |
| Selectors | broad/bounded, tag/type, nearest/random, cross-dimension, invalidation | same membership and relevant ordering |
| Reload | add/remove/change function, change tags, change objective/registry, rapid reload | no stale artifact; correct identity |
| Debug | `/debug function`, trace nesting, per-command results, profiler hooks | no lost events or wrong entry count |
| Mod interoperability | Bellows, Moonrise if target supports it, Lithium, custom mod commands | no crashes, duplicate side effects, lost optimization |
| Concurrency/lifecycle | concurrent parse tasks, background compilation, shutdown/restart | no cross-generation publication, leaks or races |
| Limits | long functions, large bytecode methods, many generated classes | deterministic graceful fallback |

### 11.4 Distinguish command quota from function size

`max_command_sequence_length` is an **execution-cost quota**, not a rule that simply stops after a certain count of source lines. An `execute` line can debit several units or fork many leaf executions, and function calls have their own charge. The integration harness must log actual cost events; pure line counting is insufficient.

### 11.5 Low-quota golden cases

Build data pack `compiler_tests` with tiny named functions, after creating required scoreboard objectives. Set `minecraft:max_command_sequence_length` to a small value **before** invoking each case. Restore game rules after testing. For each case, collect observable effects **and** an instrumented vanilla cost/queue trace. Examples:

```mcfunction
# compiler_tests:three_adds
scoreboard players add #x test 1
scoreboard players add #x test 1
scoreboard players add #x test 1
```

```mcfunction
# compiler_tests:nested_outer
function compiler_tests:nested_inner
scoreboard players add #outer test 1
```

```mcfunction
# compiler_tests:nested_inner
scoreboard players add #inner test 1
```

```mcfunction
# compiler_tests:fork
execute as @e[type=minecraft:armor_stand,tag=test_actor] at @s run scoreboard players add #count test 1
```

Run each from a consistent outermost context; note that executing these via an extra `/execute` wrapper or a tag may alter scheduling and charges. Establish a vanilla reference trace instead of assuming expected final score merely from textual command count. Include cases where modifier-stage charge pushes quota <= 0 *inside* an executing queue entry.

### 11.6 Metamorphic and property-based testing

Generate short functions from a restricted grammar: scoreboard literal commands, permitted modifiers, calls to small acyclic functions, failures, returns. Generate initial states with and without objectives/holders, two or more entities, and varying small quotas. For each generated fixture, run vanilla and compiler and compare `O`. Retain a minimized reproducer whenever a difference occurs. Scale up to longer functions and more operations once the initial grammar passes.

Also test a **toggle metamorphic property**: with compilation disabled/enabled/disabled again across reloads, the function's externally observable behavior remains invariant.

### 11.7 Handling mid-execution exceptions

Do **not** restart an entire function in vanilla after a compiled region already mutated world state and failed unexpectedly: this can duplicate side effects. Instead, recognize exceptions at the correct per-command boundary, preserve completed effects, and either resume the unexecuted tail through a vanilla continuation (if verified) or mark the artifact failed for *future invocations*. Fail closed before executing an unvalidated optimization path.

### 11.8 Completeness criteria per new command adapter

An adapter can be enabled by default only when it has: specification of argument/permission semantics; success/failure and callback tests; error-path tests; cost/yield tests; reload invalidation tests; source-context tests; Bellows/mod-compatibility assessment; and at least one measured workload showing non-regressive performance with allocations captured. Maintain these as machine-readable adapter metadata where possible.

---

## 12. Benchmarking and performance investigation plan

### 12.1 Research questions

**RQ1:** What fraction of a cheap ordinary command's time is spent in `BuildContexts`, `ExecuteCommand`, Brigadier context binding, queue dispatch and the underlying state operation?  
**RQ2:** Does a specialized `UnboundEntryAction` outperform an ordinary parsed action with exactly equivalent budget/trace behavior?  
**RQ3:** How much additional benefit comes from fusing several operations while retaining yield semantics?  
**RQ4:** Does emitted JVM bytecode outperform an equivalent specialized interpreted Java executor after proper JVM warmup?  
**RQ5:** Does Bellows remain effective, and are the two optimizers additive, neutral, or conflicting?  
**RQ6:** What is the reload/compile, allocation, class-memory, and startup cost of each backend?  
**RQ7:** What fraction of realistic datapack workloads is eligible under conservative semantic rules?

### 12.2 Baseline benchmark configurations

**V:** unmodified vanilla 26.3 + necessary test harness only.  
**I:** instrumentation-only prototype (ensure instrumentation overhead is negligible).  
**E:** one specialized entry per command, using direct Minecraft scoreboard APIs.  
**R:** resumable interpreted compiled regions.  
**J:** JVM bytecode emitted from the same lowered IR as R.  
**B:** Bellows-only.  
**E+B**, **R+B**, **J+B:** corresponding compiler modes plus Bellows.

For microbenchmarks, include a separate synthetic direct score-mutation reference path. It is **not** a functional substitute for vanilla because it omits execution machinery; it is an upper-bound diagnostic for per-command overhead.

### 12.3 Workload families

| Workload | Expected bottleneck to investigate | Control variables |
|---|---|---|
| Many independent `scoreboard add` commands | dispatch vs scoreboard operations | N lines, objective and holder count |
| Repeated updates to one score | repeated lookups, slot promotion | dependency chain length |
| Different objectives/holders | scoreboard resolution and cache locality | holder/objective cardinality |
| `execute if score` chains | context stages, predicate evaluation | branch selectivity |
| Nested small functions | function-call scheduling | depth, fan-out, call frequency |
| Long straight-line function | entry/queue overhead and quota | N, block size, small quotas |
| Broad selectors | entity lookup, Bellows index | entity population, tag/type selectivity |
| Bounded selectors | vanilla spatial index | bounding box size |
| Nearest/random selectors | ordering/sampling costs | population and distances |
| Storage NBT reads/writes | serialization/path traversal | tree depth, size, path type |
| Macro stable parameters | cached instantiation | call frequency, cache cardinality |
| Macro changing parameters | substitution and parse misses | argument entropy, cache size |
| Mixed realistic datapack | barriers, fallback share, allocation | command mix and world state |
| Sparse tick functions | compilation overhead vs saved time | number of functions, call rate |

### 12.4 Measurements

Record **median and distribution** (p50/p90/p99) of elapsed server tick time where relevant; CPU samples per subsystem; allocation rate (bytes/op, objects/op and GC); total execution invocations and cost charges; generated-class bytes; live classloader count; compilation/reload wall time; memory before/after repeated `/reload`; function coverage (% lowered, % fallback, % fused), and error/trace parity status.

Do not use elapsed end-to-end RCON request time as the core high-frequency metric: RCON/network latency can swamp cheap commands. Use JFR, async-profiler, JMH **only for isolated helper APIs**, and server-thread instrumentation for full execution. PERF-002-TIMING uses `System.nanoTime` around the `Command.run` callback in matched instrument-only and ScoreAdd arms; five trials measured 221.14 ns/action for the vanilla delegate and 130.48 ns/action for ScoreAdd. This timer includes its own matched overhead and excludes command-context construction, quota, tracing, and scheduling, so it is evidence for the callback only. PERF-002-FUNCTION-TIMING adds a matched queue timer from `FunctionCommand.queueFunctions` for the target fixture to the corresponding `ExecutionContext.runCommandQueue` return. Across five randomized trials of 5 million actions each, the median was 2.635 ms/function for the vanilla delegate and 3.024 ms for ScoreAdd (14.8% slower); every trial verified 1,000 timed calls and the expected score. It includes function instantiation, queue processing, quota, callbacks and tracing, but excludes RCON and outer `/function` parsing. The timer overhead is matched but has not been independently calibrated, and the fixed workload does not generalize to other functions. Profile both warmed and cold configurations; publish JVM flags, CPU, Java version, GC, server player/entity counts, tick rate, world seed and mod list.

### 12.5 Experimental discipline

- Freshly clone the same world fixture for each arm or use an exact deterministic reset protocol.
- Warm up generated methods and game state; separate startup/JIT and steady-state measurements.
- Alternate/run randomized arm order where practical, with multiple independent forks/runs.
- Avoid output-heavy or profiler-heavy console commands during hot benchmarks.
- Verify the *same effective effects and command costs* in every arm before comparing timings.
- Report both throughput and **compile cost amortization**; fast compilation on a function called once may not repay reload work.
- Compare functional baselines with and without Bellows at the same entity/selector state.
- Always report **regressions** and failures as well as wins; do not extrapolate single-command gains to arbitrary datapacks.

### 12.6 Performance go/no-go thresholds (proposed; adjust after baseline)

**At P2:** individual scoreboard specialization should show a repeatable, statistically credible CPU or allocation reduction on its intended workload, with zero known semantic mismatch; otherwise reconsider whether entry specialization is useful.  
**At P3:** fused execution must outperform the equally correct single-entry baseline on at least one meaningful workload and avoid material regressions on mixed workloads; the benefit must outweigh increased maintenance complexity.  
**At P4:** a bytecode backend should only be kept if it adds a meaningful measured benefit over R that justifies compile-time, code-size and classloader costs.

Avoid inventing a mandatory 2x/10x speedup at project inception. Set numerical gates once a baseline distribution and acceptable complexity budget exist.

---

## 13. Engineering roadmap, work packages and deliverables

### Phase 0 — Exact 26.3 source and environment

**Static source tasks complete:** Fingerprint the official 26.3 server bundle and Loom classfiles; inspect descriptors and method bodies for function construction, reload/tag publication, queue execution and cost debits; inventory the direct debit callers and custom executor paths; compare selected classes across 26.1.2, 26.2, and 26.3. Findings are summarized in [`26.3-internals.md`](../../research/26.3-internals.md).

**Completed since plan preparation:** Create and run the pinned Fabric 26.3 workspace; prototype the wrapper and capture helper-path quota traces; build a mod-free vanilla harness and compare 16 direct function fixtures plus scoreboard-operation cases with wrapper-off/on Fabric and opt-in ScoreAdd-on. The function set includes modifier expansion, nested calls and returns, vanilla and compiled-region recursion (including forced bytecode compile-failure fallback), return paths, stored results, isolated function conditions, dynamic quota changes, fallback resumption, runtime syntax errors, and fork match counts zero/one/two/four across limits 1–12. Scoreboard cases cover all nine operations, absent sources/targets, missing objectives, selector score-presence and cardinality combinations, wildcard-target creation of the source holder, signed integer bounds, remove/reset, objective recreation, and `execute store success`. Flat/nested debug traces, macro hash collisions/argument errors, and five changed function/tag reload generations also match. Instrumented Fabric runs confirm a function is not reparsed during repeated invocation; the `fromLines` counter advances once on each full resource reload.

**Remaining tasks:** Cover broader missing-score feedback, other fork failure shapes and selector/sort combinations, callback failures, and compatibility-mod semantic cases. The selected nearest/furthest/random/arbitrary low-cap cases now match across 16 vanilla, Fabric, Bellows 1.1.2, and Bellows + Moonrise 1.2.0 modes. Vanilla's built-in `/function` cost-debit trace remains unavailable; helper-path traces are wrapper-neutral but not a vanilla cost oracle.

**Deliverables:** Tracked exact-source notes and fingerprints (complete), target-matched development build (complete), ordinary-function low-quota state/RCON/debug-trace fixtures (partial for untested error and callback paths), expanded control-flow fixtures (partial), and architecture changes if runtime evidence contradicts the static model.

**Exit gate:** The static source model is confirmed by repeatable runtime traces, the target toolchain is reproducible, and open cases remain explicitly identified.

### Phase 1 — Hook and identity proof

**Completed runtime coverage:** Initial and five successive function-body/tag
reloads; wrapper and tag instance identity in both Fabric modes; `#minecraft:load`
and `#minecraft:tick` fixture execution; native macro fallback and a disabled
expanded-macro ScoreAdd prototype with tuple churn, storage changes, collisions,
and invalid-argument parity. The temporary lifecycle pack is under
`tests/fixtures/` and is not shipped in mod resources.

**Tasks:** Prototype `FunctionBuilder.build` return wrapper; alternatively parse-result wrapper. Delegate all execution to original function. Test concurrent reload, tick/load/custom tags, direct `/function`, function tags calling functions, nested calls, `/debug function` and mod interaction. Run a no-optimization mod to isolate hook overhead.

**Remaining gate work:** Cover additional callback and error paths; test
overlapping and erroring reload cases; measure wrapper-only overhead; complete
semantic behavior under the selected compatibility mod matrix. Flat and nested
`/debug function` traces are now captured for the wrapper-only path.

**Deliverables:** Fabric integration proof, Mixin target list, function/tag reference graph, reload-generation protocol, test fixtures and results.

**Exit gate:** All vanilla behavior unchanged and compatibility failure modes documented. If wrapper timing or identity fails, revert ADR-001 and test alternate capture point.

### Phase 2 — Profiling and first adapter

**Tasks:** Instrument cost and queue boundaries; establish hot-path profiles; add `ScoreAdd` for **literal fake-holder and objective** only with exact missing-objective handling, per-command callbacks and charge semantics. Maintain original parsed fallback. Compare vanilla, instrumented, specialized entry and direct helper path.

**Sequencing note:** The vanilla-only baseline profile (PERF-001) can start
alongside unfinished Phase 0 and Phase 1 research: it depends on the pinned
26.3 source/toolchain and a deterministic workload, not on closing unrelated
return/fork or reload cases. Keep it separate from an optimization claim.
Implementation of a disabled literal fake-holder ScoreAdd prototype and its
scoped differential case are complete. PERF-002 has also run five trials per
arm, but is provisional: it measures RCON-driven throughput and has only one
Spark CPU/allocation profile per arm, so it does not establish repeatable CPU
or allocation changes. PERF-002-TIMING's callback-only timer showed a lower
ScoreAdd callback median. The follow-up PERF-002-FUNCTION-TIMING measured
ScoreAdd 14.8% slower by median across the whole target function queue, with
exact score and timed-call counts in every trial. Both comparisons use matched
timer instrumentation whose overhead is not yet independently calibrated.
The prototype remains disabled while remaining P0 behavior and compatibility
cases are completed. The next comparison requires timer calibration, repeated
CPU/allocation evidence, additional whole-function workloads, and parity for
the full supported input domain.

**Deliverables:** raw benchmark data + analysis, first versioned semantic adapter, command result oracle, tests for missing score/objective and low quota.

**Exit gate:** correct and repeatably faster on targeted benchmark, or a written evidence-based pivot.

### Phase 3 — Multi-operation regions

**Tasks:** Implement region builder and runtime continuation protocol; use **same specialized operation** first so only scheduling/fusion changes. Add budget inspection/charge mechanism (if required), tracer correctness mode, cancellation tests, fork barriers, and underflow/zero-budget fixtures. Compare fused interpreted blocks vs specialized entries.

**Deliverables:** `CompiledRegion` specification, machine-readable cost events, action/continuation ordering tests, performance report.

**Exit gate:** no differential failures in exhaustive small-quota tests, correct nested returns and tracing, material gain in chosen workloads.

### Phase 4 — Core IR and optional JVM backend

**Tasks:** Formalize typed parse capture, effect analysis, CFG and source maps. Emit JVM bytecode from existing lowered IR (ASM or a class-file API after toolchain review). Compare codegen size, JIT warmup, steady-state performance, class unloading, verifier errors, oversized methods and 1,000+ generated functions. Keep a lower-complexity Java interpreter as a reference backend.

**Deliverables:** backend comparison and an ADR deciding whether bytecode stays; compiler IR dumps, class dumps, regression corpus.

**Exit gate:** bytecode path is either justified by data and correct, or rejected without losing semantic IR/other backends.

### Phase 5 — Broader operations and optimization passes

**Tasks:** Add scoreboard comparisons/operations, selected `execute` forms with explicit context effects, guarded objective lookups, safe cross-command reuse, deliberate spill/flush points, direct/cross-function call analysis, simple inlining, registry-aware specialization. Extend every adapter's semantic contract and test set.

**Deliverables:** command support matrix; effect-alias proofs; benchmark profiles; prioritized coverage stats from real datapacks.

**Exit gate:** each new pass has differential tests and no regressions on previous suites; unrecognized commands remain vanilla.

### Phase 6 — Macros and wider compatibility

**Tasks:** Keep Minecraft's equality-aware eight-entry macro tuple cache as the identity and eviction owner; specialize only the returned parsed expansion. Extend coverage to more macro command families and quota boundaries, then profile cache hits, misses, churn, and allocation. Audit Bellows, Lithium, Moonrise and representative modded Brigadier commands for call-path bypasses. Expand server diagnostics and exposure controls. Do not add a second tuple cache without evidence that the native cache is insufficient.

**Deliverables:** macro design, collision and churn corpus, interoperability compatibility table, memory lifecycle report.

**Exit gate:** all documented integrations and negative cases pass on the exact target mod/version matrix.

### Phase 7 — Productionization

**Tasks:** Compatibility and release notes, command coverage diagnostics, explicit performance opt-in flags per pass/backend, opt-out by namespace/function, crash-safe fallback, logging policy, test artifact publication, regression dashboard and version-porting playbook. Verify licensing of all borrowed implementation elements.

**Deliverables:** release candidate, versioned correctness report, reproducible benchmark package, maintainership/porting documentation.

**Exit gate:** published known limitations, no priority-1 semantic mismatches, acceptable server memory/reload cost, and proven positive impact on real datapacks.

---

## 14. Source-level research questions and decision log

### 14.1 Mandatory open questions

| ID | Question | Evidence needed | Owner/task suggestion |
|---|---|---|---|
| RQ-01 | Do low-quota 26.3 runtime traces match the exact-source quota-site and threshold model? | Vanilla trace harness for zero, one, and low quota | Phase 0 |
| RQ-02 | Do custom function/return/execute executors match the statically traced debit paths at runtime? | Runtime call-site traces and golden cases | Phase 0 |
| RQ-03 | Does wrapping `FunctionBuilder.build` preserve identity for all tags/reloads? | Fabric prototype | Phase 1 |
| RQ-04 | Can compilation metadata be captured without copying raw source lines or overriding reload? | 26.3 API and experiment | Phase 1 |
| RQ-05 | Where does CPU time actually go for a warm scoreboard leaf? | JFR/async-profiler and timers | Phase 2 |
| RQ-06 | Does an individual specialized entry yield meaningful throughput improvement? | Controlled A/B benchmark | Phase 2 |
| RQ-07 | Can a fused region reproduce queue-boundary exhaustion? | low-quota differential + instrumented queue | Phase 3 |
| RQ-08 | Does function tag publication resolve original or wrapped object? | identity graph on reload | Phase 1 |
| RQ-09 | How does `/debug function` report a one-entry compiled function? | trace comparison | Phase 1/3 |
| RQ-10 | Can JVM bytecode improve over a warm interpreted Java backend? | backend benchmark | Phase 4 |
| RQ-11 | Which scoreboard mutation paths invalidate cached slots? | exhaustive call-site and mod audit | Phase 5 |
| RQ-12 | Which Bellows Mixins are bypassed by each compiled operation? | actual call path and 4-way benchmark | Phase 5/6 |
| RQ-13 | How are `execute if function` isolated result callbacks and side effects preserved? | Full eight-arm `/debug function` trace parity now covers successful and failing isolated conditions; broader quota, error, and side-effect combinations remain | Phase 3/5 |
| RQ-14 | Can macro specialization be keyed without collision ambiguity or stale generation refs? | tuple equality + property tests | Phase 6 |
| RQ-15 | Is using a 26.1.2 MCFC parser as a reference practical given 26.3 command grammar changes? | Static version comparison recorded; a parser-porting experiment remains optional | Phase 5 |
| RQ-16 | Are any MCFC optimizer passes provably reusable, within LGPL terms? | licensing and semantics review | Phase 4/5 |
| RQ-17 | Does the compiler degrade startup, reload or idle memory? | repeated reload/load benchmarks | Every phase |
| RQ-18 | How can commands supplied by arbitrary Fabric mods be safely classified? | Brigadier ownership/identity + fallback tests | Phase 5/6 |

### 14.2 Assumptions that must not become silent facts

- *“A custom `UnboundEntryAction` preserves scheduling.”* It uses the same scheduler, **only if** it reproduces the original logical cost, tracing and scheduling behavior.
- *“A `CommandFunction` wrapper solves everything.”* It does not automatically solve tag identity, debug entry counts, macro instantiation, direct `CallFunction` references or reload lifecycle.
- *“Brigadier is the bottleneck.”* Parsing of ordinary functions is mostly reload-time; execution-side context handling may be the bottleneck but must be measured.
- *“Bytecode is inherently faster.”* JVM already JIT-compiles Java; domain-specific specialization matters more than code-generation method absent data.
- *“Bellows handles selectors so we never need to optimize selection.”* Bellows optimizes certain query paths, but compilation may unlock safe context reuse or narrow specialization. Such work requires its own effect and compatibility proof.
- *“MCFC's current source supports 26.3.”* The pinned source targets 26.1.2 and labels its 0.4 alpha branch in development; this report makes no such claim.
- *“Mercury proves semantic parity.”* Its source proves implementation patterns; exact quota/tracing correctness is unverified here.

### 14.3 ADR template for future decisions

```text
ADR-NNN: <decision title>
Status: Proposed | Accepted | Rejected | Superseded
Date and target game/toolchain versions:
Problem / performance evidence:
Alternatives considered:
Chosen approach and narrow interception points:
Required semantic invariants:
Bellows/mod hook impact:
Reload/cache invalidation implications:
Tests, benchmark datasets and recorded results:
Rollback / feature-flag strategy:
Residual risks and owners:
```

---

## 15. Proposed repository organization and engineering standards

```text
compiler-project/
  README.md
  docs/
    README.md
    architecture.md
    command-semantics.md
    integration-hooks.md
    execution-cost-model.md
    interoperability.md
    performance-methodology.md
    source-coverage.md
    research/
      26.3-internals.md
      mcfc-audit.md
      mercury-audit.md
      bellows-audit.md
      source-versions.lock
      reference-sources.lock
    v1/
      plans/
        research-and-implementation-plan.md
        test-matrix.csv
  common/
    ir/
    analysis/
    optimizer/
    diagnostics/
    codegen/
  minecraft-26.3-fabric/
    mixin/
    adapters/
    runtime/
    commands/
  tests/
    fixtures/
    golden/
    differential/
    macros/
    limits/
    compatibility/
  benchmarks/
    harness/
    suites/
    results/
    analysis/
```

Use concise human-readable docs supported by actual code/API references, not a growing stream of progress reports. Record incremental changes and measurements in a changelog or benchmark log; update curated architecture/semantics docs whenever decisions change. Maintain line-accurate source anchors only for pinned commits/builds, and revalidate them when porting. Completed implementation specs should be distilled into permanent documentation and archived after landing.

### Operational standards

1. Every optimization is gated by a feature flag and has an exact fallback path.
2. Every change to a runtime interception point has a specific compatibility and quota regression test.
3. Every benchmark claim includes a reproducible fixture, environment manifest and uncertainty statistics.
4. Unknown or modded commands are assumed effectful unless recognized through a reviewed adapter.
5. Hot-path static caches must be versioned/invalidated; world references cannot survive unintended reloads.
6. No compilation should execute arbitrary datapack commands in an off-thread analysis phase.
7. A failed compilation must not make otherwise valid vanilla data pack functions invalid.
8. Do not run vanilla “fallback from the beginning” after partial compiled side effects.
9. Security/permission source semantics are preserved by default; no permission checks bypassed for speed.
10. Any copied MCFC implementation or derivative must undergo explicit LGPL compliance review; no implied transfer of source license to our project.

---

## 16. Acceptance criteria, release blockers and first executable tickets

### 16.1 Minimum viable research deliverable (MVRD)

- [x] Exact 26.3 method-body and bytecode findings are fingerprinted and summarized in tracked research notes without distributing decompiled Mojang source.
- [x] Vanilla cost-debit callers, queue-check order, and custom-executor caveats are inventoried statically.
- [x] A narrow vanilla golden pack and machine-readable observation harness are runnable on the pinned 26.3 Fabric environment; the broader corpus remains open.
- [x] Wrapper-at-builder and parse-return alternatives have static pros/cons and exact method descriptor evidence; runtime hook feasibility remains open.
- [ ] Function tags, load/tick callbacks and reload generation have an explicit parity test.
- [ ] A plain native scoreboard-command hot-path profile has been collected.
- [ ] An ADR selects or rejects wrapper integration based on results, not preference.

### 16.2 Minimum viable compiler experiment (MVCE)

- [ ] One safe scoreboard command recognized from vanilla parsed representation.
- [ ] Original parsed action retained for exact fallback.
- [ ] Specialized entry implements correct result/error/callback semantics.
- [ ] Low-quota execution matches vanilla over all tested boundaries.
- [ ] Debug tracing and reload behavior match or force a verified vanilla path.
- [ ] Performance across V/I/E measured with repeatable harness and allocation data.
- [ ] Compiler+Bellows tested even if the operation itself doesn't use a selector.
- [ ] No classloader leak or generation reuse over multiple reloads.

### 16.3 Production blockers

Any of the following blocks enabling the corresponding optimization by default: changing total completed world effects at the quota boundary; missing/duplicate callbacks; command source or permission differences; incorrect return/frame cancellation; stale cache across reload; incorrect macro argument substitution; order-dependent entity selector change; unsafe exception recovery after partial mutations; unbounded generated classes or compile-time memory; or known incompatibility with commonly deployed mods without a safe fallback.

### 16.4 Initial tickets (parallelizable where independent)

| ID | Ticket | Dependencies | Completion evidence |
|---|---|---|---|
| SRC-01 | Pin a reproducible Fabric 26.3 development toolchain | None | Static fingerprints, build lock, and runnable setup complete |
| SRC-02 | Validate quota call paths against runtime queue traces | SRC-01 | Static cost map and ordinary-function state baselines complete; helper-path traces captured; broader cost traces remain open |
| SRC-03 | Prove wrapper/reload/tag identity in a running 26.3 server | SRC-01 | Initial builder wrapper, custom-tag identity, delegated instantiation, five changed generations, removal/re-addition, and one held function/tag/macro publication verified; overlapping and erroring reloads and other tags remain open |
| AUD-01 | Complete MCFC command/parser/codegen source audit | None | Static audit complete in `mcfc-audit.md`; no build or runtime reproduction |
| AUD-02 | Review Mercury bytecode quota, tracer and suspension behavior | None | Static gap review complete in `mercury-audit.md`; runtime parity does not apply to the 26.3 build |
| AUD-03 | Review Bellows selector/NBT call paths against exact 26.3 methods | SRC-01 | Focused selector/NBT runtime probes and `home_pos` adapter verified against Bellows 1.1.2; broader selector and filtered-NBT coverage remains open |
| TST-01 | Implement vanilla observation/oracle harness | SRC-01 | Sixteen direct-fixture state/RCON comparisons, flat/nested debug traces, and lifecycle outcomes run on mod-free vanilla and wrapper-off/on Fabric; broader error/callback/mod oracles remain open |
| TST-02 | Implement small-quota boundary suite | SRC-02, TST-01 | Ordinary, modifier-expansion, nested-call/return, recursion, stored-result, isolated-condition, dynamic quota-change, and zero/one/two/four fork outcomes are recorded; exact vanilla debit events remain unavailable |
| HOOK-01 | Build fully delegating function wrapper | SRC-03 | Initial and five-generation reload identity, delegated instantiation, load/tick, macro fallback, flat/nested debug traces, and one held function/tag/macro publication pass; overlapping and erroring lifecycle tests remain open |
| PERF-01 | Profile warm vanilla parsed scoreboard execution | SRC-01 | Initial one-second warmed JFR profile captured for a validated 5,000-line scoreboard fixture; repeat runs and allocation analysis remain |
| OPT-01 | Implement typed scoreboard `add` adapter | HOOK-01, TST-01 | Semantic and quota parity |
| PERF-02 | Compare vanilla/instrumentation/specialized entry | OPT-01, PERF-01 | Repro measurement report |
| RT-01 | Design resumable region with quota boundary oracle | SRC-02, OPT-01 | Formal contract + prototype |
| RT-02 | Prove nested call/return/fork/tracing ordering | RT-01, TST-02 | Differential corpus |
| PERF-03 | Compare entry vs region vs bytecode prototype | RT-01 | Backend ADR |

### 16.5 Initial wrapper-only experiment and remaining work

**Prototype `wrapper-only` before writing a compiler**. Use a narrow 26.3 Fabric Mixin to replace an ordinary `PlainTextFunction` with a delegating wrapper at construction. Keep `entries()` identical to vanilla. Run `#minecraft:tick`, direct calls, a custom function tag, nested function calls, `/debug function`, five `/reload` cycles, and one server shutdown/restart. Instrument how often wrapper instantiation and vanilla `CallFunction` are invoked. If this fails, the design is wrong early and cheaply; if it passes, only then introduce a specialized `ScoreAdd` entry.

**Evidence update (2026-10-27):** The builder-return wrapper and custom-tag
identity proof are implemented. Direct ordinary-function state and RCON
feedback match mod-free vanilla for 14 fixtures, including nested return
frames, recursion, conditional calls, stored results, dynamic quota changes,
and zero/one/two/four fork matches over limits 1–12. Flat and nested `/debug
function` traces match exactly. Load/tick tags, macro hash collisions and
argument errors, and five changed-body/tag reload generations also match.
Nearest/furthest order-sensitive and random/arbitrary selector cases match
across vanilla and both Fabric modes; direct cap-1 and cap-2 fork responses are
recorded. Other fork failure paths, broader selector/sort combinations,
additional callback failures, compatibility-mod semantics, and exact vanilla
per-debit traces remain open.

---

## 17. Source references and audit reading order

### 17.1 Exact Minecraft 26.3 artifact

Use [`26.3-internals.md`](../../research/26.3-internals.md) as the maintained
source and runtime note and [`source-versions.lock`](../../research/source-versions.lock)
for official bundle, extracted classfile, and inspection-tool fingerprints. It
records exact descriptors, static findings, and the limited wrapper prototype for `ExecutionContext`,
`CallFunction`, `BuildContexts`, `ExecuteCommand`, `CommandFunction`,
`FunctionBuilder`, `ServerFunctionLibrary`, `ServerFunctionManager`,
`FunctionCommand`, and `DebugCommand`, plus selected 26.1.2/26.2 comparisons.
The official Mojang binary is the primary source; third-party docs are
secondary references only. The wrapper prototype does not verify the compiler's
broader runtime behavior or complete Fabric integration.

### 17.2 External implementations

Pinned revisions and licenses are in
[`reference-sources.lock`](../../research/reference-sources.lock). Read each
curated audit before using upstream implementation details:

1. [MCFC audit](../../research/mcfc-audit.md) — [pinned commit](https://gitlab.epicpix.dev/EpicPix/MinecraftFunctionCompiler/-/commit/15ca1db43556999ff29619ed0e41c971b66aae3e); focuses on source capture, custom parsing, typed IR, code generation, call interception, quota policy, and tests.
2. [Mercury audit](../../research/mercury-audit.md) — [pinned commit](https://github.com/clang-mc/Mercury/commit/193d65bd031debf6539136427339f9ce1619696c); focuses on reload integration, parsed action capture, compiled/fallback execution, frame caching, macros, and validation tooling.
3. [Bellows audit](../../research/bellows-audit.md) — [release 1.1.0](https://github.com/Smithed-MC/Bellows/releases/tag/1.1.0) and [pinned commit](https://github.com/Smithed-MC/Bellows/commit/59f6e80514da6022aa4d2afd87bab201c2ed94fd); focuses on 26.3 selector and NBT interception paths.

All three reviews are static. Do not treat upstream README claims, source
structure, or test harnesses as reproduced performance or parity results.

## 18. Concluding research position

The case for a new modern function compiler is **architecturally plausible** and supported by substantive implementation precedents. Exact Minecraft 26.3 classfile behavior is statically documented, and a narrow Fabric wrapper prototype now runs. The compiler design remains **unvalidated for broad semantics and interoperability, and has no measured performance result**.

The evidence does justify building a **narrow, fully reversible prototype**, not immediately a broad bytecode optimizer:

1. Preserve Brigadier parsing, vanilla scheduler, frame semantics and world-operation call paths.
2. Validate a construction-time wrapper and original-function fallback.
3. Instrument exact command cost and yield boundaries.
4. Implement one semantically complete scoreboard adapter.
5. Benchmark and differentially validate entry specialization before fused regions.
6. Add resumable blocks only with a verified quota/trace contract.
7. Keep Mercury and MCFC as implementation references, and Bellows as a runtime interoperability target.

**Decision status: PROVISIONAL.** Promote it to **ACCEPTED** only after completing the source verification and first two runtime milestones. The measured bottleneck and correctness test results—not assumptions about Brigadier, Java bytecode, or scheduler overhead—should determine the eventual compiler design.

---

## Appendix A. Glossary

- **Brigadier parse:** Produces an analyzed command tree/context from source text.
- **`UnboundEntryAction`:** Runnable function-entry representation that binds a command source at execution time.
- **`InstantiatedFunction`:** Identifier and list of executable function entries, including an expanded macro when relevant.
- **`ExecutionContext`:** Queue, limits, tracing/profiling, and execution-driver state.
- **`Frame`:** Nested function/return-control context for queued work.
- **Cost event:** A vanilla debit against the execution quota; distinct from an entry, function line or queue boundary.
- **Yield/check boundary:** An execution point at which vanilla's queue driver can stop or pending work can be discarded.
- **Semantic IR:** Compiler representation of command meaning, effects and control flow.
- **Region fusion:** Execute several semantically distinct operations in one runtime region instead of separately scheduled actions.
- **Fallback:** Preserved original vanilla parsed action/function used when unsupported or unverified.
- **Deoptimization:** Return execution safely to an unoptimized path without replaying completed side effects.
- **Reload generation:** Immutable identity of the data pack/function-registry snapshot to which artifacts belong.
- **Bellows interception point:** Minecraft method targeted by Bellows' runtime Mixin, which specialized code may bypass.
- **Observational equivalence:** Equality of externally relevant behavior, not merely matching final score/NBT values.

## Appendix B. Report change record

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-26 | Consolidated 26.3-oriented execution research; inspected nearby vanilla code and MCFC development source; compared Mercury and Bellows; established provisional architecture, semantic contract, test matrix and milestone gates. |
| 0.1 research update | 2026-10-27 | Fingerprinted exact Minecraft 26.3 and comparison classfiles; pinned MCFC, Mercury, and Bellows revisions; added curated static audits; updated evidence labels and open runtime gates. |
| 0.1 runtime update | 2026-10-28 | Added seven-arm nested fused error/continuation and `return fail`, `return 7`, and nested `return run function` frame-discard parity with exact traces; bounded runtime-test heap use and kept the fused prototype disabled pending broader P0 and workload gates. |
| 0.1 workload update | 2026-10-28 | Screened and fingerprinted seven additional 26.3 datapack archives; added a Blastback no-TNT tick-dispatch profile that reaches one eligible ScoreAdd command, two same-stack Fabric off/on pairs with matching tick-counter deltas, and four randomized pairs on Lithium, Bellows, Lithium+Bellows, and Lithium+Bellows+Moonrise 1.2.0. A separate instrumented diagnostic confirms the specialized entry executed 340 times in its capture window. Three of the four new pairs have matching timed tick deltas; weighted Spark samples move both ways and are too sparse for a performance decision. The TNT restoration event remains invalid, and all optimizations remain disabled. |
| 0.1 backend and lifecycle update | 2026-10-28 | Added the emitted-bytecode runtime arm with the exact erased `UnboundEntryAction` bridge, selected vanilla/Bellows parity checks, 30 injected compilation failures with fallback, 25 reload cycles with stable generated-class retention and bounded metaspace growth, and PERF-004 five-trial full-function timings. Bytecode is 23.0% slower than fused interpretation on the static fixture and remains disabled; all prototypes remain gated on remaining P0 and real-workload evidence. |
| 0.1 compatibility update | 2026-10-28 | Added a six-arm vanilla and Bellows 1.1.2 + Moonrise 1.2.0 selector/entity-NBT matrix. Wrapper-off/on, ScoreAdd, fused, and bytecode arms match vanilla and same-stack pairs for the selected cases; the pinned Bellows 1.1.2 + Moonrise 1.2.1 startup incompatibility and Dynamic Lights workload-output mismatch remain separate scoped findings. |
| 0.1 modded-command update | 2026-10-28 | Added a Fabric-only unknown Brigadier leaf fixture. Across six arms, the command runs once, stores result 7, preserves total score 15, and leaves two eligible regions available to fused and bytecode backends; same-stack compiler-off/on results match. |
| 0.1 macro-reload update | 2026-10-28 | Added a same-argument macro expansion check across a changed-body reload to the full eight-arm runtime suite. Vanilla and all seven Fabric modes retained score 37 while the body marker changed from 1 to 10; all five macro-specializing modes recorded a new expansion compilation. |
| 0.1 Bellows/compiler performance update | 2026-10-28 | Added five randomized PERF-005/006 trials per arm with all-thread 1 ms Spark sampling, whole-server tick percentiles, vanilla differential checks, and five matched stacks. Bellows lowered sampled function share on the controlled NBT fixture; fused interpretation showed no repeatable sample reduction. Compiler prototypes remain disabled; the synthetic fixture does not close PERF-007. |
| 0.1 eligible datapack candidate update | 2026-10-28 | Pinned Vein Miner datapack 5.3.0 for Minecraft 26.3 (GPL-3.0-only) and traced its active tick graph to a direct eligible `#head` ScoreAdd in the per-item queue drain. An isolated vanilla runtime smoke processed a controlled 63-block vein and recorded 480 queue-head increments. The harness entered the internal operation-start path and did not run a compiler arm or the native mining trigger, so PERF-007 remains open pending native workload activation, parity/invocation checks, and repeated profiles. |
| 0.1 randomized Vein Miner profile update | 2026-10-28 | Added a generated in-game post-run block counter and seeded campaign runner. Five randomized 6×6×6 native-trigger pairs on Fabric all match 215 mined blocks, 1,952 queue-head increments, empty ore volume, and idle operation state. Median paired changes are −0.19% event completion time and +0.31% weighted `ServerFunctionManager.execute` samples, with broad ranges and mixed tick percentiles; no reliable ScoreAdd gain is demonstrated. A separate instrumented run records 1,952 specialized executions. Generic fallback coverage and Lithium/Bellows/Moonrise profiles remain open; the datapack has no adjacent eligible region for fused/bytecode workload measurement. |
| 0.1 native eligible workload update | 2026-10-28 | Added a reproducible native mining driver and Spark capture for Vein Miner. Vanilla, Fabric compiler-off, and ScoreAdd-on arms pass the 63-block workload integrity check; instrumented Fabric compiles one queue command and records 480 specialized executions, matching the datapack counter. One fixed-order uninstrumented pair is too short and trends higher in the ScoreAdd arm; a 512-block pilot missed its timeout and was discarded. PERF-007 remains open for generic fallback counts and randomized repeated distributions. The pack has no adjacent eligible region for fused/bytecode workload coverage. |
| 0.1 Lithium Vein Miner and sanity audit update | 2026-10-28 | Completed five randomized 6×6×6 Fabric+Lithium compiler-off/ScoreAdd pairs on Vein Miner. All pairs pass exact workload-state parity. ScoreAdd medians trend slower: +12.47% completion time and +12.46% weighted function samples, with a +101.19% completion outlier and mixed tick percentiles. A separate instrumented native event records 4,212 eligible `#ray` additions and 1,952 `#head` additions. Updated PERF-007/011 status, candidate evidence, and the implementation sanity audit; no optimizations are enabled and no screened datapack has adjacent eligible entries for fused/bytecode profiles. |
| 0.1 Lithium+Moonrise Vein Miner performance update | 2026-10-28 | Completed five randomized 6×6×6 compiler-off/ScoreAdd pairs on Lithium 0.26.2 + Moonrise 1.2.1. All ten arms processed 215 blocks, advanced `#head` 1,952 times, and matched exact workload state. ScoreAdd medians were +19.98% event completion, +21.62% weighted function samples, +37.67% average tick, and +30.53% P95 tick; every range crossed zero, so no reliable gain or regression was established. Both arms carried a temporary dormant diagnostic mixin, making the result directional. Reoriented the next optimization step toward profiling expensive function paths; keep ScoreAdd disabled. |
| 0.1 callback trace update | 2026-10-28 | Added `/debug function` coverage for `execute store result` around a returning function, successful/failing `execute if/unless function`, and `return run`. Mod-free vanilla and all seven Fabric modes matched exact trace text and expected state in the full 26.3 runtime matrix. Other callback and quota-boundary cases remain open. |
| 0.1 quota continuation update | 2026-10-28 | Added a four-actor `execute` followed by a queued `+10` across limits 0–16. All seven Fabric modes match mod-free 26.3 vanilla: the queue tail remains stopped through limit 7 and runs at limit 8. QUOTA-006 observable stop behavior is verified; pure-vanilla per-debit tracing remains unavailable. |
| 0.1 Vein Miner/Bellows compatibility follow-up | 2026-10-28 | Recorded a separate manual 26.3 check without Function Compiler: Vein Miner 5.3.0 completes with Lithium 0.26.2 alone but stalls with Lithium+Bellows 1.1.2. The pinned no-underscore Miraculixx VeinMiner 1.3.6 archive works with the combined stack. The only visible difference the user noted was that 1.3.6 mines the vein in one tick while 5.3.0 spreads work across ticks; cadence is an observation, not an established cause, and the different datapack is not a direct parity control. |
| 0.1 recursive backend parity update | 2026-10-28 | Added a two-ScoreAdd recursive fixture and ran its exact quota map at limits 0–16. Vanilla and all seven Fabric modes match; fused and emitted-bytecode counters each advance 33 times during the fixture, and the forced bytecode compile-failure mode matches vanilla through retained-action fallback. CTRL-004 is verified for the bounded recursive cases. |
| 0.1 callback accounting update | 2026-10-28 | Added opt-in accounting for ordinary Brigadier leaf callbacks in function queues and validated exact 7-generic and 5-generic/2-optimized fixture totals across wrapper, ScoreAdd, fused, and bytecode modes. A native 4×4×4 Vein Miner event on Lithium counted 7,116 generic and 1,122 optimized callbacks; the optimized total matched the independent ScoreAdd execution counter. Callback instrumentation is diagnostic-only and excludes modifier operations and custom executors. PERF-007 callback accounting is verified for this workload; Bellows-compatible profiling remains open. |

| 0.1 selective macro compatibility update | 2026-10-29 | Ran the focused macro fixture in three arms—mod-free vanilla, same-stack compiler-off Fabric, and selective macro candidate—on Fabric, Lithium 0.26.2, Bellows 1.1.2, Bellows+Moonrise 1.2.0, Lithium+Moonrise 1.2.1, Lithium+Bellows, and Lithium+Bellows+Moonrise 1.2.0. All comparisons passed; result reports record mod hashes. Bellows+Moonrise 1.2.1 remains excluded because it does not start. This closes only the covered fixture shapes; provider-specific errors and macro reload failure/overlap remain open. |
| 0.1 malformed and overlapping macro reload update | 2026-10-29 | Added an unterminated macro-template case; vanilla and all nine Fabric runtime modes log and omit it while retaining valid output at score 37/marker 10. The initial overlapping-reload run stages B while A is held, then A publishes last after release, matching vanilla at both states; it also covers held publication and forced whole-resource failure. This two-request result was later extended to a four-request overlap, then a five-request overlap; At that point, six-or-more-request races and macro failure shapes beyond the staged-body/selective-argument path remained open. |
| 0.1 failed-reload bytecode retention update | 2026-10-29 | Repeated 25 successful bytecode reload cycles before injecting a whole-resource reload failure. The failed preparation emitted 17,816 class bytes, but post-GC live generated classes stayed at 17, classloader identity remained stable, and metaspace grew by 20,808 bytes. Macro-specific failed-reload behavior remains open. |
| 0.1 Bellows 1.1.3 native workload and PERF-011 screen | 2026-10-29 | Lithium+Bellows 1.1.3 passes Vein Miner 5.3.0's native 6×6×6 event (215 blocks, 1,952 `#head` increments). Separate diagnostics confirm 9,546 and 9,547 selective-macro hits and 1,952 ScoreAdd executions matching datapack counters. Five no-Spark pairs per candidate pass exact workload parity. Selective macro's median completion change is −18.83% (range −20.62% to +24.37%); ScoreAdd's is +3.60% (range −2.04% to +91.11%). Both are screening-only intervals, with no promotion claim. A 15% selective-macro event-time gain threshold is selected for Lithium+Bellows 1.1.3; the existing 95% interval rule applies, and the confirmatory sample plan remains open. Bellows 1.1.2 failures remain historical. Bellows 1.1.3+Moonrise 1.2.0 passes the native control and a five-pair selective-macro screen (median −20.11%, range −36.67% to +7.01%, 93.75% interval coverage); this is screening only. Bellows 1.1.3+Moonrise 1.2.1 fails startup on a missing EntityLookup.entityById shadow. |
| 0.1 selective macro Bellows 1.1.3 correctness update | 2026-10-29 | Focused run `20261029T054345` passes the macro fixture against mod-free vanilla and same-stack compiler-off on Lithium+Bellows 1.1.3. Coverage includes inline/storage tuples, cache collision and churn, malformed/missing values, entity custom data, multi-parameter and fallback paths, traces, and quota behavior. This is fixture-level parity only; other provider-specific errors and compatibility paths remain open. |
| 0.1 PERF-012 sustained macro screen update | 2026-10-29 | Replaced the initial armor-stand/noise fixture after reviewing Vein Miner's actual queue marker and 216-entry frontier. The revised fixture uses 256 marker entities with distinct `head` macro arguments and 216-entry frontiers; vanilla, off, and candidate arms preserve exactly 256 calls and 32,896 weighted work per active tick. Two complete smoke pairs plus four pairs from an interrupted five-pair run yield an exploratory −82.25% median active-tick-average change (96.875% exact median interval −86.57% to −1.81%). The interval does not support the selected 15% minimum gain. The partial run has no standalone campaign decision; a fixed confirmatory sample plan remains required. |
| 0.1 four-generation reload overlap update | 2026-10-29 | Extended the held-preparation test to keep generation A in flight while B, C, and D publish, then released A and verified its reverse-order publication. All intermediate states, macro markers, load-tag increments (6→7→8→9→10), and macro specialization counts matched the vanilla order across vanilla and all nine Fabric runtime modes. The same run retained old state after the forced whole-resource failure. Five-or-more-request races and macro-specific failed-reload combinations remain open. |
| 0.1 Bellows 1.1.3 Moonrise macro compatibility update | 2026-10-29 | Focused selective-macro parity passes in vanilla/compiler-off/candidate arms on Lithium+Bellows 1.1.3+Moonrise 1.2.0 (run `20261029T070635`), with the selected path counted for direct, fallback, debug, and quota cases. Moonrise 1.2.1 fails before the candidate starts: Bellows' `MoonriseEntityLookupMixin` shadows missing `EntityLookup.entityById`. A native Vein Miner 5.3.0 control then passes on the 1.2.0 stack (215 blocks, 1,952 `#head` increments, clean final state). Five randomized selective-macro pairs preserve exact state, with −20.11% median event completion (−36.67% to +7.01%); 93.75% interval coverage makes this screening only. |
| 0.1 PERF-011 Moonrise 1.2.0 screen | 2026-10-29 | Lithium+Bellows 1.1.3+Moonrise 1.2.0 native Vein Miner 5.3.0 6×6×6 control passes 215/215 blocks and 1,952 `#head` increments with clean final state. Five randomized no-Spark selective-macro pairs pass exact work parity; median event completion changes −20.11%, with a −36.67% to +7.01% range and 93.75% exact median-interval coverage. Screening only; no promotion claim. The selected 15% worthwhile-gain threshold applies, but confirmatory sample size is open. |
| 0.1 five-request reload overlap update | 2026-10-29 | Extended the held-preparation sequence to keep request A in flight while B, C, D, and E publish, then released A and verified that A publishes last. Vanilla and all nine Fabric runtime modes match all five intermediate/final function, tag, and macro states; the load tag advances from 6 to 11, the five macro-specializing modes each record five specialization updates, and a forced whole-resource failure after publication retains A at load count 11. At that point, six-or-more-request races and macro failure shapes beyond the staged-body/selective-argument path remained open. |
| 0.1 Bellows 1.1.3 selector/NBT compatibility update | 2026-10-29 | Extended the selected 26.3 selector and entity-NBT compatibility probe to Lithium 0.26.2 + Bellows 1.1.3 + Moonrise 1.2.0. Run `20261029T154729` passes seven arms: vanilla, Fabric-off, and same-stack wrapper, ScoreAdd, fused, and bytecode modes. Selected selector identities/order, entity NBT, tag-index updates, `home_pos`/`home_radius`, and the modded leaf match; all same-stack pairs pass. Artifact hashes are recorded in the maintained Bellows audit. Untested selector and filtered-NBT combinations remain open. |
| 0.1 PERF-011 selective-macro confirmation plan | 2026-10-29 | Registered a fixed 23-pair randomized Lithium+Bellows 1.1.3 Vein Miner 5.3.0 campaign (seed `26871037`) with `operation_completion_seconds` as the sole primary metric and a 15% worthwhile-gain threshold. The exact two-sided median interval has 96.531% coverage (7th through 17th order statistics); its upper endpoint must be at or below −15% to meet the threshold. No early stopping is allowed; workload-parity failures remain recorded and do not count as timing pairs. The small pilot does not guarantee adequate power. |
| 0.1 PERF-011 selective-macro confirmation result | 2026-10-29 | The preregistered 23-pair no-Spark run completes with exact workload parity in all 46 arms (215 blocks and 1,952 `#head` increments each). Median paired event-completion change is −19.27%; 21/23 pairs are faster and 16/23 reach at least 15%. The full range is −46.80% to +45.98%; the 96.531% exact median interval is −27.09% to −13.03%. It supports a faster median but does not establish the 15% minimum, so the gate is inconclusive and the prototype remains disabled. Raw report: `build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-selective-macro-23pairs-seed26871037-20261029T161947Z.json`. |
| 0.1 selective macro error and composite entity argument update | 2026-10-29 | On Lithium+Bellows 1.1.3, mod-free vanilla, same-stack compiler-off, and selective macro match a present wrong-typed entity parameter (`amount:"not_an_integer"`) through the exact nested `/debug function` trace and state. Outer pre-error and post-error side effects each run once, the score target is unchanged, and the failed macro function's next command does not run. A second selected-path case copies a nested compound containing an int array and string list into storage, then verifies all six nested values. The selected-path counter advances once for each candidate case. Focused report `build/reports/runtime-probe/macro-20261029T181645.results.json`. |
| 0.1 selective macro Bellows+Moonrise error and value compatibility | 2026-10-29 | Repeated the wrong-typed entity argument and nested compound/list/int-array cases on Lithium+Bellows 1.1.3+Moonrise 1.2.0. Mod-free vanilla, same-stack compiler-off, and selective candidate match the exact error trace, state, and all six copied NBT values; the candidate counter advances once for each shape. Focused report `build/reports/runtime-probe/macro-20261029T181942.results.json`. |
| 0.1 selective macro alternate-provider fallback update | 2026-10-29 | Added a present wrong-typed storage-provider argument under `/debug function` to verify that the selective entity-data path does not intercept it. Vanilla, same-stack compiler-off, and candidate match exact trace and state, including outer side effects, unchanged target score, and skipped inner continuation. The candidate's selected entity-path counter remains zero. Verified on Lithium+Bellows 1.1.3 (report `build/reports/runtime-probe/macro-20261029T182217.results.json`) and Lithium+Bellows 1.1.3+Moonrise 1.2.0 (report `build/reports/runtime-probe/macro-20261029T182321.results.json`). |
| 0.1 selective macro nested entity path fallback update | 2026-10-29 | Added a nested entity custom-data path (`data.nested`) with both root `amount:5` and nested `amount:7`. Vanilla, same-stack compiler-off, and candidate return the nested value 7, preserve both surrounding side effects and macro continuation, and match the full `/debug function` trace. The selective entity-data counter remains zero, confirming fallback for nonliteral `data` paths. Verified on Lithium+Bellows 1.1.3 (`build/reports/runtime-probe/macro-20261029T182921.results.json`) and Lithium+Bellows 1.1.3+Moonrise 1.2.0 (`build/reports/runtime-probe/macro-20261029T183028.results.json`). |
| 0.1 six-request reload overlap update | 2026-10-29 | Extended the held-preparation race to keep A in flight while B, C, D, E, and F publish, then released A and verified that A publishes last. The vanilla and all nine Fabric runtime modes match all six intermediate/final function, tag, and macro states; load count advances once per generation (10→16 in this full run), and each of the six macro-specializing modes records six specialization updates. F publishes direct/probe_v2/tag/macro values 808/1212/808/808; A then publishes 303/707/707/303. The selective-macro counter advances after each publication and after a forced whole-resource failure, which retains A at marker 303. Report: `build/reports/runtime-probe/concurrent-resource-reload-results.json`. Seven-or-more-request interleavings and macro failure shapes beyond the staged-body/selective-argument path remain open. |
| 0.1 execute-if return-failure continuation update | 2026-10-29 | Added a child function that applies +1, returns failure, and has a pending +100/+100 region, invoked by `execute if function` before the parent's +10/+20 region. Vanilla and all nine Fabric modes finish at score 31 with the exact five-event `/debug function` trace; the conditional +1000 and child tail do not run, and the parent region executes once. Fused and bytecode execution counters each increase by exactly one for this fixture. Report: `build/reports/runtime-probe/results.json`. Other isolated callback/frame-discard shapes remain open. |
| 0.1 execute-store return-failure continuation update | 2026-10-29 | Added a child function that applies +1, returns failure, and has a pending +100/+100 region, invoked by `execute store success` before the parent's +10/+20 region. The seeded destination becomes 0, the child tail is discarded, and the parent region resumes once. Vanilla and all nine Fabric modes finish at score 32 with the exact six-event `/debug function` trace; fused and bytecode each execute one parent continuation region. Report: `build/reports/runtime-probe/results.json`. Other isolated callback/frame-discard shapes remain open. |
| 0.1 execute-store-result continuation update | 2026-10-29 | Added a child function that applies +1, returns 7, and has a pending +100/+100 region, invoked by `execute store result` before the parent's +10/+20 region. The store receives 7, the child tail is discarded, and the parent region resumes once. Vanilla and all nine Fabric modes finish at score 32 with the exact six-event `/debug function` trace; fused and bytecode each execute one parent continuation region. The full ten-arm run compares 82 exact debug traces per arm. Report: `build/reports/runtime-probe/results.json`. Other isolated callback/frame-discard shapes remain open. |
| 0.1 execute-unless return-failure continuation update | 2026-10-29 | Added a child function that applies +1, returns failure, and has a pending +100/+100 tail, invoked by `execute unless function` before its +1000 branch and the parent's +10/+20 continuation. The failed child takes the branch, discards its own tail, and resumes the parent tail once. Vanilla and all nine Fabric modes finish at score 1032 with the exact six-event `/debug function` trace; fused and bytecode each execute one parent continuation region. The full ten-arm run compares 83 exact debug traces per arm. Report: `build/reports/runtime-probe/results.json`. Other frame-discard triggers remain open. |
| 0.1 execute-store-result failure continuation update | 2026-10-29 | Added a child function that applies +1, returns failure, and has a pending +100/+100 tail, invoked by `execute store result` before the parent's +10/+20 continuation. Vanilla stores result 0, preserves the completed child effect, discards the child tail, and resumes the parent tail once at score 32. All nine Fabric modes match the exact six-event vanilla trace; fused and bytecode each execute one parent continuation region. The current ten-arm report compares 84 exact debug traces per arm. Report: `build/reports/runtime-probe/results.json`. Other callback and frame-discard combinations remain open. |

| 0.1 execute-store-success return-value continuation update | 2026-10-29 | Added a child function that applies +1, returns 7, and has a pending +100/+100 tail, invoked by `execute store success` before the parent +10/+20 continuation. The success flag is 1 despite the numeric return value; the child tail is discarded, and the parent tail resumes once at score 32. Vanilla and all nine Fabric modes match the exact six-event trace; fused and bytecode each execute one parent continuation region. The full ten-arm report compares 85 exact debug traces per arm. Report: `build/reports/runtime-probe/results.json`. Other callback and frame-discard combinations remain open. |
| 0.1 execute-store-result nested return-run continuation update | 2026-10-29 | Added a caller with `execute store result` calling a wrapper that uses `return run function` to invoke a child returning 7, with pending `+100/+100` tails in both returning frames and a parent `+10/+20` continuation. The store receives 7, both pending tails are discarded, and the parent tail resumes once at score 37. Vanilla and all nine Fabric modes match the exact eight-event trace; fused and bytecode each execute one parent continuation region. The full ten-arm report compares 86 exact debug traces per arm. Report: `build/reports/runtime-probe/results.json`. Other callback and frame-discard combinations remain open. |
| 0.1 execute-store-success nested return-run continuation update | 2026-10-30 | Added paired callers with `execute store success` calling a wrapper that uses `return run function` to invoke a child returning 7 or returning failure, with pending `+100/+100` tails in both returning frames and a parent `+10/+20` continuation. The store receives 1 on child return 7 and 0 on child return fail; in both cases, pending tails in both frames are discarded and the parent continuation resumes once at score 37. Vanilla and all nine Fabric modes match the exact eight-event traces; fused and bytecode each execute one parent continuation region per case. The full ten-arm report compares 88 exact debug traces per arm. Report: `build/reports/runtime-probe/results.json`. Other callback and frame-discard combinations remain open. |
| 0.1 selective macro block-provider and alternate entity-path fallback update | 2026-10-30 | Added a wrong-typed block-entity macro argument (`with block ... data`) and an alternate entity custom-data path (`data.custom_args`) into lifecycle tests. In all ten runtime modes, vanilla state and exact debug traces match. For the block provider, vanilla's exact error trace and continuation state are preserved with zero candidate fast-path hits. For the alternate entity path, the native fallback returns 9 with zero fast-path hits. Report: `build/reports/runtime-probe/results.json`. Other provider-specific error branches remain open. |
| 0.1 25-cycle bytecode lifecycle and reload-failure retention rerun | 2026-10-30 | Re-ran 25 changed-body/tag reload cycles followed by function removal, re-addition, malformed parse, and an injected whole-resource reload failure across mod-free vanilla, wrapper-off, and bytecode-emitted with the expanded 88-trace fixture set. Bytecode retained exactly 38 live generated classes after every GC cycle across all 29 reloads, classloader identity remained stable at 327177752, and metaspace grew by at most 983,088 bytes (~0.94 MiB) from a 120,808,896 baseline. Median reload completion was 173.1 ms bytecode, 172.0 ms wrapper-off, and 141.6 ms vanilla. The failed whole-resource reload emitted 39,715 class bytes during aborted preparation, retained exactly 38 live classes post-GC, and increased metaspace by 16,304 bytes with complete state rollback. Report: `build/reports/runtime-probe/whole-resource-reload-failure-results.json`. |

**Next review event:** After the remaining P0 semantic cases, selected compatibility-stack profiles, timer calibration, and (if a pinned pack with adjacent eligible entries is found) real-world fused/bytecode measurements, update §§3–5 and the ADR with the complete parity and performance evidence. PERF-011 now shows a faster selective-macro median on Lithium+Bellows 1.1.3 Vein Miner, but its exact interval does not establish the selected 15% minimum. The native direct-ScoreAdd path still shows no reliable gain. PERF-005/006 records controlled selector/NBT costs but no compiler gain.

