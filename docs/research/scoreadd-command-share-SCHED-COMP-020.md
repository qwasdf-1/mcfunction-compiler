# SCHED-COMP-020 — Why did ScoreAdd's synthetic CPU gain disappear in the real mining event?

**Status:** **Three-server path-coverage diagnostic completed and passed on 2026-11-15** ([CI #43692883388](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692883388), [raw artifact 14153550537](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692883388/artifacts/14153550537)). Earlier runs [#43689591524](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43689591524) and [#43692072354](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692072354) completed the 215-ore event but failed invalid cross-domain counter invariants; neither was a successful diagnostic. The legacy `score_add_executed` metric is shared by multiple specialized commands and composite wrappers. The validated run instead uses a new exclusive successful `ScoreAddCommand` counter. This is **execution-path evidence only, not proof of Amdahl dilution or of a causal CPU effect**. No production flags, optimization paths, or 30-server performance observations are changed.

## Existing evidence and motivating hypotheses

1. SCHED-COMP-016's directly randomized 12-JVM straight-line scoreboard benchmark found the cached typed ScoreAdd callback used **−8.923 signed log-%** CPU versus the native callback (~8.5% ordinary relative CPU) on the exact synthetic workload.
2. The complete, recovered SCHED-COMP-018R2 full-event native Vein Miner study found **+0.7831% median Server-thread CPU** for cached ScoreAdd versus compiler optimizers off; exact 97.85%-coverage interval **[−9.1110%, +8.9656%]**. Real event duration was +0.6941% median, interval [−7.2468%, +7.0526%]. Both placebo intervals included zero, but neither treatment benefit was established. No 15% real-workload gain supported.
3. The real Vein Miner event itself suffered substantial tick lag (typically ~250–310ms/tick in the prior heavy 6×6×6 fixture). Therefore *the absence of an improvement cannot automatically be attributed to the server always running at 20 TPS*. It was not.
4. Plausible hypotheses to distinguish: **Amdahl dilution** (ScoreAdd takes too little of the full-event CPU), **execution reach** (few eligible commands actually run), **mismatched command shapes**, **queue/tick scheduling or non-ScoreAdd work**, and **high host/game noise**. The study may reject some, but cannot magically isolate exclusive CPU without a separate sampling-based profile.

## Scope, protocol and safeguards

Use the exact pinned publisher Vein Miner 5.3.0+26.3 ZIP (SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), Minecraft 26.3 Fabric / Java 25, identical 6×6×6 native playerbot ore-mining event, and unmodified production ScoreAdd semantics. Fixed setup RCON 45-second forceload limit, pre-event 9-second tick stability gate, and 150-second event cap follow completed R2. The same native state tuple and 1,952 queue steps must match across every arm. **These are three independent diagnostic boots, not a randomized CPU performance trial.**

1. **Off CPU reference:** `--compiler-mode off --no-spark --capture-server-thread-cpu`. Requires all 215 ore operations, complete queue drain, valid Server-thread clock, and no ScoreAdd compilation. Used only as an absolute event CPU denominator.
2. **Cached CPU reference:** `--compiler-mode score-add --no-spark --capture-server-thread-cpu`. Exact same event with cached immutable-env override and genuine ScoreAdd specialization. No per-callback or Spark instrumentation. Used only to obtain an independent absolute event CPU scale; **do not calculate a significant off-vs-cached effect from these two unpaired single boots**.
3. **Counted compiled diagnostic:** `--compiler-mode score-add-instrumented --count-command-callbacks --no-spark`. Counts actual per-function ScoreAdd executions and ordinary function-queue leaf callbacks during the real event. Must verify **four commands in `vm:queue/drain` counted by the shared ScoreAdd-family compilation metric, hence `4 × 1952 = 7808` successful queue callbacks**, not 1952. A global successful typed-ScoreAdd counter, the separate entry count in `ScoreAddCommand.run`, its in-scope subset, and the instrumented plain-text leaf-wrapper count are separately checked using actual code-path inclusion relationships. These counters are **not required to be equal**. This mode adds instrumentation and wrappers, so **none of its timings are comparable** with the uninstrumented CPU arms.

No JFR, Spark or CPU attribution inference is made in this first diagnostic. All three worlds are fresh and all source/gameplay conditions are identical; no observed result is filtered after the mining packet begins. Any incomplete queue, tick instability before the event, unreadable Server thread, mismatched publisher digest, invalid command counter, or mismatched ore/marker state invalidates the diagnostic. Preserve every stdout/stderr and native event result; never pool previous experiments into this study.

## What the numerical analysis can establish

The key outputs are:

- **Number of ScoreAdd instructions compiled** in `vm:queue/drain`: static reach only. This is *not* how often they execute.
- **Number of ScoreAdd callbacks actually executed**, with a separate generic leaf-callback count: runtime reach and **fraction of observed ordinary leaf callbacks**. The ratio excludes modifier handling, custom command executors, world simulation and many tick operations; it is explicitly **NOT a fraction of CPU**.
- **Whole-event Server-thread CPU running nanoseconds** from separate, uninstrumented off/cached events. These are diagnostics, not a randomized performance effect.
- A direct, hypothetical required saving to achieve a **15% whole-event CPU reduction by optimizing only eligible ScoreAdd callbacks**:

  `required_saved_ns_per_ScoreAdd = 0.15 × whole_event_server_thread_CPU_ns / actually_executed_ScoreAdd_callbacks`.

  This is a *counterfactual budget*, not the observed ScoreAdd cost. If the required savings per eligible callback are orders of magnitude above the entire standalone command's likely execution cost, the lack of whole-event improvement is mechanistically unsurprising. If many eligible commands run and the threshold seems attainable, take the next step: an independent sampling/profiling attribution of command, function-scheduler and world-update CPU costs.

This diagnostic tests **execution reach** and the scale required for large event-wide gains. It does not by itself prove the exact exclusive CPU fraction of ScoreAdd, or causally identify one sole root cause.

## Next pressure experiment: conditional, not a fishing expedition

Once actual ScoreAdd invocation density is measured, a separate controlled mixed-command workload can vary **targeted eligible-command density** and **server tick pressure**. Treat them as *two separate experimental factors* rather than assume more lag improves an optimization. At each density and pressure condition, directly compare identical native vs compiled commands with a native/native placebo, total exact scoreboard work, TPS, mean/p95 tick time and running CPU. Calibrate stable pre-intervention load close to 50 mspt and one overloaded regime, rather than throwing an unbounded synthetic workload into a tick. If using intentional CPU quotas or affinity restrictions, the protocol must distinguish planned cgroup throttling from *unplanned host contention*—the prior zero-throttle gate is not applicable under deliberate throttling.

The expected effect has two different axes: a high enough eligible-command **CPU fraction** may reveal a larger absolute CPU saving, while a baseline around **50 mspt** may convert a modest tick-time change into an observable difference in TPS. Merely applying unrelated load generally *dilutes* the proportion of CPU saved by ScoreAdd. The Vein Miner fixture already runs far below 20 TPS during the heavy event, so another identical Vein Miner pressure campaign is not the appropriate first experiment.

**Implementation:** `scripts/ci_scoreadd_workload_share.py`, `tests/test_scoreadd_workload_share.py`, `.github/workflows/research-scoreadd-workload-share.yml`. Raw output `build/benchmarks/SCHED-COMP-020/diagnostic.json` and per-server original benchmark manifests. No change to production optimization defaults; one-file cache patch remains draft PR #15.

## Diagnostic revision after 020 first-run failure

The first run [#43689591524](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43689591524), [raw artifact 14151783327](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43689591524/artifacts/14151783327), finished the real mining event in all **three** independent JVMs. Its *unmodified* ScoreAdd instrumented event registered the full 215 ore, correct 1,952 queue steps, and valid host-quality conditions. The instrumented runner exited nonzero **after** work completion because its original validator incorrectly compared counters from different execution domains. It produced **no valid causal CPU-speed result** and should not be called successful CI.

Archived observations and exact source-code attribution:

| Counter/source | Archived actual | What it measures |
| --- | ---: | --- |
| `vm:queue/drain` compiled shared-family instructions | 4 | Four specialized source commands recorded under a shared family metric, not necessarily four direct ADD commands |
| `vm:queue/drain` shared-family increments | **7,808** | Four metric-bearing executions on each of 1,952 queue-head steps; not exclusively direct ScoreAddCommand |
| `vm:detection/ray_step` shared-family increments | 1,638 | A separate function's mixed-family counter increments, not exclusively direct ScoreAddCommand |
| Global `score_add_executed` event delta | **26,415** | **Mixed aggregate** of several specialized command types and composites; cannot be used as the number of successful direct ScoreAddCommand calls |
| Optimized Brigadier leaf-wrapper callbacks | **10,769** | Only eligible `CallbackMetricCommand` instances directly wrapping a typed ScoreAddCommand, counted before delegation and only while the callback-metrics scope is active |
| Generic Brigadier leaf-wrapper callbacks | 40,785 | Other instrumented ordinary Brigadier leaf wrappers; a generic wrapper **can itself delegate into typed commands** |
| Total instrumented leaf-wrapper callbacks | 51,554 | The sum of the two **wrapper domains**, not all Minecraft CPU work |

The old global metric is incremented inside `ScoreAddCommand.runUntimed` following mutation and feedback **AND ALSO** in `ScoreOperationCommand`, `ScoreResetCommand`, `ScoreStoreCommand`, `ContextModifierCommand` and `InlinedForkingCommand`. The last two can increment after delegated inner work, so the aggregate does not count distinct underlying ScoreAdd calls. It is also used as a per-function family counter and shares the `score_add_compiled` label across specialized command types. It must **never** be labeled an exclusive count of successful direct ScoreAdd callbacks. `CommandCallbackMetricPrototype.compile` installs a leaf wrapper only on accepted `PlainTextFunction` executable Brigadier context chains, **skipping custom executors**; its `CallbackMetricCommand.run` increments the leaf count *before* invoking the delegate but only when `ProbeMetrics.commandCallbackScopeActive()` is true. `ExecutionContextMixin.runCommandQueue` begins/ends that optional scope for queued execution. It is therefore incorrect to require `optimized_score_add_leaf_callbacks == score_add_executed` even if both metrics are enabled. That inequality alone does **not** prove an instrumentation failure or isolate why a particular invocation missed the leaf wrapper.

The revision introduces diagnostic-only counters at `ScoreAddCommand.run` entry: `score_add_callback_entries` counts every entered typed ScoreAddCommand (even if ultimately delegating/failing); `score_add_callback_entries_in_scope` counts the subset whose callback scope was active. A third **exclusive** counter, `score_add_direct_successes`, increments **only inside `ScoreAddCommand.runUntimed` after mutation and feedback**, not in any operation/reset/store/composite wrapper. These are active only during opt-in callback diagnostics, and are off during all normal CPU studies. Note that `ScoreAddCommand` itself handles ADD, SET and REMOVE modes, so the exclusive counter means successful callbacks to this typed command family, not necessarily literal `add` commands only. The revised path-inclusion gates require:

`0 < optimized_leaf <= typed_entry_in_scope <= typed_entry_total`, and `0 < exclusive_direct_successes <= typed_entry_total` and `global_mixed_family_increments >= exclusive_direct_successes`. Require `generic+optimized=total_wrapped_leaf`; `global_family >= queue_family + ray_family`; and `queue_family=4×1952=7808`. Explicitly reject corrupted or missing independent counters. The newly derived difference `typed_entry_in_scope - optimized_leaf` is **typed callback entries not represented by the direct optimized leaf-wrapper counter**, not necessarily an uninstrumented player command and certainly not a CPU share.

The historical uninstrumented compiler-off reference was **13,757,473,431 Server-thread running CPU nanoseconds**. The previous **78.1 microsecond** illustrative saving-per-command estimate used the **mixed** 26,415-increment aggregate as its denominator. That was **not a valid exclusive ScoreAdd denominator**, so the estimate is withdrawn. The second diagnostic run [#43692072354](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692072354), [raw archive 14153101378](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692072354/artifacts/14153101378), established **10,978 ScoreAddCommand entries, all in callback scope, with 10,353 direct optimized leaf-wrapper callbacks**: the missing 625 direct-leaf counts are *not* explained by scope being inactive. That same event had **25,939 aggregate family increments**, which source-code inspection proves cannot be interpreted as 25,939 exclusive ScoreAdds. To compute an honest diagnostic Amdahl budget, use the next run's exclusive successful `ScoreAddCommand` count; its CPU reference will remain **unpaired and noncausal**, not a direct measure of callback CPU.

**Revision discipline:** The prior run and raw data remain accessible unchanged. New tests explicitly accept the archived real inequalities, enforce actual four-per-head work, reject impossible ordering of new entry/scope counters, and preserve the conservative noncausal interpretation. Only the independent **three-JVM diagnostic** is rerun; the previously completed 30-event SCHED-COMP-018R2 CPU study is not repeated or reanalyzed to seek significance.

## Completed diagnostic — 2026-11-15, CI #43692883388

The dedicated [three-JVM workflow](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692883388) passed its Python contract tests (8 tests), Java build, publisher ZIP digest check, native-event validation, counter accounting, and artifact upload. The [raw archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43692883388/artifacts/14153550537) contains the diagnostic JSON and independent native run records. The three arms remained **separate unpaired diagnostic boots**. No performance or causality claim follows from their CPU difference.

| Validated metric | Observed |
| --- | ---: |
| Ore work / queue heads | 215 / 1,952 |
| Compiled mixed-family callbacks in `vm:queue/drain` per head | 4 |
| `vm:queue/drain` shared-family increments | **7,808** |
| `vm:detection/ray_step` shared-family increments | 1,332 |
| Global mixed `score_add_executed` increments | **26,206** |
| Exclusive successful `ScoreAddCommand.runUntimed` callbacks (ADD/SET/REMOVE) | **11,124** |
| Typed `ScoreAddCommand.run` entries / entries within scope | **11,124 / 11,124** |
| Directly instrumented optimized leaf wrappers | **10,485** |
| In-scope typed entries outside direct optimized-wrapper domain | **639** |
| Generic leaf wrappers / total leaf wrappers | 41,297 / 51,782 |
| Optimized direct wrappers / all instrumented leaf wrappers | **20.248%** |
| Direct optimized wrapper coverage of scoped typed entries | **94.256%** |
| Uninstrumented compiler-off event Server-thread running CPU | **17,907,425,481 ns** |
| Uninstrumented cached-ScoreAdd event Server-thread running CPU | **17,694,329,165 ns** |
| Hypothetical per-callback saving to reduce *off* event CPU by 15% | **241,470 ns (241.47 µs)** |
| Hypothetical per-callback saving to reduce *cached* event CPU by 15% | **238,597 ns (238.60 µs)** |

**Interpretation.** The 26,206 shared-family increments cannot be used as a denominator for direct ScoreAdd costs. Exactly 11,124 successful typed callbacks were counted, and all typed entries in this run were in the callback scope. The 639 difference between typed entries and directly instrumented optimized leaf wrappers is **not a scope leak**; it is a difference between instrumentation coverage domains, which can include nested commands and modifier-delegated execution. The direct-leaf ratio of 20.248% is **not an estimate of CPU time, a denominator for all actual Minecraft commands, or evidence that ScoreAdd accounts for 20.248% of event CPU**. The 241.47 µs requirement is a *counterfactual saving* computed from a separate uninstrumented CPU boot, not a measured per-command cost.

The two uninstrumented event CPU values differ by about 1.19% relative to the compiler-off value, but the two boots are not paired or randomized; this is **not** evidence for an optimization effect. The earlier failed path-coverage run counted 10,978 typed entries, versus 11,124 here, despite the same 215 ore operations and 1,952 queue steps. Therefore exact final workload parity does not imply a universal fixed number of typed callbacks across all runs.

**Conclusion and next gate.** SCHED-COMP-020 **passes execution-reach and instrumentation consistency**, resolving the original false-equality failure. It **does not establish actual exclusive ScoreAdd CPU share**, so Amdahl dilution remains plausible, not proved. A follow-on independent Server-thread CPU sampling/attribution study should determine the exclusive cost of eligible ScoreAdd callbacks versus function scheduling, queue dispatch, modifiers, and world updates before making a performance diagnosis or proposing another 30-event comparison. The older 30-server SCHED-COMP-018R2 performance study is not rerun as part of 020.
