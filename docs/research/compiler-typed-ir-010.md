# COMPILER-IR-010 — Version-validated source-score reuse

**Status: IMPLEMENTED as an explicit research-only opt-in. Native semantic gate ACCEPTED; same-JVM CPU experiment does not support promotion (2026-11-19).**

**Branch:** `work/compiler-coverage`, existing unmerged draft [PR #10](https://github.com/qwasdf-1/mcfunction-compiler/pull/10). **Previous compiler stages:** [IR-008](compiler-typed-ir-008.md) and [IR-009](compiler-typed-ir-009.md).

## Motivation: safe reuse across observable command boundaries

IR-009 adds an immutable `Effects(reads, writes, observableBoundary)` description to each typed instruction but intentionally does not reuse scoreboard values across commands. Commands have observable write, quota, feedback and trace boundaries; an external scoreboard listener can change an unrelated score in the middle of a compiled region. Therefore, simple local SSA forwarding based solely on *syntactic* writes from the IR would be unsound.

Minecraft 26.3's `ScoreAccess.get()` is a simple getter of the live `Score` value, whereas `ScoreAccess.set()` notifies `Scoreboard.onScoreChanged` when a value changes or a new row is synchronized. Score removals and objective removals use separate `Scoreboard` notifications, as inspected in the exact 26.3 reference:
[ScoreAccess.java](https://mc-packet-reference.netlify.app/26.x/source/net/minecraft/world/scores/scoreaccess/) ·
[Scoreboard.java](https://mc-packet-reference.netlify.app/26.x/source/net/minecraft/world/scores/scoreboard/) ·
[ServerScoreboard.java](https://mc-packet-reference.netlify.app/26.x/source/net/minecraft/server/serverscoreboard/).

**Implemented hypothesis:** reuse only the *pure source-score integer* read across typed scoreboard binary instructions in **one compiled region invocation**, if the specific scoreboard slot has not been changed or removed since the read and the exact Objective instance remains the same. Do not cache `ScoreAccess` handles; do not coalesce writes; do not remove observable command boundaries.

## Implementation

- `ScoreValueRevisionAccess` is a minimal watched-slot version oracle, with a key formed from literal fake-holder name and objective name.
- `ScoreValueRevisionMixin` hooks the **ServerScoreboard** `onScoreChanged`, `onPlayerScoreRemoved`, `onPlayerRemoved` and `onObjectiveRemoved` notifications. Only slots actually watched by the cache have revision entries; updates to unrelated score slots do not invalidate a cached source. A removal increments the watched revision; an objective's object identity is checked separately.
- `TypedScoreIRRuntime.State.sourceOperand` stores a locally scoped snapshot containing integer value, exact `Objective` identity and revision; on the next binary read it checks all three and either returns the snapshot or reloads via the newly acquired `ScoreAccess`. Every `begin` still runs ordinary `getOrCreatePlayerScore` to preserve row creation and callback semantics. The local cache is discarded at the end of the region invocation.
- The interpreter and ASM binary-lowering path use the same guarded source read while the mode is enabled. The compiled ASM still performs real `ScoreAccess.add/set` and JVM arithmetic, not Brigadier interpretation.
- The research switch is `FC_TYPED_IR_SCORE_CACHE=true`, *in addition to* the prior explicit `FC_WRAPPER_PROBE` / `FC_TYPED_IR_MODE` / `FC_TYPED_IR_NAMESPACE` flags. `FC_TYPED_IR_SCORE_CACHE_TOGGLE=true` registers a test-only `fc_ir010_cache on|off` command that toggles guarded source reads **without regenerating bytecode**—allowing fairer same-JVM CPU comparisons. Neither flag is set by default.
- Diagnostic counters `cache_hits`, `cache_misses`, `cache_invalidations` are enabled only with `FC_TYPED_IR_DIAGNOSTICS=true`.
- `FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER=true` is a *separate test-only flag*, not production functionality: it registers deterministic synchronous scoreboard callback effects to change a watched source when another score changes, and to reset the watched row. Native and compiled arms execute the same callback behavior.

**Effect-safety limitation:** This is a guarded speculative *read*, not proof of global referential transparency. A Fabric mod that mutates private raw score storage behind the normal Scoreboard/ScoreAccess notifications, changes the scoreboard callback implementation without invoking the hooked method, or introduces off-thread unsynchronized mutations may invalidate this model. Full cross-mod compatibility was not established. This code remains research-only, and the global Mixin is still installed on the research branch (although its body exits when neither research flag is enabled); a production-quality integration would need explicit lifecycle/compatibility design and a zero-default-overhead check.

## Accepted native semantic evidence

[Actual Minecraft 26.3 Fabric / Java 25 CI run #44653996634](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44653996634) · [Raw semantic and CPU artifacts](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44653996634/artifacts/REPLACE_WITH_VERIFIED_ARTIFACT_ID)

Each of **four independent native JVMs** executed **51 observed cases** with matching full score/row-presence snapshots: native, direct ASM with cache off, typed IR interpreted with cache on, and direct ASM with cache on. Cases cover repeated source reads, direct source writes between reads, self/alias updates, nested-function barriers, true synchronous scoreboard listener mutations, row removals, and exact partial effects at quotas 1,2,3,4,5,6,7,8,10,16,32. The low-quota observation distinguishes *absent score* from *present score with integer zero*.

| Semantic activation diagnostic | Native | ASM no cache | IR interpreter cached | ASM cached |
| --- | --- | ---: | ---: | ---: |
| Compiled IR regions | no IR | 7 | 7 | 7 |
| Real emitted bytecode regions | no IR | 7 | 0 | 7 |
| Typed instructions executed | no IR | 294 | 294 | 294 |
| Binary operations executed | no IR | 151 | 151 | 151 |
| Source-value cache hits | no IR | 0 | **90** | **90** |
| Source-value cache misses | no IR | 0 | **61** | **61** |
| Source-value invalidations observed at read | no IR | 0 | **19** | **19** |

No original-command fallbacks were needed in these cases; the IR-009 native fallback suite remains separately accepted and unchanged. This run does **not** exhaustively verify all debugger tracing, return consumers, modded mutation paths, world reload or custom scoreboard subclasses.

**Development harness corrections before acceptance:** low quota + reset can leave a row truly absent; earlier harness assumed all scores were readable. The corrected snapshot uses an explicit null/absent observation. A performance window's unused `#b` was initially absent, while the semantic fixture created `#b=0`; the accepted benchmark initializes `#b` once *outside* CPU windows. Neither failed attempt was used for performance conclusions.

## Same-JVM counterbalanced CPU check: no demonstrated gain

The CPU arm uses **two fresh actual Minecraft JVMs** with the same compiled 64-command function and **the same generated JVM bytecode** for both cache-on and cache-off conditions. A research-only runtime switch toggles only the guarded source-value reuse. Each function invocation sets the source to 7, sets the destination to zero, then performs **62 scoreboard operations reading that same source**. Each CPU window contains 120 function invocations, i.e. 7,680 original scoreboard commands and exact expected output `#a=434`.

- Six balanced ABBA/BAAB cache-on-versus-off four-window blocks per JVM, **12 blocks** total;
- Three off-versus-off A/A four-window blocks per JVM, **six controls** total;
- Correct final scoreboard state in every window, no diagnostics counted inside the CPU windows;
- Signed cache-on-versus-off median CPU fraction **+5.053%** (positive means cache uses *more* Server-thread CPU). Per-JVM medians: **+25.971%** and **−5.769%**;
- Individual cache-on fractions span **−27.452% to +61.010%**; same-path A/A median **+3.384%**, with range **−13.079% to +17.061%**.

The effect is **noisy, crosses zero, and even the two JVMs disagree in direction**. There is no established overall acceleration, no independent-server confidence bound establishing the 15% promotion gate, and no representative real-datapack speedup. A very cheap `ScoreAccess.get()` costs little to begin with; a key allocation/lookup, watched revision check and event-hook overhead may outweigh the read saved. This is a targeted compiler hypothesis tested and not validated as profitable. Not every safe optimization is a useful optimization.

**Decision:** STOP further micro-optimization of this per-score read cache. Keep it opt-in on this draft branch as an explicit test of the IR effects and observer model, but do not enable or merge it as a production optimization. Prefer future optimizer work that removes substantial observable overhead *without* globally instrumenting every scoreboard write, and require a representative native workload and the independent-server promotion gate before default changes.

## Files and reproducibility

Core: `ScoreValueRevisionAccess.java`, `mixin/ScoreValueRevisionMixin.java`, `TypedScoreIR.java`, `TypedScoreIRRuntime.java`, `TypedScoreIRBytecode.java`, `ProbeCommands.java`, and `function_compiler.mixins.json`. Tests: `scripts/ci_typed_ir010.py` and `tests/test_typed_ir010.py`. Workflow: `.github/workflows/research-typed-ir010.yml`. Original commands are generated into the disposable test datapack during the CI run; no external datapack archive is modified.
