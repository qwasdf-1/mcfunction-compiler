# Compiler coverage-widening proposal (v0.1)

**Status: proposal for decision; first step complete (batch 22). Nothing in this
document ships, and the [v1 roadmap](v1-production-roadmap.md) remains the plan
of record. This is the scoping work the roadmap's step 4 and the batch-19
performance record called for: with every parity case closed and all four
mechanisms' gates decided, the question is no longer "is the compiler correct"
(answered: yes, on the enumerated families) but "which additional shapes are
worth compiling", and that is a research question this document frames rather
than answers. The H2-first census is done and refines the diagnosis in §3.1:
the specializers do fire on real packs; the open constraint is tick-time share,
not eligibility.**

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
pack has adjacent eligible runs on its tick path (Vein Miner 250 commands in 23
runs, Spawn Animations 143 in 35, Dynamic Lights 14 in 4, Everything Clings 8
in 2), and a native Vein Miner event compiled 164 fused regions and executed
718 of them while the engine stayed on the vanilla-parity path (63/63 work,
480 queue-head increments). The fork barrier is real — 23.0% of Vein Miner's
reachable `execute` lines are forked, 19.0% in Spawn Animations, 25.0% in
Everything Clings, 18.3% in Dynamic Lights — but the non-forked pool is large
enough that "the specializers never fire" is not supported. The recorded
real-workload result is still flat (+0.69% median, interval −3.92% to +2.74%,
`does_not_meet_threshold`), so the binding constraint is **the share of tick
time the addressable work represents**, not its existence. The macro-extension
pool is also narrow in these packs: 10 `function ... with` call sites in Vein
Miner tick functions, none in the other three.

This weakens H1's premise (the existing non-forked engine already fires on the
top-ranked pack and does not move the real workload) and narrows H4's measured
addressable pool. The next decision needs a time-share attribution, not more
static coverage.

## 4. Candidate hypotheses

Each is stated with its evidence, its falsifiable prediction, its code
surface, and the campaign that would decide it. Effort estimates are for
scoping only and are to be validated against the code before any commitment.

### H2-first: instrument before building — inventory what actually fires

The cheapest real next step is not new compiler code: it is a **metrics-only
pass** over the pinned real-datapack workload family (Vein Miner, Dynamic
Lights, Everything Clings) counting eligible-region candidates, specialized
commands, and macro-argument hits per tick. The 2026-11-03 static screen
established that candidates exist statically; nothing has measured whether
they execute.

- **Prediction:** at least one pinned pack has a hot tick path with ≥2 adjacent
  eligible non-forked commands or a large selective-argument-construction
  share; the inventory ranks the packs by addressable work.
- **Code surface:** `ProbeMetrics` counters only; no behavioral change; days.
- **Decides:** whether H1/H3/H4 are worth any implementation at all, and which
  pack each candidate campaign should run on.
- **Falsified if:** every pinned pack's eligible work is either forked (H1
  only) or below the measurement floor of the tick average (all candidates
  dead).

### H4: extend the one mechanism that has already cleared its gate

Selective macro arguments avoids full entity/storage serialization when a macro
function reads a small set of top-level custom-data or storage fields. Other
per-entity expansion families plausibly share that shape: NBT path
construction, coordinate-list templates, `data modify` chains inside macro
bodies.

- **Evidence for:** it is the only cleared-gate mechanism; its cost model
  (avoid serializing a large compound to read a few fields) is shape-general.
- **Evidence against:** none measured — the extension is unmeasured by
  definition, and the inventory (H2-first) has not yet ranked these shapes.
- **Prediction:** a second selective family covering the next-largest
  per-entity expansion share in a real pack clears 15% on that pack's workload.
- **Code surface:** `SelectiveMacroArgumentPrototype` (182 lines) +
  `MacroTemplateCompiler` (60 lines); small extension of a proven mechanism;
  the semantic invariant is unchanged (the same macro result, computed
  without full serialization).
- **Decides:** a screening→confirmatory campaign on the pack H2-first ranks
  first, using the same predeclared 15% gate.

### H1: fuse across the fork barrier (highest value, highest risk)

Make fused regions eligible inside forked contexts, so real selector-heavy
tick functions can fuse.

- **Evidence for:** it is the single largest structural gap the measurements
  show; PERF-016 proves the fused engine wins ~15% on its own workload when it
  fires; batch 15's fork-limit defect shows fork-bookkeeping is exactly where
  subtle vanilla-parity bugs live.
- **Evidence against:** every fused gain so far is on synthetic workloads; the
  real-workload result is flat; fork-interior fusion must preserve per-entity
  execution order, fork budget, and quota semantics exactly — the fork-limit
  defect was found *because* that boundary is thin.
- **Prediction:** fork-interior fusion is implementable with exact parity
  (provable in the ten-arm matrix first), and a real-pack workload whose hot
  path is fork-interior eligible shows ≥15% active-tick reduction.
- **Code surface:** `FusedRegionPrototype` (248 lines) + the execution-context
  bridge's fork handling; medium implementation, highest correctness risk;
  the ten-arm differential matrix is the entry gate before any campaign.
- **Decides:** a fork-interior fixture (the matrix already has the fork-limit
  and fork-order fixtures to build on) passing in all arms, then a pair
  campaign on the H2-first-ranked pack.

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

1. **H2-first (done, batch 22).** The census ranks the pinned packs by
   addressable specialized work and finds that every one has adjacent eligible
   tick-path runs; Vein Miner ranks first, and its native event already compiles
   164 fused regions and executes 718 of them. Eligibility is therefore not the
   binding constraint — the share of tick time is. See §3.1.
2. **Time-share attribution (next).** Map the census's addressable functions to
   existing or fresh Spark samples per pack. This is the measurement that can
   decide whether any candidate has enough hot share to clear the 15% gate; a
   command census cannot.
3. **H4 (the low-risk extension) only if step 2 shows a macro-shaped hot share
   that can clear 15% on the pack it ranks first.** Screening→confirmatory with
   the predeclared minimum and 95% interval; a negative result is recorded as
   data.
4. **H1 only if step 3 fails**, and only behind the ten-arm matrix gate for the
   fork-interior fixture.

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
document the mechanism as measured-but-unpromoted") stays open until one of
H2-first, H4, or H1 produces a campaign decision.
