# Specialization Coverage Table

**Status:** Authoritative enumeration of what the specialization pass covers, per the v1 coverage gate in [`v1-production-roadmap.md §6`](../../v1/plans/v1-production-roadmap.md)

**Owner Classes:** [`ScoreAddPrototype.java`](../../../src/main/java/dev/functioncompiler/ScoreAddPrototype.java) (compiler entry), [`ProbeFunctionWrapper.java`](../../../src/main/java/dev/functioncompiler/ProbeFunctionWrapper.java) (wrapper), [`FunctionCoverageReport.java`](../../../src/main/java/dev/functioncompiler/FunctionCoverageReport.java) (runtime coverage logging)

---

## 1. What this table is

The v1 coverage gate requires that **every supported (family, argument shape,
fallback condition) has one row, and nothing is called "supported" without
one**. This document is that enumeration. It is derived from the code, not from
claims: the executable families are the entries of
`ScoreAddPrototype.EXECUTABLE_COMPILERS`, the modifier families are
`MODIFIER_PARSERS`, and the region/backend behaviour is
`FusedRegionPrototype` / `BytecodeRegionPrototype`.

**Row status values:**
- `R` — an existing matrix case already covers this row.
- `P` — an existing case covers it **partially** (see the case status text).
- `—` — no case yet; the row is a required addition before v1.

Runtime evidence for a row is the per-namespace coverage report in
[`lifecycle-and-reload.md §6`](lifecycle-and-reload.md) plus the named runtime
arm in the matrix case.

## 2. Scoreboard mutation families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| SM-01 | `scoreboard players set` × `#holder` literal | objective missing | SCORE-001 | R |
| SM-02 | `scoreboard players set` × `@s` self-selector | executed without an entity context | SCORE-001 | R |
| SM-03 | `set` with a literal player-name holder | name absent from the scoreboard | — | — |
| SM-04 | `scoreboard players add` × `#holder` × positive literal | — | SCORE-003 | R |
| SM-05 | `add` × `#holder` × 0 | — | SCORE-003 | R |
| SM-06 | `add` × absent fake score | score created at 0 first | SCORE-002 | R |
| SM-07 | `add` × `@s` | — | SCORE-002 | R |
| SM-08 | `remove` × present score | result floor | SCORE-007 | R |
| SM-09 | `remove` × absent holder | negative result semantics | SCORE-007 | R |
| SM-10 | `remove` × multi-entity `@e[...]` selector | selector fan-out | — | — |
| SM-11 | `add/set/remove` × INT_MIN/INT_MAX overflow edges | 32-bit wrap | — | — |
| SM-12 | mutation × wrapped in modifier chains | modifier-aware dispatch | — | — |

## 3. Scoreboard operation, condition and store families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| SO-01..03 | `operation` × each of the 9 operators (`= += -= *= /= %= < > ><`) | absent source / absent target | SCORE-010 | R |
| SO-04 | `operation` × `@s` source and/or target | self-selector resolution | SCORE-010 | R |
| SO-05 | `operation` × divide/remainder by zero | syntax error, target preserved | SCORE-010 | R |
| SO-06 | `operation` × `#...` wildcard target | multi-target fan-out | SCORE-005 | R |
| SC-01 | condition `if score <a> <op> <b>` × each comparison op | — | SCORE-012 | R |
| SC-02 | condition `matches <range>` inclusive/exclusive bounds | — | SCORE-012 | R |
| SC-03 | condition × absent score on either side | absent-score semantics | — | — |
| SC-04 | condition × `#holder` and `@s` combinations | — | SCORE-012 | R |
| SS-01 | `execute store result score <t> <obj> run <op>` × each specialized op | — | SCORE-009 | R |
| SS-02 | `execute store success score ...` × success/failure returns | — | SCORE-013 | R |
| SS-03 | store target present vs absent | target creation | — | — |
| SS-04 | store under a modifier chain | modifier-aware dispatch | — | — |
| SR-01 | `reset <holder> <objective>` | — | SCORE-007 | R |
| SR-02 | `reset <holder>` (all objectives) | — | SCORE-007 | R |
| SR-03 | `reset` × seeded and absent holders | — | SCORE-007 | R |

## 4. Storage and data families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| DS-01 | `data modify storage` × set value | — | DATA-001 | R |
| DS-02 | `data modify storage` × compound/array/primitive values | — | — | — |
| DS-03 | `data remove storage` | — | DATA-001 | R |
| DS-04 | `data get storage` | malformed path | — | — |
| DS-05 | `execute store result/success` around a data command | — | — | — |
| DC-01 | storage → scoreboard data copy (`DataCopyCommand`) | — | — | — |
| DC-02 | nested path copy with array indices | — | — | — |

## 5. Predicate and modifier families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| PR-01 | `execute if/unless entity @s` | zero/multiple matches | PRED-001 | R |
| PR-02 | `execute if/unless block <pos> <block>` | unloaded chunk → vanilla fallback | PRED-002 | R |
| PR-03 | block predicate × block **tag** (`#ns:tag`) | tag expansion | — | — |
| PR-04 | block predicate × explicit block **state** (`block[..]`) | state-property match | — | — |
| PR-05 | item predicate (`*[minecraft:...]`) | component predicates | — | — |
| MO-01 | `ScoreCondition`/`ScoreStore` modifiers around specialized ops | — | SCORE-009/012 | R |
| MO-02 | `DataStore` modifier around data commands | — | — | — |
| MO-03..05 | `as`, `at`, `positioned`, `rotated`, `anchored` chains and their ordering | chained combinations | CTRL-009 | R |
| MO-06 | `ForkModifier` × fork limit 1..12 overflow | cap reached | QUOTA-009 | R |
| MO-07 | `ItemPredicate` modifier on stack predicates | — | — | — |
| MO-08 | `ContextModifier` folding into a single in-memory source mutation | — | CTRL-009 | R |

## 6. State-machine command families

Each of these has a dedicated parser today (`TitleParser`, `BossbarParser`,
`EffectParser`, `SetblockParser`, `VisualSoundParser`, `ItemCommandParser`,
`GameplayCommandParser`, `StateMachineParser`) and needs one row per command
form, not one row per parser:

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| ST-01 | `title @a actionbar/title/subtitle/clear` × text and JSON component | — | — | — |
| ST-02 | `bossbar add/set/remove/get <id> ...` | unknown bar | — | — |
| ST-03 | `effect give/clear <target> <effect> ...` | amplifier/duration edges | — | — |
| ST-04 | `setblock <pos> <block>[state] [mode]` | out-of-world | — | — |
| ST-05 | `playsound <sound> ...`, `particle ...`, `stopsound` | volume/pitch edges | — | — |
| ST-06 | gameplay item commands (`item replace/modify`) | slot edges | — | — |
| ST-07 | generic state-machine wrapper for the command set above | unrecognized command → vanilla | — | — |

## 7. Leaf-call and tail-call families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| LF-01 | contiguous `function <id>` leaf runs ≥ 2 | target resolves to a plain-text function | — | — |
| LF-02 | leaf run interrupted by an unknown command | boundary → two regions | COMPAT-007 | R |
| LF-03 | `return run function` leaf | result propagation | CTRL-002 | R |
| TC-01 | tail-call loop compaction | self-recursion depth | — | — |
| TC-02 | tail-call × macro invocation | — | — | — |

## 8. Macro argument families

One row per provider × key state. Existing rows prove the covered shapes; the
wrong-type and nested paths are proven but the matrix rows are summary-level.

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| MA-01 | inline `add` value | — | MACRO-002 | R |
| MA-02 | inline `pair` compound | — | MACRO-002 | R |
| MA-03 | `with storage <path> <nbt>` provider | storage path changes between calls | MACRO-003 | R |
| MA-04 | `with entity <sel> data ...` provider | missing entity data/field | MACRO-004 | R |
| MA-05 | `with block <pos> data ...` provider (block entity) | — | MACRO-010 | R |
| MA-06 | wrong-typed present value | native failure path preserved | MACRO-004 | R |
| MA-07 | absent declared key | omitted macro, valid ones survive | MACRO-006 | R |
| MA-08 | nested compound/array/int-array argument | — | MACRO-005 | R |
| MA-09 | alternate custom-data path (`data.custom_args`, `data.nested`) | — | MACRO-004 | R |
| MA-10 | hash-colliding distinct compounds | independent results | MACRO-007 | R |
| MA-11 | eight-tuple LRU churn under native expansion | — | MACRO-008 | R |

## 9. Fused-region families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| FR-01 | run of exactly 2 adjacent fusable commands | — | CTRL-004 | R |
| FR-02 | long run (PERF-016 fixture: 5,000/20,000 contiguous adds) | — | PERF-016 | R |
| FR-03 | real-datapack run (Vein Miner `detection/acquire_target`, 145 parsed candidates) | predicate mostly failing | PERF-017 | R |
| FR-04 | region boundary at an unrecognized command | two regions either side | COMPAT-007 | R |
| FR-05 | region boundary at `return` / `return run` | pending tail discarded | CTRL-001/002 | R |
| FR-06 | region boundary at quota exhaustion | queue yield | QUOTA-008 | R |
| FR-07 | nested regions across a function call | — | CTRL-004 | R |
| FR-08 | error mid-region (missing objective) | no replay of earlier effects | CTRL-006 | R |
| FR-09 | region containing a modded unknown command | custom command runs once | CTRL-008 | R |
| FR-10 | macro-expanded function regions | LRU cache path | MACRO-008 | R |

## 10. Bytecode backend families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| BC-01 | emitted region for a hot function ≥ tiered threshold (K=5) | — | PERF-013 | R |
| BC-02 | cold function below threshold | opt-out policy | PERF-009 | R |
| BC-03 | injected compile failure | original queue entries retained | PERF-014 | R |
| BC-04 | parameterized macro bytecode sharing one class per shape | Metaspace stability | PERF-014 | R |
| BC-05 | class retention across 25+ reloads | GC unlinking | RELOAD-004 | R |
| BC-06 | measured win over fused interpretation on a declared workload | — | — | — |

## 11. Current state of the table

**93 rows: 65 covered (R), 0 partial (P), 28 missing (—).**

**The 28 rows that must be added before v1, by family group:**

- **2. Scoreboard mutation families**: SM-03, SM-10, SM-11, SM-12
- **3. Scoreboard operation, condition and store f**: SC-03, SS-03, SS-04
- **4. Storage and data families**: DS-02, DS-04, DS-05, DC-01, DC-02
- **5. Predicate and modifier families**: PR-03, PR-04, PR-05, MO-02, MO-07
- **6. State-machine command families**: ST-01, ST-02, ST-03, ST-04, ST-05, ST-06, ST-07
- **7. Leaf-call and tail-call families**: LF-01, TC-01, TC-02
- **10. Bytecode backend families**: BC-06

That is the honest shape of coverage today. The scoreboard, macro-argument and
fused-region families are enumerated and differential-proven (65 rows).
Storage/data, predicate/modifier, state-machine, leaf/tail-call and the bytecode
win are implemented in code but not enumerated per argument shape in the matrix,
and therefore may not be claimed as covered. The v1 coverage gate closes when
this section's list is empty and every row carries an R.

## 12. Reproducing this table from the code

```sh
# executable and modifier families, in compiler order
sed -n '/EXECUTABLE_COMPILERS = List.of/,/);/p' src/main/java/dev/functioncompiler/ScoreAddPrototype.java
sed -n '/MODIFIER_PARSERS = List.of/,/);/p' src/main/java/dev/functioncompiler/ScoreAddPrototype.java
# fusable command set
grep -rl "implements FusableCommand" src/main/java/dev/functioncompiler/*.java
# runtime coverage for a given load
grep "Function coverage" path/to/server.log
```
