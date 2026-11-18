# SCHED-ATTR-027 — Real Vein Miner context-copy versus result-consumer CPU inside Brigadier

**Status:** Preregistered three-arm native diagnostic, pending execution. **No accepted SCHED-ATTR-027 CPU measurements yet.** This is research-only, stacked on SCHED-ATTR-026, not a production change or a scheduler replacement.

## Why this particular study

Accepted [SCHED-ATTR-026](task-internal-phase-SCHED-ATTR-026.md) measured, on one independently booted plain/empty/timed Minecraft 26.3 native Vein Miner event, an extrapolated **58.83% of Server-thread CPU** inside `ContextChain.runExecutable`, but **35.55%** inside its nested actual `Command.run` implementation. The **23.29% signed *sensitivity difference*** is **not** Brigadier overhead: the enclosing method also copies a context and invokes a result-consumer that can trigger real gameplay effects. One boot per arm and parent-ordinal sampling prevent causal speedup or precise exclusivity claims.

[Verified bytecode inventory from #44232819056, artifact #14396745579](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44232819056/artifacts/14396745579) shows precisely:
- `ContextChain.runExecutable(CommandContext,Object,ResultConsumer,boolean):int` calls **`CommandContext.copyFor(source)`** at bytecode offset 2, before executing the command. `CommandContext.copyFor` **returns the existing object when the new source is the exact same instance**, otherwise constructs a new, shallow `CommandContext` copying references to args, nodes, modifiers and nested child.
- `Command.run(CommandContext)` is invoked at bytecode offset 13. SCHED-ATTR-026 already times it under the same selected ExecuteCommand parent.
- `ResultConsumer.onCommandComplete(CommandContext,success,result)` occurs **twice in bytecode**, at offsets 26 (successful command) and 49 (caught `CommandSyntaxException`); exactly one should run for any normally completed `runExecutable`. Neither callback branch may be silently omitted in an injection.

The study asks: **How much inclusive Server-thread CPU is observed at the context-copy callsite and result-consumer callsite, and how frequently does the copy reuse its existing object?** It does **not** assume the callback cost is avoidable, or that the copy consumes meaningful CPU.

## Frozen instrumentation and workload

Implement a research-only Fabric Mixin on Brigadier `ContextChain.runExecutable`, with exact 26.3 bytecode-verified invocation descriptors, `remap=false` and `@Redirect(require=1)` for the single `copyFor` call, **`@Redirect(require=2)`** for both `onCommandComplete` success and failure callsites. Each wrapper calls the original exactly once and closes its CPU interval in `finally` even on exceptional return. Classification counters execute outside the timed intervals.

Extend the existing SCHED-ATTR-026 `SchedulerPhaseCpuProbe` by two nested phases, `COPY` and `RESULT`, gated behind an additional explicit `FC_SCHED_BRIGADIER_PLUMBING_PROBE=true` environment opt-in. Preserve the exact existing **1-in-32 selected ExecuteCommand parent ordinal/hash** from SCHED-ATTR-025, with no independent resampling or clock reads on unselected parent calls. Keep the existing BuildContexts, ExecuteCommand, `runModifier`, `runExecutable`, and `Command.run` phase measurements for same-arm context.

Run **three independent fresh Java 25 + Minecraft 26.3 Fabric JVMs**, in fixed PLAIN/OFF, EMPTY, TIMED order, with unchanged normal cached ScoreAdd. Use the pinned publisher VeinMiner 5.3.0+26.3 ZIP SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. Perform the **real player-bot 215-ore / 1,952 queue-head advances** work. Check exact source/block/marker/scoreboard/run-state final parity, exactly four shared compiled ScoreAdd-family queue/drain commands, nine-second pre-event idle stability, Server-thread /proc running CPU, ≤25% runqueue wait and zero cgroup throttling. No JFR, Spark, global scheduler alternative, ordinary callback counter, or 30-boot campaign. Preserve failed arms without replacing observed events.

- **PLAIN/OFF:** event-window census and instrumentation classes present, **zero CPU reads** at all parent and child scopes.
- **EMPTY:** exactly the existing selected parent calls; adjacent back-to-back CPU time reads at `copyFor` and `onCommandComplete` before the real call (and existing parent/phase empty-clock controls).
- **TIMED:** match the selected parent ordinals and bracket `copyFor` and `onCommandComplete` separately with the same current Java Server-thread CPU clock.
- Within the selected copy calls count **reused original object vs newly returned object**; within selected result-consumer calls count **success vs failure**. If an error path is unobserved in the fixture, report **zero exception coverage**, not a tested error-path performance profile.

## Strict integrity and quality gates

All three arms must satisfy the original SCHED-ATTR-025/026 native parity, host, clock support, active owner thread, no nested/unclosed same-phase scopes, and sample exposure gates. For new `copy` and `result` callsites:
1. **≥200** phase samples in each enabled arm; every selected sampled call must have exactly one closed CPU interval and nonnegative CPU time, and the total observed per-phase CPU may not exceed the event's Server-thread CPU.
2. Both selected callsite counts must be within **2%** of the selected `runExecutable` sample count in the same arm. A genuine source exception may reduce these counts, but if the coverage gate fails, **reject the native screen** instead of masking it. `Command.run`, `copyFor`, and result-consumer scopes must remain in the selected parent task.
3. EMPTY vs TIMED selected call/sample exposure may differ by no more than **15%**, measured against the larger count; the original whole-task and three-stage gates remain unchanged.
4. Selected copy identity counts must sum exactly to copy calls. Selected result success + failure counters must sum exactly to callback calls. Archive both outcome categories, even if the failure branch is zero.
5. Timed zero-delta fraction >**20%** or signed control-subtracted mean ≤the mean EMPTY clock-pair time makes the individual phase **near/below clock floor** and inconclusive as a positive cost estimate. Negative signed differences remain negative; do not clamp them to zero or discard the arm.
6. Whole-event TIMED vs PLAIN CPU difference >**30%** invalidates the mechanism screen for host/instrumentation comparability; it is not a calibrated causal overhead estimate.

## Analysis: what can be claimed

For `COPY` and `RESULT` independently, compute `C = empty_cpu_ns/empty_samples`, `T = timed_cpu_ns/timed_samples`, and **signed** `D = T-C`. Project descriptive inclusive cost `D × timed_selected_calls × (timed_total_ExecuteCommand_calls/timed_selected_ExecuteCommand_calls)`, then divide by timed Server-thread CPU. This inherits the original frozen ordinal sample and has **unproven workload representativeness**, potential JIT/host differences across independent JVMs, and timer/Mixin maintenance overhead not covered by two adjacent reads. These are not causal optimizer effects or confidence-bounded percentages.

Use the already captured `runExecutable` and `Command.run` phase estimates to calculate **signed residual sensitivity**:
`runExecutable − Command.run − copyFor − ResultConsumer`.

At these exact bytecode callsites, copy, command, result-consumer are sequential; however their independently control-corrected sample extrapolations, callback-side arbitrary gameplay and instrumentation effects mean the residual is **not an exact Brigadier dispatch/queue overhead budget, proven potential compiler saving, or strict Amdahl ceiling**. Never add these observations to unrelated inclusive BuildContexts/ExecuteCommand figures as disjoint event-wide shares.

Retain a full per-arm native JSON and status record, original stdout/stderr, SHA-256 fingerprints and bytecode inventory; do not synthesize unobserved error-path measurements. If the result consumer dominates, next identify callback implementations and their original scoreboard/gameplay side effects before considering an optimization. If the copy is usually identity-reused, caching/removing `copyFor` would have less opportunity than assumed, but still requires semantics tests.

**Stop rule:** Do not loosen the gates or select profitable-looking subcases after observing times. Keep the draft research PR, return workflow to **manual-only** after first completed/failure-preserved study, and make **no production change** without independent semantic and causal speed benchmarks.
