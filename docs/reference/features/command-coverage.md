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
| --- | --- | --- | --- |
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
| --- | --- | --- | --- |
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
| --- | --- | --- | --- |
| DS-01 | `data modify storage` × set value | — | DATA-001 | R |
| DS-02 | `data modify storage` × compound/array/primitive values | numeric compound + array-indexed members | DATA-002 | R |
| DS-03 | `data remove storage` | — | DATA-001 | R |
| DS-04 | `data get storage` on an absent storage path | command failure, no store applied | DATA-004 | R |
| DS-05 | `execute store result/success score` around a data command | failing read writes 0 (measured, batch 8; the sweep's own error cases are not observably taken) | DATA-004, SCORE-018, MO-02 | R |
| DC-01 | `data modify storage A p set from storage B p` (`DataCopyCommand`) | absent source path | DATA-003 | R |
| DC-02 | nested path copy with array indices | copied container read back | DATA-003 | R |

## 5. Predicate and modifier families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- |
| PR-01 | `execute if/unless entity @s` | zero/multiple matches | PRED-001 | R |
| PR-02 | `execute if/unless block <pos> <block>` | unloaded chunk → vanilla fallback | PRED-002 | R |
| PR-03 | block predicate × block **tag** (`#ns:tag`) | tag expansion | PRED-003 | R |
| PR-04 | block predicate × explicit block **state** (`block[..]`) | state-property match | PRED-004 | R |
| PR-05 | item predicate (`*[minecraft:...]`) | component predicates | PRED-005 | R |
| MO-01 | `ScoreCondition`/`ScoreStore` modifiers around specialized ops | — | SCORE-009/012 | R |
| MO-02 | `DataStore` modifier around data commands | storage content, exact NBT tag match | MO-02 | R |
| MO-03..05 | `as`, `at`, `positioned`, `rotated`, `anchored` chains and their ordering | chained combinations | CTRL-009 | R |
| MO-06 | `ForkModifier` × fork limit 1..12 overflow | cap reached | QUOTA-009 | R |
| MO-07 | `ItemPredicate` modifier on stack predicates | — | PRED-006 | R |
| MO-08 | `ContextModifier` folding into a single in-memory source mutation | — | CTRL-009 | R |
| MO-09 | fork modifier × remaining selector shapes (random/arbitrary identity ordering) | unordered-sort identity: arbitrary resolves in insertion order, random narrowed to set semantics; cap fallback shared with QUOTA-009 | QUOTA-009 + MO-09 | R |
| MO-10 | fork modifier × broader mod-stack combinations | fork semantics under the pinned Bellows/Moonrise stacks; measured stacks are bellows113, bellows113-moonrise120 and lbm113120 | QUOTA-009 + MO-09 + MO-10 | R |

## 6. State-machine command families

Each of these has a dedicated parser today (`TitleParser`, `BossbarParser`,
`EffectParser`, `SetblockParser`, `VisualSoundParser`, `ItemCommandParser`,
`GameplayCommandParser`, `StateMachineParser`) and needs one row per command
form, not one row per parser:

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- |
| ST-01 | `title @a actionbar/title/subtitle/clear` × text and JSON component | — | STATE-001 | R |
| ST-02 | `bossbar add/set/remove/get <id> ...` | bossbar state, exact result-value match | ST-02 | R |
| ST-03 | `effect give/clear <target> <effect> ...` | amplifier/duration edges | STATE-002 | R |
| ST-04 | `setblock <pos> <block>[state] [mode]` | out-of-world | STATE-003 | R |
| ST-05 | `playsound <sound> ...`, `particle ...`, `stopsound` | volume/pitch edges | STATE-001 | R |
| ST-06 | gameplay item commands (`item replace/modify`) | slot edges for `item replace`; `item modify` with a confirmed datapack-defined modifier id (vanilla ships none) | STATE-004 + ST-06 | R |
| ST-07 | generic state-machine wrapper for the command set above | unrecognized command → vanilla | STATE-001 | R |

## 7. Leaf-call and tail-call families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- |
| LF-01 | contiguous `function <id>` leaf runs ≥ 2 | target resolves to a plain-text function | SCORE-019 | R |
| LF-02 | leaf run interrupted by an unknown command | boundary → two regions | COMPAT-007 | R |
| LF-03 | `return run function` leaf | result propagation | CTRL-002 | R |
| TC-01 | tail-call loop compaction | self-recursion depth | SCORE-019 | R |
| TC-02 | tail-call × macro invocation | — | TC-02 | R |

## 8. Macro argument families

One row per provider × key state. Existing rows prove the covered shapes; the
wrong-type and nested paths are proven but the matrix rows are summary-level.

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- |
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
| --- | --- | --- | --- |
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
| CT-01 | other return/error callback combinations after a region boundary | pending-tail discard | CT-01 | R |
| CT-02 | other callback contexts around specialized operations | result/success propagation | CT-02 | R |
| CT-03 | other callback failures after a partial mutation | no replay of completed effects | CT-03 | R |

## 10. Bytecode backend families

| Row | Family × argument shape | Fallback condition | Matrix |
| --- | --- | --- | --- |
| BC-01 | emitted region for a hot function ≥ tiered threshold (K=5) | — | PERF-013 | R |
| BC-02 | cold function below threshold | opt-out policy | PERF-009 | R |
| BC-03 | injected compile failure | original queue entries retained | PERF-014 | R |
| BC-04 | parameterized macro bytecode sharing one class per shape | Metaspace stability | PERF-014 | R |
| BC-05 | class retention across 25+ reloads | GC unlinking | RELOAD-004 | R |
| BC-06 | measured win over fused interpretation on a declared workload | — | — | — |

## 11. Current state of the table

**92 rows: 91 covered (R), 0 partial (P), 1 missing (—).**

Status is assigned from the matrix's own verdicts: **R** requires a cited matrix case recorded *complete* in [`minecraft-function-compiler-test-matrix-v0.1.csv`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv); **P** requires a cited case recorded *Partial*, which proves some of the row and names the rest; **—** means no case exists for that shape.

**The 1 missing rows, by family group:**

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
shapes under store/callback contexts)
and **CT-01, CT-02, CT-03** (other
return/error callback combinations). MO-09 was closed by batch 11 and MO-10
by batch 12.

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
| ST-03, ST-04, ST-06 | World/entity query oracle (`if block`, entity NBT), folded into the scoreboard | Closed by batch 6 (ST-03, ST-04, and ST-06's `item replace` half) and batch 10 (ST-06's `item modify` half, through a datapack-defined modifier id); all R |
| ST-02 (`bossbar`) | Folded into the scoreboard: `bossbar get value|max|players` return their values as command results, so `execute store result score` observes them; bare `bossbar get <id>` is not a valid 26.3 form | Available (closed by batch 9 without a new oracle type) |
| **ST-01 (`title`), ST-05 (`playsound`/`particle`/`stopsound`), ST-07** | **None — client packets only, RCON cannot observe them** | **Closable only by delegation contract**, accepted as the v1 claim for these rows (matrix case STATE-001; see §11.3 batch 5). Differential closure would require a packet-capturing bot, which is a separate decision |
| MO-09 | Fork selector identity: `sort=arbitrary` is oracle-able exactly (measured as entity insertion order, stable across invocations, reloads, restarts, and fresh worlds); `sort=random` is non-deterministic by design and is narrowed to per-trial set semantics plus a distinct-pair floor | Available (closed by batch 11 via the swap-chain scoreboard read-back) |
| MO-10 | Fork semantics under broader pinned mod stacks (Bellows/Moonrise); the modded server is its own reference, so within-stack direct-vs-function parity is the oracle | Available (closed by batch 12: the full fork fixture passed under bellows113, bellows113-moonrise120 and lbm113120 with each stack's result exactly equal to the mod-free vanilla arm) |
| BC-06 | A paired performance campaign, not a fixture | Requires a campaign |

### 11.3 How the rows were closed, in batches

Thirteen batches of differential fixtures and one delegation contract have been run across mod-free vanilla 26.3
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
TC-02, CT-01..03 and BC-06 remained open at that point; later batches close
TC-02 and CT-01..03.


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


**Batch 5 - the delegation rows (matrix case STATE-001).** The three
client-packet rows were closed not by a differential oracle, which does not
exist for them, but by a **delegation contract** the v1 plan accepts for this
class: the families are not specialized, and they are forwarded to vanilla
without error. Rows closed: **ST-01, ST-05, ST-07** (15 missing → 12).

A prose contract is not a checkable claim, so the contract was turned into a
measurement. `function_compiler_probe status` now reports per-function
specialization counters for three fixtures, and `run_delegation_contract`
asserts on them in every runtime arm:

* `score_delegation_positive` is the **control**. Its counters must be nonzero
  (`control_compiled=4` in every arm that specializes), so a zero reading on a
  declined fixture is evidence that the compiler refused it rather than an
  artifact of a counter that cannot move. Its *executed* counter must move
  across an invocation, which covers the other direction.
* `score_selector_declined` contains only selector-operand scoreboard commands
  and must read zero in both directions. This is the falsifiable form of the
  claim batch 4's write-up had merely asserted: that the compiler declines
  entity-selector operands.
* `state_machine_client_packet` contains only `title`, `playsound`, `particle`
  and `stopsound`, and must read zero in both directions.

**What the contract does not claim, and why that is stated rather than omitted.**
The command *effects* - the text shown, the sound's volume and pitch, the
particle count, the channel a stop-sound empties - are client packets and stay
unverified. Closing these rows is a decision to accept a delegation claim for
this class, not a claim about those semantics.

**The control caught a defect in the check itself, twice.** The first version
gated the counter half on the `FC_SCORE_ADD_PROTOTYPE` configuration flag and
therefore failed on `wrapper-off`, which specializes nothing at all: an arm
whose counters are all zero cannot be asked to prove a nonzero control. The
second version gated on the flag being *off* and would have skipped
`instrument-only`, which runs with the flag off yet still compiles four
specialized commands in the control. The gate is therefore the control's own
reading: if the control compiles something, the measurement is live and the
declined fixtures must read zero; if it compiles nothing, the arm is recorded
as not exercising the contract. Both `wrapper-off` and `wrapper-on` are
recorded that way, which is the honest description - a contract that cannot be
checked is not the same as a contract that holds.

**A silent-disarm guard, because the runtime check cannot see this.**
`tests/test_delegation_contract_fixtures.py` checks the wiring statically: the
status command must declare and report exactly the fixtures the probe checks,
each declared fixture file must exist, the control must contain a fake-holder
shape so its counter *can* move, the declined fixture must contain no fake
holder at all so its refusal does not depend on which operand the compiler
checks first, and the client-packet fixture must contain only client-packet
commands. A renamed or emptied fixture would otherwise read zero and the
contract would "pass" while proving nothing. Its first run also caught an
ambiguous line in the declined fixture itself: a fake-holder target with a
selector source, which the compiler declines only because of the source.

**Batch 6 - state-machine command rows (matrix cases STATE-002..004).** Fixtures
`state_effect_edges`, `state_setblock_edges`, `state_item_slot_edges`, run in
all ten arms with exact score-sequence parity. Closed **ST-03** and **ST-04**;
**ST-06** is closed for `item replace` and recorded **P**, because `item modify`
needs a confirmed item-modifier id from the 26.3 `minecraft:item_modifier`
registry and neither a vanilla modifier type nor a datapack-defined one could be
confirmed. 82 covered, 1 partial, 9 missing (the earlier 91/1/9 figure counted
the table's nine separator lines as rows; batch 7 corrects the generator).

**Five behaviours were read from the server rather than assumed, and each one
changed the fixture.** (1) An entity's active effects live at `active_effects`
in snake case, as `{duration, show_icon, amplifier, id}`; the pre-1.20.5 path
`ActiveEffects[0].Amplifier` matches nothing. (2) The list is **sorted by effect
id**, not ordered by application: with speed and slowness active, slowness is
index 0 whichever was given first. The first effect draft read both effects from
one list and one of its digits was validated by that sort order rather than by a
correct read, so the fixture now keeps one effect active at a time. (3) The
amplifier is a **signed byte**, so the command's maximum amplifier of 255 reads
back as -1; the fixture asserts -1, because that is what the entity holds. (4)
`effect give` refuses to **shorten** an active effect's duration as well as its
amplifier, so a truncated sweep's leftover is harmless only because it is
identical - the header says so in those words after a focused probe produced 80
against a longer-duration leftover. (5) A refused out-of-world `setblock` does
**not** abort the rest of the function, and `execute store success score` around
it writes 0, which makes the refusal observable in a scoreboard; but `execute if
block` at the same position aborts the command with an error and cannot be used
as a negative predicate there. The `effect clear` case is asserted with
`execute unless data` on a path that no longer resolves, so the claim is "the
element is gone" rather than "it holds a value I chose".

**The quota budget, not the semantics, decided the fixture's shape.** Clearing
between cases left the final case unexecuted by quota 16, which is the failure
mode the oracle-health test exists to catch: reading two fields from one effect
back to back removed a whole clear-and-give group and brought the last case in at
quota 13.

**A duplicate dict key silently overrode an encoded oracle, and now cannot.**
Encoding the new map added a second `state_effect_edges` entry below the one it
replaced. Python keeps the last value in a dict literal, so the stale map stayed
in effect and every arm failed against expectations nobody had updated; the
loaded-module health checks could not see this, because the import had already
collapsed the duplicate. `tests/test_runtime_probe_oracle_health.py` now parses
the source with `ast` and fails on a repeated fixture key. Two further
corrections: the default runtime matrix is **eight** arms, and the full set is
**ten** (nine Fabric modes plus vanilla), so the batch-6 claims quote the count
from the run that was actually made; and `EXPECTED_SCORES` is regenerated from
the runner's failure message, never typed.

**Batch 7 - tail-call/macro and callback rows (matrix cases TC-02, CT-01..03).**
Fixtures `tc02_tail_macro` (with `tc02_macro_a`, `tc02_macro_b`, `tc02_leaf`),
`ct01_return_after_boundary` (with `ct01_child_return`),
`ct02_store_specialized`, and `ct03_failure_after_mutation` (with
`ct03_macro_runtime_fail`, `ct03_macro_missing`), run in all ten arms with exact
score-sequence parity. Closed **TC-02, CT-01, CT-02, CT-03**. The table is now
92 rows: 86 covered, 1 partial, 5 missing.

TC-02 chains a plain frame into a macro function, into a second macro function,
into a plain leaf, with every call in tail position; the score 1 + 10 + 20 + 100
= 131 proves each frame contributed once. CT-01 puts a `say` boundary between two
regions in both the parent and the `return run function` child, and both pending
tails are discarded; the command response at quotas 10-16 also carries
`returned 7`, which is compared byte-for-byte with vanilla. CT-02 stores a
`data get` result (7) and an accepted `setblock` success (1), folded as the
declared 1,1 = 3. CT-03 mutates +1 and +10, fails inside a macro callee on a
missing objective, mutates +10 again, then invokes a macro whose argument
compound lacks a declared key; the completed effects apply once, the failed
expansion contributes nothing, and the caller continues.

**Two 26.3 behaviours were measured rather than assumed.** `setblock` reports
success 0 for an unchanged block ("Could not set the block"), measured directly,
so CT-02 resets the position to air before every store; without the reset later
quota iterations would assert the unchanged-block failure path. A macro
invocation with a missing key fails at expansion, before any line of the callee
runs, and a runtime command error inside a macro callee aborts neither the
callee's remaining lines nor the caller.

**The quota budget, not the semantics, chose CT-02's second case.** An
`effect give` store under `execute store success` did not fit the 0-16 sweep (32
of its declared 48 by quota 16), so the second case uses the
accepted-`setblock` side, which complements ST-04's refused-`setblock` case
rather than repeating it.

**The §11 row count was inflated by the table's own separators.** Every section
separator ends in `R`, and the earlier generator counted those nine lines as
data rows, so it reported 101/91/9 where the table held 92/82/9 after batch 6.
Batch 7's closer excludes and normalises the separators, and the current
92/86/1/5 figure is generated from the table rather than typed. No default-on
status changed and no performance claim is made in this batch; it is a
correctness and coverage measurement, and all ten arms matched vanilla on every
new map.

**Batch 8 - the DataStore modifier row, and the dead modifier pass it exposed
(matrix case MO-02).** Fixtures `mo02_store_result` and `mo02_store_failures`,
run in all ten arms with exact score-sequence parity. Closed **MO-02**. The
table is now 92 rows: 87 covered, 1 partial, 4 missing.

**26.3 syntax and failure semantics, measured not assumed.** The storage-store
tree is exactly `execute store (result|success) storage <target> <path> <type>
<scale> run <command>`: the type is one of byte/short/int/long/float/double and
the scale is a required double; omitting the scale is rejected at `run` with
"Expected double...", and the scale multiplies (10 × 2.5 = 25.0d). A failing
`data get` (absent path or no matching entity) throws, vanilla's execute
framework reports `(success=false, result=0)` to the store callback, and the
callback writes that value for a **result** store as well as a success store:
both overwrite the previous content with a zero of the declared type. The
earlier DS-05 claim that a failing read "leaves the store unapplied" was wrong
and is corrected in the table, the fixture text and matrix case DATA-004. The
MO-02 failure fixture carries the falsifiable form: it seeds the path with 9
and asserts the exact post-failure tags `0L` and `0s`, so a store that skipped
the write or dropped the type literal fails the match. `DataStoreCommand` was
fixed to write 0 before rethrowing on any exception, matching vanilla.

**The modifier-specialization pass had never executed.** While closing MO-02,
a per-function compile counter kept reading zero although score parity held.
Tracing the parse on 26.3 showed why: every `execute ... run ...` command's
`ContextChain` carries a trailing no-op modifier stage whose only node is
`run` (the `run` literal redirects to the dispatcher root with a null redirect
modifier), and `parseModifiers` requires a parser for every stage. No parser
accepted `[run]`, so **every** chained command silently declined - the whole
chained-modifier pass (`ContextModifierCommand`, `ScoreConditionCommand`,
`ScoreStoreCommand`, `DataStoreCommand`, `PredicateConditionCommand`,
`InlinedForkingCommand`) had never run at runtime, in this repository's entire
recorded history. The rows those classes were claimed to cover (MO-01's
"inlined with 100% exact parity", MO-06's fork caps, CT-02's store context)
held parity results that a vanilla fallback produces trivially; their
specialization claims had no runtime evidence. The pass is now enabled by
skipping the no-op `[run]` stage, and because every modifier parser requires
the leading `execute` node, a second real modifier stage still declines - only
single-stage chains compile.

**Vanilla's quota-debit model, derived and matched.** Vanilla charges one
quota debit per modifier stage carrying a redirect modifier (in
`BuildContexts`, before the stage's sources resolve) plus one per final source
(in `ExecuteCommand`). The debit model reproduces four independently measured
quota maps exactly (the two MO-02 fixtures, `quota_three`, and the four-actor
`as`/`at` fixture). The compiled chain keeps the per-source debit (the entry
still queues an `ExecuteCommand` per source), so each inlined command charges
its own stage debit: store and fork-stage-equivalent commands charge one,
condition and context-modifier commands charge only when they proceed (a
failed condition costs exactly one debit in vanilla, because an empty-source
stage queues no `ExecuteCommand`), and every inner command is gated on the
remaining quota not having gone negative - the compiled form of vanilla
stopping the queue before that line. The model also corrected three latent
defects that had never been exercised: `DataStoreCommand` and
`ScoreStoreCommand` fired the source result callback manually even though the
compiled entry still runs through `ExecuteCommand`/`runExecutable`, which
fires it once (a double fire would double every enclosing callback);
`ItemPredicateParser`'s evaluator returned the vanilla redirect's post-`unless`
result while the command applied `unless` again (a double inversion that made
every `unless items` line never fire); and the `fallbackChain.executeAll`
fallbacks re-enter the wrapped command itself in a timing-only arm, which is
why the runtime gates now match the compile gate exactly.

**What this retroactively changed.** All fixtures containing single-stage
modifier chains (score conditions, score and storage stores, block/entity/item
predicates, `as @s`/`at @s`) now run through the compiled commands in the six
compiling arms. The full ten-arm matrix re-verified every one of them against
the vanilla-measured maps: exact score sequences, command results, `/debug
function` traces, reload generations and fork limits. No default-on status
changed (`fused_regions` stays off; PERF-016/017 stand) and no performance
claim is made in this batch; it is a correctness and coverage measurement.

**Batch 9 - the bossbar row, closed without the new oracle type its
feasibility note expected (matrix case ST-02).** Fixtures
`st02_bossbar_ops` (add/remove lifecycle plus the unknown-bar edge) and
`st02_bossbar_values` (the set/get property shapes), run in all ten arms with
exact score-sequence parity, split because a full lifecycle does not fit one
0-16 quota sweep. Closed **ST-02**. The table is now 92 rows: 88 covered,
1 partial, 3 missing.

**The feasibility note's new oracle type was not needed.** §11.2 expected the
row to close through `bossbar get` feedback text parsed from RCON responses.
Measurement on the pinned vanilla server changed the picture twice over: bare
`bossbar get <id>` (no property) is not a valid 26.3 form - the only getters
are `value`, `max` and `players` - and each of those getters returns its value
as the command *result* (`get value` → the value, `get max` → the max,
`get players` → the online-player count), so `execute store result score`
around the getters folds bossbar state into the existing scoreboard oracle.
The same is true of the setters: `bossbar set value|max <v>` returns the
written number when the value changed and 0 with a nothing-changed failure
when it did not. The remaining set shapes (`color`, `visible`, `name`, `style`)
have no 26.3 getter at all - their state is client-rendered - so they are
covered by the same nest-host wrap (every `BossBarCommands` command wraps
identically; the wrap parses no arguments) but their effects are not
RCON-observable, and the closure text says so.

**26.3 bossbar behaviours, measured not assumed.** All are recorded in the
fixture headers. `bossbar add` returns result 1 on success and fails with "A
bossbar already exists with the ID ..." on a duplicate, which makes the
fixtures non-idempotent across the sweep's repeated iterations; both fixtures
reset the bar through a bare leading `bossbar remove` instead, relying on the
measured fact that a failing bossbar command does not abort the remaining
function lines (verified separately with a throwaway fixture, then removed).
`bossbar remove` returns result 0 whether or not a bar was removed, and a get
on an absent bar fails with "No bossbar exists with the ID '<id>'" - the
row's unknown-bar edge. A store-wrapped failing get reports
(success=false, result=0) to the store callback, the same measured semantics
batch 8 recorded for data commands, and the ops fixture's final case pins it:
after a bare remove, the store around `bossbar get value` must write 0 over
the previous read's 43, so a store that skipped the write or kept the old
value fails the match. The sweep maps also re-confirmed batch 8's debit model
on a new command family: store chains cost 2 debits, bare commands 1, taken
conditions 2, failed conditions 1, and both fixtures' completion cases land
at exactly quota 16.

**Bare bossbar lines stay vanilla, by design.** The specialization counters
(bossbar_compiled_st02_bossbar_ops/_values, added for this row) read exactly
the store-chain counts: three and four chained lines wrapped (reading 6 and 8,
the same per-line doubling per generation the DataStore counters show), while
bare `bossbar` lines never increment. That is not a defect introduced here:
the EXECUTE-stage parser list does not include `BossbarParser`, nor the other
state-machine parsers outside `StateMachineParser`'s tag/teleport/kill
shapes, so bare `title`, `effect`, `setblock` and `bossbar` lines run on the
vanilla path. The wrap is semantics-preserving by construction, so parity
holds either way; the fixtures prove the chained shapes specialize, and the
row's closure text states the bare-line scope.

**Batch 10 - the `item modify` half of the item row, closed with a confirmed
datapack-defined modifier id (matrix case ST-06).** Fixture
`st06_item_modify` plus the modifier
`data/function_compiler_probe/item_modifier/st06_set_count.json`
(`function_compiler_probe:st06_set_count`, `set_count 5`), run in all ten
arms with exact score-sequence parity. Closed **ST-06** together with
STATE-004, which had verified the `item replace` slot edges in batch 6 and
left `item modify` blocked on a confirmed id. The table is now 92 rows:
89 covered, 0 partial, 3 missing.

**The measurement that unblocked the row.** STATE-004 had recorded that
`minecraft:set_lore` and a datapack-defined id were both "rejected". The
pinned-server probe resolved why, in three steps. First, the 26.3
`minecraft:item_modifier` registry ships **no built-in modifiers at all** -
`minecraft:set_lore` fails with "Can't find element 'minecraft:set_lore' in
registry 'minecraft:item_modifier'", so no vanilla id ever existed to
confirm. Second, every id is datapack-defined at
`data/<namespace>/item_modifier/<name>.json` as a **single JSON object keyed
by `type`**: the array form fails with "Not a JSON object" and the legacy
pre-1.20.5 `function` key fails with "No key type" - and both are
**boot-fatal** ("Failed to load datapacks, can't proceed with server load"),
which is what had earlier killed the probe server outright rather than
merely rejecting the id. Third, with a well-formed file the command works:
`item modify` returns result 1 on success, is idempotent in its result, and
a store around it writes that result.

**Failure semantics, measured.** A modify on a slot the target does not
have (an armor stand's `weapon.offhand`) is a runtime failure that reports
(success=false, result=0) to the store callback and does not abort the
remaining function lines - the same measured semantics batch 8 recorded for
data commands and batch 9 for bossbar commands. An id the registry lacks is
different: it is validated at **command-parse time**, so a function line
referencing one fails the *function load* with "Can't find element ... in
registry 'minecraft:item_modifier'" - the unknown-id edge cannot be a
fixture line, and it is recorded in the fixture header instead. Two more
read-from-the-server facts went into the probe record: a malformed item
modifier file is boot-fatal for the whole datapack, and 26.3 mob equipment
NBT lives at `equipment.mainhand` (no `HandItems`), materialising only once
an item is placed.

**The fixture and its oracle.** Three cases inside one 0-16 sweep: the
stored modify result 1 (quota 6), the modifier's observable effect
`minecraft:diamond[count=5]` read back with `execute if items` (quota 8),
and the same on a fresh emerald in hotbar.8 (quota 12, the completion
signal). Every case targets the probe player, whose inventory replaces
deterministically at the head of each iteration, and the measured quota map
re-confirmed batch 8's debit model on another new family: bare item
commands 1, the store chain 2, taken conditions 2. The
`custom_name` component applied by a `set_name` modifier is observable in
entity NBT but did not match an `execute if items` component predicate in
either the canonical string or the SNBT object form, so the fixture reads
the effect back through `count` instead - a probe finding recorded here
rather than a fixture claim.

**Specialization scope.** The new dedicated per-function item-command
compile counter (`item_command_compiled_st06_item_modify`) reads exactly
the store-chain count - one chained line, reading 2, the same per-line
doubling per generation the DataStore and bossbar counters show - in the
six compiling arms, and exactly 0 in wrapper-off/on and
selective-macro-arguments. Bare `item` lines are not in the EXECUTE-stage
parser list and stay on the vanilla path, like the other state-machine
families outside tag/teleport/kill; the fixture's `execute if items`
conditions go through `ItemPredicateParser` and do not increment the
item-command counter. The row's closure text states the bare-line scope.

**Batch 11 - the unordered fork selector sorts, closed with measured identity
semantics (matrix case MO-09).** Fixtures
`mo09_fork_arbitrary_identity` and `mo09_fork_random_identity` plus an
identity/freshness block in the harness fork-order fixture runner, run in
all ten arms with the fork fixture result compared exactly against the
mod-free vanilla arm. Closed **MO-09**; cap fallback was already under
QUOTA-009, which the row now cites alongside the new case. The table is now
92 rows: 90 covered, 0 partial, 2 missing.

**The measurement that pinned the oracle.** The §11.2 note that the harness
"records effects, not identities" was resolved by making identity observable:
a two-branch `#fork_order_acc >< @s` swap chain with distinct actor values
leaves the first forked actor holding the accumulator's marker, the
accumulator holding the second actor's original value, and the second actor
holding the first actor's original value, so scoreboard read-back per
tag-pinned actor decodes the selection order. Measured on the pinned vanilla
server before the oracle was pinned: `sort=arbitrary` resolves candidates in
**entity insertion (summon) order**, not position order - a reverse-summon
control (c, b, a) resolved (c, b) - and that order is stable across repeated
invocations, `/reload`, a server restart on the same world, and fresh worlds
with different seeds, which is what makes an exact oracle legitimate.
`sort=random` is **non-deterministic by design**: 24 direct trials over three
actors covered all three candidate pairs 8/8/8 with every trial exactly two
distinct actors, so the row's claim for random is narrowed to per-trial set
semantics plus a distinct-pair floor across trials (at least 2 distinct
pairs in 16 trials per path), proving the compiled fork delegates selection
to vanilla's randomness instead of pinning it.

**What the harness now asserts per arm.** For `sort=arbitrary`: identity
order (a, b) across 5 direct and 5 function trials; a cap sweep of the swap
showing the cap includes the parent context - cap 1 reports the
maximum-context error, cap 2 truncates silently with no feedback, both
leaving state untouched, and caps 3+ fork both branches in selection order
(the same boundary QUOTA-009 recorded for the ordered sorts); and
candidate-list freshness - killing selected actor b must change the next
invocation's selection to (a, c) on both paths, and killing all actors and
re-summoning the canonical sequence restores (a, b). For `sort=random`: 16
direct and 16 function trials each selecting exactly two distinct actors
with at least two distinct pairs, and the deterministic pair {a, c} after
the kill. The fork modifier has no dedicated compile counter, so
specialization parity rests on the exact score-state parity of the
swap-chain read-backs plus the existing ordered-sort fork fixtures.

**Batch 12 - the fork modifier under the pinned Bellows/Moonrise mod stacks,
closed with a mod-stack probe (matrix case MO-10).** The full fork-order
fixture - ordered nearest/furthest identity, the batch-11 unordered-sort
identity block, the cap sweep, and the candidate-freshness block - ran with
the compiler enabled (wrapper and ScoreAdd prototype flags) under three
pinned, hash-verified stacks: `bellows113` (Bellows 1.1.3),
`bellows113-moonrise120` (plus Moonrise 1.2.0) and `lbm113120` (plus
lithium 0.26.2), each a fresh Gradle `runServer` with the stack jars in the
run directory. Closed **MO-10**. The table is now 92 rows: 91 covered,
0 partial, 1 missing.

**Result and scope.** Every stack passed every fixture assertion, and each
stack's recorded fixture result is exactly equal to the mod-free vanilla
arm's recorded result from the batch-11 ten-arm run: Bellows's selector
instrumentation and Moonrise's entity system rewrite change neither the
arbitrary insertion-order resolution nor the random set semantics this
fixture observes, and no interaction with the compiled fork appeared. The
oracle is within-stack direct-vs-function parity - the modded server is its
own reference - because a mod may legitimately change entity iteration
order; the cross-stack equality is the recorded finding, not the oracle.
The row's claim is scoped to the pinned stacks combining Bellows and
Moonrise, which is the interaction the coverage row names; the remaining
pinned stacks (c2me, ferritecore, bellows 1.1.2, Moonrise 1.2.1) and any
unpinned stacks are not claimed for fork semantics.

**Batch 13 - the callback-context x child-outcome matrix, closing the ten
partial P0 cases that shared one open end (HOOK-001, HOOK-005, HOOK-009,
CTRL-001/002/003/005/006/007, SCORE-009).** The shared open end was "other
return/error callback combinations". Rather than tail-chasing combinations, the
batch enumerated the case oracles as a matrix - the function-callback contexts
{plain nested, `return run function`, `execute if function`,
`execute unless function`, `execute store result/success function`} crossed with
child outcomes {return value, `return fail`, syntax exception} - and found 15 of
18 cells already had ten-arm fixtures. Three cells were added, each measured on
the pinned vanilla 26.3 server before any assertion was written, and each
recording a measured semantic that no earlier fixture had:

1. `cbx_return_run_fail` (+ child `cbx_return_run_fail_child`): a failed
   `return run` reports `Function ... returned 0`, discards the child's pending
   fused tail **and ends the parent frame**, so the parent's own pending
   `+1000` tail is discarded too (score 31; the 0-16 map starts
   `0,0,1,1,11,31...`; five command events in the trace).
2. `cbx_nested_fail`: a *plain nested* child that fails discards only its own
   `+100` tail - the parent's pending `+1000` fused tail resumes once through
   both additions (score 2031; two executing regions in fused and bytecode,
   contrasted with the store/if siblings whose lone-add children have no region
   of their own).
3. `cbx_unless_success`: a child returning a value discards its pending tail,
   makes `execute unless function` false so its branch is skipped, and lets the
   parent's own pending `+1000` region resume (score 2002, six command events).

**Two harness defects this batch found in its own new fixtures, and what fixed
them.** First, the initial `expected_command_events` gates for the three traces
were transcribed from the vanilla server's `Traced N command(s)` response,
which excludes the child's `return fail` command; the harness counts `[C]`
lines in the trace *file*, so all three gates were off by one until the vanilla
trace files were read directly. The lesson matches the batch-3 truncation
finding: the server's own summary is not the measurement - read the artifact.
Second, the first full run failed in `fused-interpreted` on
`cbx_nested_fail` executing two backend regions where the sibling cases assert
one; that was not a compiler defect but a fixture-shape mismatch, and
`run_case` gained an `expected_backend_regions` parameter so a case may assert
the measured count instead of only the single-region shape. The arm-parity
comparison's `backend_region_metrics` strip list gained the three new case
names, for the same reason the nine siblings are stripped: region counters are
implementation observations, not vanilla-observable facts, and every fused and
bytecode arm otherwise mismatched the mod-free vanilla arm on that one key.

**Result and scope.** The full ten-arm run of 2026-11-08 (mod-free vanilla,
wrapper-off/on, score-add-on, instrument-only, score-add-timed,
fused-interpreted, bytecode-emitted, bytecode-compile-failure,
selective-macro-arguments) matched vanilla exactly for direct-function state,
results, traces, reloads and forks including all four `cbx_*` fixtures, and the
callback cases are recorded *complete* in the matrix with the earlier cited
compatibility-arm runs retained. The ten cases above are now recorded complete;
that leaves nine partial P0 cases (HOOK-002/003/004/006/008, SCORE-007,
QUOTA-009, PERF-001, STATE-004) and the BC-06 campaign row. Closing these ten
cases amends matrix verdicts only - the coverage rows were already R under the
§11.1 narrowing convention.

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
