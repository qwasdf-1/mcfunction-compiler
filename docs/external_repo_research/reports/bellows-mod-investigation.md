# Donor Report: Bellows Mod Investigation

**Target:** Bellows 1.1.2 & 1.1.3 on Minecraft 26.3 Fabric  
**Audit Source:** [`docs/research/bellows-audit.md`](../../research/bellows-audit.md)  
**Adapter Implementation:** [`BellowsEntityFilterAdapter.java`](../../../src/main/java/dev/functioncompiler/mixin/BellowsHomePosAdapterMixin.java)

---

## 1. Overview & Optimization Strategy

Bellows optimizes Minecraft command execution and entity data queries by:
1. Intercepting entity selector parsing to bypass entity manager iteration where possible.
2. Filtering NBT serialization paths to prevent deep compound cloning during entity inspection.
3. Accelerating scoreboard operations via custom lookups.

---

## 2. Incompatibility & Behavioral Divergence

During compatibility qualification on Minecraft 26.3, two critical divergences were identified:

### Mob `home_pos` Stripping
Bellows 1.1.2 filtered entity NBT fields aggressively, omitting `home_pos` on mobs during NBT queries. This broke datapacks relying on entity position tags.
- **Resolution:** Implemented [`BellowsEntityFilterAdapter.java`](../../../src/main/java/dev/functioncompiler/mixin/BellowsHomePosAdapterMixin.java), restoring `home_pos` in init, merge, modify, and remove paths.

### Entity Lookup Shadow Collision
On Bellows 1.1.3 with Moonrise 1.2.1, server startup failed due to a missing `EntityLookup.entityById` Mixin shadow method.
- **Resolution:** Recorded in test matrix; combination is excluded until third-party upstream alignment.

---

## 3. Workload Parity Findings

In PERF-005/006 (synthetic selector and entity-NBT benchmarks), Bellows reduced `ServerFunctionManager` sample share by 67.6% on the NBT fixture. However, on real-world datapacks like Vein Miner 5.3.0, Bellows 1.1.2 stalled execution ticks, necessitating Bellows 1.1.3 qualification.
