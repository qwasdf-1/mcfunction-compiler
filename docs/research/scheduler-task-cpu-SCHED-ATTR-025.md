# SCHED-ATTR-025 — Sparse CPU timing of BuildContexts, ExecuteCommand, CallFunction and ContinuationTask

**Status:** First three-arm native sparse CPU-time screen **completed and passed the preregistered mechanism/host/sample-integrity gates on 2026-11-17**. The estimates are descriptive, inclusive, noncausal, and sampling representativeness is not proven. In particular, the two small scheduling-task corrections are near the clock-read floor. This is a deliberately small CPU-attribution diagnostic, **not** a scheduler replacement or a causal optimization benchmark.

## Preceding evidence and scope

The SCHED-ATTR-024 [accepted run #44188671911](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44188671911), raw [artifact #14375507746](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44188671911/artifacts/14375507746), counted **194,017 dequeued actions**, **80,799 BuildContexts**, **58,770 ContinuationTask**, **28,265 ExecuteCommand**, and **26,145 CallFunction** method invocations during exact 215-ore/1952-head-step real Vein Miner work. All named paths have sufficient counts to justify targeted sampling. They are **method-entry counts only**, not CPU times or a proven exclusive category partition.

SCHED-ATTR-023's every-entry nested clocks yielded a **0.96% raw queue-minus-entry residual**, smaller than its ~321 ms timer-overhead sensitivity. Do **not** repeat ~200,000 CPU clock pairs or identify almost all Server-thread CPU with queue bookkeeping.

## Locked protocol before native measurement

Run exactly **three independent fresh Minecraft 26.3 Fabric + Java 25 JVMs**, using the **same publisher Vein Miner 5.3.0+26.3 ZIP**, SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`, identical real player-bot ore-mining event, fixed world seed, and **normal cached typed ScoreAdd** in all arms:

1. **PLAIN / off:** opt-in SCHED-ATTR-024 method-entry counters and exact `fc_sched_path begin/end` event scope, no per-task clock reads. Provides an independent Server-thread CPU reference and verifies source path exposure.
2. **EMPTY control:** exactly the same census and event scope, plus a deterministic **1-in-32** pseudo-random selection of each task type's invocation ordinals. At *selected* method HEAD, read current-thread CPU time twice consecutively and accumulate the empty clock-pair delta, then perform the original method unchanged.
3. **TIMED tasks:** same predetermined per-type ordinal-hash selection and rate; at a *selected* method HEAD read one CPU clock and at its RETURN read the other, recording the inclusive task execution span. Unsampled method invocations perform no CPU-clock reads.

The four independent streams are `BuildContexts.execute`, `ExecuteCommand.execute`, `CallFunction.execute` and `ContinuationTask.execute`, **targeting typed JVM descriptors only** (the 26.3 continuation task has `execute(ExecutionContext,Frame)V`; the earlier wrong guessed three-arg target failed before mining and is preserved in SCHED-ATTR-024). The sampler uses one hard-coded per-path ordinal salt and a stable mixing function to avoid simple modulo-32 alignment with periodic queue steps. It is **not a proof of random representative workload sampling**: task cost may correlate with invocation ordinal and differ across independent JVMs.

No JFR, Spark, phase timers, scheduler architecture counters, ordinary command callback metrics, or other CPU probes. Every arm records the exact SCHED-ATTR-024 event-window counters and Linux /proc Server-thread CPU/host quality. A method's TIMED inclusive interval may include another task's work; **never sum different method's projected shares as though exclusive**. The instrumentation is off unless explicit process environment variables are set. Production optimization defaults remain unchanged.

## Preregistered integrity and quality gates

All three boots must satisfy the locked publisher ZIP hash, exactly **215 ore operations**, **1,952 queue-head advances**, original source/marker/run state, stable pre-event tick gate, valid Server-thread `schedstat` running CPU, zero sampled cgroup throttling, and max 25% Server-thread runqueue delay. **No restart after mining begins**; preserve all failures. The final `fc_sched_path end` RCON command is within the census/clock window before CPU time closes, making the diagnostic wider than the ordinary mining-only window.

In each enabled arm, verify supported/active current-thread CPU clock, same Java Server thread, no negative duration, zero nested same-type sampling, no leaked per-task depth after the event, and exactly matching task census-entry counts. For **each of four task types**:
- At least **5,000** real method calls and **200** clocked calls per enabled arm; sampled count within **±25%** of expected calls/32.
- EMPTY vs TIMED total call counts differ by no more than **10%**, and their sampled counts by no more than **15%**.
- Timed zero-delta fraction ≤**20%** for a method to have an interpretable corrected mean (otherwise report that path as **inconclusive clock floor**, not zero CPU).
- Every CPU sum nonnegative and ≤the same arm's independent Server-thread running CPU.
- The TIMED entire event Server-thread running CPU may differ from PLAIN by at most **30%**. This is a coarse perturbation/host-variability veto, not a statistical overhead estimate.

An invalid native arm, missing stream, or severe host/CPU quality failure means no accepted three-arm study. A path's negative signed control subtraction or high clock-resolution zero floor is an **inconclusive path**, not grounds to delete its observations or claim speedups.

## Analysis and interpretation

For each of the four named paths **separately**:

`C = empty_arm_sampled_cpu_ns / empty_arm_sample_count` (mean two-read control).

`T = timed_arm_sampled_cpu_ns / timed_arm_sample_count` (mean bracketing interval including the real method).

`D = T - C` **signed**, never clamped.

`P = D × timed_arm_total_method_calls / timed_arm_Server_thread_cpu_ns` is a *descriptive extrapolated inclusive CPU fraction*, under the unproven assumption that selected method calls represent all method calls. Record all call counts, per-stream samples, raw nanos, zero deltas, native CPU total, and computed signed estimates. **Do not sum P across methods**: `CallFunction` may invoke continuation scheduling, `BuildContexts` can initiate or nest other command work, and the hook scopes may overlap in ways not excluded by the separate per-method non-nesting gate.

`D` is **not** exclusive scheduler overhead, the cost saved by fusion, the cost saved by a direct scheduler backend, or an empirically proven speedup. The two arms use independent JVMs with different JIT/host variance and potentially different command mix; an empty two-clock interval does not capture all Mixin/counter overhead or the timing scope's effect on JIT. Nanosecond precision does not ensure nanosecond CPU-clock accuracy. This screening has one JVM per arm and no confidence interval.

A large inclusive method cost should lead to a *separate* within-method decomposition/semantic validation before authorizing a production optimization. A small measured cost in one method does not rule out context-building or gameplay elsewhere. No broad 30-server campaign or replacement scheduler is authorized by this study.

## Files and execution

The 024 branch is the required base: `SchedulerPathCensus`, four typed task Mixins, `fc_sched_path` commands, and the native event window. This research branch adds:
- `SchedulerTaskCpuProbe.java`: deterministic 1/32 selected CPU-clock mode and four independent counters, with fail-closed runtime checks.
- HEAD/RETURN sampling in four existing typed task Mixins. Compiled `SchedulerPathCensus` still counts every call in *every* arm.
- `ProbeStatus` and `run_veinminer_profile.py --scheduler-task-cpu-probe` for independent event-scoped raw status/count verification.
- `scripts/ci_scheduler_task_cpu.py`, `tests/test_scheduler_task_cpu*.py`, `SchedulerTaskCpuProbeContract.java`.
- `.github/workflows/research-scheduler-task-cpu.yml` (temporary PR trigger for only the initial validation, later returned to manual-only). Original records under `build/benchmarks/SCHED-ATTR-025` plus three native result directories.

**Stop rule:** If any Mixin target fails or event/counter parity fails, preserve the failed run and fix the measurement mechanism before considering another dataset. Do not loosen the 1/32 selection, sample-count or host rules post hoc to manufacture a favorable CPU estimate.

## Completed three-arm sparse sampling — 2026-11-17

**Authoritative run:** [GitHub Actions #44190487217](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44190487217), **success**. The original [raw artifact #14377425739](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44190487217/artifacts/14377425739) contains the complete three-arm `SCHED-ATTR-025/diagnostic.json`, native `results.json`, idle tick baselines, startup records and original stdout/stderr. The JDK 25 Java mode/clock contracts, Python analysis tests, Minecraft Fabric build, exact publisher ZIP hash, three native workload events, and host/clock-quality gates all passed.

Every boot produced **215 ore operations, 1,952 queue-head advances**, the identical final source/block/marker/scoreboard state, and exact cached ScoreAdd activation. Native pre-event average tick time was 5.5–5.6 ms; P95 7.2–7.7 ms; all passed idle stability. No cgroup throttling occurred. Server-thread runqueue-wait fractions were **0.197%, 0.136%, 0.206%** in PLAIN, EMPTY and TIMED. No JFR, Spark or other command instrumentation was active.

| Arm | Actual event completion | Server-thread running CPU | Execution-task CPU clock mode |
|---|---:|---:|---|
| PLAIN | 14.3305 s | 12.7942 s | No CPU reads, same event path census |
| EMPTY | 14.6263 s | 13.1008 s | 1/32 sample with two adjacent CPU reads |
| TIMED | 14.7293 s | 13.1802 s | 1/32 sample with two CPU reads bracketing real task |

TIMED vs PLAIN Server-thread CPU differed by **3.016%**, under the preregistered 30% *coarse perturbation/host* veto; these are independent JVM boots and this **is not evidence of a causal instrumentation penalty**.

### Per-task sampled CPU observations

| Method path | EMPTY calls / samples | TIMED calls / samples | Mean EMPTY clock pair | Mean TIMED inclusive interval | **Signed difference D** | Descriptive projected *inclusive* share of timed Server-thread CPU |
|---|---:|---:|---:|---:|---:|---:|
| **BuildContexts** | 80,799 / 2,512 | 81,127 / 2,523 | 817.73 ns | 59,935.01 ns | **59,117.27 ns (59.1 µs)** | **36.388%** |
| **ExecuteCommand** | 28,253 / 872 | 28,374 / 872 | 785.11 ns | 267,586.02 ns | **266,800.90 ns (266.8 µs)** | **57.436%** |
| CallFunction | 26,145 / 786 | 26,167 / 788 | 955.12 ns | 1,121.26 ns | 166.14 ns (0.166 µs) | 0.033% |
| ContinuationTask | 58,770 / 1,802 | 59,085 / 1,814 | 724.17 ns | 888.93 ns | 164.76 ns (0.165 µs) | 0.074% |

All four task types had **zero timed zero-delta samples**, **zero same-type nesting**, **zero leaked scopes**, correct thread identity and matching per-path census counts. EMPTY and TIMED method-call and sample-count differences were within the frozen limits. Every path passed the *declared basic clock gate*, and the three independent native boots passed the exact-workload and host-quality gates.

### Scientific interpretation and critical precision qualifications

**The material diagnostic signal is in `BuildContexts` and `ExecuteCommand`.** Their sampled inclusive spans are tens to hundreds of microseconds, far above the ~0.8 µs clock-pair control. The descriptive extrapolations suggest a large portion of real event CPU happens inside these two task methods. This is consistent with SCHED-ATTR-023 locating much of execution CPU inside dequeued queue entries. **It does not establish which portion is unavoidable game-state work or avoidable compilation/scheduling overhead.**

**`CallFunction` and `ContinuationTask` are *near the clock-resolution/control subtraction floor*.** Their 0.165–0.166 µs signed corrections are less than **one quarter** of their respective 0.724–0.955 µs empty clock-pair means. A zero observed zero-delta fraction only proves the clock intervals themselves were detectable; it does **not** make the much smaller difference between independent JVMs precise. Their projected sub-0.1% CPU shares should be presented as **exploratory, not reliable estimates of tiny exclusive method cost or hard ceilings**. The original analysis program's `clock_resolved=true` flag means *only* its preregistered basic positive-sign/zero-delta check passed; it is **not** a demonstrated precision floor or an empirical confidence interval.

**None of these four percentages may be added to construct a disjoint CPU histogram** without first verifying exclusive stack nesting and coverage: sampled `BuildContexts` and `ExecuteCommand` intervals can include nested work, and methods may run different amounts of actual gameplay work. The 1/32 deterministic ordinal-hash selection was frozen before results, but **its representativeness has not been empirically established** (periodicity and variance within method call types can skew the extrapolation). Only one independent JVM per arm was measured, so no rigorous interval or causal optimization gain exists. The PLAIN, EMPTY and TIMED CPU totals are not a randomized compiler A/B comparison, and the additive method-share fractions are **not** an Amdahl-law ceiling on a future scheduler/backend.

**Decision:** Further work should prioritize *inside* `BuildContexts` (modifier/source expansion, creating `ExecuteCommand` tasks) and then *inside* `ExecuteCommand` (Brigadier `ContextChain.runExecutable`, command callbacks, actual world/scoreboard/NBT operations). Keep result/exception/selector semantics, quota debits, and vanilla fallback. **Do not promote** the restricted SCHED-ARCH-014 direct scheduler or build a global `ExecutionContext` rewrite on the strength of these inclusive timings. Distinguishing dispatch cost from real command mutation requires a new separately preregistered within-method mechanism study, not another generic CPU benchmark.

The dedicated workflow was restored to **`workflow_dispatch` only** after the accepted run. This remains a draft, stacked research PR (depends on SCHED-ATTR-024), with no production optimization default changes and no claim about installed-but-disabled instrumentation overhead.
