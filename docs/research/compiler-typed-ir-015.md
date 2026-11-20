# COMPILER-IR-015 — Whole-function coverage against original real datapacks

**Status:** SHA-pinned original source coverage **accepted** and bounded real Vein Miner 26.3 gameplay **semantic parity + emitted JVM activation accepted** (2026-11-20). A typed-only parser preflight correctness defect was discovered and corrected before the accepted native run. No performance or production-promotion claim. Same existing `work/compiler-coverage` research branch / draft PR #10.

## Question and approach

The IR-008–014 program proved direct JVM scoreboard lowering, a narrow whole-function resumable scheduler, and guarded reentrant queue behavior. It did *not* establish that a material portion of an ordinary real datapack can enter the direct function compiler. Before another focused timing experiment, measure the **actual command-language coverage and function admission** on unmodified publisher datapacks.

Two independent dimensions must not be conflated:

1. **Direct typed instructions and 2–64-command regions:** A source command matches the documented literal scoreboard mutation, literal-holder `=, +=, -=, *=` operation, or exact single-integer-score guard with direct scoreboard mutation. Actual Brigadier validation and parsed command wrapping still determine runtime acceptance. Singletons are not compiled regions.
2. **IR-012 whole-function scheduler admission:** Every original source instruction must be supported, the function size must be 2–4096, every emitted chunk must compile (no lone 65th/129th etc.), and no ordinary vanilla barrier may remain. Admission is gated further by call-site callbacks, source context, tracing, return and quota checks. A *static source candidate* is not a runtime direct function call.

A source-only screen is **not** a native parser-acceptance census, does not instantiate macros, and does not measure execution hotness or CPU. The existing recursive tag/call/schedule reachability is an overinclusive approximation; dynamic datapack entry through external `/function` or player commands can be outside that graph. We report source-level upper candidates for the identified scope, not absolute dynamic coverage.

## Inputs and provenance

- **Vein Miner 5.3.0+26.3**: publisher Modrinth version `5jzz5SkG`; SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`; 76 functions.
- **Blastback Hotfix 3 / 26.3**: publisher Modrinth version `dMtA8r0n`; SHA-256 `8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90`; 21,318 functions.
- Every download is verified against its existing independent publisher pin *before* audit. No source is modified or packaged into the repo.

**Accepted [source coverage run #44771855459](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44771855459)** · [Full per-function, per-shape reports (verified artifact #14646868044)](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44771855459/artifacts/14646868044). Source has one winner run after corrections to the audit reporter; failed reporting-only attempts are not accepted evidence.

The screen's `scripts/ci_typed_ir015_coverage.py` mirrors the *strict textual* gates in `ScoreAddCommand.toMutation`, `ScoreOperationCommand.toTypedIR`, and `ScoreConditionCommand.toTypedIR`, then mirrors `TypedScoreIR.flush` segmentation. It uses the preexisting `run_specialization_inventory.Pack` reachability parser, not a new unverified parser of arbitrary Minecraft syntax. Unit tests verify supported and rejected shapes, segment boundaries at 64/65/66 and 4096/4097, and source pins.

## Findings: actual source-shape headroom

| Source-only measure | Vein Miner | Blastback |
| --- | ---: | ---: |
| Total original functions | 76 | 21,318 |
| Non-comment command lines | 768 | 269,141 |
| Exact supported IR-shaped source lines | **69** | **537** |
| Lines in 2–64-command potential typed regions | **31** | **140** |
| Potential compiled regions (static) | 6 | 26 |
| Potential complete typed functions | **2** | **1** |
| Complete typed functions in known tick/scheduled scope | **0** | **0** |
| All tick/scheduled source lines | 532 | 248,609 |
| Region candidate lines within that recurring scope | **5** | **35** |

**Important:** These numbers are *not* actual accepted Java bytecode or executed commands; the real parser may accept fewer, while macros instantiated at runtime may expose additional shapes beyond their parameterized source text. A static candidate is not necessarily valuable when it runs.

The 2 Vein Miner whole-source candidates are `vm:lifecycle/install` (11 lines) and `vm:lifecycle/migrate_v5` (5 lines), both outside the known tick/scheduled scope. Blastback's sole whole-source candidate is `erb:migrate/copy_sources` (32 lines), likewise outside that scope.

The few more relevant potential regions are `vm:detection/evaluate_target` (one 3-instruction source-shaped region) and `vm:operation/mine_block` (one 2-instruction region). Blastback candidates include `erb:restore/job_tick` (5- and 2-instruction potential regions), `erb:source/projectile_probe_step` (three 2-command regions), and `erb:pump/group` (3- and 2-command regions).

**Immediate conclusion:** A JVM scheduling micro-optimization on already fully typed functions has no identifiable recurring-function admission in either of these real source graphs. The compiler needs *language and program coverage*, not another small per-region savings experiment, before it can plausibly accelerate these packs.

## What currently breaks compilation

**Vein Miner:** The screen classifies 247 `execute ... run scoreboard` lines not covered by the exact IR guard, 174 other scoreboard lines, 119 other execute forms, and 70 `execute ... run function` lines. Examples include:

- `execute if score #budget vmr.config matches 1..64 run scoreboard players set #valid vmr.runtime 1` — range guard rather than exact `matches N`;
- `execute if block ~ ~ ~ #vm:family/oak run scoreboard players set #family vmr.runtime 1` — block-state/world predicate and dynamic relative position;
- `scoreboard players operation #owner vmr.runtime = @s vmr.owner` — source selector with context-dependent binding;
- `execute positioned ... run function ...` and `function ... with entity @s data` — modified call contexts and macro argument semantics, not currently direct typed subprogram calls.

**Blastback:** Most lexical barriers are `execute ... run function` (143,052 source lines, chiefly generated dispatch), other `execute` forms (72,479), and `execute ... run scoreboard` outside the accepted literal-guard shape (50,566). Examples include `execute if score @s erb.settings matches 1.. run function erb:player/menu`, range-guarded `scoreboard players operation`, and score writes to `@s`. **The enormous counts reflect generated source size**, not proven hot command counts. Earlier Blastback native full-restoration parity remains unqualified, so a CPU comparison on those generated functions would be premature.

Some apparently simple features are actually semantic boundaries: `@s` requires execution-source resolution, `execute positioned` changes coordinates, `execute ... run function` may need separate child frame/result/return processing, and a range or block predicate may have observable failure and quota behavior. Broadening the regex alone is not a valid compiler extension.


## Native player-event evidence — accepted after compiler admission fix

[Accepted two-JVM real gameplay study #44773783498](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44773783498) · [Complete event results and log artifact #14647289852](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44773783498/artifacts/14647289852).

The test ran the unchanged SHA-pinned Vein Miner 5.3.0 publisher datapack and its existing real player-bot mining event, with an original 6×6×6 coal-ore block group (215 additional work units after the source). Two independent Minecraft 26.3/Java 25 Fabric server JVMs used identical source and event setup:

1. **Wrapper-only baseline:** no typed IR, no old ScoreAdd/fusion/bytecode prototypes enabled. Completed 215/215 affected blocks and exact work-state checks.
2. **Typed JVM ASM:** explicit namespace `vm`, `FC_TYPED_IR_REENTRANT_SAFE=true`, diagnostics enabled outside the event, IR-010 cache and IR-011 singleton feedback disabled, IR-012 direct scheduler disabled. Completed the same **215** affected blocks, **1,952** queue-head increments, source-mine count 1, zero remaining ores, zero operation/target markers, and inactive run state.

All nine final event state fields exactly matched, including queue work and cleanup. In the real player event (after setup and before post-event RCON queries), the compiler reported:

| Typed IR runtime evidence | Value |
| --- | ---: |
| Compiled regions / generated bytecode regions at load | **6 / 6** |
| Bytecode region executions during event | **242** |
| Actual directly lowered typed instruction executions | **511** |
| Binary scoreboard operation executions | **54** |
| Conditional mutation executions | **0** |
| Original-command fallbacks within typed regions | **0** |
| Reentrant yields / recovery steps | **0 / 0** |
| IR-012 whole-function direct scheduler | **Off** |

These counters reconcile the initially misleading intuition from source counts: five recurring-path source-shaped region lines may run repeatedly. The observation **establishes runtime activation**, but it is still a small fraction of the real datapack command language. A reported 511 typed steps must NOT be divided by 215 blocks or 1,952 queue actions and called a CPU savings percentage; neither quantity is a directly comparable denominator for overall command work.

**No performance experiment was performed.** The two independent JVMs were not counterbalanced as a speed study; diagnostic metrics were on; neither timing nor CPU improvement, statistically significant effect, or general compiler speedup is established.

### Newly discovered correctness bug and bounded fix

The initial [invalid development run #44772603013](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44772603013) completed the wrapper-only 215-block event, but typed-IR Minecraft crashed before its player connected. The original server failure artifact showed repeated `ContextModifierCommand.runUntimed` → `ContextChain.executeAll` recursion ending in `StackOverflowError`.

**Cause:** `ProbeFunctionWrapper` asked the older `ScoreAddPrototype` to parse all commands in a namespace when the typed IR is enabled. That parser mutates Brigadier callback contexts for some chained `execute` operations, but `TypedScoreIR` rejects most of those source shapes and retains their original queue entry. In the typed-only mode with old optimization flags disabled, the legacy wrapper could follow a `fallbackChain` that referenced its own rewritten callback, producing unbounded recursion. This is **not** an ASM failure; it is a parser/admission and observable original-command fidelity error.

**Fix:** `ScoreAddPrototype.compileEntry` now performs a conservative **pre-mutation typed-only source-shape gate** whenever only the opt-in typed IR compiler is active. It admits only existing literal fake-holder mutation, four literal binary operations and exact single-integer-score conditional mutation shapes. Every other command is left in its original `BuildContexts` command tree before a legacy parser can mutate it. Actual admitted commands still require Minecraft's parsed Brigadier arguments and their existing typed-`toIR` checks; this does not introduce a new textual command interpreter or widen any supported IR syntax. The other legacy research prototype configurations retain their existing behavior.

The corrected source passes the build, structural contract tests and the accepted original-source real player event. The accepted event recorded 511 typed instructions rather than switching off the bytecode compiler to avoid the adversary. **This is bounded evidence, not proof that every legacy fallback/missing-objective combination is now safe**; separate IR-014 queue/objective regression must pass after the code change, and unsupported modded callbacks are still outside the tested scope.

### Priority change

This real-event finding strengthens the architectural direction: target **increasing source-language and program coverage**, not shaving another fraction off the existing region scheduler. The compiler *does* execute useful direct JVM code repeatedly today, but it misses real datapack control flow and never qualifies its current recurring whole functions for IR-012 function-level direct scheduling. A mixed-function IR should represent unsupported original entries as explicit queue barriers (without wrapping them), preserve supported chunks and verify their relative ordering. Add range-based score predicates and typed score operations under fully accounted command quotas before pursuing selector contexts or function inlining.

## Engineering implication and next compiler experiment

**Do not spend another performance campaign on IR-012 direct scheduling under the current instruction whitelist.** There is no recurring fully typed source function in these two candidate workloads; a fast scheduler applied to no meaningful real program proves little.

Prioritize a compiler-first **IR-016 mixed-function representation** with opaque original-command barrier nodes and precise queue/frame semantics. The concrete goal is to retain native/vanilla actions for unsupported commands *inside the same program model* while allowing supported adjacent typed regions, and then progressively replace the highest-value barriers with typed control flow. This is not permission to run unknown commands inside a bytecode chunk without returning to vanilla's scheduler.

A reasonable staged expansion is:

1. Build a mixed original-entry/typed-region **program and coverage ledger**. It should report line-level emitted code and fallback/admission, rather than just class generation. Validate that a nested function, unknown command, or callback never disappears or moves across a vanilla queue boundary. Do not claim whole-function direct scheduling until its frame behavior is proven.
2. Add testable `execute if/unless score ... matches <range>` and guarded simple score operations, keeping per-stage quotas and result callbacks. This is a high-confidence extension of IR-009's already-tested single-integer guard, **not** a promise of speedup.
3. Explore context-dependent `@s` score binding and block/state predicates as separate new instruction families, then `execute ... run function`/call chaining under explicit return, fork, macro and callback gates. The source examples justify compiler-language relevance, not dynamic CPU priority.
4. Use native differential tests on *representative original source command sequences* and a real datapack execution scenario. Verify generated bytecode activation, complete state, partial quota effects, traces, failures, queued callbacks and returns. Only then perform a same-JVM CPU crossover with A/A controls and end-to-end real event checks if an actual hot compiled function is demonstrated.

Production compiler defaults, prototype flags, and PR state remain unchanged. The only runtime changes are narrowly gated typed-only research parser admission behavior and native diagnostic checkpoints. This research is not merged.

## Reproduction

```bash
python3 -m unittest discover -s tests -p 'test_typed_ir015_coverage.py' -v
python3 scripts/ci_typed_ir015_fetch.py
python3 scripts/ci_typed_ir015_coverage.py --packs veinminer blastback
```

Outputs: `build/reports/COMPILER-IR-015/summary.json`, and full per-function `veinminer.full.json` and `blastback.full.json`. The original publisher archives are not committed or uploaded as test artifacts.
