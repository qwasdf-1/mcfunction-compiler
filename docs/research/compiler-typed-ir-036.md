# COMPILER-IR-036 — Effect-legality analysis and opt-in structural backend cost selection

**Status (2026-11-23/24): IMPLEMENTED; 14-JVM NATIVE SEMANTIC GATES ACCEPTED. Cost model UNCALIBRATED; no CPU performance claim or production promotion.** This is compiler architecture work on draft PR #10, not another game-engine optimization. No production default or merge decision is changed. All selections remain under the preexisting opt-in typed compiler, and the new policy itself defaults to **off**.

## Intended compiler pipeline

`Minecraft Brigadier-valid command → TypedScoreIR.Program → TypedIROptimizer.Plan → TypedIREffectAnalysis → IR036CostModel → {original vanilla commands | optimized interpreter | ASM-generated JVM code}`

The existing IR-035 optimizer canonicalizes validated source instructions **one for one** without removing or moving commands. IR-036 evaluates their existing typed effects and selects an execution implementation for the whole typed region. It does **not** infer that nonoverlapping score slots are safe for mutation elimination: modded scoreboard listeners, response feedback, command-quota truncation, trace callbacks and reentrantly enqueued commands may expose every source-command boundary, even between independent scores.

## Conservative effect legality

`TypedIREffectAnalysis` walks the immutable ordered Plan and constructs one immutable boundary record for each consecutive pair of original commands. It retains each instruction's `reads`, `writes`, and `observableBoundary` from the already validated `TypedScoreIR.Effects`. It annotates adjacent read-after-write, write-after-read and write-after-write overlaps, guard/binary counts and dynamic holder references. An `@s` target/guard/source is explicitly treated as an unknown potentially aliasing holder, rather than proving it disjoint from a fake-player score slot.

**Non-negotiable restriction:** `Boundary.reorderPermitted()` and `eliminateCommandPermitted()` are always false, including for disjoint slots. `Analysis` verifies exactly `instructions-1` ordered observed boundaries. This analysis is **not a proof that scoreboard effects can be removed**; it is a machine-readable statement of what future passes must preserve.

No new snapshot caching, direct scoreboard mutation, selector indexing, command merging, function inlining or modded-engine shortcuts are implemented.

## Cost model: structural heuristic, explicitly not calibrated

`IR036CostModel` is pure Java and can be run outside Minecraft. It receives only validated structural features and an **explicit assumed invocation count**. It predicts abstract, *dimensionless work units*, not measured CPU time, throughput, allocated bytes or actual JVM execution cost.

For `n` source commands, `g` score guards, `b` binary commands, `d` dynamic-holder source commands, and `C` assumed invocations, current hard-coded research weights are:

- `common = 4g + 3b + 2d`
- `VANILLA = (12n + common) × C`
- `INTERPRETED = (24 + 3n + 4g) + (7n + common + 3) × C`
- `BYTECODE = (200 + 18n + 14g + 5b) + (3n + common + 3) × C`

The numerals are **hypothetical** and intentionally require later independent calibration before treating the choice as a real-world performance policy. The current purpose is to exercise a three-way backend selector and its legal fallbacks, not to assert those weights describe Minecraft. The cheapest estimated backend is selected, with ties favoring the less intrusive mode. If the user has explicitly enabled **interpreted** typed IR but not bytecode, the model cannot select bytecode. The call-count assumption is limited to 1–1,000,000, with invalid values conservatively interpreted as 1.

The policy is enabled only if the existing typed IR is explicitly enabled for a namespace and `FC_TYPED_IR_COST_POLICY=select`. `FC_TYPED_IR_EXPECTED_CALLS` supplies an optional assumed invocation count (16 if absent). With no policy flag, original backend choices are bit-for-bit unchanged; with an invalid policy name, selection stays off. These are research controls, not production recommendations.

## Execution and fallback behavior

The selector operates *after* immutable IR canonicalization and effect analysis and *before* bytecode emission. For accepted selections:
- **Vanilla:** `MixedFunctionIR.flush` expands a rejected typed region into its **individual original `UnboundEntryAction` objects**, at their exact source indices, marking `COST_MODEL_VANILLA` barriers. A region must **never** be retained as a single synthetic queue entry after a vanilla choice. If no typed or compiled-fork regions survive, the original `PlainTextFunction` is returned unchanged.
- **Interpreted:** existing immutable typed instruction vector and IR-035 opcode Plan execute through `TypedScoreIRRuntime.State.begin/finish` per command.
- **Bytecode:** existing ASM emits direct `ScoreAccess` arithmetic and per-command `State.begin/finish` with original source fallbacks. Bytecode-generation failures still fall back to interpreted typed execution and cannot qualify for direct function scheduling.

Vanilla fallbacks and opaque commands are never admitted into the all-bytecode direct scheduler. Source commands, identity, quota, trace, result feedback, score listeners and reentrant queue boundaries remain in their original order. Selection itself never changes scoreboard values or source datapack content.

Diagnostic counters `ir036_cost_native`, `ir036_cost_interpreted`, `ir036_cost_bytecode`, and `ir036_cost_vanilla_entries` expose compile-time decisions when the existing diagnostics flag is explicitly on.

## Acceptance tests (before native work)

1. `tests/test_typed_ir036.py` validates effect barriers, unknown dynamic holders, opt-in policy, preservation of original actions on vanilla decisions, and both generated backends.
2. `tests/java/dev/functioncompiler/IR036CostModelTest.java` compiles and runs using only Java 25, testing that different assumed call counts can select all three backends, selection cannot exceed authorized bytecode mode, and invalid structural features fail closed.
3. Existing IR-034/035 static contracts and the Java 25/Fabric build must stay green.
4. Bounded real-server acceptance: the existing IR-008 four-mode native oracle and IR-013 six-mode reentrant oracle retain baseline semantics when the new policy is **off**. Additionally, `scripts/ci_typed_ir036.py` compares four new independent Minecraft JVMs with identical mixed-IR fixtures: uncompiled native, and bytecode-enabled typed IR with the cost model selecting one-call, eight-call and 256-call **assumed** execution profiles. It inspects compile-time ledger decisions, final scoreboard state, missing objectives, nested calls and low command-quota observations. Its A/B labels are *not* performance treatments and it does not measure CPU.

## Stop rule and limitations

No speedup claim, no acceptance of the hypothetical work-unit weights as empirical, no production default enable, no automatic repeated CPU performance pilot. The IR-033 failed no-treatment A/A qualification is still binding. A successful native parity result establishes the **correctness of backend routing within test coverage**, not global equivalence for arbitrary modded commands. Afterward, we should strengthen the optimizer's actual transformation opportunities or choose more representative supported command families, rather than add another open-ended performance research tangent.

## Results — accepted native semantic parity (2026-11-23/24)

The bounded [native workflow run #45303709483](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45303709483) completed successfully against real Java 25 / Minecraft 26.3 Fabric. All original per-JVM state, quota comparisons and server logs were archived in [artifact #14880166640](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45303709483/artifacts/14880166640). The new CLI reports `native_semantic_parity=true` and explicitly `causal_performance_claim=false`, `production_promotion=false`.

| Accepted gate | Observed result |
| --- | --- |
| IR-036 Python contracts and Java 25 pure-JDK model | Pass; **19 cost-model assertions** exercised all three backends and invalid inputs |
| Full Minecraft Fabric mod | Java 25 build success |
| IR-036 3-way cost routing plus native control | **4 independent JVMs**, 81 source-state and low-quota cases **per arm**, identical observations |
| IR-008 policy-off regression | **4 independent JVMs**: vanilla, fused, interpreted, ASM; 62 state/quota cases; native parity accepted |
| IR-013 policy-off reentrant oracle | **6 independent JVMs**, 85 cases per mode; guarded interpreted, guarded ASM and guarded direct scheduler all had **zero differences** from vanilla |
| IR-013 unsafe negative controls | Both unsafe bytecode and direct modes diverged in **46 cases** as expected |

The **IR-036 cost-arm results** establish actual branch decisions, not just simulated estimates:

| Run label | Original Minecraft `ir016_call_chain` layout (8 original commands) | Selected regions across all test functions |
| --- | --- | --- |
| `original` | Uncompiled vanilla reference | N/A |
| `cost_1` — assume 1 invocation | **8 vanilla/opaque entries, 0 typed regions**, `V1:1,V2:1,V3:1,V4:1,V5:1,V6:1,V7:1,V8:1` | 14 vanilla-region decisions, 2 interpreted, 0 bytecode |
| `cost_8` — assume 8 invocations | 3 interpreted typed regions and 2 opaque barriers, `I1:2,V3:1,I4:2,V6:1,I7:2` | 0 vanilla, 14 interpreted, 2 bytecode |
| `cost_256` — assume 256 invocations | 3 bytecode regions and 2 opaque barriers, `J1:2,V3:1,J4:2,V6:1,J7:2` | 0 vanilla, 0 interpreted, 16 bytecode |

Selection is **per region, not once per whole function**: a long region may legitimately select a different backend from a short region under the same assumed invocation count. The source positions of the two opaque commands in `ir016_call_chain` never moved. In the low-cost branch, the other six source commands reverted to individual original queue entries rather than one batched synthetic entry. Exactly the same 81 Minecraft state/quota observations were obtained in all four control/routing JVMs.

**Acceptance scope:** implementation and native semantic parity for the tested scoreboard, function calls, missing objectives, command-quota truncation, callback and boundary scenarios. This verifies **the mechanism** of safe, opt-in backend routing. It does **not** validate the heuristic weight magnitudes or predict which backend improves real-world CPU time. The failed no-treatment IR-033 performance-stability gate remains binding.

**Disposition:** IR-036 complete. Cost selection remains disabled by default, the native research workflow is restored to manual-only, PR #10 remains draft/unmerged, and production defaults are unchanged. Further performance promotion requires a separately calibrated and repeatable measurement protocol, not another post-hoc reading of these structural scores.
