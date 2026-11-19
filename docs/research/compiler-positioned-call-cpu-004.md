# COMPILER-CPU-004 — positioned child-call cost screen

**Status:** Preregistered diagnostic on \`work/compiler-coverage\`; native run must pass before any CPU claim. This follows the accepted [COMPILER-EXEC-003](compiler-dynamic-execution-003.md) and [COMPILER-ACCEPTANCE-002](compiler-runtime-acceptance-002.md) studies. **No new optimizer, no production-default change, no general scheduler Mixin.**

## Why this particular target

The 26 \`execute positioned … run function vm:queue/enqueue_here\` entries in \`vm:queue/enqueue_faces\` and \`vm:queue/enqueue_diagonals\` each reached their original BuildContexts entry 216 times per native 6×6×6 event, **5,616 actual entry reaches**, while the compiler declined the terminal function executable at load/instantiation time. This is a **dynamic exposure count**, not 5,616 completed child functions or 5,616 redundant commands.

SCHED-ATTR-025 measured generic \`CallFunction.execute\` at a corrected ~0.166µs per call, **below the empty-clock measurement floor**; its general scheduler task metrics cannot reliably be multiplied to obtain target-specific CPU cost. SCHED-COMP-021's JFR CPUTimeSample diagnostic failed the predeclared lost-sample gate. Repeating either as though it already solved this narrower question would be misleading.

**Question:** Is the *specific* 26-site positioned-call path expensive in synchronous CPU spent before child work, or is almost all real event CPU spent on meaningful work elsewhere?

## Mechanistic boundaries and clock streams

Only opt in with \`FC_CPU004_NAMESPACE=vm\`, one of \`FC_CPU004_MODE=plain|empty|timed\`, and an explicit event-window RCON \`cpu004-start\`/\`cpu004-stop\`. Both are required; outside the window, the wrappers immediately delegate with no CPU clocks. The three streams are:

| Stream | Span actually bracketed | What it excludes |
| --- | --- | --- |
| \`positioned_entry\` | Original \`UnboundEntryAction.execute\` for exact \`execute positioned … run function vm:queue/enqueue_here\` lines of the two expansion functions | Later \`ExecuteCommand\`, \`CallFunction\` or queued child work outside the synchronous entry action |
| \`enqueue_call_setup\` | The original \`CallFunction.execute\` method only when its *target function ID* is \`vm:queue/enqueue_here\` | Parent positioning work and the later execution of the child function's queued commands; includes vanilla frame/queue setup, not just redundant bookkeeping |
| \`enqueue_body_leaf\` | An ordinary Brigadier terminal \`Command.run\` callback inside \`vm:queue/enqueue_here\` | Custom executors, callback dispatch outside the command, and deferred descendant work; **not total child-body CPU** |

These are separate method spans and should **not be added as a disjoint percentage breakdown**. In particular, a parent modifier stage can schedule work that runs in a later task, and \`CallFunction.execute\` normally schedules the child rather than running all its body inline. Attributing all of \`enqueue_here\` to the initial function call would be incorrect. The body-leaf stream is a *partial observed sample of real work*, not a complete denominator.

The existing \`CallFunctionMixin\` gains two opt-in HEAD/RETURN hooks for the named target; the existing \`FunctionBuilderMixin\` admits wrappers for the three named functions only under the diagnostic mode. No new Mixin class is installed. All original entries and command callbacks are delegated exactly once, including when timed; no function-control-flow, parser or scheduler optimization is enabled.

## Frozen native protocol and acceptance gates

- Original Vein Miner 5.3.0+26.3 publisher ZIP pinned by SHA-256 \`fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e\`; Fabric Minecraft 26.3/Java 25, a genuine survival-player 6×6×6 coal mining event, the existing native playerbot, no modified gameplay commands.
- Three **fresh, nonpaired JVM boots** in the fixed order **PLAIN → EMPTY → TIMED**. All use \`--compiler-mode wrapper\` (ScoreAdd/fusion/bytecode compiler off), \`--no-spark\`, no JFR and no other compiler counters, and \`--capture-server-thread-cpu\` for a separate whole-event Linux /proc schedstat denominator.
- Each 150-second-capped event must finish 215 ore operations, exactly 1,952 queue-head advances, \`vmr.run=0\`, no remaining source/ore/markers and exact identical native state across arms. A stable 9-second pre-event idle tick gate, 45-second bounded pre-mining forceload RCON timeout, valid Server-thread CPU clock/host-quality gate and no after-mining retry apply to every arm.
- All three modes count actual calls at their selected observation boundary. PLAIN **never reads the CPU clock**. EMPTY takes two adjacent \`ThreadMXBean.getCurrentThreadCpuTime()\` readings at every 16th call and then delegates. TIMED brackets the original action/method at exactly the same sampling ordinal.
- The \`positioned_entry\` stream must have **exactly 5,616 calls** in every arm. \`enqueue_call_setup\` and \`enqueue_body_leaf\` must both be nonempty and have identical exposure counts across the three arms; the parser rejects changed execution totals rather than inventing rate corrections. For EMPTY/TIMED, require \`floor(calls/16)\` valid nonnegative CPU samples per stream, at least **32** samples per stream, and zero missing/negative samples. These are hard data-quality gates.
- Data saved at \`build/benchmarks/COMPILER-CPU-004/results.json\`, plus three individual \`*-cpu004.log\` dumps, all runner stdout and startup records, archived by the native workflow. Synthetic parser tests assert conservation, clock floor flags, invalid runs and sign-preserving control subtraction.

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

## Decision gate

If the corrected positioned entry + immediate call-setup path is near the timer floor or a tiny fraction of the original event CPU, stop: do not pursue an \`execute positioned … run function\` lowering solely to remove it. If substantial, isolate whether the candidate removes *actual* redundant modifier/source construction and call setup; preserve fork cardinality, nested call and return semantics, quota, function arguments, tracing, and result callbacks. A separate uninstrumented paired causal experiment is mandatory before promotion. No three-arm descriptive result authorizes a production optimizer or a speedup claim.
