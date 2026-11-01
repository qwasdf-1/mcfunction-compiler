# Function Compiler follow-up sanity audit

**Date:** 2026-10-29  
**Target reviewed:** Minecraft Java 26.3, Fabric, server-side  
**Purpose:** Recheck project direction, behavioral design, implemented command
scope, and measured performance after the selective macro argument prototype.

## Assessment

The project remains focused on its stated goal: speed up hot function paths
while preserving vanilla behavior. The selective macro argument path came from
repeated Spark evidence in a pinned real workload, and its prototype was
measured on the same workload with compiler-off controls. This is a direct
continuation of the profiling plan, not a tangent.

The earlier pack screening and Bellows compatibility work answered specific
gates. Stop broad datapack discovery for now. The pinned Vein Miner 5.3.0 pack
cannot provide a Bellows performance comparison because it fails its own
compiler-off workload checks on the tested Bellows stacks. Only resume pack
search for a named open gate, such as a valid Bellows workload or a real pack
with adjacent eligible commands for fused and bytecode profiling.

The strongest current performance signal is selective construction of macro
arguments from entity custom data. Across Fabric, Lithium, and
Lithium+Moonrise, the candidate reduced the profiled macro-argument serialization
path and had lower paired event completion and scheduled-function samples in
14 of 15 randomized pairs. This changes the near-term priority: keep ScoreAdd,
fused interpretation, and bytecode disabled; validate the profile-backed macro
path and close its semantic and compatibility gates before adding another
optimization target.

## Goal and design

The behavior contract remains clear: use vanilla 26.3 as the oracle, preserve
function scheduling, limits, macro expansion, errors, debug traces, reloads,
and mod hooks, and retain the original Minecraft path whenever an optimization
does not recognize its exact input. All prototypes remain disabled by default.

The new path is deliberately narrow. It handles a single resolved macro
function invoked with entity `data` when every macro parameter is a present
top-level key in custom data. It copies only the selected values into the
argument compound and lets Minecraft perform its normal macro instantiation
and cache lookup. Missing fields, ordinary functions, multi-function tags,
other providers, and unsupported NBT paths use the original
`FunctionCommand.getArgumentTag` helper.

The focused differential verifies the supported shape, a two-parameter macro,
missing parameters and data, ordinary and multi-function fallback, debug
tracing, and command sequence limits against mod-free vanilla. The native
Vein Miner event also matches compiler-off state on three stacks. These checks
do not close macro reload races, every error branch, or the full P0 matrix.

## Implemented scope and coverage

| Area | Current evidence |
|---|---|
| Validation inventory | 79 matrix IDs: 72 P0 and 7 P1. This is an inventory, not a pass count; many P0 rows remain partial or open. |
| Main behavior harness | Mod-free vanilla plus seven Fabric runtime modes for wrapper, ScoreAdd, timing, fused interpretation, and emitted bytecode. The focused macro probe also includes the selective argument mode. |
| Function fixtures | 16 direct function fixtures plus separate quotas, fork limits, scoreboard edge cases, macro/cache cases, tracing, reloads, and mod compatibility probes. These are focused cases, not exhaustive command coverage. |
| Optimized command shapes | One Brigadier leaf form: literal fake-holder `scoreboard players add` with literal objective and parsed integer amount. |
| ScoreAdd execution approaches | Callback specialization, fused interpreter, and emitted bytecode. Fused and bytecode group that same ScoreAdd form; neither adds command support. |
| Other optimization prototype | Selective macro argument construction reduces input serialization before native macro instantiation. It does not add a compiled command form. |

The accurate claim is **one optimized command form plus one bounded macro
argument optimization**, not a general Minecraft function compiler. The code
and reports should continue to use that distinction.

## Real workload evidence

Fifteen randomized compiler-off/selective-macro pairs used the pinned Vein
Miner 5.3.0 26.3 datapack on a fresh 6×6×6 native mining event. Every arm
processed all 215 blocks, advanced `#head` by 1,952, removed the source, emptied
the ore cube, and cleared operation and target markers. Every pair matched the
recorded workload state exactly.

| Stack | Completion-time median change (range) | `ServerFunctionManager.execute` sample median change (range) | Macro-argument path sample reduction (median) |
|---|---:|---:|---:|
| Fabric | −23.61% (−30.76% to −16.63%) | −24.86% (−33.58% to −18.56%) | 81.02% |
| Lithium 0.26.2 | −34.75% (−46.48% to −19.91%) | −36.14% (−47.95% to −21.08%) | 84.51% |
| Lithium + Moonrise 1.2.1 | −34.50% (−56.82% to +0.87%) | −36.83% (−59.93% to +2.11%) | 83.10% |

Fourteen of fifteen pairs were lower for both event completion and weighted
scheduled-function samples. The reconstructed
`FunctionCommand$2.arguments` to `Entity.saveWithoutId` path fell in every
pair. Total `Entity.saveWithoutId` samples also fell by a median 26.67% on the
Fabric campaign. These are inclusive Spark sampling weights, not exclusive CPU
timers.

The completion metric is wall-clock detection latency: the harness polls
workload state over RCON every half second. It is useful for matched paired
comparisons but is not an exact in-game timer. Post-profile tick percentiles
are noisy and do not establish a whole-server MSPT improvement. The evidence
supports a repeatable benefit on this specific large Vein Miner workload; it
does not establish a general speedup across datapacks or server populations.

The selective argument diagnostic counted 2,650 eligible argument builds
during one 4×4×4 mining event. That run used the optional hit counter and is
excluded from primary timing comparisons. The five-pair timing runs disabled
Function Compiler counters but had Spark CPU sampling active; they were not
fully unprofiled timing runs. New primary timing campaigns use `--no-spark`,
with Spark call-path attribution captured separately. The candidate remains
off by default.

## Audit conclusion and next gate

The optimization target is now better grounded than ScoreAdd: the profile
identified a repeated full-entity serialization path, the prototype preserves
native macro expansion and fallback, focused behavior matches vanilla, and
three randomized stack campaigns show large reductions in the targeted sampled
path. Continue with this candidate; do not enable it yet.

The focused selective macro fixture now passes three-way comparison against
mod-free vanilla and same-stack compiler-off Fabric on seven compatible pinned
stacks, including Bellows and the available Bellows+Moonrise 1.2.0 combinations.
The fixture covers selected macro errors, provider fallback, cache churn,
debugging, and quotas. Bellows+Moonrise 1.2.1 is startup-incompatible and was
excluded.

The 26.3 Lithium+Bellows 1.1.3 and Lithium+Bellows 1.1.3+Moonrise 1.2.0
follow-ups now also compare wrong-typed entity arguments, nested compound/list/
int-array copying, and a wrong-typed storage-provider argument. The alternate
provider preserves vanilla's exact error trace and continuation state while
leaving the entity fast-path counter at zero. A nested entity path (`data.nested`)
also stays on the native fallback, selects the nested value, and matches the
complete vanilla trace and state on both stacks. Probes across all ten runtime
modes now also verify a wrong-typed block-entity argument (`with block ... data`)
and an alternate entity custom-data path (`data.custom_args`). The block provider
preserves vanilla's exact error trace and continuation state with zero fast-path
hits, and the alternate entity path returns 9 with zero fast-path hits, matching
vanilla state and debug trace across all ten arms. Full report:
`build/reports/runtime-probe/results.json`.

The six-request reversed reload publication case now passes across the full
vanilla plus nine-mode runtime matrix, including the selective-macro candidate
and a forced whole-resource failure. The next correctness work is to probe
remaining provider/error branches and macro failure shapes beyond the staged
body and selective-argument cases, then record those results against
MACRO-006/007 and RELOAD-001/002. Seven-or-more-request races remain open.
Review the fast path's thread-safety and publication assumptions against the
resource-reload implementation. Keep
Bellows PERF-011 excluded until a datapack passes its native compiler-off gate
there. Keep fused and bytecode real-world gates open until a valid workload
with adjacent eligible commands exists.

Nine callback continuation cases now extend CTRL-007, CTRL-002, and SCORE-010:
six isolated-call cases and three nested `return run function` continuation
cases. In `execute if function`, a child side effect completes, the failed
result skips its branch and child tail, and the parent's fused continuation runs
once. In `execute unless function`, a failed child takes the branch while
discarding its child tail, then resumes the parent continuation once. In
`execute store success`, the failed child result stores 0, discards its pending
child tail, and resumes the parent's continuation once. In `execute store
result`, a child returns 7, the callback stores 7, its pending tail is
discarded, and the parent continuation runs once. A second child returns failure,
causing the result callback to store 0, discard its pending child tail, and resume
the parent tail once. The full vanilla plus nine-Fabric-mode comparison ends at
scores 31, 1032, 32, 32, 32, and 32 with identical five- and six-event traces;
fused and bytecode each execute one parent-tail region in each case. The
successful `execute store success` child returns 7 but records success value 1,
discards its pending child tail, and resumes the parent tail at score 32.
A nested `execute store result` wrapper using `return run function` to call a
child returning 7 stores result 7, discards pending child and wrapper tails, and
resumes the parent tail at score 37 with an exact eight-event trace; fused and
bytecode each execute one parent continuation region. Paired nested `execute
store success` cases test the same wrapper shape with child returns 7 and fail,
storing 1 and 0 respectively, discarding both pending tails, and resuming at
score 37 with matching eight-event traces and one continuation region per
optimized arm. Every arm now compares 88 `/debug function` traces. CTRL-007
remains partial because other frame-discard and callback combinations are still
untested.

The raw PERF-011 campaign reports and profiles are retained under the ignored
`build/benchmarks/PERF-011-veinminer/` directory. The tracked summary is in the
[profile evidence report](real-world-profile-targets.md#selective-macro-prototype-and-randomized-perf-011-comparison).
