# SCHED-ARCH-014 — Restricted direct function-call scheduler versus fused C

**Status:** Prototype and protocol committed; no empirical performance result until CI completes. This is the first deliberately different *function scheduling/continuation* path relative to the existing vanilla queue, but it is **not** a replacement for the global `ExecutionContext` driver.

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
