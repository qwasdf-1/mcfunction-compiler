# SCHED-COMP-022 — calibrated typed ScoreAdd Server-thread CPU time

**Status:** Implementation and preregistration on the isolated `research/sched-comp-022-threadmxbean-cpu` branch; **no real results yet**. This is a **mechanism/measurement diagnostic**, not a causal speedup experiment and not a production optimization.

## Motivation and inherited evidence

- [SCHED-COMP-020](scoreadd-command-share-SCHED-COMP-020.md) established **11,124 successful direct typed ScoreAdd callbacks** in its *separately instrumented* native Vein Miner event. The global family scoreboard counter is **not** a direct-ScoreAdd count, and the 241.47 µs per successful callback needed for 15% whole-event saving was a **counterfactual budget**, not a measured operation cost.
- [SCHED-COMP-021](scoreadd-jfr-cpu-SCHED-COMP-021.md) attempted experimental JDK 25 `CPUTimeSample` and failed its 5% lost-sample cap at 5, 10 and 20 ms. Some captured stacks were safepoint-biased. Those rejected traces may be inspected *exploratorily only*. Do **not** inherit their fractions as measurements.
- Java 25's `ThreadMXBean.getCurrentThreadCpuTime()` returns CPU time for the *calling platform thread*. The value is in nanoseconds **precision but not necessarily accuracy**; it can be unsupported or disabled. This protocol fails closed if the clock is not active, rather than activating an inconsistent probe partway through a run.

## Preregistered experiment (independent same-workload boots)

All arms use the same exact publisher Vein Miner 5.3.0+26.3 ZIP (SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), Minecraft 26.3/Fabric/Java 25, identical fixed-seed native 6×6×6 playerbot mining with **215 work operations** and **1,952 queue-head advances**, and **normal cached ScoreAdd** (`--compiler-mode score-add`). Native CPU accounting uses Linux `/proc` Server-thread running CPU time. The 9-second pre-event idle stability gate and existing host-quality gate apply to every boot.

Run three independent boots, in the predetermined order:

1. **plain**: `FC_SCORE_ADD_CPU_PROBE=off`, ordinary cached typed callback, no clock reads per command. Reference for whether instrumentation materially changes total event CPU (unpaired and noncausal).
2. **empty_control**: `FC_SCORE_ADD_CPU_PROBE=empty`. At each typed `ScoreAddCommand.run` entry, two *consecutive* `ThreadMXBean.getCurrentThreadCpuTime()` calls are accumulated *before* running the original callback, using the same per-call aggregator as the timed arm. This exposes the clock-read floor and counter overhead.
3. **timed_callback**: `FC_SCORE_ADD_CPU_PROBE=timed`. The same two clock reads bracket the original `runUntimed`, including scoreboard mutation, feedback and any nested work. An exception still closes the timer. Count successfully completed **direct** scoreboard mutations separately; vanilla-delegated fallbacks are not direct successes.

All other callback metrics, shared family execution counters, wall-clock phase timers, Spark and JFR are disabled. The mode is process-immutable and never set by ordinary runtime config. Neither a timer nor a counter is required on the default/off path. Read probe totals through `function_compiler_probe status` just before intervention and after exact event completion; use **counter deltas**, not cumulative JVM lifetime totals. Record timer zero-deltas, callback entries, direct success count, enabled-clock status, exact immutable publisher SHA-256, initial/final native state, per-event /proc CPU totals, and host diagnostics.

## Preregistered validity and analysis

A run is invalid if any native event fails exact parity, publisher hash, compiled queue command count **4**, stability or CPU host-quality gate, or if an enabled clock is unsupported/disabled, if probe thread changes, if an enabled arm has fewer than **1,000** typed entries, direct successes do not equal typed entries, aggregate probe timing is negative or exceeds its own native Server-thread CPU total, or the instrumented entry counts disagree by more than **10%** across the independent boots.

For a valid three-boot diagnostic, let:
- `C = total clock-interval CPU ns in empty_control / its callback entry count`
- `T = total bracketed CPU ns in timed_callback / its callback entry count`
- `D = T - C` (retain **signed** result; do not silently clamp negative to zero)
- `f = (D × timed_callback entry count) / timed_callback native Server-thread CPU ns`

Treat `D` as an **overhead-controlled diagnostic estimate**, not an exact method CPU time. Only label it *interpretable* when `D > 0` and no more than **20%** of timed samples have zero CPU-clock delta; report a negative or unresolvable estimate as **inconclusive**, not as evidence of zero cost. Preserve raw totals, per-arm fractions, and all three native results. Note that the direct-success diagnostic counter is inside the timed callback's bracket but outside the empty clock-read interval, so its overhead biases the estimated cost **upward**.

A 15% whole-event saving **cannot** be inferred simply because `f ≥ 15%`; the config-cache change only removes a subset of work within the typed callback. Conversely, a clearly small `f` is evidence against the idea that *eliminating this entire typed callback subtree* could achieve a large overall reduction under these assumptions. No statistical confidence interval or causal treatment effect is claimed from three independent boots, and no part of this campaign is a 30-event performance test.

A clock with nanosecond **precision** but insufficient effective resolution, overly expensive overhead, noncomparable callback counts, or unstable host means: **stop, report incomplete, and revisit the measurement design**. Do not tune a threshold post hoc to obtain a favorable conclusion.

## Files and execution

- `src/main/java/dev/functioncompiler/ScoreAddCpuProbe.java`: fail-closed, opt-in clock with `off`, `empty`, `timed` modes.
- `ScoreAddCommand.run`: research clock bracketing around original `runUntimed`, without changing command outcomes.
- `ProbeStatus.status`: explicit clock/entry/success/delta counters, queried outside the event's timed region.
- `scripts/run_veinminer_profile.py`: `--scoreadd-cpu-probe` and exact native event /proc CPU monitoring.
- `scripts/ci_scoreadd_cpu_timing.py`: three-arm independent-boot driver and comparison.
- `tests/test_scoreadd_cpu_probe.py`, `tests/test_scoreadd_cpu_timing.py`: standalone Java contract and analysis tests.
- `.github/workflows/research-scoreadd-threadmxbean-cpu.yml`: isolated optional CI diagnostic with original native JSON and logs archived.

**Decision gate:** After verified CI and all three native work/callback gates, examine `D`, `f`, the control's mean overhead, and each arm's total Server-thread CPU before choosing any new optimization. Leave ScoreAdd's production default off and the unrelated research campaigns manual-only.

**API reference:** [JDK 25 ThreadMXBean CPU time](https://docs.oracle.com/en/java/javase/25/docs/api/java.management/java/lang/management/ThreadMXBean.html).
