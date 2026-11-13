# SCHED-ARCH-013 — Return to the core scheduler-architecture question

**Status:** Design/preregistration work. No new scheduler backend implemented and no result claimed.

## The research question we should now answer

> Can a server-side mcfunction compiler replace the *work* done by vanilla's `ExecutionContext` scheduling loop sufficiently to improve real Minecraft execution, while retaining all observable command semantics?

This is **not** synonymous with "does a fused scoreboard microbenchmark run faster?" or "can Minecraft's entire scheduler be deleted?" Minecraft 26.3 already parses ordinary function commands at datapack load; the incumbent is an iterative command-queue/frame scheduler with cost debits and limits, continuation handling, callbacks, fork behavior and trace-visible entry boundaries. We must isolate its incremental cost from Brigadier callback work and game-state operations.

## What we have already answered

- The wrapper and semantic differential infrastructure work, but the compiler-disabled installed-JAR overhead estimate remained noisy across fresh JVMs (SCHED-HOOK-004, -NOISE-005, GC-006).
- The within-JVM ABBA/BAAB methodology passed an A/A and larger positive-control screening (SCHED-BENCH-008). It is **not** proof of statistical power for arbitrary 3% improvements.
- Typed ScoreAdd alone did not beat its excluded native fallback in the SCHED-COMP-009 raw estimate; the A/A negative control excluded zero, so this was **not** a confirmed comparative regression.
- Fused regions delivered approximately **−29.91 log-percent CPU** relative to ScoreAdd alone on a contiguous 2,000-command workload (SCHED-COMP-010, valid placebo). Its actual implementation still enters vanilla `ExecutionContext` as a queue action and calls `ContextChain.runExecutable` for each fused command: this optimizes **queue-entry processing**, not wholesale scheduler replacement.
- The matching real Vein Miner native-event SCHED-COMP-011 comparison found **+0.64% median completion** (exact 97.85% interval −2.85% to +6.73%, 10 valid pairs) and did not meet the 15% threshold. The separate selective-macro mechanism has repeatedly demonstrated materially faster real events.
- SCHED-COMP-012 is the final bounded static-to-dynamic fusion-coverage exercise (Blastback and Simple Timer). It does not justify another broad datapack search.

## Precise decomposition

There are at least four distinct potential costs. Treat them separately:

1. **Loaded command representation / compilation:** parsing already happens on reload; command shape detection and compile/reload overhead are startup costs. Do not ascribe them to per-command dispatch.
2. **Vanilla scheduling:** queue entries, frame/continuation bookkeeping, quota and fork checks, trace callbacks, and task dispatch. Some bookkeeping is semantically necessary and cannot simply be discarded.
3. **Brigadier command execution:** context construction, argument/selector resolution, command callback dispatch. Typed specializations target this part.
4. **Minecraft work:** scoreboard storage, entity/block updates, NBT serialization, datapack-defined logic, and unavoidable tick/event pacing. Speeding up 2 or 3 matters only when 4 does not dominate.

## Required comparison matrix

| Arm | Runtime command path | Scheduler path | Question |
|---|---|---|---|
| A. Native control | Original parsed Brigadier actions | Vanilla `ExecutionContext` | Baseline |
| B. Typed-only | Typed safe commands | Same vanilla queue entry per original command | What does command specialization alone save? |
| C. Fused region | Same typed commands as B, contiguous safe runs grouped | Vanilla queue retains fewer super-entries; quota, traces, frames preserved inside each | What does *reducing queue scheduling* add beyond B? |
| D. Research alternative | **Exactly the same typed command operations as C** | Explicitly different continuation/scheduling implementation | What does the remaining vanilla queue cost, if bypassed safely? |

Arm D is **not yet an implemented or semantically approved backend**. In particular, comparing C to a direct scoreboard loop that silently ignores quota debits, forks, trace or callbacks would measure an invalid algorithm, not the scheduler's avoidable cost.

If the direct executor can only be semantically proven for no-fork/no-return straight-line islands, specify that applicability limit and retain a vanilla boundary on every unsupported command. Consider the `UnboundEntryAction` entry boundary as a *bridge* rather than changing the global server scheduler prematurely.

## SCHED-ARCH-013 execution order

### Phase 1: Instrumented attribution, then stop instrumentation during timing

Measure candidate command density and rate of original queue entries / fused entries / cost debits **separately**. Add low-overhead test-only counters around the queue, frame, command callback and actual game-state work. Use paired A/A calibration and a dedicated instrumentation-on diagnostic; never introduce these counters selectively in a timed arm.

Determine whether the scheduler share is large enough to pursue a new backend. A useful upper-bound experiment uses the *same source function* at different command counts and types with workload-state parity. Treat results as overhead estimates, not guaranteed recoverable CPU.

### Phase 2: Controlled incremental performance

Evaluate 1, 4, 16, 64, 256, and 2,000 commands per function, with 0%, 25%, 50%, 75%, and 100% safe contiguous fusion coverage and a fixed total command count. Include functions called directly, from ticks, and in nested chains; disable random ticks and natural spawns in controlled fixtures. Predeclare the exact subset before collecting confirmatory data.

Use within-JVM crossover where different resource namespaces can be given different compiled paths **without** changing the source work; otherwise use matched randomized JVM pairs and conservatively report noisy intervals. Scoreboard state, source-line count and successful command result must agree across arms.

Primary microbenchmark endpoint: **server-thread running CPU ns per exact executed command**. Secondary: queue actions, compilation wall time, active tick average/P95 under sustained load, and whole event completion where applicable. Do not conflate any two.

Estimate: (B−A) = command specialization; (C−B) = fused queue reduction; (D−C) = incremental scheduling replacement. Do **not** infer (D−C) merely from a C−A gain.

### Phase 3: Semantics gate for any D backend

Before performance testing D, compare to official unmodified vanilla 26.3 and same-stack compiler-off for at least: zero/low/dynamic command quotas, nested calls, returns and `return run`, `execute if/unless function`, `execute store result/success`, multi-context forks, result/exception callbacks, `/debug function` traces, interleaved optimized/unoptimized commands, reload publication/failure and modded command callbacks. Preserve the original callable function for fallback and rollback.

A single failing P0 semantic case disqualifies that alternative backend's performance claim. A region may be allowed only if its *specific* supported contexts pass these tests.

### Phase 4: Decision

Predeclare a 15% **incremental** improvement threshold for D relative to C on the targeted controlled scheduler-heavy workload, with the exact >=95% median interval entirely past the threshold and independent A/A control passing. Require at least one matched real application result, or conservatively describe D as a proof-of-mechanism only. Check compile/reload cost and expected break-even active invocations.

If D fails to add material gain beyond C, **do not build a general scheduler replacement**: return to selective command specialization, macro extraction, and other profiler-attributed operations where real workload gains have been demonstrated. Conversely, if D wins the controlled gate and passes all semantic tests, expand only those proven islands.

## Stop rule for unrelated research

No more free-form GC root-cause work or speculative pack discovery. Only investigate infrastructure failures that actually invalidate the experiment at hand. After the two 012 candidates are classified, execute this scheduler decomposition—starting with the queue/callback cost split—rather than extending the current fusion-workload series.
