# PERF-016: Sustained Adjacent-Eligible Fused-Region Active-Tick Fixture

**Run:** 2026-11-02 – 2026-11-03  
**Evidence:**
- Fabric, 5,000 adds/tick, 10 confirmatory pairs: [`build/benchmarks/PERF-FUSED-SUSTAINED/fabric-confirmatory-10pairs-20261102T224610670509Z/results.json`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-confirmatory-10pairs-20261102T224610670509Z/results.json)
- Fabric, 20,000 adds/tick, 12 confirmatory pairs (seed 26871042): [`build/benchmarks/PERF-FUSED-SUSTAINED/fabric-confirmatory-12pairs-20261103T010812635221Z/results.json`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-confirmatory-12pairs-20261103T010812635221Z/results.json)
- Lithium 0.26.2 + Bellows 1.1.3 (`lb113`), 5,000 adds/tick, 10 confirmatory pairs (seed 26871043): [`build/benchmarks/PERF-FUSED-SUSTAINED/lb113-confirmatory-10pairs-20261103T031145145286Z/results.json`](../build/benchmarks/PERF-FUSED-SUSTAINED/lb113-confirmatory-10pairs-20261103T031145145286Z/results.json)
- Screening pilots retained as screening only: [`fabric-screening-5pairs-20261102T221639260029Z`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-screening-5pairs-20261102T221639260029Z/results.json) and [`fabric-screening-1pairs-20261103T005747818791Z`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-screening-1pairs-20261103T005747818791Z/results.json)
- Datapack screen: [`build/reports/datapack-screening/adjacent-regions-20261103T010423Z`](../build/reports/datapack-screening/adjacent-regions-20261103T010423Z.md)

**Status:** Complete — **inconclusive** for promotion across three confirmatory campaigns. Every confirmatory median favors the fused arm, but every 95% exact interval overlaps the pre-declared 15% minimum gain, so `fused_regions` stays disabled by default.

---

## 1. Objective & Background

The fused-region engine ([`FusedRegionPrototype.java`](../src/main/java/dev/functioncompiler/FusedRegionPrototype.java)) groups adjacent eligible commands into one scheduler entry, which is the project's core mechanism for removing command-queue overhead. Its semantic evidence is broad (ten-arm runtime matrix, 88-trace parity, frame-discard cases), but its *performance* evidence at this fixture level was one static 5,000-add fixture timed at the queue boundary (PERF-003/PERF-004) plus macro-region fusion (PERF-012).

The original plan called for a real datapack with adjacent eligible commands. A 2026-11-03 static screen ([`screen_adjacent_regions.py`](../scripts/screen_adjacent_regions.py), 19 pinned packs, 27,762 functions) found candidate runs — Blastback's generated block-state reader (32 adjacent `execute if block ... run scoreboard players set` per state table), Vein Miner's family detection (145 parsed candidates plus a one-time 19-add `@s` initialization), and Simple Timer's 36-command tick display/clock chain — but no candidate has runtime-confirmed specialization or a measured real workload. Until that exists, [`tests/fixtures/function_compiler_fused_sustained`](../tests/fixtures/function_compiler_fused_sustained/pack.mcmeta) remains the controlled adjacent-eligible workload, following the [benchmarking protocol](../docs/benchmarking.md).

[`PERF-016`](../docs/v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv) measures that fixture under the shared gates:

1. **Semantic parity** — mod-free vanilla 26.3 reference plus a same-stack compiler-off arm.
2. **Path activation** — separate diagnostic arm proving every active tick executed a fused region.
3. **Workload integrity** — exact `#fused` delta equal to the configured adds-per-active-tick in every arm.
4. **Performance** — paired, counterbalanced, unprofiled active-tick comparison.

---

## 2. Workload & Test Fixture

The checked-in fixture's `tick.mcfunction` is a pristine block of **5,000 contiguous** `scoreboard players add #fused fc_fused 1` lines. The runner generates only instrumentation into each disposable server's datapack copy (recorded by hash in the report) and leaves the checked-in block untouched:

```mcfunction
# generated data/function_compiler_fused_sustained/function/tick_instrumented.mcfunction
scoreboard players add #server_ticks fc_fused 1
execute if score #enabled fc_fused matches 1 run function function_compiler_fused_sustained:tick
execute if score #enabled fc_fused matches 1 run scoreboard players add #active_ticks fc_fused 1
```

`--adds-per-tick N` scales the block without editing the fixture: for `N` other than the checked-in 5,000, the runner also generates `function/tick_scaled.mcfunction` with exactly `N` contiguous `ADD_COMMAND` lines and points the instrumented wrapper at it. Both the scaled function and the wrapper are hash-recorded in the report's `generated_sha256`, and `configuration.adjacent_eligible_adds_per_active_tick` records the value in force. The generated `minecraft:tick` tag replaces the fixture tag and calls only the instrumented function, so the add block stays contiguous. Per active tick the workload applies exactly `N` adds through the eligible path.

**Arms.** `off` is the same stack with the probe mod loaded and every `FC_*` optimization flag false. `fused` mirrors the runtime probe's canonical `fused-interpreted` mode: wrapper enabled, the specialization pass active (it supplies the [`FusableCommand`](../src/main/java/dev/functioncompiler/FusableCommand.java) entries), and region fusion enabled. `vanilla-reference` is the fingerprinted official 26.3 server jar with the same fixture. Primary timing arms run without Spark, compiler counters, or timers.

**Flag semantics (this change).** `fused_regions=true` now implies the scoreboard specialization pass, and `score_add` is effective when fusion is off; previously `CompilerConfig.isScoreAddEnabled()` was dead code and the runtime default followed the master `enabled` switch. The candidate arm therefore reflects the production `fused_regions=true` behavior, in which `score_add=false` no longer disables specialization. A configuration that disables specialization while fusion is on now requires the diagnostic override `FC_SCORE_ADD_PROTOTYPE=false` and was not measured by this campaign. See [`docs/reference/configuration.md`](../docs/reference/configuration.md).

**Primary metric.** `workload_tick_average_ms` = active-phase `/tick query` average minus the same server's post-workload idle `/tick query` average. Each arm samples five active windows of 110 active ticks and three idle windows, and takes the per-label median, so one GC pause or JIT hiccup cannot define an arm. `/tick query` summarizes its last 100 ticks, so every sampled window lies entirely inside the workload phase it belongs to.

---

## 3. Gate Results

**Workload integrity (all arms, every campaign, exact):**

| Campaign | Vanilla reference | Activation diagnostic | Confirmatory pair arms |
|---|---|---|---|
| Fabric 5,000 adds/tick | 675 ticks · 3,375,000 adds | 674 ticks · 3,370,000 adds | 673–674 ticks · 3,365,000–3,370,000 adds |
| Fabric 20,000 adds/tick | 674 ticks · 13,480,000 adds | 671 ticks · 13,420,000 adds | 668–679 ticks · 13,360,000–13,580,000 adds |
| `lb113` 5,000 adds/tick | 672 ticks · 3,360,000 adds | 673 ticks · 3,365,000 adds | 672–675 ticks · 3,360,000–3,375,000 adds |

**Path activation (diagnostic arms):**

| Campaign | Regions compiled | Regions executed | Executed per active tick | Specialized adds executed |
|---|---:|---:|---:|---:|
| Fabric 5,000 | 94 | 674 | 1 (exact) | 3,371,874 |
| Fabric 20,000 | 95 | 671 | 1 (exact) | 13,421,904 |
| `lb113` 5,000 | 94 | 673 | 1 (exact) | 3,366,884 |

Each diagnostic executed exactly one fused region per active tick, matching the single per-tick add block, and the specialized counters cover the whole block plus the instrumented function's own adds. The compiled counts (94–95) come from the mod's built-in probe functions plus the fixture; only functions with at least two adjacent fusable commands produce a region.

**Parity:** every confirmatory pair on every stack matched its vanilla reference's exact per-active-tick add count (`all_pairs_exact_parity = true` in all three confirmatory reports).

---

## 4. Screening Pilots (retained as screening only)

The Fabric 5-pair pilot used one 100-tick window per arm. It passed exact workload parity and reported a **−22.86%** median paired change in workload-attributable tick average (range −86.55% to 0.00%, 93.75% interval, decision `screening_only`). The `off` arm's single-window values were bimodal (3.2–22.3 ms) because one GC-heavy window dominated, while the fused arm stayed near 3 ms. That spread motivated the multi-window measurement used for the confirmatory runs.

A 1-pair Fabric smoke at 20,000 adds/tick verified the scaled workload before the confirmatory campaign: exact integrity in every arm (673–686 active ticks, 13,460,000–13,720,000 adds), exact activation (95 compiled, 679 executed, `score_add_executed=13,581,975`), and a +79.93% single-pair change that the 12-pair campaign later showed to be a noisy first-arm artifact rather than a property of the scaled block.

---

## 5. Confirmatory Campaigns

Each campaign pre-declared its threshold and pair count before the first timing arm, and the report records them: **minimum worthwhile gain 15%**, paired decision on `workload_tick_average_ms`, Fabric stack without mods unless stated, Minecraft 26.3, `-Xms512M -Xmx2G`, no Spark, no compiler counters during timing.

| Campaign | Stack | Adds per active tick | Pairs | Primary median | Exact interval | Coverage | Decision |
|---|---|---:|---:|---:|---|---:|---|
| `fabric-confirmatory-10pairs` (seed 26871041) | Fabric | 5,000 | 10 | **−19.72%** | −30.30% to −12.90% | 97.85% | **inconclusive** |
| `fabric-confirmatory-12pairs` (seed 26871042) | Fabric | 20,000 | 12 | **−12.48%** | −33.09% to +77.44% | 96.14% | **inconclusive** |
| `lb113-confirmatory-10pairs` (seed 26871043) | Lithium + Bellows 1.1.3 | 5,000 | 10 | **−22.16%** | −86.39% to −12.12% | 97.85% | **inconclusive** |

### 5.1 Fabric, 5,000 adds per active tick (10 pairs)

| Pair | Order | `off` ms | `fused` ms | Change |
|---|---|---|---:|---:|---:|
| 1 | fused, off | 3.2 | 2.6 | −18.8% |
| 2 | off, fused | 3.1 | 2.7 | −12.9% |
| 3 | fused, off | 3.1 | 2.7 | −12.9% |
| 4 | off, fused | 2.9 | 2.3 | −20.7% |
| 5 | fused, off | 3.2 | 2.7 | −15.6% |
| 6 | off, fused | 3.1 | 2.3 | −25.8% |
| 7 | fused, off | 3.2 | 2.2 | −31.2% |
| 8 | fused, off | 3.0 | 2.3 | −23.3% |
| 9 | off, fused | 2.9 | 2.4 | −17.2% |
| 10 | off, fused | 3.3 | 2.3 | −30.3% |

Primary metric median −19.72% with a −30.30% to −12.90% interval; the raw active tick average median is −16.53% and the P95 median −18.63% as context. The interval overlaps −15%, so the campaign does not establish the minimum worthwhile improvement. The negative median across all ten pairs is a consistent direction, not a qualified gain.

### 5.2 Fabric, 20,000 adds per active tick (12 pairs)

This campaign tested whether a larger per-tick block would separate the interval from −15%. **It did not.** The scaled workload ran at roughly four times the tick cost, and per-arm variance grew with it: four of twelve pairs contained an arm in a 20–27 ms band that produced +4.7%, +77.4%, +93.1%, and +143.2% reversals, while the other eight pairs clustered between −10.5% and −53.0%. The primary metric's median is −12.48% with a −33.09% to +77.44% interval (96.14% coverage), far wider than the 5,000-add confirmatory. Section 6 traces the cause to host CPU contention acting on a CPU-bound block — the campaign's own mod-free vanilla reference arm measured 27.1 ms in this run and 6.4 ms on the same fixture and jar in a quieter window — so the reversals are not evidence about the fused engine.

| Pair | Order | `off` ms | `fused` ms | Change |
|---|---|---:|---:|---:|---:|
| 1 | off, fused | 12.4 | 10.9 | −12.1% |
| 2 | fused, off | 11.1 | 27.0 | +143.2% |
| 3 | off, fused | 14.0 | 12.2 | −12.9% |
| 4 | off, fused | 14.5 | 11.5 | −20.7% |
| 5 | fused, off | 14.8 | 15.5 | +4.7% |
| 6 | fused, off | 13.1 | 25.3 | +93.1% |
| 7 | off, fused | 13.3 | 11.9 | −10.5% |
| 8 | fused, off | 13.3 | 23.6 | +77.4% |
| 9 | fused, off | 22.6 | 11.1 | −50.9% |
| 10 | fused, off | 20.0 | 9.4 | −53.0% |
| 11 | off, fused | 13.6 | 9.1 | −33.1% |
| 12 | off, fused | 15.3 | 10.8 | −29.4% |

Context metrics: raw active tick average median −13.46% (interval −27.27% to +85.06%), active tick P95 median −19.47% (interval −27.11% to +210.38%).

### 5.3 Lithium + Bellows 1.1.3, 5,000 adds per active tick (10 pairs)

The first mod-stack confirmatory run for this fixture. The stack passed the same gates as Fabric: exact workload integrity in all arms, exact activation (94 compiled, 673 executed, one per active tick), and exact parity in every pair.

| Pair | Order | `off` ms | `fused` ms | Change |
|---|---|---:|---:|---:|---:|
| 1 | fused, off | 27.8 | 2.9 | −89.6% |
| 2 | off, fused | 19.1 | 2.6 | −86.4% |
| 3 | off, fused | 3.3 | 2.9 | −12.1% |
| 4 | fused, off | 3.5 | 2.9 | −17.1% |
| 5 | fused, off | 3.5 | 2.8 | −20.0% |
| 6 | off, fused | 3.6 | 2.7 | −25.0% |
| 7 | fused, off | 3.1 | 2.6 | −16.1% |
| 8 | off, fused | 4.0 | 2.7 | −32.5% |
| 9 | fused, off | 3.7 | 2.8 | −24.3% |
| 10 | off, fused | 2.9 | 3.0 | +3.4% |

Primary metric median −22.16% with a −86.39% to −12.12% interval. Pairs 1–2 open the campaign with cold-world arms (the `off` arm at 27.8 ms and 19.1 ms against fused arms near 2.6–2.9 ms); as a sensitivity observation only, excluding those two pairs leaves a −18.57% median with a −32.50% to +3.45% interval (99.22% coverage), which is still inconclusive because pair 10 crosses zero. The sensitivity view is not a decision metric.

---

## 6. Variance Diagnosis of the 20,000-Add Block (2026-11-03)

The 20,000-add campaign's interval widened instead of narrowing. A follow-up
diagnosis traced the cause to **host CPU contention acting on a CPU-bound
workload**, not to the fused engine. Recorded evidence:

**A clean baseline on a bare server.** Running the identical fixture, gamerules,
and 110/110-tick idle+warmup protocol on the mod-free 26.3 server jar (three
repeats, with `-Xlog:gc*`, per-window major/minor-fault counters, VmSwap, and
`/proc/pressure/memory`) gives **6.0–7.3 ms** per window at 20,000 adds and
**1.8–2.9 ms** at 5,000 adds, with zero major faults, `VmSwap=0`, no memory
pressure, and a steady 19.6 ticks/s. The 20k block is ~4× the 5k tick cost.

**GC is not the cause on a healthy server.** The bare server's profile at 20k is
young evacuation pauses of ~1.5 ms every ~2.6 s, the heap settling at ~538 M of
2 G, and safepoint totals ≤ 12.6 ms. Two such pauses inside a 110-tick window
move its average by ~0.03 ms — three orders of magnitude short of the observed
15–30 ms windows.

**The campaign's own mod-free reference proves the host effect.** The
`vanilla-reference` arm of the 12-pair campaign measured **27.1 ms**
(windows [19.5, 11.7, 28.3, 31.4, 31.0]); the same arm, same configuration,
same jar, in a quieter window measured **6.4 ms**. A 4× swing with no compiler
involved.

**Reproduction under controlled CPU load.** With eight CPU-bound processes on
the 8-core host: at 5,000 adds the same load moved windows 2.2 → 3.6 ms (~1.6×);
at 20,000 adds it moved a contended window 6.5 → 19.6 ms (~3×). Ticks/s stayed
19.4–19.6 throughout, so the inflation is server-thread *work time*, not the
tick pacing — the server keeps its ~50 ms tick cadence while the mutator gets
less CPU.

**Transient bursts, one to three windows long.** Slow campaign arms were slow
for 1–3 of 5 windows, then recovered — for example `pair-02-fused`
[13.6, 22.8, 37.1, 29.5, 28.5], `pair-09-off` [23.7, 14.4, 31.2, 51.3, 17.5],
`pair-11-fused` [12.3, 12.0, 13.8, 12.8, 15.5] once in the 16–40 ms band. Events
lasting 5–15 s are 1–3 of the 5.5-second windows, which is exactly the
contention-burst signature.

**A spontaneous reproduction without a compiler or injected load.** While
smoke-testing [`diagnose_perf016_host_noise.py`](../scripts/diagnose_perf016_host_noise.py)
on the mod-free server at 5,000 adds, one window measured 10.10 ms against its
2.5–3.6 ms neighbours, with the host-wide `pgmajfault` counter jumping +1,141
and +1,872 in the two windows around it while the server's own major-fault
counter stayed at zero. The host keeps only 39 MB of free swap on this machine,
so other tenants' page-fault bursts are visible as host-wide contention that
this fixture absorbs directly into its tick cost.

**Quiet-window re-run of the same campaign.** Same stack, same 20k block, same
runner, two pairs in a quieter window
([`fabric-screening-2pairs-20261103T055314892530Z`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-screening-2pairs-20261103T055314892530Z/results.json)):
`off` windows 11.8–12.6 ms, `fused` windows 9.3–10.0 ms, pairs −21.9% and
−18.9%, exact parity and exact activation. No slow band appeared. That re-run is
diagnostic evidence for the cause of the 12-pair campaign's variance; it is a
2-pair screening run and is **not** a promotion decision.

**Why the variance grows with the workload.** A CPU-bound tick's work time
scales with the block size, so any given contention event (host tenants, CPU
frequency scaling between 800 MHz and 4.8 GHz, descheduling) removes a larger
fraction of the measurement, and at 20k the inflated windows can constitute a
majority of the five-window median. At 5k the same event is a small fraction of
the tick, the five-window median filters it, and the interval stays useful.

**Consequences for measurement design.** (1) The host, not the compiler, set the
20k campaign's uncertainty. (2) A quiet-window or host-load gate (for example,
sampling `/proc/loadavg` and `/proc/pressure/memory` before and after each arm
and rejecting arms that ran under load) would recover most of the lost
precision. (3) The dev-server `off` arm also carries a systematic ~2× overhead
against the bare server (≈12 ms vs 6.4 ms at 20k) from the mod's integration
hook and the Loom dev runtime; both arms share it, so pairs are unaffected, but
it means the fixture's absolute numbers describe the dev server, not vanilla.

---

## 7. Decision & Limitations

- `fused_regions` remains `false` by default. No confirmatory campaign meets the pre-declared 15% minimum gain, and the direction is consistent (favorable median on every campaign) but unqualified.
- The workload is a **controlled mechanism fixture**, not a real datapack. It closes the mechanism-level measurement gap. The 2026-11-03 screen found candidate runs in Blastback, Vein Miner, and Simple Timer, but none has runtime-confirmed specialization or a measured campaign, so no real pack corroborates this result yet.
- Scaling the block to 20,000 adds per active tick **widened** the interval on this host rather than narrowing it, because host CPU contention inflates a larger fraction of a CPU-bound tick (Section 6). The 5,000-add design is the better instrument here. Do not repeat the 20,000 design on this machine for a promotion decision.
- No campaign sampled host state. `/proc/loadavg` and `/proc/pressure/memory` should be captured per arm, and arms that ran under contention should be re-run, before another campaign claims to separate from −15%.
- The `lb113` run extends coverage to Lithium + Bellows 1.1.3 at the 5,000-add block. It is one mod stack; Lithium-only, Moonrise, and other Bellows versions remain unmeasured for this fixture.
- The candidate arm includes the specialization pass, which `fused_regions=true` now implies. Fusion with specialization disabled requires `FC_SCORE_ADD_PROTOTYPE=false` and is a diagnostic path, not a production mode.
- The vanilla reference arm is a standalone server jar and shows a different background from the dev-server arms (~6.4 ms vs ~12 ms at 20,000 adds, from the mod's integration hook and the Loom dev runtime); only same-stack `off`/`fused` pairs feed the decision.
- The datapack screen is static candidate evidence. Its `parsed_candidates` tier is conservative: it does not cover every parser family, and a flagged run can still fail to parse at runtime.

**Next actions:** (1) instrument one screened candidate (Vein Miner `detection/acquire_target` or Blastback's state reader) with an activation diagnostic to confirm runtime specialization, then run a paired campaign on it; (2) add a host-quietness gate to the runner (load and `/proc/pressure/memory` before and after each arm, with re-run on rejection) before any further campaign attempts to separate from −15%; (3) if more mechanism-level evidence is needed, add pairs on `lb113` at 5,000 adds/tick rather than enlarging the block; (4) keep the `score_add`/`fused_regions` implication documented and covered by the runner's explicit candidate-arm configuration.

---

## 8. Reproduction

```sh
# Screening pilot (protocol minimum, single-window design)
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 5 --phase screening

# Confirmatory campaign at the checked-in 5,000-add block
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 10 --phase confirmatory \
  --minimum-gain-percent 15 --seed 26871041

# Confirmatory campaign with a scaled 20,000-add block (generated, hash-recorded)
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 12 --phase confirmatory \
  --adds-per-tick 20000 --seed 26871042

# Confirmatory campaign on Lithium + Bellows 1.1.3 at 5,000 adds/tick
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack lb113 --pairs 10 --phase confirmatory \
  --adds-per-tick 5000 --seed 26871043
```

The runner verifies the pinned server hash and mod hashes, starts a same-stack vanilla reference (or mod-free vanilla for the Fabric stack), a separate activation diagnostic, then counterbalanced `off`/`fused` pairs in fresh disposable worlds, and writes the raw reports above. Semantic parity for the fused engine is covered separately by the ten-arm runtime matrix in [`docs/verification.md`](../docs/verification.md).

Measure this workspace's noise floor for the same fixture on a mod-free server (with optional injected CPU contention) using:

```sh
python3 scripts/diagnose_perf016_host_noise.py --adds-per-tick 20000
python3 scripts/diagnose_perf016_host_noise.py --adds-per-tick 5000 --load 8
```
