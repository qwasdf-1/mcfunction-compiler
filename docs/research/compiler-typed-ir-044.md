# IR-044 — Single-condition native terminal specialization and publisher admission

**Status: implementation and preregistered gates pending execution.** Research-only on work/compiler-coverage; PR #10 remains draft. No production defaults change.

## Selection from the original IR042 archive

Read the archived 347 source sites, 17 functions, 257,697 native reaches. Original [archive](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45516230461/artifacts/14978057388). Of 21,272 dispatch reaches, 14 bare static sites contributed 14,487, 26 pure-score static sites contributed 4,216 (18,703 combined, 87.92% source-shape screen); 11 other sites contributed 2,569. No parsed-admission or speedup inference from these counts. Five archived input strings are truncated; join against SHA-pinned full original source before classification. Actual ledger must reconcile D source indices with archived visits.

Three if-block-to-tag sites in erb:capture/store account for 17,307 visits and only 230 ordinary terminal callbacks. Single score-guard-to-tag candidates add 5,771 visits (one separate return-run-tag site excluded). These 23,078 visits explain nearly all of the 23,710 execute_other bucket. Data/store 6,547; other dispatch 2,569, mostly source changes (as/at). Existing selector-fork, macro, tag-index and NBT experiments have not established a new removable cost; do not reopen from visit counts alone. Prioritize a reusable single-condition native ordinary-terminal control node over new world-state caches or new scheduler.

## Implementation boundary

G is a one-source-position node: a validated single vanilla if/unless block (literal namespaced block/tag, integer absolute/relative coordinates) or single score condition, followed by native tag @s add/remove. Also allow block-conditioned literal fake-holder scoreboard add to expose the generic terminal boundary without an entity in the benchmark. Existing score-to-score lowering unchanged. No custom terminal, return, store, chained modifier, selector transformation, local coordinates, block state/NBT syntax or modded redirect admission. Exact parsed guard and terminal identities required. Native condition still evaluates live world/score state; this is **orchestration specialization**, not replacement of native predicate or mutation. Preconstruct immutable native ExecuteCommand and retain original action, skip collection-building loop for single guard, queue same native terminal on pass. No mid-stage quota test or synthetic callback. Trace, nonempty result callback or restrictive fork limit fallback before any debit. Use native ContextChain.runModifier with no-op consumer, same fork semantics, no repeat after effects. Native bytecode basis: IR025 mapped BuildContexts offsets 130–317, 343–551, ContinuationTask singleton offsets 39–57 and ExecuteCommand fields/execute. G prevents direct-function cursor admission. Default off via FC_TYPED_IR_GUARD_TERMINAL.

## Preregistered acceptance

- Publisher: join exact original full-source rows and original native reaches against actual per-function parsed ledgers with explicit exact function allowlist; report D/G counts and nonadmitted sites. No need to rerun unchanged unqualified timing. A bounded original capture/restoration diagnostic is desirable, not a performance claim. Source eligibility is distinct from parsed admission, which is distinct from optimized runtime visits.
- Native differential: native, same-feature disabled control, interpreter, bytecode, direct enabled. Live block/tag changes, relative and absolute positions, pass/fail/negative conditions, missing score/objective, tag errors, no entity, return and store barriers, low quota, mixed neighboring typed regions; exact tag/score state and expected full-quota cases. Verify actual G counts, fallback and direct exclusion. IR043 regressions retained.
- CPU: original native twin, compiled twin, 64 single block guard commands, 32 successful native scoreboard increments per call, both paths same terminal callbacks, two JVMs, prior IR042 calibration, >=500 ms, six consecutive warmup windows plus two holdouts, ABBA/BAAB, max A/A <=5%. Preflight exact G paths and work; no diagnostics in timing. Only the tested block-to-score terminal workload qualifies, not tag or publisher CPU. No changes to gate thresholds if it fails.

## Results

Pending.
