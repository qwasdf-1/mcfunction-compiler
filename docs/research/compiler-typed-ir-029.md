# COMPILER-IR-029 — Original Blastback JFR stack attribution

**2026-11-21: ACCEPTED as descriptive JFR profiling evidence only.** The
unchanged SHA-pinned Blastback Hotfix 3 publisher ran in four fresh Java 25 /
Minecraft 26.3 servers on the IR027 controlled stone fixture. A–B–B–A used
plan-only and compiled-fork modes with diagnostics disabled. JFR
`jdk.ExecutionSample` stacks were filtered to the exact Linux Minecraft
Server-thread OS TID.

This is **not** an uninstrumented CPU comparison. JFR profiling adds overhead,
and the sampled original capture populations differed between arms. The
recordings support path attribution and hotspot identification, not a causal
performance effect. IR028's uninstrumented CPU pilot remains the authoritative
whole-event performance result: no meaningful speedup was established.

Branch: `work/compiler-coverage`. Draft/unmerged PR #10. All runtime flags
remain off by default.

## 1. Run and evidence

[IR029 JFR run #44956503873](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44956503873)
completed successfully. The retained raw profile archive is
[artifact 14728320847](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44956503873/artifacts/14728320847).

| Arm | Mode | Server-thread runnable samples | Actor-relative ticks | Capture marker population sampled | Full template restored |
| --- | --- | ---: | ---: | ---: | --- |
| A1 | Plan-only | 1,252 | 601 | 3,320 | Yes |
| B1 | Compiled | 1,140 | 603 | 5,769 | Yes |
| B2 | Compiled | 1,209 | 602 | 3,320 | Yes |
| A2 | Plan-only | 1,097 | 604 | 1,530 | Yes |

Every arm observed an original Blastback capture, the original TNT disappeared,
the complete 17³ template matched, and all block/restore-job markers were
cleared. The capture population samples are **not equal** (1,530–5,769), so
these four JFR arms are not a work-equalized A/B comparison. The profile
workflow now explicitly reports this equality gate for future manual runs.

The raw recordings were reprocessed with slash-to-dot normalization of JFR
class names. JFR JSON represents some class names as internal slash-separated
names and others as dotted binary names; the first emitted summary therefore
undercounted a few exact-class categories. The committed parser now normalizes
both forms and tests the distinction. The corrected analysis below is derived
from the retained `.jfr` files, not from the original undercounted summary.

## 2. Whole Server-thread stack presence

The following are inclusive fractions of runnable Server-thread samples. A
sample is counted for a category if that method/class appears anywhere in its
stack. Categories overlap and **must not be summed**.

| Stack category | Plan-only mean | Compiled mean |
| --- | ---: | ---: |
| Minecraft `BuildContexts` | 82.75% | 79.49% |
| Brigadier `ContextChain.runModifier` | 77.33% | 74.68% |
| Native `EntitySelector.findEntities` | 69.89% | 72.96% |
| `Scoreboard.getPlayerScoreInfo` | 3.74% | 2.68% |
| Selector-options predicate `EntitySelectorOptions.lambda$bootStrap$43` | 43.41% | 45.73% |
| `EntityType.tryCast` | 10.47% | 11.15% |
| `CommandSourceStack.withEntity` | 0.39% | 0.13% |
| Generated compiled-fork action frame | 0% | 3.74% |

These are not target-command-only percentages. `BuildContexts`,
`ContextChain` and `EntitySelector` are also used by other original
commands during the event. The compiled fork replaces only the fifth source
line (`C5:1`) in an 18-command function; other source lines and other
functions continue to use the normal command pipeline. The broad global
fractions cannot be interpreted as an exclusive cost decomposition or as a
treatment effect. Capture-population variation further prevents direct A/B
comparison.

The generated action frame is nevertheless direct profile evidence that the
compiled path executes: it appears in **41/1,140** B1 runnable samples and
**47/1,209** B2 samples (3.60% and 3.89%, respectively; mean 3.74%). It is
absent from both plan-only arms.

## 3. What the compiled action is spending samples on

Filtering B1/B2 samples to those whose stack contains the generated
`CompiledFork025$Generated` action gives a more target-specific view. These
counts are still sparse, inclusive stack-presence samples—not per-method CPU
times.

| Method present within generated-action samples | B1: 41 samples | B2: 47 samples |
| --- | ---: | ---: |
| Native `EntitySelector.findEntities` | 30 (73%) | 33 (70%) |
| Selector-options predicate lambda | 26 (63%) | 21 (45%) |
| `EntityType.tryCast` | 1 (2%) | 9 (19%) |
| `Scoreboard.getPlayerScoreInfo` | 6 (15%) | 11 (23%) |
| `ArrayList.add` | 2 (5%) | 2 (4%) |
| `ArrayList.grow` | 0 | 2 (4%) |
| `CommandSourceStack.withEntity` | 1 (2%) | 0 |
| `CompilerForkExecutor025.run` frame | 1 (2%) | 1 (2%) |

The dominant leaf stacks repeatedly show the original selector's per-entity
predicate path:

```text
HashMap.getNode
  -> HashMap.containsKey
  -> HashSet.contains
  -> EntitySelectorOptions.lambda$bootStrap$43
  -> Util.allOf predicate
  -> ServerLevel.getEntities
```

Other frequent leaves include `EntityType.tryCast` during native entity
storage filtering and `Scoreboard.getPlayerScoreInfo` during the original
job-score equality guard. The exact numeric suffix of a synthetic
`lambda$bootStrap$43` method is not a stable source-level identifier; the
observed path is a selector-options predicate using set membership, consistent
with the original selector's tag constraints.

**Interpretation:** the generated action's sampled work is largely inside
operations the compiler deliberately preserves: native entity selection,
selector predicate/type filtering, and scoreboard equality checks. The
generated action is present in only about 3.7% of all Server-thread samples in
this event. The generic dispatch/context machinery it replaces is a smaller
part of that already limited slice. This is consistent with IR028's
approximately **0.137%** whole-event CPU reduction, but it does not prove or
quantify that causal relationship.

The helper frame itself appears only once in each compiled profile while the
generated action frame appears much more often. This could reflect JIT
inlining or sampling resolution; the recordings do not establish whether
HotSpot inlined the helper.

## 4. Engineering decision

1. **Do not promote IR025.** The IR028 uninstrumented pilot did not demonstrate
   a meaningful whole-event CPU improvement. IR029 is not a replacement CPU
   benchmark and has non-equal capture samples.
2. **Do not add a global entity/tag index as a quick response.** The selector
   predicate is an obvious hotspot, but IR023 showed that direct mutable
   `Entity.entityTags()` access bypasses the partial mutation hooks previously
   considered for cache invalidation. A cache without a complete invalidation
   contract would be semantically unsafe.
3. **Do not rewrite the generated action into a more elaborate bytecode loop
   yet.** The profile shows that the retained selector and scoreboard work
   dominates the samples within the compiled action; the current helper's
   `ArrayList` operations are rarely sampled. A more elaborate loop may add
   complexity without moving the dominant cost.
4. **Keep the compiled fork as a research-only functional prototype.** If
   future work revisits this area, first establish a complete and independently
   testable selector-membership invalidation design, or target a workload
   where the compiler can remove a materially larger fraction of total work.

## 5. Relationship to prior milestones

- [IR027](compiler-typed-ir-027.md) establishes the controlled native
  completion oracle and two independent native/plan-only/compiled full-volume
  restoration comparisons.
- [IR028](compiler-typed-ir-028.md) is the uninstrumented A/A–A/B CPU pilot.
  Its 0.137% observed reduction is below the A/A variation and is not a
  demonstrated speedup.
- IR029 adds sampled stack attribution only. It does not upgrade the
  performance claim, broaden the semantic guarantee, or change production
  defaults.

**Disposition:** accepted as a scoped descriptive profile. IR025 remains
opt-in, experimental, default-off and unmerged; no production performance
promotion is authorized.
