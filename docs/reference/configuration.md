# Configuration & Admin Interface Reference (v1.0)

**Target Platform:** Minecraft 26.3 · Fabric Dedicated Server  
**Configuration File:** `config/function-compiler.json`  
**Owner Classes:** [`CompilerConfig.java`](../../src/main/java/dev/functioncompiler/CompilerConfig.java), [`ProbeCommands.java`](../../src/main/java/dev/functioncompiler/ProbeCommands.java), [`ProbeStatus.java`](../../src/main/java/dev/functioncompiler/ProbeStatus.java)  
**Verification ID:** [`CONFIG-001`](../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L95)

---

## 1. Configuration File (`config/function-compiler.json`)

The compiler automatically creates a default configuration file at `config/function-compiler.json` inside the server root upon startup if one does not exist.

### Production Schema & Default Values

```json
{
  "enabled": false,
  "score_add": false,
  "fused_regions": false,
  "selective_macros": true,
  "tiered_bytecode": false,
  "tiered_threshold": 5,
  "excluded_namespaces": []
}
```

### Options Description

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | boolean | `false` | Master switch. When `false`, compiler wrapping and optimization surfaces are disabled unless a focused probe sets their `FC_*` environment variables. |
| `score_add` | boolean | `false` | Enables parsed literal scoreboard specialization on an enabled wrapper. |
| `fused_regions` | boolean | `false` | Enables contiguous command fusing, context modifier folding, scoreboard condition/store interception, block/entity predicates, and storage data mutations. |
| `selective_macros` | boolean | `true` | Enables selective extraction of declared macro parameter keys directly from entity custom data and storage targets, bypassing full NBT compound serialization. |
| `tiered_bytecode` | boolean | `false` | Enables the ASM hidden class bytecode compilation backend for hot function regions. |
| `tiered_threshold` | integer | `5` | The number of times a region executes via interpreted fusion before automatically compiling to unrolled JVM bytecode (active only when `tiered_bytecode` is `true`). |
| `excluded_namespaces` | array of strings | `[]` | List of datapack namespaces to exclude completely from compilation (e.g. `["custom_debug", "profiler"]`). Functions in these namespaces retain 100% vanilla delegation. |

---

## 2. In-Game Operator Commands

The mod registers the `/functioncompiler` root command for server operators (Permission Level 2 / OP).

### `/functioncompiler status`
Displays the current runtime configuration, active optimization passes, and namespace exclusion rules:
```text
[FunctionCompiler] Status:
  enabled: false
  fused_regions: false
  selective_macros: true
  tiered_bytecode: false
  tiered_threshold: 5
  excluded_namespaces: []
```

### `/functioncompiler metrics`
Displays live telemetry and runtime execution counters:
```text
[FunctionCompiler] Metrics:
  fused_regions_compiled: 42
  fused_regions_executed: 1850
  macro_arguments_bound: 1952
  bytecode_classes_live: 0
  bytecode_compilation_failures: 0
```

### `/functioncompiler reload`
Reloads `config/function-compiler.json` from disk without requiring a server restart:
```text
[FunctionCompiler] Configuration reloaded successfully from disk.
```
- Active configuration parameters update immediately.
- Functions dispatched after the reload observe updated optimization and exclusion rules.

---

## 3. Configuration Precedence Hierarchy

The compiler determines its active configuration through a clear hierarchy:

1. **System Environment Variables (Highest Priority):**
   - e.g. `FC_FUSED_REGION_PROTOTYPE`, `FC_BYTECODE_REGION_PROTOTYPE`, `FC_BYTECODE_TIERED_THRESHOLD`.
   - Used by the automated test harness and differential compatibility probe to enforce specific test arms.
2. **Disk Configuration (`config/function-compiler.json`):**
   - Active on production servers when environment variables are omitted.
3. **Built-in Production Defaults (Fallback):**
   - Applied if the configuration file is unreadable or absent (`enabled=false`, `score_add=false`, `fused_regions=false`, `selective_macros=true`, `tiered_bytecode=false`).
