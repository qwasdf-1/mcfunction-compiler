# SCHED-COMP-020 — Why did ScoreAdd's synthetic CPU gain disappear in the real mining event?

**Status:** Predeclared diagnostic, not a new supported performance comparison. No root-cause conclusion until actual executed-command counts, all three real mining-event state gates, and the Amdahl budget check pass.

## Existing evidence and motivating hypotheses

1. SCHED-COMP-016's directly randomized 12-JVM straight-line scoreboard benchmark found the cached typed ScoreAdd callback used **−8.923 signed log-%** CPU versus the native callback (~8.5% ordinary relative CPU) on the exact synthetic workload.
2. The complete, recovered SCHED-COMP-018R2 full-event native Vein Miner study found **+0.7831% median Server-thread CPU** for cached ScoreAdd versus compiler optimizers off; exact 97.85%-coverage interval **[−9.1110%, +8.9656%]**. Real event duration was +0.6941% median, interval [−7.2468%, +7.0526%]. Both placebo intervals included zero, but neither treatment benefit was established. No 15% real-workload gain supported.
3. The real Vein Miner event itself suffered substantial tick lag (typically ~250–310ms/tick in the prior heavy 6×6×6 fixture). Therefore *the absence of an improvement cannot automatically be attributed to the server always running at 20 TPS*. It was not.
4. Plausible hypotheses to distinguish: **Amdahl dilution** (ScoreAdd takes too little of the full-event CPU), **execution reach** (few eligible commands actually run), **mismatched command shapes**, **queue/tick scheduling or non-ScoreAdd work**, and **high host/game noise**. The study may reject some, but cannot magically isolate exclusive CPU without a separate sampling-based profile.

## Scope, protocol and safeguards

Use the exact pinned publisher Vein Miner 5.3.0+26.3 ZIP (SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), Minecraft 26.3 Fabric / Java 25, identical 6×6×6 native playerbot ore-mining event, and unmodified production ScoreAdd semantics. Fixed setup RCON 45-second forceload limit, pre-event 9-second tick stability gate, and 150-second event cap follow completed R2. The same native state tuple and 1,952 queue steps must match across every arm. **These are three independent diagnostic boots, not a randomized CPU performance trial.**

1. **Off CPU reference:** `--compiler-mode off --no-spark --capture-server-thread-cpu`. Requires all 215 ore operations, complete queue drain, valid Server-thread clock, and no ScoreAdd compilation. Used only as an absolute event CPU denominator.
2. **Cached CPU reference:** `--compiler-mode score-add --no-spark --capture-server-thread-cpu`. Exact same event with cached immutable-env override and genuine ScoreAdd specialization. No per-callback or Spark instrumentation. Used only to obtain an independent absolute event CPU scale; **do not calculate a significant off-vs-cached effect from these two unpaired single boots**.
3. **Counted compiled diagnostic:** `--compiler-mode score-add-instrumented --count-command-callbacks --no-spark`. Counts actual per-function ScoreAdd executions and ordinary function-queue leaf callbacks during the real event. Must verify both `queue_score_add_executed_delta=1952` and exact equality between optimized callback counts and the ScoreAdd-executed counter. This mode adds instrumentation and wrappers, so **none of its timings are comparable** with the uninstrumented CPU arms.

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
