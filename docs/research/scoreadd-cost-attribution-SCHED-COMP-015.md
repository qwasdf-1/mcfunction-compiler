# SCHED-COMP-015 — ScoreAdd callback overhead, objective lookup, and feedback cost

**Status:** Preregistered and implemented; no performance result before successful runtime and A/A gates.

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
