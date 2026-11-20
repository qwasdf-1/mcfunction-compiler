# COMPILER-IR-019 — Native conditional-call census, hotness gate and dispatch feasibility

**Status (2026-11-20):** pinned two-publisher exact-source dispatch stratification ACCEPTED; three-Minecraft-JVM transparent native function-dispatch semantics/observer ACCEPTED. Original Blastback one-TNT capture-stage activation and independent post-census regression are separate gates. **No native function-dispatch optimization has been implemented. No performance claim.** Work remains on branch work/compiler-coverage, draft PR #10 unmerged.

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

## Real Blastback activation and next gate

A distinct original Blastback one-TNT capture-stage experiment exercises the unchanged original publisher pack, the accepted block/witness palette, and a 30-second bounded event window with the passive census allowlisted to 13 relevant capture/tick/job functions and 11 native callees. It requires a real TNT entity, advancing tick counter, and **at least one named capture-stage source entry** before declaring a valid activation. The source/witness observations, native call-task counts and derived output are saved independently of full restoration. In particular, a partially restored region is NOT silently promoted as a valid completed restore.

The previously attempted whole-restoration Blastback pilot had incomplete restoration. This capture census does not fix or bypass that limitation; it asks the narrower question whether specific dispatch commands are reached during a genuine capture event. The child tasks are reported by target, without inventing passing guard counts or callsite attribution.

**Dispatch-lowering promotion gate (not met merely by the accepted source/native tests):**

1. SHA-pinned real Blastback capture-stage event that actually reaches named dispatch sources; report failures rather than interpreting an invalid event as success.
2. Identify **one exact static single-score callsite** that is repeatedly and materially hot; reconcile its observed native target tasks with other possible callers rather than asserting one-to-one attribution.
3. Attribute meaningful avoidable CPU to guard parsing/evaluation or native call-task staging, not to unavoidable child body work. Use timed A/A controls and no significant perturbation from diagnostics.
4. Before compiling any dispatch op, derive/test native source-guard skip, successful child queue, quotas, parent and child frame, return-run, feedback, reentrant callback insertion and failure behavior; a first opcode may keep the child native and must preserve the prior barrier if it cannot prove exact fidelity.
5. Native 26.3 multi-JVM parity for original commands, original source and distinct feedback and partial command quota state; only then allow a separate, opt-in compiler experiment. Never cross dispatch barriers with the IR-012 direct cursor without a separate frame-equivalence proof.

## Current decision

Accepted as a **measurement and source-eligibility stage**, not as a speedup or implemented dispatch compiler. The native CallFunction task observer is the new capability; all original child scheduling remains unchanged. Continue only with a validated real capture workload and actual cost/hotness evidence. If that gate cannot be established, stop here rather than implementing an unmeasured, semantically risky optimizer on synthetic evidence.

## Reproduce

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir019.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir019_inventory.py
    python3 scripts/ci_typed_ir019_native.py
    python3 scripts/ci_typed_ir019_blastback.py

Keep all four research workflows manual-only after their individual accepted gates. All changes are on work/compiler-coverage / draft, unmerged PR #10. All performance and production switches remain OFF.
