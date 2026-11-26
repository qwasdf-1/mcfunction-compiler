# IR-047 — Effect-bounded objective and holder preflight reuse

**Status: accepted — all five gates completed successfully (2026-11-26).** Research-only, default off. Baseline is accepted IR046 at checkpoint/ir046-accepted (c03903e8d285885116a622819a5a333705033611). No new lowering coverage or global caches.

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

## Results — accepted

[Research matrix 45908911065](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908911065), tested b8ce4d304852574f1e90ee6368e22a6d982698a3; core implementation 13a1f81f4a05dc3bc33211612963f4ba68fe018c. All five jobs passed on first attempt. Standard CI [45908756880](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908756880), [45908919183](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908919183) and [45908937153](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908937153) passed. Workflow restored to manual-only in 5699d5e.

### Native differential

[Raw artifact 15158667898](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908911065/artifacts/15158667898). Independently opened archive, verified CRC and compared all five actual case maps: 670 observations per mode, 3350 total, exact native equality. Full-quota deletion leaves objective absent and cursor=0; two fresh missing-objective fallbacks in each compiled mode. Recreation leaves new objective present, radius=6, cursor=8. Ordered-slot reversal leaves entity cursor=123, fake guard=10. Each enabled mode 1871 compatible boundaries, 3333 unique objective lookups avoided, 3742 holder-slot resolutions avoided, 1871 writable checks avoided. IR047-off compiled control zero IR047 counters; IR046 counts equal across all compiled arms (1871 boundaries, 1669 present and 315 absent reads reused, 653 invalidations, one each trace/fork/callback fallback). Each compiled arm 22 reentrant yields, 331 queued steps, 378 native compound fallbacks. Direct arm actually executed 565 direct calls. State parity not exhaustive trace event parity or arbitrary mod compatibility.

### Controlled incremental CPU

[Pure artifact 15158728144](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908911065/artifacts/15158728144); [mixed artifact 15158668185](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908911065/artifacts/15158668185). Both exact workload twins use IR046 in both arms, same bytecode, diagnostic-off timed runs. Each workload two complete independently booted JVMs, 2048 batches per window, 1024 calls per batch. Reopened both raw archives and verified 64 timed block windows per workload, all x=2097152, radius=12, cursor=1 pure/0 mixed; minimum CPU 896.534 ms pure, 892.980 ms mixed. Both qualified.

| Metric | Pure | Mixed |
|---|---:|---:|
| Paired reduction 1 | 33.9489% | 27.2533% |
| Paired reduction 2 | 33.9825% | 26.1531% |
| Paired reduction 3 | 34.7805% | 29.5171% |
| Paired reduction 4 | 34.5565% | 28.6731% |
| Boot 1 median | 33.9657% | 26.7032% |
| Boot 2 median | 34.6685% | 29.0951% |
| Overall median | 34.2695% | 27.9632% |
| Maximum absolute A/A | 1.1884% | 1.7419% |

Diagnostic preflight exact equal IR046 counters and work; pure 1152 boundaries/2304 objectives/2304 holders/1152 criteria skipped and mixed 1024/2048/2048/1024, zero IR047 in control. No additive combination with earlier independent CPU experiments as a measured cumulative effect.

### Original publisher and regression

[Publisher artifact 15158938187](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908911065/artifacts/15158938187): original frozen census SHA256 5977367281d9c0958f5dbc3cabb7d22c65902373f71cf1871893a68d14c820a9. Both arms J1:10, complete restoration equal to native and each other, 17245 invocations, two terminal steps, zero fallbacks, IR046 155203 boundaries/172446 score reads avoided in both. IR047 enabled 155203 boundaries/310406 unique objective lookups/310406 holder-slot resolutions/155203 writable checks avoided, exactly predicted; disabled zero. Counted operations differ in cost. No whole-event CPU claim.

[IR046 regression artifact 15159138099](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45908911065/artifacts/15159138099): 583 exact observations per mode, 2915 total, passed with IR047 off.

**Disposition:** IR047 accepted for the narrow tested shape. No production defaults changed, PR #10 remains draft/unmerged. Next recommended work is Integration-001, independent of new coverage: inventory accepted runtime dependencies, audit rejected and diagnostic paths, prepare focused supported compiler integration, test installed-but-disabled overhead and native parity against main, and regress opt-in behavior against the accepted checkpoint. Retain historical evidence and do not merge research wholesale. Context-transforming dispatch and singleton specialization remain subsequent research candidates.
