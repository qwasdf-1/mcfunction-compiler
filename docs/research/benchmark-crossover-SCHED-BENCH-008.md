# SCHED-BENCH-008 — Within-JVM crossover sensitivity (preregistered)

**Purpose:** conclude benchmark-methodology screening and proceed to actual compiler/function research. **Not** itself a compiler performance claim.

## Design

The preceding fresh-JVM sensitivity study [SCHED-BENCH-007](benchmark-sensitivity-SCHED-BENCH-007.md) was inconclusive. This study compares execution within a single warmed Minecraft 26.3 + Fabric API JVM. We will run **12 independent JVM boots**, each containing BOTH a negative and a positive control.

Per boot:
- Create `score_a` and `score_null` with exactly the same 2,000 ordinary scoreboard-add source lines; a *negative control* compares these separate but byte-identical functions.
- Create `score_treatment`, replacing the first **300 of the 2,000** scoreboard-add source lines with semantically equivalent `execute if score #gate fc_sched matches 1 run scoreboard players add #x fc_sched 1` lines. The gate is set to 1. The *positive control* compares this function to `score_a`.
- All three functions are prewarmed for 500 calls each; a separate bounded warmup/qualification plateau is recorded using the existing stable harness. Warmup does not enter the analysis.
- Each control uses **four consecutive 800-call windows** in **ABBA** or **BAAB** order (A=baseline, B=other function). Both controls execute in the *same JVM*, with 8 timed windows per boot. Randomized seed **8008** balances which control runs first (6/6) and the ABBA/BAAB orientation for each control (6/6).
- Each function performs exactly **2,000 scoreboard increments per call**. Reset the score before each measurement, and verify exact final scoreboard state. This is the integrity gate, not an assumed semantic equivalence.
- The server-thread CPU measurement is primary. Host load, scheduler wait, cgroup throttling and optional JVM role counters are separate descriptive diagnostics. No JFR or GC unified logging is enabled during timing.
- Use existing `-Xms512M -Xmx2G` and pinned Java/Fabric/server/tooling versions; only the research harness and datapacks change. No compiler jar is installed in this screening run.

## Statistics / decision

A signed contrast for an ABBA or BAAB block is **100 × [mean log(B ns/line) − mean log(A ns/line)]**. The balanced order cancels a *linear trend in log CPU cost* during the four windows, although higher-order drift and carryover are possible.

Compute **one negative and one positive contrast per boot**, producing **12 independent paired-boot observations per control**. Report the boot-level median and a conservative distribution-free exact median interval of at least 95% coverage. Do **not** treat the 96 raw windows as independent replicates. All boots/windows, including failed qualifications or noisy windows, must remain in the archived results.

Quality gate (fixed, not tuned to observed outcomes):
- All 12 boots have a qualified warmup plateau.
- All 96 timed windows have zero cgroup throttling events.
- All timed windows have available runqueue-delay fractions ≤25%.
- All scoreboard verification succeeds (otherwise abort and mark experiment failed, preserving partial data).

Screening passes only if quality passes, the negative control interval includes zero, and the positive control interval is strictly above zero. The **positive-control overhead is not a known fixed 3–5% effect**; this study does not establish 3–5% power or false-positive frequency. The study is a bounded comparison to decide whether a within-JVM method is practical.

## Limits and next experiments

Within-JVM comparisons of distinct function bodies can suffer unequal JIT optimization, code-cache effects, and cross-function carryover. The control tests validate sensitivity to a changed instruction mix, **not** that production compiler-on/off variants can be toggled at runtime. A/A interval including zero does not prove equivalence. GC- and OS-related events still count where they affect measured server-thread CPU.

After evaluating 008, **stop general JVM-noise studies**. Next prioritize:
1. **Typed command compilation:** a real compile-on vs plain vanilla execution contrast with exact scoreboard and callback parity for the specific command families the compiler can optimize. Prefer same-JVM comparison only if the compiler exposes both execution paths without contaminating the baseline; otherwise use appropriately blocked fresh-JVM or dedicated-host measurements.
2. **Compiler cost and amortization:** report compilation/reload time and break-even calls, not just warm steady-state CPU.
3. **Scheduler replacement incrementality:** compare vanilla scheduler + normal functions vs vanilla scheduler + typed compiler vs typed compiler + alternative scheduler, rather than treating scheduler replacement as a prerequisite.

Failure of 008 should not trigger an indefinite measurement-methodology diversion; use the existing harness with honest uncertainty and move to large-effect compiler questions or dedicated hardware where warranted.

**Outputs:** `build/benchmarks/SCHED-BENCH-008/results.json` and 12 raw server logs. Tests: `tests/test_benchmark_crossover.py`. CI: `.github/workflows/research-benchmark-crossover.yml`.
