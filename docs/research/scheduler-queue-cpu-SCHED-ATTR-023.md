# SCHED-ATTR-023 — Server-thread CPU in the queue loop versus dequeued entries

**Status:** Research-only native diagnostic preregistered on `research/sched-attr-023-queue-exclusive-cpu`; no native measurements have been accepted. No scheduler rewrite, no optimizer default change.

## Why this study

Prior research distinguishes an unmeasured hypothesis from completed evidence:

- **SCHED-ARCH-013:** On one static 2,000-scoreboard-command fixture, fusion reduced observed native queue-boundary visits from 144,052 to 76 over 24 function invocations, while keeping 48,026 quota debits; incremental fusion relative to typed commands used less CPU. This did **not** measure what fraction of a real Vein Miner event is spent in exclusive scheduler work.
- **SCHED-ARCH-014:** The narrow direct `CallFunction` child-frame bypass **regressed** against fused C by a median **+4.3922 signed log-%** (about +4.49% ordinary CPU) on the only verified no-callback, straight-line island; exact 96.14% median interval entirely above zero. Ordinary public `/function` never activated direct D. This argues against repeating that restricted D architecture without a new mechanism.
- **SCHED-COMP-022**, [draft PR #2](https://github.com/qwasdf-1/mcfunction-compiler/pull/2), reported two separately booted ThreadMXBean per-typed-ScoreAdd CPU diagnostics around 1.29–1.58 µs per callback (~0.11–0.13% of whole native Server-thread CPU). These are *not* evidence that the rest of the CPU belongs to the scheduler.

**Question:** Within one *real* 215-operation Vein Miner event, how much Server-thread CPU is consumed inside the function-execution queue driver, and how much of that occurs **outside** each dispatched `CommandQueueEntry.execute` action? Can this distinguish queue-loop bookkeeping from all nested command execution before attempting any alternative scheduler?

## Measurement design

Three independent Java 25 / Minecraft 26.3 Fabric server boots, every arm using the same production cached ScoreAdd implementation, the exact publisher Vein Miner 5.3.0+26.3 ZIP (SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`), and one native player-bot 6×6×6 mining event. Must complete exactly **215 ore work operations** and **1,952 queue-head advances**, with exact ore/source/marker/run-state parity.

In each enabled arm, two nested timing boundaries are instrumented:

1. **Outer queue driver**: `ExecutionContext.runCommandQueue` from HEAD to RETURN.
2. **Inner dequeued action**: every `CommandQueueEntry.execute`, regardless of the command's implementation. These intervals include Brigadier, scoreboard, modifiers, and game/world operations run inside the queued action.

An explicit research-only `fc_sched_cpu begin` RCON command activates the capture **after** idle stability, just before the first mining packet. The matching `fc_sched_cpu end` command closes it **after** exact work completion and before reading final `/proc` Server-thread CPU time. The final stop command's own queue execution is included in both nested clocks and the `/proc` denominator; the initial begin command is outside the CPU window. This is deliberately a slightly wider diagnostic window than SCHED-COMP-022 and previous native-event timing. No RCON post-event status, datapack stats or final world probes are included.

Three independent arms, **in this order**:

- `plain` / probe `off`: identical research begin/end commands but no per-queue or per-entry clocks; uninstrumented CPU reference only.
- `empty_control` / `empty`: two adjacent `ThreadMXBean.getCurrentThreadCpuTime()` reads at the beginning of each outer queue and inner entry; real work then runs unchanged. Records a clock-pair floor and instrumentation exposure.
- `timed_queue` / `timed`: two clock reads *bracket* each entire queue and, nested within it, each dequeued action. Both intervals use the calling Server thread's CPU clock.

All modes retain the original `ExecutionContext`, `CommandQueueEntry`, quota debits, call frames, continuations, callbacks, selector semantics, and original world work. No JFR/Spark, per-command callback counters, phase timers or trace. The research `fc_sched_cpu` commands and clock session activate **only** with explicit environment opt-in. The Mixin handlers remain installed but immediately return in default OFF mode; this does not prove negligible installed-disabled hook overhead.

## Predeclared integrity and quality

- Exact publisher artifact, 215 work, 1,952 queue-head advances, four statically compiled shared ScoreAdd-family queue/drain commands, complete final world state, pre-event 9-second idle tick stability, and positive Server-thread Linux running CPU from the correct task.
- Every arm must pass existing host-quality constraints: no measured cgroup throttling, runqueue-wait fraction no more than 25%. No exclusion or restart once the first mining packet has been sent.
- One and only one completed begin/end measurement session in every arm, inactive at post-event status; no instrumented clock activity in plain; in enabled arms a supported, already-enabled `ThreadMXBean` CPU clock on the Minecraft Server thread.
- At least **20 outer queue invocations** and **100 inner executed actions** in each enabled arm. Both depths must close to zero; **any nested queue/entry execution rejects** the simple subtractive diagnostic (no double counting). The number of outer and inner calls in EMPTY and TIMED may differ by **no more than 25%** respectively. Reject more than **20% zero-delta** timed clock readings at either boundary.
- Reject an impossible timed hierarchy: inner sum greater than outer sum, or outer queue CPU greater than its own Linux Server-thread event CPU. Reject if the timed native Server-thread CPU total differs by more than **30%** from the independent plain CPU reference; this is a coarse instrumentation/host-variability screen, not a statistical regression test.
- Preserve all three raw native records, stdout/stderr, the final counters, clock support, host metrics and hashes, even on failure. Do not pool SCHED-COMP-021's rejected JFR traces or synthesize accepted data from previous experiments.

## Attribution and interpretation: **do not mislabel the residual**

Within the TIMED arm, define:

- `Q` = sum of CPU clock intervals in `runCommandQueue` (***inclusive***; includes game commands, world work, and all inner entry execution).
- `E` = sum of CPU clock intervals in `CommandQueueEntry.execute` (***inclusive*** of the dequeued action).
- `R = Q - E` = **raw instrumented queue-loop residual**: CPU observed in the outer driver but outside its timed entry bodies.

Report `Q / ServerCPU`, `E / ServerCPU`, `R / ServerCPU`, absolute nanoseconds and counts. Note that `R` also includes timer reads and Mixin/counter maintenance executed between the inner and outer boundaries, non-entry work, and any unexpected enclosure. It is **not an exact or guaranteed upper bound** on the avoidable cost of a replacement scheduler. `Q` is not exclusive scheduler CPU, since virtually all function-command gameplay work happens inside queue entries.

For sensitivity only, `C` = mean EMPTY control CPU between two adjacent clock reads at entry HEAD. Report `R_s = R - 2 C × N_entry` and its share, **retaining its sign even if negative**. This is **not** a mathematically calibrated estimator: two adjacent reads omit Mixin/aggregation work and may not represent the whole timer overhead; JIT and host state differ between JVM boots. Do not turn either residual into a strict hard Amdahl ceiling or a causal CPU saving.

**Decision:** If accepted and the raw residual is small against the full event (for example far below 15%), the *currently instrumented narrow queue driver* is unlikely to supply a 15% whole-event saving by itself; this does not exclude optimizations inside `BuildContexts`, Brigadier, `CallFunction`, macro expansion or world updates, which occur inside `E`. If `R` is substantial, first locate whether it comes from quota checks, deque management, tracer, or timer perturbation in a *new* narrower study before creating another D backend. One independent boot per arm gives no confidence interval or causal optimizer effect.

## Code and acceptance procedure

- `src/main/java/dev/functioncompiler/SchedulerQueueCpuProbe.java`: Server-thread-only OFF/EMPTY/TIMED matched clock/counter definitions.
- `src/main/java/dev/functioncompiler/mixin/ExecutionContextMixin.java`: outer queue HEAD/RETURN timer.
- `src/main/java/dev/functioncompiler/mixin/CommandQueueEntryMixin.java`: inner entry HEAD/RETURN timer, registered in mixin JSON.
- `src/main/java/dev/functioncompiler/ProbeCommands.java`: research-only event begin/end RCON commands.
- `src/main/java/dev/functioncompiler/ProbeStatus.java`: mode, clock readiness, nesting, samples and CPU totals in server status.
- `scripts/run_veinminer_profile.py`: exact 215-ore event with the expanded begin/end probe window.
- `scripts/ci_scheduler_queue_cpu.py`: independent three-arm driver and validity/interpretation.
- `tests/test_scheduler_queue_cpu_clock.py`, `tests/test_scheduler_queue_cpu.py`: standalone Java mode and synthetic quality-gate tests.
- `.github/workflows/research-scheduler-queue-cpu.yml`: isolated manual-only research workflow, with temporary PR-triggered validation before merge (remove trigger after initial execution).

**Stop rule:** Preserve actual failures. Do not loosen gates until an accepted result appears or redesign the instrumented method to handle the observed source-level problem, reporting the amendment explicitly. Do not promote a global scheduler rewrite or production default from this diagnostic.
