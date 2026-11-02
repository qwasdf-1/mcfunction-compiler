# PERF-016: Sustained Adjacent-Eligible Fused-Region Active-Tick Fixture

**Run:** 2026-11-02  
**Evidence:** [`build/benchmarks/PERF-FUSED-SUSTAINED/fabric-confirmatory-10pairs-20261102T224610670509Z/results.json`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-confirmatory-10pairs-20261102T224610670509Z/results.json) and the screening pilot [`fabric-screening-5pairs-20261102T221639260029Z/results.json`](../build/benchmarks/PERF-FUSED-SUSTAINED/fabric-screening-5pairs-20261102T221639260029Z/results.json)  
**Status:** Complete — **inconclusive** for promotion. The confirmatory median supports a faster workload-attributable tick average, but its interval overlaps the pre-declared 15% minimum gain, so the fused-region engine stays disabled by default.

---

## 1. Objective & Background

The fused-region engine ([`FusedRegionPrototype.java`](../src/main/java/dev/functioncompiler/FusedRegionPrototype.java)) groups adjacent eligible commands into one scheduler entry, which is the project's core mechanism for removing command-queue overhead. Its semantic evidence is broad (ten-arm runtime matrix, 88-trace parity, frame-discard cases), but its *performance* evidence was one static 5,000-add fixture timed at the queue boundary (PERF-003/PERF-004) plus macro-region fusion (PERF-012). No screened datapack supplies an adjacent-eligible region, so [`tests/fixtures/function_compiler_fused_sustained`](../tests/fixtures/function_compiler_fused_sustained/pack.mcmeta) was created as the controlled adjacent-eligible workload, following the [benchmarking protocol](../docs/benchmarking.md).

[`PERF-016`](../docs/v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv) measures that fixture under the shared gates:

1. **Semantic parity** — mod-free vanilla 26.3 reference plus a same-stack compiler-off arm.
2. **Path activation** — separate diagnostic arm proving every active tick executed a fused region.
3. **Workload integrity** — exact `#fused` delta equal to 5,000 adds per active tick in every arm.
4. **Performance** — paired, counterbalanced, unprofiled active-tick comparison.

---

## 2. Workload & Test Fixture

The checked-in fixture's `tick.mcfunction` is a pristine block of **5,000 contiguous** `scoreboard players add #fused fc_fused 1` lines. The runner generates two files into each disposable server's datapack copy (recorded by hash in the report) and leaves the add block untouched:

```mcfunction
# generated data/function_compiler_fused_sustained/function/tick_instrumented.mcfunction
scoreboard players add #server_ticks fc_fused 1
execute if score #enabled fc_fused matches 1 run function function_compiler_fused_sustained:tick
execute if score #enabled fc_fused matches 1 run scoreboard players add #active_ticks fc_fused 1
```

The generated `minecraft:tick` tag replaces the fixture tag and calls only that instrumented function, so the 5,000 adds run as one nested function and stay contiguous. Per active tick the workload applies exactly 5,000 adds through the eligible path.

**Arms.** `off` is same-stack Fabric with the probe mod loaded and every `FC_*` optimization flag false. `fused` mirrors the runtime probe's canonical `fused-interpreted` mode: wrapper enabled, the specialization pass active (it supplies the [`FusableCommand`](../src/main/java/dev/functioncompiler/FusableCommand.java) entries), and region fusion enabled. `vanilla-reference` is the fingerprinted official 26.3 server jar with the same fixture. Primary timing arms run without Spark, compiler counters, or timers.

**Primary metric.** `workload_tick_average_ms` = active-phase `/tick query` average minus the same server's post-workload idle `/tick query` average. Each arm samples five active windows of 110 active ticks and three idle windows, and takes the per-label median, so one GC pause or JIT hiccup cannot define an arm. `/tick query` summarizes its last 100 ticks, so every sampled window lies entirely inside the workload phase it belongs to.

---

## 3. Gate Results

**Workload integrity (all arms, exact):**

| Arm | Active ticks | Adds applied | Adds per active tick |
|---|---|---|---|
| `vanilla-reference` | 675 | 3,375,000 | 5,000 |
| `activation-diagnostic` (`fused`) | 674 | 3,370,000 | 5,000 |
| every confirmatory pair arm | 674–675 | 3,370,000–3,375,000 | 5,000 |

**Path activation (diagnostic arm):** `fused_regions_compiled=94` and `fused_regions_executed=674`, exactly one executed region per active tick, matching the single 5,000-command region per tick. `score_add_executed=3,371,874` confirms the specialized commands ran inside the region (5,000 × 674 plus the instrumented function's own adds). The 94 compiled regions come from the mod's 221 built-in probe functions plus this fixture; only functions with at least two adjacent fusable commands produce a region.

**Parity:** all ten confirmatory pairs matched the vanilla reference's exact per-active-tick add count (`all_pairs_exact_parity = true`).

---

## 4. Screening Pilot (5 pairs, single-window design)

The first campaign used one 100-tick window per arm. It passed exact workload parity in every arm and reported a **-22.86%** median paired change in workload-attributable tick average (range -86.55% to 0.00%, 93.75% interval -86.55% to 0.00%, decision `screening_only`). The `off` arm's single-window values were bimodal (3.2–22.3 ms) because one GC-heavy 100-tick window dominated, while the fused arm stayed near 3 ms. That spread motivated the multi-window measurement used for the confirmatory run; the pilot is retained as screening evidence only.

---

## 5. Confirmatory Campaign (10 pairs, multi-window design)

Pre-declared before the first server arm, and recorded in the report: **minimum worthwhile gain 15%**, **10 pairs**, seed 26871041, Fabric stack (no mods), Minecraft 26.3, `-Xms512M -Xmx2G`, no Spark, no compiler counters during timing.

| Pair | Order | `off` workload ms | `fused` workload ms | Change |
|---|---|---|---|---|
| 1 | fused, off | 3.2 | 2.6 | -18.8% |
| 2 | off, fused | 3.1 | 2.7 | -12.9% |
| 3 | fused, off | 3.1 | 2.7 | -12.9% |
| 4 | off, fused | 2.9 | 2.3 | -20.7% |
| 5 | fused, off | 3.2 | 2.7 | -15.6% |
| 6 | off, fused | 3.1 | 2.3 | -25.8% |
| 7 | fused, off | 3.2 | 2.2 | -31.2% |
| 8 | fused, off | 3.0 | 2.3 | -23.3% |
| 9 | off, fused | 2.9 | 2.4 | -17.2% |
| 10 | off, fused | 3.3 | 2.3 | -30.3% |

**Decision metrics:**

| Metric | Median | Range | Exact interval (97.85%) | Decision |
|---|---|---|---|---|
| `workload_tick_average_ms` (primary) | **-19.72%** | -31.25% to -12.90% | -30.30% to -12.90% | **inconclusive** |
| raw active tick average | -16.53% | -24.39% to -7.69% | -23.26% to -10.00% | context only |
| active tick P95 | -18.63% | -39.06% to +1.89% | -28.85% to -9.09% | context only |

The interval overlaps the pre-declared -15% gain, so under the protocol's decision rule this **does not establish the minimum worthwhile improvement** and does not promote the engine. The negative median across all ten pairs is a consistent direction, not a qualified gain.

---

## 6. Decision & Limitations

- `fused_regions` remains `false` by default. No promotion follows from this campaign.
- The workload is a **controlled mechanism fixture**, not a real datapack. It closes the mechanism-level measurement gap; it does not show that a real pack benefits. Vein Miner 5.3.0, Blastback, and Dynamic Lights still supply no adjacent-eligible region.
- The candidate arm includes the specialization pass. A configuration that enables only `fused_regions` while `score_add` stays disabled was **not** measured here; the production flag combination is a follow-up decision item, not a result.
- One stack (plain Fabric) was measured. No mod-stack confirmatory run exists.
- The vanilla reference arm is a standalone server jar and shows a lower background than the dev-server arms (1.0 ms vs ~0.8–1.2 ms); only same-stack `off`/`fused` pairs are used for the decision.

**Next actions:** (1) re-run with more pairs or a larger per-tick eligible block so the interval can separate from -15%; (2) run the confirmatory campaign on a mod stack (`lb113`) for compatibility coverage; (3) re-screen datapacks for an adjacent-eligible region so a real workload can replace or corroborate this fixture; (4) decide the flag combination (`fused_regions` with or without `score_add`) before any promotion.

---

## 7. Reproduction

```sh
# Screening pilot (protocol minimum)
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 5 --phase screening

# Confirmatory campaign (threshold and pair count pre-declared from the pilot)
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 10 --phase confirmatory \
  --minimum-gain-percent 15 --seed 26871041
```

The runner verifies the pinned server hash and mod hashes, starts a mod-free vanilla reference, a separate activation diagnostic, then counterbalanced `off`/`fused` pairs in fresh disposable worlds, and writes the raw report above. Semantic parity for the fused engine is covered separately by the ten-arm runtime matrix in [`docs/verification.md`](../docs/verification.md).
