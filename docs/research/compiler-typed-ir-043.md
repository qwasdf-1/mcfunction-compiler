# IR-043 — Typed conditional static function dispatch

**Status: implementation complete; native and CPU acceptance pending.** Research-only, disabled by default; draft PR #10 on work/compiler-coverage.

## Design

IR042 observed 21,272 unsupported function-dispatch entries among its sampled publisher functions. Typed execution had a qualified 75.54% cumulative synthetic CPU reduction, while the isolated ASM backend and direct scheduler did not establish additional gain. IR043 extends the mixed program with a typed call boundary (D), not a new ASM-only optimization. Each call remains one original source position, flushes any preceding score region, and excludes direct-function cursor admission for its caller. Call-only functions are materialized rather than discarded when no scoreboard regions exist.

Supported: bare namespace-qualified static function identifiers and single or 2–8 ordered pure score range/comparison predicates, literal fake holders or live @s, no source transformations. Validate exact source shape, actual parsed modifier/terminal identities and original CustomCommandExecutor. No pre-resolved callee object, child body inline, synthetic callback, command-context rewrite, or copied scheduler. Delegate to the original native parsed terminal with the original source, chain modifiers and ExecutionControl.create(context, frame). Native function target resolution remains live, including missing targets and reload. Decline tags, macro argument calls, return run, source changes and unsupported stages. Legacy callback-mutating prototypes incompatible.

Shared CompoundScoreIR plan preparation takes optional terminal operands, so call predicates reuse the absence-aware range and comparison analysis and ordered known-pass/fail stages. Single guard uses allocation-free local reads; compound uses command-local scratch, with no cross-call score caching. Fallback before effects for missing objectives/entity, nonempty callback, tracer, restrictive fork limit. No predicate mutations or objective writes. Compound empty-source suffix still pays all modifier debits. Native custom terminal is invoked in the original BuildContexts entry, with no additional ExecuteCommand debit or mid-chain quota gate. Verified mapped 26.3 BuildContexts bytecode in IR025 evidence (artifact 14694236421 offsets 343–464). The original native custom executor owns child queue creation, function errors, callbacks and return semantics.

## Native gate

Five modes: native, same-feature old bytecode (dispatch disabled), typed interpreter, typed bytecode, direct enabled. Reuse IR019's original seven dispatch roots plus new recursion, mutation-order, mixed region, single/multiple conditions, eight-stage suffix, missing row/objective/function, entity/no-entity, child return, execute-store callback and opaque forms. All quota 1..40, 48, 64, 128, 65536. Compare exact scoreboard snapshots and expected full-quota values; verify D nodes and direct exclusion, positive entered/pass/fail/fallback/reuse/proof/suffix counters only with feature enabled. Existing IR008 and IR013 native regression jobs. No special trace fixture or restrictive fork-limit fixture yet.

## CPU gate

Separate diagnostic preflight: identical 64-line parent twins, shared pristine native one-line child. 32 passing and 32 failing guarded calls per parent, exact increments, all 64 D nodes, native ledger excluded, actual entry/call/skip counts, zero fallbacks on timed shape. No direct scheduling or diagnostics during timing. Reuse IR042 calibration/qualification unchanged (fastest 750ms target, >=500ms per window, six consecutive warmup windows, two holdout rounds, two JVMs, A/A <=5%, counterbalanced ABBA/BAAB; fixed work, all observations archived). CPU script uses 64 top-level command visits per function, plus 32 native child visits verified by exact score. No publisher claim or promotion. Performance claim requires semantic gate too.

## Results

Pending.
