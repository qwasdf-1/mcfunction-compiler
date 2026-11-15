# SCHED-COMP-021 — Server-thread CPU-time attribution for Vein Miner

**Status:** Implementation committed; CI blocked before runner startup (no native measurements yet). Preregistered follow-up to the completed [SCHED-COMP-020 execution-coverage diagnostic](scoreadd-command-share-SCHED-COMP-020.md). **Diagnostic only; no implementation or performance claim.** Source branch: `research/sched-comp-021-jfr-cpu-attribution` (merged into `main` 2026-11-15).

## Why this experiment is distinct

SCHED-COMP-020 observed **11,124 successful typed ScoreAddCommand callbacks** in its independently instrumented event, but the global shared family counter (26,206) and direct Brigadier wrapper count (10,485) measure different execution domains. CPU-saving requirements calculated there (**241.47 µs per callback** for 15% whole-event saving relative to its compiler-off CPU reference) were **counterfactual, not measured callback times**. Those counts do not transfer unchanged to new JVM boots.

In contrast, Spark's legacy execution sampling is a **wall-clock execution stack sampler** and cannot reliably establish how much of the *on-CPU Server-thread* is spent inside the specialized callback. Use **JDK 25's Linux experimental `jdk.CPUTimeSample`**, enabled explicitly in a separate test-only JFR recording; never substitute `jdk.ExecutionSample` or whole-server /tick for CPU-time attribution.

## Exact preregistered protocol

- Same pinned Minecraft 26.3 / Fabric / Java 25 setup and **publisher Vein Miner 5.3.0+26.3 ZIP** SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e` used in 020.
- Exact native 6×6×6 playerbot mining scenario with **215** completed work operations, **1,952** queue-head advances, identical final source/ore/marker state, 45-second setup forceload timeout, 9-second idle stability gate and 150-second event completion cap.
- **Two independent, unpaired server boots:** `off_jfr` (`--compiler-mode off`) and `cached_jfr` (`--compiler-mode score-add`). Both use `--no-spark --capture-server-thread-cpu --capture-jfr-cpu`. The latter uses normal cached ScoreAdd with no added callback counters. No production configuration change.
- Start JFR **after** native workload setup and idle-stability gate, before the first mining packet; stop immediately after the event's /proc Server-thread CPU window closes. Recording includes short boundary overhead (JFR start-to-first-packet and final RCON completion observation), which cannot be claimed as pure ore-execution CPU.
- Launch `jcmd JFR.start` on the **actual Minecraft JVM child**, not Gradle, with `jdk.CPUTimeSample#enabled=true`, `jdk.CPUTimeSample#throttle=5ms` and `jdk.CPUTimeSamplesLost#enabled=true` (disable generic `jdk.ExecutionSample`). Archive the original `.jfr` and its SHA-256, full native event manifests, setup/host-quality results, stdout/stderr and aggregate report.
- Resolve `eventThread.osThreadId` to the exact thread ID identified via Linux `/proc/<pid>/task`; never include other threads or substitute thread-name-only matches.
- Reject empty/unsupported CPU sampler, fewer than **150 valid Server-thread CPU samples**, **more than 10% failed/stackless** Server-thread events, **more than 5% lost** Server-thread CPU samples, invalid /proc CPU identity, host-quality failure, mismatched publisher file, unstable pre-event baseline or different native final states.
- Classify each **valid CPU-time sample exactly once** based on the stack, first match wins, in this precedence order (**amended 2026-11-15 before any data; see [Protocol amendment](#protocol-amendment--classification-precedence)**): typed `ScoreAddCommand` (including its descendant work); other named specialized compiler callbacks; vanilla scoreboard; execute-control; other compiler overhead; function queue/scheduler or nested work; Brigadier; identifiable world-level updates; other Minecraft; other runtime. Record biased samples, counts of failed/lost samples, and the top observed innermost methods. Do **not** add the inclusive method weights from multiple nested frames together.

## Protocol amendment — classification precedence

**Recorded 2026-11-15, before any SCHED-COMP-021 sample was collected** (the only CI attempt was blocked before runner startup, so no trace exists to have informed this change).

The original order placed *function queue/scheduler or nested work* and *Brigadier* before *other compiler overhead*. Compiler command callbacks always execute beneath `ServerFunctionManager` / `net.minecraft.commands.execution.*` and Brigadier dispatch frames, so under first-match classification the *other compiler overhead* category was effectively unreachable: every sample inside an unnamed compiler callback (for example `InlinedFunctionCommand`, or macro specialization in `ProbeFunctionWrapper.instantiate`) would have been counted as scheduler or Brigadier cost. The synthetic contract test asserting that an unnamed compiler frame beneath the scheduler classifies as *other compiler* was failing against the implementation for this reason.

*Other compiler overhead* now precedes *function queue/scheduler* and *Brigadier*. It intentionally stays **below** *vanilla scoreboard* and *execute-control*, so vanilla work reached through a compiler fallback remains attributed to the vanilla command. Typed `ScoreAddCommand` and other named specialized callbacks are unchanged. The amended order is implemented in `scripts/analyze_veinminer_jfr_cpu.py` (`CATEGORIES`, `_category`) and pinned by `tests/test_veinminer_jfr_cpu.py`. All gates, arms and thresholds are unchanged.

## What would constitute evidence?

Define `f = (# valid Server-thread CPU samples whose stack contains ScoreAddCommand) / (# valid Server-thread CPU samples)` in the cached arm.

- `f` estimates the **sampled on-CPU time within the specialized typed callback subtree**, not the share of all commands, and not exclusively the savings obtainable from the config-cache change. It includes mutation, result feedback and descendant operations that optimization may never eliminate.
- Removing *every* operation in that subtree would give an **idealized sampled elimination ceiling** near `f`, under a static-work model. An achievable config-cache improvement is necessarily narrower. If `f` is far below 15%, it strongly suggests that 15% overall CPU saving from only this callback family is not credible. Sampling uncertainty, missing/inlined frames and coverage bias preclude claiming a mathematical hard upper bound on the true CPU share.
- If `f` exceeds 15%, this **does not** establish that the proposed optimization could save 15%, nor that the existing synthetic result carries over: the original saved code path may occupy only a small part of the sampled typed callback subtree.
- Function-scheduler-or-nested samples are **not equivalent to exclusive scheduler overhead**; generic wrapper and unrecognized work can be attributed to this category. The category partition describes the sampled stack, not a cycle-accurate breakdown of inner function dispatch.
- The two profiled CPU totals are **not an A/B estimate**, because two unrelated server boots cannot yield a confidence interval for a production performance gain. A 30-server re-test is deliberately out of scope.

## Implementation and raw results

- `scripts/run_veinminer_profile.py` adds an opt-in event-window JFR capture mode, with no production path changes.
- `scripts/analyze_veinminer_jfr_cpu.py` reads raw `.jfr` via `jfr print --json --events jdk.CPUTimeSample,jdk.CPUTimeSamplesLost --stack-depth 128`; rejects missing or low-quality Server-thread CPU samples and returns uniquely partitioned category fractions.
- `scripts/ci_scoreadd_cpu_attribution.py` drives the two independent boots and enforces native-workload and artifact parity.
- `tests/test_veinminer_jfr_cpu.py` checks stack categorization, independently counted samples, thread identity, failure/loss gates, and cross-arm parity.
- `.github/workflows/research-scoreadd-jfr-cpu.yml` builds and runs the two-boot diagnostic and uploads original raw traces under `build/benchmarks/SCHED-COMP-021/` plus native event directories. The historical 30-event R2 workflow is manual-only on this research branch to prevent unintentional repeat campaigns.

**Decision gate:** Do not change the cached ScoreAdd optimization or rerun an expensive performance campaign solely because of a stack fraction. Use the measured distribution first to decide whether to optimize per-callback behavior, scheduler overhead, or something else entirely.

**References:** [JDK 25 experimental CPU-Time Sampling](https://openjdk.org/jeps/509), [Java 25 JFR event definitions](https://sap.github.io/jfrevents/25.html), [JDK 25 `jfr print` JSON options](https://docs.oracle.com/en/java/javase/25/docs/specs/man/jfr.html).

## CI execution status, 2026-11-15

The PR-triggered dedicated workflow [run #43742409829](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43742409829) failed within seconds of creation and returned an Actions job with **no steps** or retrievable job log (log endpoint returned BlobNotFound). [Run #43742579265](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43742579265) on the subsequent analyzer revision likewise failed with **no runner steps**. A retry of its job also failed before any steps began. Because no checkout, unit test, build, Java 25 process, JFR capture or native Minecraft event occurred, **none of these CI failures can establish whether the code or sampling experiment would pass**. The underlying GitHub Actions startup failure has not been diagnosed and may require repository/runner-level inspection.

**No SCHED-COMP-021 sampled CPU fraction exists yet.** Leave all performance conclusions unchanged and keep this PR in draft until a real runner execution provides archived traces and validated reports. Triggering or rerunning the dedicated workflow is the remaining execution step; do not substitute counts from SCHED-COMP-020 or other boot profiles.
