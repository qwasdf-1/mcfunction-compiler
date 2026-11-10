# SCHED-ATTR-002: Official Vanilla vs Fabric API vs Compiler-Disabled Execution

**Date:** 2026-11-10  
**Status:** Completed *screening* experiment; **quiet-host gate failed in all six boots**. No production or scheduler-rewrite performance decision is authorized.

## Research question

The earlier [SCHED-ATTR-001](scheduler-attribution-SCHED-ATTR-001.md) experiment profiled three function workloads on Fabric with the compiler's optimizations disabled. Its JFR stacks exposed a real repeated trace-flag environment lookup in our injected scheduler hooks, but it could not distinguish vanilla scheduler time from overhead introduced by Fabric or the compiler.

This follow-up asks: how much native-command execution CPU time is observed when running **identical ordinary functions** with the original official Minecraft 26.3 server, with Fabric Loader + Fabric API, and with the same Fabric stack plus our compiler mod installed but optimizations disabled?

This is a **cross-mode execution-stack comparison**, not a direct experiment on a rewritten scheduler.

## Reproducible setup

- Runner: [`scripts/ci_native_cross_mode_attribution.py`](../../scripts/ci_native_cross_mode_attribution.py)
- Workflow: [`.github/workflows/research-java25.yml`](../../.github/workflows/research-java25.yml)
- Source benchmark commit: `5a8231773524de543ccecd1e4b3b06fc80333810` on branch `research/java25-dependency-bootstrap`.
- Completed Actions [run 42896055685](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/42896055685). Its artifact **`ci-native-cross-mode-attribution`** contains `results.json`, the Fabric installer log, **six dedicated server logs**, and one raw JFR diagnostic recording per stack.
- Runtime: Ubuntu 24.04 GitHub-hosted runner, Temurin Java 25.0.5, Minecraft 26.3, Fabric Loader 0.20.1, Fabric API 0.165.0+26.3, Fabric Installer 1.1.2.
- The modded arms use **standalone production server launchers** and the **remapped production compiler JAR**, *not* Gradle `runServer`. The Fabric arms use exactly the same Fabric API artifact; only the compiler JAR is added to the third arm.
- The official server JAR was located by `mc_harness.server_lifecycle.locate_official_server_jar` and checked against pinned SHA-256 `d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64`. Installer, Fabric API, launcher, and compiler JAR SHA-256 values are stored in the report.
- The two Fabric server logs show **42 loaded mods** for Fabric API alone and **43** when the `function_compiler` mod is installed. Official vanilla loads without Fabric. The compiler arm independently checks `functioncompiler status` for `wrapped=false` and explicitly sets all optimization and trace environment flags false.

### Matched function workloads

Each fixture is a 2,000-line, reload-parsed, non-macro `.mcfunction`. No custom commands are needed, so all three configurations can execute the **exact same source**:

| Family | Repeated line | Expected score |
|---|---|---|
| Scoreboard write | `scoreboard players add #x fc_sched 1` | +2,000 per call |
| True conditional | `execute if score #gate fc_sched matches 1 run scoreboard players add #x fc_sched 1` | +2,000 per call |
| False conditional | `execute if score #gate fc_sched matches 2 run scoreboard players add #x fc_sched 1` | Unchanged |

`#gate` is initialized to one. Each boot performs 300 warmup calls and 4,000 measured calls **per family**, testing exactly 8 million source lines per measurement window. Final scoreboard values are checked after each window. All 18 windows passed their exact-work checks.

### Measurement

The primary metric is **server-thread CPU time**, rather than RCON wall time. The harness locates the JVM's actual `Server thread` Linux task and measures its running CPU nanoseconds from `/proc/<pid>/task/<tid>/schedstat` immediately before and after the 4,000 measured calls. Divide the CPU time by 8 million processed source lines. This measures actual CPU time consumed on the server thread, but includes RCON work and background tick work during the measurement; it is not a perfect per-command microbenchmark.

RCON round-trip p50/p95 are retained as secondary metrics only. Idle thread CPU rate is separately reported for each boot. **No JFR runs during timing windows.** One separate JFR diagnostic for each environment is collected after the three windows on its first boot.

All boots run sequentially on the **same GitHub-hosted runner**, with mirrored mode order:

```text
vanilla → fabric → compiler → compiler → fabric → vanilla
```

Function-family order changes across boots to reduce systematic warmup/order effects. There are only **two boots per configuration**; this is explicitly *not* the project's 6–10+ pair confirmatory promotion protocol.

## Observed results

### Server-thread CPU cost (ns per processed source line)

| Native command family | Official vanilla | Fabric + API | Fabric + API + compiler off |
|---|---:|---:|---:|
| Scoreboard write | **165.436** | **171.462** | **208.696** |
| True conditional | **306.140** | **352.554** | **333.751** |
| False conditional | **149.577** | **158.154** | **151.284** |

Numbers are **medians of two per-boot CPU measurements**, not a confidence interval.

The individual observations are important:

| Family | Vanilla boot 1 / 2 | Fabric boot 1 / 2 | Compiler off boot 1 / 2 |
|---|---|---|---|
| Scoreboard | 160.701 / 170.172 | 164.764 / 178.160 | 220.913 / 196.478 |
| True conditional | 307.295 / 304.985 | 336.530 / 368.578 | 355.850 / 311.652 |
| False conditional | 138.148 / 161.006 | 141.966 / 174.341 | 173.409 / 129.158 |

### Descriptive differences — **not proven overhead percentages**

| Family | Fabric vs vanilla | Compiler-off vs Fabric | Compiler-off vs vanilla |
|---|---:|---:|---:|
| Scoreboard | +3.6% | **+21.7%** | +26.1% |
| True conditional | +15.2% | −5.3% | +9.0% |
| False conditional | +5.7% | −4.3% | +1.1% |

The scoreboard arm exhibits a larger CPU cost when the compiler mod is installed and disabled, with both observed compiler-off boots exceeding both Fabric-only boots. **This suggests a potential installed-Mixin/disabled-hook cost**, not a proven causal regression. The corresponding conditional arms do not have the same pattern; startup, JIT, cache state, instrumentation routing, background work, and host noise remain unresolved factors.

The vanilla native-function baseline shows that a 2,000-line scoreboard function consumes approximately **0.331 ms of server-thread CPU time per call** under this screening workload (165.436 ns × 2,000). That is a *workload-specific observed cost*, not an intrinsic lower bound for vanilla's scheduler or an estimate of scheduler-only time.

### Critical quality gate: host was noisy

The shared `mc_harness.host_gate` quiet-host rule considers a run noisy if the host's one-minute load average exceeds its CPU count. This runner had **2 logical CPUs**, and all six boots recorded a one-minute load average of **2.31–2.57**. Accordingly:

**The quiet-host precondition failed in 6/6 boots. The result is exploratory screening only; no speedup, regression, or architecture-promotion decision can legitimately be made from its percentages.**

This qualification is not optional. Recording that a function completed successfully and that the CPU clock worked is different from confirming that this is a controlled benchmark suitable for acceptance or promotion.

### JFR source-level diagnostic

The archived JVM flight recordings confirm the expected execution stack in **all three** configurations. The sample sizes are only around **135–150 server-thread execution samples per recording**, too few for precise per-layer CPU attribution. Representative frames are:

- Vanilla: `ExecutionContext.pushNewCommands`, `ContinuationTask.schedule`, `BuildContexts.execute`, `CommandQueueEntry.execute`, `ScoreboardCommand`, Brigadier context lookups.
- Fabric API: the same vanilla execution path, with `fabric-entity-events-v1` wrappers inside `CommandQueueEntry.execute` and `ContextChain.runExecutable`.
- Compiler disabled: those Fabric wrappers remain, and the compiler's own Mixins are installed even though the top-level wrapper and all optimization flags are off.

The Fabric API JFR stacks include `CommandQueueEntry.wrapMethod$...fabric-entity-events-v1$onExecute` in **129 of 150** server-thread samples; the compiler-off stacks include that frame in **143 of 147**. **Presence of a wrapper in a stack is not proof it consumed that proportion of CPU time**: these frames may enclose most command execution.

The recordings demonstrate concrete additional interception points but do **not** isolate queue work from context construction or mod overhead with production-grade precision.

## Interpretation

1. **Native vanilla does nontrivial general-purpose command work.** Queue scheduling, contexts, dispatch, and scoreboard operations appear throughout vanilla JFR stacks. The current experiment does not show that any of them are individually close to optimal.
2. **Fabric is not a free baseline.** Fabric API interposes on command execution through Mixin Extras wrappers, so a comparison using only a Fabric dev runtime cannot directly be called a measurement of vanilla scheduler cost.
3. **Our installed compiler may impose an overhead even when optimizations are off.** The scoreboard screening outcome is large enough to warrant a focused quiet-host test, but the two-boot sample and noisy gate prohibit a firm conclusion.
4. **The three-stack experiment is an empirical improvement over SCHED-ATTR-001**, because it uses identical vanilla commands, the production launcher in both Fabric arms, the same host, and direct server-thread CPU measurement. It does **not** eliminate the need for formal pairing and host-noise controls.
5. **Do not infer a benefit from rewriting the global scheduler.** Scheduler costs were not varied independently; direct lowering and context bypass remain competing hypotheses.

## Next falsifiable studies

**A. Quiet-host, paired disabled-hook overhead check.** Re-run with a real quiet-host precondition, 6+ counterbalanced pairs, fixed host/JVM settings, exact score parity, and no JFR in timing arms. Compare Fabric API-only vs compiler-off to test whether always-installed scheduler/debit Mixins cause meaningful overhead, including when tracing/metrics are disabled.

**B. Cost isolation.** Add selective, toggleable hook/dispatch paths in a research build, preserving an independent no-mod oracle. Measure `ExecutionContext` queue vs `BuildContexts` vs `ContextChain` and actual scoreboard lookup costs with server-thread CPU measurements and enough JFR samples to resolve them.

**C. Typed direct-lowering prototype.** Under the existing vanilla function scheduler, compile a small scoreboard-only IR into direct typed operations; compare to vanilla, Fabric-only, compiler-off, and existing fused interpretation. The goal is to quantify potential savings before considering global scheduler replacement.

## Decision

**SCHED-ATTR-002 is a successful implementation and correctness screen, but an inconclusive performance experiment due to host-noise gate failure and insufficient paired repetitions.** Do not promote a scheduler rewrite, or claim a confirmed compiler-off slowdown, on these results. Maintain this evidence to design the next controlled experiment.
