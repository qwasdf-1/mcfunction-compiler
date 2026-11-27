# COMPILER-ACCEPTANCE-002 — runtime parser acceptance and macro boundaries

**Status:** Accepted **descriptive** native parser/instantiation census (2026-11-18), not a compiler optimization or speedup claim. Branch: `work/compiler-coverage`. This follows [COMPILER-COVERAGE-AUDIT-001](compiler-coverage-audit-001.md) without promoting any scheduler or NBT runtime instrumentation.

## Research question

The prior source audit found 635 reachable Vein Miner command lines, but lexical parser-root recognition is not compiler installation and neither implies the command executes in the mining event. This study checks **what actually passes the compiler's parser boundaries**, especially `execute ... run` and expanded macros, with the 26.3 original Vein Miner publisher ZIP pinned to SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`.

Source review exposed two materially different compilation paths:

1. At the **bare EXECUTE stage**, `ScoreAddPrototype.compileEntry` attempts ScoreAdd, ScoreOperation, ScoreReset, DataStorage, StateMachine and LeafFunction only. The broader executable compiler registry is **not** reached there.
2. At a **modifier-chain stage**, the broader executable registry is tried **before** the modifier chain is parsed. If terminal compilation succeeds but a modifier declines, the terminal's Brigadier callback may already be replaced while vanilla's surrounding modifier chain remains. This is deliberately recorded as **`chain_terminal_only`**, not a fully lowered chain or a complete fallback. The current parser's handling of 26.3's trailing `run` no-op stage generally leaves only single real modifier stages eligible.

These observations identify a coverage question. They do **not** establish a semantic bug or a profitable optimization.

## Diagnostic mechanism

- Opt-in `FC_COMPILER_ACCEPTANCE_AUDIT=true` **and required namespace** `FC_COMPILER_ACCEPTANCE_NAMESPACE=vm`. The audit does nothing with just one switch. An existing function-builder Mixin admits macro-function wrappers **only for that audited namespace** even when normal parser prototypes are off; no new Mixin or command substitution is introduced. This control is not an uninstrumented production-default configuration.
- `function_compiler_probe acceptance` (or `functioncompiler acceptance`) dumps sorted, bounded records to the server log, with begin/end event and key-count conservation controls. Maximum **16,384** unique records, input excerpt at most 240 characters. The native harness **rejects any bounded-key overflow**; this gate was added after the initial 4,096-key trial lost 833 parser events into the overflow bucket. The command prints a small summary via RCON.
- **Parser outcomes:** `plain_parser_gate_off` (function seen without the compiler gate); `bare_declined`; `bare_terminal_installed`; `chain_missing_parts`; `chain_executable_declined`; `chain_terminal_only`; `chain_fully_lowered`.
- **Macro outcomes:** `macro_new_expansion`, `macro_parameter_cache_hit`, `macro_plaintext_eligible`, `macro_not_eligible`, `macro_parser_visited`, and `macro_parser_gate_off`. Macro parameter-cache reuse is **not** proof a cached result is compiled or executed. Expanded macro lines may be compiled repeatedly across distinct argument tuples.
- The existing selective macro argument metrics and ScoreAdd execution counters provide separate controls, but **this first census does not count execution frequency for every individual command**. Missing execution coverage must be addressed separately before candidate selection.

## Native two-arm screen

`research-compiler-acceptance.yml` runs the existing real mining-event harness on an isolated Fabric server (survival player, 6×6×6 ore event), without Spark/JFR and without a new scheduler profiler:

| Arm | Enabled behavior | What can be concluded |
| --- | --- | --- |
| `selective-macro` | Existing default-on selective extraction, parser prototypes off; opt-in selective argument hit counter **and namespace-gated diagnostic macro wrapper** | Tests macro calls/fast-path use while explicitly distinguishing the parser's disabled gate; not an exact production-default runtime stack |
| `score-add` | Opt-in ScoreAdd compiler/parser path, selective argument extraction off in this harness mode | Tests parser acceptance, terminal-only chain outcomes and expanded macro specialization, not a default-on production speedup |

Both arms must complete the exact source-pinned mining event and its post-event invariants. The diagnostic dump is requested **after event completion**, then `acceptance.log` and all row counts are archived. The output is `build/benchmarks/COMPILER-ACCEPTANCE-002/results.json` plus per-arm logs. The offline `scripts/analyze_compiler_acceptance.py` requires a single begin/end, exact event conservation and namespace containment; synthetic tests cover these contracts.

## Accepted native diagnostic — 2026-11-18

The [lossless two-arm native run #44379699409](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44379699409) **passed** the normal native 6×6×6 survival event parity, original publisher ZIP SHA-256 pin, parser-output conservation, namespace guard, and zero-overflow requirement. The normal branch [CI](https://github.com/qwasdf-1/mcfunction-compiler/pull/10/checks) also passed. A prior [diagnostic #44378610965](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44378610965) completed its gameplay arms but is **not accepted for complete outcome classification** because its 4,096-key log overflowed 833 events; do not mix its count distribution into the accepted one.

| Metric / outcome (per-process instances or parse/install attempts) | Selective-macro arm | ScoreAdd-enabled arm |
| --- | ---: | ---: |
| Selective macro argument fast-path hits | **11,697** | Not enabled |
| Macro **new expanded instantiations** | **2,203** | **2,203** |
| Macro parameterized instantiation **cache hits** | **9,520** | **9,556** |
| Macro parser **gate off** | **2,203** | 0 |
| Macro parser **visited** | 0 | **2,203** |
| Bare terminal **installed** | Not attempted | **114** |
| Bare terminal **declined** | Not attempted | **2,147** |
| `execute` chain **fully lowered** | Not attempted | **112** |
| `execute` chain **terminal-only** specialized | Not attempted | **221** |
| `execute` chain **executable declined** | Not attempted | **2,361** |
| Bounded-key overflows | **0** | **0** |

*These rows include distinct kinds of event and must not be summed to a unique command count. Macro expansions and parser outcomes can describe the same underlying instantiation; parsing on load and expanded macro instantiation both contribute. Counts are not per-command runtime execution and the diagnostic arms are not paired for performance inference.*

The strongest repeated declined command shapes by **compile attempt count**, not measured execution count, were:

- `vm:detection/upsert_target`: `execute as @e[type=minecraft:marker,tag=vmr.target,tag=vmr.owner.1,limit=1] run tp @s ~ ~ ~` — **30** executable declines.
- `vm:detection/upsert_target`: `execute unless entity @e[type=minecraft:marker,tag=vmr.target,tag=vmr.owner.1,limit=1] summon minecraft:marker run function vm:detection/create_target with storage vm:runtime target` — **30** executable declines.
- `vm:operation/claim`: nested `execute if score ... run return run function ...` — **2** declines.

Numerous additional once-per-load declines are ordinary admin commands such as `tellraw`. Their existence is not evidence that those commands execute during the mining event. The `chain_terminal_only` count proves that treating successful terminal callback specialization as complete-chain lowering would inflate the coverage claim. Conversely, the terminal may legitimately run behind vanilla modifier handling; that does not prove an incorrect command result.

**Decision:** This census establishes a reliable classifier and genuine uncovered parser shapes but **does not identify an economically significant compiler-owned optimization**. Do not widen the parser or scheduler merely to make these counts decrease. The next narrow gate is a **separate, bounded command-execution census** on named candidate functions/patterns during the same real event, with actual dynamic exposure and CPU attribution, before selecting a lowering candidate.

### How to interpret the results

- **Source lines** from audit 001, **parse/install attempts**, **macro cache hits**, **specialized callback executions**, **whole-event wall time** and **exclusive server CPU** are different units. Do not divide one by another as though they share a denominator.
- Load/reload compilation can repeat counts; macro expansions also multiply attempts. This is a **per-process census**, not unique static-site coverage.
- A chain recorded as `chain_terminal_only` has a specialized terminal but retains vanilla modifier handling. It is not a declaration of fallback correctness failure.
- The added logging/counters alter running overhead. Do **not** compare timing in these arms to infer savings, even if the native runner produces elapsed-time fields.
- No optimizer, new default-on feature, global NBT rewrite, new scheduler implementation or automatic timing-based promotion is part of this experiment.

**Follow-up gate:** Only investigate a concrete lowering candidate if the census identifies a specific parser rejection or terminal-only pattern **and** a separately measured hot execution path with enough avoidable compiler-owned cost. Validate callbacks, failure results, forks, return, quota and function execution semantics with fixtures before attempting a paired, non-instrumented causal performance campaign.
