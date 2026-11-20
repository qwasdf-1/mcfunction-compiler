# COMPILER-IR-013 — Re-entrant command-queue ordering

**Status:** Research-only implementation complete. **Real Minecraft 26.3 semantic comparison accepted**, including a demonstrated regression in the earlier unguarded compiler and exact state recovery in guarded ASM, guarded interpreter, and guarded IR-012 direct scheduling. **Performance promotion not established.** Date: 2026-11-20.

**Branch / review:** `work/compiler-coverage`, existing unmerged [draft PR #10](https://github.com/qwasdf-1/mcfunction-compiler/pull/10). Previous stages: [IR-008](compiler-typed-ir-008.md), [IR-009](compiler-typed-ir-009.md), [IR-010](compiler-typed-ir-010.md), [IR-011](compiler-typed-ir-011.md), [IR-012](compiler-typed-ir-012.md).

## The actual semantic bug

Minecraft's `ExecutionContext` is a staged queue. `queueNext` appends to `newTopCommands` while the current queue action runs. The driver then splices those entries onto the head of `commandQueue` **when that action returns**, ahead of existing queued function entries. Thus a synchronous scoreboard or mod callback that calls `queueNext` can schedule a function to run **between adjacent source commands**, even though the callback itself is synchronous.

IR-008/009 compiled 2–64 original commands into one generated JVM `UnboundEntryAction`. IR-012 replaced eligible function's child-frame/`ContinuationTask` work with larger scheduled regions. Both improvements preserved *per-command quota debits, feedback, scoreboard results and tracing*, but their **queue action boundaries were not identical to vanilla**. If a synchronous callback inserts work after command i, unguarded compiled command i+1 may execute before Minecraft's driver regains control and inserts the callback work. This is observable when i+1 reads a score that the newly queued function writes.

**Native negative-control reproduction:** A test-only `ServerScoreboard.onScoreChanged` observer on `#ir013_trigger` enqueues `fc_ir:ir013_injected` with the *current* `ExecutionContext` and `ExecutionContext.queueInitialFunctionCall`. It does not run the injected function inline. The injected function increments `#ir013_mark` by 7 and increments a counter. An original function first sets `#ir013_trigger`, then copies `#ir013_mark` into `#ir013_seen`. Vanilla sees the queued function's change (7); the unguarded compiler can read the old value (0). A case with the trigger at source instruction **64** (end of an ASM region) does **not** exhibit the failure: the compiler has already reached an ordinary queue boundary.

The user-visible benefit is correctness, not additional scoreboard arithmetic. This also demonstrates why **effect-set alias checks alone are insufficient**: the compiler has no static knowledge of an arbitrary queue insertion initiated by another mod.

## Guarded execution design

New `ReentrantQueueEpoch` exposes a monotonically increasing generation scoped to a Minecraft `ExecutionContext`. The existing `ExecutionContextMixin` increments it at `queueNext` only with `FC_TYPED_IR_REENTRANT_SAFE=true`. It does not replace the queue, change insertion order, or modify existing call entries. Default installations leave the extra counter inactive.

Each compiled `TypedScoreIRRuntime.State` receives its complete immutable original typed instruction array, and snapshots the queue generation when its bytecode region **begins**. Before beginning every subsequent instruction, it checks whether the generation changed. If no callback staged work, the generated ASM continues normally. If work **was queued**:

1. Finish the current already-executed instruction normally; no write, result or quota is undone.
2. At the next original instruction, **yield before its quota debit, objective lookup, guard evaluation or score mutation**; this generated region returns immediately.
3. Stage a `QueuedTail` cursor for the *remaining* immutable typed instructions in this region, **after the newly queued callback work** in `newTopCommands`.
4. When the cursor is itself dequeued, enqueue **one validated typed instruction as one Minecraft `CommandQueueEntry`**, followed by a cursor for the next remaining instruction. The driver now flushes staged work after every original command boundary; any further callback insertion takes precedence over the next cursor. These exceptional queue cursors do not charge quota, as Minecraft's own `ContinuationTask` does not charge quota; the individual typed scoreboard instructions retain the established quota, feedback, conditional and result semantics.

The exceptional tail uses `TypedScoreIR.executeTypedStep` (refactored out of the IR interpreter) rather than re-parsing text or reentering the previously wrapped `BuildContexts.Unbound` / Brigadier callback. The **normal ASM path still emits direct JVM score operations**. Only an actual detected callback insertion causes per-original-command actions.

### Why we did not resume the old wrapped command

An early implementation attempted to bind the retained `FusedCommand.vanilla().original()` for the remainder. It matched native ordering for ordinary and binary scoreboard commands, but **crashed with `StackOverflowError`** when the next line was `execute if score ... run ...`. `ScoreAddPrototype.compileChainedModifiers` mutates an executable `CommandContext` to contain a `ScoreConditionCommand` wrapper. The wrapper's historical `fallbackChain` references that context, so invoking it through the research arm with the old prototype flags disabled can recursively call itself.

This failure is independent of queue ordering. IR-013's corrected exceptional queue action uses the exact previously validated *typed IR semantics* one command at a time. Neither the wrapping code nor vanilla parser was widened. Runtime missing-objective fallbacks still retain the preexisting original-command behavior; arbitrary mutated wrappers under other fallback conditions require separate correctness validation before production promotion.

### IR-012 integration

The IR-012 `CallFunction` interception remains **strictly gated**: fully typed ASM source function, empty function/source result callback, no active tracer, no `returnParentFrame` and no unsupported/macro/fork/nested instructions. Its `Resume(...,pc)` continuation runs an existing compiled chunk. An IR-013 queue insertion within that chunk stages the typed one-command tail before the next IR-012 chunk. Insertion on the last command naturally runs before the following chunk without a special yield. Ordinary `/function`, `execute store` and `/debug function` remain in the vanilla call frame.

## Native semantic evidence

[Successful Minecraft 26.3 / Fabric / Java 25 CI #44697923172](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44697923172) · [Original fixtures, every native scoreboard observation, server logs and CPU windows (artifact #14611453042)](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44697923172/artifacts/14611453042)

**Six independent actual Minecraft JVMs**, one disposable original-source datapack. All executed **85 state observations** each:

| Mode | Parity with vanilla | Demonstrable boundary behavior |
| --- | --- | --- |
| Native/unwrapped | Reference | 69 queued test callback functions |
| Previous ASM, unguarded | **46 mismatching observations** | Reproduced bug; 0 yields |
| Guarded ASM with vanilla CallFunction | **85/85 matched** | 49 yields; 320 queued per-command recovery steps |
| Guarded typed IR interpreter | **85/85 matched** | 49 yields; 320 recovery steps |
| Previous IR-012 direct scheduler, unguarded | **46 mismatching observations** | Reproduced bug; 131 direct calls |
| Guarded IR-012 direct scheduler | **85/85 matched** | 49 yields; 320 recovery steps; 139 direct calls |

Vanilla and every guarded arm queued **69** synthetic callback functions; the two unsafe arms queued 70 because their changed command ordering can change whether an insertion remains within the quota. The intentionally unsafe modes were required to **differ inside a chunk** and **not differ for the at-the-end-of-region boundary**; both negative-control assertions passed. Thus no passing guard arm could be explained merely by a callback that never ran.

Fixture coverage includes immediate and mid-chunk queue insertion, 128-command functions with insertion at line 31 or 64, two injections during one function, a conditional `execute if score` after injection, a nested-function/unsupported compiler barrier, public `/function` return callbacks, stored function result and `/debug function` tracing. Every mode also ran 5 functions under **15 verified quota limits**: `1, 2, 3, 4, 5, 8, 16, 31, 32, 33, 64, 65, 70, 130, 260`. These tests distinguish absent scoreboard rows from a present numeric zero.

The direct guarded arm still actually exercised the function scheduler: **139 direct calls, 139 direct compiled-chunk actions, eight noninitial resumptions and four callback/tracer fallbacks**. This is **not** an optimization that merely disables the compiler in the face of the adversary; it preserves the fast path until actual re-entrant insertion forces a local change.

## Guarded CPU check (no synthetic queue injection)

[Same accepted CI evidence](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44697923172), with `scripts/ci_typed_ir013_cpu.py` reusing the IR-012 exact-work crossover study.

Both CPU arms have `FC_TYPED_IR_REENTRANT_SAFE=true` and `FC_TYPED_IR_REENTRANT_TEST_OBSERVER=false`. They run **the same emitted ASM and identical 256-command four-region function** within each Minecraft JVM. The only on/off switch is **IR-012's direct function scheduler**. This means the screen tests whether direct scheduling remains attractive with the IR-013 guard enabled, **not** the guard's isolated cost.

- Two independent actual Minecraft JVM boots; eight counterbalanced ABBA/BAAB direct-on/off blocks; four same-path off/off A/A controls.
- Every CPU window executed exactly **120 function invocations × 256 original commands = 30,720 score writes** and matched the expected scoreboard result.
- Median direct-on versus off Server-thread running CPU fraction **+2.762%** (positive means *more* CPU with direct scheduling).
- Per-JVM medians **+6.103%** and **−2.191%**, inconsistent in direction.
- Individual comparison blocks **−20.370% to +37.226%**; same-path A/A median **+7.807%** and range **−5.957% to +42.373%**.

There is **no established performance improvement**. These windows share processes within each boot, and RCON/scoreboard effects and noisy host scheduling remain in the denominator. Comparing to the earlier unguarded IR-012 study across separate runs does not isolate the guard's causal overhead. No independent-server 95% promotion gate, cross-mod workload or representative datapack speedup is established.

## Limits and disposition

IR-013 responds to staged work **reported by `ExecutionContext.queueNext`**. It is not a proof about arbitrary mods that directly corrupt the queue backing collections, use unsupported asynchronous/off-thread mutation, rewrite command internals, change the observable callback contract, or produce complex frame-discard effects not represented by these test cases. The same earlier typed-IR scoreboard objective missing/read-only fallback paths and other wrapped command families require separate adversarial tests. The return/trace API remains deliberately restricted under direct scheduling.

Crucially, this **does not retroactively make IR-008, IR-012 or the compiler safe as general production defaults**. It closes one demonstrated scheduler-order failure under the admitted command shapes. Retain `FC_TYPED_IR_REENTRANT_SAFE`, `FC_TYPED_IR_MODE=bytecode|interpreted`, explicit namespace, `FC_WRAPPER_PROBE`, and IR-012's direct-call gate as **opt-ins**; the scoreboard adversary and `fc_ir013_call` exist only when `FC_TYPED_IR_REENTRANT_TEST_OBSERVER=true`. The guarded normal path is still one 2–64-command JVM action without a queued callback.

**Decision:** keep IR-013 on draft PR #10 as a successful bounded correctness experiment; keep all production defaults off, and archive expensive research workflow as manually dispatched. The best next step is a broader queue/frame effects and representative datapack acceptance suite, especially dynamically removed objectives, nested callbacks, and discard/return interaction, before another performance campaign.

## Files and reproducibility

- `ReentrantQueueEpoch.java`, `mixin/ExecutionContextMixin.java`: research-only staged-queue generation.
- `TypedScoreIRRuntime.java`, `TypedScoreIR.java` and `TypedScoreIRBytecode.java`: instruction-boundary epoch check, yielded `QueuedTail` and shared one-instruction typed interpreter semantics.
- `ReentrantQueueProbe.java`, `mixin/ScoreboardQueueInjectionMixin.java`, `ProbeCommands.java`, `function_compiler.mixins.json`: guarded test-only real scoreboard callback that queues the injected function in the live execution context.
- `scripts/ci_typed_ir013.py`, `tests/test_typed_ir013.py`: native six-arm semantic parity + negative controls and quota matrix.
- `scripts/ci_typed_ir013_cpu.py`: guarded two-JVM exact-work direct scheduler crossover with A/A noise sentinels.
- `.github/workflows/research-typed-ir013.yml`: archived manual-only workflow after acceptance; raw artifact linked above.
