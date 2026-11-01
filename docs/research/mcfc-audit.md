# MCFC source audit

**Evidence level:** Static review of the pinned source snapshot below. The
project was not built or run as part of this audit.

## Snapshot and scope

Reviewed [MCFC commit `15ca1db`](https://gitlab.epicpix.dev/EpicPix/MinecraftFunctionCompiler/-/commit/15ca1db43556999ff29619ed0e41c971b66aae3e), dated 2026-06-17. Its `mc-26-1-fabric` module pins Minecraft 26.1.2, Fabric Loader 0.18.4, Fabric API 0.145.4+26.1.2, Loom 1.16.3, and Java 25. The changelog calls `0.4.0-alpha.1` “In Development” and says no versions are supported. It is a development reference, not evidence of a supported release or a 26.3-compatible mod.

The source is LGPL-3.0-or-later. Any reuse needs a separate license review.

## Design observed

MCFC compiles eligible functions to generated Java bytecode. Its source path
captures raw lines during `ServerFunctionLibrary` reload and feeds a custom
parser and compiler. It does not simply preserve and lower vanilla's parsed
Brigadier action tree. If parsing or command support fails for a function, that
function remains on vanilla execution. The current generator also has a
function-size cutoff and background compilation state.

Two runtime hooks divert compiled calls:

- `CallFunctionMixin` injects immediately after `ExecutionContext.incrementCost()`.
  This preserves the function-call debit before running generated code. It then
  executes the compiled body synchronously, handles result callbacks for its
  success/failure statuses, and cancels the vanilla queue entry.
- `ServerFunctionManagerMixin` also intercepts direct manager execution at the
  method head and runs a compiled function directly.

MCFC's README explicitly says it does not respect `maxCommandChainLength` as a
performance choice. The compiler's execution unit is therefore not a
source-line-for-source-line preservation of vanilla queue work. In Minecraft
26.3 the corresponding rule is named `minecraft:max_command_sequence_length`;
the exact quota and queue behavior is documented separately in
[`26.3-internals.md`](26.3-internals.md).

The current parser, continuations, command result handling, nested function
calls, return behavior, frame discard, and errors require direct parity review
before borrowing this approach. In particular, a compiled error returns an
execution-failed sentinel and the call hook still cancels the vanilla entry
when a compiled handle exists. That is not a safe point from which to restart
the original function after generated code may already have changed world
state.

## Tests and observability

The repository has a GameTest-backed harness that runs a fixture through the
compiled and vanilla paths and compares captured server state. The visible
`.mctest` fixtures in this snapshot cover scoreboard-player assignment only;
they do not establish quota, frame, callback, tracing, macro, or error parity.

Reporter code exists for compile and execution diagnostics. The README says
reports can include exceptions and command text. In this snapshot the compile
constant `ENABLE_REPORTING` is false, so this is a code capability rather than
evidence that this exact configuration sends reports.

## Relevance to this project

Useful ideas to investigate further:

- Compile only the commands and functions with proven semantics; preserve a
  vanilla fallback for unsupported inputs.
- Compare compiled and vanilla outcomes with a reusable differential harness.
- Treat function-call scheduling, callbacks, quota, frames, and partial side
  effects as separate parity obligations.

Do not carry forward the whole-function synchronous execution model or its
quota policy without a 26.3 design and low-quota runtime evidence. The audited
branch targets 26.1.2 and changes a different set of Minecraft internals from
26.3.

## Follow-up questions

- Which exact vanilla queue entries and quota debits can a 26.3 specialization
  safely replace?
- How should command failures preserve vanilla's continue/return behavior
  after earlier commands have already produced effects?
- Can the project's differential harness compare callbacks, trace events,
  frames, and quota exhaustion in addition to final scoreboard state?
