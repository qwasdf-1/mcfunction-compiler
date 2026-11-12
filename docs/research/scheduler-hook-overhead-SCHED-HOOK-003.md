# SCHED-HOOK-003 — Paired cost of installing the disabled compiler

**Experiment date:** 2026-11-12  
**Status:** All trials completed, exact workload parity passed; **performance-quality gate failed**.  
**Decision:** Inconclusive for a material CPU regression. The earlier ~22% compiler-off scoreboard overhead did **not** reproduce as a stable effect in the paired comparison.

## Research hypothesis

SCHED-ATTR-002 measured a scoreboard cost of ~171 ns per source line on Fabric with Fabric API alone, versus ~209 ns with the compiler mod installed but all optimizations off (a descriptive 21.7% increase). But that was a two-boot-per-mode screening experiment in which all six boots failed the host-noise gate. This study directly tests whether that apparent installed-Mixin overhead survives repeated, counterbalanced, adjacent comparisons on the **same runner**.

This comparison isolates the *incremental effect of adding the complete compiler mod* to a Fabric API server, not solely the cost of one Mixin or of the vanilla scheduler.

## Implementation and raw evidence

- Runner: [`scripts/ci_compiler_off_paired.py`](../../scripts/ci_compiler_off_paired.py)
- Synthetic statistical contract tests: [`tests/test_compiler_off_paired.py`](../../tests/test_compiler_off_paired.py)
- Dedicated Actions workflow: [`.github/workflows/research-hook-paired.yml`](../../.github/workflows/research-hook-paired.yml)
- First committed predeclared source at `514ae49782ea8c3c4a2f6b468f7f37b2486a4ef5`
- **Completed Actions run:** [43263924503](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43263924503), passed build, six statistical tests, all twenty boots.
- **Raw artifact:** `sched-hook-003-paired-raw` in that run. Contains `results.json` with every window, host counter, boot and pair, plus twenty server logs. Artifacts have finite Actions retention; download and preserve them for long-term reproducibility.

Artifacts are pinned/hashes preserved in `results.json`. The campaign uses the production Fabric server installer, Fabric Loader 0.20.1, Fabric API 0.165.0+26.3, Minecraft 26.3, Java 25, and the remapped production compiler artifact. The only mod difference in each pair is the added `function_compiler` JAR. All optimization and trace/probe environment flags are disabled.

### Predeclared design

| Variable | Definition |
|---|---|
| Primary target | CPU time per native scoreboard source line |
| Pairing | **10 adjacent fabric-only / compiler-off pairs** on the same CI runner |
| Order | 5 four-boot ABBA / BAAB blocks; 5 pairs start Fabric, 5 start compiler |
| JVM | Fresh for each boot, identical `-Xms512M -Xmx2G` arguments |
| Function length | 2,000 repeated native Minecraft commands |
| Per-window workload | 300 warmup calls; 1,600 timed calls = 3.2 million measured source lines |
| Within-boot sequence | Scoreboard, true conditional, false conditional, scoreboard |
| Boot-level scoreboard value | Mean of the two scoreboard windows |
| Primary statistic | Median of ten paired percentage changes, compiler-off relative to Fabric |
| Confidence | Conservative exact 95%+ distribution-free interval for the median, without dropping outliers |
| Material regression criterion | Entire exact interval above **+5%**, with all quality gates passed |
| Quality gates | Exact scoreboard parity, quiet host in every pair, pair load difference ≤1.0, within-boot score drift ≤12% |
| JFR | Off throughout measurements |
| Other observations | Per-thread Linux CPU running time, run-queue delay; cgroup CPU throttling; RCON p50/p95 |

Every boot executes *four* measurement windows. Total: **80 timed windows and 256 million measured source-line executions**, plus warmup commands. All exact-state checks passed. No pair was discarded.

This is a targeted hypothesis test with an explicit negative result permitted. It is **not** the project's default-on optimization promotion protocol.

## Results

### Primary outcome

| Metric | Observation |
|---|---:|
| Paired comparisons | 10 |
| Compiler slower / faster pairs | 6 slower / 4 faster |
| **Median compiler-off CPU difference** | **+1.458%** |
| **Exact median interval (97.85% coverage)** | **−1.940% to +8.611%** |
| Median Fabric-only CPU ns/line, across boots | 185.403 |
| Median compiler-off CPU ns/line, across boots | 188.428 |
| Quiet/stability-quality pairs | **0 / 10** |
| Machine-readable verdict | `inconclusive_host_or_stability_gate` |

The interval includes zero and the +5% threshold. **It does not establish a compiler-off regression**, and it is too wide to establish equivalence within ±5% either.

Although the earlier experiment's descriptive ~21.7% scoreboard difference is much larger than this study's median +1.46%, this is not evidence that installed hooks are free in all cases. It is evidence against treating the earlier two-boot estimate as a reproducible, well-isolated overhead percentage.

### All ten paired scoreboard changes

Positive values mean compiler installed but disabled used more server-thread CPU.

| Pair | Boot order | CPU difference |
|---:|---|---:|
| 1 | Fabric → compiler | −0.53% |
| 2 | Compiler → Fabric | +17.16% |
| 3 | Compiler → Fabric | +8.61% |
| 4 | Fabric → compiler | +5.14% |
| 5 | Fabric → compiler | +1.08% |
| 6 | Compiler → Fabric | −1.94% |
| 7 | Compiler → Fabric | −0.35% |
| 8 | Fabric → compiler | −3.48% |
| 9 | Fabric → compiler | +1.90% |
| 10 | Compiler → Fabric | +1.83% |

Order is perfectly balanced between compiler-first and baseline-first pairs, and the large pair-to-pair variation is retained, not filtered.

### Secondary conditional controls

| Workload | Median paired CPU difference | Exact 97.85% interval |
|---|---:|---:|
| `execute if score` condition true | −0.22% | −12.89% to +20.79% |
| `execute if score` condition false | +1.95% | −5.91% to +14.40% |

These controls also do not show a robust, consistent compiler-installed cost.

## Why the quality gate failed

Two independent problems were detected.

### 1. Host-load precondition

The runner had **2 reported logical CPUs**. Observed one-minute load averages at boot entry ranged **1.977–3.480**, and at least one measurement window was over the shared host gate in *every boot*. All ten pairs therefore failed the required quiet-host test. Pair-start load differences ranged from ~0.006 to ~0.490, remaining within the separate 1.0 difference threshold.

**A high load average is not proof of noisy neighbors.** It includes runnable work from the Minecraft JVMs themselves and can remain elevated from previous boots. These observations indicate that the specified quiet-host gate was not met, but do not independently identify its source.

The cgroup's `nr_throttled` counter did **not increment in any of the 80 timed windows**, indicating no cgroup quota-throttling events were observed. This does not rule out scheduling contention or cache interference. The Linux server-thread `schedstat` run-queue delay was nonzero.

### 2. Very large within-boot CPU drift

The first and second scoreboard measurements were separated by two conditional-command workloads. They should be similar if the JVM and host are stable:

| Measure | Fabric-only | Compiler installed, disabled |
|---|---:|---:|
| Median first scoreboard window (ns/line) | 192.30 | 206.90 |
| Median second scoreboard window (ns/line) | 170.62 | 164.74 |
| Mean within-boot relative drift | −14.38% | −19.32% |

Across all 20 boots:

- **18/20** second scoreboard windows were faster than the first.
- **15/20** exceeded the declared ±12% within-boot drift tolerance.
- Median within-boot drift was approximately **−16.64%**.

The consistently downward direction is strongly suggestive of **incomplete JVM warmup or phase-order effects**, potentially combined with host contention. The present experiment does not establish which mechanism dominates. Merely increasing warmup calls without observing stable compilation levels may not suffice.

In particular, **the within-JVM drift is an order of magnitude larger than the median paired compiler delta**. This is a measurement-method warning: changing the installed-mod state while comparing fresh JVMs remains confounded when the JVM has not achieved a stable execution regime.

## Methodological interpretation

The new pairing significantly improves on the previous unpaired six-boot test: it holds runner hardware, Fabric dependencies, source text, JVM arguments and data integrity constant within adjacent pairs, and counterbalances boot order. The paired median is robust to broad time trends.

But it does **not** cancel unstable JIT compilation, command family interaction, or abrupt per-boot contention. The precise conclusion is therefore:

1. **The earlier 21.7% scoreboard slowdown is not replicated as a consistent paired effect.**
2. **A real small compiler-installed overhead remains possible**; the confidence interval reaches +8.61%.
3. **The current experimental host and warmup protocol cannot establish a clean ≤5% equivalence or ≥5% regression** under the predeclared quality gates.
4. **No evidence here justifies rewriting Minecraft's global function scheduler.** This is an installed-mod overhead study, not a scheduler replacement benchmark.

## Next experiment — stability-first paired campaign

A follow-up must be declared as a **new experiment**, not an after-the-fact selective reanalysis of this one.

1. Introduce per-boot repeated-scoreboard warmup until a fixed, independently defined **stability criterion** is met (e.g., multiple successive fixed-size windows with bounded CPU changes). Set a maximum warmup budget and record failures without excluding them.
2. Run measurement **after** cross-family warmup, and counterbalance the *within-boot function-family order* rather than systematically measuring scoreboard first.
3. Keep adjacent ABBA/BAAB pairs and explicit host contention telemetry, but decide beforehand whether load average or direct run-queue / throttling measures serve as the confirmatory host gate; don't relax it retroactively after seeing these results.
4. Record JVM compilation activity (separate warmup diagnostic, not during timed windows) to determine whether the early/late change is attributable to tiered compilation.
5. Re-run at least ten pairs. Only claim a material regression if the exact paired interval and all predeclared quality gates pass.

A further isolation experiment could build the same compiler JAR with its scheduler/trace Mixins individually disabled, providing a finer attribution of any remaining installed-mod cost, but it must still be compared against an independent Fabric-only reference.

**Final verdict:** Correctness verified; timing and sample collection successful; statistically and procedurally **inconclusive** for a compiler-installed regression. Preserve the complete negative result.
