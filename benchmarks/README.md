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
| RW-11 | [Vein Miner](https://modrinth.com/datapack/vein_miner) 5.3.0 (`vein_miner`, underscore) | Pinned 26.3 archive with three direct fake-holder ScoreAdd sites. Native 6×6×6 mining passes five randomized compiler-off/ScoreAdd pairs on Fabric, Lithium, and Lithium+Moonrise 1.2.1. None shows a reliable gain; Bellows-containing compiler-off runs fail workload integrity and are excluded as comparisons. The similarly named [VeinMiner](https://modrinth.com/datapack/veinminer) project is separate; its V1 datapack is not the PERF-011 target and has no direct fake-holder ScoreAdd site. A 2026-11-03 static screen found 145 adjacent parsed candidates in `vm:detection/acquire_target`, but runtime specialization and fused/bytecode performance remain unmeasured. See [PERF-011 evidence](../docs/research/real-world-profile-targets.md#vein-miner-530-native-trigger-eligibility-and-profile-pilot). |

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
`#tick_id` delta; its timing is excluded from comparisons. A 2026-11-03 static
screen found adjacent candidate runs in the archive's generated block-state
reader (32 `execute if block ... run scoreboard players set` commands per state
table), reached from `erb:capture/store` during capture scans; runtime
specialization and performance remain unmeasured. See [PERF-010 results](../docs/research/real-world-profile-targets.md).

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
are not performance comparisons. A 2026-11-03 static screen found adjacent
candidates in `vm:detection/acquire_target` (145 parsed commands),
`vm:detection/verify_mined_stat` (59), and a one-time 19-add `@s` initialization
in `vm:player/register`; none has runtime-confirmed specialization or a
measured fused/bytecode comparison. Compiler-off Vein Miner controls on
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

## H2-first specialization inventory (2026-11-09)

The compiler-coverage-widening proposal's first step is a metrics-only
inventory of the addressable work in the pinned real datapacks. The census
runner `scripts/run_specialization_inventory.py` verifies each pack's recorded
SHA-256, walks the functions reachable from `minecraft:tick` and
`minecraft:load` (including self-rescheduling `schedule function ... 1t` loops,
which is how Dynamic Lights drives its tick path), and classifies every command
against the compiler's real eligibility rule: fused regions reject forked
`execute` contexts (`as`, `at`, `on`, `summon`), accept non-forked
context-modifier chains (`positioned`, `facing`, `rotated`, `anchored`, `align`,
`in`), and inline `function` calls only when the target is a pure leaf in the
sense of `LeafFunctionParser.isPureLeaf` (1–64 entries, no `function`/`return`
roots, no macro placeholders). The output is hermetic and reproducible; the
generated report is `build/benchmarks/COVERAGE-INVENTORY/<timestamp>/inventory.md`
and `.json`.

| Pack | Reachable fns | Command lines | Tick lines | Forked `execute` | Forked share | Leaf lines | Context-modifier lines | Adjacent tick runs | Adjacent tick commands | Longest run | Fake-holder adds | Macro fns | Macro `with` (tick) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vein Miner 5.3.0 | 58 | 635 | 532 | 102 | 23.4% | 83 | 233 | 27 | 266 | 144 | 3 | 10 | 10 |
| Spawn Animations 1.11.6 | 78 | 556 | 519 | 63 | 19.0% | 99 | 98 | 36 | 165 | 16 | 0 | 0 | 0 |
| Dynamic Lights 1.4.6 | 77 | 285 | 262 | 28 | 18.3% | 24 | 88 | 19 | 80 | 10 | 0 | 0 | 0 |
| Everything Clings 1.0.0 | 4 | 15 | 14 | 2 | 25.0% | 4 | 4 | 2 | 8 | 6 | 0 | 0 | 0 |

`Adjacent tick runs` counts maximal runs of at least two adjacent eligible
commands inside tick-reachable functions — the unit fused regions compile.
`Forked share` is over all reachable `execute` lines. Static limitation:
lexical fork status is per line, so a function called from a forked context
inherits that context at runtime even when its own lines are top-level; the
per-function JSON records the lexical counts.

Batch 23 corrected two classification gaps that undercounted the batch-22
table: a macro body line carries a leading `$` marker that is not part of the
command, and a macro call or pure-leaf call inside `execute ... run` must be
counted on the inner command. The corrected census supersedes the batch-22
numbers (Vein Miner 250→266 adjacent tick commands, Spawn Animations 143→165,
Dynamic Lights 14→80; ranking unchanged) and also recognizes
`scoreboard players remove` as a `score-add` form.

Runtime confirmation on the top-ranked pack used the existing native-event
runner: `python3 scripts/run_veinminer_profile.py --stack fabric
--compiler-mode fused --side 4 --no-spark` passed its workload gate (63/63
blocks, 480 queue-head increments, empty vein, cleared markers) and recorded
164 fused regions compiled, 718 region executions during the event (18 before
to 736 after), and 5,860 ScoreAdd executions (1,920 queue plus 318 ray). This
corroborates PERF-017's activation diagnostic on the same pack.

**Finding: addressability is not the binding constraint.** All four packs have
adjacent eligible tick-path work, and the fused engine compiles and executes
164 regions in one native Vein Miner event, yet PERF-017's paired real-workload
result is flat (+0.69% median, 97.85% interval −3.92% to +2.74%,
`does_not_meet_threshold`). The fork barrier is real — 23.4% of Vein Miner's
reachable `execute` lines are forked, 19.0% in Spawn Animations, 25.0% in
Everything Clings, 18.3% in Dynamic Lights — but the non-forked pool is large
enough that "the specializers never fire" is not supported by these packs. The
constraint is the share of tick time the addressable work represents, which a
command census cannot measure. The macro-extension pool is also narrow here:
10 `function ... with` call sites in Vein Miner tick functions and none in the
other three packs.

## Time-share attribution and the H4 decision (2026-11-09)

The census measures static eligibility; it cannot say how much tick time that
work represents. Batch 23 adds `scripts/attribute_specialization_share.py`,
which reads a Spark profile and partitions each server-thread stack's self
weight by the nearest enclosing leaf command family. Three boundaries matter
for the decision:

- `FunctionCommand$2.arguments` / `FunctionCommand.getArgumentTag` marks macro
  argument construction. The vanilla fallback reads the source tag through
  `DataCommands.getSingleTag`; that helper is not a `data` command, so it is
  reported as the separate `macro-argument` (H4) share.
- `ServerFunctionManager.execute` resets the leaf owner, so a called function's
  body is attributed to its own commands rather than to its call site.
- Samples under `net.minecraft.commands.execution.tasks.ContinuationTask` are
  marked forked; blocking syscall / `Thread.sleep` / `park` samples are marked
  idle and excluded from the active-tick denominators.

The addressable figure sums `scoreboard`, `data`, `function-call`, and `return`
self weight. It is an upper bound: Spark cannot distinguish a fusable
`scoreboard players add` from an unfusable `scoreboard players get`, nor a
pure-leaf call from an arbitrary one. Wall shares use total sampled self
weight; active shares exclude the idle family.

| Pack (capture) | Sampler weight | Idle | Function time (wall / active) | Macro arg H4 (wall / active) | Addressable leaf (wall / active) | Forked samples |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Vein Miner 5.3.0 (side 6, compiler off) | 19,960 | 7.1% | 88.5% / 95.2% | 27.4% / 29.4% | 58.7% / 63.2% | 0.0% |
| Spawn Animations 1.11.6 (vanilla, 24 actors, 12 s) | 11,876 | 87.4% | 3.1% / 24.6% | 0.0% / 0.0% | 1.3% / 10.4% | 0.1% |
| Dynamic Lights 1.4.6 (pack on, wrapper off, 30 s) | 29,516 | 60.3% | 9.7% / 24.4% | 0.0% / 0.0% | 0.6% / 1.6% | 0.2% |

Captures: Vein Miner `python3 scripts/run_veinminer_profile.py --stack fabric
--compiler-mode off --side 6` (4,317 server-thread nodes, 215/215 work);
Spawn Animations `python3 scripts/run_spawn_animations_profile.py --seconds
12` on the official server (2,205 nodes, 12 of 24 actors animating at sample
start); Dynamic Lights `python3 scripts/run_dynamic_lights_profile.py --stack
fabric --mode cpu --wrapper off --datapack on --seconds 30` (6,834 nodes, 26
markers, torch level 14). Profiles are retained under
`build/benchmarks/PERF-011-veinminer/vein-6-fabric-off-20261109T171149Z-8132fc/`,
`build/benchmarks/PERF-010/20261109T172135Z-b2fb0f/`, and
`build/benchmarks/PERF-010/dynamic-lights-fabric-pack-on-off-cpu-20261109T171936Z-b14c56/`.

**H1 is dead on this evidence.** Sampled time under the runtime fork marker is
0.0% (Vein Miner), 0.1% (Spawn Animations), and 0.2% (Dynamic Lights). The hot
Vein Miner `execute` chain (6,948 of 19,960 sampled weight) is a non-forked
conditional chain whose cost is macro argument construction (5,460), not
fork-interior leaf work; the static forked lines (23.4% of Vein Miner's
reachable `execute` lines) are not where the sampled time goes. Widening
fusion across the fork barrier therefore has no measured >15% pool on these
packs. The detector uses the `ContinuationTask` frame; a fork form that
bypasses that task would be attributed to its leaf family, but the conclusion
does not rest on the forked count alone — the hot path is demonstrably the
non-forked macro-argument chain.

**H4 is the only candidate with a >15% pool.** Vein Miner's macro argument
construction is 27.4% of sampled wall time and 29.4% of active tick time; the
other two packs have no macro-argument samples. The existing
`selective_macros` mechanism already covers Vein Miner's shape: a diagnostic
run (`--compiler-mode selective-macro --count-selective-macro-arguments --side
6 --no-spark`) recorded 215/215 work, 11,701 attempted and 11,701 used calls,
and zero unsupported providers, unsupported entity paths, invalid storage
sources, missing custom data, macro-resolution fallbacks, or missing selected
keys. No H4 code extension is needed; the open question is whether the shipped
default clears the 15% gate on the real workload.

PERF-017's fused arm set `FC_SELECTIVE_MACRO_ARGUMENTS=false`, so its flat
result did not test the shipped default. The 126.7 ms average tick query from
the selective-macro diagnostic is not a timing comparison (metrics on, no
Spark). The H4 gate is predeclared before the first arm:

- **Fixture:** Vein Miner 5.3.0 on the Fabric stack, side 6 (216 blocks; 215
  mined), native event; neither timing arm uses Spark or compiler counters.
- **Arms:** compiler off vs the shipped `selective_macros` default,
  counterbalanced from the seed.
- **Primary metric:** `operation_completion_seconds` (event completion), with
  the 15% minimum median reduction and the 95% exact paired interval entirely
  beyond it; the no-regression floor is reported alongside.
- **Secondary metric:** the post-event `/tick query` average
  (`tick_average_ms`), reported alongside as corroboration. It is not a
  sustained active-workload MSPT result and does not decide the gate.
- **Design:** five screening pairs, then a predeclared ten-pair confirmatory
  campaign if screening warrants it; seed `26871031`; exact workload parity is
  required in every pair.
- **Activation:** a one-time metrics-on `selective-macro` diagnostic (hit
  counter enabled, not a timing arm) must show positive attempted and used call
  counts; the paired timing arms stay uninstrumented.
- **Host gate:** the declared quiet-window precondition, wired into the
  campaign runner (batch 25): the start waits for the 1-minute load average to
  fall to the declared quiet load and records the outcome, every arm is
  preceded by an inter-run settle, and an arm that starts above the CPU count
  is repeated once with both results retained. PERF-001 showed this shared
  host's fresh-JVM variance can block a 5% gate, so the campaign does not
  start until the host is quiet.

`run_veinminer_campaign.py` now builds uninstrumented timing arms and records
the activation diagnostic under `activation_diagnostic`; its selective-macro
counters come from that diagnostic, not from per-pair timing arms. The
screening command is:

```
python3 scripts/run_veinminer_campaign.py --stack fabric --side 6 \
  --candidate selective-macro --phase screening --pairs 5 --seed 26871031 \
  --primary-metric operation_completion_seconds
```

The confirmatory command adds `--phase confirmatory --pairs 10
--minimum-gain-percent 15` with the same seed. If the addressable share cannot
clear 15%, that is the recorded answer and coverage widening stops.

The screening ran on 2026-11-09 under the wired quiet-window gate (observed
1-minute load 3.946). The one-time activation diagnostic intercepted 11,753
attempted and 11,753 used macro calls with zero fallback counters and 215/215
work, and all five counterbalanced pairs held exact workload parity (215/215
blocks mined, 1,952 queue-head increments in every arm) with no noisy arms and
no repeats. Median event completion change is −30.03% with the exact 93.75%
interval −32.64% to −21.27% (`screening_only`, `no_regression_holds`); the
post-event `tick_average_ms` median is −25.03% (−30.62% to −2.60%) and
`tick_p95_ms` −30.26% (−34.88% to −22.27%). Per-pair completions (off vs
selective): 20.160/13.579 s, 18.330/13.466 s, 18.701/13.086 s, 18.363/12.769 s,
18.317/14.421 s. The report is
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-fabric-selective-macro-5pairs-seed26871031-20261109T200155Z.json`.
The entire interval lies beyond the predeclared 15% gate, so the predeclared
ten-pair confirmatory (same seed, same stack, `--minimum-gain-percent 15`) is
next; the promotion decision follows that campaign.

The confirmatory ran the same day under the quiet-window gate (observed
1-minute load 2.577). The activation diagnostic intercepted 11,715 attempted
and 11,715 used macro calls with zero fallback counters and 215/215 work, and
all ten counterbalanced pairs held exact workload parity (215/215 blocks,
1,952 queue-head increments in every arm) with no noisy arms and no repeats.
The primary decision is **`meets_threshold` with `no_regression_holds`**:
median event completion change −29.58%, exact 97.85% interval −30.30% to
−26.37% (per-pair −54.84% to −24.18%; pair 3's off arm hit a 33.2 s
background spike, which widens that pair's gain but cannot move the exact
interval across the gate), every pair beyond the predeclared 15%. The
secondary post-event `tick_average_ms` is corroboration only and its window
is unstable on this fixture (per-arm averages 4.3–322.8 ms; median change
−38.81%, interval −82.00% to +467.43%, `no_regression_decision:
indeterminate`), matching the standing caveat that the post-event tick query
is not a sustained active-workload MSPT result; the sustained active-tick
floor remains PERF-012's cleared −81.72% campaign. The report is
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-fabric-selective-macro-10pairs-seed26871031-20261109T204433Z.json`.

**H4 decision: the shipped `selective_macros` default clears the real-workload
promotion gate.** Vein Miner 5.3.0 side 6 on the plain Fabric stack is the
workload whose hot path is dominated by successful specialized runs: the
macro-argument pool measured 27.4% of sampled wall time, the fast path
intercepts ~11.7k calls per event with zero fallbacks, and the predeclared
confirmatory cleared 15% with the entire exact interval beyond it. No code
extension was needed. Coverage widening closes on this evidence: H1 is dead
(runtime forked samples ~0.0–0.2%), no other profiled pack has a >15% pool
(Spawn Animations 10.4% and Dynamic Lights 1.6% active addressable), and the
one >15% pool is already covered by a promoted, default-on mechanism.

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

The 2026-11-03 static screen found adjacent candidate runs in pinned packs, but
none has runtime-confirmed specialization or a measured real-world gain, so
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

Three confirmatory campaigns are complete, each pre-declaring a 15% minimum gain.
All passed exact workload parity and exact region activation (one executed region per
active tick), and all are **inconclusive** because the interval overlaps the threshold.

| Campaign | Stack | Adds per active tick | Pairs | Primary median | Exact interval | Coverage |
|---|---|---:|---:|---:|---|---:|
| confirmatory | Fabric | 5,000 | 10 | −19.72% | −30.30% to −12.90% | 97.85% |
| confirmatory | Fabric | 20,000 (`--adds-per-tick`, generated and hash-recorded) | 12 | −12.48% | −33.09% to +77.44% | 96.14% |
| confirmatory | Lithium + Bellows 1.1.3 | 5,000 | 10 | −22.16% | −86.39% to −12.12% | 97.85% |
| confirmatory, **quiet-window re-run** | Fabric | 20,000 | 12 | **−18.43%** | **−20.18% to −14.95%** | 96.14% |
| confirmatory, **pre-declared 16-pair** | Fabric | 20,000 | 16 | **−20.72%** | −32.23% to −12.26% | 97.87% |

Scaling to a 20,000-add block did not separate the interval from −15% in the first
attempt; it widened it, because per-arm cost became bimodal at roughly four times the
tick workload (four of twelve pairs contained a 20–27 ms arm producing +4.7% to +143.2%
reversals). A follow-up diagnosis traced those reversals to host CPU contention and
page-fault bursts acting on a CPU-bound block, not to the compiler: the campaign's own
mod-free vanilla reference arm measured 27.1 ms in that run and 6.4 ms on the same
fixture and jar in a quieter window. A gated re-run of the same design then produced a
**−18.43% median with a −20.18% to −14.95% interval**, all twelve pairs negative and
0 of 24 arms above the 16 ms median-window line (against 7 of 24 in the noisy run),
confirming the diagnosis — while still leaving the interval's upper edge 0.05 percentage
points above the threshold, so it remains inconclusive under the decision rule as
written. A pre-declared 16-pair follow-up (threshold, pair count, and seed committed
before its first arm) then gave all sixteen pairs negative with a −20.72% median, but a
−32.23% to −12.26% interval — the obstacle is per-pair spread around a consistent
~−20% effect, not the effect itself, so the recorded decision stays inconclusive and no
further attempt is made on a seed re-roll. See the
[variance diagnosis section](PERF-016-sustained-fused-region-active-tick.md#6-variance-diagnosis-of-the-20000-add-block-2026-11-03)
of the report. The 5,000-add block remains the better instrument on this host, and a
host-quietness gate is a prerequisite for any future attempt to separate from −15%.
Run `python3 scripts/diagnose_perf016_host_noise.py --adds-per-tick 5000` (add `--load 8`
to reproduce contention) to measure the workspace's noise floor before a campaign.

The `lb113` campaign's first two pairs contain contaminated `off` arms (one whose own
pre-workload idle was already 14.6 ms against 7.6–10.6 ms elsewhere, one that degraded
progressively); because both are `off` arms, excluding them is the conservative
direction, and the remaining eight pairs still give a −18.57% median with a −32.50% to
+3.45% interval — inconclusive. The 5-pair screening pilot had a
−22.86% median with a −86.55% to 0.00% interval and is retained as screening only. Full
results, gates, limitations, and next actions are in
[`PERF-016-sustained-fused-region-active-tick.md`](PERF-016-sustained-fused-region-active-tick.md).
`fused_regions` stays disabled by default.

Reproduce with:

```sh
# Fabric, checked-in 5,000-add block
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 10 --phase confirmatory \
  --minimum-gain-percent 15 --seed 26871041

# Fabric, generated 20,000-add block
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack fabric --pairs 12 --phase confirmatory \
  --adds-per-tick 20000 --seed 26871042

# Lithium + Bellows 1.1.3, 5,000 adds per active tick
FC_GRADLE_OFFLINE=true python3 scripts/run_fused_region_sustained.py \
  --stack lb113 --pairs 10 --phase confirmatory \
  --adds-per-tick 5000 --seed 26871043
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
provides a native real-datapack ScoreAdd workload. The 2026-11-03 static screen
found adjacent candidates, but none has runtime-confirmed specialization or a
measured real-world fused/bytecode comparison.

### Remaining optimization comparisons

The fused static-fixture queue-timing gate has ten trials per arm across two
randomized sets; PERF-004 adds a five-trial-per-arm bytecode comparison. Remaining
gates are timer-overhead calibration, allocation, broader parity across the
supported input domain, and selected compatibility
profiles. PERF-011's Vein Miner campaign exercises a reachable direct ScoreAdd
in a native datapack event and shows no reliable gain. A 2026-11-03 static
screen found adjacent candidates for a future fused/bytecode comparison, but
none has runtime activation or performance evidence yet. Keep warmup, server
settings, world state, operation count, and
measurement instrumentation matched across arms. Report independent-run
variation, allocations, reload costs, and fallback coverage before describing
a general speedup.
