# COMPILER-IR-025 — Generated native-selector fork execution

**Status (2026-11-21): IMPLEMENTED CANDIDATE, native semantic validation in progress.**
Experimental branch `work/compiler-coverage`; PR #10 draft and unmerged.
No production flags changed, no selector index, no cached entity membership,
no causal performance claim and no original Blastback complete-restoration claim.
`docs/research/compiler-typed-ir-024.md` is the already-accepted *classifier
only* milestone; this is the first new executable generated fork.

## Goal and scope

Given a strictly validated original Minecraft function command:

```mcfunction
execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1
```

generate one JVM `UnboundEntryAction` at the original source position
that handles fork orchestration without the general Brigadier modifier-stage
walk and per-entity `CommandContext.copyFor` during the score guard.

This is an actual compiler code path, **not** a replacement EntitySelector, a
runtime global entity index, a static tag snapshot or a general Minecraft
command redirect rewrite.

## Actual mapped Minecraft 26.3 contract

The verified Loom-mapped original bytecode inspection is archived in the
`COMPILER-IR-025-MAPPED` report. Relevant native components are:

- `BuildContexts.Unbound.execute(source,context,frame)`: original command
  tracer, then one-item native source list and the `ChainModifiers.DEFAULT`
  stage executor;
- `BuildContexts.execute`: one cost debit per redirect-modifier stage,
  full native fork-limit test, first-stage `as` source mapping and second-stage
  score-guard filtering; the `run` bridge itself requires no new modifier
  cost;
- `EntitySelector.findEntities(source)`: original live permission, selector
  predicate, dimension, sort/limit and membership logic;
- `CommandSourceStack.withEntity(entity)`: per-selected source binding;
- `ContinuationTask.schedule`: native 0/1/2 special cases and a deferred
  per-source continuation when cardinality is above two;
- `ExecuteCommand.bind(source)`: original terminal scoreboard callback,
  feedback, exception, per-terminal quota debit and tracer `onReturn`.

The parsed Brigadier `execute as`, `if score` and `run` contexts remain
validated against the original source's literal node ranges. Classification
never invents a selector from an unvalidated string.

## Compiled backend

`CompilerForkBytecode025` emits a JVM hidden class implementing
`UnboundEntryAction<CommandSourceStack>`. Its constructor captures a
validated immutable `CompilerForkPlan024.Plan` and the exact original
`BuildContexts.Unbound` action for fallback. The generated `execute` method
invokes the specialized, audited `CompilerForkExecutor025.run` entrypoint.

The fast path:

1. Re-resolves both score-guard objectives and the writable terminal
   objective from the current server scoreboard; if missing or read-only,
   delegates **once** to the exact original command without any partial
   compiled fork effects.
2. Emits native `onCommand` tracing and preserves a profiler scope.
3. Debits the original `execute as` modifier cost.
4. Calls the **original parsed `EntitySelector.findEntities(source)`**
   on every execution. Builds `source.withEntity(e)` in original selected
   order for **all** selector matches, including those later excluded by
   the scoreboard condition. Enforces the native fork limit.
5. Debits the original score-guard modifier cost, including when the
   candidate list is empty.
6. Looks up `@s` and the static fake-holder score **at this execution**
   through `Scoreboard.getPlayerScoreInfo`, preserving absence as an
   unsuccessful condition. No score is stored across commands or invocations.
7. Constructs the original native `ExecuteCommand` from the retained
   parsed terminal context and `ChainModifiers.DEFAULT.setForked()`.
   Delegates queue insertion to **`ContinuationTask.schedule`**.
   Native terminal callback, feedback, errors and `onReturn` tracing remain
   in Minecraft code.

Native command quotas under 1,024 use the original entire action
deliberately until the compiled path has independently demonstrated all
small-quota and queue-truncation edge cases. The compiled fast path still
charges the two original modifier debits and calls the native per-source
terminal task, which charges its own debit.

The IR ledger retains source-spanned immutable nodes:
`N` is original-action recognized plan, `C` is a successfully
generated fork entry, `J` is adjacent scoreboard JVM code.
A fork node is always **opaque to the existing direct-function scheduler**,
whether `N` or `C`; we do not fuse across it.

## Research gates

The implementation is disabled unless the **existing typed-IR namespace and
wrapper** configuration is enabled and both
`FC_TYPED_IR_NATIVE_FORK_PLAN=true` and
`FC_TYPED_IR_COMPILED_FORK=true` are set explicitly.
Disabled/default behavior retains the original actions.

Native comparison uses *three separate fresh Minecraft 26.3/Java25 JVMs*:

1. Original native: compiler wrapper disabled.
2. IR024 plan-only: typed neighbor regions, original fork barrier.
3. IR025 generated fork: typed neighbor regions and generated fork action.

One fixture corpus runs 0, 1, 2, and 4 selected sources; dynamic score
accept/reject, four-entity deferred continuation, tag changes between
consecutive commands, nearest+limit before score matching, deliberately
unadmitted near-miss source shape, and absent guard/terminal objectives.
All mode snapshots include low, intermediate and unlimited command quotas.
The CI parser rejects absent generated fork counts, missing original fallback
counts, wrong source ledger positions, or any differing scoreboard snapshot.

**Success only establishes scoped native parity** for the tested commands and
snapshots. It does **not** independently prove arbitrary modded redirect
callbacks, every score objective lifecycle edge, all entity order/identity
equivalence, tracer event-by-event parity, complete original Blastback
restoration, causal whole-event CPU savings or general production readiness.

## Follow-up gates before enabling for real workloads

- Native original-world event A/A and A/B using unchanged SHA-pinned
  Blastback publisher and identical-work witness checks; report any residual
  restoration-oracle failure honestly.
- Stronger differential tests for custom scoreboard listeners and callback
  reentrancy, exact entity identity/order, fork limit, error/result forwarding,
  frame/return and profiling.
- Uninstrumented original-host CPU measurement only after all semantic gates.
  No benchmark result can be inferred merely from replacing Brigadier calls.
- If optional runtime indexing is ever revisited, treat it as a separate
  optional backend with complete invalidation and per-execution fallback.
  IR023's demonstrated mutable `Entity.entityTags()` bypass forbids using
  the prior partial tag mutation hooks to cache membership across commands.
