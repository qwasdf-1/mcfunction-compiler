# SCHED-ATTR-026 — Within-task context and dispatch phase attribution

**Status:** Phase A exact JVM callsite reconnaissance, not yet a validated CPU measurement.

## Motivation

Accepted [SCHED-ATTR-024](scheduler-entry-census-SCHED-ATTR-024.md) observed 80,799 `BuildContexts.execute` and 28,265 `ExecuteCommand.execute` method invocations in the pinned 215-ore Vein Miner event. Accepted [SCHED-ATTR-025](scheduler-task-cpu-SCHED-ATTR-025.md) measured descriptive inclusive costs of approximately 59.1 µs per BuildContexts and 266.8 µs per ExecuteCommand invocation with 1/32 deterministic sparse clock sampling. The same study measured CallFunction and ContinuationTask corrections of only ~0.165 µs, close to its ~0.7–1.0 µs empty-clock floor. None is a causal optimization speedup or exclusive CPU partition.

The question is **what inside BuildContexts and ExecuteCommand accounts for those inclusive spans**: modifier/source expansion, Brigadier dispatch/context preparation, or actual command callbacks/world mutation. We must not assume a particular Java callsite or continuation method before inspecting the exact Minecraft 26.3 runtime bytecode.

## Phase A — exact runtime bytecode map

Use Java 25 and Fabric Loom's pinned Minecraft 26.3 merged-deobf classfile artifact. Accept only existing SHA-256 fingerprints documented in `docs/research/source-versions.lock` (initial inspection or the later current verification); fail closed on missing/different artifact. Collect `javap -p -s -c` output for `BuildContexts`, `ExecuteCommand`, Brigadier `ContextChain`, `CommandContext`, `ContinuationTask` and `ExecutionContext`. Store every method descriptor and invocation opcode/callsite, with original raw outputs and explicit classfile SHA-256 in CI artifacts. No modified Minecraft runtime, game event or CPU observations in Phase A.

**Gate:** Only after inspection should we select exact supported `@Inject` or `@Redirect` boundaries for Phase B. Do not place arbitrary clocks at guessed method names, infer internal dispatch structure from method name alone, or confuse parsed command contexts with actual `Command.run` game effects.

## Phase B — prospective sparse native experiment (not yet active)

Once Phase A confirms the actual bytecode and injection feasibility, preregister a separate targeted mechanism diagnostic with exact 215-ore / 1,952-queue-advance native parity and zero cgroup throttling, using normal cached ScoreAdd in all arms. Preserve three independent JVM boots: PLAIN, EMPTY consecutive CPU clock read, TIMED callsite bracket. Each category must use a deterministic, matched sparse sample (target about 1/32 of a stable invocation population, bounded total clock calls). Distinguish *inclusive* from *exclusive* CPU and ensure actual Brigadier dispatch/command work is never mislabeled pure scheduler overhead. RCON begin/end and profiler readiness/quality checks must match the earlier study. A signed control subtraction near or below the clock floor is inconclusive. No production feature is enabled.

The earlier method-level SCHED-ATTR-025 36%/57% inclusive projections are **not causal gains, standalone cost partitions, or disjoint buckets**. The study may discover that context construction is dominated by vanilla source fan-out or real gameplay. Only results from verified callsite boundaries can refine that claim.

## Change discipline

Keep this work stacked on SCHED-ATTR-025, with the previous PRs remaining draft. Begin with a Java source/bytecode survey that creates archived diagnostics. No global scheduler rewrite, modified quotas, alternate function-call backend, or CI 30-boot campaign. Existing research workflows remain manual-only.
