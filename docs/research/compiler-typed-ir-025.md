# COMPILER-IR-025 — Generated native-selector fork execution

**Status (2026-11-21): ACCEPTED — research-only generated JVM fork-execution path.**
Two complete independently booted three-JVM (native / plan-only / compiled)
semantic matrices passed all **144/144 full scoreboard snapshots per arm**,
including actual original Scoreboard listener reentrancy and nested queued
callbacks, alongside **all four default-off native IR016–019 regressions**.
No production flags changed, no selector index, no cached entity membership,
no causal speedup or original Blastback complete-restoration claim. The original
native selector and continuation are reused. Branch `work/compiler-coverage`;
PR #10 remains draft/unmerged. All IR025 workflows archived manual-only.
`compiler-typed-ir-024.md` is the predecessor classifier-only milestone.

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

Nine original-source fixture cases cover 0, 1, 2 and 4 selected sources,
dynamic score accept/reject, four-entity deferred continuation, tag changes
between successive selectors, nearest+limit selection **before** the score
comparison, a deliberately unadmitted near-miss source shape, absent guard or
terminal objectives, and an actual reentrant native scoreboard listener. The
listener queues `fc_ir:ir014_inject_first`, which queues
`fc_ir:ir014_inject_second`; the fixture captures both intermediate and
post-injection score values. The live same-queue callback ordering is compared
against the original native reference, not a simulated callback.

The suite checks each case at **16 quota settings** (unlimited and 15 finite
quotas from 1 through 1,024), for **144 full-state snapshots per JVM arm**.
The compiled path is allowed only with an available quota of at least 1,024;
below that it executes the original command before any compiled effects.
The CI parser rejects absent generated fork counts, missing original fallback
counts, wrong source ledger positions, or any differing scoreboard snapshot.

**Success only establishes scoped native parity** for the tested commands and
snapshots. It does **not** independently prove arbitrary modded redirect
callbacks, every score objective lifecycle edge, all entity order/identity
equivalence, tracer event-by-event parity, complete original Blastback
restoration, causal whole-event CPU savings or general production readiness.

## Accepted native execution and independent replication

The initial three-JVM native-versus-compiled experiment
[GitHub Actions #44871911105, first successful attempt](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44871911105)
accepted **128/128** original scoreboard snapshots per arm before adding the
scoreboard-listener reentrancy case. This verified actual generated execution
rather than mere IR admission: 9 emitted fork sites, 7 executed compiled forks,
7 native selector scans, 11 selected candidates, 8 passing score guards,
4 native continuation schedules, and 74 deliberate original fallbacks.

The expanded **nine-fixture** study completed twice from fresh JVM servers:
[First expanded three-JVM matrix #44872225786](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44872225786/attempts/1)
([original evidence artifact #14693679094](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44872225786/artifacts/14693679094))
and [independent three-JVM rerun, attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44872225786/attempts/2)
([replication evidence #14694645772](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44872225786/artifacts/14694645772)).
Both passed all authored original gameplay-state, compiled-admission, native
quota, feedback and research diagnostics. Every arm is a separately
booted Java25/Minecraft26.3 server with a new forced-loaded world and
same-queue marker summon/select/kill readiness check before running fixtures.

| Actual native result | First expanded matrix | Independent replication |
| --- | ---: | ---: |
| Native source-mode full scoreboard snapshots | **144/144** | **144/144** |
| Plan-only source-mode snapshots against vanilla | **144/144** | **144/144** |
| Generated compiled fork-mode snapshots against vanilla | **144/144** | **144/144** |
| Emitted compiled fork sites | 10 | 10 |
| Compiled fork executions (not fallback) | 8 | 8 |
| Original `EntitySelector.findEntities` calls on fast path | 8 | 8 |
| Native selected source results | 12 | 12 |
| Per-entity score comparison matches | 9 | 9 |
| Native `ContinuationTask.schedule` calls | 5 | 5 |
| Original `BuildContexts.Unbound` action fallbacks | 83 | 83 |
| Original fork-limit violations or selector exceptions in compiled path | 0 | 0 |
| Production opt-in or causal speedup | **None** | **None** |

The original listener test witnessed the expected `#ir014_inner_seen=9`,
`#ir014_marker=11`, `#observed=11` scoreboard states in all three modes;
that verifies the two-level queue-inserted callback **for this fixture**.
Fallback counts reflect low quotas and unsupported/missing objective states;
they do **not** mean 83 completed executions took the fast compiled path.
The fixed authoring objective and deterministic fixture do not establish a
workload-equalized original-Blastback A/B CPU result.

The [default-off post-compiler native regression matrix #44872090155](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44872090155)
also passed all four independent suites after the compiled fork classes and
IR changes were installed:

| Existing suite | Original vanilla state parity |
| --- | ---: |
| IR016 source-positioned mixed typed regions and opaque controls | 126/126 |
| IR017 score guard and binary/ranged operations | 168/168 |
| IR018 dynamic entity source, `@s` and native barriers | 87/87 |
| IR019 native conditional function dispatch and callbacks | 84/84 |

Those backward-compatibility checks do not prove zero overhead of installed
but disabled code. The native mapped API inventory
[GitHub Actions #44871381290](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44871381290)
was accepted before runtime implementation, and the original source, mapped
method disassembly and artifact contracts are retained as research evidence.

**Disposition:** The first generated compiler fork backend is admitted as a
**research-only functional prototype**, not a production feature. It removes
Brigadier redirect/context-copy processing for the allowlisted shape when the
guard passes, while delegating entity selection, native terminal effects and
continuation scheduling to Minecraft's original implementations. No
persistent entity index is used. The original runtime fallback is retained at
every site, and the direct scheduler remains conservatively ineligible.
All three IR025 research workflows are manual-only after acceptance.
Draft PR #10 remains unmerged.

## Follow-up gates before enabling for real workloads

- Native original-world event A/A and A/B using unchanged SHA-pinned
  Blastback publisher and identical-work witness checks; report any residual
  restoration-oracle failure honestly.
- Stronger differential tests **beyond the accepted two-level native
  scoreboard-listener reentrancy fixture**: arbitrary custom listener
  behavior, exact entity UUID/order, triggered fork-limit errors, error/result
  forwarding, frame/return, and per-event tracer/profiler parity.
- Uninstrumented original-host CPU measurement only after all semantic gates.
  No benchmark result can be inferred merely from replacing Brigadier calls.
- If optional runtime indexing is ever revisited, treat it as a separate
  optional backend with complete invalidation and per-execution fallback.
  IR023's demonstrated mutable `Entity.entityTags()` bypass forbids using
  the prior partial tag mutation hooks to cache membership across commands.
