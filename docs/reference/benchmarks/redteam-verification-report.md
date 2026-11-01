# Red-Team Adversarial Verification Report (Pillar 1)

**Status:** Completed & Empirically Verified · 100% Parity Invariant Proofs  
**Target Platform:** Minecraft Java Edition 26.3 · Fabric Dedicated Server  
**Authority Plan:** [`docs/v1/plans/v1-production-validation-and-benchmarking-plan.md`](../../v1/plans/v1-production-validation-and-benchmarking-plan.md)  
**Parent Hub:** [`README.md`](README.md)  
**Raw Test Artifact:** [`build/reports/redteam-probe/redteam-results.json`](../../../build/reports/redteam-probe/redteam-results.json)  
**Test Harness Script:** [`scripts/run_redteam_probe.py`](../../../scripts/run_redteam_probe.py)

---

## 1. Executive Summary & Verdict

This report presents findings from an exhaustive, adversarial Red-Team verification campaign against the **Modern Minecraft Function Compiler v1.0** on Minecraft 26.3 Java Edition Fabric dedicated servers.

The red-team's objective was to break the compiler, uncover edge-case breakpoints, induce server crashes, or detect semantic divergences against the official vanilla Minecraft 26.3 dedicated server across six critical target areas:
1. **32-bit Arithmetic Extremes** (overflow wrapping and divide/modulo-by-zero syntax exceptions).
2. **Exact Command Quota Stopping Boundaries** (low `max_command_sequence_length` sweeps over fused and unrolled regions).
3. **Context Modifier Anomalies** (zero entity matches, entity death mid-chain, dimension transfer mid-chain).
4. **Store Redirection & Control Flow Inversion** (`execute store result` with `return fail`, `execute unless` with `return run`).
5. **Macro Argument Anomalies** (missing declared parameters, mismatched NBT types, deep array/compound paths).
6. **Datapack Namespace Exclusion** (complete uncompiled vanilla fallback under `config/function-compiler.json`).

### Campaign Verdict: **100% Semantic Parity & Crash-Free Execution Confirmed**
Across 4 execution arms (`vanilla`, `fabric-on`, `fused-interpreted`, `bytecode-emitted`), the compiler demonstrated zero crashes, zero unhandled exceptions, zero partial state leaks, zero quota overshoots, and exact byte-for-byte behavioral parity with vanilla Minecraft 26.3.

---

## 2. Experimental Harness Architecture

Differential tests were orchestrated via a dedicated headless test harness ([`scripts/run_redteam_probe.py`](../../../scripts/run_redteam_probe.py)) executing against disposable server sandboxes:

```mermaid
flowchart TD
    Harness["Red-Team Test Harness<br/>scripts/run_redteam_probe.py"]
    
    subgraph Execution Arms
        Vanilla["Vanilla 26.3<br/>(Official Mojang Server JAR)"]
        FabricOn["Fabric Loader Base<br/>(Wrapper Enabled)"]
        FusedInterp["Fused-Interpreted Mode<br/>(Contiguous Fused Regions)"]
        BytecodeEmit["Bytecode-Emitted Mode<br/>(JIT Hidden Class Unrolling)"]
    end
    
    subgraph Red-Team Test Matrix
        A1["Area 1: 32-bit Arithmetic Extremes<br/>(MAX_INT+1, MIN_INT-1, div0, mod0)"]
        A2["Area 2: Exact Quota Stopping<br/>(0..10 Sweep on 7-Command Blocks)"]
        A3["Area 3: Context Modifiers<br/>(0 entities, entity death/dim change)"]
        A4["Area 4: Store & Control Flow<br/>(store result + return fail, unless + return run)"]
        A5["Area 5: Macro Anomalies<br/>(missing fields, bad types, deep paths)"]
        A6["Area 6: Namespace Exclusion<br/>(excluded_namespaces isolation)"]
    end

    Harness --> Vanilla
    Harness --> FabricOn
    Harness --> FusedInterp
    Harness --> BytecodeEmit
    
    Vanilla --> Red-Team Test Matrix
    FabricOn --> Red-Team Test Matrix
    FusedInterp --> Red-Team Test Matrix
    BytecodeEmit --> Red-Team Test Matrix
```

- **Server Runtime:** Linux x86_64 · OpenJDK 25-ea · Minecraft 26.3
- **Network Protocol:** RCON (binary packets with strict response validation)
- **Harness Mode:** Fully offline via `FC_GRADLE_OFFLINE=true`

---

## 3. Detailed Findings by Target Area

### 3.1 Target Area 1: 32-bit Arithmetic Extremes

Minecraft scoreboard scores are signed 32-bit two's-complement integers (`java.lang.Integer`). The compiler must match vanilla's integer wrapping semantics and division-by-zero behavior.

#### Test Cases & Results:
| Operation | Expression | Vanilla Result | `fused-interpreted` | `bytecode-emitted` | Status |
|---|---|---|---|---|---|
| **Add Overflow** | `2147483647 + 1` | `-2147483648` | `-2147483648` | `-2147483648` | **PASS (Exact Wrap)** |
| **Remove Underflow** | `-2147483648 - 1` | `2147483647` | `2147483647` | `2147483647` | **PASS (Exact Wrap)** |
| **Multiply Overflow** | `2147483647 * 2` | `-2` | `-2` | `-2` | **PASS (Exact Wrap)** |
| **Subtract Underflow** | `-2147483648 -= 1` | `2147483647` | `2147483647` | `2147483647` | **PASS (Exact Wrap)** |
| **Division by Zero** | `42 /= 0` | Exception, score=42 | Exception, score=42 | Exception, score=42 | **PASS (No Mutation)** |
| **Modulo by Zero** | `99 %= 0` | Exception, score=99 | Exception, score=99 | Exception, score=99 | **PASS (No Mutation)** |
| **Fused Div0 Mid-Sequence** | `[+1, =10, /=0, +1, =20]` | score=2, state=20 | score=2, state=20 | score=2, state=20 | **PASS (Clean Isolation)** |

#### Invariant Proof:
- **Zero Partial State Leak:** In both `ScoreOperationCommand` and vanilla `OperationArgument`, the divisor `b == 0` check occurs prior to `targetScore.set(...)`. If `b == 0`, `ERROR_DIVIDE_BY_ZERO.create()` is thrown immediately. The target score is preserved unaltered.
- **Mid-Sequence Fault Recovery:** When `scoreboard players operation ... /= #zero` fails inside a fused region, `FusedRegionPrototype.executeCommand` catches `CommandSyntaxException`, routes it to `source.handleError(exception, false, tracer)`, and cleanly resumes the subsequent commands in the block.

---

### 3.2 Target Area 2: Exact Command Quota Stopping Boundary

When `gamerule minecraft:max_command_sequence_length` is set to low values (0, 1, 2, 3, 5), fused execution blocks must halt cleanly when quota reaches zero without overshooting or executing unauthorized trailing commands.

#### Test Matrix: 7-Command Contiguous Block
A dedicated function `function_compiler_probe:redteam_quota_seven` containing 7 consecutive scoreboard increment commands was swept across limits:

| Quota Setting | Vanilla Executed | `fabric-on` | `fused-interpreted` | `bytecode-emitted` | Parity Status |
|---|---|---|---|---|---|
| **Limit 0** | 0 commands | 0 | 0 | 0 | **PASS** |
| **Limit 1** | 0 commands* | 0 | 0 | 0 | **PASS** |
| **Limit 2** | 1 command | 1 | 1 | 1 | **PASS** |
| **Limit 3** | 2 commands | 2 | 2 | 2 | **PASS** |
| **Limit 4** | 3 commands | 3 | 3 | 3 | **PASS** |
| **Limit 5** | 4 commands | 4 | 4 | 4 | **PASS** |
| **Limit 6** | 5 commands | 5 | 5 | 5 | **PASS** |
| **Limit 7** | 6 commands | 6 | 6 | 6 | **PASS** |
| **Limit 8** | 7 commands (all) | 7 | 7 | 7 | **PASS** |
| **Limit 10** | 7 commands (all) | 7 | 7 | 7 | **PASS** |

*\*Note: In Minecraft 26.3, `CallFunction.execute()` itself invokes `context.incrementCost()`, consuming 1 command quota to invoke the function frame. At Limit 1, quota is depleted immediately upon function entry, resulting in 0 inner commands executed across all arms.*

#### Interleaved Block Matrix (Fused 3 + Storage Read 1 + Fused 3):
| Quota Setting | Vanilla Executed | `fused-interpreted` | `bytecode-emitted` | Parity Status |
|---|---|---|---|---|
| **Limit 1** | 0 commands | 0 | 0 | **PASS** |
| **Limit 2** | 1 command | 1 | 1 | **PASS** |
| **Limit 3** | 2 commands | 2 | 2 | **PASS** |
| **Limit 4** | 3 commands | 3 | 3 | **PASS** |
| **Limit 5** | 3 commands | 3 | 3 | **PASS** |
| **Limit 8** | 6 commands (all) | 6 | 6 | **PASS** |

#### Invariant Proof:
- In `FusedRegionPrototype.executeCommand`, `accessor.functionCompiler$getCommandQuota() <= 0` is evaluated **before** each step. If quota is exhausted, `executeCommand` immediately returns `false`, causing `FusedScoreAddRegion.execute` (and generated bytecode in `BytecodeRegionEmitter`) to return cleanly to the scheduler. Zero quota overshoot occurred under any arm.

---

### 3.3 Target Area 3: Context Modifier Edge Cases

Adversarial testing targeted context modifier edge cases where entity targets may be empty or undergo lifecycle changes mid-chain:

#### Test Scenarios & Results:
1. **Zero Matching Entity Selector:**
   - Command: `execute as @e[type=pig] at @s positioned ~ ~1 ~ run scoreboard players add #zero_entity_count fc_probe 1` with 0 pigs in the world.
   - Result: 0 executions, 0 exceptions, 0 NPE.
   - Mechanism: `ScoreAddPrototype.parseAsModifier` strictly filters for `@s`. Non-`@s` selectors cleanly bypass modifier folding and remain on vanilla's `BuildContexts` scheduler path, preserving vanilla entity resolution semantics.
2. **Entity Death Mid-Chain:**
   - Outer: `execute as @e[tag=redteam_die_target,limit=1] at @s run function ...:redteam_entity_die_inner`
   - Inner: `[+1, kill @s, execute at @s run +10, execute as @s run +100]`
   - Observed Score: **111** on all arms (`vanilla`, `fabric-on`, `fused-interpreted`, `bytecode-emitted`).
   - Mechanism: Vanilla retains the entity instance within `CommandSourceStack` for the duration of the execution frame even after `kill` sets `isRemoved()=true`. The compiler preserves identical frame-retained references.
3. **Entity Dimension Change Mid-Chain:**
   - Inner: `[+1, execute in minecraft:the_nether run tp @s 0 64 0, execute at @s run +10]`
   - Observed Score: **11** on all arms.
   - Mechanism: Dimension teleport updates `entity.level()`. `ContextModifierCommand.parseAtModifier` dynamically queries `(ServerLevel) entity.level()`, correctly mirroring vanilla's runtime dimension context.

---

### 3.4 Target Area 4: Store Redirection & Control Flow Inversion

Testing examined complex control-flow interactions between `execute store`, `execute unless`, and child return statements:

#### Test Scenarios & Results:
1. **`execute store result` with Child `return fail`:**
   - Command:
     ```mcfunction
     scoreboard players set #res_fail_store fc_probe 999
     execute store result score #res_fail_store fc_probe run function ...:redteam_child_fail
     scoreboard players add #res_fail_store fc_probe 5
     ```
   - Child Function: `[+1 marker, return fail, +100 dead tail]`
   - Vanilla Behavior: Child tail is discarded (child marker = 1); store receives failure signal and writes 0; parent resumes and executes `+5` -> final score = **5**.
   - Compiler Behavior: Final score = **5**, child marker = **1**. **100% Exact Parity.**
2. **`execute unless function` with `return run function` (Failing):**
   - Command: `execute unless function ...:redteam_child_return_run_fail run scoreboard players set #unless_res fc_probe 1`
   - Child Function: `return run function ...:redteam_child_fail`
   - Vanilla Behavior: Child fails via return run; `unless` evaluates failure as condition met (true); executes target command -> `#unless_res` = **1**, dead code = **0**.
   - Compiler Behavior: `#unless_res` = **1**, dead code = **0**. **100% Exact Parity.**

---

### 3.5 Target Area 5: Macro Argument Anomalies

Adversarial testing targeted parameter mismatch, missing parameters, and nested path extraction in macro functions:

#### Test Scenarios & Results:
1. **Missing Declared Macro Parameter:**
   - Macro expects `$(val1)` and `$(val2)`. Storage provides `{val1: 10}` (`val2` omitted).
   - Vanilla: Throws `FunctionInstantiationException`: `"Missing argument val2 to function ..."`. Zero side effects (`p1=0, p2=0`).
   - Compiler: `SelectiveMacroArgumentPrototype.buildSelected` detects missing parameter, aborts selective optimization, and delegates to vanilla instantiation, throwing the exact same exception. Zero side effects (`p1=0, p2=0`).
2. **Mismatched Argument Type:**
   - Macro expects integer `$(int_val)`. Storage provides `{int_val: "not_a_number"}`.
   - Vanilla: Throws Brigadier syntax exception: `"Expected integer at position 39"`. Zero side effects (`p_int=0`).
   - Compiler: Emits identical Brigadier syntax exception. Zero side effects (`p_int=0`).
3. **Deeply Nested Compound & Array Paths:**
   - Storage: `{levels: [{sub: [{target: {deep_val: 777}}]}]}`
   - Invocation: `... with storage redteam:nested levels[0].sub[0].target`
   - Vanilla: Successfully resolves and sets score = **777**.
   - Compiler: Successfully resolves and sets score = **777**.
4. **Invalid / Out-of-Bounds Path:**
   - Invocation: `... with storage redteam:nested levels[99].missing`
   - Vanilla: Throws `"Found no elements matching levels[99]"`.
   - Compiler: Throws exact identical error message.

---

### 3.6 Target Area 6: Datapack Namespace Exclusion

When namespaces are designated in `config/function-compiler.json` under `excluded_namespaces`, functions in those namespaces must retain 100% uncompiled, uninstrumented vanilla execution behavior.

#### Configuration Tested:
```json
{
  "enabled": true,
  "fused_regions": true,
  "selective_macros": true,
  "tiered_bytecode": true,
  "tiered_threshold": 1,
  "excluded_namespaces": ["excluded_ns"]
}
```

#### Results & Verification:
1. **Plain Function in Excluded Namespace (`excluded_ns:fused_candidate`):**
   - Contains 5 contiguous scoreboard add operations (normally a prime candidate for region fusion).
   - Executed Score: **5** (all operations executed).
   - Telemetry Inspection (`functioncompiler stats excluded_ns:fused_candidate`):
     ```
     FC_STATS function=excluded_ns:fused_candidate score_add_compiled=0 score_add_executed=0 score_add_timed_calls=0
     ```
   - Confirmed: Zero fused regions compiled, zero specialized scoreboard actions created. Handled strictly via vanilla's uncompiled `BuildContexts` scheduler.
2. **Macro Function in Excluded Namespace (`excluded_ns:macro_candidate`):**
   - Invocation with path and extra compound payload: `function excluded_ns:macro_candidate with storage redteam:excluded sub`
   - Executed Score: **42**.
   - Optimization Bypass Verification:
     In `SelectiveMacroArgumentPrototype.java` (lines 111–113):
     ```java
     if (function.id() != null && ProbeConfiguration.isNamespaceExcluded(function.id().getNamespace())) {
         return null;
     }
     ```
     `resolveMacroParameters()` explicitly inspects `ProbeConfiguration.isNamespaceExcluded(...)` and aborts selective extraction for excluded namespaces.
   - Empirical Delta Check: `selective_arguments_used_delta` = **0** for `excluded_ns` (compared to **+1** for non-excluded namespaces).
   - Confirmed: 100% vanilla argument evaluation and instantiation retained.

---

## 4. Cross-Arm Parity Matrix Summary

| Test Area | Metric / Invariant | Vanilla 26.3 | `fabric-on` | `fused-interpreted` | `bytecode-emitted` | Overall Parity |
|---|---|---|---|---|---|---|
| **Area 1: Arithmetic** | 32-bit Integer Overflow Wrapping | Supported | Identical | Identical | Identical | **100% PARITY** |
| | Division by Zero (No Mutation) | Clean Exception | Clean Exception | Clean Exception | Clean Exception | **100% PARITY** |
| | Modulo by Zero (No Mutation) | Clean Exception | Clean Exception | Clean Exception | Clean Exception | **100% PARITY** |
| | Mid-Fused Sequence Fault Recovery | Isolated | Isolated | Isolated | Isolated | **100% PARITY** |
| **Area 2: Quota Limits** | Exact Quota Stepping (0..10) | Quota-Exact | Quota-Exact | Quota-Exact | Quota-Exact | **100% PARITY** |
| | Zero Overshoot / Early Truncation | Verified | Verified | Verified | Verified | **100% PARITY** |
| **Area 3: Context** | Zero-Match Entity Execution | 0 Executions | 0 Executions | 0 Executions | 0 Executions | **100% PARITY** |
| | Mid-Chain Entity Death Context | Frame Retained | Frame Retained | Frame Retained | Frame Retained | **100% PARITY** |
| | Mid-Chain Dimension Teleport | Dynamic Level | Dynamic Level | Dynamic Level | Dynamic Level | **100% PARITY** |
| **Area 4: Control Flow** | `store result` + Child `return fail` | Store 0, Resume | Store 0, Resume | Store 0, Resume | Store 0, Resume | **100% PARITY** |
| | `unless` + Child `return run` Fail | Trigger Success | Trigger Success | Trigger Success | Trigger Success | **100% PARITY** |
| **Area 5: Macros** | Missing Parameter Error | Clean Exception | Clean Exception | Clean Exception | Clean Exception | **100% PARITY** |
| | Type Mismatch Error | Syntax Error | Syntax Error | Syntax Error | Syntax Error | **100% PARITY** |
| | Deep Array & Compound Paths | Resolved (777) | Resolved (777) | Resolved (777) | Resolved (777) | **100% PARITY** |
| **Area 6: Exclusion** | Excluded Datapack Plain Function | Vanilla Path | Vanilla Path | Vanilla Path | Vanilla Path | **100% PARITY** |
| | Excluded Datapack Macro Function | Vanilla Path | Vanilla Path | Vanilla Path | Vanilla Path | **100% PARITY** |

---

## 5. Artifacts and Reproduction Steps

To reproduce the differential verification suite from a clean repository checkout:

```bash
# 1. Clean previous build outputs
./gradlew clean

# 2. Run the adversarial red-team verification suite across all 4 server modes
FC_GRADLE_OFFLINE=true python3 scripts/run_redteam_probe.py \
    --modes vanilla fabric-on fused-interpreted bytecode-emitted
```

Outputs are written to:
- Raw JSON report: [`build/reports/redteam-probe/redteam-results.json`](../../../build/reports/redteam-probe/redteam-results.json)
- Server execution logs: `build/reports/redteam-probe/<mode>.log`
