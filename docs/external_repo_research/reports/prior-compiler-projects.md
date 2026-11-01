# Donor Report: Prior Minecraft Function Compilers (MCFC & Mercury)

**Primary Sources:** [`docs/research/mcfc-audit.md`](../../research/mcfc-audit.md), [`docs/research/mercury-audit.md`](../../research/mercury-audit.md)

---

## 1. MCFC (Minecraft Function Compiler)

### Architecture
- **Version Audited:** 0.4.0-alpha.1
- **Approach:** Source-to-source / Java translation. Parses `.mcfunction` files into generated Java source files, compiles them on the fly with `javax.tools.JavaCompiler`, and loads them into a custom ClassLoader.

### Architectural Risks & Lessons
1. **Compilation Latency:** Generating Java source and invoking `javac` in-process imposes massive reload latency (seconds per datapack reload).
2. **ClassLoader Retention:** Custom ClassLoaders retain metaspace memory when functions are repeatedly reloaded unless strictly collected.
3. **Fragility:** Generated code directly references internal obfuscated Mojang mappings, breaking on minor game updates.

### Adoption in Function Compiler
MCFC's source-generation model was **rejected**. Instead, this project uses:
- Direct bytecode generation with OW2 ASM.
- Hidden nestmate classes via `MethodHandles.Lookup.defineHiddenClass` to prevent ClassLoader leaks and ensure instant unloading upon reload.

---

## 2. Mercury

### Architecture
- **Version Audited:** 1.21.4 snapshot
- **Approach:** AST compaction and interpreted virtual machine. Groups sequential basic commands into contiguous blocks and executes them via an internal loop.

### Architectural Lessons
1. **Queue Boundary Respect:** Mercury demonstrated that the primary cost of Minecraft command execution is queue dequeue overhead, not raw arithmetic.
2. **Interpreted Efficiency:** Compacting commands into a single queue entry without full bytecode emission achieves ~40% queue time reduction without JIT complexity or compilation overhead.

### Adoption in Function Compiler
Mercury's fused compaction pattern directly informed [`FusedRegionPrototype.java`](../../../src/main/java/dev/functioncompiler/FusedRegionPrototype.java), which achieved the lowest median queue latency (1.537 ms) in PERF-004 benchmarks.
