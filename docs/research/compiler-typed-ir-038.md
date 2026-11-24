# IR-038 — Extended scoreboard IR and same-command predicate CSE

**Status: implemented; native acceptance pending (2026-11-24).** This is a larger, cohesive compiler milestone rather than a new research campaign for each local transformation. Work is on draft PR #10, `work/compiler-coverage`.

## Scope and rationale

Extend the existing post-Brigadier typed language with non-throwing, single-write min/max scoreboard operations (`<`, `>`) and all five score-to-score conditional operators (`=`, `<`, `<=`, `>`, `>=`). Both `if` and `unless` are supported. Validated literal fake holders and the existing independently opted-in `@s` support remain the eligibility boundary. Division, modulo, swap, selectors with multiple targets, and complex modifier chains are **not** admitted by this milestone.

The new coverage requires `FC_TYPED_IR_EXTENDED_SCORE=true` in addition to the existing namespace/mode configuration. Absent the flag, IR-037's command eligibility remains unchanged. This is an experimental feature; no production promotion or default change.

## Compiler changes

- `TypedScoreIR.BinaryOperator` and `TypedIROptimizer.Op` represent minimum and maximum. Interpreter, exceptional queued-tail interpreter, and generated ASM perform the same single target write and preserve original feedback.
- `TypedScoreIR.Conditional` represents either an already-parsed range or a parsed comparison, never both. The second read-only guard operand participates in the effect set and dynamic-holder analysis. Source eligibility and both operands/operator are checked against Brigadier callback metadata.
- The IR-037 prepared-step transformation now proves exact objective-name equivalence across target, left and right predicate operands, and binary terminal source. It reuses only a freshly resolved Objective within a single command, before any mutation or callback.
- Exact same-slot comparison CSE: if both guard operands have identical objective and holder identity (two equal fake names or two `@s` references), reuse the first read-only score record. For an absent score, the predicate remains false; we **must not** fold a reflexive predicate to unconditional true. No row is created by predicate reads. Distinct slots always use independent reads. This is conditional common-subexpression elimination, not cross-command value propagation.
- All source instructions, quota boundaries, trace, feedback, score mutations, original fallback and reentrant queue continuations are preserved. Diagnostic counters count new min/max steps, comparison evaluations and duplicate predicate score lookups avoided. They are not timing estimates.

## Acceptance and consolidated testing

Ordinary CI builds Java 25 / Minecraft 26.3 and runs existing IR-034–037 contracts, plus IR-038 source/fixture tests. The focused `scripts/ci_typed_ir038.py` reuses the existing IR-017 launcher, original no-result call harness, callback observer, and snapshots. It compares five independent JVMs: native, existing bytecode with the extension off, extended interpreter, extended ASM, extended direct scheduler. Eight new fixtures and five inherited fixtures are exercised with full quota plus eight bounded quota values (117 observations per arm). Admission checks require full typed coverage of the supported fixture patterns and original opaque barriers for division/modulo/swap. Active arms must execute all new kinds of operations, elide duplicate predicate reads, and yield to a real callback; off-control counts must stay zero.

Run the existing four-mode IR-008 and six-mode IR-013 suites as regression gates, without changing their default flags. Archive all native outcomes and logs. A failed gate cannot be treated as acceptance. No CPU-speedup claim, given IR-033's measurement stability rejection.

## Limits and decisions

New feature flag, choice of non-throwing single-write operators, and the larger bundled scope are milestone design decisions. The proof assumes vanilla pure same-thread score/objective lookup behavior; arbitrary third-party side effects on reads are not covered. Tests use literal holders; dynamic-holder coverage remains separately opt-in and needs its own targeted extension evidence. Added IR metadata has a memory/compile-time tradeoff. Keep draft PR unmerged, and expensive native workflow manual-only after launch.

## Results

Pending.
