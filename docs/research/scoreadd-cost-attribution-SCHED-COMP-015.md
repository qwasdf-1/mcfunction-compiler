# SCHED-COMP-015 — ScoreAdd callback overhead, objective lookup, and feedback cost

**Status:** **Completed; ten independent JVMs passed the A/A and host gates.** The controlled results identify substantial overhead in our per-command wrapper and repeated configuration checks, and a smaller objective-lookup benefit. See the authoritative outcome below.

## Why this study follows SCHED-ARCH-013/014

SCHED-ARCH-013 found typed ScoreAdd substantially slower than its native equivalent on a 2,000-command contiguous scoreboard fixture (+42.46 signed log-percent median) while fusion removed much of the typed-vs-typed queue cost. SCHED-ARCH-014's additional direct call scheduling bypass was slower than fusion by +4.3922 signed log-percent (~4.49% ordinary relative CPU), with valid control and strict **verified** 26.3 quota semantics. The next sensible hypothesis concerns the typed callback implementation, not more scheduler replacement.

Review of `ScoreAddCommand` reveals its hot path re-reads three flags through `ProbeConfiguration` / `System.getenv` before resolving an objective, accessing/updating a score, and constructing a `CommandResponseTracker`. That observation identifies **candidate work**, not proven wall-time attribution.

## Causal comparison matrix

All source functions are byte-identical (`scoreboard players add #x fc_sched 1` × N), every invocation occurs through the ordinary vanilla `/function` command, and **no fusion or replacement scheduling is active in any arm**.

| Arm | Namespace | Executed callback path | Question |
| --- | --- | --- | --- |
| A | `fc_attr_native` | Vanilla parsed Brigadier ScoreboardCommand, excluded from specialization | Reference |
| A' | `fc_attr_native_null` | Same vanilla callback, identical source | A/A placebo |
| B | `fc_attr_delegate` | ScoreAddCommand wrapper calling its captured original vanilla command | Cost of inserting our wrapper and configuration checks, without changing scoreboard logic |
| C | `fc_attr_typed` | Current typed ScoreAddCommand, uncached flag checks, ObjectiveArgument validation and response tracker | Incremental typed body versus B |
| D | `fc_attr_cached` | Same typed body but fixed research flag checks compiled into the callback | How much of C's cost is hot-path flag evaluation? |
| E | `fc_attr_fastobj` | D plus current-scoreboard objective-name lookup, falling back to the original writable-objective validator when missing or read-only | Incremental objective lookup/argument resolution overhead |

B's command is still the real original vanilla ScoreboardCommand callback, and C–E all retain identical score mutation, response tracking/feedback, native function quota accounting and command input.

**Critical scope boundary for D/E:** the cached-flag path activates only with `FC_SCORE_ADD_ATTRIBUTION=true` and explicit **fixed environment values** `FC_SCORE_ADD_PROTOTYPE=true`, `FC_SCORE_ADD_TIMING=false`, `FC_SCORE_ADD_METRICS=false`. It cannot silently replace ordinary runtime configuration that is dynamically reloaded. E is further restricted to the exact literal `fc_sched` objective and single literal fake-holder ADD form. E resolves the live current server scoreboard on every execution; it never caches an Objective object across objective deletion/recreation or reload. Missing/read-only objective handling delegates to `ObjectiveArgument.getWritableObjective`.

All other namespaces and commands stay on their existing paths; all optimization defaults remain unchanged.

## Stage A — one separate instrumented JVM

Opt-in `FC_SCORE_ADD_PHASE_TIMERS=true` instruments only `fc_attr_typed`, collecting total `System.nanoTime` spans over:

1. Source / writable objective resolution, including score-source lookup.
2. Score access / creation and actual scoreboard mutation.
3. `CommandResponseTracker` allocation, tracking and feedback dispatch.

For N=2000, run 32 exact `/function` invocations (64,000 original commands). Phase-sample count must equal 64,000, and all phase aggregates must be nonzero. Record samples and per-callback average times, **not** falsely claiming the spans are exclusive CPU or that they add cleanly to uninstrumented CPU. Sampling/timers are disabled during actual performance tests.

In the same separate diagnostic, prove the B/D/E intervention paths ran by reading `score_attr_delegate_calls`, `score_attr_cached_calls`, and `score_attr_fastobj_hits`; each must increase. Test current objective removal and recreation against native, pass-through, typed, cached and fast objective paths, and include a read-only `health` objective exercise. A failed diagnostic blocks timing. This does **not** substitute for the full production semantic matrix on dynamic config reload, custom sources, callbacks, or all scoreboard criteria.

## Stage B — controlled CPU crossover

Exactly **10 fresh independent Minecraft 26.3 / Java 25 JVM boots**, with all six arms installed together and **five** predeclared ABBA/BAAB contrasts per boot:

1. A vs A' (negative control)
2. A vs B (wrapper insertion and configuration-check cost)
3. B vs C (typed callback body beyond the wrapper)
4. C vs D (cached fixed configuration flag checks)
5. D vs E (live objective lookup shortcut)

Seed **15015**, five ABBA and five BAAB orientations per contrast, a five-position Latin-square rotation repeated twice (each contrast appears exactly twice in each block position). Same world, compiler jar, 2,000 source commands per function, native queue, ordinary `/function` entry and 220 calls per measured window. Each boot runs original validated stable-CPU qualification, then prewarms each arm for 120 calls.

Primary outcome: Linux server-thread **running CPU nanoseconds / exact source command**, not RCON wall-clock latency. For each block, calculate signed `100×[mean(ln(CPU/command)_B)−mean(ln(CPU/command)_A)]` across its two A and two B windows. Collapse all 20 timing windows **to one per-contrast observation per JVM**; report 10 boot-level log effects and conservative exact >=95% order-statistic median intervals (10 boots yields 97.85%). Do not drop any boots to make an effect significant.

Work-integrity gate: every timed window must produce 440,000 scoreboard increments. Verify compiler specialization counts in each function namespace (A/A'=0, all others=N), and fusion count=0 everywhere. Host gate: no cgroup CPU throttling in any window, available runqueue delay ≤25% and stable prewarm qualification. A/A median interval must contain zero. If either control fails, all substantive estimates are exploratory/invalid.

The 15 signed log-percent incremental improvement threshold is preregistered for E relative to D. Report smaller effects clearly and do not promote E as a production optimization without full reload and real-world checks. A sum of separated B/A + C/B log contrasts is exploratory, not an independently paired C/A test.

## Interpreting the result

- Large B/A slowdown → wrapper / configuration / callback overhead, not native scoreboard operation itself.
- Large C/B slowdown → typed body and response implementation more costly than native callback; A's native feedback behavior remains the benchmark.
- Large reduction D/C → hot-path getenv / config checks have a measurable cost under explicit frozen flags; this is **not** permission to freeze reconfigurable flags generally.
- Large reduction E/D → objective argument lookup potentially worth a guarded optimization. Missing and read-only objective parity are mandatory.
- Phase timers can suggest whether objective validation, score mutation or response tracking **within the existing typed callback** dominate, but cannot independently estimate true exclusive CPU fractions or establish causality of the response tracker. If feedback dominates, a *separate* semantics-preserving response optimization would be needed; skipping callbacks to manufacture gains is unacceptable.

If none of B/C/D/E yields a confirmed incremental benefit, return to profiling vanilla/compiled runtime paths using sampling instead of inventing scheduler shortcuts.

**Files:** `scripts/ci_scoreadd_attribution.py`, `tests/test_scoreadd_attribution.py`; workflow `.github/workflows/research-scoreadd-attribution.yml`; artifacts `build/benchmarks/SCHED-COMP-015/`. This is a research-only branch; no production configuration defaults changed.

## Completed results — SCHED-COMP-015 (November 13, 2026)

**Authoritative experiment run:** [GitHub Actions #43547629956](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43547629956). Raw artifact: [`sched-comp-015-scoreadd-cost-attribution`, ID 14094567277](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43547629956/artifacts/14094567277); `diagnostic.json`, `timing.json`, and 11 Minecraft server logs. All earlier build-failure attempts are superseded; their data are not pooled.

**Campaign integrity:** 10/10 independent timing JVM boots completed; exactly 5 ABBA/BAAB blocks per boot and 4 windows per block (**200 total timed windows**); **every window returned exactly 440,000 scoreboard additions**, all compilation activations were verified, and **no boot failed the host-quality gate**. The A/A median exact interval includes zero. The old inherited workflow step label says "12-JVM" but the actual `N_BOOTS` and frozen ten assignments in the artifacts are **10**, as preregistered.

| Predeclared contrast (B vs A) | Median signed log-% | Exact 97.8516%-coverage median interval (signed log-%) | Ordinary CPU change at median |
| --- | ---: | --- | ---: |
| Native placebo vs native | −0.2485 | [−3.5910, +1.0471] | −0.25% |
| Delegating wrapper vs native | **+36.3252** | **[+34.0761, +39.2114]** | **+43.80%** |
| Existing typed body vs delegating wrapper | **+5.4436** | **[+2.4343, +8.1339]** | **+5.59%** |
| Cached frozen flags vs existing typed body | **−52.0874** | **[−53.9816, −49.1217]** | **−40.60%** |
| Live fast objective lookup vs cached flags | **−5.2047** | **[−9.8653, −1.7431]** | **−5.07%** |

Positive = **slower** than the comparison's baseline; negative = **faster**. These estimates are from matched 10-JVM, within-JVM contrasts. The median of signed log percentages is transformed into ordinary percentage change as `100×(exp(median/100)−1)`. Exact intervals are for the population median *under the specific benchmark workload*, not expected game-wide improvements. The A/A interval includes zero despite one large placebo outlier (−13.08 signed log-%); no outlier was dropped.

**Predeclared E-vs-D 15 signed log-% materiality verdict:** `small_gain_supported_below_15logpercent_threshold`. The score objective shortcut is statistically distinguishable from no effect on this benchmark but **does not** meet our worthwhile incremental improvement requirement. Conversely, the frozen-flag experiment identifies a much larger hotspot, although the 15-log-% threshold was *not* preregistered as its formal production promotion gate.

### Diagnostic wall-time breakdown

One separate diagnostic JVM timed exactly 64,000 invocations of the **existing typed** callback with `System.nanoTime` around the three phases, yielding these averages:

| Instrumented phase | Wall nanoseconds / typed command |
| --- | ---: |
| Source and writable objective resolution | 162.97 ns |
| Score access / creation and scoreboard mutation | 429.24 ns |
| Response tracker allocation, tracking and feedback dispatch | 382.83 ns |

All three phase totals were nonzero and the sample count exactly matched the 64,000 expected commands. These are **instrumented wall-time spans**, affected by `System.nanoTime` and instrumentation, not separately sampled **server-thread CPU**; they cannot be treated as exclusive cost percentages or subtracted from the uninstrumented total.

Research-mode counters from the independent diagnostic: delegating callback calls **+8**, cached-fixed-flag calls **+20** (includes cached and fast-objective variants), fast-objective live-scoreboard hits **+4**. Thus no new performance arm is a silent fallback to the old path. The diagnostic removed and recreated `fc_sched`; all five meaningful paths returned **exactly 4** after recreation. It also invoked the paths with missing and `health` read-only objectives, but the harness did **not** assert matched error messages or no mutation in those negative cases; do not claim complete missing/read-only semantics based on this diagnostic alone. The code delegates failed live-name lookups and read-only objectives to the existing vanilla validation path.

### What we learned, and what we did not

1. **Wrapper + configuration checking, not scoreboard mutation alone, appears to be the dominant source of the typed prototype's slowdown.** Inserting a delegating wrapper that executes the captured vanilla command increased CPU by +36.33 signed log-%, even though the actual scoreboard command remained unchanged. This comparison includes the extra wrapper call, several configuration checks, and any related dispatch effects; it does *not* isolate every one of those costs independently.
2. The specialized typed body **also** adds measurable overhead over that delegating wrapper (+5.44 signed log-%), despite preserving game-state work. The measured wrapper and body effects broadly reconcile with the previous SCHED-ARCH-013 typed-vs-native slowdown; direct cross-study equality is not warranted because the instrumented builds differ.
3. **Freezing three explicitly overridden configuration flags** (prototype enabled, per-command timing off, execution metrics off) saves −52.09 signed log-% relative to the same typed body with hot-path flag evaluation. That corresponds to ~40.6% fewer CPU nanoseconds per exact scoreboard command on this case. The ordinary implementation currently calls `ProbeConfiguration` / `System.getenv` on the hot path. We must **not** naively freeze dynamically reloadable production configuration flags based on this best-case experimental override.
4. **Runtime objective resolution contributes, but much less:** the guarded current-scoreboard objective-name shortcut saved a further −5.20 signed log-% relative to cached flags. The cost of scoreboard access/mutation and feedback construction remains measurable and semantically necessary; we did not benchmark removing either.
5. Combining the *separate* log contrasts within each boot gives an **exploratory**, not directly randomized, E-versus-native median near **−14.01 signed log-%** (~**−13.1% ordinary CPU**) for this specific function. The five contrasts were run in different temporal blocks; this combined estimate is **not** a confirmatory optimized-versus-vanilla result. A new directly paired native-vs-optimized control, semantic differential, and a real-workload measurement are still required before any production-speedup claim.

### Next, and stop rule

**Do not promote either research implementation unchanged.** A legitimate follow-up is a production-semantics-preserving configuration accessor that caches immutable *environment overrides* once at process startup but evaluates dynamic `CompilerConfig` state on every call only when no override is supplied; verify configuration reload and tracer/callback/quota equivalence. Then compare that corrected typed path directly with native, with a valid negative control and at least one representative datapack. Only after this should any objective-lookup shortcut receive broader semantic tests or promotion.

No additional scheduler replacement experiment is justified by these findings: the study shows that avoidable callback and configuration machinery could dominate before scheduling itself becomes the binding constraint.
