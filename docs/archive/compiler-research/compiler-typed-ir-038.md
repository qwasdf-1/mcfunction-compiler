# IR-038 — Extended scoreboard IR and same-command predicate CSE

**Status: implemented; native semantic acceptance passed (2026-11-24).** This is a larger, cohesive compiler milestone rather than a new research campaign for each local transformation. Work is on draft PR #10, `work/compiler-coverage`.

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

## Results — accepted

[Native run 45448263135](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45448263135) completed successfully, with [archived evidence 14948730165](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45448263135/artifacts/14948730165). The implementation and restored manual-only workflow also passed [ordinary CI](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45448321439).

| Gate | Observed result |
| --- | --- |
| IR-038 focused five-JVM suite | 117 state/quota observations per mode; all matched vanilla |
| IR-008 four-JVM regression | 62 cases; native parity |
| IR-013 six-JVM regression | 85 cases per mode; zero differences for all three guarded modes |
| Unsafe negative controls | 46 differences each in unsafe bytecode and direct modes, as expected |
| Java 25 build and source contracts | Passed |

Across the eight new fixture functions, the old bytecode configuration lowered 12 of 56 source lines into typed regions; the extended configurations lowered 53 of 56. The remaining three lines are the deliberately unsupported division, modulo and swap operations. Across the complete loaded test corpus the typed-line counter increased from 38 to 127. These are fixture-specific coverage results, not estimates of typical datapack coverage. The old-bytecode control also disables the preexisting ranged-guard flag, so this comparison is not a single-flag ablation.

| Diagnostic | Old bytecode | Extended interpreter | Extended bytecode | Extended direct |
| --- | ---: | ---: | ---: | ---: |
| Typed min/max steps | 0 | 42 | 42 | 42 |
| Comparison evaluations | 0 | 74 | 74 | 74 |
| Duplicate predicate row lookups avoided | 0 | 16 | 16 | 16 |
| Objective-name lookups avoided (IR-037 counter, including inherited paths) | 6 | 244 | 244 | 244 |
| Reentrant yields | 8 | 20 | 20 | 20 |

All extended modes exercised the new lowering and local read elimination. The matching observations include absent rows, missing objectives, comparison branches, quota truncation, and callback ordering. The 244 objective-lookup count includes inherited IR-037 optimizations; it is not an incremental IR-038 savings estimate. The same-slot counter counts avoided row lookups, not elimination of every subsequent value accessor. No CPU timing or production promotion follows from these counts.

**Disposition:** accepted for tested literal-holder configurations. Dynamic-holder comparison extension and arbitrary third-party read-side effects remain outside the demonstrated parity scope. The extended score flag remains off by default; PR #10 remains draft/unmerged. The native workflow is restored to manual-only.
