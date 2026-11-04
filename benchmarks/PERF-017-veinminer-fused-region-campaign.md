# PERF-017: Fused-Region Campaign on the Vein Miner Native Event

**Run:** declared 2026-11-03; arms run after the declaration was committed
**Status:** Pre-declared — the parameters below are recorded before the first trial

---

## 1. Objective

PERF-016 established a mechanism-level fused-region effect on a controlled
fixture but never measured a real datapack, because no screened pack had a
runtime-confirmed fused workload. A 2026-11-03 static screen
([`screen_adjacent_regions.py`](../scripts/screen_adjacent_regions.py)) found
candidate runs, and a follow-up activation diagnostic proved that the fused
engine really fires inside the pinned Vein Miner 5.3.0 26.3 archive during a
native mining event. This campaign is the paired performance measurement that
follows from that activation evidence.

## 2. Why Vein Miner, and what fires

- The pinned archive's `vm:detection/acquire_target` holds 145 adjacent
  `execute if block ... run scoreboard players set` candidates (block-family
  and block-state if-chains), with 59 more in `vm:detection/verify_mined_stat`.
- **Activation diagnostic (run before this campaign, metrics on, Fabric, 6×6×6
  event):** `fused_regions_compiled=105`, **`fused_regions_executed` delta 303**
  and **`score_add_executed` delta 16,833** during one native event, with exact
  native workload validity. This is the first recorded runtime confirmation that
  a real datapack's commands execute through fused regions.

## 3. Pre-declared parameters (recorded before the first arm)

| Parameter | Value |
|---|---|
| Workload | Vein Miner 5.3.0 26.3, native survival-player mining of the pinned 6×6×6 ore cube |
| Stack | Fabric (no mods), Minecraft 26.3, `run/veinminer_campaign.py` disposable worlds |
| Arms | `off` (compiler off) vs `fused` (wrapper + specialization + region fusion, **metrics off**) |
| Instrumentation | Symmetric: no Spark, no compiler counters or timers in either timing arm |
| Primary metric | `operation_completion_seconds` (event completion, the established real-workload metric) |
| Context metrics | `tick_average_ms`, `tick_p95_ms` |
| Minimum worthwhile gain | **15%** (same threshold as every prior confirmatory campaign) |
| Pairs | **10** (the protocol needs at least six to attain the 95% exact median-interval coverage) |
| Seed | **26873010** |
| Decision rule | Unchanged: the 95% exact paired interval for the primary metric must support at least the pre-declared gain (interval upper edge ≤ −15%) |
| Host gate | Run behind the same external host-quietness gate as PERF-016 §5.5 (1-minute load < 4.0, no `rustc`/`cargo`/`auditor` processes, > 1 GB free swap, PSI cpu < 4%, PSI io < 3%), with 15-second host-state sampling archived alongside the report |
| Actuation gate | Per arm: exact native workload validity (215 blocks, `#head` advanced, ore removed, no operation markers). Per pair: exact off/on workload-state parity. The fused arm must also report `fused_regions_compiled > 0` and `score_add_metrics_enabled=false` |

**Rationale for the symmetric arms.** The fused engine's region-execution and
scoreboard counters only advance when compiler metrics are enabled
(`FusedRegionPrototype` increments them under `scoreAddMetricsEnabled()`), so an
activation-proving run cannot be a timing run. PERF-016 solved this with a
separate activation-diagnostic arm, and this campaign does the same: the timing
arms are un-instrumented in both directions, and activation is evidenced by the
diagnostic in §2 plus the per-arm `fused_regions_compiled` gate. The alternative
— metrics on in the candidate arm only — was rejected because it would bias the
pair against the candidate.

**What would count as success.** A promotion-grade result requires the interval
to clear −15%. A negative or inconclusive result is an equally valid outcome and
will be recorded as such; the fused engine's real-workload gate stays open
either way, and `fused_regions` remains disabled by default unless the interval
clears.

## 4. Reproduction

```sh
# Activation diagnostic (metrics on; proves regions execute during the event)
FC_GRADLE_OFFLINE=true python3 scripts/run_veinminer_profile.py \
  --stack fabric --compiler-mode fused --side 6 --no-spark

# The pre-declared paired campaign
FC_GRADLE_OFFLINE=true python3 scripts/run_veinminer_campaign.py \
  --stack fabric --side 6 --candidate fused --pairs 10 \
  --phase confirmatory --minimum-gain-percent 15 --seed 26873010 \
  --primary-metric operation_completion_seconds
```

Results, gates, limitations, and the decision are recorded below after the run.
