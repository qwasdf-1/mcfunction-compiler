# SCHED-COMP-009 — Actual ScoreAdd optimization vs namespace-excluded fallback

**Purpose:** first post-noise actual mod performance experiment. Based on SCHED-BENCH-008's within-JVM crossover implementation, but the intervention is now **real compiler specialization** rather than a synthetic extra command.

## Research question

Does MCFC's opt-in typed literal ScoreAdd command specialization reduce steady-state **Minecraft Server thread CPU nanoseconds per exact scoreboard increment**, relative to the vanilla parsed-command callback, when the ordinary Minecraft scheduler remains active?

This asks about ScoreAdd's command callback only, **not** fused regions, bytecode, alternate scheduler, whole-JVM CPU, or sustained MSPT.

## Fixed protocol

- 12 independent Minecraft 26.3/Fabric JVM boots using pinned Java 25 and identical compiler JAR. All three function families coexist in every JVM; the compiler is installed in every arm.
- Use a datapack with three **byte-identical** 2,000-line functions, each performing `scoreboard players add #x fc_sched 1`: `fc_bench_native:score`, `fc_bench_null:score`, `fc_bench_scoreadd:score`.
- Enable wrapper and ScoreAdd prototype, disable fused-region, bytecode, selective macro and timed-path metrics. Configure `excluded_namespaces=["fc_bench_native","fc_bench_null"]`.
- Call the three functions through equally-shaped 1-line `fc_sched_cross_mode:score_a`, `score_null`, and `score_treatment` wrappers. The measurement denominator is **2,000 actual scoreboard increments per call**; an additional alias-function line is executed in *every* arm and is a shared overhead, not counted as a scoreboard operation.
- Before each boot's measurements, verify `functioncompiler status` indicates wrapper and ScoreAdd enabled, fused/bytecode disabled; `functioncompiler stats <function>` must show ScoreAdd compiled commands in the optimized namespace and **zero** compiled commands in both excluded namespaces. Reject any boot where this activation check fails.
- Fixed candidate warmup 500 calls each and additional bounded qualification, followed by two four-window crossover blocks (A/A placebo and A/B specialization). Each timed window contains 800 function calls, and each window must pass exact scoreboard state verification.
- Reuse SCHED-BENCH-008's seeded balanced ABBA/BAAB design: block order 6/6, orientation 6/6 for each kind. Take one signed log CPU contrast per boot per kind. Retain all 12 boots and all 96 windows, including noisy ones and failures. No selective exclusion or early stop.
- Record server CPU, runqueue wait, throttling, host state and output logs; do not subtract GC or worker CPU. No JFR in scored windows.

## Statistical decision

Effect = **100 × mean(log(optimized CPU ns/increment)) − 100 × mean(log(fallback CPU ns/increment))**, aggregated within each block. The independent analysis unit is one JVM boot (n=12). Compute the boot-level median and conservative exact >=95% median interval, plus the placebo A/A interval.

- All integrity and host quality checks pass, and placebo A/A interval contains zero.
- Entire real ScoreAdd A/B interval **below zero**: `scoreadd_faster_supported`.
- Entire interval **above zero**: `scoreadd_slower_supported`.
- Interval crosses zero: `scoreadd_effect_inconclusive`.
- Any boot quality failure: `inconclusive_quality`.

There is **no post-hoc minimum material effect threshold**, and a small statistically detectable effect may not have practical value. This first pass should be followed by real-datapack event-level tests before changing any defaults. The current ScoreAdd prototype remains disabled by default.

## Interpretation limitations

The excluded and eligible functions have different resource identifiers, but their source bodies are identical and both execute through the same one-line alias mechanism. Identical instruction source does not mean identical runtime compilation state; that difference *is* the intervention. Separate startup/reload compilation cost is outside this steady-state CPU estimand. ScoreAdd run counters are disabled during timing to avoid introducing an unequal atomic-metric cost, so activation is verified by compile counters and runtime flags, plus exact state changes, rather than by an extra per-command timed counter. It must not be claimed that no other mod overhead or JVM drift exists.

The optimized and excluded functions share the same JVM, GC, loader, scheduler and compiler installation. This answers a narrower and more attribution-friendly question than comparing separate Fabric and compiler JVM boots.

**Next optimization experiments:** fused interpreted regions vs typed ScoreAdd (incremental value), bytecode-tier vs fused interpreted on the *same eligible workload*, and real-datapack endpoint timing/amortization. Reuse compatible within-JVM design only when flags and compilation paths can genuinely be separated. Avoid general JVM noise studies unless integrity collapses.

## Source

`scripts/ci_compiler_scoreadd_crossover.py`, `tests/test_compiler_scoreadd_crossover.py`, workflow `.github/workflows/research-compiler-scoreadd-crossover.yml`, raw output `build/benchmarks/SCHED-COMP-009/results.json`.
