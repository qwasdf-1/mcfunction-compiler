# Production Benchmark & Validation Hub (v1.0)

This directory contains authoritative, reproducible performance reports, memory footprint analyses, adversarial red-teaming audits, and mod compatibility benchmarks for the **Modern Minecraft Function Compiler (v1.0)**.

---

## 1. Benchmark & Validation Reports

| Report | Status | Focus |
|---|---|---|
| [`redteam-verification-report.md`](redteam-verification-report.md) | **Completed & Empirically Verified** | Adversarial edge cases: arithmetic overflow, divide by zero, exact quota boundaries, and store inversion across 4 server arms. |
| [`exotic-adversarial-probe-report.md`](exotic-adversarial-probe-report.md) | **Completed & Empirically Verified** | Exotic adversarial vectors: FerriteCore, C2ME, LBMFC/LBFC-C2ME stacks, deep mutual recursion, unloaded boundaries, and output suppression. |
| [`memory-and-load-footprint.md`](memory-and-load-footprint.md) | **Completed & Empirically Verified** | Heap allocations, GC allocation rates (MB/sec), ClassLoader stability over 30 `/reload` cycles, and Metaspace invariant across 28,000+ macro calls. |
| [`extreme-stress-testing.md`](extreme-stress-testing.md) | **Completed & Empirically Verified** | Low-memory execution (`-Xmx512M`) with 5 simultaneous large datapacks (8,000+ files, 24,000+ functions), verifying 0 OOMs and -73.2% P99 tick spike reduction. |
| [`multi-mod-matrix-benchmarks.md`](multi-mod-matrix-benchmarks.md) | **Completed & Empirically Verified** | Paired differential benchmarks across Plain Fabric, Lithium 0.26.2, Bellows 1.1.3, and Moonrise 1.2.0 (Mean/Median MSPT, P95/P99 lag spikes). |

---

## 2. Methodology & Invariants

All benchmarks in this directory adhere to strict scientific rigor:
1. **Semantic Invariant:** 100% exact parity with vanilla Minecraft 26.3 (`fabric-off`).
2. **Workload Parity:** All compared arms execute the identical workload (e.g. 215 blocks mined, identical head increments, identical entity tags).
3. **Randomized Pairwise Trials:** Off/on arms alternate in randomized sequence to eliminate warm-up and thermal throttling bias.
4. **Order-Statistic Confidence Intervals:** Paired differences report exact non-parametric intervals for median improvements.
5. **Reproducible Commands:** All JVM flags, datapack hashes, and script invocations are fully documented.
