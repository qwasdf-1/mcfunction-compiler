# Compiler coverage-widening proposal (v0.1)

**Status: proposal for decision; census and attribution complete (batches
22–23). Nothing in this document ships, and the [v1
roadmap](v1-production-roadmap.md) remains the plan of record. This is the
scoping work the roadmap's step 4 and the batch-19 performance record called
for: with every parity case closed and all four mechanisms' gates decided, the
question is no longer "is the compiler correct" (answered: yes, on the
enumerated families) but "which additional shapes are worth compiling", and
that is a research question this document frames rather than answers. The
H2-first census and the time-share attribution are done: the specializers do
fire on real packs, the open constraint is tick-time share, and the attribution
selects H4. H1's runtime fork pool is ~0 on all three profiled packs, while
Vein Miner's macro-argument construction is 27.4% of sampled wall time / 29.4%
of active tick time and the existing selective-macro mechanism already covers
11,701/11,701 calls with zero fallbacks. The remaining question is a
real-workload selective-macro campaign, not new code; the gate is predeclared
(event completion at 15%, five screening then ten confirmatory pairs, seed
26871031), the screening passed at a −30.03% median with its entire exact
interval beyond the gate, and the predeclared ten-pair confirmatory is next.**

## 1. The question

Can a *second* optimization clear its promotion gate (≥15% median gain with
the 95% exact paired interval entirely beyond it, zero regression) on a
declared workload — and if so, which one, on which shapes, at what
implementation cost?

Selective macro arguments answers "yes" once already, twice over:
`selective_macros=true` is the one shipped default-on optimization, promoted on
the event-completion campaigns (Fabric −22.34%, Lithium −22.06%) and fortified
in batch 19 by the sustained-workload confirmatory (lb113, ten pairs, median
−81.72%, 97.85% interval −82.98% to −80.58%, decision `meets_threshold`).
That campaign is the template for what "clearing a gate" looks like on this
project.

## 2. What the measurements already establish

| Mechanism | Best recorded result | Decision |
| --- | --- | --- |
| Selective macro arguments | −81.72% sustained (lb113, 10 pairs); −22% event-completion | **Cleared; default-on** |
| Fused regions | −15.64% sustained synthetic (10 pairs, interval −29.27% to −3.23%) | `inconclusive` (point estimate crosses 15%, interval cannot certify); real Vein Miner +0.69% [−3.92, +2.74] → `does_not_meet_threshold`; **off** |
| ScoreAdd | +14.8% median slower on the full-function workload; no reliable gain on any measured workload | **off** |
| Bytecode backend | 10.4% slower than fused (BC-06, interval 3.85% to 33.33% slower, `regression_proven`) | **off**; the backend investigation is answered |
| Predicate/selector/NBT family (FR-03) | PERF-005/006: exact parity, but no reduction in sampled function share; FR-03 real-datapack run: predicate mostly failing | **off** |

## 3. The diagnosis the numbers support

The fuser's eligibility rule (`FusedRegionPrototype`, line 119) fuses a run
only when the command is one of the 15 `FusableCommand` implementors **and the
context is not forked** (`context.isForked()`). Real datapack tick functions
are, per the recorded profiles, selector-heavy and entity-relative: their hot
work runs inside `execute as @e[...]` / `at @s` blocks, i.e. exactly the
forked contexts fusion refuses. ScoreAdd's coverage is the literal fake-holder
`#` family only, so storage-backed and entity-relative score commands (the
`execute store result score` shapes the coverage matrix now proves) get no
specialization at all. Selective macro arguments wins because per-entity macro
expansion *is* what real packs spend their ticks on.

So the pattern is consistent: **the specializers do not fire on the shapes real
code contains.** The 2026-11-03 static screen found adjacent eligible runs in
several pinned packs, but no screened pack has a runtime-confirmed specialized
region — nothing yet says a real hot path both fuses *and* dominates its tick.

### 3.1 Census result (batch 22, 2026-11-09)

The H2-first census tested that diagnosis against the pinned packs. It walks
the functions reachable from `minecraft:tick`/`minecraft:load` (including
self-rescheduling `schedule function ... 1t` loops), classifies commands by the
fuser's real eligibility rule, and verifies each pack's recorded SHA-256. The
full table is in the
[benchmarks README](../../../benchmarks/README.md#h2-first-specialization-inventory-2026-11-09).

The census **refines the diagnosis rather than confirming it**. Every pinned
pack has adjacent eligible runs on its tick path (Vein Miner 266 commands in 27
runs, Spawn Animations 165 in 36, Dynamic Lights 80 in 19, Everything Clings 8
in 2), and a native Vein Miner event compiled 164 fused regions and executed
718 of them while the engine stayed on the vanilla-parity path (63/63 work,
480 queue-head increments). The fork barrier is real — 23.4% of Vein Miner's
reachable `execute` lines are forked, 19.0% in Spawn Animations, 25.0% in
Everything Clings, 18.3% in Dynamic Lights — but the non-forked pool is large
enough that "the specializers never fire" is not supported. The recorded
real-workload result is still flat (+0.69% median, interval −3.92% to +2.74%,
`does_not_meet_threshold`), so the binding constraint is **the share of tick
time the addressable work represents**, not its existence. The macro-extension
pool is also narrow in these packs: 10 `function ... with` call sites in Vein
Miner tick functions, none in the other three.

Batch 23 corrected two census gaps that undercounted the batch-22 table: a
macro body line's leading `$` marker is not part of the command, and a macro or
pure-leaf call inside `execute ... run` belongs to the inner command. The
corrected numbers above supersede the batch-22 figures (250/23, 143/35, 14/4);
the ranking is unchanged.

### 3.2 Time-share attribution (batch 23, 2026-11-09)

The census measures static eligibility; it cannot say how much tick time that
work represents. `scripts/attribute_specialization_share.py` partitions each
Spark server-thread stack's self weight by the nearest enclosing leaf command
family, with three decision-relevant boundaries: macro argument construction
(`FunctionCommand$2.arguments` / `getArgumentTag`, including the
`DataCommands.getSingleTag` helper) is reported as its own H4 share rather than
as a `data` command; `ServerFunctionManager.execute` resets the leaf owner so a
function body is attributed to its own commands; and `ContinuationTask` marks
runtime forked samples while blocking syscall/`Thread.sleep`/`park` samples are
split out as idle. Full method and captures are in the
[benchmarks record](../../../benchmarks/README.md#time-share-attribution-and-the-h4-decision-2026-11-09).

| Pack | Idle | Function time (wall / active) | Macro arg H4 (wall / active) | Addressable leaf (wall / active) | Forked samples |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vein Miner 5.3.0 (side 6, compiler off) | 7.1% | 88.5% / 95.2% | 27.4% / 29.4% | 58.7% / 63.2% | 0.0% |
| Spawn Animations 1.11.6 (vanilla, 24 actors, 12 s) | 87.4% | 3.1% / 24.6% | 0.0% / 0.0% | 1.3% / 10.4% | 0.1% |
| Dynamic Lights 1.4.6 (pack on, wrapper off, 30 s) | 60.3% | 9.7% / 24.4% | 0.0% / 0.0% | 0.6% / 1.6% | 0.2% |

The attribution decides the H1/H4 branch:

- **H1 is dead.** Runtime forked samples are 0.0–0.2%, and the hot Vein Miner
  `execute` chain is a non-forked conditional chain whose cost is macro argument
  construction, not fork-interior leaf work. The static forked lines are not
  where the sampled time goes.
- **H4 survives.** Vein Miner's macro-argument construction is the only >15%
  candidate pool (27.4% wall / 29.4% active); the other packs have none. A
  selective-macro diagnostic on the same fixture recorded 11,701 attempted and
  11,701 used calls with zero unsupported providers, entity paths, storage
  sources, missing custom data, resolution fallbacks, or missing keys. The
  mechanism already covers the shape, so the next step is a real-workload
  campaign of the shipped default, not a code extension.

PERF-017's fused arm set `FC_SELECTIVE_MACRO_ARGUMENTS=false`, so its flat
real-workload result did not test the shipped default. The 126.7 ms tick query
from the selective-macro diagnostic is not a timing comparison. The campaign
also needs an uninstrumented selective arm: `run_veinminer_campaign.py`
currently forces the hit counter on its timing arm, and that counter perturbs
timing.

## 4. Candidate hypotheses

Each is stated with its evidence, its falsifiable prediction, its code
surface, and the campaign that would decide it. Effort estimates are for
scoping only and are to be validated against the code before any commitment.

### H2-first: instrument before building — inventory what actually fires (done, batches 22–23)

The cheapest real next step was not new compiler code: it was a **metrics-only
pass** over the pinned real-datapack workload family (Vein Miner, Dynamic
Lights, Everything Clings) counting eligible-region candidates, specialized
commands, and macro-argument hits per tick. The 2026-11-03 static screen
established that candidates exist statically; batch 22 measured whether they
execute, and batch 23 added the time-share attribution.

- **Prediction:** at least one pinned pack has a hot tick path with ≥2 adjacent
  eligible non-forked commands or a large selective-argument-construction
  share; the inventory ranks the packs by addressable work.
- **Result:** the prediction holds statically (every pack has adjacent runs;
  Vein Miner ranks first). The attribution finds a broad addressable leaf pool
  that did not move the real workload, and a 27.4% macro-argument share that
  the existing selective-macro mechanism covers. H1 is dead; H4 survives.
- **Code surface:** `ProbeMetrics` counters only; no behavioral change; days.
- **Decided:** H1/H3 are not worth implementation on these packs; H4 is the
  only candidate with a measured >15% pool, and it needs no code extension.
- **Falsified if:** every pinned pack's eligible work is either forked (H1
  only) or below the measurement floor of the tick average (all candidates
  dead). Not falsified: Vein Miner's macro-argument share is 27.4% wall /
  29.4% active.

### H4: run the proven mechanism on the real workload (selected)

Selective macro arguments avoids full entity/storage serialization when a macro
function reads a small set of top-level custom-data or storage fields. The
attribution shows that this is the one >15% pool in the measured packs, and the
existing mechanism already covers the observed shape; the remaining question is
whether the shipped default clears the gate on the real workload.

- **Evidence for:** it is the only cleared-gate mechanism; Vein Miner's
  macro-argument construction is 27.4% of sampled wall time / 29.4% of active
  tick time; a diagnostic used the fast path on 11,701/11,701 calls with zero
  fallbacks, exact 215/215 work.
- **Evidence against:** the diagnostic's 126.7 ms average tick query is not a
  timing comparison (metrics on, no Spark); PERF-017's flat result did not test
  the shipped default because its fused arm set
  `FC_SELECTIVE_MACRO_ARGUMENTS=false`.
- **Prediction:** compiler-off vs the shipped selective-macro default on Vein
  Miner side 6 clears the predeclared 15% gate with exact workload parity and
  no regression. If the addressable share cannot clear it, that is the recorded
  answer and coverage widening stops.
- **Code surface:** none required. The campaign runner needs an uninstrumented
  selective timing arm (its current arm forces the hit counter) and a separate
  activation diagnostic.
- **Decides:** a predeclared screening→confirmatory campaign on Vein Miner,
  using the same 15% gate; threshold, pair count, and seed fixed before the
  first arm.

### H1: fuse across the fork barrier (dead on current evidence)

Make fused regions eligible inside forked contexts, so real selector-heavy
tick functions can fuse.

- **Evidence for:** it was the single largest structural gap the static census
  showed; PERF-016 proves the fused engine wins ~15% on its own workload when
  it fires.
- **Evidence against:** the attribution shows runtime forked samples at
  0.0–0.2% on all three profiled packs, and the hot Vein Miner `execute` chain
  is non-forked. Every fused gain so far is on synthetic workloads; the
  real-workload result is flat; fork-interior fusion must preserve per-entity
  execution order, fork budget, and quota semantics exactly.
- **Prediction:** fork-interior fusion is implementable with exact parity
  (provable in the ten-arm matrix first), but it has no measured >15% pool on
  these packs.
- **Code surface:** `FusedRegionPrototype` (248 lines) + the execution-context
  bridge's fork handling; medium implementation, highest correctness risk.
- **Decides:** not pursued. Reopen only if a new workload shows a >15% runtime
  forked-leaf share; then the ten-arm matrix is the entry gate before any
  campaign.

### H3: storage-holder ScoreAdd (deprioritized)

Widen ScoreAdd beyond literal `#` holders to storage- and entity-relative
score commands.

- **Evidence for:** the `execute store result score` shapes are proven and
  measured (SCORE-007) and uncovered by any specializer.
- **Evidence against:** ScoreAdd shows no reliable gain even where it *does*
  fire (instrumented Vein Miner: 4,212 `#ray` + 1,952 `#head` calls per event,
  no speedup; full-function 5M-action workload 14.8% slower); PERF-005/006
  found no sample-share reduction on adjacent NBT/selector work. Widening a
  mechanism that has never shown a gain widens a cost, not a win.
- **Prediction:** revisit only if the H2-first inventory shows storage-holder
  adds dominating a real hot path.

### Explicitly not proposed

- Re-running the negative designs (roadmap step 4's own rule): the fused
  real-workload campaign and the bytecode-vs-fused comparison are decided.
- A new execution backend (bytecode's investigation is answered).
- Predicate-family widening: FR-03's real-datapack run is mostly failing and
  PERF-005/006 measured no reduction.

## 5. Recommended sequence and decision framework

1. **H2-first (done, batches 22–23).** The census ranks the pinned packs by
   addressable specialized work and finds that every one has adjacent eligible
   tick-path runs; Vein Miner ranks first, and its native event already compiles
   164 fused regions and executes 718 of them. Eligibility is therefore not the
   binding constraint — the share of tick time is. See §3.1.
2. **Time-share attribution (done, batch 23).** Fresh Spark samples on Vein
   Miner, Spawn Animations, and Dynamic Lights show H1's runtime fork pool at
   0.0–0.2%, while Vein Miner's macro-argument construction is 27.4% wall /
   29.4% active — the only >15% pool. See §3.2.
3. **H4 campaign (screening passed; confirmatory next).** Run compiler-off vs
   the shipped selective-macro default on Vein Miner side 6. The gate is event
   completion (`operation_completion_seconds`) at a 15% minimum median
   reduction with the 95% exact paired interval entirely beyond it; the
   post-event `tick_average_ms` is reported alongside as corroboration, not as
   the decision. Design: five screening pairs, then a predeclared ten-pair
   confirmatory campaign, seed 26871031, counterbalanced arms, exact workload
   parity in every pair. The campaign start enforces the declared
   quiet-window host gate with per-arm settles and a repeat-once noise rule.
   A one-time metrics-on activation diagnostic proves the
   fast path fires; the timing arms are uninstrumented. A negative result is
   recorded as data and stops coverage widening. The existing mechanism covers
   11,701/11,701 calls with zero fallbacks, so this is a campaign, not a code
   extension.
4. **H1 is not pursued.** Runtime forked samples are ~0 on all three profiled
   packs, and the hot Vein Miner path is non-forked. Reopen only if a new
   workload shows a >15% runtime forked-leaf share; then the ten-arm matrix is
   the entry gate.

Decision framework is the existing one, now mechanically available through
the extracted harness (`mc-harness` 1.0.0): predeclared seed, pair count fixed
from screening variance before the confirmatory's first arm, the exact-median
interval deciding `meets_threshold` / `does_not_meet_threshold` /
`inconclusive`, the no-regression floor reported alongside, and no default-on
status without a cleared gate.

## 6. What this proposal authorizes

Nothing. It is input to a decision, not a plan of record: the roadmap's steps
remain the committed work, and any hypothesis here still needs its sizing
validated against the code, its fixtures written, and its campaign predeclared
before an implementation change begins. The roadmap's §6.3 step 4 ("find a
workload whose hot path is dominated by successful specialized runs, or
document the mechanism as measured-but-unpromoted") stays open until the H4
real-workload campaign produces a decision.
