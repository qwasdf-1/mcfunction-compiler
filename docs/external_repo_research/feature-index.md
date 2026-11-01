# External Repository Feature Index

This index connects compiler optimization areas with external mod donors,
prior compiler research, and real-world datapack workloads.

---

## 1. Feature to Donor Mapping

| Compiler Concern | External Systems & Donors | Relevant Reports | Key Lessons & Impact |
|---|---|---|---|
| **Macro Serialization Avoidance** | Vein Miner 5.3.0, Vanilla 26.3 `FunctionCommandInvoker` | [`reports/datapack-workloads.md`](reports/datapack-workloads.md) | Entity NBT serialization is the primary bottleneck for entity-backed macros; selective parameter extraction yields ~24–35% speedup. |
| **Entity NBT Access & Filtering** | Bellows 1.1.2/1.1.3 | [`reports/bellows-mod-investigation.md`](reports/bellows-mod-investigation.md) | Bellows filters entity NBT fields for performance, stripping `home_pos` on mobs; requires a verified adapter ([`BellowsEntityFilterAdapter`](../../src/main/java/dev/functioncompiler/mixin/BellowsHomePosAdapterMixin.java)) to maintain vanilla behavior. |
| **Command Compaction & Inlining** | MCFC (0.4.0-alpha.1) | [`reports/prior-compiler-projects.md`](reports/prior-compiler-projects.md) | Compiling directly to Java source is fragile across game versions and risks ClassLoader bloat. In-memory ASM hidden classes with fallback is significantly safer. |
| **Interpreted Queue Acceleration** | Mercury (1.21.4) | [`reports/prior-compiler-projects.md`](reports/prior-compiler-projects.md) | Fused interpreted execution often matches or exceeds JIT-compiled bytecode for short command runs due to method handle dispatch overhead. |
| **Compatibility Mod Interactions** | Lithium 0.26.2, Moonrise 1.2.0/1.2.1 | [`reports/datapack-workloads.md`](reports/datapack-workloads.md) | Third-party Mixin collisions on `ServerFunctionManager` and entity lookups require differential multi-mode testing. |
