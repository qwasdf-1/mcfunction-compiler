# Emitted ASM Bytecode Regions & Tiered JIT Engine

**Status:** Opt-in / Experimental Tiered JIT Backend (Milestone 2 Verified).  
**Configuration Key:** `"tiered_bytecode": false` (in `config/function-compiler.json`)  
**Threshold Setting:** `"tiered_threshold": 5`  
**Owner Classes:** [`BytecodeRegionPrototype.java`](../../../src/main/java/dev/functioncompiler/BytecodeRegionPrototype.java), [`BytecodeRegionEmitter.java`](../../../src/main/java/dev/functioncompiler/BytecodeRegionEmitter.java), [`TieredRegionAction.java`](../../../src/main/java/dev/functioncompiler/TieredRegionAction.java)  
**Test IDs:** [`PERF-013`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L92), [`PERF-014`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L93), [`PERF-008`](../../../benchmarks/PERF-008-large-scale-compilation.md), [`RELOAD-002`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L52)

---

## 1. Parameterized Bytecode Backend (Milestone 2)

Earlier ASM bytecode approaches compiled classes tied to specific command text or parameter values, leading to Metaspace exhaustion when applied to dynamic macro functions.

The **Parameterized Bytecode Backend** resolves this by emitting structural loop classes parameterized purely by **command count**:
1. **Structural Class Shape:** The emitted class holds a private array `Object[] commands` passed into its constructor.
2. **Indexed Array Unrolling:** Each step in the emitted `execute` method loads the command from `commands[i]` and calls `BytecodeRegionPrototype.executeStep`.
3. **Constructor MethodHandle Caching:** Constructor `MethodHandle` instances are cached in `ConcurrentMap<Integer, MethodHandle> CONSTRUCTOR_CACHE`.
4. **Zero Metaspace Leaks for Macros:** All macro function instantiations and static functions containing the same number of contiguous commands share the **exact same single JVM class**.

### Empirical Metaspace Invariant Proof (`PERF-014`)
In empirical testing over 300 macro invocations across 4 runtime modes (`macro-benchmark-20261030T175426.json`):
- Pre-invocation live generated classes: **6**
- Post-invocation live generated classes: **6** ($\Delta = 0$)
- Total class bytes emitted: **6,562 bytes** ($\Delta = 0\ \text{bytes}$)
- Operations executed in bytecode: **3,410 operations**

---

## 2. Tiered JIT Engine & 4-Part Cold Policy (`PERF-013`)

To avoid compilation overhead on one-shot or cold functions, the backend integrates [`TieredRegionAction.java`](../../../src/main/java/dev/functioncompiler/TieredRegionAction.java) with a four-part cold policy:

1. **Length Threshold:** Functions with fewer than 3 commands ($L < 3$) bypass bytecode generation, executing via interpreted fusion with zero bytecode overhead.
2. **Startup Routine Bypass:** `#minecraft:load` and initialization routines bypass bytecode generation, preventing cold code pollution.
3. **Deferred JIT Tiering:** The action executes calls $1 \dots K-1$ via interpreted fusion. Upon invocation $K \ge \text{threshold}$ (default: 5), it compiles the region to unrolled bytecode and swaps the reference atomically.
4. **Weak Class Retention:** Emitted classes are tracked via `WeakReference` in `BytecodeRegionPrototype` to ensure prompt JVM garbage collection.

---

## 3. Compilation Failure Fallback

If bytecode emission, class loading, or constructor invocation throws an exception (forced via `functioncompiler.bytecode_compile_failure_forced=true`):
- The failure is caught and logged at warning level.
- The function builder immediately falls back to the original uncompiled queue entries or interpreted actions.
- In validation tests, 30 injected compilation failures resulted in 0 emitted bytecode classes and 100% successful execution through original queue entries with byte-for-byte state parity against vanilla.

---

## 4. Large-Scale Compilation Scalability (`PERF-008`)

In `PERF-008`, the compiler was stress-tested with **1,024 generated `.mcfunction` files** emitting **1,574 hidden JVM classes**:
- **Reload Overhead:** Emitting 1,574 hidden classes added only ~31 ms of reload time (332.12 ms bytecode vs 301.16 ms uncompiled baseline).
- **Class Emission Efficiency:** Generated class bytes totaled 1.62 MiB (averaging 1,077 bytes per compiled class).
- **Metaspace Stability:** Metaspace overhead was 3.05 MiB (~2.03 KiB / class); post-GC retention held steady at 1,574 classes across reloads.
- **Execution Parity:** 100% of sample functions executed with byte-for-byte exact scoreboard parity.
