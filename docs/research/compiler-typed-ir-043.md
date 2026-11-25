# IR-043 — Typed conditional static function dispatch

**Status: completed — native differential and controlled dispatch CPU pilot accepted (2026-11-25).** Research-only, disabled by default; draft PR #10 on work/compiler-coverage.

## Design

IR042 observed 21,272 unsupported function-dispatch entries among its sampled publisher functions. Typed execution had a qualified 75.54% cumulative synthetic CPU reduction, while the isolated ASM backend and direct scheduler did not establish additional gain. IR043 extends the mixed program with a typed call boundary (D), not a new ASM-only optimization. Each call remains one original source position, flushes any preceding score region, and excludes direct-function cursor admission for its caller. Call-only functions are materialized rather than discarded when no scoreboard regions exist.

Supported: bare namespace-qualified static function identifiers and single or 2–8 ordered pure score range/comparison predicates, literal fake holders or live @s, no source transformations. Validate exact source shape, actual parsed modifier/terminal identities and original CustomCommandExecutor. No pre-resolved callee object, child body inline, synthetic callback, command-context rewrite, or copied scheduler. Delegate to the original native parsed terminal with the original source, chain modifiers and ExecutionControl.create(context, frame). Native function target resolution remains live, including missing targets and reload. Decline tags, macro argument calls, return run, source changes and unsupported stages. Legacy callback-mutating prototypes incompatible.

Shared CompoundScoreIR plan preparation takes optional terminal operands, so call predicates reuse the absence-aware range and comparison analysis and ordered known-pass/fail stages. Single guard uses allocation-free local reads; compound uses command-local scratch, with no cross-call score caching. Fallback before effects for missing objectives/entity, nonempty callback, tracer, restrictive fork limit. No predicate mutations or objective writes. Compound empty-source suffix still pays all modifier debits. Native custom terminal is invoked in the original BuildContexts entry, with no additional ExecuteCommand debit or mid-chain quota gate. Verified mapped 26.3 BuildContexts bytecode in IR025 evidence (artifact 14694236421 offsets 343–464). The original native custom executor owns child queue creation, function errors, callbacks and return semantics.

## Native gate

Five modes: native, same-feature old bytecode (dispatch disabled), typed interpreter, typed bytecode, direct enabled. Reuse IR019's original seven dispatch roots plus new recursion, mutation-order, mixed region, single/multiple conditions, eight-stage suffix, missing row/objective/function, entity/no-entity, child return, execute-store callback and opaque forms. All quota 1..40, 48, 64, 128, 65536. Compare exact scoreboard snapshots and expected full-quota values; verify D nodes and direct exclusion, positive entered/pass/fail/fallback/reuse/proof/suffix counters only with feature enabled. Existing IR008 and IR013 native regression jobs. No special trace fixture or restrictive fork-limit fixture yet.

## CPU gate

Separate diagnostic preflight: identical 64-line parent twins, shared pristine native one-line child. 32 passing and 32 failing guarded calls per parent, exact increments, all 64 D nodes, native ledger excluded, actual entry/call/skip counts, zero fallbacks on timed shape. No direct scheduling or diagnostics during timing. Reuse IR042 calibration/qualification unchanged (fastest 750ms target, >=500ms per window, six consecutive warmup windows, two holdout rounds, two JVMs, A/A <=5%, counterbalanced ABBA/BAAB; fixed work, all observations archived). CPU script uses 64 top-level command visits per function, plus 32 native child visits verified by exact score. No publisher claim or promotion. Performance claim requires semantic gate too.

## Results

[Research run 45554554773](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45554554773), tested commit `774e5d7d`; [manual-only restoration CI 45554596934](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45554596934) passed. All four research jobs completed.

### Native acceptance

[Raw native evidence](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45554554773/artifacts/14995715826): 880 observations per mode, 4,400 total; exact parity in all five modes. Each enabled mode lowered 31 sites, entered 1,494 dispatches: 829 calls, 402 skips, 263 native fallbacks; 660 reused operands, 183 proofs, 328 empty-stage debits. Feature-off counters zero. IR008 and IR013 inherited regression jobs passed (IR013 retains its intentional unsafe negative control). Dedicated trace and restrictive fork-limit fixtures remain open.

### Controlled CPU acceptance

[Raw CPU evidence](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45554554773/artifacts/14994967570) and [job logs](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45554554773/job/139003447525). Preflight: all 64 parent positions are D nodes; 8,192 typed entries, 4,096 calls, 4,096 skips, 8,192 reused operands, 6,144 proofs, zero fallbacks; final x=4096 in both arms. Two timed JVMs calibrated at 32 batches/window, fastest calibration 773.407 and 771.387 ms; six warmup rounds each. Both boots completed. Paired CPU reductions 39.9888%, 40.4784%, 39.6155%, 39.9419%; boot medians 40.2336% and 39.7787%; overall paired median **39.9653%**; maximum absolute A/A 1.9179% (limit 5%). Pilot gate true. Denominator is top-level source visits, with equal verified child work; no claim of whole-pack speedup or four independent JVM trials.

### Disposition

Accept IR043 for its tested scope; no default change, scheduler replacement, or promotion. Raw ZIP audit subsequently independently matched all 880 snapshots in each of five arms, recalculated all 64 timed block windows (minimum 746.236 ms CPU), confirmed exact per-window work, both complete boots, maximum A/A and paired median from archived numeric samples. The IR042 count of 21,272 function-dispatch reaches is an opportunity bucket, NOT actual newly admitted sites. Next reconcile exact publisher site shapes, observed visits and parsed D admission, and rank remaining execute modifiers before selecting IR044. Keep workflow manual-only and PR draft.
