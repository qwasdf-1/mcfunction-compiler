# COMPILER-ACCEPTANCE-002 — runtime parser acceptance and macro boundaries

**Status:** Diagnostic implementation and manual/PR-native workflow; **no accepted native measurements yet**. Branch: `work/compiler-coverage`. This follows [COMPILER-COVERAGE-AUDIT-001](compiler-coverage-audit-001.md) without promoting any scheduler or NBT runtime instrumentation.

## Research question

The prior source audit found 635 reachable Vein Miner command lines, but lexical parser-root recognition is not compiler installation and neither implies the command executes in the mining event. This study checks **what actually passes the compiler's parser boundaries**, especially `execute ... run` and expanded macros, with the 26.3 original Vein Miner publisher ZIP pinned to SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`.

Source review exposed two materially different compilation paths:

1. At the **bare EXECUTE stage**, `ScoreAddPrototype.compileEntry` attempts ScoreAdd, ScoreOperation, ScoreReset, DataStorage, StateMachine and LeafFunction only. The broader executable compiler registry is **not** reached there.
2. At a **modifier-chain stage**, the broader executable registry is tried **before** the modifier chain is parsed. If terminal compilation succeeds but a modifier declines, the terminal's Brigadier callback may already be replaced while vanilla's surrounding modifier chain remains. This is deliberately recorded as **`chain_terminal_only`**, not a fully lowered chain or a complete fallback. The current parser's handling of 26.3's trailing `run` no-op stage generally leaves only single real modifier stages eligible.

These observations identify a coverage question. They do **not** establish a semantic bug or a profitable optimization.

## Diagnostic mechanism

- Opt-in `FC_COMPILER_ACCEPTANCE_AUDIT=true` **and required namespace** `FC_COMPILER_ACCEPTANCE_NAMESPACE=vm`. The audit does nothing with just one switch. No new Mixin or live command substitution is introduced by the diagnostic.
- `function_compiler_probe acceptance` (or `functioncompiler acceptance`) dumps sorted, bounded records to the server log, with begin/end event and key-count conservation controls. Maximum 4096 unique records, input excerpt at most 240 characters. The command prints a small summary via RCON.
- **Parser outcomes:** `plain_parser_gate_off` (function seen without the compiler gate); `bare_declined`; `bare_terminal_installed`; `chain_missing_parts`; `chain_executable_declined`; `chain_terminal_only`; `chain_fully_lowered`.
- **Macro outcomes:** `macro_new_expansion`, `macro_parameter_cache_hit`, `macro_plaintext_eligible`, `macro_not_eligible`, `macro_parser_visited`, and `macro_parser_gate_off`. Macro parameter-cache reuse is **not** proof a cached result is compiled or executed. Expanded macro lines may be compiled repeatedly across distinct argument tuples.
- The existing selective macro argument metrics and ScoreAdd execution counters provide separate controls, but **this first census does not count execution frequency for every individual command**. Missing execution coverage must be addressed separately before candidate selection.

## Native two-arm screen

`research-compiler-acceptance.yml` runs the existing real mining-event harness on an isolated Fabric server (survival player, 6×6×6 ore event), without Spark/JFR and without a new scheduler profiler:

| Arm | Enabled behavior | What can be concluded |
| --- | --- | --- |
| `selective-macro` | Existing default-on selective extraction, parser prototypes off; opt-in selective argument hit counter | Tests macro calls/fast-path use while explicitly distinguishing the parser's disabled gate |
| `score-add` | Opt-in ScoreAdd compiler/parser path, selective argument extraction off in this harness mode | Tests parser acceptance, terminal-only chain outcomes and expanded macro specialization, not a default-on production speedup |

Both arms must complete the exact source-pinned mining event and its post-event invariants. The diagnostic dump is requested **after event completion**, then `acceptance.log` and all row counts are archived. The output is `build/benchmarks/COMPILER-ACCEPTANCE-002/results.json` plus per-arm logs. The offline `scripts/analyze_compiler_acceptance.py` requires a single begin/end, exact event conservation and namespace containment; synthetic tests cover these contracts.

### How to interpret the eventual results

- **Source lines** from audit 001, **parse/install attempts**, **macro cache hits**, **specialized callback executions**, **whole-event wall time** and **exclusive server CPU** are different units. Do not divide one by another as though they share a denominator.
- Load/reload compilation can repeat counts; macro expansions also multiply attempts. This is a **per-process census**, not unique static-site coverage.
- A chain recorded as `chain_terminal_only` has a specialized terminal but retains vanilla modifier handling. It is not a declaration of fallback correctness failure.
- The added logging/counters alter running overhead. Do **not** compare timing in these arms to infer savings, even if the native runner produces elapsed-time fields.
- No optimizer, new default-on feature, global NBT rewrite, new scheduler implementation or automatic timing-based promotion is part of this experiment.

**Follow-up gate:** Only investigate a concrete lowering candidate if the census identifies a specific parser rejection or terminal-only pattern **and** a separately measured hot execution path with enough avoidable compiler-owned cost. Validate callbacks, failure results, forks, return, quota and function execution semantics with fixtures before attempting a paired, non-instrumented causal performance campaign.
