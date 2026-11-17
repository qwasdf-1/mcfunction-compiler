# SCHED-ATTR-024 — Real Vein Miner execution-task path census

**Status:** Preregistered on `research/sched-attr-024-entry-path-census`; **no native measurements accepted yet**. This is the *path-frequency stage* of a larger within-entry cost investigation. It is not a scheduler rewrite, a CPU-share estimate or a new production optimization.

## Existing evidence that constrains the question

- **SCHED-ARCH-013** showed fusion substantially reduces queue-boundary visits on a 2,000-line synthetic score fixture, but did not prove a large real-workload whole-event improvement.
- **SCHED-ARCH-014** tested a tightly guarded alternate direct function call implementation and found a **+4.3922 signed log-%** median CPU regression against fused C, with the exact 96.14% interval entirely positive. It applies only to the research no-callback call site, not ordinary `/function`.
- **SCHED-COMP-022** measured roughly 1.29–1.58 µs per typed ScoreAdd callback (0.11–0.13% of the native Vein Miner Server-thread CPU) in separate descriptive studies, not causal speedups.
- **SCHED-ATTR-023** measured **18.2242 s in dequeued `CommandQueueEntry.execute`** out of **18.9559 s total Server-thread CPU**, with a raw **182.4 ms / 0.96%** queue-minus-entry residual. The empty clock-pair control suggested ~321 ms of timer overhead at this high entry count. Therefore the residual is **unresolved relative to timer cost**, and none of the 96.14% inside entries may be assigned wholesale to the scheduler.

The next question is: **which task methods actually run and how frequently?** We need those counts before deciding which subpaths can be sampled or batch-timed without perturbing ~200,000 hot queue entries.

## Exact scoped diagnostic (first stage)

One Minecraft 26.3 / Java 25 Fabric server with *normal cached typed ScoreAdd* executes the publisher's **unchanged Vein Miner 5.3.0+26.3 ZIP**, fixed SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. The existing native player-bot mines the same **215-ore** workload and advances the known queue head by **1,952 steps**. Original source state, marker cleanup and final scoreboard work are exact gates. This is not a synthetic substitute.

Only `FC_SCHED_PATH_CENSUS=true` activates a research command, `fc_sched_path begin`/ `end`. The runner begins the scope after the nine-second idle tick-stability gate and ends it just after the exact ore work completes. Event RCON polling and the single final stop-command execution are within the counted window. Other post-event status checks are outside it. No Spark, JFR, per-callback clocks, function phase timers or ordinary callback counters are enabled; Linux `/proc` Server-thread CPU is recorded **only as a host/integrity scale**, not as per-path attribution.

Record five separate counters via exact method-entry hooks:

| Counter | Method entry | Meaning |
|---|---|---|
| `queue_entries` | `CommandQueueEntry.execute` | Total observed dequeued actions in the scoped interval |
| `build_contexts` | `BuildContexts.execute` | Modifier/context-construction task entries |
| `execute_command` | `ExecuteCommand.execute` | Built-in leaf command-action entries, not all custom executors |
| `call_function` | `CallFunction.execute` | Function invocation task entries, potentially followed by child actions |
| `continuation` | `ContinuationTask.execute` | Function continuation task entries |

Each hook is a static-false, counter-only no-op unless explicitly enabled and recording. There is **no stopwatch in any hot entry**. Method injections target the typed JVM descriptors, not synthetic erased bridges, where known; runtime Mixin application must still be verified by the server boot.

**Important interpretation:** The four named **method-entry counts are not automatically a disjoint partition of all queue entries.** A task may call another task, and vanilla has custom executor paths outside the named built-in tasks. The fraction `count / dequeued entries` is a call-density ratio **not a CPU percentage** and need not sum to 100%. Record counts and the aggregate without pretending the leftover is exclusively some category.

## Frozen acceptance / failure conditions

The diagnostic is accepted only if:
1. Publisher ZIP fingerprint, runtime/compiler activation, all **215 ore operations**, **1,952 queue steps**, and the same verified final world state pass the existing native event gates.
2. The pre-event idle tick-stability gate and native Server-thread CPU/host-quality gates pass; no cgroup throttling; actual event CPU running time is positive.
3. Exactly one `begin`/`end` session completes on the Minecraft Server thread, with recording off at the final status snapshot.
4. Total dequeued-entry count is at least **1,000** and method-entry counts are all nonnegative. The built-in `BuildContexts` and `ExecuteCommand` paths must each have at least one real invocation, to verify that their hooks actually participated. **Zero `CallFunction` or `ContinuationTask` calls is not automatically invalid**; it must be reported as an observation subject to runtime reach/coverage caveats.
5. There are no selective-macro, ordinary callback, JFR or Spark counters contaminating the census; the original raw native result and server logs are archived.

Any failure makes the study incomplete. No source-level claim is made from a missing or rejected event. One boot gives descriptive event counts only; no statistical interval or causal performance effect.

## Next decision *after* accepted counts, not before

Inspect the raw call densities rather than infer CPU from frequency alone:
- A frequent `BuildContexts`/leaf path becomes the first candidate for **sparsely sampled, separately overhead-controlled ThreadMXBean CPU timing**. Predeclare sampling schedule and cap total probes (target a few thousand per event rather than ~200,000), sample entry and exit at the **same** scope, and validate counter parity. The class method may contain nested work, so label timing inclusive.
- A relatively sparse `CallFunction` or continuation path could justify direct batched timing with a matched clock-read control, provided event reach and callback semantics are verified.
- Any expensive combined action must still be further decomposed into **Brigadier/context resolution versus Minecraft mutations** before attributing savings to the scheduler. Do not treat the unsupported remainder of tasks as a single optimization target.
- Separately, the additional installed-but-disabled Mixin overhead must be checked before considering retaining instrumentation in `main`; the census itself cannot establish it is free.

Only after this count stage passes should a **separate protocol and separate dataset** attempt narrower CPU measurements. Do not add a 30-server campaign, another direct scheduler backend or a blanket JVM/JFR sampling run in response to these descriptive counts.

## Implementation

`SchedulerPathCensus.java`, four typed task Mixins, one `CommandQueueEntry` entry Mixin, status/capture commands in `ProbeStatus`/`ProbeCommands`, `scripts/run_veinminer_profile.py --scheduler-path-census`, `scripts/ci_scheduler_entry_census.py`, and two sets of Java/Python contract tests. Dedicated research workflow: `.github/workflows/research-scheduler-entry-census.yml` (temporary PR trigger only for first validation, **restore manual-only after acceptance**). Raw artifacts under `build/benchmarks/SCHED-ATTR-024` and the original native event directory.

**Scientific stop rule:** If the method hooks do not resolve against the verified 26.3 jar, or the event fails, fix exact mapping/diagnostic correctness and explicitly preserve failed runs. Do not remove low/zero counts just to make a path look significant.
