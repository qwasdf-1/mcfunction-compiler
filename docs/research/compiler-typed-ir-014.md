# COMPILER-IR-014 — Adversarial queue, scoreboard lifecycle and return-frame acceptance

**Status:** Implementation and tests committed as a **research-only native validation candidate** on `work/compiler-coverage`; native result **pending**, no performance or production-promotion claim. The successful IR-013 semantic study is the prerequisite, not evidence that IR-014 has already passed.

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

## Safety and scope

The benchmarked IR-013 CPU study was inconclusive and is not rerun. This test introduces no production compiler default, no value-caching optimization, no broad fallback handling change, no inlining, and no performance claim. It does **not** prove behavior for arbitrary mod-driven direct queue mutation, asynchronous callback violations, unsupported command families, multiple players, resource reload or arbitrary frame-discard interactions.

**Next step:** Run the bounded native workflow and inspect its per-case artifacts, Minecraft errors, and function/queue counters. Do not call this accepted until the actual run passes. If any mismatch appears, first establish the exact vanilla ordering and the differing compiled action boundary; only then modify the runtime.
