# COMPILER-IR-018 — Selector-bound scoreboard IR and native function-call barriers

**Status (2026-11-20):** **Accepted native research milestone**: five new selector-aware Minecraft 26.3 JVMs with 87/87 observed states per arm, thirteen additional post-repair IR-014/016/017 regression JVMs, a three-JVM original Vein Miner player mining event and two SHA-pinned publisher source audits. Research-only, no CPU/speedup claim or production promotion; branch work/compiler-coverage and draft PR #10 remain unmerged.

## Workload decision

Use **both original SHA-pinned datapacks for different questions**. Blastback is a much richer discovery corpus for execution-context selectors and conditional function dispatch; generated source counts cannot establish actual execution frequency. Vein Miner is our repeatable native gameplay baseline, with a passing 215-block player-bot mining event. The unresolved full Blastback restoration-workload oracle is not suitable for whole-pack performance comparison. An additional focused original-mcfunction fixture must prove native selector and child-function semantics before enabling anything more broadly.

## Compiled language expansion — opt-in, not production default

FC_TYPED_IR_SELF_HOLDER=true adds ONLY the literal current-source entity selector @s to the previously Brigadier-validated typed scoreboard forms:

- scoreboard players add/set/remove @s objective N;
- scoreboard players operation with @s as target, source or both, restricted to existing safe operations =, +=, -=, *=;
- a single if/unless score @s objective matches integer-range guard, or a fake-holder range guard followed by a supported @s terminal mutation or binary operation, under the separate IR-017 range flag.

The source string is an admission preflight, not a new command parser. Previously parsed Minecraft score-holder arguments, objective names, operations and bounds remain authoritative. Arbitrary @e/@a/@p selectors, execute as/at/positioned, multiple modifiers, forks, macros, score swaps and unsupported arithmetic stay vanilla.

TypedScoreIR records separately whether the target, binary source and condition holder are dynamically bound to the function invocation's CommandSourceStack. The effects ledger represents @s symbolically and conservatively marks each source command an observable barrier: no cross-instruction value forwarding, instruction elimination or hoisting is enabled. TypedScoreIRRuntime.State resolves each @s against the LIVE execution source per instruction, checks existence of the entity and objectives before direct-path quota charges or score writes, and uses the resolved holder in original feedback and result delivery. Missing entity/objective conditions take the original validated command path. The IR-013 reentrant queue-epoch guard remains opt-in as before.

## Conditional function dispatch is an opaque native barrier

MixedFunctionIR classifies original source lines that resemble execute if/unless score ... run function ... as FUNCTION_DISPATCH opaque barriers. A source-span ledger uses the letter F and reports dispatch_barriers; aggregate diagnostics include ir018_dispatch_barriers. Classification is source-level and intentionally overinclusive; it does NOT parse, interpret, inline or directly execute those child calls. Each barrier retains the exact original Minecraft UnboundEntryAction. Child function frame creation, queued command order, result/return/failure propagation, macro arguments and callback semantics remain vanilla. Such functions cannot enter IR-012's all-bytecode direct scheduler.

## Original publisher source coverage: accepted

[Two-publisher SHA-verified census](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44813074072) · [per-function classifications](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44813074072/artifacts/14668501438)

| Source-only statistic | Vein Miner 5.3.0 | Blastback Hotfix 3 |
| --- | ---: | ---: |
| Total original functions | 76 | 21,318 |
| Original source command lines | 768 | 269,141 |
| Newly IR-018-shaped selector commands | 90 | 14,668 |
| Potential typed-region lines, IR-017 | 44 | 157 |
| Potential typed-region lines, IR-018 | 133 | 273 |
| Potential recurring tick/scheduled region lines, before → after | 5 → 94 | 42 → 138 |
| Source-text guarded function dispatches, **all remain opaque** | 21 | 132,982 |

Blastback's newly eligible shapes are dominated by generated isolated guarded self-mutations: 14,668 lexical matches add only 116 potential compiled-region lines. Most of Vein Miner's new potential contiguous compilation is in vm:detection/acquire_target (61-instruction region candidate) and vm:player/register (26). The census is not a runtime parser acceptance study, dynamic hotness profile, or CPU benchmark; some source-shaped lines may decline at the parsed callback boundary.

## Real publisher 215-block gameplay: accepted

[Original untouched Vein Miner three-JVM run](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44813376167) · [raw observations](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44813376167/artifacts/14668198271)

The unchanged, independently SHA-pinned publisher pack ran the same original player mining event in separate wrapper-only, IR-017 bytecode with selector flag OFF, and IR-018 bytecode with selector flag ON Minecraft 26.3/Java25 servers. All three completed 215 affected blocks, 1,952 queue-head increments and the same nine checked final gameplay state fields. No ore or operation markers remained.

| Event diagnostic | IR-017 bytecode | IR-018 bytecode |
| --- | ---: | ---: |
| Generated JVM regions at load | 7 | 11 |
| Executed regions during mining | 242 | 268 |
| Executed typed instructions | 511 | 589 |
| Direct guarded-binary executions | 0 | **26** |
| Original command fallbacks inside typed regions | 0 | 0 |

Unlike IR-017, this feature did execute new supported guarded arithmetic in real gameplay. The independent boots have different internal instruction totals; their differences are NOT a measured CPU benefit or speedup. No same-JVM A/A controls, calibrated CPU sampling or performance confidence intervals were taken.

## Separate semantic gate and status

The dedicated IR-018 five-JVM differential matrix compares native Minecraft, IR-017 baseline bytecode with selector flag OFF, IR-018 interpreter, IR-018 ASM and IR-018 ASM plus guarded direct scheduling. Disposable original mcfunctions test real entity-bound @s, fake and dynamic holder aliases, distinct objectives, missing bound source, missing objectives, score ranges, nested conditional calls, returns, and partial quota cuts. The native function-dispatch barrier must never enter the direct cursor. Initial fixture runs were invalid because a no-player headless server could not retain an armor stand between RCON commands, even with a forced chunk and a support platform. The fixture now uses Minecraft's native execute summon modifier to bind an entity in the same command stage, then stores its scoreboard state into original fake-score holders before the function returns. This eliminates reliance on persistent entity tickets, while preserving native entity-bound scoreboard resolution and direct/opaque barrier admission tests.

The dedicated five-JVM entity/no-entity matrix **passed** after the true-original-Brigadier fallback repair. IR-014/016/017 native regressions **also passed after the final repair** (see final gate below). The evidence is bounded to these cases, not every modded callback or execution context.

## Reproduction

    ./gradlew --no-daemon build
    python3 -m unittest discover -s tests -p test_typed_ir018.py -v
    python3 scripts/ci_typed_ir015_fetch.py
    python3 scripts/ci_typed_ir018_coverage.py
    python3 scripts/ci_typed_ir018.py
    python3 scripts/ci_typed_ir018_real_event.py

## IR-018 entity/no-entity native acceptance and exceptional-path repair

[Accepted five-real-JVM matrix #44815757004](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44815757004) · [source, full states and logs, artifact #14668154970](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44815757004/artifacts/14668154970).

Five fresh Minecraft 26.3/Java25 JVMs executed identical original mcfunctions under vanilla, IR-017 bytecode with selector support off, IR-018 interpreter with selector support on, IR-018 generated bytecode with selector support on, and IR-018 bytecode with guarded direct whole-function scheduling on. A real armor stand was bound as @s with Minecraft's native execute summon command modifier; the original function copied its scores to fake holders before its invocation completed, avoiding dependence on retaining a headless-server entity between RCON calls. Separate original console invocations tested missing bound entities. Both paths were checked at full quota and under 11 quota cuts, with different score objectives, self-as-target and self-as-operand aliases, ranged guards, missing objective errors, child function calls and child return.

**Every compiled/control mode matched vanilla on all 87 complete scoreboard observations: 435 observed full states.** The old feature-off bytecode compiled one region with two source lines. The IR-018 bytecode emitted 10 real JVM regions comprising 53 typed source lines and executed 265 typed instructions across the native fixture, including 96 binary operations and 10 guarded binary operations. It performed 29 correct original-command runtime fallbacks. The guarded direct-scheduler mode admitted 39 function calls, but correctly refused to schedule functions containing opaque conditional child-call barriers. The J1:2,F3:1,F4:1,J5:4 dispatch layout retains Minecraft's native queue and frames. These are compilation activation and correctness observations, NOT CPU timings or performance gains.

**Important bug fixed before native acceptance:** The initial no-entity IR-018 interpreter crashed with StackOverflowError while falling back from a typed conditional guard. The ScoreAddPrototype parser had saved a ContextChain referencing a mutable executable CommandContext, and later replaced that same context's command with ScoreConditionCommand. The saved fallback therefore called the wrapper recursively rather than the true original callback when @s was unavailable. The fix records the original validated Brigadier executable callback BEFORE mutation, clones the original parsed executable context (including Brigadier arguments via a new Mixin accessor), and uses an independent native fallback ContextChain for accepted typed-only guards. This is a real original-command fallback, not source re-parsing or a synthetic exception. Earlier legacy prototype configurations retain their previous behavior. The post-repair native suite validated missing-entity and missing-objective low-quota states without recursion.

## Legacy post-change native regressions: accepted

[Successful three-suite native regression #44814071570](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44814071570).

The full Java 25/Minecraft 26.3 build and updated IR-009, IR-014, IR-016, IR-017 and IR-018 contract tests passed. Thirteen further independent real Minecraft JVMs exercised all accepted earlier features after the IR-018 Java code changes:

- IR-014 vanilla and three guarded modes: **70/70** native partial/full states matched per mode; artifact [#14669350681](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44814071570/artifacts/14669350681).
- IR-016 native, interpreter, bytecode and direct modes: **126/126** full quota and original-barrier states matched per mode; artifact [#14669260681](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44814071570/artifacts/14669260681).
- IR-017 native, old bytecode, interpreter, bytecode and direct modes: **168/168** range guard and reentrant callback states matched per mode; artifact [#14668673646](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44814071570/artifacts/14668673646).

These regressions were run with the new selector flag OFF, as in the original milestones; they establish that the old behavior remains stable in the bounded native scenarios. They do not substitute for the new entity-context native fixture or prove a selector-aware speedup.

## Final post-repair native regression gate: accepted

[Accepted post-2026-11-20 Brigadier fallback correction, 13 native JVMs #44816191427](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44816191427).

All three prior native suites were rerun after the independent original parsed Brigadier context snapshot fix, with the feature's default still OFF. Each suite passed its original Java build and the three new explicit pre-mutation fallback source contracts:

- **IR-014:** four vanilla/guarded mode JVMs, **70/70** complete scoreboard states in each arm, covering cascading queue callbacks and objective remove/recreate. [Raw artifact #14670530306](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44816191427/artifacts/14670530306).
- **IR-016:** four vanilla/interpreted/ASM/direct JVMs, **126/126** states in each arm, covering original queue barriers, child function/return, error fallback and command quotas. [Raw artifact #14669921146](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44816191427/artifacts/14669921146).
- **IR-017:** five vanilla/old-ASM/interpreted/ASM/direct JVMs, **168/168** states in each arm, including exact range guards, guarded arithmetic, reentrant callbacks and low quotas. [Raw artifact #14669248281](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44816191427/artifacts/14669248281).

**IR-018 is accepted as a bounded compiler correctness and language-coverage experiment.** This does NOT claim a CPU speedup, complete Blastback restoration correctness, arbitrary-mod callback fidelity, arbitrary selectors or compiled conditional function dispatch. Those remain future research questions. The accepted IR-018 selector feature and original-Brigadier fallback fix stay opt-in on the draft branch.

## Next safe direction

Before ever compiling conditional function dispatch, prove exact native child-frame scheduling, conditional command cost, return/run function, result callbacks, macro arguments, entity-context changes, fork handling, and listener-queued work. Blastback provides representative syntax, Vein Miner provides validated gameplay, and independent native fixtures provide precise semantic oracles. Measure performance only after demonstrating that a repeatable real workload executes newly compiled operations with a controlled CPU A/A and A/B design.
