# COMPILER-IR-019 — Native conditional-call census, hotness gate and dispatch feasibility

**Status (2026-11-20):** **Accepted research-only dispatch feasibility and measurement stage**: two SHA-pinned real-datapack source inventories; three native Minecraft JVMs for dispatch/observer parity; two independent authentic one-TNT Blastback capture-window observations; and 14 native IR-016/017/018 regression JVMs. **No compiled function-dispatch opcode, causal CPU/speedup result, validated full restoration, production promotion or PR merge.** Same branch work/compiler-coverage, draft PR #10.

## Why the optimizer is gated

IR-016's source-spanned MixedFunctionIR and IR-018's selector-bound direct scoreboard lowering are validated. The remaining large source-shape barrier is execute if/unless score ... run function ..., but replacing that action with a direct Java child call would change Minecraft queue order, nested frames, callbacks, command quota charges, trace, return run function behavior, entity contexts, and macro arguments. Even a single score predicate can guard a native child call that is itself an observable frame boundary. Treating every generated Blastback dispatch line as an optimization is particularly unsafe.

The prerequisite for a compiled dispatch opcode is **measured real-gameplay hotness and a control-flow cost model**, not the number of lexically matched source lines. IR-019 therefore first adds an opt-in, non-mutating call-task counter at Minecraft's native CallFunction boundary and a stricter source-screening classification. It does not patch scheduling or compile a new function-call instruction merely to pass synthetic tests.

## Exact original-publisher source inventory — accepted

[Accepted SHA-verified two-publisher IR-019 inventory #44829662188](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44829662188) · [per-function source inventory #14675737603](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44829662188/artifacts/14675737603).

The exact unchanged Vein Miner 5.3.0+26.3 ZIP (SHA-256 fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e) and Blastback Hotfix 3 ZIP (SHA-256 8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90) were inspected with the existing source Pack parser and a new conservative two-way dispatch classifier.

| Original code line classification | Vein Miner | Blastback |
| --- | ---: | ---: |
| All conditional score → function source lines | 21 | 132,982 |
| **Exact single score-range guard → static named child** | **4** | **12,761** |
| Chained predicates, altered context, return-run, tags or other complex dispatch | **17** | **120,221** |
| Exact single-guard calls in tick/schedule reachability approximation | 2 | 11,803 |
| Distinct exact single-guard child function targets | 4 | 12,751 |

The exact family requires one fake holder or @s, one literal scoreboard objective, one inclusive integer range, one if/unless predicate, and a statically named function ID. Every other form is classified complex; a complex source is NOT eligible for proposed first-pass lowering. All such function calls remain native. This screen does not validate Brigadier callback structure, macro resolution or runtime reachability.

Concrete single-guard source witnesses: vm:detection/evaluate_target → vm:detection/verify_mined_stat; vm:queue/enqueue_neighbors → vm:queue/enqueue_diagonals; erb:capture/prepare → erb:group/add_segment; erb:capture/check_captured_position → erb:capture/requeue_moved; erb:runtime_tick; and several generated erb:watch/scan/root_* dispatchers. Concrete unsafe complex witnesses: Vein Miner player-context execute-as chains and return-run function; Blastback multi-condition and entity-existence guards with return-run frame propagation. Do not infer hotness from Blastback's thousands of generated root names.

## New transparent native observation boundary

CompilerExecutionCensus already recorded allowlisted original source-entry reaches and ordinary Brigadier callbacks. IR-019 extends it without modifying command execution or scheduling:

- Explicit environment gate FC_COMPILER_EXEC_CENSUS=true, existing namespace and comma-separated function allowlist. Newly optional FC_COMPILER_EXEC_CENSUS_CALLEES limits native child ID observations to a maximum of **96 explicitly named IDs**, validated before enabling. There is no unrestricted global callee census.
- Each allowlisted source entry is labeled single_score_static_call, complex_or_return_call, or none. Entry counts measure **original UnboundEntryAction.execute reached**, not success of the score condition.
- A passive CallFunctionMixin HEAD observer calls CompilerExecutionCensus.recordNativeCall(function.id()) before native CallFunction.execute. The observer counts exact **native call TASKS reached** for independently allowlisted child IDs during the same bounded event window, not successful child completion or the identity of a caller site. A child may have multiple callers; independent per-child counts must NEVER be blindly attributed to a specific guard.
- Existing functioncompiler exec-census-start/exec-census-stop gates control counts. At stop, FC_EXEC_ROW logs report source type and entry reaches, FC_EXEC_CALLEE logs the native target call-task counts, and FC_EXEC_END summarizes the two source categories plus native call totals. No child frame, source, queue, quota, callback or function body is replaced or short-circuited.

The existing typed compiler and legacy prototype flags remain OFF by default. A test-only original-function entrypoint fc_ir019_call exists only under FC_TYPED_IR_DISPATCH_TEST_HARNESS=true and strictly accepts fc_ir:ir019_*.

## Native baseline and observer semantics — accepted

[Three-original-Minecraft-JVM native run #44829643542](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44829643542) · [raw source/child task logs and all scoreboard snapshots #14675837665](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44829643542/artifacts/14675837665).

Fresh Minecraft 26.3/Java25 servers executed the same disposable original mcfunctions in three modes: unwrapped vanilla semantics; wrapper plus passive source/callee census (no typed code); and previously accepted IR-018 ASM scoreboard lowering with entirely native function calls. Original cases cover false and true single guards, negative/missing holders, chained score conditions, return run function, nested child calls, @s source via Minecraft's execute summon, the original mixed compilation boundary, and eleven command quota cuts (1,2,3,4,5,6,8,12,16,32,64).

**All 84 complete scoreboard observations in both experimental/control modes exactly matched vanilla (252 complete snapshots).** The instrumented arm recorded **285 original source-entry reaches, 185 ordinary callbacks, 66 single-guard dispatch source reaches, 22 complex-dispatch source reaches, 56 native CallFunction target tasks**, and zero native call tasks to the deliberately never-passed child function. Native per-child tasks: ir019_child_hit 34; ir019_child_chain 6; ir019_child_nested 8; ir019_child_return 8; ir019_child_skip 0.

Those 56 call tasks are not 56 proven successful predicate evaluations *at identifiable call sites*. The counts provide separately validated observation boundaries. No CPU was measured, no conditional dispatch instruction compiled, and no speedup is claimed.

## Real Blastback original capture-stage dispatch activation — accepted

[Accepted original publisher pilot #44830205578](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830205578) ([raw artifact #14676455133](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830205578/artifacts/14676455133)) and [independent confirmation with complete original source text #44830583429](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830583429) ([raw artifact #14675244535](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830583429/artifacts/14675244535)).

The experiment loaded the untouched SHA-verified Blastback Hotfix 3 archive in an actual Fabric Minecraft 26.3/Java25 JVM, using the accepted block-palette positions and untouched real datapack functions. A single **native summoned TNT** with tag fc_blastback_probe and an explicitly longer **160-tick test fuse** was observed in-world. The source world initially matched the separate cloned template, including all five independently placed witness blocks. A passive source and native child-call census ran for 30 seconds without ScoreAdd/fusion/typed lowering or other scheduler changes. The original first attempted fixture used a queued setup function, and its TNT presence probe returned zero; that attempt was explicitly invalid, not counted as accepted. The corrected pilot summoned TNT directly, confirmed exactly one actual entity, and required a reached Blastback capture source before accepting the narrower capture-stage observation.

**Accepted capture-window facts:** 625 game ticks elapsed; census overflow=0; **141 observed original function-source sites**, **71,161 original source-entry reaches**, **351,588 ordinary Brigadier callback invocations**, **4,562 exact single-score/static-child dispatch entry reaches** across 21 reached sites, **682 multi-stage/return dispatch entry reaches** across 4 reached sites, and **5,623 original native CallFunction target tasks** across 11 allowlisted callees. The capture stage was genuinely reached (55 capture-related source rows had nonzero entry counts). All counts are from a bounded event window and may include ongoing restoration. No compiler opcode or child-call scheduler optimization ran.

| Original native callee target | Observed CallFunction task entries |
| --- | ---: |
| erb:capture/store | **3,278** |
| erb:restore/job_tick | **1,242** |
| erb:capture/schedule | **449** |
| erb:runtime_tick | **618** |
| erb:pump/dormant | 31 |
| erb:group/join | 2 |
| erb:group/add_segment | 1 |
| erb:job/create | 1 |
| erb:capture/queue | 1 |
| erb:capture/loop | 0 |
| erb:capture/requeue_moved | 0 |

Those per-target tasks are **not** independently attributable to the 4,562 single-score call-site reaches, especially because the native target may have other callers, function tags, scheduled/tick dispatch and multi-stage conditions. For example, both exact simple guards in erb:runtime_tick were reached **618 times**; neither observation gives the outcome of the guard without separate native target/source attribution.

### Independent capture-stage confirmation

The same pinned original publisher, native one-TNT test fixture, explicit 30-second observation gate and original command semantics were run in a **second independently booted Minecraft server** after extending the report to retain bounded 240-character original source text. It again confirmed one original TNT actor, original capture-stage entry, and zero census overflow. Independent Minecraft processes are not an A/A CPU study, and their dynamic command/tick exposures are allowed to differ.

| Original capture-window metric | First accepted JVM #44830205578 | Independently repeated JVM #44830583429 |
| --- | ---: | ---: |
| Minecraft ticks observed | 625 | 593 |
| Original source-entry reaches | 71,161 | 70,550 |
| Ordinary callback entries | 351,588 | 348,980 |
| Exact static single-score dispatch source reaches | 4,562 | 4,341 |
| Complex/return dispatch source reaches | 682 | 647 |
| Native child-call tasks for selected targets | 5,623 | 5,589 |
| Original callback invocations on restore/job_tick line index 4 | 319,509 | 316,969 |

Both pilots provide *similar magnitude* activation and a concrete high-fanout source line, but neither controls identical work or proves that the dispatch condition parsing is a major CPU cost. The second run archives exact original command text alongside the per-site source/callback records.

### A more important observed fork/callback workload

The original source entry **erb:restore/job_tick, source index 4** was reached **1,242** times but its original terminal Brigadier callback ran **319,509** times (roughly 257 times per reached entry). The exact publisher source is:

    execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1

This demonstrates **massive fan-out between source entry and callback**, arising from Minecraft's selector-driven, context-forked execution. It also exposes a serious measurement trap: the total **351,588 callbacks** cannot be interpreted as only 71,161 command executions, or as child-function call completions. The forked scoreboard writes and selector scans are real vanilla semantics and cannot simply be skipped. Whether their *overhead* can be safely reduced is a separate future compiler-cost question.

The parent source/template region was **not restored to its reference template** at the end of this short capture observation; this remains **NOT a successful full restoration workload and NOT a CPU benchmark**. The same limitations of the earlier BLASTBACK-007 study apply. The accepted IR-019 claim is narrower: original event activation, specific named source entry frequency, native child-call tasks, and callback fan-out were observed under an authentic publisher datapack.

**Dispatch-lowering promotion gate (not met merely by the accepted source/native tests):**

1. SHA-pinned real Blastback capture-stage event that actually reaches named dispatch sources; report failures rather than interpreting an invalid event as success.
2. Identify **one exact static single-score callsite** that is repeatedly and materially hot; reconcile its observed native target tasks with other possible callers rather than asserting one-to-one attribution.
3. Attribute meaningful avoidable CPU to guard parsing/evaluation or native call-task staging, not to unavoidable child body work. Use timed A/A controls and no significant perturbation from diagnostics.
4. Before compiling any dispatch op, derive/test native source-guard skip, successful child queue, quotas, parent and child frame, return-run, feedback, reentrant callback insertion and failure behavior; a first opcode may keep the child native and must preserve the prior barrier if it cannot prove exact fidelity.
5. Native 26.3 multi-JVM parity for original commands, original source and distinct feedback and partial command quota state; only then allow a separate, opt-in compiler experiment. Never cross dispatch barriers with the IR-012 direct cursor without a separate frame-equivalence proof.

## Post-observer native backwards compatibility — accepted

[Accepted post-census native regression #44830314012](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830314012). After adding the passive CallFunctionMixin observer, a separate 14-JVM regression repeated three previously accepted original-Minecraft 26.3 suites, with census disabled unless explicitly requested:

- IR-016 mixed-function native/interpreted/ASM/direct barrier and quota semantics: **126/126 complete states per mode**, [artifact #14675608629](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830314012/artifacts/14675608629).
- IR-017 range/guarded scoreboard arithmetic native/previous/interpreted/ASM/direct: **168/168 complete states per mode**, [artifact #14675833552](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830314012/artifacts/14675833552).
- IR-018 source-bound @s original-entity/no-entity and opaque function barriers across five modes: **87/87 complete states per mode**, [artifact #14674084671](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44830314012/artifacts/14674084671).

These bounded backwards-compatibility results show that the default-off observer did not alter established native queue, quota and fallback behavior on the tested original commands; they are not CPU or real-Blastback restoration evidence.

## Current decision

**IR-019's measurement and source-eligibility stage is accepted**, but the dispatch compiler remains deliberately **NOT implemented**. The genuine Blastback window proves 4,562 exact-call guard entry reaches, yet the most prominent measured event activity was 319,509 selector-forked callbacks from one restore-source command. No bounded CPU attribution proves that simplifying the single-score function guards removes meaningful event CPU. Prior [COMPILER-CPU-004](compiler-positioned-call-cpu-004.md) found native immediate CallFunction setup negligible in a *different* Vein Miner workload; its timing must not be directly projected onto Blastback. Focus next on measured guard-stage and selector-fork overhead or a validated capture-specific CPU comparator; only reopen dispatch lowering with a positive actual-cost hypothesis and frame/return parity. All child scheduling remains original Minecraft.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir019.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir019_inventory.py
    python3 scripts/ci_typed_ir019_native.py
    python3 scripts/ci_typed_ir019_blastback.py

Once all accepted updated runs finish, archive the four IR-019 research workflows as manual-only. All changes are on work/compiler-coverage / draft, unmerged PR #10. All performance and production switches remain OFF.
