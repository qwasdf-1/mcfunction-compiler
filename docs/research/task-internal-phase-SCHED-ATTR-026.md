# SCHED-ATTR-026 — Within-task context and dispatch phase attribution

**Status:** Phase A exact JVM callsite reconnaissance completed on 2026-11-18. Phase B sparse native CPU attribution preregistered below; no accepted Phase B CPU data yet.

## Motivation

Accepted [SCHED-ATTR-024](scheduler-entry-census-SCHED-ATTR-024.md) observed 80,799 `BuildContexts.execute` and 28,265 `ExecuteCommand.execute` method invocations in the pinned 215-ore Vein Miner event. Accepted [SCHED-ATTR-025](scheduler-task-cpu-SCHED-ATTR-025.md) measured descriptive inclusive costs of approximately 59.1 µs per BuildContexts and 266.8 µs per ExecuteCommand invocation with 1/32 deterministic sparse clock sampling. The same study measured CallFunction and ContinuationTask corrections of only ~0.165 µs, close to its ~0.7–1.0 µs empty-clock floor. None is a causal optimization speedup or exclusive CPU partition.

The question is **what inside BuildContexts and ExecuteCommand accounts for those inclusive spans**: modifier/source expansion, Brigadier dispatch/context preparation, or actual command callbacks/world mutation. We must not assume a particular Java callsite or continuation method before inspecting the exact Minecraft 26.3 runtime bytecode.

## Phase A — exact runtime bytecode map

Use Java 25 and the versioned Fabric Loom Minecraft 26.3 merged-deobf classfile, generated from the official Mojang server distribution. **The whole generated Loom jar SHA-256 is not reproducible across these CI boots**, so it is recorded per run but cannot serve as a stable acceptance lock. Instead verify the official Mojang server SHA-256 from `source-versions.lock` (and the intended `26.3` Gradle version), then check exact typed method signatures and source bytecode callsite descriptors. Collect `javap -p -s -c` output for `BuildContexts`, `ExecuteCommand`, Brigadier `ContextChain`, `CommandContext`, `ContinuationTask` and `ExecutionContext`. Store every method descriptor and invocation opcode/callsite, with original raw outputs and explicit classfile SHA-256 in CI artifacts. No modified Minecraft runtime, game event or CPU observations in Phase A.

**Gate:** Only after inspection should we select exact supported `@Inject` or `@Redirect` boundaries for Phase B. Do not place arbitrary clocks at guessed method names, infer internal dispatch structure from method name alone, or confuse parsed command contexts with actual `Command.run` game effects.

## Phase A completed and bytecode-backed callsite selection

[Actions run #44231519067](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44231519067) **passed** the official Mojang server SHA-256 check (`d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64`), the Fabric 26.3 build, exact typed method signatures, Brigadier jar discovery, and full `javap -p -s -c` inspection. [Original bytecode artifact #14394823122](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44231519067/artifacts/14394823122) contains the raw disassemblies.

The exact 26.3 bytecode establishes three **non-speculative** callsite boundaries:

1. `BuildContexts.execute` at bytecode offset **197** invokes the static `ContextChain.runModifier(CommandContext,Object,ResultConsumer,boolean):Collection`, inside the source-expansion loop. The method later creates `ExecuteCommand` and calls `ContinuationTask.schedule` at offset **548**. A nonempty redirect may invoke `runModifier` multiple times; the rest of `BuildContexts` is NOT necessarily all queue construction (it also branches, checks fork limits and handles errors).
2. `ExecuteCommand.execute` at bytecode offset **34** invokes static `ContextChain.runExecutable(CommandContext,Object,ResultConsumer,boolean):int` following the command quota debit. The returned value and error/trace/profiler work occur outside this call.
3. `ContextChain.runExecutable` at bytecode offset **13** invokes `Command.run(CommandContext):int`, after copying the context and before notifying the result consumer. **This is the actual command implementation**, including scoreboard/world/NBT mutations; its CPU cannot be declared avoidable dispatch overhead.

Use an opt-in Mixin `@Redirect` for each exact invocation, delegate the original call **exactly once**, and close the timing scope in `finally` on successful or exceptional return. Keep method-typed descriptors and generic erasure correct, and retain native world/parity/exception integrity gates. The caller's `ContextChain` is in the separately resolved Brigadier dependency; the original Minecraft jar alone does not contain every Brigadier class.

## Phase B — preregistered sparse nested callsite CPU study

Once Phase A confirms the actual bytecode and injection feasibility, preregister a separate targeted mechanism diagnostic with exact 215-ore / 1,952-queue-advance native parity and zero cgroup throttling, using normal cached ScoreAdd in all arms. Preserve three independent JVM boots: PLAIN, EMPTY consecutive CPU clock read, TIMED callsite bracket. Each category must use a deterministic, matched sparse sample (target about 1/32 of a stable invocation population, bounded total clock calls). Distinguish *inclusive* from *exclusive* CPU and ensure actual Brigadier dispatch/command work is never mislabeled pure scheduler overhead. RCON begin/end and profiler readiness/quality checks must match the earlier study. A signed control subtraction near or below the clock floor is inconclusive. No production feature is enabled.

The earlier method-level SCHED-ATTR-025 36%/57% inclusive projections are **not causal gains, standalone cost partitions, or disjoint buckets**. The study may discover that context construction is dominated by vanilla source fan-out or real gameplay. Only results from verified callsite boundaries can refine that claim.

## Change discipline

Keep this work stacked on SCHED-ATTR-025, with the previous PRs remaining draft. Begin with a Java source/bytecode survey that creates archived diagnostics. No global scheduler rewrite, modified quotas, alternate function-call backend, or CI 30-boot campaign. Existing research workflows remain manual-only.

## Phase A inspection provenance amendment — 2026-11-18

The first [Actions inspection run #44231002304](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44231002304) built the Fabric mod successfully but **failed closed** before its source inventory because a freshly generated Loom Minecraft 26.3 classfile at the standard `minecraft-merged-deobf/26.3` path had SHA-256 `bf8e2d4fbaeac8e71179cac31f826262292fe9d6bc170143f893c38354d83597`, not either earlier source-inspection fingerprint. This is a **toolchain/cache provenance change**, not observed runtime CPU. Its observed hash is now recorded separately in `source-versions.lock`. The rerun is required to confirm the historical typed method descriptors against that new artifact. Brigadier's `ContextChain`/`CommandContext` must additionally be loaded from the resolved external Mojang Brigadier jar, not assumed present in the Minecraft merged jar. **No CPU timing or native game event is authorized from this fingerprint alone.**

### Frozen experimental protocol and acceptance

Three independent new Minecraft 26.3 JVM boots in locked order **PLAIN/OFF**, **EMPTY control**, **TIMED**. All run exactly the same publisher Vein Miner 5.3.0+26.3 ZIP SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`, six-sided 215-ore playerbot event and 1,952 queue-head advances, with normal cached typed ScoreAdd and no Spark/JFR/other command counters. Keep the original nine-second idle baseline, positive Linux /proc Server-thread running CPU, zero cgroup throttling and ≤25% runqueue wait, exact source/final marker/scoreboard parity and four compiled queue/drain ScoreAdd commands. Record all failures including startup/mixin failures, never rerun an observed mining event.

The SCHED-ATTR-025 whole-task CPU clocks retain their **unchanged 1-in-32 per-type ordinal hash**, and the internal phase clocks are enabled **only for those same selected parent invocations**. The new three phase streams are `modifier` inside selected `BuildContexts`, and `executable` + `command` inside selected `ExecuteCommand`. OFF collects neither parent nor phase CPU clocks (the scoped event path census remains). EMPTY records two consecutive CPU reads at each selected parent and selected internal callsite; TIMED brackets the original method and its nested callsites. Each individual sample is on the same Server thread. No extra clock on an unselected task.

For every arm, verify task-level SCHED-ATTR-025 call/sample counts and their original gates. For the new phase streams, fail if any clock is disabled, different thread, negative, nested same-phase, leaked, greater than event CPU, missing a `finally` close, or contaminated by additional instrumentation. `Command.run` must not outnumber enclosing `runExecutable`. EMPTY vs TIMED sampled invocation exposure for a phase may differ at most **15%**. Define a phase as **underpowered** rather than silently ignoring it when it has fewer than **100** samples for modifier or **200** samples for executable/command; the other valid phases may still be assessed, and raw data from an underpowered stream is preserved. A timed zero-interval fraction over **20%** or a signed corrected mean ≤ its EMPTY clock-pair mean is flagged **near/below clock floor** and not treated as a precise positive cost. If TIMED whole-event Server-thread CPU differs from the separately booted PLAIN by >**30%**, reject the diagnostic for host/instrumentation comparability, without inferring an A/B effect.

### Analysis without false attribution

For each phase independently compute `C = total_empty_cpu_ns / empty_phase_samples`, `T = total_timed_cpu_ns / timed_phase_samples`, and **signed** `D = T - C`; never clamp to zero. Project a descriptive whole-event inclusive phase cost using the **original selected parent task expansion factor** `parent_calls / parent_samples`: `P = D × observed_phase_calls_in_selected_parents × (parent_calls/parent_samples)`. This is **only** a deterministic-sample extrapolation, not a known representative cost of all methods.

Compute three *sensitivity differences* within the same TIMED sample regime: (1) inclusive BuildContexts minus measured runModifier work; (2) ExecuteCommand minus runExecutable; (3) runExecutable minus Command.run. These subtract control estimates gathered in independently booted JVMs, so their small residuals may be dominated by JIT/mixin/clock overhead. They do NOT form a disjoint whole-event CPU histogram, exact cost of queue construction/Brigadier itself, or a causal speedup. The sampled CallFunction/ContinuationTask studies are **not** part of the new optimizer target.

On successful raw results, prioritize only a separately testable micro-optimization with verified semantics (selectors, fork limits, quota debit, errors, callbacks and nested functions). Keep the PR **draft** and the workflow manual-only after acceptance; do not promote the experimental hooks or rewrite the global scheduler.
