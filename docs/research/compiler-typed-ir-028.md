# COMPILER-IR-028 — Uninstrumented completed-event CPU A/A–A/B pilot

**2026-11-21: ACCEPTED as an exploratory, uninstrumented CPU pilot; NO measurable
compiler speedup established.** The unchanged SHA-pinned Blastback Hotfix 3
publisher was run on the IR027 controlled full-stone 17×17×17 fixture. Four
fresh Java 25 / Minecraft 26.3 server JVMs ran a preregistered A–B–B–A
sequence. A is typed-IR plan-only; B differs only by enabling the actual
IR025 compiled fork. The complete TNT capture-and-restore event was included
in the Linux Minecraft Server-thread CPU window.

Branch: `work/compiler-coverage`. Draft/unmerged PR #10. The default compiler
and gameplay behavior remain unchanged.

## 1. Question and treatment

IR027 had already established two independently replicated native / plan-only /
compiled complete-restoration comparisons on the same controlled fixture.
IR028 asked whether enabling the generated original-selector fork reduces
whole-event Server-thread CPU compared with leaving the exact same source
position on the plan-only native path.

| Arm | Typed scoreboard IR | Native fork plan | Compiled fork | Runtime diagnostics |
| --- | --- | --- | --- | --- |
| A: plan-only | bytecode | enabled | **false** | off |
| B: compiled | bytecode | enabled | **true** | off |

Both arms retained the same exact function filter, reentrant queue-epoch
semantics, neighboring typed regions, original selector, original publisher,
and disabled score cache / entity index / unrelated probes. The only treatment
switch was `FC_TYPED_IR_COMPILED_FORK`.

The pre-registered order was **A1, B1, B2, A2**. Each arm used a fresh JVM and
one original tagged TNT actor. Linux `/proc/<pid>/task/<tid>/schedstat`
measured the actual Minecraft Server thread from before TNT spawn through 600
Blastback datapack ticks. This includes early capture and restoration work.
The run stopped the CPU clock before the full post-event diagnostic snapshot.
Compiler counters, tracing, ScoreAdd metrics and in-process timing probes were
disabled throughout the measured interval.

## 2. Accepted run

[GitHub Actions IR028 run #44946957785](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44946957785)
completed successfully. The evidence archive is
[artifact 14723988572](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44946957785/artifacts/14723988572).

| Run | Treatment | Event ticks | Capture markers sampled | Server-thread CPU | CPU per datapack tick |
| --- | --- | ---: | ---: | ---: | ---: |
| A1 | Plan-only | 603 | 5,769 | 12.891 s | 21.379 ms |
| B1 | Compiled | 600 | 5,769 | 12.779 s | 21.299 ms |
| B2 | Compiled | 603 | 5,769 | 12.300 s | 20.398 ms |
| A2 | Plan-only | 604 | 5,769 | 12.307 s | 20.376 ms |

Every run independently passed the event-completion gate:

- The original TNT actor was spawned and disappeared.
- The same 5,769 original `erb.block` markers were observed by the bounded
  capture witness.
- The complete 17³ source volume matched its pre-event reference after the
  CPU window.
- All saved block and restore-job markers were cleared.
- Host-quality checks passed in all four runs; cgroup throttling was zero.
- Server-thread runqueue-wait fractions were approximately 0.07–0.13%.

## 3. CPU comparison

| Metric | Result |
| --- | ---: |
| A plan-only median | **20.877 ms/tick** |
| B compiled median | **20.849 ms/tick** |
| Observed B-vs-A CPU reduction | **0.137%** |
| A1-to-A2 relative spread | **4.804%** |
| Preregistered A/A rejection threshold | 8.000% |
| Host-quality passes | 4/4 |
| Cgroup throttle increments | 0 |

The adjacent paired directions do not agree:

- B1 is 0.372% lower CPU/tick than A1.
- B2 is 0.109% **higher** CPU/tick than A2.

The small median difference is far below the observed A/A spread and changes
direction between the two adjacent pairs. The A/A gate passing means the
pilot was not rejected for severe host contention; it does **not** mean that
a 0.137% effect is resolved or statistically distinguishable from noise.

**Conclusion:** this pilot does not demonstrate a meaningful CPU improvement
from the compiled fork. The result is accepted as a valid scoped negative /
inconclusive performance finding, not as proof that the compiler is slower or
that every workload has exactly zero benefit.

## 4. What the current implementation actually removes

Inspection of the current source explains why the whole-event effect may be
small.

- `CompilerForkBytecode025` emits a hidden JVM action class, but that
  generated `execute` method delegates to the static Java helper
  `CompilerForkExecutor025.run`. It is a generated dispatch wrapper, not a
  per-entity loop emitted directly into the generated class. Whether HotSpot
  inlines the helper in this workload has not been established.
- The helper still calls the original
  `EntitySelector.findEntities`, maps every selected entity through
  `CommandSourceStack.withEntity`, constructs a candidate list, performs the
  per-entity score comparison, constructs a second passing list, and delegates
  terminal execution and continuation scheduling to the original
  `ExecuteCommand` / `ContinuationTask`.
- The path replaces the original generic Brigadier redirect/context-copy
  processing for this allowlisted shape. It does **not** replace the native
  entity scan, eliminate per-candidate source objects, compile the terminal
  command, or replace Minecraft's continuation policy.

IR021's earlier instrumented native attribution had found roughly 2.9%
inclusive Server-thread CPU in the native selector, 0.5–0.8% in nested
`withEntity` mapping, 2.0–2.7% in the score-predicate modifier, and about 5%
in the inclusive BuildContexts stage. Those are overlapping, instrumented
sample projections, not disjoint removable-work budgets. They make it
plausible that much of the original path's cost is work the compiled fork
intentionally retains. They cannot be subtracted from the IR028 whole-event
measurement to manufacture a predicted speedup.

## 5. Next investigation: profile before rewriting

Do **not** respond to this result by immediately adding a global selector
index, tag cache, or new scheduler. IR023 already demonstrated that the
previous partial entity-tag mutation hooks cannot safely maintain a global
membership cache.

The next useful experiment is a separate **JFR stack-attribution study** on
the same original publisher and controlled event, with plan-only and compiled
arms. It should establish whether the compiled path actually shifts sampled
Server-thread stacks away from `BuildContexts` / Brigadier
`ContextChain.runModifier`, and how much sampled time remains in
`EntitySelector.findEntities`, `CommandSourceStack.withEntity`,
`Scoreboard.getPlayerScoreInfo`, and native continuation scheduling.

JFR sampling is profiling, not an uninstrumented CPU comparison; it must not be
used to revise the IR028 CPU numbers. If the profile shows that the remaining
selector scan dominates and the removed Brigadier layer is small, the rational
decision may be to stop optimizing this fork rather than add more machinery.
If it identifies a material, semantics-preserving allocation or dispatch
target, isolate that target in its own differential milestone before another
CPU pilot.

**Disposition:** functional correctness remains accepted only within IR027's
controlled original-publisher event. IR028 shows no measurable whole-event
speedup. No production promotion, default enablement, or general performance
claim is authorized.
