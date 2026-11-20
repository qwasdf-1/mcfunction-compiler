# COMPILER-IR-021 — Native fork-stage cost decomposition and deferred scheduling

**Status (2026-11-20):** **ACCEPTED original Minecraft 26.3 exact-method inspection, first original Blastback native three-JVM PLAIN/EMPTY/TIMED CPU matrix, and all default-off IR-016–019 native semantic regressions.** A separately booted three-JVM CPU replication is under way. No compiled selector, new scheduling implementation, causal speedup, complete restoration or production promotion. Work stays on work/compiler-coverage / draft unmerged PR #10.

## Motivating question

IR-020 observed the original SHA-pinned Blastback one-TNT restore workload: the same multi-stage original command in erb:restore/job_tick (source index 4) triggered approximately 1,240 BuildContexts source entries and 320,000 per-entity native terminal commands over a 30-second original event. Separate three-JVM CPU-clock studies projected approximately **5.631%** and **5.649%** inclusive Server-thread CPU at BuildContexts.execute for the exact original command. Those figures include essential Minecraft work, not a demonstrated removable compiler overhead or causal speedup.

The original untouched Blastback Hotfix 3 ZIP is pinned by SHA-256:

    8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90

Its exact original indexed command is:

    execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1

This command is **not** a simple score-guard static-function dispatch. It selects entity sources, applies a per-entity scoreboard comparison, and mutates real scoreboard state only where appropriate. The native fork order, quota, callbacks, feedback, source object, error/fallback and frame behavior must remain unchanged. IR-021 is an attribution study; no compiled opcode, custom selector, task removal or cache is implemented.

## Actual bytecode-bound scheduling and attribution

[Exact Loom-mapped Minecraft 26.3 and Brigadier original method inventory #44836564029](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44836564029) ([method-disassembly artifact #14678836444](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44836564029/artifacts/14678836444)) verifies:

- BuildContexts.execute calls ContextChain.runModifier for each source in the active redirect stage. It accumulates the Collection results, enforces the original fork limit, advances through further modifier stages, and finally hands the resulting sources to ContinuationTask.schedule.
- ContextChain.runModifier delegates the original parsed redirect to Brigadier after copying the original CommandContext for its current source. For this command the execute-as redirect invokes EntitySelector.findEntities, followed by CommandSourceStack.withEntity for each returned entity. The separate execute-if-score stage may apply its own conditions and can remove candidates.
- EntitySelector.findEntities contains permissions, target selection, predicate filtering and final sort-and-limit. CommandSourceStack.withEntity retains the original source fields and creates a new source only if the entity reference changes.
- The original ContinuationTask.schedule is NOT equivalent to immediately queueing N child commands. For 0, 1 and 2 sources it follows direct branches; for greater than two it creates one ContinuationTask with a retained source list, enqueues its initial entry, then that SAME ContinuationTask.execute queues the per-entity original command and normally its next continuation on each subsequent task. Most per-entity queue work therefore happens **outside** the original BuildContexts.execute method.

The initial method-inspection attempt failed because it asked javap to find Brigadier ContextChain inside Minecraft's JAR; ContextChain belongs to the separate pinned Brigadier dependency. The corrected inspection accesses both original dependency JARs. This is an inspection tool configuration correction, not a native execution result.

## New passive boundaries

All hooks are added to the already research-only branch, and are disabled unless BOTH FC_CPU021_NAMESPACE=erb and FC_CPU021_MODE=plain|empty|timed are present at process start AND an explicit functioncompiler cpu021-start command arms the bounded event window. The original source command text is matched exactly; the native benchmark also SHA-verifies the publisher ZIP and asserts the literal original source at index 4.

| Bounded observer stream | Native synchronous invocation | Sampling stride | Nesting / interpretive scope |
| --- | --- | ---: | --- |
| exact_build_contexts | Existing original BuildContexts.execute | 1/16 | Inclusive reference from IR-020; contains all original stages and initial schedule |
| modifier_execute_as | Brigadier ContextChain.runModifier for as stage | 1/16 | Native selector scan and per-entity source mappings are nested |
| modifier_score_predicate | ContextChain.runModifier for if score stage | 1/128 | Repeated per source; includes genuine comparisons and CommandContext.copyFor |
| modifier_other | Any unrecognized modifier stage | 1/16 | Logged without silently assigning its work to selector or score |
| entity_selector_find | Original EntitySelector.findEntities during exact execute-as stage | 1/16 | Nested inside modifier_execute_as |
| source_with_entity | Original CommandSourceStack.withEntity during execute-as | 1/128 | Nested inside modifier_execute_as, one per mapped source |
| continuation_initial_schedule | Original ContinuationTask.schedule from the exact active BuildContexts | 1/16 | Nested inside exact_build_contexts; counts original source list cardinality |
| continuation_deferred_step | Actual later ContinuationTask.execute on an instance marked only when CONSTRUCTED during this exact schedule | 1/128 | Occurs outside BuildContexts; includes native queueNext work but excludes later terminal command body |

The constructor-only attribution flag is set on original native continuations when created inside the exact matched active BuildContexts schedule; it does **not** change arguments, list contents, queue insertion, command source, frame or task execution. Later native task entries may stop being timed at the explicit window boundary; per-arm visit/result counts are reported without claiming completed restore correctness.

Each stream records visits, exact sampled CPU-clock intervals, invalid readings, original result/source cardinality and maximum single result. PLAIN counts without reading the CPU clock. EMPTY samples two adjacent Java ThreadMXBean current-thread CPU reads on frozen ordinals and delegates to the original method. TIMED samples the identical native method inclusive time on the same ordinals. Linux /proc Server-thread schedstat is an independent whole-event running-CPU denominator, with host delay and cgroup throttling recorded. An instrumented Java callback is not proof that the scoreboard value actually changed.

The timing streams are deliberately overlapping. For example, selector_find and source_with_entity are nested within modifier_execute_as, itself nested in exact_build_contexts; initial schedule is also nested there. NEVER SUM those percentages as disjoint CPU. Deferred continuation steps instead happen later, outside the BuildContexts interval. A signed TIMED-minus-EMPTY clock-corrected inclusive projection is a **descriptive** sample-based method cost, not a precise exclusive cost, removable-work budget, CPU speedup, or causal control experiment.

## Native validation and admission

The three independent original Java25/Minecraft26.3 Fabric JVMs execute the exact original one-TNT, tagged in-world actor with unchanged witness-block palette, bounded pre-event source/template clone checks and the same 30-second Blastback capture/restoration window as IR-020. No original publisher content is rewritten. No controlled successful complete restoration is assumed.

The parser requires all eight row definitions; no missing or negative/invalid clock intervals; exact floor(visits/stride) sample counts; meaningful source, selector, mapping, condition, scheduling and delayed continuation activity; and exposure counts that differ by no more than 1.5 times across original PLAIN/EMPTY/TIMED boots. A truly absent other-modifier stage must be reported as unobserved, not silently treated as CPU=0 with a fabricated correction. Events that do not satisfy prerequisites are invalid, not successful benchmarks. Score predicate cardinality is measured separately from total entity selection, and schedule source count separately from native later continuation executions; incomplete end-of-window children are not imputed.

Post-instrumentation regressions repeat IR-016, IR-017, IR-018 and IR-019 accepted original vanilla scoreboard, queue, quota, @s source, callback and function dispatch comparisons with CPU021 default-off. This is bounded semantic regression evidence, not proof that installed-but-disabled Mixins have zero production overhead. Workflows remain draft-branch research only.

## First complete original three-JVM CPU attribution — accepted

[Accepted first native three-arm workflow #44837775475](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837775475) · [exact per-source native stage counts, original-world witness checks and raw time samples #14679258637](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837775475/artifacts/14679258637).

The first attempt passed its initial PLAIN native event, including exact selector and continuation cardinalities, but the next EMPTY arm failed a tagged-TNT presence check before a usable CPU comparison. That attempt is invalid. The corrected source runner now **summons and confirms exactly one native TNT actor with bounded, recorded pre-event RCON probes, BEFORE starting the clock window**. The accepted run passed all three original 30-second event arms with no invalid or missing clock intervals, exact publisher ZIP/source-index check, forced source/template witness state and Linux Server-thread quality checks.

| Observed original native quantity | PLAIN | EMPTY | TIMED |
| --- | ---: | ---: | ---: |
| Minecraft ticks in bounded window | 600 | 600 | 601 |
| Source BuildContexts and execute-as calls | 1,239 | 1,372 | 1,246 |
| EntitySelector.findEntities calls | 1,239 | 1,372 | 1,246 |
| Native selected entity sources, withEntity calls and if-score predicate visits | 320,704 | 317,720 | 320,473 |
| Source entries passed to initial ContinuationTask.schedule | 320,704 | 317,720 | 320,473 |
| Actually reached later ContinuationTask.execute entries | 320,702 | 317,588 | 320,471 |
| Linux Server-thread running CPU | 5.372 s | 5.596 s | 5.289 s |

Exactly the original selector results, entity-bound source-mapping calls, score-predicate calls, and initial scheduled source cardinalities agree within each accepted original arm. The difference in the later continuation counts is expected from work possibly outstanding at a bounded observation edge, not a claim about dropped tasks. The EMPTY arm's source scan count is higher despite comparable selected source totals; no equal-work randomized CPU comparison is implied.

| Measured inclusive native method stage | EMPTY clock mean | TIMED method mean | Signed TIMED minus EMPTY ns per call | Descriptive fraction of TIMED Server-thread CPU |
| --- | ---: | ---: | ---: | ---: |
| Exact BuildContexts stage (overlaps modifiers and initial scheduling) | 1,047.54 ns | 214,918.83 ns | 213,871.29 ns | **5.038%** |
| Brigadier execute-as modifier, includes selector and source mappings | 530.06 ns | 141,385.16 ns | 140,855.10 ns | **3.318%** |
| EntitySelector.findEntities (nested in execute-as) | 524.81 ns | 127,045.00 ns | 126,520.19 ns | **2.981%** |
| Native CommandSourceStack.withEntity (nested in execute-as) | 740.71 ns | 876.53 ns | 135.83 ns | **0.823%** |
| Brigadier per-source score modifier (inside BuildContexts) | 657.86 ns | 994.61 ns | 336.75 ns | **2.040%** |
| One-time ContinuationTask.schedule | 744.11 ns | 729.27 ns | **−14.83 ns** | **−0.00035%** |
| Deferred per-source ContinuationTask.execute, outside BuildContexts | 662.94 ns | 728.26 ns | 65.33 ns | **0.396%** |

The independent source + modifier stage and selector times are sampled on different deterministic ordinals and are not an algebraic exclusive decomposition. Selector.findEntities is the **largest clearly resolvable nested original substage of execute-as** in the first result. It performs necessary entity enumeration, type/tag predicates, world lookups, sorting/limit and permission checks; its entire projected ~2.98% is NOT an avoidable compiler budget.

The measured source mapping and per-entity deferred continuation corrections (136 ns and 65 ns) are much smaller than their corresponding EMPTY clock means (~741 ns and ~663 ns). Individual values at that scale are near/below the clock's observational floor and cannot justify a claimed CPU saving. The initial continuation scheduling has a slightly **negative signed correction**; the analyst intentionally preserves this result rather than clamping to zero or misreporting it as a scheduler optimization. Deferred continuation steps execute in a different queue phase from BuildContexts and should never be added to the BuildContexts percentages as though they were a simple independent speedup budget.

The 2.04% measured score modifier includes genuine per-entity condition checks, CommandContext.copyFor and redirect evaluation, not just an avoidable Brigadier callback. This original one-TNT event happens to show matching source and resulting context totals for this stage, but that does NOT prove predicate result equivalence for other worlds, or that the score predicate can be skipped in a compiler.

## Post-observer Minecraft semantic equivalence — accepted

[Post-default-off IR-021 native regression #44837526785](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837526785) passed all four prior 26.3/Java25 differential suites with native fork-observer Mixins installed: IR-016 mixed-function frames/quotas **126/126** complete vanilla states per arm; IR-017 range/guard/binary score arithmetic **168/168**; IR-018 @s entity binding and opaque function dispatch barriers **87/87**; IR-019 original native conditional function dispatch **84/84**. These runs verified native scoreboard, command quota, frame, callback and fallback state on the tested original paths with CPU021 disabled. They do not prove zero disabled-hook CPU overhead.

[IR-016 regression artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837526785/artifacts/14678758205) · [IR-017 artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837526785/artifacts/14679751209) · [IR-018 artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837526785/artifacts/14678309203) · [IR-019 artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44837526785/artifacts/14678652961).

## Open gate and decision rule

**The first three-arm descriptive method-cost attribution and native regression matrix passed.** An independent original three-arm repetition is being checked before treating the stage shares as stable. The next compiler optimization must have an exact semantics-preserving replacement with a separately measured avoidable part. Selector scans, per-entity CommandSourceStack state, score predicates and native queued command actions all do necessary work, even if they are expensive. In particular, the previous IR-020 inclusive ~5.6% BuildContexts estimate is **not** an upper bound on achievable speedup.

If an independently repeatable CPU component can be isolated and a candidate optimization is implemented in a later milestone, require full fork order and count, selector permissions and tag/score filters, source identity and lifecycle, partial quota cuts, callback/error and return behavior, reentrant queue inserts and player/gameplay state parity, and an uninstrumented placebo-controlled real-workload CPU test. Do not merge research-only Mixins until their disabled overhead is independently assessed.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir021_cpu.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir021_cpu.py

Initial reported CPU numbers are directly from accepted original native run #44837775475, not inferred from static source. Finish independent repetition before the final closeout decision.
