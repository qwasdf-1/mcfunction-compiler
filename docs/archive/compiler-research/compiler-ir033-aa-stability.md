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

## Results — first bounded native campaign rejected (2026-11-23)

[GitHub Actions run #45283502793](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45283502793); [complete source/manifests/logs artifact #14869279942](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45283502793/artifacts/14869279942). Six real Fabric JVMs finished and produced all data. IR-033 precommitted schema tests, pinned source preflight, and Java 25 build succeeded. The runner exited with failure on the independent **no-treatment CPU stability screen** after writing and archiving the full JSON report.

| Exact same uninstrumented stationary workload | CPU ns / observed tick | Tick count |
| --- | ---: | ---: |
| A1 | 2,064,177 | 1,200 |
| B1 | 1,798,211 | 1,200 |
| B2 | 1,954,088 | 1,200 |
| A2 | 2,094,982 | 1,200 |
| A3 | 2,535,003 | 1,200 |
| B3 | 2,270,142 | 1,201 |

A/B labels were entirely placebo; **neither label enabled compiler optimizations**. There is no causal treatment.

| Predeclared screen | Result | Admission threshold | Status |
| --- | ---: | ---: | --- |
| Pseudo-B median / pseudo-A median - 1 | **-6.7253%** | Absolute <= 5% | FAIL |
| Adjacent-pair relative spread A1/B1 | 13.7721% | <= 8% | FAIL |
| Adjacent-pair relative spread B2/A2 | 6.9593% | <= 8% | Pass individually |
| Adjacent-pair relative spread A3/B3 | 11.0241% | <= 8% | FAIL |
| Full six-run CPU range relative to mean | **34.7636%** | <= 10% | FAIL |

All original benchmark-correction hashes and exact entities/holders passed the IR-032 inherited validation; all host-quality gates passed. The observed game-time window was within the predeclared 1120–1260 ticks in every arm. The original logs/JSON record `cgroup_nr_throttled_delta = 0` for every arm, with Server-thread runqueue wait fractions 0.053%–0.234% (not a host-throttle explanation). The pre-window idle 100-tick snapshots varied (mean MSPT 2.0–3.2 ms) but were all below the accepted stability admission limits; such baseline variation cannot retroactively be used to select subsets. Warmup elapsed times also varied (14–21 seconds) and JIT/GC lifecycle were not independently controlled. These differences are **possible investigation leads**, not established causes.

**Conclusion: IR-033 A/A STABILITY REJECTED / CLOSED.** Longer 60-second identical workload windows did not qualify the host/fixture for measuring small effect sizes. A wholly fictitious placebo difference of -6.73% was observed despite no compiler-mode change. This is not a compiler speedup and it is not evidence the compiler is ineffective. Do not use this setup to promote new 5–15% CPU effects.

**Decision:** No post-hoc extra A/A attempts, no tightened or loosened thresholds, and no third IR-032 movement-specific optimization investigation. This closes the bounded stability study. A future separately scoped study may isolate per-JVM warmup/JIT/GC or host differences, or adopt a more internally paired design, but should not become the default workstream. Prioritize building reusable typed-IR optimizer infrastructure and identify a concrete compiler transform with a hard correctness oracle before further expensive CPU campaigns.

**Audit note:** the repository's older `docs/architecture.md` still states that fused regions are default-enabled, whereas the present `CompilerConfig.java` and `README.md` default fused regions off. That is stale documentation, not a basis for changing production configuration in this research milestone.
