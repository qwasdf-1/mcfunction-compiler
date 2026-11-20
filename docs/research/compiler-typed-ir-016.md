# COMPILER-IR-016 — Source-spanned mixed-function IR and vanilla barrier fidelity

**Status:** Implemented in draft on `work/compiler-coverage`; native acceptance pending. Research-only, no production-default change, no performance promotion. PR #10 remains open/draft.

## Goal

IR-015 established that the direct JVM lowering already executes meaningful work on a pinned real Vein Miner event (511 real typed steps), but IR-012's whole-function fast path cannot admit even one identified recurring full function in Vein Miner or Blastback. The current typed compiler created a flat list of emitted actions and original actions without representing which source instructions each action replaced. That made barriers and source coverage implicit, fragile compiler invariants.

**IR-016 introduces the first-class function program representation needed for later language widening.** It does not claim that unsupported commands can already run inside a custom direct scheduler or that the compiler understands the semantics of arbitrary `execute` chains. Each unsupported command is a *native vanilla queue barrier*, not an inlined opaque callback.

## New compiler stage

```text
Minecraft PlainTextFunction; original validated queue entries
        |
        v
ScoreAddPrototype (typed-only preflight from IR-015)
        |
        v
MixedFunctionIR.lower
  [TypedRegion(start, Program[2..64], emitted action, bytecode?)]
  [OpaqueBarrier(start, EXACT original action, UNSUPPORTED_OR_CONTROL)]
  [OpaqueBarrier(start, EXACT original action, TYPED_SINGLETON)]
        |
        v
MixedFunctionIR.Program(id, original line count, immutable ordered nodes)
  - validates contiguous source spans / original count, no duplicate/drop
  - rejects unknown effect model on typed nodes
  - executableEntries() assembles the actual native queue entry list
  - directBytecodeChunks(): all nodes typed and bytecode or null
        |
        v
TypedScoreIR.CompiledFunction original + mixed executable entries
  - original function identity and trace length preserved
  - already-valid generated ASM and interpreter backends unchanged
  - vanilla owns opaque entry scheduling, callbacks, returns, forks
  - IR-012 direct cursor only sees all-bytecode programs (no barriers)
```

The source-to-node lowering is now the **single source of truth**, replacing IR-008's independently constructed `flush`/flattened entry-list pass. There is no separate declaration of barriers that the compiler might forget to honor at execution time: actual `CompiledFunction.entries()` are assembled from the immutable node actions. A `Program` constructor fails on source span gaps, overlaps, or dropped entries.

Every typed region is 2–64 consecutive Brigadier-validated instructions, retaining an effect/observability model per instruction. Unsupported or control-flow commands are wrapped *only as opaque IR nodes*, **not** as custom executable wrappers; they remain their exact original `UnboundEntryAction` and use Minecraft's existing `BuildContexts` and frame logic. A one-command typed island remains an original source action (singleton barrier). A 65-command run becomes a bytecode region of 64 plus a singleton barrier; a 66-command run can become two bytecode regions of 64 and 2. If bytecode generation fails, the node is an interpreted typed region and the no-child-frame direct scheduler refuses the function.

**Safety rule:** no direct scheduling if a program contains ANY opaque barrier, interpreted region, singleton tail, return, child function call, macro or unknown modded command. IR-013's optional reentrant queue-epoch guard continues to manage insertion **inside** a generated region; an opaque node is a stronger boundary because it runs through Minecraft's original queue behavior.

## Research-only observability

`functioncompiler ir008` now includes `ir016_visited`, `ir016_mixed_functions`, `ir016_typed_regions`, `ir016_typed_lines`, `ir016_opaque_barriers`, and `ir016_singletons` counters. Counters are enabled by `FC_TYPED_IR_DIAGNOSTICS=true`; regular gameplay does not maintain them.

`functioncompiler ir016 fc_ir:ir016_call_chain` returns a *bounded*, per-function compact source layout and admission report, for example fields `source_lines`, `typed_lines`, `typed_regions`, `opaque_barriers`, `singleton_barriers`, `direct_candidate`, and `layout`. Layout codes `J` (ASM node), `I` (interpreted node), `V` (original vanilla), `S` (singleton original) identify source line numbers and lengths. Only 2,048 function ledgers and the first 24 layout nodes per function are retained. **This is a diagnostic summary, not an execution-cost or hotness measurement.** Large real datapacks may exceed this ledger limit; aggregate counters still record all compiled program nodes. No function source bytes are copied into the ledger.

The dedicated `fc_ir016_call` native CI entrypoint exists only under `FC_TYPED_IR_MIXED_TEST_HARNESS=true` and only accepts fixture namespace `fc_ir` with `ir016_*` function names. It is not a production API.

## Native acceptance plan

Four fresh actual Minecraft 26.3/Java25 Fabric JVMs: uncompiled Minecraft reference, interpreted mixed IR, generated JVM mixed IR, and generated JVM with the existing conditional IR-012 whole-function direct scheduler. All modes execute the *same disposable original mcfunction sources*. Cases include:

- A sequence of two typed regions separated by an original nested function call, plus a range-score guard barrier and following typed region;
- A return command between compiled regions (unreachable tail must stay unreachable);
- `execute store result score` around scoreboard operations, including a custom `fc_probe_leaf` mod-added command returning 7;
- Objective removal/re-creation from a vanilla barrier, and missing-objective behavior inside a typed region;
- A deliberately isolated typed singleton, a 65-command singleton tail and a 66-command full bytecode program.

The same cases are repeated under command quotas `1,2,3,4,5,6,8,12,16,32,64,65,130`, comparing exact *full observed scoreboard state* to the native reference, including partial effects and existence of the dynamically created objective. An independent expected full-run state is checked for each case. Compiled modes must return the expected source-span ledger and nonzero actual typed execution; the direct arm must admit the all-bytecode chunked function but not any function containing a call, return, barrier, or singleton tail.

**Acceptance:** exact state equality on every full and quota case in all compiled modes, without hiding native divergences or claiming performance. Re-run the older IR-014 adversarial callback/objective semantic gate after the refactor. Any failed native test is a blocked milestone, not a result to reinterpret as pass.

## Remaining deliberate limitations

This is a necessary *compiler representation* change, not yet a new function scheduler capable of stepping through arbitrary opaque actions, nor a wider instruction language. Range guards and `@s` score operations remain vanilla. No cross-instruction state caching, command elision, hoisting, inlining, custom full-function cursor for mixed programs, general macro bytecode, or result/trace bypass is enabled.

**Next incremental compiler milestone:** introduce a typed range-score conditional instruction and exhaustively validate quota, failure, feedback and adversarial queue injection semantics at mixed/typed boundaries. Separately decide whether a mixed direct cursor is worthwhile only after proving it can preserve Minecraft's original frame, result and queue staging and measuring actual workload coverage.
