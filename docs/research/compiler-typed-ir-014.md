# COMPILER-IR-014 — Adversarial queue, scoreboard lifecycle and return-frame acceptance

**Status:** **Accepted bounded native Minecraft 26.3/Java 25 semantic parity** (2026-11-20); research-only, no CPU/performance promotion or production-default change. On `work/compiler-coverage`, existing open draft PR #10.

## Why this test exists

IR-013 closed one demonstrated execution-order bug: a synchronous scoreboard listener could call `ExecutionContext.queueNext` and arrange to run another function between two source commands, while the original generated region continued before Minecraft flushed the queue. A per-context queue epoch now yields the remainder into individual typed command actions on actual insertion.

That proof was bounded to one-level enqueuing and a known set of commands. The next significant adversaries are **cascading insertions**, **dynamic objective replacement/removal**, and **child-frame return/discard**, all of which can invalidate assumptions about commands executed after a callback.

This milestone is intentionally a **correctness expansion**, not a new optimizer or scheduler rewrite.

## Changes

- The opt-in `ReentrantQueueProbe` observer can dispatch different already-authored functions for watched `#ir014_*` fake holders. It still uses the *actual current ExecutionContext* and `ExecutionContext.queueInitialFunctionCall`. No callback executes the injected function inline. No normal game action enables these hooks.
- `fc_ir013_call`'s research-only allowlist admits bounded `fc_ir014_*` fixture functions in addition to `ir013_*`. The ordinary command path and production defaults are unchanged.
- `scripts/ci_typed_ir014.py` creates one disposable source datapack and runs four actual Minecraft 26.3/Java 25 modes: uncompiled native, guarded JVM bytecode, guarded typed interpreter, and guarded direct resumable scheduler.
- Per-mode test cases include first-level and second-level callback insertion; an inner score read that must observe the second insertion; a conditional guarded mutation after insertion; a callback removing and then re-creating an objective with the **same name but a new identity**; a callback leaving an objective missing so the next typed instruction uses its original fallback; and an injected child function with `return 0` whose frame must not suppress the caller's tail.
- Full-result checks are complemented with native-versus-compiler **complete scoreboard snapshots** at command quotas `1,2,3,4,5,8,12,16,32,64,65,80,140`. Snapshots distinguish absent watched score rows, missing `fc_aux` objective, and an existing score of zero. The test checks nonzero generated-region, detected-yield and resumed-step counters, and direct-scheduler actual call admission.

Acceptance is strict: **all guarded cases must exactly match the native arm, including partial effects**. The native arm is authoritative for frame/return effects; no guess about those semantics is silently used as an expected result. Independent full-run expectations additionally check the nested callback order and objective identity behavior. Any divergence is a failed experiment to diagnose, not a result to suppress.


## Accepted native evidence — November 20, 2026

[Successful four-JVM GitHub Actions run #44768987301](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44768987301) · [Archived server logs and 280 per-case observations (artifact #14647070317)](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44768987301/artifacts/14647070317).

The build and four structural tests passed, followed by **four independent real Minecraft JVMs** running **70 state snapshots per arm** (five full-run cases + five cases under 13 individually verified command quotas). The original native mode was the reference; every guarded compiled mode matched its **entire scoreboard snapshot in all 70 cases**, including objective and row absence.

| Execution mode | Native state parity | Runtime evidence |
| --- | --- | --- |
| Vanilla/unwrapped | Reference, 70 observations | 80 real listener-queued function calls |
| Guarded JVM bytecode, ordinary call scheduling | **70/70** | 8 emitted regions, 73 yields, 125 exceptional queued steps |
| Guarded interpreted typed IR | **70/70** | 8 IR regions, 73 yields, 125 exceptional queued steps |
| Guarded JVM bytecode, direct resumable scheduler | **70/70** | 8 bytecode regions, 73 yields, 125 queued steps, **105 admitted direct function calls** |

Each compiled mode also executed **232 actual typed steps** and **nine original-command runtime fallbacks**, exercising missing-objective behavior rather than simply refusing all compiled work. The test observer queued 80 calls per JVM.

Independent expected full-run checks confirmed that the nested callback's newly queued mutation was visible to its caller (inner_seen=9, final marker=11); the same-name replaced objective was read after re-creation (aux_input=19, seen=20); a removed objective stayed absent but did not suppress the independent next command (after=1); and an injected child return 0 did not cancel the caller's continuation. The guarded execute-if-score test also matched vanilla.

**Interpretation:** IR-014 extends native correctness evidence for IR-013's exceptional queue recovery to nested callbacks, re-created/removed objectives, fallback, result-independent frame return and low quota partial effects. It **does not establish performance improvement or universal correctness** under arbitrary mods, tracing, async misuse, unsupported function shapes or frame discard contexts beyond these fixtures. The native workflow was archived as manual-only after acceptance.

## Safety and scope

The benchmarked IR-013 CPU study was inconclusive and is not rerun. This test introduces no production compiler default, no value-caching optimization, no broad fallback handling change, no inlining, and no performance claim. It does **not** prove behavior for arbitrary mod-driven direct queue mutation, asynchronous callback violations, unsupported command families, multiple players, resource reload or arbitrary frame-discard interactions.

**Next step:** Expand whole-function acceptance with representative datapack programs and broader trace, callback and frame-discard behavior. Optimize execution boundaries only after the semantic coverage and a credible workload are established.
