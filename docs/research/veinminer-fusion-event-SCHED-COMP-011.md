# SCHED-COMP-011 — Vein Miner real-event fusion incrementality and compilation cost

**Status:** Preregistered. This is a **new comparison**; the previous Vein Miner PERF-017 study compared compiler disabled vs fused and found an event-level median **+0.69%** (97.85% exact interval **−3.92% to +2.74%**) despite runtime fusion activation. SCHED-COMP-010 subsequently measured an isolated synthetic *fusion over ScoreAdd-only* median **−29.91 log-percent** in server-thread CPU (96.1% exact median interval **−33.68 to −28.21**, clean placebo). Neither result establishes application-level value for fusion.

## Primary question

Does actual fused-region execution materially reduce **whole native Vein Miner event completion latency** compared with typed ScoreAdd specialization **without fusion**, on the pinned real Vein Miner datapack? This is the incremental real-event value of fusion, not fusion vs vanilla, per-command CPU, or a new generic scheduler.

## Locked artifact and workload

- Vein Miner 5.3.0 Minecraft 26.3 datapack ZIP; pinned SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`.
- Use the existing `scripts/run_veinminer_profile.py` native player-bot survival event, **6×6×6 ore vein (215 expected mined blocks)** on identical Fabric stacks. Do not replace it with a synthetic score function.
- Two modes: `score-add` (compiler wrapper and typed ScoreAdd **on**, fusion off); `fused-timed` (wrapper, ScoreAdd and fusion **on**, timing counters disabled). Both without Spark/JFR and without per-command execution metrics.
- All ten paired events must verify the complete native state vector (source mining stat, work count, queue progress, ore removal, markers, run state). Disagreement aborts; no 'corrected' performance metric.
- Fused arm: `fused_regions_compiled >0` globally **and** `vm:detection/acquire_target` has a fused region compiled. Baseline: `fused_regions_compiled=0`. Source-level compile counters are non-timed. Execution activation had already been demonstrated for this pinned workload in PERF-017 diagnostics; a separate diagnostic may be run if behavior changes.

## Predeclared paired design and decision

- **10 complete fresh-server pairs**, seeded order `26874011`, exactly five ScoreAdd→fused and five fused→ScoreAdd. Retain all attempts/results; do not omit noisy pairs.
- Primary metric: `operation_completion_seconds`, and paired `100*(fused/scoreadd - 1)` percent change.
- The conservative exact >=95% median interval across ten paired effects (97.85% coverage for ten) is the decision basis. A minimum worthwhile **15% improvement**, as in the previous PERF-017 promotion gate, requires upper endpoint ≤−15%.
- If interval lower endpoint is >0, `real_event_regression_supported`. If entire interval lies above −15%, `does_not_meet_15pct_gain`. All other cases `real_event_inconclusive`; keep fusion disabled by default.
- Primary results must never be pooled with SCHED-COMP-010 synthetic server CPU, nor with PERF-017's different baseline.
- Tick query average and P95, if reported, are **secondary exploratory game-impact signals**; not interchangeable with event-completion time.

## Compilation and startup cost (separate estimands)

An opt-in `FC_BENCH_COMPILE_TIMING=true` instruments **constructor-time** `ScoreAddPrototype.compile` and `FusedRegionPrototype.compile` stages with `System.nanoTime`; counters are exposed through `function_compiler_probe status` and per-function stats. These are **wall-clock elapsed time during parser/compilation phases**, not thread CPU time and not full datapack reload cost. They can include scheduling delays and do **not** cover all macro/lifecycle compilation.

- For every arm, record ScoreAdd stage cumulative wall ns; in fused arm also record fused stage cumulative wall ns. Compute per-pair candidate minus baseline summed stage time, and report its median separately.
- Also record process launch→RCON readiness seconds. This includes the JVM/Gradle launch, datapack load, and other initialization. It is **not** attributable solely to the compiler and is **not** subtracted from the event-completion result.
- Timing hooks run only on load/initialization and do not add per-command execution metrics in either arm.
- No unconditional break-even claim. A speculative 'events to amortize' ratio is unqualified until event latency reduction is independently supported and full reload latency isolated.

## Reproducibility caveat

The pinned Vein Miner ZIP is **not tracked in Git**. CI first attempts to obtain version ID `5jzz5SkG` from the publisher's Modrinth API, selects exactly `VeinMiner-5.3.0+26.3.zip`, and verifies the expected SHA-256. An optional `MC_VEINMINER_REFERENCE_URL` secret can point to a trusted mirror of the exact pinned file. If no source yields matching bytes, **fail at preflight, preserve the attempted checksum, and report NO experimental result**; do not silently use a different pack.

## Next

This is an application-level falsification test following the synthetic mechanism study. A large CPU gain coupled with no event-completion gain implies that this real workload is not dominated by eligible fused regions. Then prioritize a different real workload with substantial measured fusion coverage, reload-cost improvements, or other compiler specializations; do not revisit generic GC-noise investigation without a specific broken gate.

**Code:** `scripts/ci_veinminer_fusion_event.py` and `scripts/run_veinminer_profile.py`. **Tests:** `tests/test_veinminer_fusion_event.py`. **Output:** `build/benchmarks/SCHED-COMP-011/results.json`. **Workflow:** `.github/workflows/research-veinminer-fusion-event.yml`.
