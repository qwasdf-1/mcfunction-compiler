# COMPILER-QUEUE/CPU-005 — source-verified macro predicates and append-state CPU

**Status:** Source trace and dynamic census accepted; **five-stream CPU diagnostic preregistered and awaiting native validation**. Existing `work/compiler-coverage` / draft PR #10. Not a compiler optimization or a speedup study. New `BuildContexts` and `ExecuteCommand` hooks are **research-only Mixins; do not merge into production without separately proving disabled-hook overhead**.

## Source and dynamic exposure (independently verified)

The pinned, original Vein Miner 5.3.0+26.3 publisher ZIP SHA-256 is `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. The read-only [source inspection workflow #44453566255](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44453566255) passed the SHA pin and traversed the complete three-function, seven-command graph:

```mcfunction
# vm:queue/enqueue_here:
function vm:queue/enqueue_match with entity @s data

# vm:queue/enqueue_match:
$execute unless block ~ ~ ~ #vm:excluded_blocks if block ~ ~ ~ #$(match) run function vm:queue/append_here

# vm:queue/append_here:
tp @s ~ ~ ~
data modify entity @s data.frontier append value {x:0,y:0,z:0}
execute store result entity @s data.frontier[-1].x int 1 run data get entity @s Pos[0]
execute store result entity @s data.frontier[-1].y int 1 run data get entity @s Pos[1]
execute store result entity @s data.frontier[-1].z int 1 run data get entity @s Pos[2]
```

An independent, pinned [dynamic native run #44454058436](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44454058436) passed the game-state and namespace conservation gates, and observed:

| Function | Reached original command entries | Ordinary Brigadier callbacks |
| --- | ---: | ---: |
| `vm:queue/enqueue_faces` | 1,296 | 0 (custom executor) |
| `vm:queue/enqueue_diagonals` | 4,320 | 0 (custom executor) |
| `vm:queue/enqueue_here` | **5,616** | 0 (custom executor) |
| `vm:queue/enqueue_match` | **5,616** | 0 (custom executor) |
| `vm:queue/append_here` | **9,700** (5 × 1,940) | **9,700** |

**1,940 of the 5,616** macro predicate entries led to the five-step append body. The original [compiler-acceptance archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44379699409) recorded **one** newly instantiated `enqueue_match` macro and **5,615** parameter-cache hits. Repeated macro *reparsing* is not the plausible bottleneck here; repeated predicate evaluation and actual entity NBT update are the open CPU questions. Source counts and callback-entry counts do not establish success/result parity or removable work.

## Frozen target-specific CPU method-clock screen

A three-arm native PLAIN / EMPTY / TIMED diagnostic uses independent Java 25/Fabric Minecraft 26.3 servers with compiler mode `wrapper` and no ScoreAdd/fusion, Spark, JFR or other command metrics. Explicit environment opt-in `FC_CPU005_NAMESPACE=vm` plus `FC_CPU005_MODE=plain|empty|timed` is required, and the RCON start/stop hooks enable clocks **only around the real survival-player 6×6×6 mining event**. The existing runner, ore state and host-quality gates remain unchanged.

The CPU observer counts and sparsely samples the following synchronous methods with 1/16 deterministic selection, alongside an independent Linux /proc Server-thread running-CPU denominator:

| Probe stream | Exact native method boundary | Frozen call count |
| --- | --- | ---: |
| `enqueue_macro_predicate_build` | `BuildContexts.execute` for the instantiated `execute unless block … if block … run function vm:queue/append_here` | **5,616** |
| `append_tp_execute` | `ExecuteCommand.execute` for exact `tp @s ~ ~ ~` | **1,940** |
| `append_frontier_execute` | `ExecuteCommand.execute` for exact `data modify entity @s data.frontier append ...` | **1,940** |
| `append_coordinate_store_execute` | `ExecuteCommand.execute` for all three exact `execute store result entity @s data.frontier[-1].{x,y,z} ...` sites | **5,820** |
| `append_data_get_leaf` | Nested ordinary `Command.run` for each of those three `data get entity @s Pos[*]` terminal callbacks | **5,820** |

The final stream is **nested inside** the coordinate-store span. Its time is not disjoint from `append_coordinate_store_execute`. Every `ExecuteCommand` span includes ordinary command execution, callback/result processing, and **meaningful world/NBT mutations**. A `BuildContexts` predicate span includes actual block tests and conditional child-function setup. None of these is proven removable compiler overhead. Cross-stream percentages are **not added**.

The protocol does not attempt to instrument arbitrary commands: each `ExecuteCommand` input is matched to a uniquely appearing command line in the SHA-pinned archive (the CI verifies all five unique sites); the predicate is matched by a highly constrained source shape and fixed child target. The probe is explicitly disabled in ordinary server processes. Its Mixin classes nonetheless add method hooks, so installed-but-disabled performance must be independently certified before any production merge.

### Validity, timing and stopping gates

- **Source and native parity:** Original publisher ZIP checksum, exact unique input commands, 215 ore units, 1,952 queue-head increments, `vmr.run=0`, no remaining ore, exact final state parity, original world and mining action.
- **Host and clock:** Same 9-second idle baseline gate, 45-second *pre-mining* setup timeout, fixed 150-second event observation, valid Linux Server-thread running CPU and host-quality checks, no post-mining retries or dropped observations.
- **Clock control:** PLAIN counts only, EMPTY performs two adjacent `ThreadMXBean.getCurrentThreadCpuTime` calls at every 16th invocation before delegating, TIMED brackets the original method on the same ordinal. Enforce exactly `floor(N/16)` valid samples for every active stream, zero invalid intervals, at least 64 samples per stream, and the frozen counts on all three boots.
- **Analysis:** Signed CPU per call is TIMED mean minus EMPTY mean. The descriptive event-CPU fraction multiplies that correction by the observed call count and divides by the TIMED /proc Server-thread CPU. Report negative or sub-clock-floor results without clamping. The three independent boots do **not** constitute a causal paired comparison or a confidence interval.

**Decision:** If predicate setup takes a measurable nontrivial fraction of native CPU, isolate exactly what a compiler transformation could remove while preserving both block checks, return/fork/result, macro cache and context identity. If most CPU is in real frontier append and coordinate-result writes, **do not** treat it as an optimizer budget; stateful NBT mutation is necessary and belongs to the Minecraft command semantics. No optimizer or further broad scheduler profiler is warranted without a distinct compiler-owned semantic transformation and a future uninstrumented paired native experiment.
