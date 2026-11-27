# IR-042 — Representative execution, attribution and compilation profitability

**Status: completed — publisher diagnostic parity accepted; publisher CPU qualification blocked; controlled attribution passed three contrasts (2026-11-24).** Research branch `work/compiler-coverage`, draft PR #10. No production default or heuristic promotion.

## Prior evidence

IR041 mixed synthetic workload passed the preregistered cumulative CPU gate (59.42% median reduction, max A/A 3.54%). Its incremental dataflow result did not pass (0.70%). Compound workload showed 81.54% cumulative and 21.44% incremental reductions but failed final placebo (8.66%). See [IR041](compiler-ir041-steady-state.md); preserve the full original evidence and thresholds.

## Publisher execution gate

Use the exact original SHA-pinned Blastback 26.3 publisher ZIP and the previously accepted IR027 solid-stone 17-cube scene. Vein Miner remains a subsequent candidate, not a second speculative large event campaign. Native census uses the existing original entry/callback and native CallFunction task boundaries. Explicit research-only Blastback scope admits selected erb and erb_generated IDs; capped at 900 statically counted non-macro source lines and 96 callee IDs. Start with reset/wrap, job_tick, projectile_probe_step, player_state and inherited capture/dispatch targets. Source-index and source-text identity required, no overflow, exact same-work completion oracle. Macro bodies are excluded from source-index sampling; native call tasks are not child completions. Rank uncompiled opportunities by observed source entries (isolated typed, dispatch/macro, selector/context, storage/data and other barriers). Not whole-pack dynamic coverage or CPU attribution.

Choose the function with greatest observed candidate region entries in that sampled scope, tie by ID. This is based on actual native entry frequencies joined to conservative source shapes, not the static number of lines. If no candidate reaches, stop rather than select arbitrarily. In a separate diagnostic JVM enable the accepted typed bytecode flags only for that exact function ID, not the entire enormous generated namespace. Demand native full-state parity, actual typed ledger spans, positive executed regions/steps, and record fallback, proof and read-reuse counters. Join the native sampled source indices to the actual J/I spans to count eligible visits in the native event, not claim every visit executed optimized in the compiled event. Record diagnostic compile cost separately. Other compiler experiments (fork, direct, legacy callback rewriting, macro specialization) disabled.

## Actual publisher CPU gate

Do not toggle a retained function to native in the same JVM: the typed adapter may mutate parsed Brigadier callbacks, so a retained original action is not generally a pristine uncompiled baseline. Use fresh independent publisher servers instead. This is a bounded pilot, not a large repeated benchmark campaign. Two native control boots before any treatment; each boot must complete two full warmup events from restored clean starting state, with CPU/tick spread <=5%, then a third measured event. Each event observes >=1000 original capture markers, complete restoration of the full test volume and all witness blocks, original job/marker cleanup and normalized state parity. Use accepted natural 600-publisher-tick window and existing bounded tick polling; normalize running Server-thread CPU by observed ticks. External telemetry and wall time archived, no diagnostic probes or census in timed arms. If initial native A/A exceeds 5% or warmup fails, skip treatment. Otherwise ABBA across four fresh JVMs; final native/native and compiled/compiled placebo contrasts <=5%, both paired reductions >=max(5%, 2*max A/A). Workload includes idle and event scheduling; capture witness is a sampled lower bound, not exact total capture cardinality. Independent JVMs and repeat-event residual world history limit causal interpretation. No general datapack speedup.

## Same-JVM controlled attribution

One unchanged 64-command compound workload, five arms: native namespace, interpreted IR039-style, bytecode IR039-style, bytecode+IR040 dataflow, bytecode+dataflow+direct scheduler. Separate exact interpreter twin uses research-only backend override; IR039-style twins disable dataflow only. Direct uses the identical flow function and existing runtime switch. Diagnostic preflight must verify I/J layouts, exact work, proof/read reuse only in flow/direct, and direct executions only in direct. In all timed boots diagnostics and compile clocks off; simulation frozen, tiered JVM compilation left normal.

Calibrate a common work size in each of two boots using 1024 calls per batch, doubling batches 8..256 until the fastest observed arm reaches 750ms CPU; lock the size before treatment. Minimum eligible window 500ms running Server-thread CPU. Six consecutive stable warmup windows (5% max-min/median) for every arm, at most 12 rounds; two independent holdout rounds must maintain the same stability. Five initial same-arm A/A blocks, all <=5%. Two counterbalanced ABBA/BAAB cycles interleave all same-arm controls and five comparisons: native/interpreter, interpreter/bytecode, bytecode/dataflow, dataflow/direct, native/dataflow. Every treatment contrast must be positive in all four paired blocks, both boot medians >=max(5%, twice worst absolute A/A), every eligible sample >=500ms, all controls <=5%, both boots qualified. Retain every sample, no rerun merely for failed stability. No inference that this synthetic result generalizes to gameplay.

## Profitability

Diagnostic-only current-thread CPU and wall time separately capture post-parse ScoreAddPrototype adapter validation and TypedScoreIR.compile. For an accepted cumulative native-vs-interpreter or native-vs-flow contrast, estimate saved CPU per call from paired per-line costs times 64, and illustrative calls to amortize measured post-parse compiler CPU (ceil compile CPU / per-call CPU saving). Single cold diagnostic observation is not a calibrated cost model; excludes parsing, resource loading, class/JIT work on other threads and retained per-function memory. No break-even estimate for unqualified comparisons. Whole JVM telemetry is descriptive; no reliable retained per-function memory measurement. IR036 weights remain unchanged until replicated compile/load and execution data justify a profile-guided policy.

## Results

### Native execution and publisher gate

[Run 45516230461](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45516230461) completed both jobs; [final implementation CI](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45516280055) passed. [Publisher raw evidence](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45516230461/artifacts/14978057388).

17 sampled non-macro functions, 257,697 native source entries, 197,604 candidate region entries (76.68% of sampled entries, NOT whole pack). Ranking: restore/wrap 172,450 entries (17,245 calls), capture/store 17,307, restore/job_tick 7,024, restore/reset 489 (three calls). The selected erb_generated:restore/wrap accounts for 87.27% of sampled region-candidate visits. Native/compiled diagnostic complete restoration parity passed: 600 ticks, 17 y slices, all witnesses, original marker cleanup. Actual J1:10 layout (10/10 typed), 17,245 executed regions, two executed terminal steps, zero reported fallback steps, compound native fallbacks, dataflow proofs or operand reuse. Native census had exactly two ordinary terminal callbacks among 172,450 wrap entries: 10 independent two-stage guards, each tests a radius and cursor boundary; overwhelmingly false guards. This is not a redundant-predicate workload; no evidence of an incremental IR040 gain in this publisher function.

Both native control boots failed within-boot warmup (A0 18.840 -> 16.873 ms/tick, spread 11.01%; A1 20.100 -> 18.190 ms/tick, spread 9.98%). No measured native A/A block or timed treatment was admitted. No publisher CPU speedup claim. Sampled capture peaks differ across events; exact capture cardinality equivalence is not proved by the final state oracle. No throttling in these four windows. Initial A0 peak 1,530 vs 5,769 on later sampled events is not exact capture count.

Diagnostic adapter/typed compiler thread CPU 11.392/21.944 ms, combined 33.336 ms; wall 11.442/164.808 ms. No publisher break-even estimate without qualified publisher CPU saving.

### Controlled attribution — accepted qualified contrasts

[Attribution raw evidence](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45516230461/artifacts/14978186570). All five actual path and exact-work preflight checks passed. Both boots calibrated at 128 batches x 1024 calls x 64 lines = 8,388,608 source visits/window; each qualified after six warmup rounds and two holdout rounds. 25 blocks per boot (five initial A/A plus 20 measurement blocks), 200 block windows overall. Minimum block-window CPU 779.281 ms. Maximum absolute A/A 0.73551%, below 5%. Both boot status complete.

| Comparison | Four paired reductions (%) | Median | Gate |
| --- | --- | ---: | --- |
| Native / interpreter | 75.51, 75.47, 75.57, 75.59 | 75.54% | Pass |
| Interpreter / bytecode | 2.75, 3.57, -4.79, -4.87 | -1.02% | No gain established |
| Bytecode / dataflow | 20.53, 21.09, 31.75, 31.34 | 26.21% | Pass |
| Dataflow / direct | 0.61, 1.12, 0.14, 0.53 | 0.57% | No gain established |
| Native / flow | 81.25, 81.22, 82.33, 82.47 | 81.79% | Pass |

Only the tested repeated compound fixture and measured Server-thread CPU qualify. Native/interpreter saving 25.587 us/call, cold post-parse compiler CPU 9.312 ms, illustrative break-even 364 calls; native/flow 27.664 us/call, 34.970 ms, 1,265 calls. Adapter/typed phase CPU for IR039 bytecode 0.346/21.811 ms. Cold phase costs include load-time/JIT variation; not calibrated policy or retained memory estimates. Bytecode does not establish an independent advantage; prefer wider typed coverage over further speculative ASM tuning. No general performance or production promotion.

### IR043 opportunity decision

Native reached unsupported entries: execute_other 23,710; function_dispatch 21,272; data_or_store 6,547; tag 5,777; entity_context_or_selector 1,688; isolated_typed_candidate 1,091. Categories are exclusive priority buckets, not an exhaustive typed classification. Callback cardinality differs dramatically: restore/job_tick has 653,227 ordinary callbacks, including 647,279 at the already investigated selector+score-guard+write site (IR025); reached-entry ranking alone understates fork work. Prior IR028 whole-event CPU comparison of that compiled fork was inconclusive. Prefer a reusable typed conditional static-function-dispatch capability next, preserving the original queued child-call and callback/return/quota semantics; classify actual eligible source sites before implementation. Investigate cheap false-guard paths and shared read/decision optimization for wrap only with exact effects; don't infer whole-event improvement from native entry counts. The publisher event still needs a better repeatable workload and warmup protocol; do not immediately rerun unchanged failed gate. No more broad benchmarking-only milestone before IR043 implementation.
