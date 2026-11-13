# SCHED-ARCH-014 — Restricted direct function-call scheduler versus fused C

**Status:** **Completed; restricted D regressed versus fused C.** The corrected semantic gate and all twelve timing boots passed in CI run `43520441346`. This is a genuinely different *function scheduling/continuation* path relative to the existing vanilla queue, but it is **not** a replacement for the global `ExecutionContext` driver.

## Question

SCHED-ARCH-013 confirmed, on one literal scoreboard fixture, that C (fused typed) reduces the instrumented native queue-boundary count from 144,052 to 76 over 24 × 2000-command invocations, with 48,026 quota debits in both arms. Against typed ScoreAdd, fusion saved **−28.17 signed log-percent** server-thread CPU; typed ScoreAdd itself was **+42.46 signed log-percent** slower than native. 013 did **not** measure a D execution path.

The remaining narrowly isolatable question: with the **exact same per-command typed execution semantics** as C, how much overhead remains in (i) `CallFunction` creating its child frame, (ii) its continuation scheduling, and (iii) later entering one fused region through vanilla's queue?

## D architecture, exact constraints

Existing C compiles adjacent safe ScoreAdd actions into one `FusedRegionPrototype` region; the ordinary `CallFunction` action creates a child frame and queues that region via a continuation. D is a strict opt-in `CallFunctionMixin` HEAD fast path that, when it can prove a whole function is a safe straight-line island, charges **exactly one vanilla function-call quota debit** and runs the exact same `FusedRegionPrototype.executeCommand` bridge through a local program counter without creating the child frame or enqueueing its continuation. That bridge continues to handle every leaf's original quota debit, Brigadier execution, result callback, syntax error handling, and source feedback. All unrelated function calls, commands, nested control flow and queue work remain on vanilla's `ExecutionContext`.

Only functions explicitly allowlisted through **both** `FC_DIRECT_SCHEDULER_PROTOTYPE=true` and nonempty `FC_DIRECT_SCHEDULER_ONLY_NAMESPACE` are even considered. Then the *whole body* must be two or more identical literal `scoreboard players add #x fc_sched 1` commands, whose parsed executable is the actual `ScoreAddCommand` specialization and whose Brigadier context is non-forked. The function name must match `score_[0-9]+`. This is deliberately too restrictive for arbitrary user datapacks.

Each eligible D function retains its original plain-text command entries **and** a previously compiled, regular fused C representation; it behaves like C whenever the CallFunction context has any nonempty function-result callback, nonempty sender callback, `returnParentFrame=true`, non-null trace callbacks, incompatible sender type, or no quota. Functions with a `function`, `return`, `execute`, modded command, macros or any other command in the body cannot become D at all. This whitelist is an experimental semantic boundary, not a proof for arbitrary no-fork functions.

### Semantics caveat

The fast path uses the **caller's Frame**; this is only acceptable in the restricted mode because no child return, trace, or callback frame observation may be possible. If a test reveals any observable frame distinction even in this whitelist, the entire D fast path is disqualified. SCHED-ARCH-014 **must not be promoted** as a general replacement on the basis of a single benchmark result.

## Predeclared semantic gate, independent diagnostic JVM

Generate byte-identical `fc_arch_fused:score_N`, `fc_arch_fused:score_null_N`, and `fc_arch_direct:score_N` for `N ∈ {4,16,256,2000}`. Every command changes `#x fc_sched` by one. A fourth unsupported D-namespace function contains a nested `function` call and **must not** be direct compiled.

Before timing, confirm ScoreAdd compilation of all N commands, one fused region in all three arms, and a direct-compiled marker **only** for D. With `FC_DIRECT_SCHEDULER_DIAGNOSTICS=true` *only in this diagnostic JVM*, require at least one direct execution; if callbacks force every attempt to fallback, **do not run any D-vs-C timing**.

Compare C/D exact scoreboard work for all four function lengths. Sweep command-chain quotas **2,3,4,5,8,16,32,64,1024** for 16-command functions (quota zero cannot support the RCON reset/observation commands in the same scheme and is handled in the broader official vanilla parity suite). Verify nested caller continuations with a regular parent containing: increment; function call; increment. Verify unsupported D-namespace function uses C fallback; issue `/debug function` and require a recorded trace-related fallback. Record responses, counters, quota results, nested and debug evidence. If a semantic assertion fails, the entire study stops *before* timing.

These checks cover a **restricted subset** of the required global scheduler semantics. A general D would still require explicit fork, `return run`, custom callbacks, /debug trace equality, macro, reload and error-path parity before any promotion.

## Protocol amendment — empty-callback invocation site

The first CI diagnostic (run `43517938301`) **failed its required direct-activation gate**: the ordinary public `/function` command never invoked the direct path, because its callback context requires the vanilla frame. There was **no timed result** from that run. We did not weaken the callback guard.

The revised protocol adds an explicit research-only `fc_arch_call <function-id>` command, registered **only** when `FC_DIRECT_SCHEDULER_HARNESS=true`. It uses `ExecutionContext.queueInitialFunctionCall` with `CommandResultCallback.EMPTY` and a source with an empty callback, resembling a fire-and-forget tick/manager function call. This is the *same* invocation mechanism for the placebo fused C, control fused C, and direct D; only the already precompiled function's scheduling path differs. It does not change or override ordinary `/function` behavior or any production command.

The revised diagnostic explicitly checks that ordinary `/function` **does not** activate D and that the research no-callback invocation **does** activate D. Do not interpret any result as an optimization of public `/function`, which remains on fused fallback, or as a blanket tick-function performance improvement. The CI campaign after this amendment is an **independent new screen**; the first failed diagnostic is retained as an important applicability result.

## Semantic gate correction — actual Minecraft 26.3 command quota

A subsequent audit found that the previous diagnostic used `gamerule maxCommandChainLength`, which Minecraft Java 26.3 **does not recognize** (the current ID is `minecraft:max_command_sequence_length`). That command failure was not checked, so the reported quota=2–1024 parity actually used the unchanged default quota. The prior **"quota sweep passed" statement was invalid**. No D-path semantic approval or C/D CPU claim may rely on that run. The run's ordinary `/function` fallback, D activation, nested and debug evidence remain separate observations.

The corrected protocol invokes `gamerule minecraft:max_command_sequence_length N`, immediately queries the current value with `gamerule minecraft:max_command_sequence_length` and **requires exact numeric readback**. It also requires real truncation of the 16-command function under at least one quota ≤8, all C/D scoreboard results equal at each quota, and complete 16-command execution at quota=1024. The original gamerule is restored in a `finally` block. Any failed readback or missing truncation is a fatal diagnostic failure before timing. Regression unit tests cover an unknown gamerule, no-truncation bogus checks, and correct restoration.

This fix is a semantic validity correction; it does not change the actual direct or fused executors, benchmark effect threshold, sample count, or quality filters.

## Timing study

- Exactly **12 independent JVMs**, each compares two predeclared ABBA/BAAB crossover blocks: placebo **C versus byte-identical C'** and treatment **C versus D**, both within the same warmed Minecraft 26.3 Fabric JVM.
- Seed `14014`, six of each block order and six ABBA/BAAB orientations per comparison.
- Prewarm three identical source families 180 calls each, plus reuse existing bounded warmup qualification. Each measured window is **360 × 2,000 original commands**; 8 windows per JVM; all raw windows and boots retained.
- Same compiler JAR, vanilla dispatcher, scoreboard commands, server/world, JVM flags and command bodies. Distinction is only `fc_arch_direct` eligible for the direct-call path.
- **All** direct execution diagnostic counters, queue metrics, JFR, Spark and runtime trace are **off** during timed JVMs. Verify compilation activation but do not pay atomic recording costs in D. Exact scoreboard count and source work are hard gates every window.
- Primary outcome: **Linux Server thread running CPU ns / 2,000 exact scoreboard increments per function** (one boot-level signed `100 ln(D/C)`). 12 independent boot-level ratios, conservative exact >=95% median interval. RCON wall time is not a server CPU measurement.
- Quality: all qualification windows stable; no cgroup CPU throttling on any measured window; runqueue-delay fraction ≤25% for each window. A/C' placebo median interval must include zero. No post-hoc exclusions or reruns to chase significance.
- **Decision:** 15% *incremental signed log-percent* gain only if D/C exact upper interval ≤−15, under clean placebo and quality. If interval lower >0, report regression. If entirely above −15 report no material gain; otherwise inconclusive.
- No attribution from C/D gain to a whole-game improvement, and do not extrapolate to functions outside this narrow eligibility.

## Interpretation

The earlier 013 diagnostic showed that C has already eliminated almost all observed native queue-boundary visits for this fixture. Thus **a small or nonexistent additional D gain is plausible and scientifically useful**: it would argue that removing `CallFunction`'s last few scheduling operations is not worth maintaining an alternative scheduling implementation. A measurable D benefit would qualify only this straight-line function class and trigger a broader semantic differential campaign, not immediate general replacement.

**Files:** `src/main/java/dev/functioncompiler/DirectSchedulerPrototype.java`, `scripts/ci_direct_scheduler_crossover.py`, `tests/test_direct_scheduler_crossover.py`. **Workflow:** `.github/workflows/research-direct-scheduler.yml`. **Artifacts:** `build/benchmarks/SCHED-ARCH-014/{diagnostic,timing}.json`.

**Production defaults unchanged.** No feature flag is enabled without explicit environment variables and an exact namespace match.

## Completed outcome — SCHED-ARCH-014 (2026-11-13)

**Authoritative run:** [GitHub Actions #43520441346](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43520441346). Raw artifact `sched-arch-014-restricted-direct-call`, artifact ID `14083450300`, contains `diagnostic.json`, `timing.json`, and per-server logs. Prior interrupted and superseded runs are **not pooled**. The first "quota parity passed" diagnostic used an invalid old rule name; it was explicitly invalidated, corrected, and rerun. The decisive run validated *readback and actual truncation* in Minecraft 26.3.

### Corrected semantic diagnostic

- Exactly **160 actual D executions** in the separate diagnostic JVM, over four eligible lengths (4,16,256,2000).
- Ordinary public `/function`: **0 direct executions**, as required by result-callback safety; falls back to the original fused representation. Therefore the D/C outcome applies only to the research no-callback `fc_arch_call` invocation shape.
- `minecraft:max_command_sequence_length` command **set and read back** to 2,3,4,5,8,16,32,64,1024. For 16-line functions, both C and D executed exactly [0,1,2,3,6,14,16,16,16] commands respectively; explicit truncated execution at low quotas, full execution at high quota. These are real quota tests, not a synthetic re-labeling of unlimited execution.
- Nested parent function: C and D both produced **18** scoreboard increments; unsupported control-flow function produced **6**; `/debug function` generated a positive direct fallback delta (**1**). Source function lines byte-identical across all comparison arms.
- These tests are **not** proof of arbitrary fork, recursion, mod callback, reload or general return semantics for any generalized scheduler. D's strict compiler and call-site guard *exclude* such scenarios.

### CPU screening results

**12 complete independent fresh JVMs**, balanced crossover per the frozen design, both A/A and C/D contrasts inside every JVM; every timed window passed exact work/host-quality gates; **zero quality-failed boots**. The A/A placebo median interval includes zero. Retain all boots, including one placebo boot with +23.37 signed log percent (large within-run outlier); never drop it post-hoc.

| Predeclared contrast | Median signed log-percent (B/A) | Exact 96.14% median interval (signed log-percent) |
| --- | ---: | --- |
| Identical fused C' vs fused C (A/A) | −0.3224 | [−1.0999, +1.6216] |
| Direct D vs fused C | **+4.3922** | **[+0.7412, +9.0727]** |

Converted to **ordinary relative CPU** on the measured fixture, the D/C median is `exp(0.04392185)−1 ≈ +4.49%`, with exact interval approximately **+0.74% to +9.50%**. Positive means D is slower. Preregistered decision: **`direct_scheduler_regression_supported`** (CI report).

The regression is **not** proof that all direct scheduling or all future execution architectures regress. It says this *restricted child-frame bypass* adds cost or removes insufficient overhead to win against C on a long straight-line ScoreAdd function, using the same typed command bridge. CPU time attributed separately to scheduler internals remains unmeasured; do not claim a precise scheduling-time percentage.

### Decision and research relevance

**Do not promote D** or generalize its whitelist. Keep all production defaults unchanged, retain the prototype only as an opt-in negative research result or remove it after archival. More attempts to optimize this exact no-callback ScoreAdd island are not justified without a new profiler-attributed cost hypothesis.

SCHED-ARCH-013 already established that fused C dramatically reduced queue-boundary counts without reducing command quota debits, and the current test shows bypassing the residual `CallFunction` child frame did **not** improve this workload. Also, the earlier 013 native comparison was significantly faster than typed B (and C was still above native on a separately derived exploratory comparison), so even a C/D relative gain would not have been sufficient to demonstrate production value versus vanilla.

**Next research direction:** return to the original *end-to-end* objective with profiler-attributed command work: reduce overhead of typed `ScoreAddCommand` itself, verify a true benefit versus vanilla before adding architecture complexity, and prioritize selective macro optimizations already qualified on real datapacks. If an entirely new scheduler design is proposed later, require a *new* causal mechanism, narrowed semantic contract, and direct C/D plus vanilla comparison, rather than treating this result as an excuse for another unconstrained prototype.
