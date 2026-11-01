# Scoreboard Specialization (`ScoreAddPrototype`)

**Status:** Production implementation verified; promoted in v1.0.  
**Configuration Key:** Controlled via `"enable_fused_regions": true` (in `config/function-compiler.json`)  
**Owner Classes:** [`ScoreAddPrototype.java`](../../../src/main/java/dev/functioncompiler/ScoreAddPrototype.java), [`ScoreAddCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreAddCommand.java), [`ScoreOperationCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreOperationCommand.java), [`ScoreResetCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreResetCommand.java), [`ScoreConditionCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreConditionCommand.java), [`ScoreStoreCommand.java`](../../../src/main/java/dev/functioncompiler/ScoreStoreCommand.java)  
**Test IDs:** [`SCORE-001`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L21) through [`SCORE-015`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L91)

---

## 1. Design & Scope

In vanilla Minecraft 26.3, executing `scoreboard players <add|set|remove|operation|reset>` traverses:
1. Brigadier command node resolution and syntax parsing
2. Argument extraction and type validation
3. Objective lookup and read-only criteria checks in `ServerScoreboard`
4. Score access, integer arithmetic, and 32-bit overflow handling
5. Command response tracker feedback generation and scoreboard change broadcasting

The scoreboard specialization engine pre-resolves objectives and target holders during function compilation, replacing runtime dispatcher traversal with zero-allocation integer arithmetic and direct memory operations.

---

## 2. Supported Command Shapes

A command is eligible for scoreboard specialization if and only if:
1. **Mutation Commands (`add`, `set`, `remove`):**
   - Command pattern is `scoreboard players <add|set|remove> <targets> <objective> <score>`
   - Target holder is either a literal fake player (name starting with `#`, e.g. `#fcprobe`) or the unconstrained self-selector `@s` (which dynamically resolves to `source.getEntity()` at execution time, falling back to vanilla delegation if invoked without an entity context)
   - Objective is a valid existing objective name
   - Amount is a literal signed 32-bit integer (`int`)
2. **Operation Commands (`operation`):**
   - Command pattern is `scoreboard players operation <targets> <targetObjective> <operation> <source> <sourceObjective>`
   - Both target and source holders are either literal fake players (`#...`) or unconstrained self-selectors (`@s`)
   - Objectives exist and target objective is writable (not read-only)
   - Operation is one of the 9 vanilla scoreboard operations: `+=`, `-=`, `*=`, `/=`, `%=`, `=`, `<`, `>`, `><`
3. **Reset Commands (`reset`):**
   - Command pattern is `scoreboard players reset <targets> [<objective>]`
   - Target holder is either a literal fake player (`#...`) or the unconstrained self-selector (`@s`)
   - Objective, if present, is a valid existing objective name; if omitted, resets all objectives for the holder
4. **Condition Commands (`if/unless score`):**
   - Command pattern is `execute if/unless score <targets> <targetObjective> <op> <source> <sourceObjective>` or `matches <range>`
   - Target and source holders are fake players or `@s`
   - Direct integer comparison against `ServerScoreboard`
5. **Store Commands (`store result/success score`):**
   - Command pattern is `execute store result/success score <targets> <targetObjective> run ...`
   - Writes the numeric outcome of the executed child command directly to the destination score holder

Any other command form—including multi-entity selectors (`@e`, `@a`, `@p`), complex selector arguments with filters (`@s[...]`), relative modifications, or variable sources—retains vanilla command delegation. Eligible specialized commands implement [`FusableCommand.java`](../../../src/main/java/dev/functioncompiler/FusableCommand.java) and are grouped into contiguous regions via [`FusedRegionPrototype.java`](../../../src/main/java/dev/functioncompiler/FusedRegionPrototype.java).

---

## 3. Observable Parity Contract

The specialized path guarantees exact observable parity with mod-free vanilla:
- **Missing Objectives:** Throws the identical `CommandSyntaxException` if the objective is missing.
- **Divide by Zero:** Throws vanilla's `ERROR_DIVIDE_BY_ZERO` syntax exception on `/=` or `%=` by zero.
- **Signed 32-Bit Wrapping:** Under/overflow wraps exactly as Java `int` addition and multiplication according to vanilla Minecraft scoreboard rules.
- **Side Effects & Listeners:** Updates the scoreboard instance directly, firing vanilla score change events and updating displays.
- **External Mutations & Resets ([`SCORE-011`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L32)):** Does not cache stale score values or score handles. External modifications via commands or mod APIs (`set`, `add`, `reset`) are reflected immediately on subsequent calls without stale state or desync.
- **Feedback & Tracking:** Replicates vanilla tracker responses using [`ScoreboardCommandAccessor.java`](../../../src/main/java/dev/functioncompiler/mixin/ScoreboardCommandAccessor.java) (`RESPONSE_SCORE_ADD`, `RESPONSE_SCORE_SET`, `RESPONSE_SCORE_REMOVE`, `RESPONSE_SCORE_OPERATION`, `RESPONSE_SCORE_RESET`, `RESPONSE_SCORE_RESET_ALL`).

---

## 4. Performance & Integration

Across isolated trials, single specialized commands produce modest gains because scheduler overhead dominates individual commands. However, when grouped into contiguous fused regions ([`PERF-012`](../../../benchmarks/PERF-012-macro-region-compilation.md)), contiguous scoreboard mutations achieve **90.9% queue reduction** and a **+37.17% median speedup**.
