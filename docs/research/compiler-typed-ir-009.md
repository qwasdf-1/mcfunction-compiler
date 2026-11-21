# COMPILER-IR-009 — Direct scoreboard binary arithmetic and conditional bytecode

**Status: IMPLEMENTED; bounded native semantic gate ACCEPTED on Minecraft 26.3 / Fabric / Java 25. Research-only, no production promotion (2026-11-19).**

**Parent:** [COMPILER-IR-008](compiler-typed-ir-008.md), which first introduced post-Brigadier typed mutation IR, an interpreted reference and real ScoreAccess.add/set JVM bytecode. **Branch:** `work/compiler-coverage`, existing draft [PR #10](https://github.com/qwasdf-1/mcfunction-compiler/pull/10). All work remains unmerged and disabled by default.

## Implementation and compiler boundary

The new compiler consumes vanilla-parsed scoreboard commands and constructs an immutable typed `Program` from a bounded sequence of 2–64 `Instruction` entries. The emitted ASM no longer wraps `ContextChain.runExecutable` for accepted commands. There are now three IR instruction families:

| IR | Accepted vanilla source shape | Emitted JVM semantics |
| --- | --- | --- |
| `Mutation` | `scoreboard players set/add/remove #literal objective integer` | `ScoreAccess.set` or `ScoreAccess.add` |
| `Binary` | `scoreboard players operation #target objective =/+=/-=/*= #source objective` | Direct `ScoreAccess.get`, `set`/`add` and integer multiplication (`IMUL`) |
| `Conditional` | `execute if/unless score #guard objective matches N run scoreboard players set/add/remove #target objective integer` | Runtime score guard evaluation, emitted JVM conditional jump, and directly emitted terminal mutation on the taken branch |

Only **literal fake scoreboard holders** and the exact single-stage integer `matches N` predicate are eligible. The typed classes are `TypedScoreIR.Mutation`, `Binary` and `Conditional`; they share the interpreter and ASM backend. The compiler uses already-validated Brigadier command callbacks (`ScoreAddCommand` / `ScoreOperationCommand` / `ScoreConditionCommand`); text checks are **restrictive eligibility checks**, not replacement parsers.

**Explicitly *not* lowered:** division, modulo, min/max, two-way score swap, selectors such as `@s`, multi-stage `execute`, score-to-score comparisons, general `matches 1..7` ranges, functions, macros, arbitrary return/fork paths, mod-added or otherwise unrecognized commands. Their original parsed scheduler entries remain in place. A declined command splits an accepted region; compilation of a single isolated command is intentionally skipped.

The existing score-condition modifier parser used `targets` where Brigadier's actual condition node is `target`. IR-009 corrects that lookup only when the function belongs to the *explicitly opted-in* typed-IR namespace **and** the entire original source matches the narrow supported literal condition/terminal shape. The correction does not silently widen acceptance of unrelated modifiers in production or in the older fusion prototype.

### Semantics and guardrails

- `TypedScoreIRRuntime.State.begin` checks the current command quota, resolves the **current** scoreboard objectives, emits tracing, charges the per-command debit, evaluates conditional reads without inventing a missing score, and charges the additional modifier-stage debit on a passing condition. A failed `if` (or true `unless` negation) skips its terminal mutation with the original visible result.
- Original-command fallback is used before any direct-path debit/state change when an objective becomes missing or read-only. All instructions retain their original parsed `FusedCommand`. A Java class-generation failure selects the typed-IR interpreter before executing the program, not a partially applied bytecode fragment.
- Each accepted binary reads source and target scores through current `ScoreAccess` objects, and performs the same single-score update as its supported vanilla operation. Self-operations, signed arithmetic overflow and command feedback are included in the bounded semantic test.
- `finish` uses Minecraft's `CommandResponseTracker` and the original scoreboard message families, including operation feedback, tracing and handled syntax errors. Normal Minecraft execution frames and function ordering remain intact; there is no scheduler replacement or quota relaxation.

### Effects: safe groundwork rather than unsound cached values

Each instruction has an explicit immutable `Effects(reads, writes, observableBoundary)` over named `Slot(holder, objective)` keys. Assignment reads the source but not the previous destination; mutation-add reads/writes its target; binary arithmetic reads source and target; a conditional reads its guard as well as the terminal operation's conservatively modeled reads, and may write the terminal target.

All recognized instructions currently set **`observableBoundary=true`**, because command feedback, tracing and other mods' scoreboard callbacks could observe or change intermediate state. `mayReuseValueAcross` therefore does **not** authorize forwarding cached scoreboard values across these commands. No redundant write is deleted and no write is delayed; a future optimization pass must first prove a non-observable region under a documented effect and callback model. This milestone lays the groundwork, not an already implemented cross-command elimination pass.

## Native validation — accepted

[Final four-JVM native CI run #44647474632](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44647474632) · [Complete archived per-arm logs and JSON](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44647474632/artifacts/14588768082)

Four independent actual Minecraft 26.3 Fabric / Java25 JVMs ran the same disposable datapack through:

1. vanilla function path with the compiler wrapper disabled;
2. existing fused region execution;
3. typed IR interpreter;
4. emitted ASM direct bytecode.

**All four produced exactly matching scoreboard state** across full arithmetic, multiply/subtract/self-operation, conditional true/false and absent-score guards, missing-then-created guard objective, missing read-only destination tests, an intentionally unsupported score division barrier, an unsupported range-predicate barrier, nested function calls, stored results and integer overflow. Low-quota snapshots matched for ordinary mutations, binary operations, guarded execution, and missing-guard-objective fallback at quotas **1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 32**.

| Diagnostic counter | IR interpreter | Emitted ASM |
| --- | ---: | ---: |
| Typed regions compiled | 16 | 16 |
| Bytecode regions created | 0 | **16** |
| Typed regions executed in bounded semantic phase | 58 | 58 |
| Direct instruction executions | 197 | 197 |
| Binary instruction executions | **34** | **34** |
| Taken conditional terminal mutations | **18** | **18** |
| Skipped conditional branches | **16** | **16** |
| Runtime fallbacks to original command | **15** | **15** |

Counters only run in diagnostic testing. This verifies that compiler acceptance is not confused with actual dispatch or execution. All expected partial-effect observations matched, including quota exhaustion before later writes.

**Development failures excluded from accepted evidence:** the initial runner's `fc_missing` substring query incorrectly matched `fc_missing_guard` (harness issue, corrected); a second run showed zero conditional activations because the old `targets` parser bug declined literal guards (corrected within the research-only literal source gate). Only passing native runs are accepted as semantic evidence.

## Performance scope and follow-up

The four-arm runner retains the older **64 bare-add benchmark** for a lightweight CPU screening check. Its independent-JVM CPU measurements are **not a causal effect of IR-009**, do **not** exercise the new scoreboard binaries/guards, and are **not** a reason to promote this feature. No real-world datapack comparison or new same-JVM binary/conditional crossover is claimed. The earlier IR-008 directional crossover pertains only to bare score-add regions, not these operations.

The IR-009 implementation is an architectural extension, **not yet a generally optimizing compiler**. The next development stages should implement a rigorously specified observer/alias/effect model before any cross-instruction score promotion, test exact debug traces and callback failure behavior, and add representative multi-command real datapacks plus independent-JVM performance confirmation before changing a default.

**Decision:** Keep research mode gated by `FC_WRAPPER_PROBE=true`, `FC_TYPED_IR_NAMESPACE=<explicit namespace>` and `FC_TYPED_IR_MODE=interpreted|bytecode`. `FC_TYPED_IR_DIAGNOSTICS` and `functioncompiler ir008` remain development-only activation observability; no production default, broad patch or existing runtime config is changed.
