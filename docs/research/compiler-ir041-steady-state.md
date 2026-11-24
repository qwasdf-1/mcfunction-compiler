# IR-041 — Steady-state CPU qualification and mixed-workload pilot

**Status: protocol implemented; native performance qualification pending.** No production compiler behavior is enabled by default. This is a bounded measurement milestone on `work/compiler-coverage`, not an additional optimization pass.

## Motivation and frozen prior evidence

IR040 accepted native semantic parity, but its 28.39% maximum absolute A/A placebo exceeded the 5% preregistered gate. The complete [IR040 evidence archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45464991546/artifacts/14955306595) was inspected; no windows are excluded or retrospectively promoted. Median ns/top-level source line in first versus second halves of each arm's chronological windows:

| Arm | Boot 0 early | Boot 0 late | Boot 1 early | Boot 1 late |
| --- | ---: | ---: | ---: | ---: |
| Native | 896.0 | 432.9 | 652.0 | 516.4 |
| IR039-style | 185.8 | 129.9 | 187.5 | 128.9 |
| IR040 | 188.7 | 99.3 | 123.9 | 142.3 |

This confirms time-varying costs, not a causal diagnosis of JIT warmup. IR041 archives JVM-wide CPU, surviving JIT/GC thread CPU, scheduling wait and cgroup telemetry alongside Server-thread CPU. Those are observational only; never subtract or omit windows using them.

## Workloads and scope

Same JVM, identical source twins, original initial-function-call scheduling, direct scheduling off. Keep IR040 arithmetic extension off in all arms to isolate predicate dataflow and avoid a second treatment. Native twin uses an excluded namespace; base twin uses the IR039 plan, flow twin enables dataflow. Separate diagnostic preflight verifies actual typed layout, native exclusion, IR040-only proof counters, and exact state. Both timed boots disable diagnostics, callback-test observer and compile timing.

- Compound: original IR040 64-command four-pattern stress workload. Exactly 48 increments per call.
- Mixed: 64 top-level commands, eight changing-score groups, compound ranges/comparisons with pass/fail variation, arithmetic, native execute-store or shared native child calls, isolated native guards. Four nested native commands per call. Exactly x += 92 per call, final g=8, y=9, result=72, observed=72. Top-level denominators count 64 source visits; nested visits recorded separately. Expected compiler layout: 48/64 top-level typed, 16 opaque/singleton. Not a publisher datapack or representative performance estimate.

A separate static census reuses the pinned original Vein Miner and Blastback archives and the existing source region segmentation. It screens current literal score/compound shapes, recognizes arithmetic eligibility, reports candidates within tick-reachable functions and opaque roots. This is NOT parsed coverage, actual hotness, or publisher workload speed. A full publisher event is deferred until a stable synthetic protocol exists; do not claim actual datapack speedup from the mixed fixture or the census.

## Separate compilation measurement

During the diagnostic boot only, a four-exact-ID probe records post-parse TypedScoreIR.compile wall and current-thread CPU time per function, including lowering, optimizer, and bytecode emission. It excludes vanilla parsing, initial ScoreAddPrototype validation, resource loading and JVM startup. Single cold-build observations are descriptive only; parallel loading and JIT can distort wall/CPU costs. No full load-time speedup or break-even claim. Timed JVMs never call the compile probe.

## Fixed protocol

- Two independent timed Minecraft JVMs. Reverse workload order in second boot; rotate arm order in warmup.
- Freeze game simulation; RCON, command scheduler and incidental server work remain. Confirm freeze and exact score state.
- 128 calls/batch, 64 batches/window = 524,288 top-level source visits (16x IR040); mixed includes 32,768 nested visits. Minimum 20 ms running CPU per eligible window. Timing uses external Linux /proc Server-thread schedstat; reset and snapshot outside clocks.
- Minimum six, maximum sixteen warmup rounds per workload per boot, all three arms in each round. Last four consecutive windows of EACH arm must have (max-min)/median <=5% and each >=20ms CPU. Warmup samples kept; do not time treatments until qualified.
- After warmup, run separate ABBA or BAAB placebo block for each of native/native, base/base, flow/flow. All must be within 5%. If either gate fails, skip that boot/workload's treatments, retain evidence.
- Two counterbalanced treatment cycles ABBA and BAAB (reverse order in second boot) interleave same-arm controls around native-vs-flow and base-vs-flow. Both boot/workload gates, every final A/A <=5%, all four paired treatment reductions positive, both boot medians >= max(5%, twice max A/A), all windows >=20 ms. Otherwise no accepted speedup. No stopping when treatment happens to look good.
- No more than two timed boots, one diagnostic boot; no automatic repeat. No general datapack claim even if qualified.

## Results

Pending.
