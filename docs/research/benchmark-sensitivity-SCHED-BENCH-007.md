# SCHED-BENCH-007 — Paired benchmark sensitivity and controls

**Stage:** first prospective measurement-sensitivity campaign. This is **not** a compiler speedup benchmark. It runs against the identical Fabric-only stack on every boot.

## Question and estimand

Can the current shared GitHub Actions host and fresh-JVM paired experiment (1) correctly report no directional CPU effect when the measured workloads are identical, and (2) detect the increased CPU work of a deliberately more expensive, semantically equivalent Minecraft function?

Primary endpoint: paired **server-thread CPU ns per 2,000 executed source lines**, expressed as signed `100 * ln(B/A)` (positive = B slower), measured from two adjacent fresh Minecraft JVM boots. The conservative exact >=95% order-statistic median interval is reported for each control separately. CPU ns per source line is not whole-JVM CPU or TPS/MSPT.

## Preregistered allocation

- 20 pairs, 40 boots, all on the same pinned Fabric-only stack. Ten A/A negative-control pairs and ten A/B positive-control pairs, interspersed by fixed RNG seed **7007**.
- Independently balanced A/B vs B/A positions within both controls (five of each).
- A/A: two byte-for-byte identical function packs and JVM configurations. Labels A/B are placebo, not compiler conditions.
- A/B: the B arm's `score.mcfunction` replaces the **first 300** of its existing **2,000** `scoreboard players add` lines with equivalent `execute if score #gate fc_sched matches 1 run scoreboard players add #x fc_sched 1` lines. The gate is initialized to 1 before warmup. All 2,000 score increments per function call must still happen; full scoreboard verification is required for every window. This increases command-processing complexity, not source-line count.
- The 300/2,000 choice is fixed before collecting results. **It is not an a priori known 3%, 5%, or 10% slowdown**, and one cannot infer detection power at those thresholds from a single A/B experiment.
- Reuse SCHED-HOOK-004 qualification plateau, two timed score windows, scoreboard parity, Linux thread scheduling counters, and fixed host quality gates. No GC-log flag is enabled. Retain each boot and all failed quality pairs in results; no substitutions or early stopping.
- Only score windows enter the primary contrast. Condition-true and condition-false workloads remain integrity/secondary diagnostics.

## Decision criteria

1. **Negative control:** 95% exact median interval of A/A signed `ln(B/A)` includes zero.
2. **Positive control:** corresponding A/B median interval has lower endpoint >0, indicating consistently slower B in this campaign.
3. **Quality:** every pair meets the existing preregistered quality gates. Quality failures produce an inconclusive verdict; they are never removed to improve significance.

Both control conditions and all quality gates must pass for `passed_defined_control_detections`. These are a **single-campaign screening rule**, not estimates of statistical power or type-I error. A 95% interval containing zero is failure to reject a difference, not proof of equivalence. The post-campaign signed median and interval should be interpreted in log-percent units, not ordinary percent without converting.

## Limits and interpretation

A/B alters the instruction mix, rather than adding a fixed amount of CPU nanoseconds. The observed effect size is unknown until measured; it cannot validate detection of a precise 3% improvement. Repeated JVM boots may differ in JIT state and host load. Adjacent pairing and randomized order help but cannot remove systematic host drift or mode-specific warmup behavior. The code tests exercise assignment, fixture semantics, arithmetic, exact-score invariants and failure retention.

If both controls pass, the next experiment is a predeclared, independently repeated set of real compiler-on/off comparisons, with tighter design or dedicated runner if the target is a ~3% effect. If the negative control suggests false positives, reassess host blocking/inference. If the positive control fails, increase sensitivity or choose a larger identifiable workload delta *in a new preregistered study*; do not retune 007 after inspecting results.

This change contains **no compiler production modifications** and does not assert that an alternative scheduler improves throughput.

## Outputs

`build/benchmarks/SCHED-BENCH-007/results.json` plus 40 per-boot console logs. Run `python3 scripts/ci_benchmark_sensitivity.py` in the existing pinned CI environment. The dedicated workflow preserves raw artifacts and executes the synthetic contracts before Minecraft boots.
