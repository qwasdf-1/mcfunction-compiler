# PERF-008: Large-Scale Compilation Benchmark (1,000+ Generated Functions)

**Run:** 2026-10-30  
**Evidence:** [`build/reports/benchmarks/PERF-008/20261030T062052.results.json`](../build/reports/benchmarks/PERF-008/20261030T062052.results.json)  
**Status:** Complete. Verified compilation latency, class emission, Metaspace usage, and execution parity across 1,024 generated functions.

---

## 1. Methodology

The benchmark stress-tests function compilation, JVM hidden class generation, Metaspace footprint, reload latency, and execution parity on Minecraft 26.3 Fabric server with a datapack containing **1,024 distinct `.mcfunction` files**.

### Function Generation Patterns
The 1,024 functions follow four distinct structural patterns to evaluate varying region boundaries:
- **Pattern 0 (256 functions):** Pure contiguous ScoreAdd block (8 additions to `#var_i`). Compiles to **1 fused/bytecode region** per function.
- **Pattern 1 (256 functions):** Split ScoreAdd block separated by a native non-eligible command (`say step_i`). Compiles to **2 distinct regions** per function (4 additions each).
- **Pattern 2 (256 functions):** Triple ScoreAdd block separated by multiple native commands (`say a_i`, `say b_i`). Compiles to **3 distinct regions** per function (3 additions each).
- **Pattern 3 (256 functions):** Pure vanilla non-ScoreAdd commands (`say no-op_i`). Compiles to **0 regions** (pass-through fallback).

Across all 1,024 generated functions plus baseline probe fixtures:
- **Expected generated regions:** 1,536 regions (1,574 including base probe functions).
- **Expected ScoreAdd operations:** 6,400 operations (6,542 including base probe functions).

### Evaluated Arms
1. **`fabric-off`**: Project runtime loaded with all compiler prototypes disabled (uncompiled baseline).
2. **`score-add-on`**: Narrow Brigadier callback specialization enabled.
3. **`fused-interpreted`**: Contiguous ScoreAdd interpretation loop enabled.
4. **`bytecode-emitted`**: In-memory ASM bytecode generation emitting hidden JVM classes via `defineHiddenClass`.

---

## 2. Compilation Latency & Reload Performance

| Mode | Server Startup | Reload Cycle 1 Latency | Reload Cycle 2 Latency |
|---|---|---|---|
| **`fabric-off`** | 17.01 s | 301.16 ms | 239.17 ms |
| **`score-add-on`** | 16.01 s | 331.40 ms | 241.13 ms |
| **`fused-interpreted`** | 16.01 s | 489.82 ms | 312.44 ms |
| **`bytecode-emitted`** | 17.01 s | 332.12 ms | 301.53 ms |

### Key Observations
- Emitting 1,574 hidden JVM classes on-the-fly in `bytecode-emitted` added only **~31 ms** to the `/reload` cycle over `fabric-off` (332.12 ms vs 301.16 ms).
- Server startup remained virtually identical across all arms (~16–17 s).
- Second reload cycle warmed to ~301 ms in bytecode and ~239 ms in uncompiled baseline.

---

## 3. Class Generation & Memory Footprint

| Metric | `fabric-off` | `score-add-on` | `fused-interpreted` | `bytecode-emitted` |
|---|---|---|---|---|
| **Compiled Regions** | 0 | 0 | 1,574 (3,148 cumulative) | 1,574 (3,148 cumulative) |
| **Emitted Class Bytes** | 0 B | 0 B | 0 B | 1,696,208 B (~1.62 MiB) |
| **Average Class Size** | N/A | N/A | N/A | **1,077 B / class** |
| **Live Generated Classes (Post-GC)** | 0 | 0 | 0 | **1,574** |
| **Baseline Metaspace** | 104.82 MiB | 104.91 MiB | 104.99 MiB | **107.87 MiB** |
| **Metaspace Overhead** | 0 MiB | +0.09 MiB | +0.17 MiB | **+3.05 MiB** (~2.03 KiB / class) |
| **Metaspace Growth Reload 1** | +79.4 KiB | +91.2 KiB | +89.8 KiB | **+153.6 KiB** |
| **Metaspace Growth Reload 2** | +396.7 KiB | +389.5 KiB | +350.4 KiB | **+377.6 KiB** |

### Key Observations
- **Class Unloading / Retention Stability:** After GC collection (`function_compiler_probe collect`), the count of live generated classes in `bytecode-emitted` was exactly 1,574 across reloads. Unreferenced previous-generation classes are successfully eligible for JVM unlinking.
- **Metaspace Efficiency:** Emitting 1,574 distinct classes consumed only 3.05 MiB of Metaspace overhead (~2.03 KiB per compiled region).

---

## 4. Execution Parity & Graceful Fallback

A stratified sample of 40 generated functions (10 functions from each of Patterns 0, 1, 2, and 3) was executed across all arms:
- **Pattern 0:** Exact score 36 reached (`1+2+3+4+5+6+7+8`).
- **Pattern 1:** Exact score 36 reached across 2 regions and interleaved `say`.
- **Pattern 2:** Exact score 45 reached across 3 regions and interleaved `say` commands (`1+...+9`).
- **Pattern 3:** Exact score 0 reached (vanilla pass-through).
- **Execution Parity:** 100% of sample functions matched expected scoreboard outcomes with zero divergence between `fabric-off`, `fused-interpreted`, and `bytecode-emitted`. In bytecode mode, `bytecode_regions_executed` advanced by exactly 60 regions during the 40-function sample run.

---

## 5. Conclusion & Prototype Promotion Readiness

1. **Large-Scale Scalability Confirmed:** The bytecode emitter handles 1,000+ functions and 1,500+ generated regions without noticeable reload delay (+31 ms) or Metaspace explosion (+3 MiB).
2. **Prototype Gating Status:** While technical scalability and stability are verified, real-world datapack workload screening reveals that few unmodified datapacks exhibit long contiguous fake-holder scoreboard addition runs (most real-world commands interleave entity selectors, macros, or NBT operations). Prototypes should remain **disabled by default** until wider instruction types (or selector targets) are supported.
