# SCHED-GC-006 — Archived GC cycle reanalysis (2026-11-12)

**Source:** Successful [Actions run 43281755953](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43281755953), artifact `sched-gc-006-phase-attribution-raw` (artifact ID 13974107260). **Not a new benchmark run.**

## Method

Reconstruct G1 collection cycles by GC ID using the JVM's unified log. Match top-level `[gc]` completion messages to `[gc,start]` records where available. For `Concurrent Mark Cycle`, reconstruct the start by subtracting the logged duration when no explicit start exists. Retain nested phases, but do **not** add their durations to the containing cycle. Intersect intervals with the Python epoch-clock brackets around each scored window. The bracket contains more than the server-thread CPU interval, so overlap timing is approximate.

The reusable analyzer is `scripts/analyze_gc006_archive.py`; run against the archived ZIP and retain every boot and window. No performance-relevant JVM flags or production code were modified by the offline reanalysis.

## Findings

- All **20** boots and **40** timed scoreboard windows remain in the analysis.
- The logs contain **1,560 top-level GC events**: **1,411 pauses** and **149 concurrent mark cycles** across whole boot lifetimes. Concurrent cycle starts were duration-inferred; the pause starts were explicit.
- **Zero** of the 40 timed scoreboard windows overlaps a logged concurrent mark cycle. This does not establish absence of GC workers or concurrent refinement work.
- Across scored windows, median GC-worker CPU ≈ **8.46 ms**, maximum ≈ **11.63 ms**, versus the roughly 350 ms anomalous regime observed in the prior SCHED-NOISE-005 run.
- Median stop-the-world pause overlap ≈ **5 ms per window**.
- Exploratory window-level Pearson correlations with server-thread ns/source line: GC-worker CPU **r ≈ +0.27**; observed pause overlap **r ≈ +0.20**. Neither supports a causal interpretation.
- Original A/A verdict is unchanged: **`null_calibration_failed_variance_targets`**. Median absolute apparent effect **3.66%**, compared with a preregistered ≤3% target; remaining P90/max and quality gates passed.

Adjacent first-to-second CPU changes (%), all ten pairs retained:

| Pair | Stack | First → second |
|---:|---|---:|
| 1 | Fabric | −2.48 |
| 2 | Compiler disabled | +4.90 |
| 3 | Compiler disabled | +1.86 |
| 4 | Fabric | −2.92 |
| 5 | Fabric | +9.82 |
| 6 | Compiler disabled | −1.19 |
| 7 | Fabric | +4.50 |
| 8 | Compiler disabled | −5.41 |
| 9 | Compiler disabled | +2.83 |
| 10 | Fabric | −6.52 |

The time-ordered percentage change uses the first boot as denominator, and is not identical to blinded signed changes or symmetric log ratios.

## Interpretation and restrictions

The observed GC pattern is consistent with ordinary G1 young-generation activity during the timed workload and concurrent marking predominantly during startup/warmup. It explains why the new run does **not** reproduce the previous extreme concurrent-GC observation, but cannot establish why 005 and 006 differed. Different Actions host conditions and logging effects remain plausible.

Most importantly, the residual 3–9% A/A differences cannot be explained away by concurrent mark cycle overlap in the 006 timed windows, because no such overlap is logged. This does not prove that pause cost, concurrent refinement, cache interference, JIT tier differences, or host contention played no role.

**Next research decision:** do not post-hoc filter GC windows or treat the cleaner 006 result as a compiler improvement. Validate a prospective GC-quiet qualification rule with an independent A/A calibration, or move to a dedicated benchmark host if resolving ~5% effects is the practical goal. No scheduler replacement or performance equivalence is supported.
