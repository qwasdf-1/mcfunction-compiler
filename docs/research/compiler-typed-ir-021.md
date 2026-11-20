# COMPILER-IR-021 — Native fork-stage cost decomposition and deferred scheduling

**Status (2026-11-20):** Exact native Minecraft 26.3 method-inspection gate passed. Research-only instrumentation compiles and is under native PLAIN/EMPTY/TIMED and post-observer IR-016–019 semantic validation. **Do not infer a CPU attribution or optimization until both native gates accept.** Same branch work/compiler-coverage, draft unmerged PR #10; no production setting changed.

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

## Open gate and decision rule

**CPU attribution is accepted only when the three native clock arms and regression matrix pass.** The next compiler optimization must have an exact semantics-preserving replacement with a separately measured avoidable part. Selector scans, per-entity CommandSourceStack state, score predicates and native queued command actions all do necessary work, even if they are expensive. In particular, the previous IR-020 inclusive ~5.6% BuildContexts estimate is **not** an upper bound on achievable speedup.

If an independently repeatable CPU component can be isolated and a candidate optimization is implemented in a later milestone, require full fork order and count, selector permissions and tag/score filters, source identity and lifecycle, partial quota cuts, callback/error and return behavior, reentrant queue inserts and player/gameplay state parity, and an uninstrumented placebo-controlled real-workload CPU test. Do not merge research-only Mixins until their disabled overhead is independently assessed.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir021_cpu.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir021_cpu.py

Data and final conclusions must be recorded from the accepted run, not inferred from static method shapes or earlier IR-020 ratios.
