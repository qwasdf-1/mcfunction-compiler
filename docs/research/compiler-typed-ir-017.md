# COMPILER-IR-017 — Typed inclusive score ranges and guarded scoreboard arithmetic

**Status (2026-11-20):** **accepted** five-JVM IR-017 native parity, two SHA-pinned source-coverage audits, three original Vein Miner JVMs and eight post-change IR-014/IR-016 regression JVMs. No CPU/performance evaluation or production promotion. Research branch `work/compiler-coverage`; draft PR #10 remains unmerged. **No CPU or production speedup claim.**

## Why extend IR-016?

IR-016 made the compiled function a source-positioned immutable `MixedFunctionIR.Program` with compiled typed regions and exact original-command queue barriers. It did NOT make a substantially larger portion of real datapacks eligible for optimized code. IR-017 expands the native typed language in two precise ways:

1. `execute if/unless score #literal objective matches <range> run scoreboard players add|remove|set #literal objective N`, including `N..M`, `..M`, `N..`, negative integers, exact `N`, and full int32 endpoints.
2. The same score predicate guarding one validated literal-target scoreboard binary operation `=, +=, -=, *=` with a literal score source and objective.

No `@s` or entity selector, multi-modifier execute chain, fork, function call, data-context macro, arbitrary arithmetic operator or generic unknown command is newly compiled. Source string regex is **admission preflight only**. All actual score holder identities, objectives, operands and bounds come from Minecraft's already-validated Brigadier callback and must match the textual source exactly. The new experimental feature is **explicit opt-in via `FC_TYPED_IR_RANGE_GUARDS=true`**, which requires the existing nonblank `FC_TYPED_IR_NAMESPACE` and `FC_TYPED_IR_MODE=interpreted|bytecode` as before. With the IR-017 flag omitted or false, the IR-009 exact-equality/mutation-only guard acceptance remains unchanged. All production defaults are off.

## Compiler and runtime changes

- `ScoreConditionCommand`: exact one-stage literal guard preflight extended to one integer interval and one of the preexisting four safe binary operations. The source interval is parsed solely for a **fail-closed equivalence check** against Minecraft's parsed `MinMaxBounds.Ints`: test both inclusive endpoints, test immediate values outside bounded endpoints, and check the int32 extremes for unbounded intervals. Invalid integer literals and inverted ranges decline. Parsed command nodes and target identities remain authoritative, not the textual substring.
- `ScoreOperationCommand.toBinary`: the same strict Brigadier-backed eight-token and callback operand equality validation used for plain binary instructions now accepts the separately extracted guarded terminal. The parent `FusedCommand` retains the exact *whole original execute command* for vanilla fallback and tracing.
- `TypedScoreIR.Conditional`: now owns an immutable terminal of type `Mutation` **or** `Binary` and a parsed score interval; its effect model conservatively reads the guard holder plus all terminal read/write slots. Nested `Conditional` is forbidden. Each original command, including the guard and terminal, remains one observable boundary.
- `TypedScoreIRRuntime.State.begin`: resolves and validates up to **three distinct objectives** (target, guard, binary source) *before any quota debit or score-row creation*. Missing objectives take the normal original validated command fallback. The condition uses `ReadOnlyScoreInfo` before any scoreboard write, handles an absent score row, charges the condition stage, and charges the terminal stage only for a passing guard; no terminal write or feedback occurs on skip. Under insufficient quota the terminal is never run.
- Both ASM and IR interpreter lower the guarded `Binary` operation to direct JVM `ScoreAccess` calls after the shared range decision. `finish` sends the original operation's `CommandResponseTracker` response rather than accidentally using a mutation message, preserving original command return/feedback/tracing contracts. `guarded_binary_steps` is a diagnostics-only count of actually started terminal operations.
- All IR-016 mixed-program queue boundaries and IR-012 direct-scheduler admission gates remain intact. A valid fully typed **range-guarded function** may now be admitted to IR-012, but any barrier, return, macro, missing objective runtime path, compiler failure or original singleton retains its prior guarded fallback behavior. IR-013 queue-epoch recovery remains the only supported opt-in mitigation for scoreboard listeners that insert work inside a compiled region.

## Native semantic acceptance — complete

[Five-Minecraft-JVM accepted native test #44799403212](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44799403212) · [Full data artifact #14659876660](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44799403212/artifacts/14659876660).

Five fresh real Minecraft 26.3 / Java 25 JVMs ran **identical original mcfunction source** across 12 adversarial function cases at full execution and under 13 command quotas (`1,2,3,4,5,6,8,12,16,32,64,65,130`), producing **168 full scoreboard snapshots per mode / 840 observations overall**. Modes:

1. Vanilla/no compiler — authority for state, errors, scheduling, and quota behavior.
2. Original IR-016/IR-009 opt-in bytecode with `FC_TYPED_IR_RANGE_GUARDS=false` — same new binary but old exact-integer/mutation-only guard admission.
3. IR-017 typed reference interpreter, ranges on.
4. IR-017 generated direct JVM bytecode, ranges on, whole-function direct scheduler off.
5. IR-017 generated bytecode with the existing guarded IR-012 direct scheduler on, ranges on.

**All four compiled/experimental arms exactly matched the original vanilla state in every 168/168 snapshot.** Independent full-execution assertions checked negative and int32 extreme bounds, `if`/ `unless`, inclusive/open-ended bounds, all four guarded binary operations, three distinct objectives, absent score holders and missing objectives, same-target/read holder aliasing, unsupported division barriers, nested function calls and `return`, and cascading native scoreboard-listener-queued child functions. The test does not reduce absent scoreboard entries to zero: it explicitly snapshots missing score holder and objective conditions.

| Native full-test diagnostic | IR-016 ASM (flag off) | IR-017 interpreter | IR-017 ASM | IR-017 ASM + direct |
| --- | ---: | ---: | ---: | ---: |
| Compiled typed regions at load | 11 | 18 | 18 | 18 |
| Emitted generated JVM ASM regions | 11 | 0 | 18 | 18 |
| Actual typed-step executions | 248 | 548 | 548 | 548 |
| Started conditional terminals | 0 | 178 | 178 | 178 |
| Guarded binary steps | 0 | 104 | 104 | 104 |
| Original-command runtime fallbacks | 0 | 21 | 21 | 21 |
| Reentrant yields / queued continuations | 9 / 14 | 20 / 33 | 20 / 33 | 20 / 33 |
| Direct scheduler admitted function calls | 0 | 0 | 0 | 137 |

The compiler's bounded source-span ledger independently showed `ir017_guarded_binary` changing from **3 of 10 typed lines** in the previous compiler to **10 of 10** in IR-017, a single JVM region with no opaque barriers and valid whole-function admission. The seven-line ranged-mutation fixture likewise changed from **2 of 7** to **7 of 7** typed lines. The direct scheduler continued rejecting functions containing opaque nested calls or returns.

The counts above are **not CPU timings** and do not imply corresponding reductions in runtime work; IR-017 performs different internal work and the two compiled variants do not execute an equal number of typed steps.

## Real publisher source-coverage delta — accepted

[SHA-verified original datapack census #44799041030](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44799041030) · [raw classification artifact #14659688626](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44799041030/artifacts/14659688626).

The exact same original Vein Miner 5.3.0 publisher ZIP (SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`) and Blastback Hotfix 3 ZIP (SHA-256 `8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90`) were rescanned with IR-016 vs IR-017 *exact source-shape* screens.

| Source-only count | Vein Miner IR-016 → IR-017 | Blastback IR-016 → IR-017 |
| --- | ---: | ---: |
| Total original functions | 76 | 21,318 |
| Total source command lines | 768 | 269,141 |
| Exact typed-shaped instructions | **69 → 78 (+9)** | **537 → 551 (+14)** |
| Candidate lines in 2–64 typed regions | **31 → 44 (+13)** | **140 → 157 (+17)** |
| All-typed whole-function candidates | **2 → 2** | **1 → 2** |
| Recurring tick/scheduled candidate region lines | **5 → 5 (unchanged)** | **35 → 42 (+7)** |

A Vein Miner source-level gain of nine ranged guard instructions is concentrated in `vm:lifecycle/load` and two administration helper functions, not the identified recurring queue/mining scope. Blastback gains ten ranged-mutation source lines and four guarded-binary lines, including several new short recurring candidate regions. These counts **do not prove runtime parser acceptance, hotness, or a speedup**; generated macro expansions and external function entry are not exhaustively represented in this static graph.

**Engineering conclusion:** The new IR language makes more code compilable and was actually exercised in native Minecraft, but the measured real-source expansion is still modest. It is premature to claim real-player CPU savings. The primary blocked language families remain selectors, context-bound `execute` modifiers, and especially conditional function dispatch (e.g. `execute if score @s ... run function`). Implementing them requires preserving execution-source semantics, function frames, callback outcomes, forked branches, macros and queue order; merely broadening eligibility regexes is unsafe.

## Real 215-block publisher event: old versus new compiler — accepted, NOT a speed benchmark

[Three-new-JVM original Vein Miner 5.3.0 run #44799665141](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44799665141) · [raw original-source event artifact #14661395614](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44799665141/artifacts/14661395614).

Three independent Minecraft 26.3 Java25 server processes ran the unchanged SHA-verified Vein Miner ZIP with exactly the existing player-bot 215-block mining test:

1. Wrapper-only reference, no typed compiler;
2. IR-016 bytecode baseline (`FC_TYPED_IR_RANGE_GUARDS=false`);
3. IR-017 bytecode (`FC_TYPED_IR_RANGE_GUARDS=true`).

All arms completed **215 work blocks**, with the **same 1,952 queue-head increments**, one actual player source-block mine, full cleanup and no remaining markers or ores. **All nine independently checked final event state fields matched**. Both bytecode modes emitted and executed real generated JVM instructions.

| Event-local diagnostic | IR-016 compiler | IR-017 compiler |
| --- | ---: | ---: |
| Bytecode regions generated at load | **6** | **7** |
| Executed regions during player mining | 245 | 241 |
| Actual directly lowered typed steps | 520 | 508 |
| Guarded binary instruction executions | **0** | **0** |
| Reentrant callback yields in this ordinary workload | 0 | 0 |
| Original-command fallbacks within typed regions | 0 | 0 |

The new compiler did compile one more static region at load, consistent with IR-017's additional source shapes in the load path. **No new guarded binary operations executed in this mining event.** The independent server boots perform similar but not precisely identical numbers of dynamic commands; 520 versus 508 typed steps must NOT be characterized as an improvement, reduction, or CPU-saving percentage. No server-thread CPU samples, A/A controls, paired timing windows, or end-to-end timing comparisons were taken. The result supports new *compilability* at load, not a measured new hot-path optimization.

These native findings narrow the hypothesis: **range/guarded-binary lowering is a genuine language/compiler expansion, but its effect on this real datapack's mining critical path is currently negligible or absent.** Focus on selectors, context modifiers, and controlled conditional function calls before spending more research cycles on a synthetic-only speedup claim.

## Legacy semantic regressions after introducing IR-017 — accepted

[Accepted eight-real-JVM regression #44800233727](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44800233727) · [all IR-014 and IR-016 native state artifacts #14661371126](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44800233727/artifacts/14661371126).

After implementing the ranged/guarded-binary changes, we rebuilt the Minecraft 26.3/Java25 mod and passed IR-009, IR-013, IR-014, IR-015, IR-016 and IR-017 structural contracts (7 + 7 + 4 + 4 + 5 + 6 tests). We then ran **eight additional native Minecraft JVMs**:

- IR-014's vanilla, guarded interpreter, guarded bytecode, and direct guarded bytecode arms: **70/70 complete scoreboard states per mode** matched vanilla across nested callback queue insertion, lifecycle removal/recreation, conditional guards and multiple command quota cuts.
- IR-016's vanilla, mixed interpreter, mixed generated JVM and whole-function direct arms: **126/126 states per mode** matched vanilla across opaque barriers, nested function calls, `return`, result stores, a mod-added command, missing objectives, chunk boundaries and quota cuts.

The old language still behaves as before with `FC_TYPED_IR_RANGE_GUARDS` omitted. These regressions support backward compatibility for the bounded tested cases; they do not certify every modded command or all execution contexts.

## Reproduction

```bash
./gradlew --no-daemon build
python3 -m unittest discover -s tests -p 'test_typed_ir017.py' -v
python3 scripts/ci_typed_ir017.py
python3 scripts/ci_typed_ir015_fetch.py
python3 scripts/ci_typed_ir017_coverage.py
python3 scripts/ci_typed_ir017_real_event.py
```

Run the publisher datapack event separately from this test; do not call distinct JVM boot work times a performance crossover.

## Non-goals and remaining verification

No new generic `execute` interpreter, entity selector support, macro expansion bytecode, cross-command value cache, scoreboard command elimination, or transparent direct scheduling across vanilla barriers. No production defaults or merged PR changes. Those native compatibility gates have passed. Before adopting IR-017 or making performance claims, perform a properly controlled CPU study on a workload shown to exercise the new typed instruction families and measure whether scheduling/dispatch costs actually decline. Any actual CPU analysis should then use a bounded warm-up, repeated samples, and same-JVM A/A controls or carefully counterbalanced native boots; report uncertainty rather than converting source coverage into percentage speedup.
