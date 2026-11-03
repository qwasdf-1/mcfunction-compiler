# Architecture overview

## Status: Production Architecture (v1.0)

This document describes the production architecture for the Minecraft Function
Compiler v1.0 on Minecraft Java Edition 26.3 Fabric dedicated servers.

The system combines:
1. **Pipeline Chaining & Fused Region Specialization (Default-Enabled):**
   Fuses contiguous eligible commands into single unrolled actions, folding
   context modifiers (`as @s at @s`), direct scoreboard predicates (`if score`),
   score store redirection (`store result score`), block/entity predicates
   (`if block`, `if entity`), and storage mutations into zero-frame operations.
2. **Selective Macro Arguments (Default-Enabled):**
   Extracts targeted keys directly from compound tags or storage targets without
   full compound serialization, yielding -22.25% to -28.40% faster event latency
   on sustained server workloads (Vein Miner 5.3.0) and full mod stacks (Lithium
   0.26.2 + Bellows 1.1.3 + Moonrise 1.2.0).
3. **Tiered JIT Engine & Parameterized ASM Bytecode (Opt-In / Experimental):**
   Generates unrolled JVM hidden classes parameterized strictly by command count
   and cached via `MethodHandle`, completely eliminating Metaspace leaks while
   bypassing cold and startup paths.
4. **Configuration & Admin Commands:**
   `config/function-compiler.json` configuration file with hot reload support and
   in-game `/functioncompiler status|metrics|reload` commands.
Focused seven-arm macro state/error checks match vanilla and verify the expected
per-function specialized callback counts. PERF-002 has not established a
reliable speedup: its RCON median is effectively tied with vanilla, and its single-per-arm Spark
allocation estimates remain higher than vanilla. The harness also verifies
nested returns, recursion, dynamic quota changes, zero/one/two/four fork
matches over limits 1–12, fused-region quota/error continuation, and exact
flat/nested `/debug function` trace parity, including nested error continuation
and pending-region discard after `return fail`, `return 7`, and nested
`return run function`. An isolated `execute if function` callback also returns
failure after a child side effect while discarding the child's pending tail and
resuming the parent's pending fused tail exactly once, with vanilla state and
trace parity in all nine Fabric modes plus the vanilla reference. An isolated
`execute store success` child return-failure case stores 0, discards the child
tail, and resumes the parent tail once; its state and exact trace also match
vanilla in all nine Fabric modes. The paired `execute store result` child
return-value case stores 7, discards its pending child tail, and resumes the
parent tail once; its state and trace also match vanilla in all nine Fabric
modes. The inverse `execute unless function` return-failure case runs its
conditional branch, discards the child tail, and resumes the parent tail once;
all nine Fabric modes match the vanilla score and six-event trace. When an
`execute store result` child returns failure, the callback stores 0, discards
the child's pending tail, and resumes the parent tail once; that state and
trace also match in all nine Fabric modes. A successful `execute store success`
child return-value case records 1 even though the child returns 7, discards the
child's pending tail, and resumes the parent continuation once; state and
exact six-event trace match in all nine Fabric modes. A nested `execute store
result` wrapper using `return run function` stores result 7, discards pending
child and wrapper tails, and resumes the parent tail once at score 37; that
state and exact eight-event trace also match in all nine Fabric modes.
Paired nested `execute store success` wrappers using `return run function` record
1 on child return 7 and 0 on child return failure, discard pending child and
wrapper tails, and resume the parent tail at score 37 with matching eight-event
traces in all nine Fabric modes.
Five sequential changed-body/tag reloads, removal/re-addition, and load/tick
tags also pass. An extended 25-cycle bytecode check retained 15 live generated
classes after each GC with stable classloader identity and about 1.03 MiB peak
metaspace growth. An injected compile failure retained and ran the original
actions. The macro expansion prototype passes its focused tuple/cache
differential. A parse counter shows that repeated invocation does not reparse
one ordinary function and advances once per full resource reload. Compatibility
semantics, untested error/callback paths, concurrent/erroring reloads, and the
exact performance gate remain open.

The callback-only timer measured a lower ScoreAdd command-callback median,
but the matched full-function queue timer measured ScoreAdd 14.8% slower by
median in the 5,000-command fixture. Neither result supports enabling ScoreAdd:
callback timing excluded the scheduler, while the whole-function comparison
showed no gain. A separate fused-region queue timer completed ten trials per
arm across two randomized sets; fused was 40.8% lower than the instrument-only
delegate and 36.0% lower than ScoreAdd by median on the same static fixture.
This does not establish a real-world gain. Vein Miner supplies a native
real-pack ScoreAdd workload: five Fabric pairs show no reliable gain, and five
Fabric+Lithium plus five Fabric+Lithium+Moonrise pairs have slower medians with
wide ranges crossing zero. The Moonrise campaign included a temporary dormant
diagnostic mixin in both arms. No tested stack demonstrates a real-world
ScoreAdd speedup. A 2026-11-03 static screen found adjacent candidate runs in
the pack's family detection, but they have no runtime activation or performance
evidence, so fused and bytecode have not been measured in a real pack.
Allocation, timer calibration, fallback coverage, and broader parity gates
remain open. PERF-004 found emitted
bytecode about 23% slower than fused interpreted for the measured static
fixture. Prioritize profiling expensive function paths before adding more
ScoreAdd/backend variants. Keep all prototypes disabled.

## Proposed execution path

```text
Data pack resources
  -> vanilla resource resolution and Brigadier parsing
  -> capture validated parsed actions and source provenance
  -> immutable, reload-scoped semantic representation
  -> conservative recognition and effect analysis
  -> vanilla action, specialized entry, or resumable compiled region
  -> vanilla function scheduler, frames, and queue
  -> Minecraft world APIs, preserving relevant mod interception points
```

Static inspection supports the leading hypothesis of a narrow construction-time
integration point around `FunctionBuilder.build(...)`: vanilla has already
parsed ordinary commands there, and the resulting function map is used to
resolve tags afterward. This makes a delegating wrapper a plausible way to
preserve the original parsed function for fallback and expose the wrapper to tag
resolution. `FunctionBuilder` is package-private. The prototype proves Mixin
application, wrapper identity for custom tags through five reload generations,
and delegated instantiation. These results do not establish optimization
correctness or a performance benefit. Neither the hook nor an optimization
backend has been accepted.

The source review confirms that vanilla checks quota at queue-entry boundaries,
while debits can occur inside a running entry. A compiler must preserve both
cost events and yield/check boundaries; source lines are not a safe proxy for
either. Keep the vanilla scheduler and frames in the first prototype.

## Required boundaries

- Keep vanilla scheduling, frames, function calls, and queue checks in the first
  prototype.
- Model execution cost debits separately from yield/check boundaries.
- Preserve the source action for safe fallback; do not replay completed effects.
- Treat unknown commands as effectful and route them to vanilla.
- Fallback is a compile-time/selection safety path: ineligible actions stay
  vanilla, and backend compilation failures retain original actions. There is
  no runtime detector that recognizes a semantically wrong result and safely
  rolls back or retries a command; parity must be established before enabling
  an optimization, and mod-specific divergence needs a verified adapter or a
  disabled path.
- Scope artifacts and caches to one reload generation.
- Preserve debug tracing, callbacks, permission checks, errors, and mod hooks.
- Require observational parity with vanilla for every supported optimization
  case, including world and score state, return values, callback order,
  messages/errors, macro inputs, quota stops, fork behavior, tracing, and
  reload behavior. Keep a candidate disabled when a case fails or is untested.
- Vanilla 26.3 is the semantic oracle. On a modded server, compare the
  optimized path with the unoptimized path on that same stack as well; where
  the mod changes observable behavior, use a reviewed adapter to preserve
  vanilla semantics. If no adapter is verified, keep the affected optimization
  disabled for that mod/path and do not claim support. Do not treat a mod's
  divergence as a new vanilla behavior contract.
- Keep selector and entity NBT operations on vanilla paths until exact
  interception and fallback behavior is understood. Focused Bellows 1.1.2
  runtime checks passed the tested selector/AABB cases. A focused adapter now
  restores vanilla mob `home_pos` behavior for the tested merge, modify, and
  remove cases; broader selector and filtered-NBT paths remain open.
- Gate optimizations behind explicit controls until parity and performance are
  demonstrated.

See the versioned plan for the full semantic IR proposal, execution invariants,
and alternative integration hooks.
