# SCHED-GC-006 — GC/JVM scheduling phase attribution (preregistration)

**Status:** Stage A implementation; no performance results have been collected or validated yet.
**Parent:** [SCHED-NOISE-005](scheduler-noise-calibration-SCHED-NOISE-005.md).
**Scope:** Java 25, Minecraft 26.3, pinned Fabric Loader/API, identical binary A/A only.

## Research question

Are the anomalous ~350 ms GC-worker CPU windows from SCHED-NOISE-005
associated with identifiable GC collection phases, heap changes, pauses,
or runnable-worker contention? Are the phases also visible on both
Fabric-only and compiler-installed/disabled stacks?

**This experiment cannot establish GC causation by observational correlation.**
No intervention, compiler optimization, scheduler replacement, or real A/B
effect is tested.

## Fixed protocol

- Reuse SCHED-NOISE-005's 10 same-binary A/A pairs, balanced labels,
  exact scoreboard checks, 6–18 qualification windows, two score windows,
  two conditional controls, and existing Linux/host telemetry.
- Keep all 20 fresh JVMs, all quality failures, all anomalous windows
  and the previous A/A screening thresholds unchanged.
- Add **opt-in** JVM unified logging using
  `-Xlog:gc*,safepoint=info:file=gc-phase.log:time,uptimemillis,level,tags`.
- Every command window is bracketed by Python epoch-clock readings;
  the underlying server-thread CPU measurement remains unchanged.
- Preserve *complete* per-boot JVM logs; parse phase labels, GC IDs,
  collection durations, event timestamps and heap before/after/capacity
  when exposed by G1 logging.
- Report GC-worker CPU and run-queue delay side by side with GC events.
  Do not subtract worker CPU or GC pause duration from command CPU.
- Store per-window raw and diagnostic results in
  `build/benchmarks/SCHED-GC-006/results.json`.

## Logging and clock limitations

Unified logging changes observation cost; results are **not numerically
interchangeable** with 005. A timestamp may mark phase *completion*
rather than entry, and full cycles may comprise several lines.
The current parser identifies overlapping recorded intervals and exposes
unclassified lines; it does **not** yet reconstruct complete GC cycles.
Python epoch time brackets more than the inner server-thread CPU interval.
System clock adjustments and log flush behavior may affect alignment.
These limitations prohibit inferring 'no GC' from an empty overlap list.

The experiment reuses Linux thread-name based CPU attribution, which
misses short-lived threads and has 15-character name truncation. Whole-JVM
process CPU remains an independent coarser counter.

## Outputs and stop rules

**Success for stage A:** All contract tests pass; all 20 server boots
finish; logs exist and have identifiable timestamps; scoreboard results
remain exact; every A/A boot is retained. The experiment may still fail
its original variance/quality gates, which would be a valid scientific result.

**Failure or missing log:** Preserve partial JSON and raw server logs,
mark telemetry unknown, and do not classify missing evidence as GC-quiet.
CI process success does not mean statistical qualification success.

The exploratory analysis may look for correlations between GC phase
activity, heap transitions, server-thread CPU and scheduler wait.
It must not remove 'high-GC' boots and then promote apparent compiler
gains.

## Deferred stage B: explicit GC-quiet A/A estimand

Stage B is *not implemented* in this change. It requires a separately
predeclared and independently testable **pre-window** qualification rule
that observes GC cycle state (including concurrent phases), a bounded
attempt cap, heap occupancy stability, and JIT activity. Reaching quiet
state is an outcome: retain the qualification failure rate. If GC starts
during a prequalified timed window, retain and separately classify the
observation. Post-window exclusions are not a substitute for a valid
prequalification design.

Separate reports must retain (1) GC-quiet steady-state server-thread
CPU, and (2) GC-inclusive whole-JVM CPU, elapsed latency and sustained
MSPT. No equivalence or significant speedup claim is authorized by an
A/A calibration alone.

## Follow-up after first instrumented data

Only after the phase source is established should we vary GC-worker count
or heap configuration. If the A/A noise distribution remains wider than
the intended small compiler effect, stop adding batches to the shared
GitHub host and move to dedicated CPU capacity.
