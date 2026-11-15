# SCHED-HOOK-004 — Stability-first paired compiler-off CPU study

**Performed:** 2026-11-12  
**Status:** Complete, **inconclusive performance verdict** under the predeclared gate.  
**Core finding:** Within-JVM scoreboard measurements became substantially more repeatable, but between-JVM CPU costs remain highly variable. Larger observed compiler-off slowdowns coincide with increased server-thread scheduling delay and, in two cases, failure to reach a warmup plateau. A reproducible installed-compiler penalty has **not** been established.

## Research question

[SCHED-HOOK-003](scheduler-hook-overhead-SCHED-HOOK-003.md) compared Fabric API alone against Fabric API with the function compiler installed but every optimization disabled. It observed a median paired score difference of +1.46% (conservative exact 97.85% interval −1.94% to +8.61%), but the host-noise/stability gate failed in every pair. Crucially, repeated scoreboard windows in the same JVM differed by a median ~16.6%; 18 of 20 second windows were faster. This could reflect incomplete JVM warmup, the intervening conditional workloads, host contention, or several effects.

The new experiment targets that instability first: **can each fresh JVM reach a reproducible scoreboard execution plateau, and after doing so does adding the disabled compiler still produce a material CPU penalty?**

## Protocol and frozen preregistration

Implementation: [`scripts/ci_compiler_off_stability.py`](../../scripts/ci_compiler_off_stability.py).  
Contract tests: [`tests/test_compiler_off_stability.py`](../../tests/test_compiler_off_stability.py).  
Independent Actions workflow: [`.github/workflows/research-hook-stability.yml`](../../.github/workflows/research-hook-stability.yml).  
**Predeclared code/protocol commit:** `cac46f31d791cd476390d60181a878335bb4eecd`.  
**Successful measurement run:** [GitHub Actions 43268543737](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43268543737). Artifact `sched-hook-004-stability-first-raw` contains full `results.json` and all 20 server logs. GitHub Actions artifacts have finite retention; save the ZIP if long-term reproducibility is required.

Identical production Minecraft **26.3**, Fabric Loader **0.20.1**, Fabric API **0.165.0+26.3**, JDK **25**, and production server launcher/JVM parameters on both modes. Artifact SHA-256 hashes are retained in the machine-readable report. The only mod difference within a pair is the `function_compiler` JAR. The compiler wrapper, ScoreAdd, fusion, bytecode emission, selective macros, tracing, callback metrics, and function-timing options are disabled by explicit environment flags. Status checks reject an unexpectedly enabled wrapper.

| Design element | Predeclared rule |
|---|---|
| Pair structure | Ten adjacent Fabric-only vs compiler-installed/off pairs, 20 fresh JVMs |
| Order | Five mirrored ABBA/BAAB four-boot blocks |
| Native workload | 2,000 repeated commands per function, using the same generated datapack in every boot |
| Preliminary warmup | 800 calls each of true-conditional, false-conditional, and scoreboard functions |
| Scoreboard qualification | 1,000 calls per fixed CPU window; **at least 6, at most 18** windows |
| Stability test | Last four CPU windows each within **6%** of their median, and first-to-last trend at most **4%** |
| Timed scoreboard | Two **adjacent** 1,600-call windows (no conditionals in between) |
| Timed controls | 800 calls each of true and false `execute if score` after scoreboard windows |
| Within-boot stability gate | Timed scoreboard early/late difference at most **8%** |
| Primary cost | Actual server-thread CPU nanoseconds per source line from Linux `schedstat` |
| Primary effect | Compiler-off vs Fabric-only *paired percentage difference*; retain all 10 pairs |
| Confidence interval | Conservative exact 97.85% order-stat interval for paired-median effect |
| Decision threshold | An entire interval above **+5%** with all quality gates passing establishes material regression |
| Direct contention gate | Both score windows’ run-queue wait fractions at most **25%**; pair difference at most **10 percentage points** |
| Additional quality gates | Zero cgroup CPU throttles; pair load-average difference ≤1.0; every boot must qualify |
| Profiling | No JFR in timed windows; historical load-average-over-CPU-count rule retained as a diagnostic only |

This **redefines** the quality criterion relative to SCHED-HOOK-003. The old one-minute load average above CPU count could be raised by our own sequential server boots. This fresh protocol uses *direct server-thread wait and throttling* to assess contention, while still reporting that legacy gate. It must not be retroactively applied to earlier experiments.

Every warmup, qualification, and timed window checks exact scoreboard state. **No boots, pairs, or anomalous measurements were excluded** after inspecting their results. If a JVM fails warmup qualification, it still executes and records timed windows, but its pair fails the predeclared quality gate.

## Work completed

- 20 fresh server boots; 10 intact adjacent pairs.
- **80 timed windows / 192,000,000 timed source-line executions**.
- **209 qualification windows / 418,000,000 qualification source-line executions**.
- **96,000,000 preliminary warmup source-line executions**.
- All expected scoreboard states verified. Total: **706,000,000 checked source-line executions**.
- The Java 25 production build and 11 new statistical/protocol unit tests passed.
- No cgroup CPU-throttling events in measured windows.

## Primary results

| Metric | Observation |
|---|---:|
| **Median paired compiler-off CPU difference** | **+3.823%** |
| **Exact 97.85% median interval** | **−1.051% to +27.297%** |
| Median Fabric-only server CPU | 212.221 ns/source line |
| Median compiler-off server CPU | 219.675 ns/source line |
| Pairs passing all *predeclared* quality gates | **8/10** |
| Boots reaching fixed warmup plateau | **18/20** |
| Median within-JVM timed scoreboard early/late drift | **1.269%** |
| Formal decision | `inconclusive_quality_gate` |

The interval includes zero and a material positive regression. It establishes **neither** a >5% penalty **nor** equivalence within ±5%. Two pairs failed the quality gate.

### All ten paired differences

Positive means compiler installed with all optimizations disabled consumed more server-thread CPU than Fabric alone.

| Pair | Boot order | Score CPU change | Predeclared quality |
|---:|---|---:|---|
| 1 | Fabric → compiler | −1.05% | Pass |
| 2 | Compiler → Fabric | +35.22% | Pass |
| 3 | Compiler → Fabric | +27.30% | **Fail** |
| 4 | Fabric → compiler | +3.17% | Pass |
| 5 | Fabric → compiler | −2.22% | Pass |
| 6 | Compiler → Fabric | +19.62% | **Fail** |
| 7 | Compiler → Fabric | −0.57% | Pass |
| 8 | Fabric → compiler | +11.22% | Pass |
| 9 | Fabric → compiler | +0.24% | Pass |
| 10 | Compiler → Fabric | +4.48% | Pass |

Pairs 3 and 6 failed because the compiler-side JVMs did not qualify by the 18-window limit; pair 3 also exceeded the 8% within-boot score-drift threshold. Both remain in the primary interval. **Pair 2 passed all declared gates despite its unusually large CPU difference**, demonstrating that the present delay threshold is insufficient to eliminate every suspect high-cost regime.

## Warmup stability improved, with an important caveat

The earlier SCHED-HOOK-003 median within-JVM scoreboard early/late difference was ~**16.6%**. Under the new procedure, it was **1.27%**, and 18/20 JVMs reached the four-window stability criterion after 7–16 qualification windows. The remaining two exhausted the 18-window cap.

**This is a joint improvement from more warmup *and changed measurement order*.** In SCHED-HOOK-003 the two scoreboard windows were separated by conditional functions; in SCHED-HOOK-004 they are adjacent and follow explicit warmup of all families. The study cannot assign how much of the improvement to each modification individually. It does establish that this *combined protocol* produces much more internally repeatable scoreboard CPU results.

The median scoreboard costs for the two modes now cluster around ~212 ns and ~220 ns per source line, respectively, but individual compiler-side boots range from ~209 ns to ~279 ns.

## Host-noise and JVM execution diagnostics

All 20 boots tripped the **legacy** load-average-vs-CPU-count diagnostic. The new protocol instead uses direct Linux server-thread wait and cgroup throttling; it recorded **zero cgroup throttles** in the timed windows. The ten Fabric-only server boots had scoreboard run-queue wait fractions around **0.5–1.7%**. Most compiler-off boots were similarly low, but three compiler-side boots had **5.9%, 6.5%, and 6.1%** wait fractions.

| Compiler-side boot | Score CPU ns/source line | Server-thread wait fraction | Paired CPU difference | Warmup qualified? |
|---:|---:|---:|---:|---|
| 2 | 278.56 | 5.90% | +35.22% | Yes |
| 4 | 275.51 | 6.55% | +27.30% | No |
| 10 | 266.29 | 6.11% | +19.62% | No |

These three outlying boots account for much of the between-JVM variation. The **exploratory** Pearson correlation across all ten paired results between compiler-side wait fraction and paired CPU difference is approximately **+0.90**.

This is **evidence of an association**, not evidence of the origin of contention. Wait might arise from unrelated GitHub-host processes, JVM JIT compilation threads, GC, or other activity caused by loading our mod. Importantly, CPU running time excludes runnable wait time, but contention can still alter observed CPU execution cost through shared caches, scheduling-dependent JIT state, or changes in effective CPU frequency.

Also note that pair 8 had a **+11.22%** scoreboard difference with a low compiler-side run-queue wait fraction, so scheduling delay is **not** sufficient to explain all the slower outcomes.

### Post-hoc diagnostic, NOT a replacement estimate

Selecting only seven pairs where compiler-side wait fraction was below 2% produces a paired median of **+0.243%**, compared with the predeclared full-ten-pair median of +3.823%. The 2% cutoff was examined *after* seeing data. Do not quote this filtered value as a confirmed performance estimate or use it to change the experiment's formal verdict.

The secondary true/false conditional tests are saved alongside score results in `results.json`. Some high-score-delay boots also have high conditional costs, but the relationship is not uniform; they do not prove a scoreboard-specific transformation bug.

## Interpretation, constraints, and next study

1. **Measurement protocol improved.** Repeated CPU windows are now much more stable inside a given JVM, an essential prerequisite for meaningful per-command benchmarking.
2. **Compiler-installed overhead remains unresolved.** The earlier 21.7% two-boot estimate is not established as a systematic cost, but neither does the current +3.82% paired median prove negligible overhead. The high-side interval remains broad.
3. **There may be distinct compiler-side performance regimes.** Three high-cost boots coincide with higher scheduling delay and two failed warmup qualifications; another slower boot has low delay. This can reflect host-state differences, JVM compilation/tiering, or compiler startup/Mixin effects. The current data cannot identify the cause.
4. **The present host gate is permissive.** The 25% delay-fraction cap is not fine-grained enough to reject all strongly stressed cases; it was frozen *before* measurements, so changing it on this dataset would be invalid.
5. **The JVM is still a confounder.** Stability of four adjacent CPU windows does not establish that all hot paths reached the same JIT compilation tier or inlining profile across JVMs. Tracking JIT compilation activity separately is warranted.
6. **No scheduler rewrite justified.** We have measured the cost of installing an entire mod with all features off, not the potential performance benefit of replacing vanilla's queue.

**Recommended next experiment:** Record JIT compilation state and per-thread CPU/load during the qualification and timed stages to distinguish host-level scheduling interference from JVM-internal compiler activity. A separately preregistered comparison of full compiler-installed vs research build without individual scheduler/quota Mixins could then isolate installed hook cost, provided the warmup/host gate is demonstrably controlled.

**Final verdict:** Completed, data retained, major within-JVM stability improvement, **performance question inconclusive** under the declared test. Do not silently reinterpret the data as a proven speedup or regression.
