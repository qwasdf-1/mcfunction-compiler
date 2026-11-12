# SCHED-NOISE-005 — Same-binary A/A calibration and GC-worker discovery

**Experiment:** 2026-11-12  
**Status:** Completed; build and tests passed; all 20 JVM boots and 80 timed windows completed with exact scoreboard integrity. **Predeclared calibration and quality gates failed.**  
**Decision:** Current GitHub-hosted fresh-JVM protocol is not qualified to resolve small compiler effects. The dominant observed anomalies correlate with **concurrent JVM GC-worker activity in BOTH test stacks**, not uniquely with the compiler mod.

## Research question and motivation

The [SCHED-HOOK-004](scheduler-hook-overhead-SCHED-HOOK-004.md) experiment reduced within-JVM scoreboard timing drift from 16.6% to 1.27% using bounded warmup and adjacent timed windows. However, between-JVM overhead remained extremely variable: a +3.82% paired median with a broad −1.05% to +27.30% interval, 8/10 quality-qualified pairs and several slow boots accompanied by run-queue delay.

Before attributing this to code or external CPU contention, run the same A/B analysis against **A/A pairs where there is no code difference**. The two independently calibrated runtime stacks are Fabric+API only and Fabric+API+the complete compiler JAR with all optimizations disabled. The study tests the measurement system's false-effect floor, **not the true effect of installing the compiler**.

## Fixed preregistration and implementation

- Script: [\`scripts/ci_noise_aa_calibration.py\`](../../scripts/ci_noise_aa_calibration.py).
- Reusable Linux/JVM telemetry: [\`scripts/benchmark_noise_telemetry.py\`](../../scripts/benchmark_noise_telemetry.py).
- Synthetic contracts: [\`tests/test_noise_aa_calibration.py\`](../../tests/test_noise_aa_calibration.py).
- Dedicated CI: [\`.github/workflows/research-noise-aa.yml\`](../../.github/workflows/research-noise-aa.yml).
- **Pre-measurement commit:** \`96006507d1ea86f441922722ec449af05033a6ff\`.
- **Verified successful run:** [GitHub Actions 43273896651](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43273896651). Artifact: **\`sched-noise-005-aa-raw\`**, including \`results.json\` (~770 KB) and all 20 server logs. Artifacts expire under Actions retention policy; preserve a ZIP copy elsewhere for permanent reference.
- Environment: Java 25, Minecraft 26.3, pinned Fabric Loader 0.20.1 and Fabric API 0.165.0+26.3, production server launcher, same JVM flags, exact same datapack/function text for both arms of every pair. All compiler optimization and tracing flags off. JAR SHA-256 values and fixed settings are recorded in JSON.

The study predeclared 10 adjacent same-binary pairs, with five Fabric/Fabric and five compiler-off/compiler-off comparisons interleaved and the time-order labels counterbalanced. For each JVM: identical three-family prewarm, 6–18 fixed scoreboard qualification windows until the specified 4-window plateau criterion (6% individual deviation / 4% trend), then two adjacent scored CPU windows and two conditional controls.

**Primary measurement:** Linux **server-thread running CPU** nanoseconds per verified \`.mcfunction\` source line. The environment monitor snapshots process CPU, per-surviving-thread CPU categorized as compiler/GC/server/other, run-queue wait, cgroup throttling, CPU pressure and affinity. No JFR runs during timed windows; environment snapshots bracket rather than occur inside the inner timed command CPU clock.

**Null screening targets (predeclared):** median absolute paired effect ≤3%, 90th-percentile absolute paired effect ≤8%, and maximum absolute paired effect ≤12%, with no failed-quality pairs. These are pragmatic **screening** criteria, NOT a confidence guarantee of detecting a 5% change; the total sample is just ten pairs and each stack has five.

All pair labels, warmup failures and outliers are retained. A failed quality gate overrides any favorable central estimate.

## Verified workload and results

- 20 separate production JVM boots; 10 identical-binary A/A pairs.
- 80 timed windows; **192 million exact-checked timed source lines**.
- 96 million prewarm source lines, plus qualification windows (all exact-checked).
- **17/20** JVMs qualified on the predeclared warmup plateau.
- **6/10** pairs passed all quality gates; failed pairs **4, 7, 8 and 9**.
- All timed exact-state parity checks passed.
- **Zero observed cgroup CPU-quota throttle events** in timed windows.

### Primary negative-control distribution

| Metric | A/A observation |
|---|---:|
| Median absolute apparent effect, pooled 10 pairs | **4.831%** |
| 90th percentile absolute apparent effect | **20.152%** |
| Maximum absolute apparent effect | **20.927%** |
| Pooled blinded signed median | −1.962% |
| Conservative exact signed-median interval (97.85% coverage) | −18.188% to +5.422% |
| Fabric/Fabric median absolute apparent effect, 5 pairs | 5.422% |
| Compiler-off/compiler-off median absolute apparent effect, 5 pairs | 3.816% |
| Predeclared verdict | **\`inconclusive_quality_gate\`** |

The signed distribution is only a diagnostic: both labels point to **identical** code, and the interval legitimately includes zero. With only five observations per stack, the independent stack statistics are descriptive, not reliable estimates of their population variance.

### All A/A pairs

The *first-to-second* percentage below uses the first boot as denominator. The primary null-analysis script also assigns balanced A/B labels, so the corresponding maximum absolute **blinded** percentage is 20.93%, not the 26.47% first-to-second percentage (percent changes are not symmetric under inversion).

| Pair | Identical stack | First → second CPU change | Quality gate |
|---:|---|---:|---|
| 1 | Fabric-only | +4.24% | Pass |
| 2 | Compiler-off | +3.97% | Pass |
| 3 | Compiler-off | +2.35% | Pass |
| 4 | Fabric-only | **+26.47%** | **Fail** |
| 5 | Fabric-only | −5.14% | Pass |
| 6 | Compiler-off | −1.57% | Pass |
| 7 | Fabric-only | **+11.53%** | **Fail** |
| 8 | Compiler-off | **−18.19%** | **Fail** |
| 9 | Compiler-off | **−16.77%** | **Fail** |
| 10 | Fabric-only | −2.36% | Pass |

These results categorically falsify the assumption that a large apparent CPU difference in fresh JVMs must indicate a different Minecraft command or compiler implementation.

## Main mechanistic finding: concurrent GC-worker CPU

The new per-thread telemetry revealed a strong, previously unmeasured pattern. Three slow JVMs — **Fabric boot 7, compiler-off boots 14 and 16** — all spent approximately **343–353 milliseconds of GC-worker CPU per timed scoreboard window**. The remaining 17 JVMs' GC-worker CPU averaged only a few milliseconds.

| Per 1,600-call timed scoreboard window / boot metric | Ordinary boots, n=17 | GC-intensive boots, n=3 |
|---|---:|---:|
| Median GC-worker running CPU per window | **8.921 ms** | **350.563 ms** |
| Range of GC-worker CPU per window | 4.49–11.60 ms | 342.85–352.73 ms |
| Median server-thread scoreboard CPU | 165.472 ns/source line | **203.975 ns/source line** |
| Median server-thread run-queue wait fraction | 0.697% | **4.426%** |
| Warmup qualification passed | 17/17 | **0/3** |

The three high-GC boots spanned BOTH installed-mod configurations, so the phenomenon is **not specific to the compiler mod** in this dataset. They were also the three JVMs that failed warmup qualification (a fourth pair quality failure came from excessive within-boot score drift in Fabric boot 13).

Exploratory correlations across 20 boots:
- GC-worker CPU versus server-thread scoreboard CPU cost: **r ≈ +0.921**.
- GC-worker CPU versus server-thread run-queue wait fraction: **r ≈ +0.975**.
- JIT compiler-thread CPU versus scoreboard CPU cost: **r ≈ −0.060**.

These strong associations do **not** prove that GC caused the server-thread CPU slowdown; GC and the server thread can be affected simultaneously by heap state, system scheduling and memory behavior. However, concurrent GC is now a well-grounded specific hypothesis, unlike the previous generic description of “host noise”. JIT-worker CPU did not exhibit the same association in this limited snapshot sample; that does not prove compilation tiers were identical or JIT state irrelevant.

Per-thread CPU categorization uses Linux \`/proc/<pid>/task/*/comm\` names, which are truncated, and counts **surviving threads** observed at both snapshots. The whole-process CPU counter includes all threads but has coarse tick granularity. The new role totals are informative approximations, not a complete Java GC/compilation event trace.

### Do NOT use post-hoc exclusion as a performance claim

Removing the three high-GC boots after seeing them would make the null distribution narrower, but that would defeat the test's purpose: an A/A calibration must measure how often *the actual protocol* produces these states. These observations remain in all formal paired results, and **the quality verdict remains failed**. To exclude GC by definition, preregister a separate *GC-quiet steady-state* estimand with a GC-specific precondition and report the failed qualifications too.

## What this proves, and what it does not

**Supported:** (1) Even identical production Fabric JVMs can show ~20% false signed performance differences; (2) three of twenty boots exhibited a large, distinctive concurrent GC-worker CPU signal with higher server-thread CPU and scheduler wait; (3) no cgroup-quota throttling events were observed; (4) this host/protocol has not met its declared precision gates for small compiler effects.

**Not supported:** a proven installed-compiler CPU regression; a proven *absence* of installed-compiler overhead; proof the Minecraft vanilla scheduler is or is not the bottleneck; attribution of the GC activity to the mod or GitHub host; or a mathematical technique to “subtract GC noise” from a raw scoreboard CPU time.

This is a measurement methodology finding, not a compiler optimization result.

## Next falsifiable experiment

1. **GC-phase diagnosis**, a new preregistered A/A campaign with per-JVM GC unified logs (\`-Xlog:gc*\`, with explicit assessment of logging overhead), heap occupancy and collection counters, plus the same CPU/GC-worker telemetry. Determine which GC phase explains the 350 ms worker-CPU regime.
2. Run an **explicit GC-behavior factorial diagnostic**, e.g. default G1 vs controlled GC-worker count, on identical Fabric-only binaries; make no production performance inference from a diagnostic GC configuration.
3. Separately report **GC-inclusive whole-JVM/event cost** (where GC induced by an intervention counts) and **GC-quiet steady-state command cost** (where the quiet criterion is predeclared, with failures retained). Do not equate them.
4. If the A/A noise floor remains comparable to the intended target effect, move to a genuinely isolated benchmark host or a safe within-JVM crossover for compilation paths that support it. A shared GitHub-hosted 2-vCPU runner cannot guarantee physical-core exclusivity.

See also [benchmark noise-control standard](benchmark-noise-control-standard-v0.1.md). The study's raw ZIP and logs are required for any follow-on analysis.
