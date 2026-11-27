# COMPILER-QUEUE/CPU-005 — source-verified macro predicates and append-state CPU

**Status:** **Accepted descriptive** pinned-source, real-gameplay CPU diagnostic (2026-11-18 EST / 2026-11-19 UTC). **Not** a causal optimization or speedup study. Existing `work/compiler-coverage` / draft PR #10. Not a compiler optimization or a speedup study. New `BuildContexts` and `ExecuteCommand` hooks are **research-only Mixins; do not merge into production without separately proving disabled-hook overhead**.

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

## Accepted CPU result — November 18, 2026 EST

The [three-arm original native workflow #44455179984](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44455179984) **passed** the Java/Fabric build, eight synthetic sample/overlap tests, official publisher ZIP pin, all five source text uniqueness gates, all three independent genuine 6×6×6 survival-player events, event-window start/stop controls, Linux Server-thread clock identity/quality and idle stability gates, and **exact 215 ore / 1,952 queue-head / no remaining ore, source or markers parity across all three boots**. No timed interval was invalid or dropped. The [original raw artifact #14497381820](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44455179984/artifacts/14497381820) contains the native JSON result, all five raw stream rows per arm, runner logs and pre-mining manifests; the Gradle dependency cache is outside the archive.

| Native method stream | Calls / all arms | EMPTY mean (ns) | TIMED mean (ns) | Signed corrected per call | Projected timed-event Server CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| Macro predicate `BuildContexts.execute` | 5,616 | 1,205.11 | 3,503.02 | **2.298 µs** | **12.91 ms / 0.0963%** |
| `tp @s ~ ~ ~` `ExecuteCommand.execute` | 1,940 | 1,125.01 | 20,333.76 | **19.209 µs** | **37.26 ms / 0.2781%** |
| Frontier `data modify` `ExecuteCommand.execute` | 1,940 | 385.88 | 351,466.92 | **351.081 µs** | **681.10 ms / 5.0822%** |
| Three coordinate-store `ExecuteCommand.execute` sites | 5,820 | 1,347.08 | 605,438.66 | **604.092 µs** | **3,515.81 ms / 26.2341%** |
| Nested `data get` ordinary `Command.run` | 5,820 | 344.59 | 257,157.26 | **256.813 µs** | **1,494.65 ms / 11.1527%** |

Actual active sample sizes: **351** for the predicate, **121** for teleport and frontier append each, **363** for coordinate stores and data-get callbacks each, independently in EMPTY and TIMED. Server-thread running CPU across the whole real event was **13.195 s PLAIN**, **13.011 s EMPTY**, **13.402 s TIMED**. Those different boot totals are **not** a treatment effect. The displayed percentages normalize the descriptive sparse-clock extrapolations to TIMED's 13,401,680,302 ns Server-thread CPU denominator.

### Cost interpretation and stopping decision

The **compiler-declined macro predicate is not a substantial synchronous CPU contributor** in this measured event: its inclusive `BuildContexts.execute` span projects to ~0.096% of Server-thread CPU, *before* allowing for necessary block checks and call scheduling. The separate previous CPU004 synchronous positioned-entry (~0.142%) and immediate `CallFunction` setup (~0.011%, below clock floor) were also small. Neither study measures every scheduling boundary, but their evidence does **not** support prioritizing a specialized positioned-child-call or macro predicate fast path merely to reduce compiler rejection counts.

By contrast, **actual stateful data work dominates these measured paths**. The coordinate stores alone are ~26.23% inclusive in the TIMED projection, of which the observed ordinary `data get` leaf work is ~11.15% **nested within the same calls**. Do **not** add them to 37.39% or subtract them and label the difference *exclusive avoidable Brigadier dispatch*. The residual includes necessary stateful result-consumer updates, exception/feedback and other execution plumbing; differences between separate calibrated interval estimates are not a precise exclusive measurement. The frontier NBT append's ~5.08% is also real mutable state. Replacing these with a compiler optimization would require preserving the exact NBT contents, entity source position, failure/return/result/callback semantics, and observable scheduling; these operations are not removable bookkeeping.

**Decision:** Do **not** implement a `vm:queue/enqueue_match` or `execute positioned … run function` compiler lowering on this evidence, and do not restart broad generic scheduler or NBT rewriting research. We have traced the original compiler rejection to a hot path, **but the measured CPU opportunity is predominantly meaningful Minecraft state manipulation, not demonstrated compiler-owned overhead**. The existing selective macro-argument optimization is already active and its `enqueue_match` parameter cache had one expansion plus 5,615 hits; do not duplicate it.

All projections remain **one sampled JVM per arm**, with deterministic 1/16 selection, no randomized causal paired analysis or confidence interval, and possible time-varying NBT-size/sampling bias. These are descriptive workload-specific costs, **not** exact true CPU fractions, theoretical upper bounds, or observed speedups. No feature has been promoted. Two new research-only Mixins were installed for observation; their *disabled-hook overhead* is not independently certified, so this draft branch must not be merged wholesale into production.

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
