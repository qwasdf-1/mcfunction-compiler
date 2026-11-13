# SCHED-COMP-010 — Incremental fused-region benefit over typed ScoreAdd

**Status:** Preregistered, no performance result until the campaign completes. **Parent:** SCHED-COMP-009, which returned `invalid_negative_control`, although its positive-arm median was +37.4 log-percent (typed ScoreAdd slower than excluded vanilla fallback).

## Question

For identical 2,000-line Minecraft scoreboard-add functions, does **fusing adjacent ScoreAdd commands** improve steady-state server-thread CPU relative to **typed ScoreAdd without fusion**? This is the incremental cost of the fused-region scheduler-entry reduction, NOT the whole-mod performance difference against unmodified vanilla, a general scheduler replacement, or MSPT.

## Intervention isolation

The existing global `FC_FUSED_REGION_PROTOTYPE` flag would fuse **both** arms if used without change. SCHED-COMP-010 therefore introduces an **optional research-only** `FC_FUSED_REGION_ONLY_NAMESPACE` environment setting in `ProbeConfiguration`, checked in `ProbeFunctionWrapper` for fused-region compilation. When unset, fusion behavior is unchanged. Both ScoreAdd and fusion are enabled, but fusion is compiled only for `fc_bench_fused`. Every function remains ScoreAdd-eligible.

The datapack includes byte-identical 2,000-scoreboard-add functions:
- A: `fc_bench_scoreonly_a:score` — typed ScoreAdd, **not fused**.
- N: `fc_bench_scoreonly_null:score` — independent, byte-identical typed ScoreAdd negative control, **not fused**.
- B: `fc_bench_fused:score` — same 2,000 adds, typed ScoreAdd and fused-region execution.

All are invoked through equally shaped single-command aliases and share one JVM, same compiler binary, same vanilla execution context, world, JVM flags and ScoreAdd optimizer. Per-function compile counters from `functioncompiler stats` are a **hard activation gate**: typed ScoreAdd >0 in **all three** functions; fused regions >0 **only** in B; zero in A and N. New per-function fused compile counters are diagnostic-only, not timed-path counters. Any misclassification aborts the run.

## Frozen protocol

- 12 independent JVM boots; each boot performs negative (A/N) and treatment (A/B) comparisons using the existing fixed seed **8008** balanced crossover schedule.
- Two four-window ABBA/BAAB blocks per boot, one placebo and one treatment, six of each orientation, and 6/6 block orders. Each timed window executes 800 calls, each call 2,000 exact-score increments. The alias invocation adds one equal command to every arm. Preserve all 96 windows.
- Prewarm three function families (500 calls each) and retain the bounded existing qualification protocol.
- Collect Linux server-thread CPU, runqueue delay, cgroup throttling and descriptive JVM/host telemetry outside timed CPU intervals; zero JFR in timing.
- Scoreboard parity must succeed on **every** timed window; count values match precisely. If the result is wrong, abort and report a failed experiment, not an apparent improvement.
- All independent analysis units are **boots (n=12)**, never individual windows. Contrast for each block is `100*(mean(log(B CPU ns/increment))-mean(log(A CPU ns/increment)))`; report the exact at-least-95% median interval across boots.

## Decision criteria

- Hard source-state and activation checks pass; all 12 boots reach qualification, no timed cgroup throttling, available runqueue fraction ≤25% for each timed window.
- The placebo A/N median interval contains zero.
- If B/A interval upper endpoint is below zero, report `fusion_faster_than_scoreadd_supported`.
- If B/A interval lower endpoint is above zero, report `fusion_slower_than_scoreadd_supported`.
- Otherwise, report `fusion_incremental_effect_inconclusive`.
- If placebo fails, verdict `invalid_negative_control`. If quality fails, verdict `inconclusive_quality`. No post-hoc removals or reruns to make significance.

These are descriptive screening rules for this synthetic workload; even a negative interval does not qualify fusion for production or any general real-datapack performance claim. Neither the generic compiler master setting nor the fusion default is changed by this experiment.

## Interpretation and follow-on

This experiment deliberately targets a contiguous region eligible for maximal fusion. A performance benefit here establishes **opportunity**, not prevalence. The next application-level experiment should measure a real datapack/event workload with activation and semantic checks and use compiled/executed function counters to assess coverage. Real event completion and active MSPT must be reported separately from server-thread CPU per command.

The SCHED-COMP-009 A/A failure motivates retaining strict placebo testing, not trying to 'correct' 009 by cherry-picking runs. Regardless of the outcome, return to **mod/compiler research**: fused regions, selective macros, tiered bytecode, compilation/reload amortization, and eventual incremental scheduler-replacement tests.

**Implementation:** `scripts/ci_fused_incremental_crossover.py`. **Tests:** `tests/test_fused_incremental_crossover.py`. **Workflow:** `.github/workflows/research-fused-incremental.yml`. **Output:** `build/benchmarks/SCHED-COMP-010/results.json`.
