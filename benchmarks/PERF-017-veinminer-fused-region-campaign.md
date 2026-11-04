# PERF-017: Fused-Region Campaign on the Vein Miner Native Event

**Run:** declared 2026-11-03; arms run after the declaration was committed
**Status:** Complete — **does not meet the threshold**. The fused engine is active on this real workload but delivers no measurable gain, so the fused-region real-world gate stays open and `fused_regions` remains disabled by default.

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

---

## 5. Results

The campaign ran behind the pre-declared host gate (passed at 2026-11-04T06:26:36Z; pair 1 inside that window, pairs 2–10 after a second gate pass at 06:50:40Z), resuming from pair 1 after a runner fix (see §7). All ten pairs passed the exact native workload gate — 215/215 blocks mined, `#head` advanced 1,952, ore removed, no operation markers — and every pair matched the off arm's workload state exactly (`exact_parity: true`).

| Pair | Order | `off` completion | `fused` completion | Change |
|---|---|---:|---:|---:|---:|
| 1 | off, fused | 18.556 s | 19.182 s | +3.37% |
| 2 | off, fused | 17.989 s | 18.443 s | +2.52% |
| 3 | off, fused | 17.906 s | 18.396 s | +2.74% |
| 4 | off, fused | 19.884 s | 20.101 s | +1.09% |
| 5 | fused, off | 18.861 s | 18.122 s | −3.92% |
| 6 | fused, off | 18.627 s | 18.682 s | +0.29% |
| 7 | fused, off | 18.370 s | 18.840 s | +2.56% |
| 8 | off, fused | 18.387 s | 18.221 s | −0.90% |
| 9 | fused, off | 20.408 s | 19.053 s | −6.64% |
| 10 | off, fused | 18.686 s | 18.267 s | −2.25% |

**Primary metric, `operation_completion_seconds`:** median **+0.69%** (fused
slightly slower), exact interval **−3.92% to +2.74%** at 97.85% coverage,
decision **`does_not_meet_threshold`**. Context metrics: `tick_average_ms`
median +0.73% (interval −14.02% to +99.74%), `tick_p95_ms` median +2.53%
(interval −4.28% to +18.26%) — both screening only, and both noisier, which is
why the paired event-completion metric is the declared primary.

**Activation held throughout.** Every fused arm reported
`fused_regions_compiled=105` and passed the symmetric-mode gate
(`score_add_metrics_enabled=false`, so the timing arms were un-instrumentated).
The separate metrics-on diagnostic in §2 measured what the timing arms could
not: **303 region executions and 16,833 specialized commands per event**. The
engine was genuinely active on the workload that produced no gain.

## 6. Interpretation

This is the first paired, real-datapack measurement of the fused-region engine,
and it is a **negative** result: a tight interval around a zero median. Two
readings are consistent with all the evidence, and the data cannot separate
them:

- **Dilution is the simplest explanation.** The mechanism's demonstrated effect
  is queue-overhead removal (~−20% on PERF-016's fixture, where the eligible
  commands *are* the workload). In Vein Miner they are not: one event executes
  16,833 specialized commands, but the event also spends the bulk of its ~18–20 s
  on block predicates (145 per `acquire_target` call), loot, entity NBT, and
  selector work that fusion leaves on the vanilla path. Removing queue overhead
  from a small fraction of a much larger cost produces a median indistinguishable
  from zero — exactly what was measured.
- **Potential masking is not excluded.** Fusion replaces per-command queue
  dispatch with an in-region loop, which may trade queue savings for other cost
  inside `FusedScoreAddRegion`. The tight interval rules out a large win; it
  cannot distinguish "small fraction, no masking" from "small fraction with some
  masking."

The result does not contradict PERF-016. The fixture measured the mechanism in
isolation and showed ~−20%; this campaign shows that the mechanism does not
move a real event's completion time. Both are true, and together they are the
argument for keeping `fused_regions` disabled: the engine works, and it does not
help where it would need to help.

## 7. Limitations and one recorded mistake

- One workload, one stack, one event shape. Vein Miner is a burst workload whose
  eligible commands are adjacent if-chains that mostly *fail* their predicates
  (only one branch runs per block), so the fused regions execute many predicate
  evaluations and few mutations. A pack whose hot path is genuinely dominated by
  long *successful* runs of specialized commands could behave differently, but
  no pinned pack has been shown to be one.
- The campaign needed a runner fix mid-flight: the fused candidate maps to the
  profile mode `fused-timed`, and the candidate lookup compared against the
  campaign candidate name, so it raised `StopIteration` after pair 1. Pair 1 was
  retained and the campaign resumed from pair 2 (`9e29dd4`); no data was lost
  and both arms of every pair were completed in the same gate-passing window.
- Absolute completion times (18–20 s) describe this workspace's hardware, and
  the paired design is what the decision rests on.

**Next actions:** (1) record this as the fused engine's real-workload result and
stop pursuing fusion promotion on this workload — further pairs would only
tighten an interval that already excludes 15%; (2) if fusion is to be promoted,
the target must be a workload where specialized commands dominate the hot path,
which the current screen has not identified; (3) keep the host-quietness gate,
which produced a ±4% interval here — markedly tighter than any PERF-016
mechanism campaign, and good evidence that event-completion timing on a
long-running workload is far more robust to host noise than per-tick cost.
