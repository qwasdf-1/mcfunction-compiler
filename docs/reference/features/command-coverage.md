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

**Row status values** (assigned in §11 from the matrix's own verdicts, not by hand):
- `R` — a cited matrix case recorded *complete* proves this row.
- `P` — a cited matrix case recorded `Partial` proves some of this row.
- `—` — no matrix case yet; a required addition before v1.

Runtime evidence for a row is the per-namespace coverage report in
[`lifecycle-and-reload.md §6`](lifecycle-and-reload.md) plus the named runtime
arm in the matrix case.

## 2. Scoreboard mutation families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| SM-01 | `scoreboard players set` × `#holder` literal | objective missing | SCORE-001 | R |
| SM-02 | `scoreboard players set` × `@s` self-selector | executed without an entity context | SCORE-001 | R |
| SM-03 | `set` with a literal player-name holder | name absent from the scoreboard | SCORE-016 | R |
| SM-04 | `scoreboard players add` × `#holder` × positive literal | — | SCORE-003 | R |
| SM-05 | `add` × `#holder` × 0 | — | SCORE-003 | R |
| SM-06 | `add` × absent fake score | score created at 0 first | SCORE-002 | R |
| SM-07 | `add` × `@s` | — | SCORE-002 | R |
| SM-08 | `remove` × present score | result floor | SCORE-007 | R |
| SM-09 | `remove` × absent holder | negative result semantics | SCORE-007 | R |
| SM-10 | `remove` × multi-entity `@e[...]` selector | selector fan-out | SCORE-020 | R |
| SM-11 | `add/set/remove` × INT_MIN/INT_MAX overflow edges | 32-bit wrap | SCORE-016 | R |
| SM-12 | mutation × wrapped in modifier chains | modifier-aware dispatch | SCORE-023 | R |

## 3. Scoreboard operation, condition and store families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| SO-01..03 | `operation` × each of the 9 operators (`= += -= *= /= %= < > ><`) | absent source / absent target | SCORE-010 | R |
| SO-04 | `operation` × `@s` source and/or target | self-selector resolution | SCORE-010 | R |
| SO-05 | `operation` × divide/remainder by zero | syntax error, target preserved | SCORE-010 | R |
| SO-06 | `operation` × `#...` wildcard target | multi-target fan-out | SCORE-005 | R |
| SC-01 | condition `if score <a> <op> <b>` × each comparison op | — | SCORE-012 | R |
| SC-02 | condition `matches <range>` inclusive/exclusive bounds | — | SCORE-012 | R |
| SC-03 | condition × absent score on either side | absent-score semantics | SCORE-017 | R |
| SC-04 | condition × `#holder` and `@s` combinations | — | SCORE-012 | R |
| SS-01 | `execute store result score <t> <obj> run <op>` × each specialized op | — | SCORE-009 | R |
| SS-02 | `execute store success score ...` × success/failure returns | — | SCORE-013 | R |
| SS-03 | store target present vs absent | target creation | SCORE-018 | R |
| SS-04 | store under a modifier chain | modifier-aware dispatch | SCORE-018 | R |
| SR-01 | `reset <holder> <objective>` | — | SCORE-007 | R |
| SR-02 | `reset <holder>` (all objectives) | — | SCORE-007 | R |
| SR-03 | `reset` × seeded and absent holders | — | SCORE-007 | R |
| SM-13 | mutation/operation under `execute store result/success` × remaining selector shapes | store-target creation semantics | SCORE-021 | R |
| SO-07 | operation × every remaining selector shape × store/callback context | absent scores, fan-out ordering | SCORE-022 | R |
| SC-05 | condition × every remaining selector shape under each store/callback context | absent scores | SCORE-017 | R |

## 4. Storage and data families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| DS-01 | `data modify storage` × set value | — | DATA-001 | R |
| DS-02 | `data modify storage` × compound/array/primitive values | numeric compound + array-indexed members | DATA-002 | R |
| DS-03 | `data remove storage` | — | DATA-001 | R |
| DS-04 | `data get storage` on an absent storage path | command failure, no store applied | DATA-004 | R |
| DS-05 | `execute store result/success score` around a data command | failing read leaves the store unapplied | DATA-004, SCORE-018 | R |
| DC-01 | `data modify storage A p set from storage B p` (`DataCopyCommand`) | absent source path | DATA-003 | R |
| DC-02 | nested path copy with array indices | copied container read back | DATA-003 | R |

## 5. Predicate and modifier families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- | R |
| PR-01 | `execute if/unless entity @s` | zero/multiple matches | PRED-001 | R |
| PR-02 | `execute if/unless block <pos> <block>` | unloaded chunk → vanilla fallback | PRED-002 | R |
| PR-03 | block predicate × block **tag** (`#ns:tag`) | tag expansion | PRED-003 | R |
| PR-04 | block predicate × explicit block **state** (`block[..]`) | state-property match | PRED-004 | R |
| PR-05 | item predicate (`*[minecraft:...]`) | component predicates | PRED-005 | R |
| MO-01 | `ScoreCondition`/`ScoreStore` modifiers around specialized ops | — | SCORE-009/012 | R |
| MO-02 | `DataStore` modifier around data commands | — | — | — |
| MO-03..05 | `as`, `at`, `positioned`, `rotated`, `anchored` chains and their ordering | chained combinations | CTRL-009 | R |
| MO-06 | `ForkModifier` × fork limit 1..12 overflow | cap reached | QUOTA-009 | R |
| MO-07 | `ItemPredicate` modifier on stack predicates | — | PRED-006 | R |
| MO-08 | `ContextModifier` folding into a single in-memory source mutation | — | CTRL-009 | R |
| MO-09 | fork modifier × remaining selector shapes (random/arbitrary identity ordering) | cap overflow | — | — |
| MO-10 | fork modifier × broader mod-stack combinations | Bellows/Moonrise interaction | — | — |

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
| LF-01 | contiguous `function <id>` leaf runs ≥ 2 | target resolves to a plain-text function | SCORE-019 | R |
| LF-02 | leaf run interrupted by an unknown command | boundary → two regions | COMPAT-007 | R |
| LF-03 | `return run function` leaf | result propagation | CTRL-002 | R |
| TC-01 | tail-call loop compaction | self-recursion depth | SCORE-019 | R |
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
| CT-01 | other return/error callback combinations after a region boundary | pending-tail discard | — | — |
| CT-02 | other callback contexts around specialized operations | result/success propagation | — | — |
| CT-03 | other callback failures after a partial mutation | no replay of completed effects | — | — |

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

**101 rows: 86 covered (R), 0 partial (P), 15 missing (—).**

Status is assigned from the matrix's own verdicts: **R** requires a cited matrix case recorded *complete* in [`minecraft-function-compiler-test-matrix-v0.1.csv`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv); **—** means no case exists for that shape.

**The 15 missing rows, by family group:**

- **5. Predicate and modifier families**: MO-02, MO-09, MO-10
- **6. State-machine command families**: ST-01, ST-02, ST-03, ST-04, ST-05, ST-06, ST-07
- **7. Leaf-call and tail-call families**: TC-02
- **9. Fused-region families**: CT-01, CT-02, CT-03
- **10. Bytecode backend families**: BC-06

### 11.1 How the eleven partial-cited rows were resolved

SCORE-007, SCORE-009, QUOTA-009, CTRL-001, CTRL-002 and CTRL-006 are recorded
`Partial` because their status text proves a large set of shapes and then notes
that *other* combinations remain open. Rather than mark these rows P (which
would understate what those cases prove) or R (which would overstate it), each
row was **narrowed to the specific claim its case already proves**, and every
combination the case leaves open became its own `—` row. The gap count therefore
*rose* — from 28 to 36 — because hidden gaps are now visible rows.

| Rows | Proved by (from the case's own verified text) |
|---|---|
| SM-08, SM-09 | SCORE-007: "remove 4 from 10 yields 6; remove from an absent score creates -4" |
| SR-01, SR-02, SR-03 | SCORE-007: "reset of seeded and absent holders preserves vanilla score presence" |
| SS-01 | SCORE-009: "stored function result state and RCON match vanilla and all seven Fabric modes at sequence limits 0–16" |
| MO-01 | Stage 1A: `ScoreConditionCommand`/`ScoreStoreCommand` inlined into contiguous regions with 100% exact parity |
| MO-06 | QUOTA-009: fork caps 1–4 with zero/one/two/four matches, "match across all 16 compatibility arms" |
| LF-03 | CTRL-002: nested `return run function` result 7, tails discarded, parent resumes once |
| FR-05 | CTRL-001/002: inner and outer pending fused regions discarded after the child returns |
| FR-08 | CTRL-006: mid-region missing-objective error, later commands run "without replaying the first effect" |

The newly visible gaps they concealed are rows **SM-13, SO-07, SC-05** (selector
shapes under store/callback contexts), **MO-09, MO-10** (remaining fork selector
shapes and mod-stack combinations), and **CT-01, CT-02, CT-03** (other
return/error callback combinations).

### 11.2 How each missing row can be closed (oracle feasibility)

Closing a row means running a differential case whose oracle can *observe* the
effect. The project's existing oracle is the scoreboard counter folded through
`EXPECTED_SCORES` in [`run_runtime_probe.py`](../../../scripts/run_runtime_probe.py),
swept over quotas across vanilla and nine Fabric modes, with `EXTENDED_QUOTA_FIXTURES`
extending a fixture to 0–16 so longer fixtures fit. Rows are classified by the
mechanism their oracle needs:

| Row(s) | Oracle mechanism | Status |
|---|---|---|
| SM-03, SM-11, SM-12, SC-03, SS-03, SS-04, SC-05, CT-01, CT-02, CT-03, TC-01, TC-02 | Scoreboard oracle, new fixtures only | Available (closed by batches 2-4 for the rows shown cited) |
| ST-03, ST-04, ST-06 | World/entity query oracle (`if block`, entity NBT), folded into the scoreboard | Available |
| ST-02 (`bossbar`) | `bossbar get` feedback through RCON | Available, new oracle type |
| **ST-01 (`title`), ST-05 (`playsound`/`particle`/`stopsound`), ST-07** | **None — client packets only, RCON cannot observe them** | **Not closable differentially.** Requires either a packet-capturing bot, or an explicit documented delegation contract as the claim |
| MO-02 | `execute store result/success storage <id> <path> run ...`; the 26.3 node arity this parser expects is not yet confirmed | **Blocked on syntax confirmation** (the row is `—` until a fixture parses) |
| MO-09, MO-10 | Fork selector identity for random/arbitrary ordering; harness records effects, not identities | Partially available |
| BC-06 | A paired performance campaign, not a fixture | Requires a campaign |

### 11.3 How the rows were closed, in batches

Four batches of differential fixtures have been run across mod-free vanilla 26.3
and the full ten-arm Fabric matrix with exact score-sequence parity. Each batch
is recorded with what it closed, and each batch's claims are regenerated from
the table rather than typed by hand.

**Batch 1 - storage (matrix cases DATA-002/003/004).** Fixtures
`storage_value_shapes`, `storage_copy_paths`, `storage_store_and_errors`.
Closed **DS-02, DS-04, DC-01, DC-02** (36 missing → 31).

**Batch 2 - scoreboard, holders, leaf/tail (matrix cases SCORE-016..019).**
Fixtures `score_holder_and_overflow`, `score_condition_absent`,
`score_store_targets`, `leaf_and_tail_runs` plus the `leaf_score_a`,
`leaf_score_b` and `leaf_tail_a` helpers. Closed **SM-03, SM-11, SC-03, SC-05,
SS-03, SS-04, LF-01, TC-01, DS-05** (23 missing).

**Defect found and fixed while building batch 2.** The
`score_holder_and_overflow` fixture uses a literal player-name holder
(`FCFused`), and every Fabric arm failed the whole function load with
`NullPointerException: Cannot invoke "...MinecraftServer.getPlayerList()"
because "server" is null`: `ScoreAddPrototype.resolveStaticHolder` resolved a
holder name before checking that it begins with `#`, and resolving a literal
player name consults the player list, which is null while a datapack loads.
All seven call sites now decline non-`#` holders before resolving, so the
literal holder stays on the vanilla path. The fixture proves both the fallback
and the 32-bit INT wrap. This is the kind of defect the coverage table exists to
find: a shape that "works" in vanilla and takes down the compiled path.

**Correction recorded.** The storage batch's write-up initially claimed it also
closed DS-05. It did not: the row's text was `execute store result/success around
a data command`, the edit searched for `run <op>`, the search silently matched
nothing, and the row stayed `—` while the count arithmetic (36 − 5 = 31)
contradicted the recorded 32. DS-05 is closed in batch 2 instead, cited to
DATA-004 and SCORE-018. The rule applied to this document: §11's numbers are
regenerated from the table, never edited by hand.

**What batch 2 could not close, and why.** `score_store_targets` first used
`scoreboard players get` as its inner command and produced an all-zero sequence
in every arm - an oracle that can never fail, which is worse than a failing test.
It was rebuilt around a data command with a known result value. SM-10, SM-12,
SM-13, SO-07, MO-02, MO-07, MO-09, MO-10, ST-01..07, TC-02, CT-01..03 and BC-06
remain open for the reasons in the table and in the feasibility classification
above.

**Batch 3 - predicate selectors (matrix cases PRED-003..006).** Fixtures
`predicate_block_tag`, `predicate_block_state`, `predicate_item_stack`,
`predicate_item_modifier`. Closed **PR-03, PR-04, PR-05, MO-07** (23 missing →
19).

**How the 26.3 syntax was confirmed before these fixtures were written.** Three
shapes here were new to the project: a block predicate naming a tag, a block
predicate naming a state, and an item predicate. Each was confirmed against the
vanilla server's own parser in a scratch server before a fixture was written -
one function per candidate syntax, booted from the pinned
`minecraft-server.jar`, with each candidate's load failure or score reported
individually. That pass recorded one syntax fact that a guess would have gotten
wrong: a count *range* in an item predicate is not `[count=1..]` and not
`[count=2..3]` (both fail to parse), nor `[count~1..]`; the range form is an SNBT
object, `[count={"min":1,"max":3}]`. It also showed that the entity-target form
of these predicates was not usable in the scratch world (a summoned armor stand
was not selectable), which is why the item fixtures use a chest-container target.

**The truncation defect this batch found in its own fixtures - and in the
harness's ability to see it.** The quota sweep runs a fixture across
`maxCommandSequenceLength` 0-16, and an `execute if items` line costs noticeably
more of that budget than a block predicate, with a two-predicate chain costing
more again. The first drafts of `predicate_block_tag`, `predicate_item_stack`
and `predicate_item_modifier` were therefore too long: the run charged out
mid-function and their later cases never executed in *any* arm. This is a
different failure from the all-zero oracle in batch 2 but the same class: part
of the fixture cannot fail, so it only looks like coverage.

It is also invisible to the value comparison alone. A truncated tail of cases
that take no branch produces exactly the same score as an executed tail, so the
observed map matched a shortened fixture just as happily as a complete one. The
fixture now guards against this structurally: **the final case of every fixture
must be a branch that is taken**, so its weight is an unconditional completion
signal, and `tests/test_runtime_probe_oracle_health.py` enforces that
invariant, that each fixture's declared full-run value is reached at the top
quota, that no map is constant or all-zero, and that a fixture registered in
`DIRECT_FIXTURES` is never silently skipped (the runner returns early when
`EXPECTED_SCORES` has no entry, so a missing entry is a fixture that can never
fail).

**What batch 3 could not close, and why.** The item fixtures are four cases and
eight, not the nine and twelve their first drafts had, because the command quota
will not carry more inside the 0-16 sweep; the shapes dropped (a negated
component term, a second count-range mismatch, a chain whose first conjunct
fails, an item predicate behind a zero-match `as` selector in both polarities)
are the first candidates for a second item-predicate fixture if command-quota
headroom is found. SM-10, SM-12, SM-13, SO-07, MO-02, MO-09, MO-10, ST-01..07,
TC-02, CT-01..03 and BC-06 remain open as before.


**Batch 4 - selector-shaped scoreboard rows (matrix cases SCORE-020..023).**
Fixtures `score_selector_mutation`, `score_selector_store`,
`score_selector_operation`, `score_modifier_dispatch`. Closed **SM-10, SM-13,
SO-07, SM-12** (19 missing -> 15).

These four rows are the shapes the compiler *declines*: every operand is an
entity selector rather than a `#` fake holder, so the specialized path bails out
and vanilla runs the command. The claim a row makes here is therefore about the
fallback, not about an inlined evaluator, and the oracle is that the compiled
arm's folded per-entity effects match vanilla exactly.

These fixtures are invoked by name from `run_scoreboard_semantics` rather than
from the `DIRECT_FIXTURES` quota sweep, for two reasons. First, the row's claim
is semantic fan-out, which does not need a sequence-limit sweep. Second, a
fold over four actors costs the whole command budget a predicate fixture spends
on eight cases, so a sweep-run fixture of these shapes could only carry one
observation. Each function performs its own mutations *and* its own per-entity
fold into one fake holder (`#mutation_sum`, `#store_sum`, `#operation_sum`,
`#modifier_sum`), so the console side only reads a score and the specialized
commands always execute inside the compiled function.

Every expectation was derived arithmetically before it was run - four actors at
a known seeded value, a known removal, and so on - and the vanilla arm then
confirmed each one exactly: 20, 20, 5636 and 60020. That ordering matters: a
fixture whose expectations are discovered by reading a failure message can be
made to pass by fitting the failure, whereas a derived expectation that the
server then confirms is a claim about behaviour rather than about the harness.

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
