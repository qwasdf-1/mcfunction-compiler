# COMPILER-IR-011 — Singleton scoreboard feedback lowering

**Status:** Implemented as a strictly gated compiler research experiment; native semantic parity **ACCEPTED**; same-JVM CPU result **does not support promotion** (2026-11-19).

**Branch:** `work/compiler-coverage`, existing [draft PR #10](https://github.com/qwasdf-1/mcfunction-compiler/pull/10). **Predecessors:** [IR-008](compiler-typed-ir-008.md), [IR-009](compiler-typed-ir-009.md), [IR-010](compiler-typed-ir-010.md). The feature is disabled by default, and none of these changes are merged into production.

## Why this compiler pass was considered

The typed IR currently lowers a supported scoreboard command to real `ScoreAccess.add/set` bytecode but `TypedScoreIRRuntime.State.finish` still assembles a `CommandResponseTracker`, tracks one holder/result, dispatches one-element feedback and returns the score.

The exact Minecraft 26.3 runtime implementation establishes a narrower equivalence:

1. Every accepted IR `Mutation`, `Binary` and taken `Conditional` terminal writes **one fixed literal fake scoreboard holder**, and `finish` tracks it **exactly once**, with `ElementType.ANY`.
2. `CommandResponseTracker.track(holder, newScore)` sets `elementCount=1`, `onlyElement=holder` and `totalValue=newScore`. This remains true even if `newScore=0` or negative.
3. `sendFeedback` first calls `messages.throwIfZero(1, ...)` (which cannot trigger), then invokes `source.sendSuccess` with the **single-element** message factory via `messages.onSuccess().onSingle()`, then returns `totalValue`.
4. Replacing that tracker/dispatch work with exactly `source.sendSuccess(() -> message.onSuccess().onSingle().create(holder, newScore, objective, ...), true)` and `result = newScore` is therefore equivalent for the supported fixed one-holder instruction shape. It retains Minecraft's own `sendSuccess` behavior, including lazy message creation, source acceptance, broadcast/admin handling and the original `TraceCallbacks.onReturn` result.

Pinned reference inspection:
[CommandResponseTracker, 26.3](https://mc-packet-reference.netlify.app/26.x/source/net/minecraft/server/commands/commandresponsetracker/) ·
[CommandSourceStack, 26.3](https://mc-packet-reference.netlify.app/26.x/source/net/minecraft/commands/commandsourcestack/) ·
[ScoreboardCommand, 26.3](https://mc-packet-reference.netlify.app/26.x/source/net/minecraft/server/commands/scoreboardcommand/).

This is not legal for a command that tracks multiple holders, aggregates results, uses `ElementType.NON_ZERO`, has conditional zero-result error behavior, or delegates to an arbitrary modded callback. Such commands are **not accepted** by the existing typed IR subset and remain original vanilla entries.

## Implementation and gates

- `TypedScoreIRRuntime.State.finish` contains a new explicit **singleton-result branch**, keeping the previous `CommandResponseTracker.create/track/sendFeedback` branch intact as the control. The direct branch sends ordinary vanilla success feedback and calls the same original per-command tracer. It never elides scoreboard writes, score-object access, command quota debits or original-entry fallback.
- `TypedScoreIR` has `FC_TYPED_IR_SINGLETON_FEEDBACK=true` as a strict feature gate and explicit `singleton_feedback_steps` and `tracker_feedback_steps` counters when `FC_TYPED_IR_DIAGNOSTICS=true`.
- `ProbeCommands` registers `fc_ir011_feedback on|off` **only** if both `FC_TYPED_IR_SINGLETON_FEEDBACK` and `FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE` are true. This changes the guarded `finish` branch at runtime without recompiling any ASM instruction, so both A/B conditions execute identical generated code for the score operations themselves.
- The rejected IR-010 per-score value cache is disabled in **all** IR-011 tests. The IR-008/009 compiler opt-in conditions (`FC_WRAPPER_PROBE`, explicit namespace and bytecode/interpreted modes) remain mandatory.

**Scope note:** The specialization lives in shared typed-IR response bookkeeping, not the assembler's arithmetic emission; the emitter still performs real direct scoreboard JVM operations as established in IR-008/009. There is no changed scheduler implementation here.

## Accepted native semantics

[Final Minecraft 26.3 Fabric/Java25 validation](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44657976931) · [Raw semantic and CPU logs/results](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44657976931/artifacts/14594835294)

Four fresh actual Minecraft JVMs each executed **54 observed cases** using the same disposable datapack:

1. native/unwrapped vanilla;
2. typed ASM with standard `CommandResponseTracker`;
3. typed IR interpreter with singleton result feedback;
4. typed ASM with singleton result feedback.

Exact observed scoreboard states matched for zero-result and negative-result mutations, signed overflow, assignment/other binary operations, taken/untaken score predicates, a vanilla nested-function barrier, a surrounding function-result consumer, feedback-enabled function invocations and partial execution at quotas **1,2,3,4,5,6,7,8,10,16,32**. Command callback/feedback counts below demonstrate actual activation, not only successful compilation.

| Activation diagnostic | ASM tracker | IR singleton | ASM singleton |
| --- | ---: | ---: | ---: |
| Direct typed instructions executed | 266 | 266 | 266 |
| Emitted bytecode regions | 7 | 0 | 7 |
| Standard tracker finish executions | **266** | 0 | 0 |
| Direct singleton finish executions | 0 | **266** | **266** |
| Binary instruction executions | 113 | 113 | 113 |
| Taken conditional terminal executions | 15 | 15 | 15 |
| Skipped conditional instructions | 19 | 19 | 19 |
| Original-entry runtime fallbacks | 0 | 0 | 0 |

**Limitations:** These are native scoreboard-state/result-consumer equivalence checks and structural proof of feedback-message dispatch; they are **not** exhaustive message-text captures from every command source, `/debug function` trace comparison, modded callback interception, concurrency, plugin compatibility or reload endurance. Those would still be required before default promotion. The branch retains precise vanilla fallback for instructions outside the typed subset.

A failed *development* crossover run ended before timing conclusions because two unused scoreboard rows were absent (rather than zero) in the benchmark world. The accepted script initializes those two rows **outside** the measured interval; that failure did not change the compiler implementation and was not used as performance evidence. The signed-overflow fixture also uses vanilla-valid `scoreboard players remove 1`; the `add` argument is constrained to nonnegative values by 26.3 Brigadier.

## Same-JVM CPU evaluation — no justified speedup

Two independent native Minecraft JVMs ran **the same compiled 64-command function**, with 62 repeated scoreboard binary operations per invocation. The runtime switch toggled only the response specialization, with IR-010 source-value caching disabled and all high-cost profiling counters turned off. Each CPU window executed **160 × 64 = 10,240 original scoreboard commands**, with the exact expected final scoreboard state checked.

- **Twelve** four-window ABBA/BAAB singleton-vs-tracker blocks across the two JVMs;
- **Six** same-tracker-vs-tracker A/A blocks;
- Signed singleton-vs-tracker median Server-thread running CPU **+2.271%** (positive means *more* CPU with singleton enabled);
- JVM-level medians **+6.480%** and **−2.171%**, i.e. inconsistent direction;
- Singleton-vs-tracker individual blocks ranged **−12.067% to +29.139%**;
- A/A median **−2.456%** and range **−14.106% to +12.262%**.

These timing blocks are correlated within each JVM, and A/A itself shows noticeable noise. The experiment does **not** demonstrate a statistically reliable performance improvement, either over the tracker on the synthetic fixture or for real datapacks. HotSpot/JIT may already optimize away much of the small single-element object graph, and scoreboard mutation and command scheduling costs remain.

**Disposition:** Keep the singleton path explicitly opt-in, off by default, and do not promote it. Do not repeat more speculative allocation microstudies here. This second consecutive result alongside IR-010 indicates that the next work should be **genuine function-level compiler scheduling/IR optimization** rather than shaving very small amounts of per-command scoreboard overhead. Candidate: a carefully modeled fast path for contiguous compiled blocks that reduces per-command scheduler, context and objective-resolution work with precise quota/trace/callback continuation, with real-world datapack coverage; that is **not** implemented in IR-011.

## Reproduction

Implementation: `TypedScoreIR.java`, `TypedScoreIRRuntime.java`, `ProbeCommands.java`. Fixtures, native arms and same-JVM counterbalanced A/B: `scripts/ci_typed_ir011.py`. Structural tests: `tests/test_typed_ir011.py`. Workflow: `.github/workflows/research-typed-ir011.yml`, archived **manual-only** after acceptance. Complete raw logs and every measured CPU window are retained in the above linked artifact.
