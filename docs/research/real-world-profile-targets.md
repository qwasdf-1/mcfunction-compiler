# PERF-010/011: Minecraft 26.3 datapack profile evidence

This page records the pinned real-world datapack workload, Spark capture setup,
and the first vanilla/Fabric/mod-stack results. It is an evidence log, not a
Function Compiler optimization result: the prototype wrapper delegates to
vanilla functions and no function body is compiled. All new performance
campaigns follow the shared [benchmarking protocol](../benchmarking.md).

## Measurement model

Use three measurements for distinct questions:

- Spark CPU sampling shows sampled server-thread call paths across an 18-second
  window. It does not report exact function invocation counts or exact time
  spent in one datapack function.
- Minecraft's /tick query reports whole-server tick percentiles over its
  latest 100 ticks. The runner records it immediately after profiling; it is
  not a summary of exactly the Spark sample window.
- A future compiler comparison needs a low-overhead in-server counter/timer for
  completed invocations and elapsed time of the exact measured region. Keep
  that instrumentation as its own arm and measure its overhead.

The harness follows useful patterns from Terra Rasa and Soul Link. Terra Rasa
generates packet IDs from the exact server jar, drives headless players, uses
RCON for setup and observations, and gives each run a disposable server
directory. Soul Link separates its bounded-code-path System.nanoTime timing
from whole-server /tick query percentiles. This project uses Spark for sampled
server impact and will add narrow timing only when a compiler region exists.

## Pinned workload and scenario

The selected artifact is [Dynamic Lights by CreepermeYT v1.4.6 for Minecraft
26.3](https://modrinth.com/datapack/dynamic-lights-creepermeyt/version/v1.4.6-mc1.17.x-26.3).
The downloaded zip SHA-256 is
afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20. The pack
loads on the official 26.3 server, creates its dynbclevel objective, and passes
its own version check.

Each fresh seeded server creates the same controlled tick scenario:

- Four connected headless creative players at fixed positions 64 blocks apart.
- Twenty-four stationary, zero-motion dropped torches in distinct light-source
  positions on a fixed stone platform.
- Each player holds stone, which does not emit light.
- Seed 264010, view and simulation distance 4, forced test chunks, daylight
  cycle and natural mob spawning disabled.
- Dynamic Lights Smart preset (score 2).
- The runner waits for all 24 items to remain tracked across ten consecutive
  readiness reads before the profile starts.

The datapack rebuilds marker entities as part of its tick processing. Marker
counts are diagnostic and can vary; they are not the readiness gate. The
runner records tracked item count, direct and predicate-based dynbc.torch tag
counts, marker counts, datapack tick scores, a source light-level score,
connected players, /tick query output, and artifact hashes. Fabric runs also
query the Function Compiler wrapper probe to verify wrapper mode, tag identity,
and delegation to the original function.

## Workload intensity: measurable command load in a controlled scenario

The exact archive has a recurring tick path that checks several entity/item
categories, prepares holders and dropped items, manages tagged marker entities,
checks blocks and predicates, and updates dynamic lights. The selected Smart
preset enables the pack's broad feature set. This makes it a useful command-
and selector-heavy compiler workload. It is not a controlled “worst case”:
the harness uses only 24 stationary torch items and four players, with no
deliberate population of TNT, glowing mobs, allays, glow squids, enchanted
armor, or a busy survival world. Stationary lights also avoid much of the
movement-driven marker update work.

Three fresh vanilla on/off pairs now compare the same four players and 24
stationary torch items. Every datapack-on Spark tree contains a recurring
`FunctionCallback.handle` -> `ServerFunctionManager.execute` path, with
716–756 ms of weighted Server thread samples (4.00–4.22% of the full 18-second
sample weight). The datapack-off trees contain no scheduled function path.
This confirms that the pack contributes a real recurring command workload in
this scenario. The sample weight is statistical profiler output, not elapsed
time measured by an in-server timer.

The workload is meaningful but constrained, not a demonstrated worst case.
We have not added movement, busy survival entities, TNT, glowing mobs, allays,
glow squids, or enchanted armor. Across three pairs, the median post-profile
/tick query values were P50/P95/P99 6.4/9.7/12.0 ms with the datapack and
4.9/7.6/9.7 ms without it. One pair reversed sharply, with the off arm much
slower, so those MSPT differences are not stable cost estimates. Modrinth
describes the pack as optimized and says it has minimal performance impact;
that is the publisher's claim, not independent evidence. See the
[publisher's feature and preset description](https://modrinth.com/datapack/dynamic-lights-creepermeyt).

The 26.3 server jar SHA-256 is
d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64. Spark
1.10.194 standalone-agent SHA-256 is
a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9. The same
standalone agent is used on vanilla and Fabric stacks; Fabric does not use a
separate Spark mod. The corrected runner samples all threads at 4 ms for 18
seconds, stops Spark before post-profile RCON checks, and rejects saved CPU
profiles without thread sample nodes. The previous `--thread "Server thread"`
selection resolved to an empty thread set in these standalone-agent runs, so
those older CPU `.sparkprofile` files contain metadata but no call trees. The
allocation capture uses a separate 524287-byte allocation interval. The idle
control attaches Spark but records no profile for the same duration.

Fabric arms use the Loom development server and the Function Compiler probe
mod. They verify the current wrapper lifecycle in this environment; they are
not measurements of a published production mod jar.

## Matched vanilla datapack-on/off profiles

Each pair uses a fresh world with the same seed, four headless players, 24
stationary torch items, JVM settings, Spark 1.10.194 standalone agent, and
18-second all-thread CPU sample. Order alternated between pairs. Every profile
contains 41–45 thread nodes, and all six workload checks passed. MSPT is the
separate post-profile `/tick query` sample of 100 ticks.

| Pair and order | Datapack off: P50/P95/P99 MSPT | Datapack on: P50/P95/P99 MSPT | Run IDs off/on |
|---|---:|---:|---|
| 1, off then on | 4.9/7.6/9.7 | 6.4/9.7/12.0 | `2611e4` / `ed85a0` |
| 2, on then off | 4.9/7.5/9.4 | 6.8/10.5/21.1 | `2aae03` / `6fcf3b` |
| 3, off then on | 13.1/31.3/39.6 | 6.2/8.7/10.7 | `5a1680` / `8ea209` |

The median across runs is 4.9/7.6/9.7 MSPT off and 6.4/9.7/12.0 on. Pair 3
reversed sharply, showing that the host and short MSPT window can overwhelm
the workload delta. Use this set as an initial load-attribution signal, not a
stable performance estimate. In contrast, the Spark call-path signal repeated
in all three on profiles: 716–756 ms weighted to the scheduled function
callback and `ServerFunctionManager.execute`; none of the off profiles
contains that scheduled datapack path. These are samples, not precise elapsed
time or invocation counts.

Earlier vanilla, Fabric, Lithium, Bellows and Moonrise captures used the
`Server thread` filter and saved zero thread nodes. Those files are not CPU
profiles. The corrected runner has now captured valid all-thread CPU profiles
for Fabric, Lithium, and Lithium+Moonrise, described below. The older Bellows
captures remain compatibility-only evidence; their MSPT snapshots are not
matched profile comparisons.

## Fabric and optimization-mod stack profile pilots

One datapack-on wrapper-off/on pair was captured for each of Fabric, Lithium,
and Lithium+Moonrise 1.2.1. Each profile contains 44–47 thread nodes, retains
all 24 tracked torch sources and source tags, and includes the scheduled
`FunctionCallback.handle` → `ServerFunctionManager.execute` path. The table
reports inclusive weighted Spark samples for `ServerFunctionManager.execute`;
these are sampled call-path weights, not elapsed-time measurements. MSPT is
the separate post-profile `/tick query` window of 100 ticks.

| Stack | Wrapper off/on run IDs | Thread nodes off/on | `ServerFunctionManager.execute` weighted samples off/on | Post-profile P50/P95/P99 MSPT off/on |
|---|---|---:|---:|---|
| Fabric | `b4c8ca` / `5412e3` | 46 / 44 | 812 / 756 ms | 10.7/14.9/39.7 / 43.4/95.3/121.1 ms |
| Lithium | `930be9` / `090060` | 44 / 46 | 524 / 1,960 ms | 5.3/7.9/10.5 / 19.1/37.2/56.5 ms |
| Lithium + Moonrise 1.2.1 | `435047` / `2c85c9` | 45 / 47 | 620 / 772 ms | 5.3/9.3/10.2 / 10.9/32.7/60.5 ms |

These are capture-path pilots, not optimization or wrapper-cost results. There
is only one pair per stack, every run has the datapack enabled, and post-profile
MSPT varies sharply. No optimization was enabled; the Function Compiler was
only toggled between its delegating wrapper off and on. The profiles establish
that valid Spark trees and the scheduled datapack path are available on these
stacks. They establish neither a comparative performance result nor behavior
parity between arms. The existing differential harness remains the semantic
gate. Benchmark captures must follow that gate and keep a same-stack
compiler-off/on comparison as well as a mod-free vanilla reference.

The wrapper probe checks tag identity and delegation independently of whether
the datapack workload is equivalent. The following Bellows-related runs
establish compatibility only; their older Spark CPU files have no thread
sample nodes.

| Stack | Workload and compatibility result |
|---|---|
| Bellows, wrapper off/on | All items remain tracked, but zero have dynbc.torch, no source score is set, and no light markers are produced. Wrapper probe passes when on. |
| Lithium + Bellows, wrapper off/on | Neither run produces light markers; wrapper-on also records zero torch-source tags and no source score. |
| Lithium + Bellows + Moonrise 1.2.1 | Server fails during startup: Bellows 1.1.2's Moonrise selector mixin cannot find its shadowed entityById field in Moonrise 1.2.1. |
| Lithium + Bellows + Moonrise 1.2.0, wrapper off/on | Server starts, but there are zero torch-source tags and no light markers. Wrapper probe passes when on. |

The Bellows results are a compatibility finding for these exact artifacts and
this datapack scenario. They do not show why the datapack's entity tags and
light markers disappear, and they should not be generalized to every Bellows
or Moonrise release. The Moonrise 1.2.1 startup failure is specific to the
pinned Bellows 1.1.2 and Moonrise 1.2.1 pair. Moonrise 1.2.0 starts but does
not restore this workload's output.

A separate command-level compatibility run against Bellows 1.1.2 + Moonrise
1.2.0 passed selected vanilla selector, entity-NBT, tag-index, and `home_pos`
parity cases in wrapper-off/on, ScoreAdd, fused, and bytecode modes. This does
not make the Dynamic Lights arms comparable: the datapack still has no
equivalent torch-source output in those stacks. See the
[Bellows audit](bellows-audit.md) for the runtime matrix and pinned hashes.

The new vanilla and compatible mod-stack call trees have had an initial
comparison. Spark's function callback weight is an approximate sampled path,
not a per-function timer. MSPT values come from `/tick query`, not Spark sample
percentages. More randomized repeats, datapack-off controls on each stack, and
a busier/moving workload are needed before ranking the pack's absolute cost or
comparing optimization performance.

## Artifact pins

| Artifact | Version/file | SHA-256 |
|---|---|---|
| Lithium | 0.26.2+mc26.3 | 0be5b17ef9f6e9244cd07b24b227553a73aec0cf93158cf28099f3094c167f1b |
| Bellows | 1.1.2 | d0c7218e7e368c7d1473483881540ff78554853ff0a4f0bab098df6b3c753b67 |
| Bellows | [1.1.3](https://api.modrinth.com/v2/version/QoiW2Z70), 26.3 Fabric | 4d9fc818d0e800c1a7414b4670c676339020749e516a50742bd18c4e3d61055c |
| Moonrise Fabric | 1.2.1+e53de7f | 78911260bbf2e8053910c93de66d48709f2fd8fb2d69958e575328ffb1291fc3 |
| Moonrise Fabric alternate | 1.2.0+61c1328 | cb4890a8aeb61115b4b57aff3d4ec26c96ffdb4194d28fd7ed9d1365db3aa4d6 |

## Reproducing the profile

The project runner is scripts/run_dynamic_lights_profile.py. It checks the
pinned server, datapack, Spark agent, and selected mod hashes before launch.
Each server receives a fresh disposable run/<id> directory and a deterministic
scenario. Successful shutdown removes that server directory; manifests and
profiles are copied to build/benchmarks/PERF-010. Remove leftover run/<id>
directories from interrupted runs after confirming no server process remains.

The local datapack, Spark agent, and mod jars must be placed at the paths
expected by the runner under references/real-world. The raw Spark profiles,
manifests, downloaded jars, and temporary worlds are local-only benchmark
artifacts. Curated findings and pins in this document are tracked.

Examples:

- Vanilla datapack on: python3 scripts/run_dynamic_lights_profile.py --stack vanilla --mode cpu --datapack on
- Vanilla matched control: python3 scripts/run_dynamic_lights_profile.py --stack vanilla --mode cpu --datapack off
- Vanilla allocation: python3 scripts/run_dynamic_lights_profile.py --stack vanilla --mode alloc
- Vanilla idle control: python3 scripts/run_dynamic_lights_profile.py --stack vanilla --mode idle
- Fabric wrapper-off: python3 scripts/run_dynamic_lights_profile.py --stack fabric --mode cpu --wrapper off
- Fabric wrapper-on: python3 scripts/run_dynamic_lights_profile.py --stack fabric --mode cpu --wrapper on
- Mod stacks use --stack lithium, bellows, lb, lm, lbm, or lbm120 and --wrapper off/on.

## Spawn Animations burst pilot and other screening

The pinned Tschipcraft Spawn Animations 1.11.6 artifact loaded on official
Minecraft 26.3. The corrected runner now creates its 24 tagged zombies in one
setup-function call, then captures all threads with Spark 1.10.194 at 4 ms.
Vanilla pilot `20261028T093844Z-c6f27b` retained all 24 tagged zombies; six
were in the active animation state at the start of the six-second sample and
none remained active at the end. The profile contains 47 thread nodes and
288 ms of inclusive weighted `ServerFunctionManager.execute` samples. The
post-capture `/tick query` reported P50/P95/P99 5.9/8.9/11.4 ms. This proves a
short real function burst, but it does not measure sustained animations or a
stable performance delta. It has no pack-off pair, repeated run distribution,
mod-stack arm, or compiler optimization. Raw profile SHA-256 is
`fcc38294e813172114245a26088c540341e0b20b455c847b9338babb56de8c62`.

An earlier Spawn Animations capture used the invalid `Server thread` filter
and contained no sample nodes. Its two active animations and zero active at the
end were not valid CPU evidence. The new runner fixes that filter and spawns
the cohort together to avoid animations finishing during per-entity RCON setup.

Everything Clings 1.0.0 loads on 26.3 and has valid all-thread Spark trees, but
its controlled pig population was not retained: 8 fell to 2 over two and four
seconds, and 32 fell to 12 over 18 seconds. Those profiles are rejected for
comparison until a stable actor fixture is found.

Bigger Every Kill 1.0.0 advertises 26.3, but the pinned archive fails registry
loading on official 26.3 because its advancement `conditions.entity` has the
wrong JSON shape. No profile was captured for it.

Blastback Hotfix 3 loads on official 26.3 and its one-TNT run samples
`FunctionCallback.handle` and `ServerFunctionManager.execute`. The pinned run
`20261028T095704Z-7b7765` used one tagged TNT with an 80-tick fuse, the default
one-block-per-tick restore setting, an all-thread 4 ms Spark capture for 180
seconds, and a five-minute completion bound. It cloned a 17×17×17 source
volume to a forced-loaded template and disabled random ticks. The profile had
44 thread nodes and 179,132 ms of total weighted samples; 178,832 ms were
inclusive to `FunctionCallback.handle` and 97,764 ms to
`ServerFunctionManager.execute`. These are profiler sample weights, not exact
elapsed function time. Post-drain `/tick query` reported P50/P95/P99
29.0/61.6/89.6 ms. The raw Spark profile SHA-256 is
`9b75f912607a6b827e2fefb265f097131fbc7a5ec914ac61d9aa6e4190d2b148`.

The run did not pass restoration validation. TNT, capture, verification, and
unresolved counts reached zero, and all five floor witnesses matched, but the
full source volume still differed from its template after the five-minute
drain. Two group jobs and five protected items remained; one restore job and
3,273 saved-block markers were still present. The 180-second sample is useful
for finding the scheduled-function path, but this fixture is not valid for a
performance comparison or a quiet-idle control. Do not run the 4- and 32-TNT
matrix until this single-source restoration path completes. Raw profile and
manifest are local under the ignored `build/benchmarks/PERF-010/` tree; the
runner is `scripts/run_blastback_profile.py`.

A separate **no-TNT dispatch pilot** uses the same pack's ordinary
`#minecraft:tick` entry without starting the restoration event. The runner
supports `--tnt-count 0` and `--compiler-mode off|score-add`; the ScoreAdd arm
keeps per-command execution metrics disabled during capture. It verifies the
exact `erb:runtime_tick` compile count through the probe stats command, the
`#tick_id` state delta, zero TNT, and zero event-specific job/restore markers.
Blastback still reports one active group, so this is not an idle or quiescent
server profile. It is a no-event profile of the pack's normal dispatcher. It
does not replace the failed TNT restoration gate or measure that event path.

Two sequential same-stack Fabric pairs produced the following capture-window
results. Spark values are inclusive weighted samples for
`ServerFunctionManager.execute`, not precise elapsed time. Each pair's
`#tick_id` delta matched exactly between compiler-off and ScoreAdd-on.

| Pair | Mode and run ID | `#tick_id` delta | `ServerFunctionManager.execute` weighted samples | Thread nodes |
|---|---|---:|---:|---:|
| 1 | compiler off `20261028T135203Z-a4d42b` / ScoreAdd `20261028T135647Z-88f9ba` | 460 / 460 | 160 / 104 ms | 54 / 49 |
| 2 | compiler off `20261028T135812Z-b103e8` / ScoreAdd `20261028T135918Z-7ef021` | 461 / 461 | 168 / 152 ms | 50 / 48 |

The ScoreAdd arm compiled exactly one command in `erb:runtime_tick`; 71 literal
fake-holder ScoreAdd commands were compiled across the full archive. The
original direct-entry scan found no adjacent eligible region; a 2026-11-03
static screen later found 32-command block-state tables in the generated
reader, but runtime specialization remains unmeasured. The manager sample was lower in
both pairs, which is a signal to repeat on more workloads, not enough evidence
to enable ScoreAdd: there are only two short captures, the measured function
loop is lightweight, and post-profile MSPT is a noisy 100-tick sample. Exact
score deltas and the existing prototype fixture checks support semantic parity
for the specialized operation; this profile does not close remaining P0 or
compatibility gates. Both prototypes remain disabled by default.

A separate 12-second diagnostic run, `20261028T140627Z-5564ad`, enabled
per-command ScoreAdd counters to verify that the real dispatcher actually
called the specialized entry. It compiled one `erb:runtime_tick` entry and
recorded 340 executions while `#tick_id` advanced by exactly 340; the no-event
integrity gate passed, with one active group and no event-specific markers.
This confirms invocation coverage for the pilot. Because instrumentation was
enabled, its Spark timings are excluded from performance comparisons.

### Randomized compiler A/B pilots on mod stacks

Four additional randomized 12-second pairs ran the same no-TNT dispatcher
scenario on the exact pinned Minecraft 26.3 server, Spark 1.10.194, and
Blastback archive. Each run passed the no-event integrity gate. The ScoreAdd
arm compiled one command in `erb:runtime_tick`; the off arm compiled none.
`#tick_id` counts match within three pairs. The Lithium pair differs by one
tick, illustrating why timed Spark captures are not the parity oracle. Exact
semantic comparisons remain in the fixed-invocation differential harness.

| Stack | Order | compiler-off / ScoreAdd run IDs | `#tick_id` delta off/on | `ServerFunctionManager.execute` weighted samples off/on |
|---|---|---|---:|---:|
| Lithium | ScoreAdd → off | `20261028T141027Z-360dc2` / `20261028T140940Z-4f1c73` | 341 / 340 | 220 / 48 ms |
| Bellows 1.1.2 | off → ScoreAdd | `20261028T141114Z-c6c190` / `20261028T141201Z-00e7a8` | 340 / 340 | 28 / 8 ms |
| Lithium + Bellows 1.1.2 | ScoreAdd → off | `20261028T141335Z-1e8549` / `20261028T141248Z-17c638` | 340 / 340 | 44 / 296 ms |
| Lithium + Bellows 1.1.2 + Moonrise 1.2.0 | off → ScoreAdd | `20261028T141423Z-036d09` / `20261028T141510Z-c5e6c7` | 341 / 341 | 28 / 104 ms |

The sample direction varies: the ScoreAdd capture is lower for Lithium and
Bellows alone, and higher for Lithium+Bellows and the three-mod stack. These
are short, single pairs with low sample counts, not a speedup estimate. They
show the optimized command remains reachable on these compatible stacks; the
runtime differential matrix, not the capture duration, is the behavior-parity
gate. Bellows + Moonrise 1.2.1 is not represented because that pinned stack
fails server startup; Moonrise 1.2.0 is the bootable three-mod profile.

Dynamic Lights by darpanshete 1.0.0 remains rejected for this target: its pack
metadata declares an invalid format range and the server cannot resolve its
load and tick functions. This is separate from the CreepermeYT datapack
selected above.

## Vein Miner 5.3.0 native-trigger eligibility and profile pilot

The [Vein Miner datapack](https://modrinth.com/datapack/vein_miner) publishes
version 5.3.0 for Minecraft 26.3 under GPL-3.0-only. Its Modrinth slug is
`vein_miner` (with an underscore). It is a different project from
[VeinMiner](https://modrinth.com/datapack/veinminer) (without an underscore),
whose page offers a V1 datapack and a V2 mod/plugin. The separate V1 1.3.6
26.3 datapack is retained as a negative eligibility candidate; it has no
direct literal fake-holder ScoreAdd site and is not the PERF-011 workload.
Our pinned 5.3.0 archive has SHA-256
`fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`.
The archive has 76 functions. It contains three direct literal fake-holder
ScoreAdd sites: `vm:player/register` increments `#next_id`,
`vm:detection/ray_step` increments `#ray`, and `vm:queue/drain` increments
`#head`. The active native mining path reaches the ray-step and queue-drain
entries. The earlier direct-entry scan found no adjacent eligible pair; a
2026-11-03 static screen found 145 adjacent parsed candidates in
`vm:detection/acquire_target` and 59 in `vm:detection/verify_mined_stat`, so
the archive is a static fused candidate, but runtime specialization and
performance remain unmeasured.

The repeatable driver is `scripts/run_veinminer_profile.py`. It pins the
datapack, official 26.3 server, and Spark hashes; creates a deterministic ore
cube; joins a headless survival player; verifies the datapack ray target; and
sends native start/stop destroy-block packets. It then records pack state,
ScoreAdd compile/execution counters, Spark samples, and tick percentiles. Run
outputs are retained under the ignored `build/benchmarks/PERF-011-veinminer/`
directory; each temporary world and server log directory is deleted.

The 4×4×4 fixture passes the native trigger and workload-integrity check on
vanilla and Fabric compiler-off/ScoreAdd-on. Each run processes 63 blocks and
records a 480 `#head` delta, zero remaining ore, no operation marker, and an
idle player run score. A 6×6×6 vanilla run finishes 215 blocks and records
1,952 queue increments. The harness verifies the post-event block volume with
one generated in-game function, avoiding hundreds of separate RCON calls.

Five seeded randomized pairs ran on a Fabric development server with no extra
mods, each processing a fresh 6×6×6 vein. All ten arms pass native-trigger and
workload-integrity gates and match exact block, source, player-work, queue, and
operation state within each pair. A separate instrumented Fabric capture
compiled one `vm:queue/drain` ScoreAdd and recorded 1,952 executions, exactly
matching the queue counter. Instrumented timing is excluded from the campaign.
The campaign report and raw Spark captures are retained under
`build/benchmarks/PERF-011-veinminer/`.

Five-pair Fabric ScoreAdd/off median relative changes are −0.19% in event
completion time (range −22.43% to +1.89%), −4.35% in average tick time
(−30.00% to +4.35%), −15.38% in P95 tick time (−64.58% to +65.17%), and +0.31%
in weighted `ServerFunctionManager.execute` samples (−23.51% to +1.76%). The
large pairwise ranges and mixed metric directions do not establish a reliable
gain or regression. Keep ScoreAdd disabled.

A separate instrumented 6×6×6 native event compiled the `vm:queue/drain`
ScoreAdd entry and recorded 1,952 executions, matching the `#head` delta. It
also compiled `vm:detection/ray_step` and recorded 4,212 `#ray` additions.
Instrumentation is excluded from performance comparisons.

### Callback accounting on a native event

`scripts/run_veinminer_profile.py --stack lithium --compiler-mode
score-add-instrumented --side 4 --count-command-callbacks` enables an opt-in
diagnostic that wraps ordinary Brigadier leaf callbacks in function queues
and counts all queue callbacks during the native mining event. The run
processed the full 63-block vein, advanced `#head` by 480, and completed with
no ore or operation marker remaining. It counted 8,238 ordinary leaf
callbacks: 7,116 generic callbacks and 1,122 optimized ScoreAdd callbacks
(13.6% of the counted callbacks in this run). The optimized callback count
exactly matched the independent ScoreAdd execution counter; the two measured
functions accounted for 480 queue-drain additions and 642 ray-step additions.

This closes the generic callback-accounting gate for the tested Vein Miner
event. It is one controlled event, not a frequency estimate for other packs or
server loads. The diagnostic excludes execute modifier operations and custom
command executors. It adds callback wrappers and is explicitly unsuitable for
timing comparisons; use ordinary runs with callback counters disabled for
performance evidence. Historical event timing still had Spark sampling active;
the campaign now uses `--no-spark` for primary timing. The runner's callback
metric option remains disabled by default.

Five additional randomized 6×6×6 compiler-off/ScoreAdd pairs ran on Fabric +
Lithium 0.26.2. All ten arms pass the native mining and integrity gates; each
pair matches 215 work items, 1,952 `#head` increments, source-block removal,
empty ore volume, player-work state, and cleared operation markers. The
ScoreAdd arm compiled the eligible queue entry; the profiler records are
un-instrumented. Median paired changes are +12.47% in event completion time
(range −2.38% to +101.19%), +12.46% in weighted
`ServerFunctionManager.execute` samples (−1.77% to +102.86%), +15.79% average
tick time (−9.09% to +52.63%), and +6.06% P95 tick time (−15.79% to +40.00%).
The fifth ScoreAdd arm is a large outlier: 60.19 seconds versus 29.92 seconds
for its pair's compiler-off arm. Tick percentile directions vary. This is no
evidence of a gain and a regression signal to investigate, not a stable causal
estimate. Details and raw profiles are in the ignored
`build/benchmarks/PERF-011-veinminer/` tree.

Five additional randomized pairs ran on Lithium 0.26.2 + Moonrise 1.2.1. Every
arm processed 215 blocks, advanced `#head` by 1,952, removed the source, left
the ore volume empty, and cleared operation markers; each pair matched exact
workload state. Median ScoreAdd changes were +19.98% event completion time
(range −23.53% to +33.73%), +21.62% weighted
`ServerFunctionManager.execute` samples (−24.21% to +37.79%), +37.67% average
tick time (−31.31% to +54.29%), and +30.53% P95 tick time (−47.39% to
+45.90%). Every metric range crosses zero, so this is not a robust regression
estimate, but there is no evidence of a speedup. This campaign included a
temporary dormant diagnostic mixin in both arms, so treat it as directional
evidence rather than a final product-build performance estimate. Raw files are
in the ignored `build/benchmarks/PERF-011-veinminer/` tree.

### Profile-derived cost-center lead: entity NBT used for macro arguments

The local Spark analyzer can now reconstruct selected call paths from a
`.sparkprofile`, not only aggregate method names. Across all 15 valid
compiler-off captures (five each on Fabric, Lithium, and Lithium+Moonrise
1.2.1), the leading sampled path to `Entity.saveWithoutId` passes through
`FunctionCommand` argument construction:

```text
FunctionCommand$2.arguments
  -> FunctionCommand.getArgumentTag
  -> DataCommands.getSingleTag
  -> EntityDataAccessor.getData
  -> NbtPredicate.getEntityTagToCompare
  -> Entity.saveWithoutId
```

Static inspection of the pinned Vein Miner archive shows two hot-path calls
using `with entity @s data`: `vm:queue/drain` passes marker data to
`vm:queue/load_next`, and each `vm:queue/visit` reaches
`vm:operation/dispatch`, which passes marker data to
`vm:operation/dispatch_match`. The target macros use only selected values such
as `head`, `x/y/z`, and `match`, while the argument provider first obtains the
entity's serialized data compound. The profiles and source together make this
a concrete optimization candidate: avoid repeatedly serializing unrelated
entity state when a macro expansion consumes only a small known set of fields.

This began as a cost-center lead rather than an exclusive timer. The selective
argument prototype below now intercepts this bounded path and keeps unsupported
cases on Minecraft's original helper. Focused semantic checks and a native Vein
Miner diagnostic confirm that the candidate is exercised. The performance
result remains specific to the pinned workload, server, and stack.

#### Controlled queue-size profile

The existing PERF-011 harness was extended with a 5×5×5 vein to place an
intermediate point between its 4×4×4 and 6×6×6 workloads. Valid vanilla runs
show the following native event sizes:

| Vein size | Work completed | `#head` delta | Completion time | Macro-argument path to `Entity.saveWithoutId` |
|---|---:|---:|---:|---:|
| 4×4×4 | 63 | 480 | 3.01 s | 436 weighted samples |
| 5×5×5 | 124 | 1,056 | 9.89 s | 2,708 weighted samples |
| 6×6×6, run A | 215 | 1,952 | 31.40 s | 9,268 weighted samples |
| 6×6×6, run B | 215 | 1,952 | 29.60 s | 8,728 weighted samples |

Each profile passed the native workload-integrity checks. The path metric is
the inclusive Spark sample weight for
`FunctionCommand$2.arguments -> FunctionCommand.getArgumentTag ->
DataCommands.getSingleTag -> EntityDataAccessor.getData ->
NbtPredicate.getEntityTagToCompare -> Entity.saveWithoutId`; it is not an
exclusive timer. The increasing path samples justified a selective-argument
prototype and a matched performance comparison, but these four profiles are an
exploratory size sweep, not randomized evidence of a speedup. The 8×8×8 attempt
did not produce a valid result: Minecraft's watchdog terminated the server
before the harness could finish its workload checks. Exclude that attempt from
performance analysis.

The candidate boundary is now concrete: consider only `function ... with
entity @s data` where the resolved call contains exactly one macro function and
every macro parameter is a present top-level key in the entity's custom-data
compound. Construct the argument compound from copies of those values, then
let Minecraft perform its normal macro instantiation and caching. Keep the
vanilla `getArgumentTag` path for missing keys, non-macro or multi-function
calls, other data providers, other NBT paths, and any unsupported case. The
implementation is a disabled research prototype. Its focused vanilla
differential covers present and missing fields, a second macro parameter,
multi-function and non-macro fallbacks, `/debug function`, and sequence quotas.
Focused run `20261029T181645` adds a present but invalid entity value
(`amount:"not_an_integer"`) and a composite entity value on Lithium+Bellows
1.1.3. Vanilla, same-stack compiler-off, and the selective path have identical
before/error/after scores and exact nested debug traces; the selected-path
count advances once, and the outer function continues without replaying its
preceding side effect. The composite case copies a nested compound containing
an int array and string list into storage, then reads back each nested value
identically; its selected-path count also advances once. The same two cases
pass on Lithium+Bellows 1.1.3+Moonrise 1.2.0 with identical vanilla/off/
candidate state and traces; both candidate path counters advance once. The raw
reports are `build/reports/runtime-probe/macro-20261029T181645.results.json`
and `build/reports/runtime-probe/macro-20261029T181942.results.json`.
The native Vein Miner profile below confirms call-site use. Cross-stack
compatibility, reload races, broader macro command shapes, and the remaining
P0 cases are still open.

Reconstruct the call path from a retained local capture with:

```sh
python3 scripts/analyze_spark_profile.py \
  build/benchmarks/PERF-011-veinminer/<run-id>/veinminer.sparkprofile \
  --method Entity.saveWithoutId --paths 3
```

### Selective macro prototype and randomized PERF-011 comparison

The implementation is opt-in through
`FC_SELECTIVE_MACRO_ARGUMENTS=true`; it stays disabled by default. The fast path
only handles a single resolved macro function, `with entity ... data`, and
present top-level parameters in entity custom data. It builds an argument
compound from copies of those selected values. Missing fields, non-macro or
multi-function targets, alternate providers and paths, and any unrecognized
shape call Minecraft's original `FunctionCommand.getArgumentTag` helper.

The focused 26.3 differential matched mod-free vanilla for macro scores,
multi-parameter state, error results, sequence quota state, and the complete
`/debug function` trace. Metrics confirmed two direct eligible fixture calls,
then one additional selected call under the debug trace; multi-function,
plain-function, and missing-argument paths did not increment the counter.

A separate metrics-enabled diagnostic on Vein Miner 5.3.0 completed a native
4×4×4 event (63 blocks and 480 queue increments) and counted 2,650 selected
macro argument constructions during the mining event. That run is diagnostic
only and is excluded from timing results.

Five randomized Fabric pairs then compared compiler-off with
`selective-macro` on a 6×6×6 event. Spark sampled all threads at 4 ms during
these historical event-timing runs; Function Compiler counters were disabled,
but event completion time was measured with the sampler active. All ten arms
processed 215 blocks, advanced
`#head` by 1,952, removed the source, emptied the ore volume, cleared operation
and target markers, and matched exact workload state within each pair.

| Metric | Paired median change | Pair range | Reading |
|---|---:|---:|---|
| Event completion time | −23.61% | −30.76% to −16.63% | Lower in all five candidate arms |
| Inclusive `ServerFunctionManager.execute` Spark samples | −24.86% | −33.58% to −18.56% | Lower in all five candidate arms |
| Average tick time | +8.82% | −5.26% to +18.18% | No consistent improvement |
| P95 tick time | +3.39% | −16.67% to +62.50% | No consistent improvement; wide range |

Inspecting the saved Spark trees shows the intended path changed. The inclusive
sample weight on `FunctionCommand$2.arguments` paths that reach
`Entity.saveWithoutId` fell in every pair:

| Pair | Selective macro samples | Compiler-off samples |
|---|---:|---:|
| 1 | 1,548 | 8,088 |
| 2 | 1,600 | 8,768 |
| 3 | 1,584 | 7,880 |
| 4 | 1,568 | 8,260 |
| 5 | 1,012 | 5,856 |

The median reduction for this reconstructed macro-argument path is 81.02%.
Total `Entity.saveWithoutId` method samples fell by a median 26.67%. These are
inclusive Spark sample weights, not exact elapsed-time measurements; other
entity-NBT command paths remain in both profiles. The aligned reduction in
event completion, scheduled-function samples, and the targeted serialization
path is promising evidence for this workload, not proof of a general server
speedup.

The same five-pair comparison also passed on Lithium 0.26.2 and Lithium 0.26.2
+ Moonrise 1.2.1. All 20 arms across these two stacks matched the exact native
workload state. The candidate is enabled in all selective arms; macro-argument
metrics remain off during captures. Reconstructed macro-argument sample-path
reductions are also consistent across stacks:

| Stack | Completion-time median (range) | `ServerFunctionManager.execute` median (range) | Macro-argument path sample reduction median (range) |
|---|---:|---:|---:|
| Fabric | −23.61% (−30.76% to −16.63%) | −24.86% (−33.58% to −18.56%) | −81.02% (−82.72% to −79.90%) |
| Lithium 0.26.2 | −34.75% (−46.48% to −19.91%) | −36.14% (−47.95% to −21.08%) | −84.51% (−87.49% to −80.73%) |
| Lithium + Moonrise 1.2.1 | −34.50% (−56.82% to +0.87%) | −36.83% (−59.93% to +2.11%) | −83.10% (−89.34% to −77.44%) |

The completion and scheduled-function sample medians are lower on all three
stacks; 14 of the 15 pairs are lower on both metrics, with the remaining
Lithium+Moonrise pair close to flat. Post-capture tick query results remain
noisy: average and P95 tick deltas have wide ranges, particularly on Fabric and
Lithium. Treat the paired native-event completion and profiler call-path
reductions as promising repeated evidence for this targeted workload. They do
not establish a broad MSPT or whole-server speedup.

## Selective macro compatibility fixture

The same Minecraft 26.3 macro fixture was then run in three arms on each
compatible pinned stack: official mod-free vanilla, same-stack compiler-off
Fabric, and the selective macro candidate. All three outcomes matched for
macro state, errors, provider fallbacks, debug trace, and sequence quotas on
Fabric; Lithium 0.26.2; Bellows 1.1.2; Bellows+Moonrise 1.2.0;
Lithium+Moonrise 1.2.1; Lithium+Bellows; and
Lithium+Bellows+Moonrise 1.2.0. The runner stores the exact mod filenames and
SHA-256 values in each result. Bellows+Moonrise 1.2.1 remains excluded because
it fails to start in this 26.3 setup.

Focused follow-up runs on Lithium+Bellows 1.1.3 and the same stack with
Moonrise 1.2.0 cover a present wrong-typed entity argument, copying a nested
compound/list/int-array entity value, and a present wrong-typed storage-provider
argument. The entity error and copied composite value match vanilla and
compiler-off, with one selected-path hit each. For the storage-provider error,
all three arms match the exact nested `/debug function` trace and surrounding
score effects, while the candidate's entity fast-path counter stays at zero.
Reports: `build/reports/runtime-probe/macro-20261029T181645.results.json`,
`build/reports/runtime-probe/macro-20261029T181942.results.json`,
`build/reports/runtime-probe/macro-20261029T182217.results.json`, and
`build/reports/runtime-probe/macro-20261029T182321.results.json`.

A further fallback case supplies both root and nested values, then invokes the
macro with entity path `data.nested`. The native path selects the nested value
7; vanilla, compiler-off, and candidate match surrounding side effects and the
full `/debug function` trace, while the candidate selected-path counter stays
at zero. This passes on Lithium+Bellows 1.1.3 and the same stack with Moonrise
1.2.0. Reports:
`build/reports/runtime-probe/macro-20261029T182921.results.json` and
`build/reports/runtime-probe/macro-20261029T183028.results.json`.

This closes the focused selective-argument compatibility fixture for these
stacks. It does not validate every mod-provided macro command/provider, the
ScoreAdd/fused/bytecode backends on every stack, or a Bellows Vein Miner
workload. The candidate remains disabled while the broader P0, reload, and
memory gates remain open.

Bellows-containing PERF-011 arms remain excluded because the pinned datapack
fails its native workload gate there before Function Compiler is enabled. Keep
the prototype disabled until the remaining P0 semantics, compatibility, reload
and memory gates are complete.

The campaign records and raw profiles are under the ignored
`build/benchmarks/PERF-011-veinminer/` directory. Fabric, Lithium, and
Lithium+Moonrise reports use seed 26871028 and five randomized pairs each.
These are screening pilots. A distribution-free interval for the median from
five pairs can achieve at most 93.75% coverage and spans the full observed pair
range; none of these runs had a predeclared promotion threshold. The campaign
has since gained a no-Spark timing arm and preregistered confirmatory mode. A
separate 4×4×4 Fabric/selective-macro no-Spark smoke run passed native
integrity (63/63 blocks, 480 queue increments, no remaining ore or markers)
in 3.88 seconds. It validates that arm and the workload oracle, not a speed
gain. Its `/tick query` was post-event and does not measure active-load MSPT.

The local campaign record and raw profiles are under the ignored
`build/benchmarks/PERF-011-veinminer/` directory. To reproduce the five-pair
Fabric comparison:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_veinminer_campaign.py \
  --stack fabric --side 6 --candidate selective-macro --phase screening --pairs 5 \
  --seed 26871028 --capture-timeout 60
```

PERF-007's generic callback-accounting gate is verified for this Vein Miner
event. Bellows 1.1.2 failures remain version-specific compatibility history:
Bellows alone and Lithium+Bellows at 4×4×4 processed 0/63 blocks, while
Lithium+Bellows+Moonrise 1.2.0 at 6×6×6 processed 0/215. Those compiler-off
runs establish a datapack/mod workload failure for the pinned 1.1.2 stacks;
they do not establish compiler behavior or general Bellows incompatibility.
The user-reported no-underscore Miraculixx VeinMiner 1.3.6 comparison remains a
separate datapack and is not a parity control. Moonrise 1.2.1 still does not
start with Bellows 1.1.2.

The user reports that Bellows maintainers closed the issue and released 1.1.3.
Modrinth identifies artifact `QoiW2Z70` as Bellows 1.1.3 for Minecraft 26.3 on
Fabric; its release notes say that some NBT paths in data commands were fixed.
The jar is pinned above and in the local profile runner as `bellows113`, with
separate stack IDs for Lithium and Moonrise combinations. The 1.1.2 failures
above are historical and do not establish whether 1.1.3 fixes the workload.
The Bellows-only compiler-off 4×4×4 run passed its native workload gate:
63/63 blocks, `#head` +480, and clean source/operation/target state. The
Lithium+Bellows 1.1.3 compiler-off 6×6×6 no-Spark run also passed: 215/215
blocks, `#head` +1,952, and clean source/operation/target state. Two separate
selective-macro diagnostics on Lithium+Bellows counted 9,546 and 9,547 eligible
calls while processing the same 215-block event; counters were enabled, so
those arms are activation evidence and not timing evidence.

Five randomized no-Spark off/on pairs then screened selective macro on
Lithium+Bellows 1.1.3. All ten arms passed exact workload checks and each pair
matched 215 work items, 1,952 `#head` increments, source removal, empty ore,
and cleared markers. Event completion had a −18.83% median paired change
(lower is faster), with pair changes from −20.62% to +24.37%. The exact
distribution-free median interval achieved 93.75% coverage and spans the same
range, so this is screening evidence only; one pair was slower with the
candidate. The campaign is
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-selective-macro-5pairs-seed26871029-20261029T051440Z.json`.
The post-event `/tick query` values are not an active-workload MSPT comparison.
A 15% event-time gain is selected as the worthwhile threshold for a
Lithium+Bellows 1.1.3 selective-macro confirmation. Under the current protocol,
the exact two-sided median interval must support at least that gain. Before
confirmation, the project registered 23 randomized off/on pairs on `lb113`,
using event-completion seconds as the sole primary metric and seed `26871037`.
For 23 pairs, the exact order-statistic interval has 96.531% coverage (the 7th
through 17th ordered paired changes); the interval's upper endpoint must be at
or below −15% to meet the target. The count is fixed before collection, and the
run will not stop early for a favorable result. All pairs must pass exact
workload parity; failures stay in the campaign record and do not count as
timing pairs.

The confirmatory run completed all 23 pairs. All 46 arms passed exact workload
integrity (215 blocks and 1,952 `#head` increments per arm). The median paired
event-time change is −19.27%; 21 pairs were faster and 16 were at least 15%
faster. The full pair range is −46.80% to +45.98%. The 96.531% exact median
interval is −27.09% to −13.03%: it excludes zero, supporting a faster median,
but does not establish the preselected 15% minimum. The registered decision is
therefore inconclusive for promotion; keep the prototype disabled. The raw
campaign is
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-selective-macro-23pairs-seed26871037-20261029T161947Z.json`.

The exact registered command was:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_veinminer_campaign.py \
  --stack lb113 --side 6 --candidate selective-macro --phase confirmatory \
  --pairs 23 --seed 26871037 --minimum-gain-percent 15 \
  --primary-metric operation_completion_seconds --capture-timeout 60
```
A separate five-pair no-Spark ScoreAdd screen on the same stack also passes
exact workload parity in every arm. Its median event-completion change is
+3.60% (slower), with pair changes from −2.04% to +91.11% and 93.75% exact
median-interval coverage; this is screening evidence, not a confirmed
regression. The separate activation diagnostic counted exactly 1,952 compiled
`#head` executions, matching the datapack counter. The raw campaign is
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lb113-score-add-5pairs-seed26871030-20261029T053118Z.json`.

The focused selective-macro fixture passes on Lithium+Bellows 1.1.3+Moonrise
1.2.0 (`lbm113120`), and the native Vein Miner 5.3.0 6×6×6 compiler-off
control also passes (215 blocks, 1,952 `#head` increments, clean final state).
A five-pair no-Spark selective-macro screen on this stack passes exact work
parity in every arm. Event completion has a −20.11% median paired change, with
pair changes from −36.67% to +7.01%; the exact interval achieved 93.75%
coverage, so this remains screening evidence. The campaign is
`build/benchmarks/PERF-011-veinminer/campaigns/vein-6-lbm113120-selective-macro-5pairs-seed26871036-20261029T153147Z.json`.
The previously selected 15% worthwhile-gain threshold for selective macro
applies to this stack; no confirmatory sample plan has been set. Lithium+Bellows
1.1.3+Moonrise 1.2.1 (`lbm113`) still fails
startup on Bellows' `MoonriseEntityLookupMixin`: its `EntityLookup.entityById`
shadow is missing from the pinned Moonrise target, so no datapack workload
comparison was run there.

A 2026-11-03 static screen found 145 adjacent parsed candidates in Vein Miner's
`vm:detection/acquire_target` and 59 in `vm:detection/verify_mined_stat`, so it
is a static fused candidate even though runtime specialization and performance
remain unmeasured. Its queue is drained after mining and idle between events,
making this a player-triggered traversal burst rather than continuous idle tick
load.

The original 15 ScoreAdd pairs cover Fabric, Fabric+Lithium, and
Fabric+Lithium+Moonrise 1.2.1; none demonstrates a reliable gain. The new
Lithium+Bellows 1.1.3 selective-macro and ScoreAdd screens are additional
stack results, not confirmatory performance claims. Keep all prototypes
disabled pending the remaining semantic, compatibility, and confirmatory
performance gates.
