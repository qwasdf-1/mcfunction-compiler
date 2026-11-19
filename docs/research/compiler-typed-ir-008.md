# COMPILER-IR-008 — first typed-IR-to-direct-JVM execution slice

**Status: IMPLEMENTED and NATIVE SEMANTIC GATE ACCEPTED (2026-11-19). Focused same-JVM performance screen accepted, directional only. Research-only and disabled by default.**

The objective is to return to the project's *optimizing compiler* goal rather than continue profiling ever narrower vanilla command boundaries. This is the first feature in this research branch whose bytecode backend actually executes supported scoreboard mutations directly, rather than merely unrolling calls to `FusedRegionPrototype.executeCommand` and `ContextChain.runExecutable`.

Implemented on the **existing `work/compiler-coverage` branch / draft PR #10**, with no merge, no production default change, no broad scheduler Mixin and no new textual command parser.

## 1. Implemented pipeline and exact supported subset

```text
Vanilla FunctionBuilder / Brigadier parsed command
        |
        v
ScoreAddPrototype.compile (existing typed validation)
        |
        v
TypedScoreIR.lower (strict bare literal fake-holder source-shape gate)
        |
        v
Immutable Program [Instruction × 2..64] or untouched vanilla entry
        |
        +--> TypedScoreIR.Interpreted (semantic reference)
        |
        +--> TypedScoreIRBytecode (ASM hidden class)
                 |        ScoreAccess.add(int)
                 +------> ScoreAccess.set(int)
                 |
                 +--> TypedScoreIRRuntime.State
                     per-command quota, trace, Objective/ScoreAccess access,
                     exact vanilla scoreboard feedback and error handling
```

The supported *direct-lowered* command subset is **only** bare, Brigadier-validated `scoreboard players add/set/remove #literal_holder objective integer` where `#literal_holder` is a static fake scoreboard holder. Accepted programs are contiguous runs of 2–64 instructions. A leading `execute` modifier, selectors (`@s`, `@e` etc.), score `operation`, conditional `execute if score ... run`, returns, function calls, unsupported or mod-added commands, macros, and all other commands are retained as **original vanilla scheduler entries**. A single typed-ineligible command splits the compiled regions.

The IR uses validated operation, static `ScoreHolder`, objective and amount from the existing `ScoreAddCommand` installed after vanilla parsing. The input regex checks exact command shape and equality with those parsed values; it does **not** create another Minecraft command parser.

**The new backend is real direct lowering:** `TypedScoreIRBytecode` emits JVM `INVOKEINTERFACE ScoreAccess.add(I)I` or `ScoreAccess.set(I)V` for each accepted instruction. It does **not** emit `BytecodeRegionPrototype.executeStep` or use `ContextChain.runExecutable` on an accepted direct step. That is the architectural change being tested.

**Still performed once per source command:** dynamic scoreboard/Objective lookup, a `ScoreAccess` mutation, the per-command `ExecutionContext` quota debit, `TraceCallbacks.onCommand/onReturn` if attached, `CommandResponseTracker.sendFeedback`, and the corresponding error handling. **No scoreboard writes are folded or delayed.** This intentionally avoids assuming command callbacks, scoreboard listeners or other mods cannot observe intermediate states. Typed IR interpretation and direct ASM call the exact same runtime boundary code.

An objective absent or read-only at execution time uses `FusedRegionPrototype.executeCommand` on the **retained parsed original command**, before the new backend has charged any quota or changed any game state. The test confirms this guard works when the formerly missing objective is later created. ASM class generation failure falls back to the typed interpreter before executing any command. Commands outside the typed subset are never rewritten. Ordinary vanilla function scheduling, frame creation, forks and return behavior are left untouched; no `max_command_sequence_length` relaxation.

Feature gate: `FC_WRAPPER_PROBE=true FC_TYPED_IR_MODE=interpreted|bytecode FC_TYPED_IR_NAMESPACE=<one explicit namespace>`. When absent the new code does not change function compilation. `FC_TYPED_IR_DIAGNOSTICS=true` permits the research-only `functioncompiler ir008` command to report program creation, execution and fallback counters; it is off in timed crossover windows.

Relevant new implementation files:

- [`TypedScoreIR.java`](../../src/main/java/dev/functioncompiler/TypedScoreIR.java): immutable instruction/program, lowering, region segmentation, two backends, source function identity;
- [`TypedScoreIRRuntime.java`](../../src/main/java/dev/functioncompiler/TypedScoreIRRuntime.java): one invocation state per region, quota/error/feedback/trace and original fallback;
- [`TypedScoreIRBytecode.java`](../../src/main/java/dev/functioncompiler/TypedScoreIRBytecode.java): direct ASM semantic operations and hidden JVM class;
- [`ScoreAddCommand.java`](../../src/main/java/dev/functioncompiler/ScoreAddCommand.java): strict parsed-value IR exposure;
- [`ProbeFunctionWrapper.java`](../../src/main/java/dev/functioncompiler/ProbeFunctionWrapper.java): opt-in function-build integration, original identity preservation;
- [`ProbeCommands.java`](../../src/main/java/dev/functioncompiler/ProbeCommands.java): opt-in activation report;
- [`scripts/ci_typed_ir008.py`](../../scripts/ci_typed_ir008.py): full native semantic test and unpaired CPU screen;
- [`scripts/ci_typed_ir008_crossover.py`](../../scripts/ci_typed_ir008_crossover.py): same-JVM ABBA/BAAB CPU crossover and same-path A/A.

## 2. Accepted actual Minecraft native semantic evidence

**Accepted [four-arm native CI run #44568589981](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44568589981)**. All four fresh actual Minecraft **26.3 Fabric / Java 25** JVMs ran the same disposable datapack:

1. native (wrapper disabled);
2. existing fused interpreter;
3. typed IR interpreted;
4. typed IR direct ASM bytecode.

All four paths produced identical observed scoreboard state for each of the following original commands/functions:

| Test shape | Exact accepted observation |
| --- | --- |
| Consecutive set/add/remove, two holders | `#x = 13`, `#y = -3` |
| Vanilla function call between two compiled regions | `#x = 17` |
| `execute if score ... run` **vanilla barrier** | `#x = 11` |
| `scoreboard players operation +=` **vanilla barrier** | `#x = 8` |
| 32-bit signed wraparound | `#x = 2147483647` |
| Missing objective, later created while server running | absent first, then `#m = 2` |
| Read-only objective | same vanilla absence/error response |
| `execute store result ... run function` | matching stored result and final scoreboard state |
| `minecraft:max_command_sequence_length` | exact parity for quotas **1,2,3,4,5,6,7,8,10,16,32**, including partial effects |

Actual **bytecode** activation diagnostic: **11** compiled regions, **11** generated bytecode regions, **22** region executions, **74** direct scoreboard instruction executions and **4** original-entry runtime fallbacks. IR-interpreted had the same region executions, steps and fallbacks and zero emitted bytecode regions. This is not a test of every possible trace, callback topology, modded command or reload interleaving. The built-in source/semantic tests cover the explicit contract, not a proof of universal vanilla equivalence.

There were two invalid *development* attempts that were not used as CPU results: a Java compile error at the checked `sendFeedback` exception boundary (corrected to match the existing executor), and an initial CPU runner that searched for the Server thread in the Gradle wrapper PID rather than its Minecraft JVM descendant (corrected). Only the accepted run above is used.

### First unpaired CPU screen (same 10,240 writes)

| Mode | Linux Server-thread running CPU |
| --- | ---: |
| Native/wrapper disabled | **37.625 ms** |
| Existing fused interpreted | **23.696 ms** |
| Typed IR interpreted | **14.832 ms** |
| Direct ASM IR | **13.441 ms** |

These are **four independent server boots**, one CPU interval per mode with semantic diagnostic instrumentation enabled. They establish exact work and measure a *screening* direction, **not** a causal speedup or production promotion.

## 3. Same-JVM, original-fusion vs direct-ASM controlled screen

**Accepted [same-JVM native crossover #44569699216](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44569699216)**. Both original 64-line benchmark functions are byte-for-byte identical except their namespace: `fc_fused:bench64` uses the existing `FusedRegionPrototype`, and `fc_ir:bench64` uses the new directly emitted JVM backend. They run in **the same JVM, with distinct compiler namespace gates**, with all high-cost command metrics off.

- **Two fresh Java25/Minecraft26.3 Fabric JVMs**, eight balanced ABBA/BAAB fused-vs-ASM blocks in each, 16 blocks total. Every block consists of four CPU windows and each window executes **160 calls × 64 commands = 10,240 actual scoreboard writes**. Each window validates the exact resulting scoreboard value; **all windows passed**.
- Four additional same-function A/A blocks per JVM (**eight** total) compare the fused function with itself to expose ordinary noise.
- Median signed ASM-versus-fused running-CPU fraction over the **16 correlated windows' four-way block estimates**: **−17.947%**. Each JVM's median favored direct bytecode: **−11.445%** and **−22.274%**.
- Individual ASM/fusion blocks ranged **−39.55% to +54.87%**; the same-path A/A median was **+0.608%** and its range was **−15.11% to +24.23%**. Measurement noise and outliers are material.
- The observations are **directional evidence of an advantage in a focused uniform-score workload**, not a 95% independent-server confidence result, a confirmed 15% promotion gate, or a generalized speedup on arbitrary datapacks. Within-boot windows are correlated, and both backends still perform essential scoreboard and feedback work.

Both accepted research workflows archive per-arm/per-window logs, artifacts and all unfiltered source/clock observations:
[IR-008 native semantic artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44568589981/artifacts/14552592991) ·
[IR-008 same-JVM crossover artifact](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44569699216/artifacts/14554466419).

## 4. What this proves and what comes next

This milestone has an actual compiler-front-end-to-execution vertical slice: **already-parsed commands → conservative typed semantic IR → IR interpreter or direct generated JVM operations → vanilla-compatible command bookkeeping**. It is not simply an ASM wrapper for an old execute-step method. It works on the pinned native server, exhibits exactly exercised bytecode, and has directional CPU evidence compared with the prior fused interpreter.

**It is not yet a general optimizing compiler.** There is no direct lowering for scoreboard operation, condition, arbitrary command or nested function. Cross-instruction scoreboard caching, common-subexpression elimination, constant propagation and function inlining are deliberately not claimed: they require a sound effect/callback/barrier model. No substantial real-datapack campaign, comprehensive `/debug function` tracer comparison, multi-mod compatibility run, reload/class-unloading endurance or independent-JVM confirmatory performance gate has been run for this new backend.

**Next compiler milestones, not another datapack search:** introduce a typed branch/score-operation IR with exact modifier-stage quota semantics and boundaries; add a conservative per-instruction effect model so reads can be reused when legal; then evaluate the same interpreter vs direct bytecode backend on arithmetic and control-heavy real workloads. Preserve a native reference for every new instruction family, not just the final score. A production promotion still requires exact semantic coverage (including modded callbacks, trace, quotas and reload) and a separately preregistered reliable real-world performance result.

**Decision:** Keep enabled only by explicit research env flags and keep PR #10 draft/unmerged. This milestone successfully tests the *compiler architecture*, not broad production performance.
