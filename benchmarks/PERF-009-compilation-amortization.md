# PERF-009: Compilation Amortization for Cold and Hot Functions

**Run:** 2026-10-30  
**Evidence:** [`benchmarks/PERF-004-bytecode-timing/results.json`](../build/benchmarks/PERF-004-bytecode-timing/results.json), [`benchmarks/PERF-008-large-scale-compilation.md`](PERF-008-large-scale-compilation.md)  
**Status:** Complete. Evaluated empirical compilation latency, per-invocation queue execution improvement, break-even invocation threshold ($N^*$), and cold-function opt-out policies.

---

## 1. Objective & Amortization Model

The goal of [`PERF-009`](../docs/v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L78) is to establish whether in-memory bytecode generation ([`BytecodeRegionPrototype.java`](../src/main/java/dev/functioncompiler/BytecodeRegionPrototype.java)) and fused interpretation ([`FusedRegionPrototype.java`](../src/main/java/dev/functioncompiler/FusedRegionPrototype.java)) amortize their upfront reload compilation latency and Metaspace memory footprint against repeated runtime execution savings across cold and hot Minecraft function invocations.

### Analytical Model

Let:
- $C_{\text{compile}}$: Upfront compilation latency per compiled region during datapack loading / `/reload`.
- $T_{\text{baseline}}$: Execution time per invocation of the uncompiled interpreted vanilla command queue.
- $T_{\text{compiled}}$: Execution time per invocation of the compiled region (fused or bytecode).
- $\Delta T_{\text{exec}} = T_{\text{baseline}} - T_{\text{compiled}}$: Net runtime reduction per invocation.
- $N$: Number of times the function is invoked across the server lifecycle.

The cumulative execution time after $N$ invocations is:
$$T_{\text{total}}(N) = C_{\text{compile}} + N \cdot T_{\text{compiled}}$$

The break-even invocation threshold $N^*$ is defined as the minimum number of invocations required for cumulative execution time to match baseline uncompiled execution ($N^* \cdot T_{\text{baseline}}$):
$$N^* = \left\lceil \frac{C_{\text{compile}}}{\Delta T_{\text{exec}}} \right\rceil$$

---

## 2. Empirical Inputs from PERF-004 and PERF-008

Data is derived from server-thread measurements in [`PERF-004`](../docs/v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L73) (five randomized 1,000-invocation trials on 5,000-add fixtures) and [`PERF-008`](PERF-008-large-scale-compilation.md) (1,024 generated `.mcfunction` files emitting 1,574 regions and 1,696,208 class bytes):

| Metric | Uncompiled Delegate (`fabric-off`) | Fused Interpreted (`fused-interpreted`) | Bytecode Emitted (`bytecode-emitted`) |
|---|---|---|---|
| **Compilation Latency per Region ($C_{\text{compile}}$)** | $0.00\ \mu\text{s}$ | $\sim 119.8\ \mu\text{s}$ | $\mathbf{19.67\ \mu\text{s}}$ ($30.96\ \text{ms} / 1,574\ \text{regions}$) |
| **Emitted Class Bytes per Region** | $0\ \text{B}$ | $0\ \text{B}$ | $\mathbf{1,077\ \text{B}}$ |
| **Metaspace Growth per Region** | $0.00\ \text{KiB}$ | $0.00\ \text{KiB}$ | $\mathbf{2.03\ \text{KiB}}$ ($3.05\ \text{MiB} / 1,574$) |
| **Median Queue Time per Invoc. (5,000 adds)** | $2.500\ \text{ms}$ | $1.537\ \text{ms}$ | $1.890\ \text{ms}$ |
| **Per-Invocation Saving ($\Delta T_{\text{exec}}$)** | Baseline | $\mathbf{0.963\ \text{ms}}$ ($963\ \mu\text{s}$ / 38.5% faster) | $\mathbf{0.610\ \text{ms}}$ ($610\ \mu\text{s}$ / 24.4% faster) |
| **Per-Operation Saving ($\Delta T_{\text{op}}$)** | Baseline | $\mathbf{0.193\ \mu\text{s}}$ / addition | $\mathbf{0.122\ \mu\text{s}}$ / addition |

---

## 3. Break-Even Invocations Analysis ($N^*$)

### Hot Functions ($N \ge 1$)

Evaluating the break-even threshold for a contiguous scoreboard-addition region:

1. **ASM Bytecode Emission:**
   $$N^*_{\text{bytecode}} = \frac{19.67\ \mu\text{s}}{610\ \mu\text{s}} \approx 0.032 \implies \mathbf{N^* = 1\ \text{invocation}}$$
   Because generating an in-memory class via ObjectWeb ASM and defining it with `defineHiddenClass` requires only **$19.67\ \mu\text{s}$**, whereas executing 5,000 additions via compiled JVM bytecode saves **$610\ \mu\text{s}$** per invocation over vanilla command queue dispatch, the compilation overhead is amortized on the **very first hot invocation**.
   Even for a smaller region of 100 additions:
   $$\Delta T_{\text{exec, 100}} = 100 \times 0.122\ \mu\text{s} = 12.2\ \mu\text{s} \implies N^* = \left\lceil \frac{19.67}{12.2} \right\rceil = \mathbf{2\ \text{invocations}}$$

2. **Fused Interpretation:**
   $$N^*_{\text{fused}} = \frac{119.8\ \mu\text{s}}{963\ \mu\text{s}} \approx 0.124 \implies \mathbf{N^* = 1\ \text{invocation}}$$
   Fused interpretation amortizes on the first call while incurring **zero Metaspace or class-definition overhead**.

---

## 4. Cold Functions & Opt-Out Policy

While hot functions amortize instantaneously ($N^* \le 2$), **cold functions** (functions invoked 0 times, or only executed once during initialization) present negative amortization:
- Functions that never run still incur upfront reload compilation time and Metaspace memory allocations.
- In large datapacks with hundreds of library utilities, compiling all inactive functions bloats Metaspace without runtime return.

### Established Opt-Out Policy

To prevent wasteful compilation of cold functions, the compiler architecture establishes four gating policies:

1. **Region Length Threshold Gating:**
   - Isolated single operations (`run_length = 1`) are never compiled into fused regions or JVM bytecode classes.
   - Contiguous candidate runs must meet a minimum length threshold ($L \ge 3$) before triggering ASM class generation, ensuring savings exceed the 1,077 B class footprint.

2. **Cold Lifecycle Path Opt-Out:**
   - Functions under the `#minecraft:load` lifecycle tag run once during world load and never execute during server gameplay ticks.
   - Initialization functions retain interpreted fallback or fused interpretation without emitting permanent hidden JVM classes.

3. **Deferred / Tiered Compilation (JIT Threshold):**
   - Datapack functions initially execute through vanilla or fused interpretation.
   - Bytecode emission is deferred until an invocation counter passes an execution threshold ($K \ge 5$ calls), ensuring 100% of generated JVM classes target proven hot code paths.

4. **Weak Retention & GC Unloading:**
   - Generated classes are tracked via `WeakReference` in [`BytecodeRegionPrototype.java`](../src/main/java/dev/functioncompiler/BytecodeRegionPrototype.java).
   - Reload cycles drop references to previous function generations; unreferenced classes are reclaimed during GC cycles without memory accumulation.

---

## 5. Summary & Prototype Promotion Guidance

1. **Amortization Speed:** Bytecode emission latency ($19.7\ \mu\text{s}$/region) amortizes on hot functions within 1–2 invocations.
2. **Interpreter Efficiency:** Fused interpretation delivers lower execution queue time (1.537 ms vs 1.890 ms) than bytecode emission with zero Metaspace consumption.
3. **Promotion Gating:** Both prototypes remain disabled by default until real-world datapacks with contiguous multi-add workloads are identified and wider instruction patterns (such as entity `@s` targets) are supported.
