# Benchmarks

All optimization performance experiments follow the shared
[benchmarking protocol](../docs/benchmarking.md). Five-pair campaigns are
screening pilots. Before a confirmatory campaign, set that optimization's
minimum worthwhile gain and sample size, then record both before the first
trial. Use the shared paired analysis helper for median changes and uncertainty.

Do not claim a compiler speedup until correctness is established for the exact
workload and target. Keep workload fixtures, environment manifests, raw results,
and analysis reproducible. Report independent-run distributions, allocation and
reload costs, fallback coverage, and regressions as well as gains.

## Measurement roles

Use [Spark](https://spark.lucko.me/) for real-world CPU sampling, server-thread
call trees, health/TPS reports, and separate allocation profiles. The
[standalone Java agent](https://spark.lucko.me/docs/Standalone-Agent) supports
an unmodded vanilla server and applies Minecraft mappings there. This project
pins Spark 1.10.194 and uses the same standalone agent across vanilla and
Fabric arms. CPU profiles sample all threads at 4 ms; a separate allocation
capture uses Spark's 524287-byte interval. Spark's
[command reference](https://spark.lucko.me/docs/Command-Usage) documents
sampling, thread targeting, allocation, and local profile saving.

Spark samples call paths; it does not provide exact invocation counts or exact
per-function elapsed time. Record Minecraft's /tick query separately for
whole-server MSPT percentiles over its latest 100 ticks. For exact compiler
claims, add a low-overhead in-server timer/counter around the measured region,
keep instrumentation-only as a distinct arm, and measure its overhead. The
real-world profile setup uses the same useful split found in Terra Rasa and
Soul Link: disposable server directories, exact-server-derived packet IDs,
headless players and RCON orchestration, plus narrow System.nanoTime timing
only for bounded project code.

PERF-005/006 uses a denser controlled fixture and samples all threads at 1 ms;
see the [Bellows selector and entity-NBT report](PERF-005-006-bellows-selector-nbt.md).

For private or local datapacks, save profiles to disk and do not upload them.
The .sparkprofile files can be opened in the [Spark viewer](https://spark.lucko.me/).

## PERF-001: warm scoreboard baseline

Run scripts/run_perf_baseline.py from the project root. It executes a fixed
5,000-line scoreboard function for 50 warmup calls and 1,000 measured calls,
validates the final score, and stores JFR, server log, and metadata under the
ignored build/benchmarks/PERF-001 directory. Its RCON round-trip timings are
orchestration data only; they are not command-throughput measurements.

The first exploratory capture ran 5.25 million scoreboard updates and recorded
one second of warmed JFR data with 101 execution samples. Leading sampled
methods in that run were ObjectArrayList.grow (31.7%), HashMap.getNode (15.8%),
CommandContext.getArgument (6.9%), and
ExecutionContext.pushNewCommands (5.9%). A separate exploratory run had a
different leading method. Treat these samples as inspection leads, not a
stable profile or performance claim. Spark 1.10.194 was also validated against
the fixture with a local 200-call profile.

Useful JFR views:

- jfr view --width 160 hot-methods build/benchmarks/PERF-001/vanilla-scoreboard.jfr
- jfr view --width 160 allocation-by-site build/benchmarks/PERF-001/vanilla-scoreboard.jfr

## PERF-005/006: Bellows selector and entity-NBT workloads

Five randomized repetitions compared official vanilla, Fabric with compiler
features off, Bellows with compiler features off, fused interpretation, and
Bellows plus fused interpretation. All 25 server arms passed their normalized
output checks against vanilla. Bellows lowered the sampled function share on
the controlled entity-NBT workload in all five paired trials. The fused
compiler prototype showed no repeatable sample reduction, and its whole-server
tick timings were variable; keep it disabled. The detailed report contains
per-mode tick percentiles, paired changes, raw-run location, fixture limits,
artifact hashes, and hardware details.

Run `python3 scripts/run_bellows_selector_nbt_benchmark.py` for five
repetitions, or pass `--repetitions 1 --seconds 3` for a harness pilot. The
default run saves all-thread Spark profiles at 1 ms and keeps raw reports under
the ignored `build/benchmarks/PERF-005-006/` directory. Pilot results are for
harness validation only and must not be used as performance evidence.

## PERF-010: real datapack profiles and staged arms

Candidate workloads must have a pinned artifact and a workload path that
actually runs on Minecraft 26.3. Keep world-generation studies separate from
tick/function profiles because mods such as Moonrise also change chunk
generation.

| ID | Candidate | Status |
|---|---|---|
| RW-01 | A pinned [Animated Java](https://animated-java.dev/docs/core-concepts/blueprints) export | Candidate; select and hash one export and fix rig count and animation state. |
| RW-02 | [Incendium Legacy](https://modrinth.com/datapack/incendium) | Excluded unless Stardust Labs grants permission: its license prohibits using its works to test or debug AI systems. |
| RW-03 | [Tschipcraft Spawn Animations](https://modrinth.com/datapack/spawn-animations/) 1.11.6 | Six-second vanilla burst pilot: 24 zombies remained, six were active at start and none at end; all-thread Spark profile had 47 nodes and 288 ms weighted `ServerFunctionManager.execute`. Repeat with waves and pack-off controls before comparison. |
| RW-04 | Dynamic Lights by darpanshete 1.0.0 | Rejected: invalid pack metadata and unresolved load/tick functions on the exact server. |
| RW-05 | Deeper Dark or Tschipcraft Dynamic Lights | Defer until an exact artifact compatible with 26.3 is available. |
| RW-06 | [Dynamic Lights by CreepermeYT](https://modrinth.com/datapack/dynamic-lights-creepermeyt/version/v1.4.6-mc1.17.x-26.3) 1.4.6 | Selected as a recurring command/selector workload; absolute server cost is not established. Vanilla and Fabric arms pass workload checks; Bellows-containing arms do not. See [the PERF-010 profile report](../docs/research/real-world-profile-targets.md). |
| RW-07 | [Everything Clings](https://modrinth.com/datapack/everything-clings) 1.0.0 | Loads and has valid Spark trees, but the controlled entity population fell 8→2 in 2–4 seconds and 32→12 in 18 seconds. Defer matched profiles until the fixture retains its actors. |
| RW-08 | [Bigger Every Kill](https://modrinth.com/datapack/bigger-every-kill) 1.0.0 | Rejected: exact archive fails official 26.3 registry loading because its advancement JSON has the wrong `conditions.entity` shape. Do not profile until an upstream fix is available. |
| RW-09 | [Blastback](https://modrinth.com/datapack/blastback/version/dMtA8r0n) Hotfix 3 | Its 1-TNT event still fails the restoration gate after a 180-second profile plus a five-minute drain. A separate no-TNT dispatcher profile now passes two same-stack Fabric compiler-off/ScoreAdd pairs and compiles one ScoreAdd in `erb:runtime_tick`; this only validates a light recurring path and is not event-workload evidence. |
| RW-10 | [Datapack Function Library](https://modrinth.com/datapack/datapack-function-library) 5.1.0 | Exact 26.1–26.3 artifact pinned for screening. It ships with no tick tag and no direct literal fake-holder ScoreAdd entry, so it is not an active optimizer workload without a host datapack. |
| RW-11 | [Vein Miner](https://modrinth.com/datapack/vein_miner) 5.3.0 (`vein_miner`, underscore) | Pinned 26.3 archive with three direct fake-holder ScoreAdd sites. Native 6×6×6 mining passes five randomized compiler-off/ScoreAdd pairs on Fabric, Lithium, and Lithium+Moonrise 1.2.1. None shows a reliable gain; Bellows-containing compiler-off runs fail workload integrity and are excluded as comparisons. The similarly named [VeinMiner](https://modrinth.com/datapack/veinminer) project is separate; its V1 datapack is not the PERF-011 target and has no direct fake-holder ScoreAdd site. No adjacent pair exists for fused/bytecode coverage. See [PERF-011 evidence](../docs/research/real-world-profile-targets.md#vein-miner-530-native-trigger-eligibility-and-profile-pilot). |

Run the Dynamic Lights harness with python3 scripts/run_dynamic_lights_profile.py.
It pins the server, datapack, Spark agent, and selected mod jars by hash,
generates packet IDs from the exact server jar, creates four headless players
and 24 stationary torch items, waits for workload readiness, captures Spark,
and records the post-capture /tick query. Each run uses a fresh disposable
server directory under run/; successful shutdown removes it. Profiles and
manifests remain local under the ignored build/benchmarks/PERF-010 directory.
Place the pinned local artifacts under references/real-world as expected by
the runner.

Run modes:

- --mode cpu samples all threads at 4 ms for 18 seconds by default and rejects
  a saved profile with zero thread sample nodes.
- --mode alloc captures a separate allocation profile.
- --mode idle attaches Spark but leaves sampling idle for an overhead control.
- --wrapper off/on selects the Function Compiler delegating-wrapper probe on
  Fabric runs; it does not enable an optimization.

The supported stacks are vanilla, fabric, lithium, bellows, lb
(Lithium+Bellows), lm (Lithium+Moonrise), lbm (Lithium+Bellows+Moonrise 1.2.1),
and lbm120 (the same stack with Moonrise 1.2.0). The exact pins and results are
in the [profile report](../docs/research/real-world-profile-targets.md).

The earlier CPU captures selected `Server thread`, but the standalone agent
resolved that filter to an empty thread set. Those files contain metadata and
health metrics, not CPU call trees. The runner now samples all threads,
requires nonempty thread nodes, counts its startup-settle period inside the
requested duration, and stops Spark before post-profile RCON checks.

Three fresh vanilla datapack-on/off pairs now contain valid call trees. Their
median P50/P95/P99 MSPT was 6.4/9.7/12.0 with the datapack and 4.9/7.6/9.7
without it, but one pair reversed sharply. All three on profiles show
`FunctionCallback.handle` and `ServerFunctionManager.execute` at 716–756 ms of
weighted sample time; the off trees have no scheduled datapack function path.
This establishes a recurring command workload, while the MSPT deltas remain
too variable for a stable cost estimate or optimization claim. The exact
profile IDs and caveats are in the [PERF-010 report](../docs/research/real-world-profile-targets.md).

Corrected all-thread CPU profiles now exist for one datapack-on wrapper-off/on
pair each on Fabric, Lithium, and Lithium+Moonrise. They contain 44–47 thread
nodes, preserve the 24 torch sources, and sample
`FunctionCallback.handle` → `ServerFunctionManager.execute`. Weighted
`ServerFunctionManager.execute` samples are 812/756 ms for Fabric, 524/1,960
ms for Lithium, and 620/772 ms for Lithium+Moonrise. These are one-pair
capture-path pilots, not wrapper-cost or optimization results; post-profile
MSPT varies sharply and each stack still needs datapack-off controls and
repeats. Bellows and Lithium+Bellows kept source items tracked but produced no
torch-source tags or light markers. Bellows 1.1.2 with Moonrise 1.2.1 fails
server startup; Moonrise 1.2.0 starts but still produces no datapack output.
Exclude those invalid workload arms from performance comparisons. Wrapper
probe invariants pass on the tested wrapper-on stacks, including incompatible
workload arms; wrapper lifecycle success does not make their datapack output
comparable. Details and run IDs are in the [PERF-010 report](../docs/research/real-world-profile-targets.md).

Behavior parity remains a separate hard gate. Use mod-free vanilla 26.3 as the
semantic reference and compare the same mod stack with the compiler disabled
and enabled. If a mod changes behavior, record the difference and resolve a
compatibility policy or adapter before enabling an optimization on that path.

The first valid on/off Spark trees have been inspected. Do not infer an
optimization from the MSPT values alone. Repeat valid arms with more
randomized order and vary movement/entity load before ranking the workload's
absolute cost. The [profile report](../docs/research/real-world-profile-targets.md)
contains capture IDs, workload checks, and exact compatibility failures.

## Candidate datapack workloads

Candidate classes and artifact evidence are in the
[tick-heavy datapack research](../docs/research/tick-heavy-datapack-candidates.md).
Blastback's first 1-TNT profile passes exact-target loading and samples the
scheduled-function path, but fails its full restoration gate: after a
180-second profile and a five-minute drain, its 17x17x17 source volume still
differs from the cloned template, with 3,273 saved-block markers and active
restore/protected-item state. Keep the 4- and 32-TNT cases deferred. Its
separate no-TNT dispatcher mode passes two compiler-off/ScoreAdd pairs on
Fabric: the exact `#tick_id` deltas match at 460 and 461 across the pairs, and
the ScoreAdd arm compiles one direct add in `erb:runtime_tick`. Inclusive Spark
samples for `ServerFunctionManager.execute` were lower in both ScoreAdd arms
(104/152 ms) than their controls (160/168 ms), but two short captures are only
a reason to repeat, not a performance decision. A separate instrumented
diagnostic counted 340 executions of that compiled entry, matching the
`#tick_id` delta; its timing is excluded from comparisons. No adjacent region
is eligible for fusion. See [PERF-010 results](../docs/research/real-world-profile-targets.md).

The Blastback diagnostic runner is `python3 scripts/run_blastback_profile.py`.
For the no-event dispatch pilot, use `--tnt-count 0 --compiler-mode off` or
`--compiler-mode score-add`; `--compiler-mode score-add-instrumented` is only
for path diagnostics because its per-command counters add overhead. This
profile still has one active group, so it is not a quiet-idle server control.
For TNT events, the runner accepts 1, 4, or 32 TNT, and the 1-TNT restoration
gate remains a prerequisite for the larger cases. The same pinned Fabric/mod
stacks are available.

Four additional randomized 12-second compiler-off/ScoreAdd pairs exercised
the normal Blastback dispatcher on Lithium, Bellows 1.1.2, Lithium+Bellows,
and Lithium+Bellows+Moonrise 1.2.0. Each pair's no-event gate passed and each
ScoreAdd arm compiled one `erb:runtime_tick` command. Tick deltas matched in
three pairs; the Lithium pair differed by one tick. Weighted
`ServerFunctionManager.execute` samples moved in both directions, so these are
path-coverage pilots and not speedup evidence. Exact pair run IDs and values
are in the [PERF-010 report](../docs/research/real-world-profile-targets.md).

PERF-011's Vein Miner 5.3.0 runner drives a native player mining event on a
pinned ore cube and verifies the datapack work counter, queue counter, block
volume, source block, and operation state. A fresh Bellows-only 4×4×4
compiler-off rerun on 2026-10-28 reproduced the stall after the native trigger
succeeded: the source was mined and the operation started, but only one queue
item was visited and all 63 remaining ore blocks remained. The same fixture
passes on vanilla and Fabric. This finding is limited to the `vein_miner`
5.3.0 artifact; it does not test the separate no-underscore Modrinth project's
V1 datapack or V2 mod. Five randomized 6×6×6 pairs each on Fabric,
Fabric+Lithium, and Fabric+Lithium+Moonrise 1.2.1 all pass exact workload-state
parity. Fabric shows no reliable ScoreAdd gain. Lithium medians trend slower
(+12.47% completion and +12.46% weighted function samples), with a +101.19%
completion outlier. Lithium+Moonrise medians also trend slower (+19.98%
completion and +21.62% weighted function samples), with wide ranges crossing
zero; both arms carried a temporary dormant diagnostic mixin. Neither campaign
establishes a stable gain or regression. A separate instrumented diagnostic
observes 4,212 `#ray` and 1,952 `#head` additions in the event. An opt-in
callback diagnostic now counts generic and optimized ordinary leaf callbacks:
one aligned 4×4×4 Lithium event counted 7,116 generic and 1,122 optimized
callbacks (8,238 total), with the optimized count matching the independent
ScoreAdd execution counter. Callback wrappers perturb execution, so these runs
are not performance comparisons. No adjacent eligible pair exists for
real-world fused/bytecode measurement. Compiler-off Vein Miner controls on
Bellows 1.1.2, Lithium+Bellows, and Lithium+Bellows+Moonrise 1.2.0 fail native
workload integrity: mining starts, but the queue advances only once, 0/63 or
0/215 ore blocks are processed, the ore remains, and the operation marker is
not cleared. These are invalid datapack/mod workload comparisons, not compiler
failures or evidence that Bellows generally breaks functions. Use a separate
workload for those stacks. See the [full PERF-011 profile
evidence](../docs/research/real-world-profile-targets.md#vein-miner-530-native-trigger-eligibility-and-profile-pilot).

The historical PERF-011 event completion measurements ran while Spark was
sampling at 4 ms. Compiler timing and path counters were disabled, but the
sampler was active, so those times are profiled comparisons. The campaign now
uses `--no-spark` for primary paired timing; run Spark separately to inspect the
call path. A 4×4×4 no-Spark selective-macro smoke run passed exact native work
(63/63 blocks, 480 queue-head increments, empty vein and cleared markers) in
3.88 seconds. It validates the timing arm and workload gate only; one candidate
arm is not a speed comparison, and its post-event tick query is not whole-server
MSPT evidence.

The Bellows 1.1.2 workload failures are version-specific historical results.
Lithium + Bellows 1.1.3 passes the full 6×6×6 compiler-off event (215 blocks,
1,952 `#head` increments, clean final state). Two separate diagnostics counted
9,546 and 9,547 selective-macro hits on that stack. Five randomized no-Spark screening
pairs for selective macro all pass exact workload parity; median event
completion changes by −18.83%, with a −20.62% to +24.37% range and 93.75%
achieved interval coverage. This remains screening evidence, not a confirmed
gain. The report is retained locally at
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-selective-macro-5pairs-seed26871029-20261029T051440Z.json`.
Its post-event tick query is not an active-workload MSPT result. A separate
five-pair ScoreAdd screen on the same stack passes every parity check but has a
+3.60% median completion change (slower) and a −2.04% to +91.11% interval. It
does not establish a regression or support promotion. Its report is retained at
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-score-add-5pairs-seed26871030-20261029T053118Z.json`.
Bellows 1.1.3 Moonrise workload checks remain open.

## PERF-012: sustained selective-macro active-tick fixture

The current controlled fixture in
`tests/fixtures/function_compiler_selective_macro_perf` models Vein Miner's
queue call with 256 marker entities, each carrying a unique `head` macro
argument and a 216-entry coordinate frontier. Each active tick makes 256
macro calls with distinct argument tuples, exercising the eight-entry macro
cache under churn and serializing the large entity data. A previous 32-armor-
stand fixture with 256 irrelevant integers was superseded after comparing it
with Vein Miner's actual marker and frontier data. Its measurements are not
pooled with the current fixture.

The runner uses no Spark or compiler timing/counters in performance arms,
warms the workload for 100 active ticks, and reads `/tick query` after at least
110 more active ticks. It also runs standalone vanilla and a separate
instrumented arm that must count every selected argument call. The selected
practical threshold for active-tick average on Lithium+Bellows 1.1.3 is 15%;
confirmation requires the 95% paired median interval to support at least that
gain.

Two complete smoke pairs and four pairs from an interrupted five-pair screen
pass exact vanilla work parity at 256 calls and 32,896 weighted work per active
tick. The six exploratory paired changes are −82.35%, −82.14%, −83.33%,
−86.57%, −1.81%, and −78.63%. Their median is −82.25%, but the 96.875% exact
median interval is −86.57% to −1.81%; it does not support a gain of at least
15%. The five-pair screen's final pair did not complete, so it has no campaign
decision. The two-pair smoke is
`build/benchmarks/PERF-MACRO-SUSTAINED/lb113-screening-2pairs-20261029T062852495318Z/results.json`;
the interrupted run, with four recorded parity-passing pairs, is
`build/benchmarks/PERF-MACRO-SUSTAINED/lb113-screening-5pairs-20261029T063844945129Z/results.json`.
Treat the pooled figures as exploratory only; selective macro remains disabled
by default pending a complete confirmatory run.

Repeat with:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_selective_macro_sustained.py \
  --stack lb113 --pairs 5 --phase screening
```

To collect callback counts, run a separate diagnostic profile (the added
wrappers make its Spark timing non-comparable). The flag also enables the
delegating wrapper when `--compiler-mode off` is selected so callback commands
can be instrumented during datapack parsing:

```sh
python3 scripts/run_veinminer_profile.py \
  --stack lithium --compiler-mode score-add-instrumented --side 4 \
  --count-command-callbacks
```
In a separate manual 26.3 check without Function Compiler, the user reports
that Vein Miner 5.3.0 works with Lithium 0.26.2 alone but stalls with
Lithium+Bellows 1.1.2; the pinned no-underscore Miraculixx VeinMiner 1.3.6
pack works with the combined stack. The only visible difference the user noted
was that 1.3.6 mines its vein in one tick while 5.3.0 spreads work across
ticks. This reinforces the
pack-specific compatibility report but is not a matched parity comparison.
Reproduce the completed Lithium+Moonrise campaign with:

```sh
python3 scripts/run_veinminer_campaign.py --stack lm --side 6 \
  --pairs 5 --seed 26871028 --capture-timeout 60
```

An interrupted report with status `running` can be resumed with the same
options plus `--resume-report <report-path>`; completed arms are retained.

Next, repeat Spawn Animations with controlled waves and a pack-off control.
Defer Everything Clings until its entity population remains stable; reject the
current Bigger Every Kill archive because it fails 26.3 registry loading.
Require exact workload checks and matched pack-off controls before comparison
profiles. Incendium stays excluded unless its upstream AI project restriction
is resolved.
## PERF-016: sustained adjacent-eligible fused-region active-tick fixture

No screened datapack contains an adjacent eligible region for the fused engine, so
`tests/fixtures/function_compiler_fused_sustained` supplies the controlled workload:
a pristine block of 5,000 contiguous `scoreboard players add #fused fc_fused 1` lines
that runs once per enabled active tick. The runner generates only tick instrumentation
(a gated call plus tick counters) into each disposable datapack copy, so the measured
command block is untouched.

Each arm samples five active 110-tick windows and three idle windows and takes the
per-label median, which removes single-window GC outliers from the arm estimate. The
primary metric is the workload-attributable tick average (active minus the same
server's post-workload idle average). Arms: mod-free vanilla reference, a separate
activation diagnostic that must count exactly one executed fused region per active
tick, and counterbalanced same-stack compiler-off/candidate pairs with no Spark and
no compiler counters or timers.

The confirmatory 10-pair Fabric campaign pre-declared a 15% minimum gain. All ten
pairs passed exact workload parity at 5,000 adds per active tick. The primary metric's
median paired change is −19.72% with a 97.85% exact interval of −30.30% to −12.90%, so
it overlaps the threshold and the campaign decision is **inconclusive**; the raw active
tick average median is −16.53% and the P95 median −18.63% as context. The 5-pair
screening pilot (single-window design) had a −22.86% median with a −86.55% to 0.00%
interval and is retained as screening only. Full results, gates, limitations, and next
actions are in
[`PERF-016-sustained-fused-region-active-tick.md`](PERF-016-sustained-fused-region-active-tick.md).
`fused_regions` stays disabled by default.

Reproduce with:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 10 --phase confirmatory \
  --minimum-gain-percent 15 --seed 26871041
```

## Compiler optimization A/B

### PERF-002: literal fake-holder ScoreAdd prototype

Run `python3 scripts/run_score_add_ab.py` to resume the pinned comparison, or
add `--fresh` to create a new report. It runs five randomized, independent
trials per arm with the same Minecraft 26.3 artifact, JVM flags, fixture hash,
quota, headless player, and Spark setup. Each trial executes 5 million
`scoreboard players add` actions after warmup and verifies the exact
post-timing score delta. The first trial per arm then captures CPU and
allocation profiles on a separate 10-million-action workload and verifies
that profile workload's score delta too. The four arms are official vanilla, Fabric with wrapper disabled,
Fabric with the delegating wrapper, and Fabric with the opt-in ScoreAdd
prototype. ScoreAdd hot-path metrics are off in timed trials. Spark CPU and
allocation profiles were captured once per arm on a separate 10-million-action
tick workload.

The specialization is narrowly limited to parsed literal fake-holder adds. It
keeps vanilla `BuildContexts`, execute scheduling, quota, trace, and result
callback machinery, and falls back to the original Brigadier command for
unrecognized inputs. Differential checks passed for the covered fixture, but
this does not establish parity for every command context or mod stack.

| Arm | Median fixture commands/s | Min–max | IQR | MAD | Ratio to vanilla |
|---|---:|---:|---:|---:|---:|
| Vanilla | 1,735,805 | 872,001–1,810,333 | 423,435 | 74,528 | 1.000 |
| Fabric, wrapper off | 1,537,356 | 1,504,709–1,580,682 | 40,940 | 24,967 | 0.886 |
| Fabric, wrapper only | 1,554,522 | 1,339,937–1,609,788 | 235,921 | 55,266 | 0.896 |
| ScoreAdd prototype | 1,735,937 | 1,471,269–1,790,464 | 262,828 | 54,526 | 1.000 |

IQR is the linear-interpolated 75th percentile minus the 25th percentile;
MAD is the median absolute deviation across the five independent trial values.

The measured rate is RCON-driven throughput, including orchestration and
dispatch; it is not exact server-thread elapsed time. The prototype median is
effectively equal to vanilla (+0.008%) and its distribution overlaps the
vanilla results. It is 11.7% above wrapper-only by median, but this comparison
does not isolate a reliable gain over vanilla.

Spark's single allocation capture per arm estimated roughly 337 B/action for
vanilla, 464 for Fabric wrapper off, 453 for wrapper only, and 401 for
ScoreAdd. These are sampling estimates, not exact allocation totals. CPU
samples show vanilla spent time in argument/name resolution that is absent from
the specialized path, but the prototype still allocates substantially and the
single capture per arm cannot establish a repeatable CPU reduction. The
prototype therefore remains disabled by default and PERF-002 remains open.

The raw trial results and eight profiles are stored locally under the ignored
`build/benchmarks/PERF-002/` directory. `scripts/analyze_spark_profile.py`
summarizes methods in a saved profile and can reconstruct matching call paths
from the Spark tree, for example `--method Entity.saveWithoutId --paths 3`.
Preserve the summarized findings here before removing generated benchmark
output under the stale-build cleanup rule.

#### Server-thread callback timer follow-up

Run `python3 scripts/run_score_add_ab.py --exact-timing` for five randomized
trials each of two matched Fabric arms. `instrument-only` wraps the original
vanilla `ScoreboardCommand` callback with `System.nanoTime`; `score-add-timed`
uses the ScoreAdd prototype under the same timer. Each trial verifies the
timed scoreboard delta and exactly 5 million timed command callbacks. Spark's
agent is attached but idle, with no sampling during this comparison.

| Arm | Median callback wall time/action | MAD | Min–max |
|---|---:|---:|---:|
| Instrument-only, delegates to vanilla | 221.14 ns | 20.13 ns | 201.00–464.30 ns |
| ScoreAdd prototype | 130.48 ns | 1.35 ns | 127.32–302.55 ns |

The ScoreAdd callback median is 41.0% lower in this fixture. The RCON-driven
throughput median was 1.51M commands/s versus 1.30M for instrument-only, but
RCON trial variation was large, so it is supporting context rather than the
primary measurement. The callback timer is enabled in both arms and includes
the timer calls and counter update; its absolute overhead was not independently
calibrated. It measures only the `Command.run` callback, excluding context
construction, queue scheduling, quota checks, tracing, and the rest of function
execution. Treat this as scoped callback evidence, not a whole-function or
vanilla-server speedup. Raw results are in the ignored
`build/benchmarks/PERF-002-timing/` directory.

The timer-only and timed-ScoreAdd arms also pass the seven-arm runtime
differential suite against vanilla, including state, command feedback, quota,
fork, macro, lifecycle, callback, and trace observations. The ScoreAdd
prototype remains disabled by default pending broader input and mod coverage,
timer-overhead calibration, repeatable allocation/CPU evidence, and a
performance decision based on whole-function measurements.

#### Earlier PERF-002 server-thread function-queue timing

The earlier two-arm comparison warmed up 50 calls, then timed 1,000 function calls
with 5,000 commands each (5 million measured actions) and verifies the exact
score delta. The test-only timer starts at `FunctionCommand.queueFunctions`
for the target fixture and stops at the corresponding
`ExecutionContext.runCommandQueue` return. It includes function
instantiation, command queue processing, quota, callbacks, and tracing, while
excluding RCON and parsing the outer `/function` command. Both arms use the
same timer; Spark's agent is attached but idle.

| Arm | Median queue time/function | MAD | Min–max |
|---|---:|---:|---:|
| Instrument-only, vanilla command delegate | 2.635 ms | 0.025 ms | 2.418–3.759 ms |
| ScoreAdd prototype | 3.024 ms | 0.403 ms | 2.232–3.427 ms |

The full-function median was 14.8% slower with ScoreAdd in this fixture. Its
RCON throughput median is also 14.4% lower, with substantial trial spread.
Each of the ten trials recorded exactly 1,000 timed function queues and the
expected 5.25-million post-warmup score. This result does not confirm the
callback-only timer's 41% reduction; it shows why callback-level timing cannot
stand in for the function execution path. The timer overhead is matched across
arms but has not been independently calibrated. ScoreAdd remains disabled,
and this result does not establish a general regression or gain beyond this
static workload. The raw trial report is under the ignored
`build/benchmarks/PERF-002-function-timing/` directory.

### PERF-003: fused interpreted-region pilot

Run `python3 scripts/run_score_add_ab.py --repetitions 3
--warmup-calls 25 --measured-calls 300 --profile-seconds 5 --fresh` to repeat
the randomized pilot. It compares vanilla, Fabric wrapper-off, wrapper-only,
ScoreAdd, and the opt-in fused-interpreted mode. Each trial verifies an exact
1,625,000-action score. Metrics are disabled during timed trials. One Spark CPU
and allocation profile per arm is captured separately; these single captures
are descriptive and do not establish a stable profile distribution.

| Arm | Median RCON-driven actions/s | Min–max |
|---|---:|---:|
| Vanilla | 1.462M | 1.429–1.698M |
| Fabric, wrapper off | 0.706M | 0.591–1.436M |
| Fabric, wrapper only | 0.951M | 0.727–1.195M |
| ScoreAdd | 1.112M | 0.854–1.339M |
| Fused interpreted | 1.496M | 0.785–1.644M |

The RCON-driven distributions are wide and overlap. The fused median is 2.3%
above vanilla, which is not enough evidence for a performance claim. Keep the
prototype disabled. Repeat with more independent trials and calibrated
server-thread timing before deciding whether this backend is useful. The exact
score checks and one CPU/allocation profile per arm are retained locally under
the ignored `build/benchmarks/PERF-002/` directory.

#### PERF-003 server-thread queue timing

Run `python3 scripts/run_score_add_ab.py --function-timing --fresh --seed 260326`
for five randomized trials of three matched Fabric arms: the vanilla command delegate,
ScoreAdd, and fused interpreted regions. Each trial warms up 50 calls, then
times 1,000 invocations of the same 5,000-command function (5 million measured
actions). The timer spans `FunctionCommand.queueFunctions` through the matching
`ExecutionContext.runCommandQueue` return. It includes instantiation, quota,
callbacks, and queue execution, but excludes RCON and parsing the outer
`/function` command. Exact scores are checked after each timed phase. Timed
arms keep ScoreAdd and fused-region counters disabled. A second independent set
uses `--seed 260327`. Both five-trial-per-arm reports are retained under the
ignored `build/benchmarks/PERF-003-function-timing/` folder.

| Arm | Median queue time/function | MAD | Min–max |
|---|---:|---:|---:|
| Instrument-only, vanilla command delegate | 3.399 ms | 0.810 ms | 2.393–4.895 ms |
| ScoreAdd prototype | 3.147 ms | 0.481 ms | 2.148–3.646 ms |
| Fused interpreted region | 2.014 ms | 0.166 ms | 1.480–2.628 ms |

Every trial executed 1,000 measured queues with 5,000 commands each and
verified the exact 5.25-million post-warmup score. Across the combined ten
trials per arm, fused queue time was 40.8% lower by median than the matched
instrument-only delegate and 36.0% lower than ScoreAdd. The direction also
held in both randomized sets separately: the fused median was 23.0% and 38.5%
below instrument-only, respectively. These are promising results for this
static 5,000-add fixture, not general or real-world performance evidence. The
timer's `System.nanoTime`/counter overhead is matched across arms but is not
independently calibrated; allocation, reload, and compatible datapack gates
remain open. Keep the prototype disabled pending those gates.

### PERF-004: emitted bytecode vs fused interpreted

Run `python3 scripts/run_score_add_ab.py --backend-comparison --seed 260328`
for five randomized server-thread full-function timing trials per arm. The
four Fabric arms are instrument-only vanilla delegation, ScoreAdd, fused
interpreted, and emitted bytecode. Each trial times 1,000 invocations of the
same 5,000-command function after warmup and verifies exactly 5,250,000
scoreboard updates. The timer spans the target function queueing and queue
completion, including instantiation, quota, callbacks, and tracing, but excludes
RCON and parsing the outer `/function` command. Timed runs leave prototype
counters disabled. Raw trial data is in the ignored
`build/benchmarks/PERF-004-bytecode-timing/results.json`.

| Arm | Median queue time/function | MAD | Min–max |
|---|---:|---:|---:|
| Instrument-only, vanilla delegate | 2.500 ms | 0.101 ms | 2.379–2.620 ms |
| ScoreAdd | 2.784 ms | 0.223 ms | 2.353–3.006 ms |
| Fused interpreted | 1.537 ms | 0.055 ms | 1.482–1.608 ms |
| Emitted bytecode | 1.890 ms | 0.060 ms | 1.727–2.267 ms |

The emitted backend was 24.4% faster than the instrument-only delegate by
median, but 23.0% slower than fused interpreted. It therefore does not justify
the extra code generation and class-lifecycle complexity for this fixture.
ScoreAdd was 11.4% slower than the delegate. The comparison covers one static
5,000-add function, and the timer overhead has not been independently
calibrated; it is not a real-world speedup claim. A separate 25-cycle reload
check kept the bytecode arm at 15 live generated classes after each GC, with a
stable defining classloader identity and about 1.03 MiB maximum metaspace
growth. See [Minecraft 26.3 internals](../docs/research/26.3-internals.md) for
reload details. Keep every optimization disabled pending remaining parity,
allocation, timer calibration, and fallback/compatibility gates. PERF-011
provides a native real-datapack ScoreAdd workload, but no screened pack has an
adjacent eligible pair for real-world fused or bytecode region measurements.

### Remaining optimization comparisons

The fused static-fixture queue-timing gate has ten trials per arm across two
randomized sets; PERF-004 adds a five-trial-per-arm bytecode comparison. Remaining
gates are timer-overhead calibration, allocation, broader parity across the
supported input domain, and selected compatibility
profiles. PERF-011's Vein Miner campaign exercises a reachable direct ScoreAdd
in a native datapack event, but shows no reliable gain and has no adjacent
eligible pair for real-world fused/bytecode comparison. Keep warmup, server
settings, world state, operation count, and
measurement instrumentation matched across arms. Report independent-run
variation, allocations, reload costs, and fallback coverage before describing
a general speedup.
