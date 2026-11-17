# SCHED-COMP-022 — calibrated typed ScoreAdd Server-thread CPU time

**Status:** First three-arm native diagnostic **complete and accepted against its preregistered mechanism/measurement gates** on 2026-11-17. This establishes a descriptive overhead-controlled CPU-time estimate, not a statistical or causal optimization result. This is a **mechanism/measurement diagnostic**, not a causal speedup experiment and not a production optimization.

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

## Completed first native diagnostic — 2026-11-17

Dedicated [GitHub Actions run #44169241336](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44169241336) **passed** the Java mode/clock contract, Python calibration-contract tests, Minecraft 26.3 Fabric Gradle build, pinned Vein Miner ZIP SHA-256, all three real native events, exact native-state parity, probe gate, and artifact archive. [Raw artifact #14367636370](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44169241336/artifacts/14367636370) includes `SCHED-COMP-022/diagnostic.json`, stdout/stderr for all arms, startup readiness records, and the three complete native event results.

**All three independent boots:** 215 completed work operations; 1,952 queue-head advances; source ore removed; 0 remaining ore; 0 operation or target markers; correct publisher hash; stable pre-event idle tick gate; valid Server-thread /proc CPU and host-quality gates; 4 compiled queue/drain ScoreAdd callbacks in each; no old shared ScoreAdd metrics, callback wrappers, Spark or JFR.

| Arm | Event elapsed | Server-thread CPU | Typed callback entries | Direct successes | CPU between probe clocks | Zero CPU deltas |
|---|---:|---:|---:|---:|---:|---:|
| `plain` | 14.577 s | 13.018457228 s | *Not instrumented* | *Not instrumented* | — | — |
| `empty_control` | 14.333 s | 12.791600217 s | 11,400 | 11,400 | 7,922,482 ns | 0 |
| `timed_callback` | 14.514 s | 12.960433236 s | 11,010 | 11,010 | 25,023,600 ns | 0 |

Instrumented exposure differs by **390 / 11,400 = 3.421%**, inside the declared 10% threshold; all instrumented entries completed the direct typed path. Both had zero samples with a zero-duration CPU-clock delta; the 20% timed zero-floor threshold passed.

**Predeclared control subtraction:**
- Back-to-back clock cost: **694.955 ns per control callback**.
- Two-clock bracket including real typed callback: **2,272.807 ns per timed callback**.
- Difference **D = 1,577.852 ns (1.578 µs) per callback**.
- Projected callback contribution in the timed run: **D × 11,010 = 17.371 million CPU ns**, or **0.13404%** of that same run's **12.9604 billion Server-thread CPU ns**.

The earlier [SCHED-COMP-020](scoreadd-command-share-SCHED-COMP-020.md) **241,470 ns** average saving needed *per eligible callback* for 15% whole-event improvement was an Amdahl counterfactual, not a measured saving. This study's overhead-controlled **1,578 ns total callback CPU** estimate is ~153× smaller, suggesting the originally sought whole-event speedup is implausible **from optimizing only this narrow ScoreAdd callback family** in this workload. This comparison cannot establish a universal upper bound or test the potential benefit of wider scheduler/command-queue optimizations.

**Interpretation limits:** This is *one run per independent boot*, not a paired treatment experiment. Clock resolution, per-mode JIT state, background CPU, exact callback exposure and direct-success counter overhead can bias `D`; the empty and timed event totals are not direct causal comparisons. The direct-success increment occurs inside the timed interval but outside the control interval, introducing slight **upward** bias. The callback includes scoreboard mutation, feedback and descendants; **the config-cache flag lookup is only a subset**, so `D` is not the CPU saved by the existing cache. The fraction is a descriptive estimate of native Server-thread CPU for this exact 215-operation Vein Miner scenario, not a confidence interval, universal Minecraft claim or time share of all Minecraft servers.

**Research decision:** The mechanism diagnostic reached its intended validity gate and strongly points away from the typed ScoreAdd callback as the high-impact optimization target. Leave ScoreAdd's disabled-by-default production configuration unchanged. Future performance attribution should target the broader function scheduling/queue and modifier execution path with independently validated controls, rather than trying to extract a 15% CPU benefit solely from the narrow typed ScoreAdd callback. The temporary PR trigger was removed and the dedicated research workflow restored to manual-only after this completed run.

## Unplanned exploratory repeat — 2026-11-17 (not part of the preregistered first campaign)

A documentation-only PR update before restoration of dispatch-only research workflow inadvertently triggered [Actions run #44170251809](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44170251809). The repeat ran the **same pre-registered three-arm code and fixed acceptance gates**, but it was **not planned as a confirmatory repetition or statistical sample**. It independently passed the unit tests, full Fabric build, pinned publisher ZIP and all three exact native event/host/CPU and callback exposure gates. [Raw artifact #14368146540](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44170251809/artifacts/14368146540) contains the second complete set of JSON event records.

| Metric | First completed diagnostic | Exploratory repeat |
|---|---:|---:|
| Plain arm Server-thread CPU | 13.0185 s | 12.6887 s |
| Empty-control Server-thread CPU | 12.7916 s | 13.7772 s |
| Timed Server-thread CPU | 12.9604 s | 12.8452 s |
| Empty-control typed callbacks | 11,400 | 11,010 |
| Timed typed callbacks | 11,010 | 11,048 |
| Control clock interval/callback | 694.95 ns | 674.48 ns |
| Timed clock bracket/callback | 2,272.81 ns | 1,967.06 ns |
| **Signed difference D** | **1,577.85 ns** | **1,292.58 ns** |
| **Descriptive CPU share f** | **0.13404%** | **0.11117%** |
| Timed zero-delta fraction | 0% | 0% |
| Diagnostic quality decision | Accepted | Accepted |

Both runs completed 215 work operations / 1,952 queue steps in every arm, and both accepted timed arms had all typed callback entries complete the direct-success path. The difference between the first and exploratory repeat is compatible with JVM/host and runtime variability; neither run had within-boot randomized pairing. The **observed range (1.29–1.58 µs per callback; 0.111–0.134% of total Server-thread CPU)** is descriptive, **not** a confidence interval or a bound on a production optimizer. Unpaired whole-event CPU totals were not used to calculate speedup.

The dedicated workflow is now **manual-only**, so subsequent documentation edits cannot automatically schedule new CPU experiments.
