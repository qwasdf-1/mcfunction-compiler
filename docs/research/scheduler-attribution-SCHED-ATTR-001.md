# SCHED-ATTR-001: Minecraft 26.3 scheduler and command-execution cost screening

**Status:** completed *screening* experiment, 2026-11-10. **Not** a compiler-promotion decision or an exact vanilla CPU-time decomposition.

## Research question

How much of a Minecraft 26.3 function's execution cost comes from queue scheduling, context-building and Brigadier dispatch, underlying game operations, and the compiler/Fabric interoperability hooks? Before replacing vanilla's scheduler, can we identify which parts actually dominate the workload?

## Source and reproducibility

- Runner: [`scripts/ci_scheduler_attribution.py`](../../scripts/ci_scheduler_attribution.py).
- Minimal opt-in command and exact-work counter: [`ProbeCommands.java`](../../src/main/java/dev/functioncompiler/ProbeCommands.java), registered only with `FC_SCHEDULER_RESEARCH=true`.
- Queue trace injection: [`ExecutionContextMixin.java`](../../src/main/java/dev/functioncompiler/mixin/ExecutionContextMixin.java); trace flag cache: [`ProbeConfiguration.java`](../../src/main/java/dev/functioncompiler/ProbeConfiguration.java).
- Baseline raw [JFR + JSON](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/42887087889), compiler revision `18cddcf5`.
- Cached-flag raw [JFR + JSON](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/42888533071), compiler revision `bb10467d`.
- Both are GitHub-hosted **Ubuntu 24.04**, **Temurin Java 25**, **Minecraft 26.3**, Fabric Loader `0.20.1`, Fabric API `0.165.0+26.3`; Gradle build and full 110-test Python suite passed in both.
- The artifacts have finite GitHub Actions retention. Re-run the workflow using the pinned sibling `mc-tooling` checkout to regenerate the recordings.

### Declared workload

Each function contains **2,000 identical commands**. One Fabric dedicated server per run, six roughly six-second JFR windows in the order `noop → score → conditional → conditional → score → noop`. Before each window, execute 80 warmup calls. Exact work counters are checked in every window.

| Arm | Repeated command | What it approximates |
|---|---|---|
| `noop` | `fc_research_noop` | Minimal Brigadier leaf; it increments a primitive counter for integrity |
| `score` | `scoreboard players add #x fc_sched 1` | Typical native scoreboard write |
| `conditional` | `execute if score #gate fc_sched matches 1 run fc_research_noop` | Conditional `execute` context plus the minimal leaf |

The environment disables `FC_WRAPPER_PROBE`, `FC_SCORE_ADD_PROTOTYPE`, `FC_FUSED_REGION_PROTOTYPE`, `FC_BYTECODE_REGION_PROTOTYPE`, and `FC_SELECTIVE_MACRO_ARGUMENTS`. Importantly, the compiler's Mixin hooks **remain installed**, and Fabric API is present. Thus this is **not** a mod-free vanilla baseline.

JFR records `jdk.ExecutionSample`; classification filters `Server thread` stacks containing `ExecutionContext.runCommandQueue`. Layers are assigned using the **nearest recognizable** source frame, with explicit separate buckets for the compiler tracing hook and Fabric event hooks. This heuristic is not an exact time accounting. JFR profiles JVM sampled CPU stacks, not event elapsed time.

## Initial profiling failure and instrumentation discovery

The first successfully executed run reported zero scheduler samples. Its classifier had two defects: the JFR CLI defaults to printing only five frames, so the enclosing queue frame was often omitted, and class names in the JFR file used `/` separators rather than dotted Java names. Both were corrected (request `--stack-depth 96`, normalize `/` to `.`). The original raw recordings were intact and were reanalyzed with the corrected method.

The reanalysis revealed an unexpected hot path: `ExecutionContextMixin` checks whether runtime tracing is enabled at queue boundaries and on command-quota debits. `ProbeRuntimeTrace.enabled()` called `ProbeConfiguration.traceEnabled()`, which performed `System.getenv("FC_RUNTIME_TRACE")` on every check, **even with tracing disabled**.

The source of the samples was confirmed by full JFR stacks containing:

```text
java.lang.ProcessEnvironment$StringEnvironment.get
java.lang.System.getenv
dev.functioncompiler.ProbeConfiguration.readBoolean
dev.functioncompiler.ProbeConfiguration.traceEnabled
dev.functioncompiler.ProbeRuntimeTrace.enabled
net.minecraft.commands.execution.ExecutionContext.handler$...traceQueueBoundary
net.minecraft.commands.execution.ExecutionContext.runCommandQueue
```

The quota-debit trace hook has an analogous stack.

**Approximate proportion of sampled queue CPU stacks involving this compiler environment lookup before the fix:**

| Workload | Probe environment lookup share |
|---|---:|
| Minimal leaf | 49.2% (419 / 852) |
| Scoreboard addition | 38.0% (352 / 927) |
| Conditional `execute` | 48.9% (436 / 891) |

These are JFR **sample fractions**, not exact fractions of elapsed time. They describe our *instrumented Fabric process* and should never be presented as costs of vanilla's scheduler.

The research branch now caches the immutable environment flag once via `private static final boolean TRACE_ENABLED` and uses the cached value in `traceEnabled()`. No runtime user configuration is changed; the process environment is not designed to be altered after Java starts.

## Before/after screening

Median of the two **within-run window medians** for each workload. Values below are RCON function **round-trip** latencies. They include command transport and are not CPU-exclusive timings. The before and after trials ran on different CI hosts, without counterbalanced interleaving between revisions; improvement percentages are descriptive, **not causal proof** or promotion evidence.

| 2,000-command workload | Original tracing flag | Cached tracing flag | Observed change |
|---|---:|---:|---:|
| Minimal leaf | 0.4168 ms | 0.2723 ms | −34.7% |
| Scoreboard addition | 0.5226 ms | 0.4020 ms | −23.1% |
| Conditional `execute` | 0.6458 ms | 0.4866 ms | −24.7% |

All twelve windows completed their verified workloads; each measured arm executed millions of commands. No instrumentation counter was enabled in the timing arms beyond the minimal leaf's integrity increment.

## Initial after-fix JFR layer attribution (one runner)

Pooled per-arm samples from the two after-fix JFR windows (753 minimal-leaf samples, 857 scoreboard samples, 916 conditional samples). Percentages are **sampling-based screening classifications**, not exact scheduler percentages. Categories are mutually exclusive as assigned by the classifier.

| Closest recognized layer | Minimal leaf | Scoreboard | Conditional |
|---|---:|---:|---:|
| Scheduler / function queue | 29.5% | 16.9% | 21.7% |
| Context building / leaf dispatch | 25.1% | 18.7% | 25.3% |
| Brigadier | 21.5% | 31.4% | 34.0% |
| Fabric entity-event hooks | 23.5% | 20.8% | 19.0% |
| Scoreboard operations | 0% | 12.3% | 0% |
| Compiler environment lookup | 0.4% | 0% | 0% |

**Interpretation:** Eliminating just our own disabled tracing lookup removes a large source of sampled work. Afterward, command-queue scheduling, context/leaf dispatch, and Brigadier processing remain substantial on these *specific cheap-command workloads*. The Fabric entity-event hooks also consume noticeable sampled work. No single JVM layer explains all of it, and a rewrite of the scheduler alone would leave substantial dispatch/context work intact.

The minimal-leaf fixture intentionally has little native command work, making its overhead proportions unrepresentative of all real datapacks. Heavy NBT, selectors, world edits, and macro extraction could have very different profiles.

### Independent rerun on a new CI host — reproducibility warning

GitHub Actions [run 42889815692](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/42889815692), compiler revision `58dbb8c8`, re-executed the **same Java production code and benchmark runner**. Only a five-case profiler unit test and the research documentation had changed. The Gradle build, **115 tests**, two server smoke arms, and all six profiled benchmark windows passed. Yet the observed latencies and JFR sample proportions were materially different:

| Workload | First after-fix runner (42888533071) | Repeated after-fix runner (42889815692) |
|---|---:|---:|
| Minimal leaf RCON median | 0.2723 ms | 0.1910 ms |
| Scoreboard RCON median | 0.4020 ms | 0.2637 ms |
| Conditional RCON median | 0.4866 ms | 0.3368 ms |
| Minimal leaf sampled Fabric hook share | 23.5% | 54.0% |
| Minimal leaf sampled scheduler share | 29.5% | 19.6% |
| Scoreboard sampled Fabric hook share | 20.8% | 47.9% |

This is a **large reproducibility failure for exact timing and attribution** across GitHub-hosted runners. The relative ordering of the three workload families remains the same, but we cannot confidently attribute an end-to-end percentage gain to the cached trace flag *or* use the JFR percentages as a reliable Amdahl-law bound for rewriting the vanilla scheduler. Runner allocation, host CPU contention, JVM tiered compilation/inlining, and sample-classification sensitivity have not been controlled or separated.

The qualitative observation from the **original full stack traces** remains strong: a specific repeated disabled trace-flag environment lookup was present in the command hot path, and the cached implementation no longer incurs that lookup each command. The magnitude of its runtime impact remains open until a properly controlled same-host paired campaign.


## Important limitations

1. **No mod-free vanilla baseline:** This execution stack includes Fabric API and the compiler's default-off Mixins. Their time must not be mislabeled vanilla time.
2. **JFR CPU samples are estimates:** Java inlining, stack classification, sampling variance, garbage collection and interpreter/JIT transitions can shift shares. A second after-fix run showed substantial changes in category proportions with identical profiler code. Around 350–470 queue samples per window is useful for screening but not for a precise percentage claim.
3. **RCON round trips are not CPU timers:** No network overhead was subtracted. A run-to-run percentage change in RCON time cannot be reported as a Minecraft CPU improvement.
4. **Different hosts, not randomized A/B:** The cached-flag change is strongly mechanistically supported by the stack evidence, but the magnitude of an end-to-end speedup is still unconfirmed. Indeed, an after-fix repeat on another CI host produced a roughly 30% faster round trip with **no** runtime implementation change.
5. **No full callback/quota parity proof for the new command:** The counter establishes exactly completed benchmark work only. Production changes should go through the project's full behavioral test matrix.
6. **The effect of optimizing the scheduler alone is not isolated:** The nearest-owner method partitions stack samples but does not establish an Amdahl-law bound on a hypothetical new scheduler.

## Research conclusions and next tests

- **Confirmed source-level issue:** `FC_RUNTIME_TRACE` was read via `System.getenv` in the hot queue/debit hooks even with tracing off. It is a valid optimization target independent of any general compiler architecture.
- **Measured screening result:** Both cached-flag runs have shorter RCON function round trips than the original run across all three fixtures, and JFR confirms removal of the hot lookup. But variation between *unchanged* cached-flag runners is itself approximately 30%; no precise causal speedup claim is warranted.
- **Open architectural question:** Neither the pre-fix nor post-fix comparison proves that vanilla's scheduler is optimal, or that replacing it would be profitable.

**Next falsifiable tests:**

1. Run matched native-scoreboard and conditional functions on the official **mod-free** 26.3 dedicated server, then on Fabric without compiler optimization, and the compiler mod with instrumentation disabled. This will separate vanilla infrastructure from mod hooks.
2. Collect a randomized, paired comparison of trace-flag caching with JFR/counters **off on timing arms**, use JFR only for separate activation diagnostics, and report absolute baseline CPU time and variance.
3. Prototype **direct typed leaf execution** that bypasses Brigadier per-command context and scoreboard lookup, while retaining vanilla quota/frame behavior. Compare against the current queue and existing fusion to decide whether semantic whole-region compilation is more promising than global scheduler replacement.

**Decision:** Do not undertake a global scheduler rewrite on this evidence. Investigate a deeper compiler IR/direct-lowering backend, and establish a mod-free baseline first.
