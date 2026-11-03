# Function Compiler implementation sanity audit

**Date:** 2026-10-28  
**Target reviewed:** Minecraft Java 26.3, Fabric, server-side  
**Purpose:** Check scope alignment, design clarity, implementation breadth, and
performance evidence after the first compiler-backend and real-datapack test
campaigns.

## Assessment

Work remains aligned with the stated goal: investigate faster function
execution while preserving vanilla behavior, validate exact 26.3 internals,
prototype distinct execution paths, and measure them on repeatable workloads.
The source audits, differential fixtures, mod-compatibility matrices, and
datapack profiles all serve those questions. The remaining risk is breadth:
adding more pack screens or one-off profiles can consume time without closing
the P0 correctness and performance gates. The next work should close open
matrix cases and validate the profile-backed entity-NBT argument candidate
instead of expanding command coverage speculatively.

The workload search has had some diminishing-return exploration: several
candidate packs were screened only to discover unstable populations, failed
restoration, or no eligible commands. That was useful for establishing
selection criteria, and Vein Miner now satisfies the real-pack direct-ScoreAdd
gate. Further pack discovery should be limited to the specific missing
fused/bytecode workload: a pinned pack with adjacent eligible commands and a
stable, parity-checkable trigger. General candidate browsing is no longer the
best use of effort.

The goal and governing design are still clear: vanilla 26.3 is the behavior
oracle; preserve scheduling, frames, limits, callbacks, tracing, errors,
reload behavior, and compatible mod hooks; retain vanilla fallback; keep every
optimization opt-in. No backend has been accepted or enabled by default.

During this pass the only runtime-adjacent code change was adding resumable
campaign-report support to the Vein Miner benchmark runner, so an interrupted
campaign could retain and continue its completed randomized pairs. No compiler
semantics or supported command forms changed during the audit.

There is a scale gap to keep explicit. The project plan describes a future
general function compiler and typed IR, while the code currently tests one
scoreboard command form through three execution approaches. This is a narrow
research prototype, not a general-purpose command compiler. Fused and bytecode
prototypes group or emit that same ScoreAdd form; they do not broaden the set of
commands understood by the compiler.

## Quantified implementation and test coverage

| Area | Current evidence |
|---|---|
| Test inventory | 79 matrix IDs: 72 P0 and 7 P1. Matrix status is free text and many P0 entries record partial coverage, so a raw “passed test count” would overstate closure. |
| Runtime modes | Eight arms for the main differential suite: mod-free vanilla plus seven Fabric modes (wrapper off/on, ScoreAdd, timer-only, timed ScoreAdd, fused-interpreted, and emitted bytecode). |
| Function/control-flow probes | 16 direct function fixtures, plus separate quota/fork sweeps, scoreboard edge cases, macros, reloads, traces, and compatibility matrices. These are scoped fixtures, not exhaustive command coverage. |
| Optimized command forms | One Brigadier leaf shape: `scoreboard players add` with a single literal fake holder beginning `#`, a literal objective, and a parsed integer amount. A selector as the ScoreHolder target is excluded. The same leaf may be specialized after macro expansion. |
| Execution approaches | The ScoreAdd callback specialization; a fused interpreter for runs of at least two adjacent eligible non-forked entries; and an ASM bytecode emitter for those regions. The latter two do not add new command forms. All remain disabled by default. |
| Fallback and support accounting | Unrecognized commands remain vanilla actions. An opt-in wrapper counts ordinary Brigadier leaf callbacks in function queues, separating generic callbacks from optimized ScoreAdds; modifier operations and custom command executors are excluded. |

The pinned Vein Miner 5.3.0 archive has three direct literal fake-holder ScoreAdd
sites across 76 functions: player ID allocation, ray-step accounting, and
queue-head advancement. A native 6×6×6 event exercises two hot-path sites.
One instrumented run recorded 4,212 `vm:detection/ray_step` additions and
1,952 `vm:queue/drain` additions. This is 6,164 observed specialized callbacks
across two function entries in that run; it is not a percentage of all command
dispatches. The pack contains no adjacent eligible pair in the direct-entry
scan, so it cannot measure the fused or bytecode region paths. A 2026-11-03
static screen later found adjacent parsed candidates in the family-detection
and mined-stat functions, but runtime confirmation and performance remain
unmeasured.

A separate aligned 4×4×4 callback-accounting diagnostic on Lithium counted
8,238 ordinary leaf callbacks in one native mining event: 7,116 generic and
1,122 optimized ScoreAdds (13.6%). The optimized count matches the independent
ScoreAdd execution counter and consists of 480 queue-drain plus 642 ray-step
calls. This is one instrumented event, not a timing result or general
estimate; modifiers and custom executors are outside the count.

## Performance evidence

| Measurement | Result | What it supports |
|---|---|---|
| ScoreAdd callback-only static timer | 41.0% lower median callback time | A narrow callback result only; it omits scheduler and function-queue overhead. |
| ScoreAdd full-function static timer | 14.8% slower median than the vanilla delegate | No ScoreAdd gain on the tested 5,000-add function. |
| Fused interpreted static function | 40.8% lower median queue time than delegate and 36.0% lower than ScoreAdd | A promising result for one static fixture; timer calibration and generality remain open. |
| Emitted bytecode static function | 24.4% lower median than delegate but 23.0% slower than fused interpretation | Bytecode is not selected on current evidence. |
| Vein Miner native event, Fabric | Five randomized pairs had exact workload-state parity. Median paired changes: −0.19% completion time and +0.31% weighted `ServerFunctionManager.execute` samples. | No reliable gain or regression was established. |
| Vein Miner native event, Fabric + Lithium | Five randomized pairs had exact workload-state parity. Median changes: +12.47% completion time, +12.46% weighted function samples, +15.79% average tick time, and +6.06% P95 tick time. Completion deltas ranged −2.38% to +101.19%; function-sample deltas ranged −1.77% to +102.86%. | No gain. The consistently positive medians and large outlier are a regression signal that needs diagnosis/repetition; these data do not justify enabling ScoreAdd. |
| Vein Miner native event, Fabric + Lithium + Moonrise 1.2.1 | Five randomized pairs had exact 215-block workload-state parity. Median changes: +19.98% completion time, +21.62% weighted function samples, +37.67% average tick time, and +30.53% P95 tick time. Each metric range crosses zero. | No gain demonstrated. The medians trend slower, but the spread does not establish a stable causal regression; both arms also carried a temporary dormant diagnostic mixin. |
| Vein Miner callback accounting, one 4×4×4 Lithium event | 1,122 of 8,238 ordinary leaf callbacks were optimized ScoreAdds (13.6%); that count matched the independent ScoreAdd execution counter. | Shows the reachable callback share for this event, not CPU time or a general workload share. |
| Vein Miner compiler-off profile call paths | In all 15 valid captures, the leading path to `Entity.saveWithoutId` goes through `FunctionCommand` macro argument construction and `DataCommands.getSingleTag`. | A stronger target lead than ScoreAdd: repeated `with entity @s data` calls serialize entity NBT for macros that consume only selected keys. This is sampled attribution, not exact exclusive time; validate with a controlled selective-argument prototype. |

The Lithium campaign's 60.19-second ScoreAdd completion in pair 5 is a large
outlier; its paired compiler-off completion was 29.92 seconds. Tick percentile
directions are mixed, and both completion and function-sample deltas include
observations on either side of zero. The positive medians are a warning to
investigate, not a stable causal regression estimate. The evidence still does
not show a real-world speedup.
Raw profiles, manifests, and exact pins remain under the ignored local
`build/benchmarks/PERF-011-veinminer/` directory.

Dynamic Lights and Spawn Animations establish real recurring and bursty
function workloads, respectively, but neither supplies eligible ScoreAdd work
for these prototypes. Vein Miner supplies eligible direct ScoreAdd work but is
event-triggered. A 2026-11-03 static screen later found adjacent candidates in
several packs, but none has runtime confirmation. Therefore the current
evidence includes a real-pack direct-ScoreAdd comparison, but no real-pack
fused/bytecode comparison and no demonstrated real-world optimization gain.

## Audit conclusion and next gate

The project is on track, with one important scope caveat: describe current
support as one optimized command form and three candidate execution approaches,
not as broad command compilation. The runtime behavior goal has not drifted;
all implementations remain experimental and disabled. Synthetic measurements
show lower queue-time medians for fused interpretation (40.8% versus delegate)
and emitted bytecode (24.4% versus delegate, but 23.0% slower than fused).
Those results are limited to a static fixture with uncalibrated timer overhead;
neither has shown a real-datapack speedup.

The implementation pause begins before the broader P0 gates are closed. The
three Vein Miner stack campaigns show no real-world ScoreAdd speedup; stop
expanding ScoreAdd as the primary target. A new call-path review of all 15
valid compiler-off profiles finds repeated `FunctionCommand` macro argument
construction followed by full entity serialization in `Entity.saveWithoutId`.
The pack's queue functions pass `with entity @s data` while their macro targets
consume only a small set of fields. This is a profile-backed optimization
candidate, not yet an implementation design or proof of exclusive cost. The
next work should vary queue size in a controlled run and compare the full-data
path with a semantics-preserving selective-argument prototype. Keep that path
disabled until missing-value, error, reload, and vanilla parity gates pass.
Compiler-off Vein Miner controls fail workload integrity on the pinned
Bellows-containing stacks, so do not repeat its compiler comparison there.
Before treating the Lithium or Lithium+Moonrise medians as regressions, inspect
their outliers and repeat or stabilize the measurements. Keep fused and
bytecode real-world gates open until a pinned, runtime-validated pack contains
adjacent eligible commands. Continue Bellows compatibility testing with a
workload that succeeds when the compiler is off. No default enablement is
justified by the current record.
