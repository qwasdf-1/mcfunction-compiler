# SCHED-COMP-020 — Why did ScoreAdd's synthetic CPU gain disappear in the real mining event?

**Status:** **Counter-domain revision after first diagnostic failed its false equivalence assumptions.** Original [CI #43689591524](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43689591524) completed the 215-ore gameplay event in all three JVMs, but the instrumented runner rejected its counts. No valid root-cause inference is made from that failed attempt. The re-run adds *diagnostic-only* typed callback entry and scope counters to establish exact coverage; no production flags, optimization paths, or 30-server performance observations are changed.

## Existing evidence and motivating hypotheses

1. SCHED-COMP-016's directly randomized 12-JVM straight-line scoreboard benchmark found the cached typed ScoreAdd callback used **−8.923 signed log-%** CPU versus the native callback (~8.5% ordinary relative CPU) on the exact synthetic workload.
2. The complete, recovered SCHED-COMP-018R2 full-event native Vein Miner study found **+0.7831% median Server-thread CPU** for cached ScoreAdd versus compiler optimizers off; exact 97.85%-coverage interval **[−9.1110%, +8.9656%]**. Real event duration was +0.6941% median, interval [−7.2468%, +7.0526%]. Both placebo intervals included zero, but neither treatment benefit was established. No 15% real-workload gain supported.
3. The real Vein Miner event itself suffered substantial tick lag (typically ~250–310ms/tick in the prior heavy 6×6×6 fixture). Therefore *the absence of an improvement cannot automatically be attributed to the server always running at 20 TPS*. It was not.
4. Plausible hypotheses to distinguish: **Amdahl dilution** (ScoreAdd takes too little of the full-event CPU), **execution reach** (few eligible commands actually run), **mismatched command shapes**, **queue/tick scheduling or non-ScoreAdd work**, and **high host/game noise**. The study may reject some, but cannot magically isolate exclusive CPU without a separate sampling-based profile.

## Scope, protocol and safeguards

Use the exact pinned publisher Vein Miner 5.3.0+26.3 ZIP (SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), Minecraft 26.3 Fabric / Java 25, identical 6×6×6 native playerbot ore-mining event, and unmodified production ScoreAdd semantics. Fixed setup RCON 45-second forceload limit, pre-event 9-second tick stability gate, and 150-second event cap follow completed R2. The same native state tuple and 1,952 queue steps must match across every arm. **These are three independent diagnostic boots, not a randomized CPU performance trial.**

1. **Off CPU reference:** `--compiler-mode off --no-spark --capture-server-thread-cpu`. Requires all 215 ore operations, complete queue drain, valid Server-thread clock, and no ScoreAdd compilation. Used only as an absolute event CPU denominator.
2. **Cached CPU reference:** `--compiler-mode score-add --no-spark --capture-server-thread-cpu`. Exact same event with cached immutable-env override and genuine ScoreAdd specialization. No per-callback or Spark instrumentation. Used only to obtain an independent absolute event CPU scale; **do not calculate a significant off-vs-cached effect from these two unpaired single boots**.
3. **Counted compiled diagnostic:** `--compiler-mode score-add-instrumented --count-command-callbacks --no-spark`. Counts actual per-function ScoreAdd executions and ordinary function-queue leaf callbacks during the real event. Must verify **four compiled ScoreAdd commands in `vm:queue/drain`, hence `4 × 1952 = 7808` successful queue callbacks**, not 1952. A global successful typed-ScoreAdd counter, the separate entry count in `ScoreAddCommand.run`, its in-scope subset, and the instrumented plain-text leaf-wrapper count are separately checked using actual code-path inclusion relationships. These counters are **not required to be equal**. This mode adds instrumentation and wrappers, so **none of its timings are comparable** with the uninstrumented CPU arms.

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
| `vm:queue/drain` compiled ScoreAdd instructions | 4 | Four separately compiled source commands |
| `vm:queue/drain` executed ScoreAdds | **7,808** | Four successfully executed commands on each of 1,952 queue-head steps |
| `vm:detection/ray_step` executed ScoreAdds | 1,638 | A separate typed function's successfully executed commands |
| Global typed `score_add_executed` event delta | **26,415** | Successful ScoreAddCommand typed mutations **across all functions**, recorded after response/feedback, regardless of leaf callback wrapper or execution scope |
| Optimized Brigadier leaf-wrapper callbacks | **10,769** | Only eligible `CallbackMetricCommand` instances directly wrapping a typed ScoreAddCommand, counted before delegation and only while the callback-metrics scope is active |
| Generic Brigadier leaf-wrapper callbacks | 40,785 | Other instrumented ordinary Brigadier leaf wrappers; a generic wrapper **can itself delegate into typed commands** |
| Total instrumented leaf-wrapper callbacks | 51,554 | The sum of the two **wrapper domains**, not all Minecraft CPU work |

The global typed counter is incremented inside `ScoreAddCommand.runUntimed` following the scoreboard mutation and feedback when `FC_SCORE_ADD_METRICS` is enabled; the function-specific counter is keyed by the parsed function identifier. `CommandCallbackMetricPrototype.compile` installs a leaf wrapper only on accepted `PlainTextFunction` executable Brigadier context chains, **skipping custom executors**; its `CallbackMetricCommand.run` increments the leaf count *before* invoking the delegate but only when `ProbeMetrics.commandCallbackScopeActive()` is true. `ExecutionContextMixin.runCommandQueue` begins/ends that optional scope for queued execution. It is therefore incorrect to require `optimized_score_add_leaf_callbacks == score_add_executed` even if both metrics are enabled. That inequality alone does **not** prove an instrumentation failure or isolate why a particular invocation missed the leaf wrapper.

The revision introduces two **new, diagnostic-only** counter hooks at entry to `ScoreAddCommand.run`: `score_add_callback_entries` counts every entered typed ScoreAddCommand (even if ultimately delegating/failing); `score_add_callback_entries_in_scope` counts the subset whose callback scope was active. They are only incremented when BOTH ScoreAdd and ordinary-callback metrics are enabled, and are off during all normal CPU studies. The revised path-inclusion gates require:

`0 < optimized_leaf <= typed_entry_in_scope <= typed_entry_total`, and `0 < successful_typed_executions <= typed_entry_total`. Require `generic+optimized=total_wrapped_leaf`; `score_add_executed_global >= queue_executed + ray_executed`; and `queue_executed=4×1952=7808`. Explicitly reject corrupted or missing independent counters. The newly derived difference `typed_entry_in_scope - optimized_leaf` is **typed callback entries not represented by the direct optimized leaf-wrapper counter**, not necessarily an uninstrumented player command and certainly not a CPU share.

The historical uninstrumented compiler-off reference was **13,757,473,431 Server-thread running CPU nanoseconds**; at the instrumented run's **26,415 global successful ScoreAdd executions**, a counterfactual 15%-whole-event reduction would require about **78,123 ns (78.1 microseconds) saved per ScoreAdd**, holding all other work constant. This is an illustrative Amdahl budget from **independent single runs** with instrumented counts; it is not exclusive CPU profiling, a direct measure of the ScoreAdd callback cost, or statistically supported performance attribution. The updated diagnostic verifies this formula against a new valid instrumented run rather than reusing invalid assumptions.

**Revision discipline:** The prior run and raw data remain accessible unchanged. New tests explicitly accept the archived real inequalities, enforce actual four-per-head work, reject impossible ordering of new entry/scope counters, and preserve the conservative noncausal interpretation. Only the independent **three-JVM diagnostic** is rerun; the previously completed 30-event SCHED-COMP-018R2 CPU study is not repeated or reanalyzed to seek significance.
