# COMPILER-IR-033 — No-treatment A/A compiler measurement stability qualification

**Pre-registered 2026-11-23, before native runs.** This milestone is bounded benchmark infrastructure, not compiler optimization or a new Dynamic Lights optimization hypothesis. It directly follows the rejected 18-second IR-032 Gate C CPU study. Do not amend acceptance thresholds in response to observing its result.

## Goal, stop rule and compiler relevance

IR-032 Gate C rejected two independent native stationary/moving campaigns due to CPU noise (including 27.1% stationary and 36.2% moving two-run spread in the second attempt) despite exact source checks, 360 observed ticks, no cgroup throttling, and adequate independent JFR sample coverage (362/454). Before investing in more candidate-selection investigations, test whether our **unmodified compiler configuration and unchanged datapack workload** can yield stable completed-window Server-thread CPU at all. The A/A run must finish with a pass/reject result. Do not automatically increase repeats, revise thresholds, or begin a third IR-032 CPU-versus-movement run.

This is not a compiler speedup test. No A/B optimization treatment exists. The only intended change relative to IR-032 is **run-to-run stability design and window duration**, not runtime behavior. The success criterion is diagnostic noise qualification, not demonstrated 5% detection power.

## Exact experiment

- Six independent fresh Java 25 Minecraft 26.3 Fabric server JVMs, sequence **A1, B1, B2, A2, A3, B3**. A and B are placebo labels: they have absolutely identical flags, compiler assembly, build, datapack, blocks, entities, platform, seed, and command execution.
- Stationary scenario ONLY: pinned original Dynamic Lights by CreepermeYT v1.4.6 publisher SHA `afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20`, separately declared upstream two-call benchmark-only corrected runtime ZIP SHA `c649d206faac63a773ce5dec06ec531128d1f6feaa104ad4e28a18143706d083` (the runtime ZIP is not byte-exact publisher), Smart preset, four fixed creative player holders carrying stone, exactly 24 tagged static dropped torch items, no other light sources, fixed seed 264010, no natural mob spawning or daylight advancement. Reuse the exact IR-032 environment and population guards.
- Java Fabric compiler wrapper active only for the same unchanged configuration. `FC_TYPED_IR_MODE=off`, score specialization, macro selection, IR-030, IR-031, research execution census, callback timers, trace and JFR all disabled. Spark off. No compilation candidate is being measured.
- Each server: regular established warmup, pre-window tick-health gate, then **60 seconds nominal**, target 1200 game-time ticks with admitted range **1120–1260**. Measure the running CPU of the exact Linux Minecraft Server thread through `/proc/<pid>/task/<tid>/schedstat`. Reject any failed item or holder population, unexpected source hash, missing tick count, CPU validity, host stability, cgroup throttling, or excess runqueue wait. Use exact game ticks observed as denominator; RCON bounds are not an atomic exact command-count census.
- Run complete order even if early CPU results look bad. No filtering outliers, choosing subset pairs, instrumentation in CPU windows, or retries based on results. Record six original manifests, logs, a partial-results file, final screen, and full original runtime provenance.

## Precommitted no-treatment placebo screens

Let `c(label)` be Server-thread running CPU ns / observed game tick, lower better.

1. **Placebo effect:** absolute `median(c(B1),c(B2),c(B3)) / median(c(A1),c(A2),c(A3)) - 1` must be **<= 5%**.
2. **Adjacent-pair drift:** `abs(c(x)-c(y))/mean(c(x),c(y))` must be **<= 8%** for each fixed pair A1/B1, B2/A2, A3/B3. These pairs contain no treatment differences.
3. **Overall spread:** `(max(c)-min(c))/mean(all six c)` must be **<= 10%**.

**All three must pass**, together with every per-run provenance and host gate. Report all numerical observations even if rejected. Six arms are insufficient to establish the statistical power to detect any arbitrary true 5% effect, even on a pass; this is a coarse screen for obviously unreliable infrastructure. A/A rejection blocks the next CPU optimization A/B campaign until the cause of noise is isolated in a *separately authorized* fixture or host study. A/A pass permits choosing **one compiler-owned IR-level transformation** for a candidate-specific benchmark with proper A/A + A/B, exact semantic parity, and the unchanged 15% whole-event promotion threshold.

## Explicit project direction after this gate

Treat IR-033 as an infrastructure capstone, not a continuing optimization series. Do not expand into general game-engine/entity-world optimizations merely because they appear in profiler stacks. Candidate work should operate on parsed function command structure, typed IR, permitted static facts, safe compiler-generated command plans, specialization, or lowering into JVM bytecode. The reusable optimization pass must articulate its exact semantic boundary (quota, feedback, exceptions, recursion, nested calls, data mutation, observable side effects and reload). Use cost-based selection and vanilla fallback, not an ever-growing list of event-specific native patches.

The milestone is implemented in `scripts/ci_ir033_aa_stability.py`, tested by `tests/test_ir033_aa_stability.py`, and launched through `.github/workflows/research-ir033-aa-stability.yml`. The final workflow is manual-only. No production defaults are changed and draft PR #10 stays unmerged.

## Results

**PENDING native measurement.** This section is deliberately blank of observations at the time of preregistration; the exact result and artifact link must be appended after the bounded run, whether accepted or rejected.
