# SCHED-ATTR-028 — concrete result-consumer routing and callback effects

**Status:** Phase A exact Minecraft 26.3 bytecode inspection pending. **No accepted SCHED-ATTR-028 native counts or CPU effects.** Research-only branch stacked on accepted [SCHED-ATTR-027](brigadier-plumbing-SCHED-ATTR-027.md).

## Hypothesis and important limits

In the previous three-arm native screen, `ResultConsumer.onCommandComplete` had a control-subtracted descriptive mean ~102.61 µs in a 1-in-32 sampled `ExecuteCommand` subset, extrapolated to ~21.43% of the event Server-thread CPU. There were 857 successful callbacks and 15 failure callbacks in 872 matched TIMED samples. `CommandContext.copyFor` was near the timer-control floor. This is **inclusive callback CPU**, not scheduler waste, recoverable CPU, or evidence that result handling can be skipped.

The next question is *which runtime result-consumer implementations and delegate callbacks actually run in this same Vein Miner fixture,* and whether their CPU is necessary state-changing work (scoreboard writes, return values, command success-count handling, nested function continuations) rather than repeated routing/dispatch bookkeeping.

## Phase A — pinned bytecode inspection

Before selecting any Mixin/classification targets, inspect the exact Java 25 / Minecraft 26.3 runtime classes `ExecutionCommandSource`, `CommandSourceStack`, `CommandResultCallback`, `Frame`, `ExecutionContext`, `ExecuteCommand`, `CallFunction`, `BuildContexts`, and Brigadier `ResultConsumer`/`ContextChain`, with `javap -p -s -c`. Verify the official Mojang 26.3 server SHA from `source-versions.lock`, separately record the nondeterministic Loom-generated development jar and resolved Brigadier jar fingerprints, and archive every disassembly as-is. Explicitly identify where the `ResultConsumer` for `ExecuteCommand` is obtained, its concrete receiver, how it delegates to underlying `CommandResultCallback` and any function-frame callbacks, and what exact methods mutate scoreboard/return state.

A static class name or JVM lambda identifier alone does not prove callback side effects or CPU. If the callback receiver is an adapter capturing a source or frame, the correct next hook must classify **its delegate and effects**, not just the common adapter's class name.

## Phase B — prospective bounded native diagnostic

Only after Phase A establishes the actual 26.3 method signatures and call chain should a separate predeclared native method classification run be enabled. Reuse the pinned publisher Vein Miner 5.3.0+26.3 ZIP SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`, 215 ore operations and 1,952 queue head advances, same cached ScoreAdd, exact final world state, stable idle/Server-thread host gates and zero cgroup throttling.

First classify concrete callback *delegations* and their event counts. Where feasible, measure inclusive CPU inside the actual delegate actions using the existing bounded parent-ordinal clock selection, matched empty-clock control, and native three-arm parity. State-changing work is not automatically eliminable. Do not suppress/replace callbacks, infer savings from 21.4%, change quotas/errors/forks, or launch unbounded profiling. Any no-measurement result or failure must remain in the record; never synthesize zero callback cost.

**Stop rule:** A failed bytecode/API check or missing native callback coverage rejects a measurement; document original errors and change source targets only with evidence. Keep this as a **draft** stacked research PR with a manual-only workflow after testing. No production defaults changed.
