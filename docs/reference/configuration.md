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
| `score_add` | boolean | `false` | Enables the shared parsed-command specialization pass on an enabled wrapper when `fused_regions` is off. The pass covers scoreboard mutations, operations, resets, conditions, and stores plus the other parsers in `ScoreAddPrototype`. `fused_regions=true` implies this pass, because fused regions execute the specialized commands; an explicit `FC_SCORE_ADD_PROTOTYPE=false` environment override still wins for diagnostics. |
| `fused_regions` | boolean | `false` | Enables contiguous command fusing, context modifier folding, scoreboard condition/store interception, block/entity predicates, and storage data mutations. This also enables the specialization pass even when `score_add` is `false`. |
| `selective_macros` | boolean | `true` | Enables selective extraction of declared macro parameter keys directly from entity custom data and storage targets, bypassing full NBT compound serialization. |
| `tiered_bytecode` | boolean | `false` | Enables the ASM hidden class bytecode compilation backend for hot function regions. |
| `tiered_threshold` | integer | `5` | The number of times a region executes via interpreted fusion before automatically compiling to unrolled JVM bytecode (active only when `tiered_bytecode` is `true`). |
| `excluded_namespaces` | array of strings | `[]` | List of datapack namespaces to exclude completely from compilation (e.g. `["custom_debug", "profiler"]`). Functions in these namespaces retain 100% vanilla delegation. |

---

## 2. Administrative Commands

The mod registers the `/functioncompiler` root and legacy `/function_compiler_probe` alias. These commands are intended for administration; the current registrations do not explicitly enforce an operator permission level. Do not rely on the command names as an access-control boundary.

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

`fused_regions=true` implies the scoreboard specialization pass in the disk
configuration, so `score_add=false` does not disable specialization while
fusion is active. A focused probe can still force the specialization off by
setting `FC_SCORE_ADD_PROTOTYPE=false`; that combination exercises fusion with
vanilla scoreboard command execution and is not a production mode.

## 4. Startup-only typed compiler profile

See [Opt-in typed compiler](features/typed-compiler.md). Set `FC_TYPED_COMPILER_PROFILE=validated` and `FC_TYPED_IR_NAMESPACE=my_pack` before server startup. Explicit feature flags override profile defaults. No namespace means the profile stays off; `FC_WRAPPER_PROBE=false` overrides the wrapper gate. `/functioncompiler reload` does not change startup-only typed flags. `/functioncompiler status` includes requested typed profile, mode, namespace, reentrant and reuse flags and fixture-build status. `/functioncompiler ir008` reports typed counters; `/functioncompiler ir016 <namespace:function>` reports the diagnostic layout ledger when enabled. The former IR025 diagnostic command is withdrawn along with the abandoned fork backend. No legacy JSON defaults changed.
