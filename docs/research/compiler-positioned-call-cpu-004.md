# COMPILER-CPU-004 — positioned child-call cost screen

**Status:** **Accepted descriptive native CPU-clock diagnostic (2026-11-18 EST / 2026-11-19 UTC)** on `work/compiler-coverage`. No causal optimization or complete child-body CPU claim. This follows the accepted [COMPILER-EXEC-003](compiler-dynamic-execution-003.md) and [COMPILER-ACCEPTANCE-002](compiler-runtime-acceptance-002.md) studies. **No new optimizer, no production-default change, no general scheduler Mixin.**

## Why this particular target

The 26 `execute positioned … run function vm:queue/enqueue_here` entries in `vm:queue/enqueue_faces` and `vm:queue/enqueue_diagonals` each reached their original BuildContexts entry 216 times per native 6×6×6 event, **5,616 actual entry reaches**, while the compiler declined the terminal function executable at load/instantiation time. This is a **dynamic exposure count**, not 5,616 completed child functions or 5,616 redundant commands.

SCHED-ATTR-025 measured generic `CallFunction.execute` at a corrected ~0.166µs per call, **below the empty-clock measurement floor**; its general scheduler task metrics cannot reliably be multiplied to obtain target-specific CPU cost. SCHED-COMP-021's JFR CPUTimeSample diagnostic failed the predeclared lost-sample gate. Repeating either as though it already solved this narrower question would be misleading.

**Question:** Is the *specific* 26-site positioned-call path expensive in synchronous CPU spent before child work, or is almost all real event CPU spent on meaningful work elsewhere?

## Mechanistic boundaries and clock streams

Only opt in with `FC_CPU004_NAMESPACE=vm`, one of `FC_CPU004_MODE=plain|empty|timed`, and an explicit event-window RCON `cpu004-start`/`cpu004-stop`. Both are required; outside the window, the wrappers immediately delegate with no CPU clocks. The three streams are:

| Stream | Span actually bracketed | What it excludes |
| --- | --- | --- |
| `positioned_entry` | Original `UnboundEntryAction.execute` for exact `execute positioned … run function vm:queue/enqueue_here` lines of the two expansion functions | Later `ExecuteCommand`, `CallFunction` or queued child work outside the synchronous entry action |
| `enqueue_call_setup` | The original `CallFunction.execute` method only when its *target function ID* is `vm:queue/enqueue_here` | Parent positioning work and the later execution of the child function's queued commands; includes vanilla frame/queue setup, not just redundant bookkeeping |
| `enqueue_body_leaf` | An ordinary Brigadier terminal `Command.run` callback inside `vm:queue/enqueue_here` | Custom executors, callback dispatch outside the command, and deferred descendant work; **not total child-body CPU** |

These are separate method spans and should **not be added as a disjoint percentage breakdown**. In particular, a parent modifier stage can schedule work that runs in a later task, and `CallFunction.execute` normally schedules the child rather than running all its body inline. Attributing all of `enqueue_here` to the initial function call would be incorrect. The body-leaf stream is a *partial observed sample of real work*, not a complete denominator.

The existing `CallFunctionMixin` gains two opt-in HEAD/RETURN hooks for the named target; the existing `FunctionBuilderMixin` admits wrappers for the three named functions only under the diagnostic mode. No new Mixin class is installed. All original entries and command callbacks are delegated exactly once, including when timed; no function-control-flow, parser or scheduler optimization is enabled.

## Frozen native protocol and acceptance gates

- Original Vein Miner 5.3.0+26.3 publisher ZIP pinned by SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`; Fabric Minecraft 26.3/Java 25, a genuine survival-player 6×6×6 coal mining event, the existing native playerbot, no modified gameplay commands.
- Three **fresh, nonpaired JVM boots** in the fixed order **PLAIN → EMPTY → TIMED**. All use `--compiler-mode wrapper` (ScoreAdd/fusion/bytecode compiler off), `--no-spark`, no JFR and no other compiler counters, and `--capture-server-thread-cpu` for a separate whole-event Linux /proc schedstat denominator.
- Each 150-second-capped event must finish 215 ore operations, exactly 1,952 queue-head advances, `vmr.run=0`, no remaining source/ore/markers and exact identical native state across arms. A stable 9-second pre-event idle tick gate, 45-second bounded pre-mining forceload RCON timeout, valid Server-thread CPU clock/host-quality gate and no after-mining retry apply to every arm.
- All three modes count actual calls at their selected observation boundary. PLAIN **never reads the CPU clock**. EMPTY takes two adjacent `ThreadMXBean.getCurrentThreadCpuTime()` readings at every 16th call and then delegates. TIMED brackets the original action/method at exactly the same sampling ordinal.
- The `positioned_entry` stream must have **exactly 5,616 calls** in every arm. `enqueue_call_setup` must be nonempty and `enqueue_body_leaf` must be recorded explicitly, including zero, with identical exposure counts across arms; the parser rejects changed execution totals rather than inventing rate corrections. For EMPTY/TIMED, require `floor(calls/16)` valid nonnegative CPU samples per stream, at least **32** samples for each *active* timed stream (zero ordinary body-leaf callbacks are explicitly unmeasured), and zero missing/negative samples. These are hard data-quality gates.
- Data saved at `build/benchmarks/COMPILER-CPU-004/results.json`, plus three individual `*-cpu004.log` dumps, all runner stdout and startup records, archived by the native workflow. Synthetic parser tests assert conservation, clock floor flags, invalid runs and sign-preserving control subtraction.

For stream \(s\), report

\[
\Delta_s = \frac{\text{TIMED clock ns}_s}{\text{TIMED samples}_s}
 - \frac{\text{EMPTY clock ns}_s}{\text{EMPTY samples}_s}
\]

and the **descriptive signed projection**

\[
P_s = \frac{\Delta_s \times \text{TIMED calls}_s}
               {\text{TIMED event Server-thread CPU ns}}.
\]

The empty clock correction is an attempt to screen out clock-read overhead, **not** a proven exact counterfactual on the same JVM. Clock-floor or negative corrections should be reported directly, never clamped into a positive speedup. An observed span containing necessary original work is at best an *inclusive cost sensitivity*, not all CPU the compiler could remove.

## Accepted native result and source-backed interpretation

The [original three-arm Actions run #44450681503](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44450681503) passed the Java 25/Fabric build, nine synthetic Python clock-contract tests, source ZIP hash, all **three** independent genuine Minecraft events, pre-event idle/host CPU gates, exact full native state parity, 215 completed ore operations and 1,952 queue-head increments. All streams reported zero negative clock intervals, and the two active stream sample counts were **351** each in EMPTY and TIMED. [Raw 14,762-byte artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44450681503/artifacts/14495582424) includes `results.json`, all per-arm sparse-timing logs and runner logs; the Gradle dependency cache was excluded from the archive after a prior failed attempt accidentally included it.

| Stream | Calls per arm | Empty mean | Timed mean | Signed corrected per call | Descriptive projection, TIMED Server CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| `positioned_entry` | 5,616 | 1,412.52 ns | 4,673.76 ns | **3,261.25 ns** | **18.315 ms; 0.14214%** |
| `enqueue_call_setup` | 5,616 | 580.95 ns | 832.03 ns | **251.08 ns** | **1.410 ms; 0.01094%** |
| `enqueue_body_leaf` | 0 observed | n/a | n/a | **Unmeasured** | **Not estimable** |

Whole-event Linux Server-thread running CPU was **12.641 s PLAIN**, **13.192 s EMPTY**, and **12.885 s TIMED**. These are three **independent and nonpaired JVMs**. Differences between their whole-event CPU totals are not a treatment effect. The TIMED denominator (12,885,453,156 ns) is used only to place the sparse-clock projection in approximate context.

The direct call-setup subtraction of ~0.251µs is **below the 0.581µs empty-clock measurement floor**. It is not a precise per-call CPU estimate or a hard upper bound. The positioned-entry subtraction is greater than its empty-clock pair mean, but its entire synchronous action includes necessary vanilla work and is not proven removable. **Do not add the percentages as a reliable disjoint total**, and neither is a measured CPU saving.

### Why no leaf callbacks were observed in `enqueue_here`

The original publisher ZIP was inspected by SHA-verified workflow before the three events. The actual file `data/vm/function/queue/enqueue_here.mcfunction` contains exactly one command:

```mcfunction
function vm:queue/enqueue_match with entity @s data
```

This is a **custom function executor**, not an ordinary Brigadier terminal callback. Hence zero `enqueue_body_leaf` observations are the correct boundary-specific outcome; **not** evidence that the child function does nothing. The actual block matching, queue checks and mutation are further downstream in `vm:queue/enqueue_match` and descendants. Those costs and the separate asynchronous `ExecuteCommand` execution/modifier phase are **outside the direct timer spans measured here**.

### Decision

This screen does **not** support prioritizing a compiler transformation that only removes synchronous parent entry setup or immediate `CallFunction` frame setup. Their measured inclusive spans are small relative to the 12.885 s native event, and some work is mandatory anyway. It does **not** eliminate the possibility of a useful *larger* lowering because `ExecuteCommand` modifier evaluation and `enqueue_match` work were not timed by this experiment. Any further experiment should first use the exact pinned `enqueue_match` source to define a narrowly attributable command-site or downstream macro/mutation CPU stream; do not revert to general scheduler replacement, or use the zero leaf-callback row as a body CPU estimate.

## Decision gate

If the corrected positioned entry + immediate call-setup path is near the timer floor or a tiny fraction of the original event CPU, stop: do not pursue an `execute positioned … run function` lowering solely to remove it. If substantial, isolate whether the candidate removes *actual* redundant modifier/source construction and call setup; preserve fork cardinality, nested call and return semantics, quota, function arguments, tracing, and result callbacks. A separate uninstrumented paired causal experiment is mandatory before promotion. No three-arm descriptive result authorizes a production optimizer or a speedup claim.
