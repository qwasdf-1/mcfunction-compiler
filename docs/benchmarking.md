# Benchmarking protocol

**Protocol version:** 1.0

This page defines the shared performance-test contract for Function Compiler.
Use it for each optimization so controlled tests, real datapack profiles, and
future candidates produce comparable evidence. The current workload and result
log is [PERF-010/011](research/real-world-profile-targets.md); runnable commands
and retained reports are indexed in [benchmarks/README.md](../benchmarks/README.md).

## What a result can claim

State the optimization mechanism, target Minecraft build, mod stack, workload,
and primary metric before collecting confirmatory results. A result supports a
claim about that tested mechanism and workload. A general claim can be built
from a small, deliberately representative workload set; it does not require
testing every datapack. One synthetic workload alone demonstrates behavior
under controlled conditions, while one real datapack alone can be peculiar to
that pack. Pair the two when practical.

Do not treat a Spark sample reduction as elapsed-time reduction. Spark samples
call paths and attributes sampled CPU; it does not report exact per-function
time or invocation counts. Minecraft `/tick query` summarizes its latest 100
ticks and is not aligned automatically to a Spark window or a short event. Use
it as corroborating whole-server context, not as the primary timer for a brief
burst. If whole-server MSPT is the claim, sustain the controlled workload over
the measured ticks and capture those tick durations while it is active.

## Evidence gates

Every optimization follows these gates in order:

1. **Semantic parity.** Compare against official mod-free vanilla 26.3 for the
   supported command/context. Compare the same mod stack with the candidate
   disabled and enabled. Check final state, results, errors, callbacks,
   ordering, quota behavior, and trace behavior relevant to the candidate.
2. **Path activation.** Prove that eligible work reached the candidate and
   unsupported work used the original path. Use counters only in a separate
   diagnostic arm; counters and wrappers can perturb timing.
3. **Workload integrity.** Assert the work completed in every arm: exact
   iteration count, datapack work counter, queue delta, resulting blocks/data,
   and completion state as applicable. A run that fails this gate is a
   compatibility result, not a performance comparison.
4. **Performance measurement.** Run the uninstrumented paired comparison only
   after the first three gates pass. Preserve each trial and report variation,
   not only a pooled average.
5. **Promotion decision.** Apply the minimum worthwhile improvement selected
   for that optimization before confirmatory trials, and check regressions in
   secondary metrics. This project has no universal percentage threshold; the
   threshold is per optimization and must not be chosen after looking at the
   confirmatory results.

## Workload types

### Controlled mechanism workload

Build a small deterministic datapack fixture that repeatedly exercises the
specific code path. Keep the fixture checked in under `tests/fixtures/` and
drive it through a dedicated runner. This isolates call count, relevant input
size, irrelevant input size, fallbacks, and per-tick load. It should include:

- an eligible path that runs enough times to measure;
- ineligible shapes that must fall back;
- exact observable state and work counters;
- low-load and sustained-load configurations where tick impact is relevant;
- a vanilla arm, same-stack compiler-off arm, and same-stack candidate arm.

For selective macro arguments, the controlled fixture should call
`function ... with entity @s data` repeatedly, vary the number and size of
unrequested custom-data fields, and assert the requested macro arguments and
fallback behavior. Its result isolates the entity-serialization mechanism; it
does not replace a real datapack profile.

The first sustained fixture is
[`function_compiler_selective_macro_perf`](../tests/fixtures/function_compiler_selective_macro_perf/pack.mcmeta).
It models Vein Miner's queue call with 256 marker entities, each carrying a
216-entry coordinate frontier plus a `head` parameter. Each active tick makes
one macro call per marker, so all 256 calls have distinct parameter tuples;
this exercises the eight-entry macro cache under churn as well as the large
entity-data serialization. The runner warms for 100 active ticks, then obtains
`/tick query` after at least 110 more active ticks so its latest-100-tick
summary is entirely inside the workload. Primary runs have no Spark agent,
compiler counters, or timers. A separate candidate diagnostic verifies every
eligible call reached selective argument construction.

`function_compiler_fused_sustained` is the adjacent-eligible fused-region
counterpart ([`PERF-016`](../benchmarks/PERF-016-sustained-fused-region-active-tick.md)):
a pristine contiguous block of 5,000 eligible adds per active tick, instrumented only
by generated tick counters and an enable gate so the measured command block is
untouched. Its runner is the first to sample several full tick-query windows per arm
and aggregate them with a per-label median, which keeps one GC pause or JIT hiccup
from defining an arm; its primary metric is the workload-attributable tick average
(active phase minus the same server's post-workload idle phase).

Run a five-pair screen on the pinned Lithium+Bellows 1.1.3 stack with:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_selective_macro_sustained.py \
  --stack lb113 --pairs 5 --phase screening
```

The runner starts a standalone vanilla reference, a separate activation
diagnostic, then randomized same-stack compiler-off/candidate pairs in fresh
worlds. It checks exact calls and work per active tick against vanilla and
records active and idle tick average, P50, P95, and P99. For a confirmatory
campaign, use the 15% minimum worthwhile active-tick-average improvement
selected for this stack and size the paired sample from the screening spread;
the 95% exact median interval must support at least that gain. Do not treat a
short smoke or a post-workload tick query as a promotion result.

### Real datapack workload

Pin the exact archive and SHA-256. Confirm that the selected datapack function
actually reaches the candidate path, then verify native work before comparing
compiler modes. Prefer one or more workloads that exercise the mechanism under
different call structures. Do not add unrelated packs just to increase the
count. For example, Vein Miner is useful for entity-data macro arguments; a
2026-11-03 static screen found adjacent candidate runs in its family detection,
but they have no runtime activation or performance evidence, so it cannot yet
establish fused-region or bytecode performance.

### Mod-stack workload

Treat each mod set and version as its own target. Keep both compiler-off and
candidate-on arms on the same stack; keep a mod-free vanilla reference for
semantic checks. Pin every jar by filename and hash. If a mod/datapack
combination fails its native workload gate, exclude it from compiler
performance comparisons and record the compatibility failure separately.

## Trial procedure

1. Record the hypothesis, candidate, exact workload, primary metric, secondary
   metrics, target threshold, and trial plan before the confirmatory run.
2. Use identical seeds, world state, player actions, datapack settings, JVM
   flags, server properties, view/simulation distance, and mod versions across
   each pair. Start each arm in a fresh disposable server directory unless the
   experiment specifically measures warm state or reload behavior.
3. Apply the same readiness gate and warmup to both arms. Randomize or
   counterbalance arm order within each pair so temperature, JIT warmup, or
   background load does not always favor one side.
4. Record primary metrics per pair, plus absolute values. Retain all raw trials,
   including slow runs and failures; do not silently drop outliers. A failed
   workload-integrity run is invalid for speed comparison but remains part of
   the compatibility record.
5. Keep primary timing runs free of Spark sampling and compiler counters.
   Capture Spark call trees and activation counters in separate diagnostic
   runs using the same fixture and stack. If an in-server timer is needed,
   measure timer-only overhead in a separate arm. Older campaigns that timed
   events while Spark sampling was active must say so and are not equivalent to
   the unprofiled timing arm.
6. Use an initial five-pair campaign as a screening pilot only. Before the
   confirmatory run, select both the per-optimization minimum worthwhile gain
   and the paired sample size, using pilot variance and the effect to be
   distinguished. Record both in the campaign report before its first trial.
   Report paired median change, full pair range, and a paired confidence
   interval with achieved coverage. The shared helper
   [`scripts/paired_benchmark_analysis.py`](../scripts/paired_benchmark_analysis.py)
   calculates a distribution-free exact order-statistic interval for the
   median paired change. For a metric where lower is better, the interval must
   lie entirely at or beyond the preselected gain to meet the threshold. An
   interval that overlaps the threshold is inconclusive; an interval entirely
   above it does not meet the threshold. With five pairs, the maximum
   two-sided coverage is 93.75%, so screening results are descriptive. The
   runner refuses confirmatory campaigns with fewer than six pairs; six is
   only the minimum for a nominal 95% interval, not a recommended sample size.
   Choose the actual count from pilot spread and the preselected practical
   effect.
7. Re-run semantic and workload-integrity checks on any changed artifact,
   profile, runner, or optimization code before reusing its performance data.

`run_veinminer_campaign.py` implements this for the current real datapack
comparison. A five-pair screening run is:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_veinminer_campaign.py \
  --stack fabric --side 6 --candidate selective-macro --phase screening \
  --pairs 5 --seed 26871028 --capture-timeout 60
```

For a confirmatory run, set the threshold for that optimization and choose the
pair count from the pilot before starting. Both arguments are required, the
count must be at least six, and the report records them before the first server
arm:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_veinminer_campaign.py \
  --stack fabric --side 6 --candidate selective-macro --phase confirmatory \
  --minimum-gain-percent <preselected-percent> --pairs <preselected-pairs> \
  --seed 26871028 --capture-timeout 60
```

The campaign runner uses `--no-spark` for event timing. Its Spark call-tree
evidence comes from separate profiles and must remain labeled as sampled CPU
attribution, not elapsed time.

## Extension contract for each optimization

Keep a shared analysis method and let each optimization own its workload
adapter. A new candidate should add or update these pieces:

1. A checked-in deterministic fixture under `tests/fixtures/<feature>/` with
   exact expected effects and enough repeated work for measurement.
2. A vanilla differential case and same-stack compiler-off/candidate-on
   correctness arms in the runtime harness. Cover candidate activation and
   fallback in a separate diagnostics run.
3. A disposable per-arm runner that pins the game, loader, mods, workload and
   hashes; warms both arms the same way; checks exact work completion; records
   absolute measurements and environment details; and preserves failed-run
   evidence.
4. A paired campaign adapter that randomizes arm order and calls
   `paired_benchmark_analysis.py`. Keep optimization-specific setup and
   assertions local to the adapter; use the same paired analysis fields,
   confidence rule, and report meanings across candidates.
5. A maintained result page linked from `benchmarks/README.md`, the relevant
   correctness/benchmark matrix rows, and `docs/current-state.md`.

Use three workload classes where they fit: the controlled mechanism fixture,
one or more real datapacks with an eligible live call path, and separately
identified mod-stack runs. A synthetic fixture proves the mechanism in a
controlled setting; a representative real pack shows that the mechanism
matters in a real call graph. Do not require every datapack or mistake one
pack-specific compatibility failure for general support behavior.

Spark should answer “which call paths consumed sampled CPU?” Event-completion
or server-thread timing should answer “how long did the selected work take?”
Tick-duration capture should answer “what changed in tick time while the
workload was active?” Keep those measurements distinct in reports.

## Reusable report record

Every campaign report should preserve these fields, whether stored as JSON or
documented in a result page:

| Group | Required fields |
|---|---|
| Claim | Optimization, hypothesis, primary metric, practical threshold, known risks |
| Target | Minecraft, Java, loader/API, OS/CPU, JVM flags, server properties |
| Artifacts | Server, mod jars, datapack and Spark filenames plus SHA-256 hashes |
| Workload | Fixture or archive, seed, scenario, readiness gate, warmup, expected work and final-state assertions |
| Arms | Arm name, mod stack, compiler setting, candidate setting, instrumentation state |
| Trial | Pair number, randomized order, start/end timestamps, work integrity, absolute metrics and units |
| Analysis | Paired deltas, median, range, confidence interval, excluded/failed arms and reason |
| Decision | Screening/confirmatory, pass/fail/inconclusive, limitations, next action |
| Reproduction | Command line, runner revision, local raw-report/profile location |

Use fresh run IDs and unique report paths. Raw profiles and temporary server
worlds remain local under ignored `build/` and `run/`; summarize the evidence
in maintained docs, then remove stale generated outputs after the run ends.

## Current evidence limits

PERF-011 has five randomized pairs per stack for Fabric, Lithium, and
Lithium+Moonrise. Those historical event timings used Spark sampling; separate
no-Spark timing runs are now used for primary comparisons. A five-pair no-Spark
screen on Lithium+Bellows 1.1.3 passes exact workload parity and has an
−18.83% median selective-macro event-completion change, but its exact 93.75%
interval spans −20.62% to +24.37%, so it remains screening evidence. The
post-event `/tick query` values do not establish active-workload MSPT. The new
PERF-012 now models Vein Miner's queue more closely: 256 marker entities, each
with a changing `head` value and a 216-entry coordinate frontier. Two complete
smoke pairs and four pairs from an interrupted five-pair campaign all pass
exact vanilla work parity. Pooled as exploratory observations, the six pairs
have a −82.25% median active-tick-average change and a 96.875% exact median
interval from −86.57% to −1.81%. That interval does not establish the selected
15% minimum gain; the five-pair campaign also lacks its final pair and has no
standalone campaign decision. See [PERF-011
evidence](research/real-world-profile-targets.md#selective-macro-prototype-and-randomized-perf-011-comparison)
and [PERF-012 evidence](../benchmarks/README.md#perf-012-sustained-selective-macro-active-tick-fixture).

ScoreAdd has no reliable real-datapack gain. Selective macro has a confirmed
faster median on Lithium+Bellows 1.1.3 Vein Miner (−19.27%, 96.531% interval
−27.09% to −13.03%), but does not establish the preselected 15% minimum. Keep
it disabled pending a result that meets the practical threshold and the
remaining semantic and compatibility gates. Fused interpretation now has a
controlled adjacent-eligible workload (`PERF-016`): a 10-pair confirmatory
Fabric campaign passed exact workload parity and exact region activation, but
its −19.72% median workload-attributable tick-average change has a 97.85%
interval of −30.30% to −12.90% that overlaps the preselected 15% minimum, so
it is inconclusive rather than qualifying. It is one synthetic workload on one
stack. A 2026-11-03 static screen found adjacent candidates in several pinned
packs, but none has runtime-confirmed specialization or performance evidence.
Emitted bytecode has semantic and reload-retention evidence but no real-workload
performance result. Keep ScoreAdd, fused interpretation, and emitted bytecode
disabled while their relevant workload and confirmatory performance gates remain
open.
