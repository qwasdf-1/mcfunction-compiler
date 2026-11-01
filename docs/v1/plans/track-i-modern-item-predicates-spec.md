# Track I Specification: Modern Item & Equipment Predicates

**Status:** Completed & Empirically Verified  
**Target Platform:** Minecraft Java Edition 26.3 · Fabric Dedicated Server (`net.fabricmc.fabric-loader:0.20.1`)  
**Parent Roadmap:** [`docs/v1/plans/v1-production-roadmap.md`](v1-production-roadmap.md)  
**Verification Target:** 100% Differential Parity with Vanilla 26.3 `ExecuteCommand` Items Predicate

---

## 1. Problem Statement & Motivation

Minecraft 1.20.5+ / 26.3 introduced modern item predicate conditionals:
```mcfunction
execute if items entity @e[tag=fc_i_agent,limit=1] weapon.mainhand diamond_sword run scoreboard players set #has_item fc_probe 1
execute unless items entity @e[tag=fc_i_agent,limit=1] weapon.mainhand iron_sword run scoreboard players set #missing_item fc_probe 2
```

### The Vanilla Bottleneck
In vanilla, evaluating `if/unless items` instantiates item accessor streams, filters slots, and manages sub-frame execution contexts for each condition check. When chained with entity selectors, this induces unnecessary scheduler queue churn.

---

## 2. Architecture & Design

Track I introduces [`ItemPredicateParser.java`](../../../src/main/java/dev/functioncompiler/ItemPredicateParser.java), bridging modern item slot checks directly into [`PredicateConditionCommand.java`](../../../src/main/java/dev/functioncompiler/PredicateConditionCommand.java):

```mermaid
flowchart TD
    A["execute if/unless items <target> <slots> <predicate>"] --> B["ItemPredicateParser.parse()"]
    B --> C["Extract RedirectModifier & Evaluator"]
    C --> D["PredicateConditionCommand (FusableCommand)"]
    D --> E["In-Memory Slot Count & Evaluation with Zero Sub-Frames"]
```

### Key Semantics Preserved
1. **Direct Evaluator Delegation:** Evaluates items using the native `RedirectModifier` attached to the Brigadier context, ensuring exact component matching, item tags, count boundaries, and slot sources (`weapon.*`, `armor.*`, `container.*`).
2. **Unless Logic:** Inverts boolean matches cleanly without allocating intermediate failure frames.
3. **Fusable Execution:** Combines seamlessly with fused arithmetic, store operations, and bytecode regions.

---

## 3. Empirical Verification Results

Differential verification executed across `vanilla`, `fabric-on`, and `bytecode-emitted`:

| Metric / Probe | Vanilla | Fabric-On | Bytecode-Emitted | Parity |
| :--- | :--- | :--- | :--- | :--- |
| `has_item` (`if items ... diamond_sword`) | 1 | 1 | 1 | 100.0% Exact |
| `missing_item` (`unless items ... iron_sword`) | 2 | 2 | 2 | 100.0% Exact |

---

## 4. Engineering Auditor Compliance

- Total Findings: 94 (Budget: $\le 94$)
- Source Lines: Compliant with $\le 1,500$ line limit
- Offline Build: Verified (`FC_GRADLE_OFFLINE=true ./gradlew --offline build`)
