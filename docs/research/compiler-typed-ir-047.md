# IR-047 — Effect-bounded objective and holder preflight reuse

**Status: implementation and fixed verification gates staged; acceptance pending.** Research-only, default off. Baseline is accepted IR046 at checkpoint/ir046-accepted (c03903e8d285885116a622819a5a333705033611). No new lowering coverage or global caches.

## Plan and invariants

IR046 already identifies adjacent homogeneous two-positive-range/set commands with exact ordered distinct symbolic slots and second predicate equal to terminal target. The source is invariant within a State, literal fake holders use name-only parsed holders (# names), @s is the current entity, and objective index order is deterministic from the same ordered slot pair. A successful preflight resolves every objective and holder and proves the target criterion writable. A pure failed guard authorizes the next matching descriptor; no terminal access, feedback, callback, or native fallback can intervene. Existing quota debits, empty suffix, queue-epoch checks and all preflight rejection conditions remain.

IR047 adds FC_TYPED_IR_GUARD_PREFLIGHT_REUSE, effective only with IR046 runtime reuse and reentrant-safe epoch support. Reuse existing per-State objective and holder arrays and successful writable-criterion proof only on the exact matching priorFailedRun identity. First command, changed slot order/shape, invalidation, queued tail, distinct region/source and failed preflight always resolve afresh. Never retain writable ScoreAccess, never reuse integer values for a terminal, never resolve at compile time or across calls. Missing objective/holder and read-only still use untouched native fallback. State clears authorization before any terminal access, which itself can trigger a listener. References remain ordinary scratch for the current terminal, not authorized for later use. Native trace, restrictive fork and nonempty callback guards remain ahead of reuse. Same vanilla-thread/read-purity assumption as IR046; arbitrary external mod mutation during pure reads is not supported. Diagnostic counters distinguish unique objective map lookups, holder-slot resolutions (including trivial literal reads), and read-only checks skipped.

## Fixed gates

1. Five real native modes, 23 scenarios × 29 quota cases + 3 special checks = 670 snapshots/arm. Existing IR046 native cases plus synchronous objective removal on terminal, removal/recreation with same name via native commands, and changed ordered slot/holder/objective layout inside a region. Exact native snapshots, positive missing-objective fallback after terminal listener and full-quota witnesses; positive trace/fork/callback/reentrant paths. All compiled modes retain IR046; only treatment enables IR047. IR047 counters must match IR046 compatible boundaries, two holder slots and one criteria check per boundary, one or two unique objective lookups. Disabled control zero IR047.
2. Same-JVM A/B exact IR046 pure and mixed workloads, IR046 enabled in both, same source/bytecode/actual entity, only IR047 toggle differs; same 128-call diagnostic preflight, exact score states and region/terminal counts. Pure predicts 1152 boundaries/2304 objective and holder resolutions/1152 criteria checks avoided; mixed 1024/2048/1024. Diagnostics off for timing, same qualified 750ms calibration/500ms minimum, six stable warmup windows/two holdouts, two boots, all four positive reductions and each boot median >= max(5%,2*max absolute A/A), A/A <=5%. No threshold changes after seeing results. Negative/inconclusive measurements retained.
3. Pinned original Blastback generated wrap scope, same frozen census and full restoration. IR046 both arms 17245 regions, two terminals, 155203 reuse boundaries and 172446 reads avoided, IR047 enabled predicts 310406 objective and holder-slot resolutions and 155203 checks avoided; disabled zero. No event CPU claim.
4. IR046 native regression with IR047 off, inherited structural tests, Java25 ordinary CI. No production defaults, no merge or release.

## Integration disposition

PR #10 is technically clean but very large (988 commits, 362 files, +43936/-123 at IR046). Preserve checkpoint; keep research branch and history. Before integrating into main, inventory accepted vs rejected/diagnostic-only paths, remove obsolete research hooks from the integration runtime or establish disabled overhead, retain tests and evidence provenance, curate supported scope and flags, build and run default-off baseline parity and disabled-overhead A/A plus opt-in differential/performance regression against the accepted checkpoint. Create focused integration PR rather than treating default-off as proof of zero overhead. No default enable or merge authorized yet.

## Results

Pending.
