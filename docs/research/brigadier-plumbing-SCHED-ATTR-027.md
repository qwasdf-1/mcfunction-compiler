# SCHED-ATTR-027 — Real Vein Miner context-copy versus result-consumer CPU inside Brigadier

**Status:** Three-arm native sparse CPU diagnostic **completed and passed all preregistered workload/host/clock/sample gates on 2026-11-18 UTC (November 17 EST)**. The observed result-consumer CPU signal is substantial, but it is **not proven avoidable scheduler overhead or a causal speedup**. This is research-only, stacked on SCHED-ATTR-026, not a production change or a scheduler replacement.

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

## Completed native screen — 2026-11-18 UTC

**Authoritative accepted campaign:** [GitHub Actions #44238748694](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44238748694), **success**. Original [raw artifact `sched-attr-027-brigadier-plumbing-cpu` #14398144505](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44238748694/artifacts/14398144505) retains all `SCHED-ATTR-027/diagnostic.json` per-arm records, all native `PERF-011-veinminer/.../results.json`, stdout/stderr and startup/idle records, the exact code/official-source fingerprint and Brigadier bytecode. Original standalone Java and Python quality-gate tests, Fabric build and pinned official Minecraft 26.3 plus publisher datapack hashes all passed.

Every native arm completed **215 real ore work operations, 1,952 queue head advances, source stat 1, original source removed, zero remaining ore and marker entities, run state zero, and four compiled ScoreAdd-family queue/drain commands** with identical final state. All pre-event idle gates passed, no measured cgroup throttling; /proc Server-thread runqueue-wait fractions were **0.088%, 0.071%, 0.157%** in PLAIN/EMPTY/TIMED respectively, well below 25%.

| Independent JVM arm | Complete event elapsed time | Linux Server-thread running CPU |
|---|---:|---:|
| PLAIN (no clocks) | **14.534 s** | **13.00899 s** |
| EMPTY pair reads | **14.227 s** | **12.69518 s** |
| TIMED callsite brackets | **15.038 s** | **13.52331 s** |

The TIMED vs PLAIN whole-event Server-thread CPU difference was **+3.954%**, under the previously locked 30% coarse host/instrumentation veto. The independent JVM clock totals **do not establish causal treatment or overhead effects**.

### Matched selected-callback results

The existing original parent 1/32 ordinal selection produced exactly **872 selected `ExecuteCommand` / `runExecutable` / `Command.run` calls in both EMPTY and TIMED arms**, with 872 selected `copyFor` and 872 selected result-consumer callbacks in each. All five scopes were on the correct Minecraft Server thread, with zero nested or leaked timing scopes and zero timed zero-delta intervals. Both success and caught-syntax-exception callback **bytecode injection sites were required by Mixin**; the native sample actually exercised 15 failure callbacks.

| Nested invocation, TIMED arm | EMPTY pair mean | TIMED inclusive mean | Signed corrected mean | Projected *inclusive* event CPU fraction |
|---|---:|---:|---:|---:|
| `ContextChain.runExecutable` (enclosing scope) | 0.277 µs | 282.907 µs | **282.631 µs** | **59.02%** |
| `Command.run` (real command gameplay work) | 0.263 µs | 176.610 µs | **176.347 µs** | **36.83%** |
| **`ResultConsumer.onCommandComplete`** | **0.455 µs** | **103.066 µs** | **102.611 µs** | **21.43%** |
| `CommandContext.copyFor` | **0.317 µs** | **0.407 µs** | **0.0906 µs** | **0.019% — unresolved clock floor** |

**`copyFor` context identity in TIMED samples:** **1 returned the existing context**, and **871 returned a distinct context**, of 872 sampled calls (**0.115% fast-path reuse**). EMPTY separately observed 0 reuse and 872 distinct contexts in its selected sample. A distinct context is **shallowly copied** per verified bytecode, not deep-parsed or cloned through all argument maps; a very high distinct-context count **does not prove large CPU allocation overhead**.

**Result-consumer outcomes in TIMED:** **857 success callbacks** and **15 failure callbacks** (1.72%) in 872 sampled calls. EMPTY observed exactly the same 857/15 distribution for the selected callsites; this is genuinely exercised failure-callback coverage for this real fixture, **not** comprehensive exception/selector/fork correctness testing.

### Narrowed remainder, correctly qualified

| Same-arm sampled extrapolation sensitivity | Projected CPU | Fraction of TIMED event Server-thread CPU |
|---|---:|---:|
| `runExecutable − Command.run` | **3.0016 s** | **22.195%** |
| `ResultConsumer.onCommandComplete` | **2.8978 s** | **21.429%** |
| `copyFor` | **2.56 ms** | **0.019% (below correction floor)** |
| `runExecutable − Command.run − ResultConsumer − copyFor` | **101.15 ms** | **0.748%** |

The result-consumer callback explains **most of the observed runExecutable-minus-Command.run difference** in this specific sample projection. It is a **measured inclusive callback interval**, not automatically Brigadier overhead, scheduler bookkeeping, or time a mod can eliminate. Its receiver is the ordinary `ResultConsumer` and may execute substantial necessary scoreboard, function, success/return, or user-defined callback effects. Eliminating, deferring, duplicating, or caching it could silently change state and trace/error semantics.

The remaining ~**0.75%** is a signed sensitivity difference between separately EMPTY-corrected sparse method intervals. It can include nearby Java dispatch/scaffolding and timer/Mixin/aggregation perturbation; it is **not a reliable exclusive CPU-time budget or hard ceiling**. The `copyFor` signed difference of **90.6 ns** is far smaller than its **316.7 ns empty clock-pair** mean, making a precise positive cost **unresolved at this instrumentation floor**. Do not interpret 0.019% as an established exact share.

No statistically powered confidence intervals, independent randomized treatment, sample representativeness proof or causal optimization gain were obtained. All displayed fractions are *nested*, control-adjusted extrapolations from one event per arm. The 15 error callbacks should not be interpreted as broad exception-path behavior across all datapacks or modpacks. The additional disabled Mixin wrapper cost remains unmeasured and should block casual integration into production.

### Decision

**No reason to rewrite Brigadier, skip `copyFor`, or change the outer scheduler based on this study.** The apparent ~23% dispatch gap is mostly required-or-potentially-required **result callback execution**. If the goal remains more CPU savings, inspect exactly which **`ResultConsumer` implementations** occur in the native Vein Miner fixture and which specific callback effects are produced. A follow-up must distinguish real scoreboard/game-state changes from recomputable overhead and prove full success/failure/trace/selector/fork parity before testing a *specific* transformation with independent causal CPU benchmarking. Do not treat callback suppression as a valid optimization.

**Repository state:** This remains draft, stacked on SCHED-ATTR-026 / PR #6. The dedicated `.github/workflows/research-brigadier-plumbing-cpu.yml` workflow is back to **manual `workflow_dispatch` only** after the accepted native campaign. No production compiler or scheduler defaults have been changed.
