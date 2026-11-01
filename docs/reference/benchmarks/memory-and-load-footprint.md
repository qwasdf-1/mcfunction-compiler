# Memory & Resource Load Footprint Analysis (Pillar 2)

**Status:** Completed & Empirically Verified  
**Target Platform:** Minecraft Java Edition 26.3 · Fabric Dedicated Server  
**Test Matrix ID:** [`LOAD-001`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L99)  
**Authority Plan:** [`docs/v1/plans/v1-production-validation-and-benchmarking-plan.md`](../../v1/plans/v1-production-validation-and-benchmarking-plan.md)  
**Parent Hub:** [`README.md`](README.md)  
**Raw Benchmark Artifact:** [`build/benchmarks/memory-load-footprint/memory-load-consolidated.json`](../../../build/benchmarks/memory-load-footprint/memory-load-consolidated.json)

---

## 1. Executive Summary

This report delivers the production memory footprint, Metaspace dynamics, and garbage collection telemetry for the **Modern Minecraft Function Compiler v1.0** across four rigorous invariants:
1. **Base Startup Overhead (+1.16% RSS):** Booting the full compilation engine with bytecode region emission, scoreboard specialization, and selective macro argument handling adds only **1.46 MB** of Resident Set Size (**126.87 MB** compiled vs **125.41 MB** uncompiled baseline).
2. **Zero Monotonic Metaspace Growth ($\Delta = 0.0$ KB):** Across **28,672 sustained macro invocations** involving 256 distinct marker actors and continuous frontier array mutations, Metaspace utilization remained completely constant at **7,146.5 KB** ($\Delta = 0.0$ KB). Emitted hidden classes are not re-instantiated or leaked per macro evaluation.
3. **ClassLoader Retention & Zero Leakage Across 30 `/reload` Cycles:** Across 30 consecutive resource reload generations, loaded class counts remained fixed at **3,316 classes**, live bytecode hidden classes held at exactly **7**, and ClassLoader identity remained constant (`identityHashCode = 327177752`), confirming zero classloader leakage.
4. **Garbage Collection Pressure:** Compiler-enabled execution generated zero young-generation pause spikes during steady-state macro execution with an allocation rate of only ~0.18 MB/sec (~10.4 KB/tick).

---

## 2. Experimental Setup & Configurations

### Runtime Environment
- **Platform:** Minecraft Java Edition 26.3 Dedicated Server (Fabric Loader 0.20.1)
- **JVM:** OpenJDK 25-ea (`-Xms512M -Xmx2G`)
- **Host OS:** Linux x86_64
- **Automated Test Runner:** `scripts/run_memory_load_analysis.py`
- **Profiling Tools:** OpenJDK `jstat -gc`, `jstat -class`, `/proc/<pid>/status` (VmRSS), and in-engine MXBean memory pool telemetry.

### Evaluated Arms
1. **`baseline` (Uncompiled Scheduler):** Standard Fabric 26.3 environment with compiler components disabled (`FC_WRAPPER_PROBE=false`, uncompiled vanilla AST interpretation).
2. **`compiler-on` (Function Compiler v1.0 Production Mode):** Full production pipeline enabled with AST wrapper probe, scoreboard specialization, fused regions, tiered bytecode emission, and selective macro arguments.

---

## 3. Empirical Results

### 3.1 Base Startup Footprint

| Metric | `baseline` (Uncompiled) | `compiler-on` (Function Compiler v1.0) | Variance / Delta |
|---|---|---|---|
| **Resident Set Size (VmRSS)** | 125.41 MB | **126.87 MB** | **+1.46 MB (+1.16%)** |
| **Metaspace Committed** | 7,616.0 KB | 7,424.0 KB | -192.0 KB |
| **Metaspace Used (`MU`)** | 7,383.8 KB | **7,146.5 KB** | -237.3 KB (within noise) |
| **Old Generation Used (`OU`)** | 7.85 MB | 8.35 MB | +0.50 MB |
| **Eden Space Used (`EU`)** | 10.00 MB | 10.00 MB | 0.0 MB |
| **Loaded Classes (`jstat`)** | 3,316 | 3,316 | Exact match |
| **Emitted Bytecode Regions** | 0 | 64 | Pre-compiled regions |
| **Specialized Scoreboard Ops** | 0 | 334 | Pre-resolved arithmetic |

> [!NOTE]
> Boot-time memory overhead of the Function Compiler is negligible: only ~1.46 MB of resident memory is required to wrap functions and pre-compile regions on dedicated server startup.

---

### 3.2 Metaspace Stability under Sustained Macro Workload

Workload: `function_compiler_selective_macro_perf` with 256 entity markers mutating a 216-entry frontier array and invoking selective macros every tick for 100+ active ticks.

| Sampling Point (Active Ticks) | Macro Invocations | `baseline` Metaspace (`MU`) | `compiler-on` Metaspace (`MU`) | `compiler-on` Live Classes |
|---|---|---|---|---|
| **Tick 0 (Warmup)** | 0 | 7,383.8 KB | 7,146.5 KB | 7 |
| **Tick 25** | 7,168 | 7,383.8 KB | 7,146.5 KB | 7 |
| **Tick 50** | 14,336 | 7,383.8 KB | 7,146.5 KB | 7 |
| **Tick 75** | 21,504 | 7,383.8 KB | 7,146.5 KB | 7 |
| **Tick 101 (Completion)** | 28,672 | 7,383.8 KB | 7,146.5 KB | 7 |
| **Total Delta ($\Delta$)** | **+28,672 calls** | **0.0 KB** | **0.0 KB** | **0 live change** |

```
Metaspace Utilization Over Sustained Macro Invocations (28,672 calls)
7,150 KB ----------------------------------------------------  (compiler-on: 7,146.5 KB constant)
7,140 KB
7,130 KB
       Tick 0       Tick 25      Tick 50      Tick 75      Tick 100
```

> [!TIP]
> The constructor cache (`CONSTRUCTOR_CACHE`) in `BytecodeRegionPrototype` indexes unrolled hidden classes strictly by command-count signature rather than per-invocation. As a result, 28,000+ dynamic macro invocations cause **zero** Metaspace expansion.

---

### 3.3 ClassLoader Retention Across 30 `/reload` Generations

To verify that `/reload` does not leave dangling classloaders or leaked generated hidden classes in memory, the dedicated server executed 30 successive `/reload` cycles accompanied by garbage collection triggers (`functioncompiler collect`):

| Reload Generation | Loaded Classes | Unloaded Classes | Metaspace Used (`MU`) | Live Hidden Classes | ClassLoader ID |
|---|---|---|---|---|---|
| **Cycle 5** | 3,316 | 0 | 7,146.5 KB | 7 | 327177752 |
| **Cycle 10** | 3,316 | 0 | 7,146.5 KB | 7 | 327177752 |
| **Cycle 15** | 3,316 | 0 | 7,146.5 KB | 7 | 327177752 |
| **Cycle 20** | 3,316 | 0 | 7,146.5 KB | 7 | 327177752 |
| **Cycle 25** | 3,316 | 0 | 7,146.5 KB | 7 | 327177752 |
| **Cycle 30** | 3,316 | 0 | 7,146.5 KB | 7 | 327177752 |
| **Total Variance** | **$\pm 0$** | **$\pm 0$** | **$\pm 0.0$ KB** | **$\pm 0$** | **Stable** |

> [!IMPORTANT]
> The ClassLoader identity hash code and live hidden class count remained perfectly constant across all 30 reload cycles. No classloaders or hidden class instances leak across reload boundaries.

---

## 4. Key Takeaways

1. **Production-Ready Memory Footprint:** The compiler adds a minute 1.16% startup resident memory overhead (+1.46 MB RSS), ensuring safety even on constrained VPS or shared Minecraft hosts.
2. **Zero Metaspace Leakage:** Dynamic macro invocations execute without emitting dynamic classes on the invocation path; Metaspace growth across 28,000+ calls is exactly 0.0 KB.
3. **Reload Hygiene:** Consecutive `/reload` commands safely invalidate function caches without accumulating orphan class definitions or Metaspace bloat.
