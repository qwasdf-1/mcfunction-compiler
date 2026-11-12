# Noise-control standard for compiler performance research (v0.1)

**Date:** 2026-11-12. **Applies to:** all new Minecraft 26.3 / Java 25 function-compiler performance studies. **Status:** candidate shared research protocol, requiring independent validation per platform and workload.

## The key principle

Noise is not a scalar correction to subtract. Concurrent JIT, GC, kernel scheduling, CPU migration, cache interference and virtual-host contention can influence both elapsed time and **server-thread CPU running time**. Some of these costs may be caused by the compiler and should count in an end-to-end measurement. Define and report the performance question **before** deciding which effects to control.

### Separate estimands

| Estimand | Primary metric | Does GC/JIT count? |
|---|---|---|
| Warm steady-state function CPU | Server-thread CPU nanoseconds per exact, equivalent command/event | Worker CPU not in numerator, but its interference may affect server-thread CPU |
| Whole-JVM CPU efficiency | Total process CPU time over an explicit workload/horizon | Yes |
| Event-completion latency | Elapsed wall-clock until all observable effects complete | Yes, including stalls |
| Sustained game impact | Active MSPT (P50/P95/P99), TPS and work rate | Yes, indirectly |
| Compilation/reload amortization | Startup, reload, compilation and code-cache costs, break-even point | Yes |

Never swap the primary metric in response to results. Never equate CPU time with wall time. Use exact-work checks for callbacks, scoreboard state, command quotas and other relevant Minecraft semantics.

## Mandatory study design

1. **Lock and fingerprint:** source commit, build and server JAR SHA-256, Minecraft/Fabric/API/Java versions, JVM flags, mods, compiler toggles, world seed/gamerules, datapack and function source, quota, host CPU count/affinity and cgroup quota. Do not assume disabled optimization flags remove installed Mixins.
2. **Calibrate with A/A negative controls:** identical binary and settings on both sides, independently for Fabric-only and compiler-disabled stacks. Report all apparent differences and check that the chosen runtime/host can resolve the effect size of interest. An A/A null distribution does not estimate the actual A/B effect.
3. **Pair and counterbalance:** for changes requiring a restart, compare adjacent fresh JVMs in randomized, balanced ABBA/BAAB blocks. For changes safe to switch *within* one JVM, use randomized crossover with reset state and verify no cache or JIT carryover. Never compare all A boots to all B boots with no counterbalancing.
4. **Bounded, verified warmup:** prewarm all relevant command paths, measure fixed CPU qualification windows, and require a declared stable plateau or mark qualification failed at its cap. A CPU plateau alone does not establish equal JIT tier or no concurrent GC.
5. **Measure two categories at once:** primary command/event cost without JFR in timed windows; separate JVM/OS diagnostics before and after windows. Preserve timestamps, precision and unavailable counters.
6. **Keep every result:** retain warmup windows, failed qualification, noisy pairs and aborted attempts. Predeclare failure thresholds. Failed host, semantic or stability gates => **inconclusive**, not a filtered speedup. A post-hoc subset is useful for hypothesis generation only.
7. **Make decisions with uncertainty:** use paired differences and an interval appropriate to sample size. A material regression requires a valid interval above the declared threshold; equivalence requires the entire interval *inside* its declared margin. Low variation in a limited A/A sample is not itself proof of future stability.
8. **Escalate when the host cannot resolve the effect:** do not keep averaging a demonstrably unstable runner until a desired result appears. Use dedicated hardware or an appropriately controlled self-hosted runner; consider pinned affinity, fixed CPU policy and consistent JVM topology where available.

## Required telemetry

The reusable implementation [\`scripts/benchmark_noise_telemetry.py\`](../../scripts/benchmark_noise_telemetry.py) captures:
- Server-thread running and wait CPU nanoseconds from \`/proc/<pid>/task/<tid>/schedstat\`.
- Whole-JVM CPU from \`/proc/<pid>/stat\`, with coarser tick resolution, plus per-surviving-thread CPU by role (\`jit_compiler\`, \`gc\`, \`server\`, other). Linux thread names are truncated and threads can disappear mid-window: **role totals are indicative, not full attribution**.
- \`cpu.stat\` cgroup throttling, system CPU pressure from \`/proc/pressure/cpu\`, host load and process CPU affinity.
- Exact work counters and independent secondary RCON latency.

Snapshot telemetry outside the core timing boundaries; a process snapshot may encompass a slightly wider window than the exact server-thread CPU timer. Record that limitation explicitly.

**Do not subtract JIT, GC, scheduler-wait or CPU-pressure measurements from the primary CPU measurement.** They can explain why a comparison is invalid, and motivate a separate *causal intervention*.

## Critical result from SCHED-NOISE-005

[Same-binary calibration](scheduler-noise-calibration-SCHED-NOISE-005.md) found that even identical fresh-server binaries can show a roughly 20% apparent difference. Three boots across both stacks exhibited 340–350 ms of concurrent GC-worker CPU per timed scoreboard window (rather than ~9 ms), accompanied by more run-queue delay and higher server-thread CPU. This confirms why a stable within-JVM plateau and zero cgroup-throttling events alone are insufficient.

A future study should separately declare:
- **GC-inclusive real-world performance**, for which intervention-caused GC and compilation are valid costs.
- **GC-quiet steady-state execution**, for which GC and JIT activity must be gated *before* measurement, with the number of failed qualifications disclosed, not silently filtered.

An A/A run with GC logging plus a controlled diagnostic variation of GC settings would help identify the remaining noise. A JVM option that reduces GC noise is not by itself a proven speedup in normal production settings.

## Required archived outputs

Every campaign must publish its preregistration, exact source, build fingerprints, raw per-window counters, all pair labels, work verification, JVM warmup and host-quality gate outcomes, interval calculation, separate diagnostic recordings and a decision specifying what is supported or unproven. Preserve failed and negative experiments.

**Related:** [SCHED-HOOK-003](scheduler-hook-overhead-SCHED-HOOK-003.md), [SCHED-HOOK-004](scheduler-hook-overhead-SCHED-HOOK-004.md), and [SCHED-NOISE-005](scheduler-noise-calibration-SCHED-NOISE-005.md).
