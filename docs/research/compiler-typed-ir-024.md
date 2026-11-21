# COMPILER-IR-024 — Compiled fork-plan admission, native-selector delegation, and backend separation

**Status (2026-11-21): ACCEPTED first compiler-owned fork-plan admission milestone.** Two independent native-vs-compiler Minecraft 26.3/Java25 matrices passed (four fresh game JVMs); the compiled branch recognized three exact hot-shape native fork plans, rejected the near-miss, ran generated JVM scoreboard code on both sides of original fork barriers, and preserved 26 native scoreboard snapshots per arm across ordinary and 12 low/medium command quotas. **No compiled fork execution, selector replacement, index, membership cache, causal CPU gain or production promotion.** Branch `work/compiler-coverage`; PR #10 draft/unmerged. The workflow is archived manual-only.

## Why this is compiler work

The compiler's responsibility is **function-level specialization**: recognize a safe post-Brigadier `execute as @e[...] if score @s ... run scoreboard players set ...` shape and retain an immutable, source-positioned representation of that operation. A future generated JVM path could use the existing parsed `EntitySelector` for live lookups, retain the original score condition and generate the terminal scoreboard mutation. The compiler must never mistake selector membership for final score-condition eligibility.

A global tag index, spatial index, or cross-command membership cache would be a **separate runtime service**, albeit one a compiler might call. The service would own membership, lifecycle and invalidation correctness, plus runtime capability/guard checks. The compiler would only admit a guarded lowering when that service's exact semantic contract and original fallback are established. Recognized site shape alone grants no right to use a cached answer.

## IR-023 constraint

The mapped 26.3 `Entity.entityTags()` exposes a mutable set. A native test-only direct-set fixture changed selector eligibility `0,1,0,1,0` inside a single function while all `addTag/removeTag` and watched-eligibility observer counters remained zero. The earlier original Blastback census measured approximately 5.3 successful watched-tag changes per original selector call, but did not account for every mutation path. This precludes a generic index based on the existing method/lifecycle invalidators. A global epoch also cannot help unless **every** mutation increments it; validating cached hits cannot recover newly matching omitted entities.

The original `EntitySelector` is already parsed by Brigadier and reused. "Cache parsed selectors" is not a valid standalone performance proposal. Maintaining a list of `Entity` references across commands also risks unloaded/replaced entities, ordering, source permissions, dimension changes and observed same-queue tag changes.

## First compiler-only milestone

`CompilerForkPlan024` is a strictly opt-in **classification**, enabled only by `FC_TYPED_IR_NATIVE_FORK_PLAN=true` plus the existing typed-IR wrapper/namespace gates. It checks a deliberately narrow static source shape and extracts the **original Brigadier-parsed** `EntitySelector` from the existing `execute as` modifier. It validates the **three actual native Brigadier modifier contexts** (verified from the mapped Minecraft JVM: `[execute, as, targets]`, `[if, score, target, targetObjective, =, source, sourceObjective]`, and the distinct `[run]` bridge) plus the scoreboard terminal, rejecting nonmatching shapes. It does NOT evaluate, materialize, cache or substitute any selection.

`MixedFunctionIR.NativeForkPlanBarrier` is a source-positioned immutable node containing that plan **and the exact original** `BuildContexts.Unbound` entry. Its executable action is still the original native action, its direct-scheduler eligibility is always false, and its IR ledger reports `native_fork_plans` and source-position layout symbol `N`. Adjacent scoreboard regions remain independently eligible for existing typed JVM compilation. When the flag is off, even the classification is bypassed and all original opaque barriers remain as before.

This deliberately modest first step tests the correct compiler boundary before touching runtime semantics. **An admitted plan is not an optimized fork.**

## Native acceptance gate

Two fresh original Minecraft 26.3/Java25 JVMs execute the same original test-only datapack:
- Native mode: no compiler wrapper or fork-plan flag.
- Fork-plan mode: typed bytecode for validated adjacent scoreboard regions, with opt-in parsed selector-plan admission and exact original action retained for the fork.

The authored function contains three watched-tagged per-entity score-guarded selector commands and real intervening `tag` mutations. Native expected state includes both accepted and suppressed guards, and the source-position ledger must admit exactly those three plans, not the deliberate near-miss. A 13-setting original command-sequence quota matrix is compared using full scoreboard snapshots; missing rows remain distinct from zeros. Direct function scheduling, cached scores, selector indexes, custom compiled fork execution and unrelated prototype flags remain off. The experiment does not claim identical entity identity/order under every source, every quota, callback or mod integration; it verifies the specific authored native fixtures.

**STOP:** Any source-slot mismatch, missing parsed-argument evidence, unexpected near-miss admission, native scoreboard/quota divergence or direct-scheduler eligibility fails this compiler milestone. Even successful admission does not permit replacing native `BuildContexts` without separate native callback, quota, ordering, error, frame and performance evidence.

## Native acceptance — twice independently reproduced

The first [native/compiled research workflow #44870605236 attempt 1](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44870605236/attempts/1) and the [independent fresh-server repeat, attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44870605236/attempts/2) both completed successfully after real Minecraft26.3 native execution. Original reference commands and selected source text are not rewritten or mocked. Artifacts: [first native matrices #14694007128](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44870605236/artifacts/14694007128) and [independent repeat #14693713166](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44870605236/artifacts/14693713166).

| Exact acceptance gate | Both independently booted two-JVM matrices |
| --- | --- |
| Real vanilla vs opt-in compiler scoreboard parity | **26/26 full holder snapshots per arm**, including 12 truncating command quotas and unlimited execution on each of two fixtures |
| Post-Brigadier exact native selector fork shapes admitted | **3/3** at original source indices 7, 10, 12 (1-based ledger `N8:1,N11:1,N13:1`) |
| Similar execute-as score guard lacking required negated tag | **0 admitted**; original action retained |
| Generated JVM scoreboard compilation and actual execution | `bytecode_regions=2`, positive executed region and step counts; 0 reported fallback steps in first acceptance |
| Original world selectors and queue entry positions | Original `BuildContexts.Unbound` action reused; original executor, parsed selector and command ordering unchanged |
| Incorrect direct scheduler admission | **0**; exact native fork acts as an opaque compiler barrier |
| Cached membership or global index | **None**; per-command runtime selector remains original |
| Measured speedup | **Not measured** |

First compiler ledger for `fc_ir024:plan_case`:

```text
IR016 function=fc_ir024:plan_case source_lines=14 typed_lines=5 typed_regions=1 opaque_barriers=9 singleton_barriers=2 dispatch_barriers=0 native_fork_plans=3 direct_candidate=false layout=J1:5,V6:1,V7:1,N8:1,S9:1,V10:1,N11:1,V12:1,N13:1,S14:1
```

Near-miss `fc_ir024:near_miss` was a real compiled-scoreboard neighboring function yet reported `native_fork_plans=0`, demonstrating admission is not enabled merely by compiling a containing function. The first rejected admission attempt was **not** accepted as evidence: source-pattern recognition succeeded but our initial expectation of *two* parsed modifier contexts was wrong. Exact Minecraft logging showed a third `[run]` modifier stage, so the compiler now requires all three. The correction was verified in both accepted matrices.

These tests validate only the deliberate research fixtures and compiled neighboring score operations. **The fork itself is still uncompiled** and follows the original Brigadier task flow. Future backend work needs new native entity identity/order, callback, error, quota, and source-context equivalence gates; the existing four-suite default-off IR016–019 studies and IR023 direct-mutation bypass remain applicable safety context, not a blanket certification of this new instruction family. The source/harness is test-only and all production flags remain OFF.

The research workflow has been archived as manual-only after two accepted attempts.

## Future architecture — not implemented

A possible later Java interface would distinguish a source-shaped compiled query plan from runtime execution:

```text
PostBrigadierForkPlan(nativeSelector, scoreCondition, terminal)
   |
   +--- original native BuildContexts [current only path]
   |
   +--- optional compiled native-selector delegation [unimplemented]
           |
           +--- original selector.findEntities(source) [live, no cache]
           |
           +--- optional runtime lookup service [not admitted]
                    requires complete invalidation or exact fallback
```

The runtime service could live in a separate package or optional module and be reused by noncompiler clients, but it must not hold broad global entity state under the guise of a compiler optimization. Only allowlisting at the compilation site with original runtime fallback can ever admit it.

**Priority:** advance genuinely compiled execution, scoreboard/condition code generation and queue-compatible fork lowering; treat global entity indexes and membership caches as optional independent systems rather than blocking prerequisites.
