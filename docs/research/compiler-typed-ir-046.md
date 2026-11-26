# IR-046 — Effect-bounded cross-command guard reuse

**Status: implementation and fixed studies staged; acceptance pending.** Research-only, default off, draft PR #10. See [candidate investigation](compiler-typed-ir-046-candidate-investigation.md).

## Implementation

FC_TYPED_IR_GUARD_RUN_REUSE gates compile-time matching of adjacent compound two-positive-range/set instructions with identical ordered distinct symbolic slots and target equal to second predicate slot. Existing dataflow must be on. Prepared descriptors share an identity only within the contiguous shape run. Per-execution State is enabled only with reentrant-safe queue epoch support; no global cache, no mutation hooks for optimization, no stored ScoreAccess, no objective or holder preflight reuse. Ordinary preflight remains fresh. Only compoundBranch(false) authorizes carrying the existing integer/presence bitset to the next exact matching descriptor. Before any terminal (including score row creation), fallback, noncompound, exhausted boundary or reentrant yield invalidate the facts. Original source positions, predicate branches and modifier debits retained. Tracer, nonempty source callback and restrictive fork limit retain native fallback. Queued tail descriptors never carry the shared shape. No cross-invocation reuse. Vanilla same-thread read purity assumed. Test-only synchronous mutation and reentrant listeners and a narrowly gated callback harness are independent of the optimization flag.

## Fixed gates

- Five modes with same-feature disabled bytecode, actual exact wrap source shape, all quotas 1..25/32/48/64/full, missing rows/objectives, readonly objective, no entity, extrema, terminal write then another guard, ordinary and opaque boundaries, actual synchronous changes/removals and reentrant queue insertion, trace/fork/callback fixtures and positive reuse/invalidations/fallback counters. Compare exact scores including absent rows and storage state. 
- Two independent publisher diagnostics, exact original generated wrap only, prior accepted IR045 regression independently; same frozen source identity and complete restoration oracle, actual J1:10 and positive reuse only enabled. Cannot enable erb plus erb_generated under current exact namespace guard without broadening scope; use a separate explicit wrap experiment. No whole-event CPU claim.
- Two separate same-JVM A/B workloads, pure (exact 10 wrap commands plus one witness add) and mixed (reset cursor to 7153, exact 10 wrap commands and witness add). Actual persistent armor stand as source, radius12; cursor1 pure, cursor0 after each mixed wrap. Both arms use identical emitted bytecode, direct off and single research toggle; exact count of completed calls from witness. Preflight only diagnostics. 1024 calls per batch, 8..2048 calibrated batches (short exact functions), 750ms target, 500ms minimum, six stable windows and two holdouts, two JVM boots per workload, A/A <=5%, all four paired reductions positive and boot medians >= max(5%,2*worst A/A). No extrapolation to publisher performance; any valid negative or inconclusive outcome retained. No threshold relaxation.
- IR045 native differential regression and inherited structural tests. IR037 contract updated for the new prepare(original,shape) signature without changing its identity checks.

## Results

Pending.