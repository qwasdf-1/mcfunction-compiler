# Donor Report: Real-World Datapack Workloads & Profiling

**Primary Sources:** [`docs/research/tick-heavy-datapack-candidates.md`](../../research/tick-heavy-datapack-candidates.md), [`docs/research/real-world-profile-targets.md`](../../research/real-world-profile-targets.md)

---

## 1. Candidate Workload Screening

To avoid optimizing for synthetic fixtures, real-world datapacks were screened against Minecraft 26.3:

| Datapack | Version | Workload Profile | Suitability for Compiler Evaluation |
|---|---|---|---|
| **Vein Miner (Cloudburst)** | 5.3.0 | Heavy macro invocations with entity `data` (`with entity @e[...] data`), recurring `#head` scoreboard increments, recursive branch scheduling. | **Primary target for macro specialization.** Demonstrates substantial serialization bottleneck. |
| **VeinMiner (Miraculixx)** | 1.3.6 | Single-tick vein destruction, lower recursion depth, less macro reliance. | Secondary comparative baseline. |
| **Ship In A Bottle** | Latest | Heavy `#minecraft:tick` function loops, armor stand raycasting, block display transforms. | Screened; heavy block interaction limits basic scoreboard gains. |
| **BlastBack** | Latest | Physics simulation via vector scoreboard arithmetic. | Good potential target for scoreboard operations once complex selectors are supported. |

---

## 2. Profiling Insights: Macro Serialization Bottleneck

Spark profiles on a 6×6×6 Vein Miner event identified:
- Over 80% of function execution time in macro calls was spent inside:
  `net.minecraft.world.entity.Entity.saveWithoutId` → `CompoundTag.copy` → `NbtPathArgument$CompoundPathNode.get`.
- The actual macro function only needed `{amount: 1}` from the entity's custom data.
- This finding established the empirical justification for [`SelectiveMacroArgumentPrototype`](../../../src/main/java/dev/functioncompiler/SelectiveMacroArgumentPrototype.java).

---

## 3. Contiguous Instruction Screening for Fused & Bytecode Evaluation

To evaluate prototype promotion readiness for [`FusedRegionPrototype`](../../../src/main/java/dev/functioncompiler/FusedRegionPrototype.java) and [`BytecodeRegionPrototype`](../../../src/main/java/dev/functioncompiler/BytecodeRegionPrototype.java), 18 real-world datapack archives and candidate repositories were analyzed for contiguous runs of adjacent scoreboard addition commands:

| Candidate Datapack | Files | Total Lines | Total `ScoreAdd` | Other Score Cmds | Max Contiguous Run | Runs $\ge 2$ | Screening Classification |
|---|---|---|---|---|---|---|---|
| **Vein Miner (Cloudburst 5.3.0)** | 76 | 771 | 24 | 78 | **19** | 1 | 19-addition run in `player/register.mcfunction` initializing `@s` objectives. |
| **Bookshelf Generation 4.2.1** | 66 | 1,523 | 36 | 47 | **3** | 2 | Two 3-addition runs in `enumerate/generation` and `load` on literal fake-holder `$bs.generation.*`. |
| **A-Star Pathfinding** | 18 | 181 | 5 | 28 | **2** | 1 | 2-addition run in `step_up` mixing `@s` and literal holder `vertical`. |
| **BlastBack (Hotfix 3)** | 21,318 | 269,169 | 14 | 430 | 1 | 0 | 266k `execute` lines; all 14 `ScoreAdd` operations are isolated single commands. |
| **BlazeandCaves Advancements 1.21.1** | 5,436 | 173,886 | 24 | 233 | 1 | 0 | All 24 additions are isolated single-command occurrences. |
| **Hostile Mobs Over Time 2.3** | 397 | 4,935 | 7 | 349 | 1 | 0 | Heavily uses macro templates; all 7 additions isolated. |
| **Datapack Function Library 5.1.0** | 98 | 446 | 0 | 12 | 0 | 0 | Uses macros and execute stores; no raw `ScoreAdd`. |
| **Dynamic Torches 5.4** | 10 | 124 | 0 | 11 | 0 | 0 | Raycasting and block checks; no contiguous additions. |
| **Simple Timer 1.2** | 4 | 84 | 1 | 9 | 1 | 0 | 1 isolated addition. |
| **Others (Day-Night, Clings, XP, TNT)** | < 10 ea | < 100 ea | 0–2 | 1–11 | 0–1 | 0 | Short utility scripts; no contiguous runs. |

### Prototype Gating Recommendation
1. **Target Expansion:** The `ScoreAddPrototype` now supports unconstrained `@s` self-selectors in addition to literal fake holders (`#...`), unlocking the 19-addition run in Vein Miner's `data/vm/function/player/register.mcfunction` for fused interpretation and ASM bytecode compilation.
2. **Prevalence in Unmodified Datapacks:** In unmodified real-world packs, contiguous scoreboard additions are primarily clustered in player registration routines and load-time setup scripts (e.g. Bookshelf Generation and Vein Miner).
3. **Promotion Decision:** Prototypes must remain **disabled by default**. Enabling them provides no performance benefit on mainstream datapacks until broader instruction types (e.g. `operation`, `execute store`) or full macro compilation are supported.
