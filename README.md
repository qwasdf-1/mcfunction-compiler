# Minecraft Function Compiler

A server-side Fabric mod for Minecraft 26.3 functions and macros, containing conservative, evidence-gated specialization and execution prototypes.

Minecraft Function Compiler investigates eliminating Minecraft's recursive command queue scheduler overhead while preserving vanilla execution semantics, error handling, command quotas, and trace parity. The specialized command handlers and prototype paths below are narrow parsed-command optimizations and evidence-gated experiments; see `docs/research/implementation-sanity-audit-2026-10.md` and the raw reports in `build/reports/` and `build/benchmarks/` for current evidence status.

---

## Features & Optimizations

### Maintained typed compiler (opt-in, experimental)

The consolidated typed compiler uses bounded parsed-command IR, an interpreter and direct JVM bytecode for eligible scoreboard regions, with native dispatch, conditional terminal and score-store boundaries. Unsupported commands retain their native queue entries. Enable only for a selected namespace, at server startup:

```sh
FC_TYPED_COMPILER_PROFILE=validated FC_TYPED_IR_NAMESPACE=my_pack java -jar fabric-server-launch.jar nogui
```

See the [typed compiler reference](docs/reference/features/typed-compiler.md) for flags, invariants, diagnostics and fixture packaging. Default-off parity/CPU, native IR043–047, publisher restoration, incremental pure/mixed CPU and absolute pure CPU passed scoped qualification; absolute mixed CPU nonregression remains inconclusive and is explicitly waived for Integration-001, merged in PR #11. See [Integration-001](docs/integration-001.md#final-disposition--2026-11-27). No blanket speedup or default enablement is claimed. The sections below describe separate legacy engines.

### 1. Fused Region Specialization (Disabled by Default / Experimental)
Minecraft functions normally execute commands sequentially through an iterative command queue (`ExecutionContext`), allocating separate execution frames and re-resolving command dispatchers on every line. 

The **Fused Region Engine** groups consecutive eligible commands into single unrolled actions:
- **Scoreboard Predicates & Mutations:** Specializes literal fake-holder additions (`scoreboard players add`), score comparisons (`execute if/unless score`), and score ranges (`matches <range>`).
- **Store Redirection:** Writes command return values and success flags directly to destination objectives without intermediate observer allocations (`execute store result/success score`).
- **Context Modifier Folding:** Folds chained context modifiers (e.g. `execute as @s at @s positioned ~ ~1 ~ run ...`) into a single in-memory source transformation.
- **Entity & Block Predicates:** Inlined evaluation of `execute if/unless entity @s` and `execute if/unless block <pos> <block>`.
- **Storage Operations:** Direct in-memory mutation for `data modify storage ... set value` and `data remove storage`.

`fused_regions` remains disabled by default: its semantic matrices and static-fixture timings pass, and the first real-workload measurement (PERF-017, Vein Miner 6×6×6 native event, ten pairs with exact parity and confirmed region activation) found no gain — a +0.69% median event-completion change with a 97.85% interval of −3.92% to +2.74%, decision `does_not_meet_threshold` — so its promotion gate is closed rather than open (see the promotion table below).

### 2. Selective Macro Arguments (Default: Enabled)
Dynamic macro functions (`function <name> with ...`) traditionally trigger full NBT compound serialization on every call. The **Selective Macro Prototype** inspects the function template and extracts only the targeted keys (e.g., `amount`, `x`, `y`, `z`) directly from compound tags or storage targets:
- **Selective macro:** 3-pair Vein Miner screening campaign reported -22.25% to -28.40% median event completion latency; confirmatory 6-pair Vein Miner campaigns now meet the pre-declared 15% gate on the real event workload: Fabric -22.34%, Lithium -22.06%. A separate confirmatory 6-pair synthetic sustained macro benchmark met the same gate more strongly: -80.49% active tick average (`lb113`) and -83.22% (`lbm113120`). ScoreAdd remains unqualified and, in its own 6-pair confirmatory Vein Miner run, changed the workload median by only -0.88% and did not meet the gate.
- **Tick-time evidence is secondary.** The 3-pair PERF-015 screening run reported `>6.5x` average-tick ratios and `-35.21%` P95 MSPT; three pairs provide at most 93.75% exact median coverage, so those numbers are screening observations only. Tick percentiles remain noisy, and the promotion decision rests on the confirmatory event-completion campaigns above.
- Fully synergistic with [Lithium](https://github.com/CaffeineMC/lithium-fabric), [Bellows](https://github), and [Moonrise](https://github.com).

### 3. Tiered JIT & Parameterized ASM Bytecode (Opt-In / Experimental)
For server workloads demanding peak throughput, an optional ASM bytecode backend generates unrolled JVM hidden classes for frequently executed function regions:
- **Zero Metaspace Leaks:** Parameterizes structural hidden classes strictly by command count rather than dynamic macro tuple values, caching constructor `MethodHandle` instances in `ConcurrentMap`. All macro invocations and functions of identical shape share the exact same single JVM class.
- **4-Part Cold-Function Policy:** Bypasses startup routines (`#minecraft:load`) and short routines ($L < 3$), deferring bytecode compilation until an invocation threshold ($K \ge 5$) is reached.

---

## Configuration (`config/function-compiler.json`)

The compiler automatically generates a configuration file at `config/function-compiler.json` upon server startup:

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

| Setting | Type | Default | Description |
|---|---|---|---|
| `enabled` | boolean | `false` | Master switch for compiler wrapping and optimizations. |
| `score_add` | boolean | `false` | Enables parsed literal scoreboard specialization when wrapper mode is active. |
| `fused_regions` | boolean | `false` | Enables pipeline chaining and fused region execution. |
| `selective_macros` | boolean | `true` | Enables selective NBT key extraction for macro invocations. |
| `tiered_bytecode` | boolean | `false` | Enables tiered JIT ASM hidden class bytecode compilation. |
| `tiered_threshold` | integer | `5` | Invocations required before a hot region transitions to bytecode. |
| `excluded_namespaces` | array | `[]` | Datapack namespaces completely excluded from compilation (e.g. `["debug_pack"]`). |

---

## In-Game Admin Commands

Permission Level 2 (OP) commands are available for server operators:

- `/functioncompiler status`: Displays active configuration, wrapper status, and optimization flags.
- `/functioncompiler metrics`: Displays real-time metrics including fused regions executed, macro arguments bound, bytecode classes live, and command queue savings.
- `/functioncompiler reload`: Reloads `config/function-compiler.json` from disk without restarting the server.

---

## Compatibility & Safety

The compiler undergoes continuous differential verification against vanilla Minecraft:
- **100% Differential Parity:** Verified across 55 pairwise test matrix combinations against vanilla `fabric-off`, covering nested returns, control flow, recursion, fork limits, quota debits, and `/debug function` traces.
- **Mod Compatibility:** Tested and verified compatible alongside performance mods including **Lithium 0.26.2**, **Bellows 1.1.3**, and **Moonrise 1.2.0**.
- **Safe Fallback:** If any compilation failure or unrecognized command occurs, execution safely falls back to standard vanilla command interpretation with zero state divergence.

---

## Promotion Status (Current Evidence)

Statuses follow the saved campaign results recorded in `docs/research/implementation-audit-2026-11.md`.

| Optimization | Default | Promotion status | Evidence |
|---|---|---|---|
| Selective macro arguments | `true` | **Supported** — promoted | Real-event Vein Miner 6-pair confirmatory campaigns passed the 15% gate: Fabric -22.34%, Lithium -22.06%; MSPT-based Bellows metric also passed (-73.75%). Native real-datapack confirmatory (2026-11-09, plain Fabric stack): 10 pairs, median event completion -29.58%, exact interval -30.30% to -26.37%, `no_regression_holds`. |
| Selective macro arguments on Bellows | `true` | **Supported with closed evidence** | New nested extraction run: -22.17% event completion (-25.41% to -16.50%), 6 pairs, 95% confidence; all 70,494 attempts became eligible. |
| Fused regions | `false` | Experimental / unqualified | Adjacent-eligible PERF-016 confirmatory campaign (`benchmarks/PERF-016-sustained-fused-region-active-tick.md`): all 10 pairs passed exact workload parity at 5,000 adds per active tick and exact region activation, median -19.72% workload-attributable tick average, but the 97.85% interval (-30.30% to -12.90%) overlaps the pre-declared 15% gain, so the decision is inconclusive. |
| Tiered bytecode | `false` | Opt-in / evidence-gated | Static-fixture result shown as slower than fused interpreted; bounded Metaspace/reload evidence only. |
| ScoreAdd specialization | `false` | Not qualified | 6-pair confirmatory Vein Miner run median -0.88%, `does_not_meet_threshold`; no current evidence qualifies it. |

Supporting stack aliases live in [`docs/reference/stack-aliases.md`](docs/reference/stack-aliases.md).

---

## Building from Source
r
Requirements: Java 25 JDK.

```sh
# Build jar
./gradlew build

# Run offline with pre-cached dependencies
FC_GRADLE_OFFLINE=true ./gradlew build --offline
```

The output jar is located in `build/libs/function-compiler-0.1.0-SNAPSHOT.jar`.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
