# COMPILER-IR-026 — Original publisher Blastback compiled-fork native-gameplay gate

**2026-11-21: ACCEPTED only as a bounded original-publisher semantic and
execution gate.** This milestone demonstrates that IR025's actual JVM-generated
native-selector fork runs inside the **unchanged, SHA-256-pinned Blastback
Hotfix 3 (Minecraft 26.3)** datapack, at the exact original `erb:restore/job_tick`
source command, under live one-TNT world simulation. Two independent
three-JVM wall-window matrices and two independent three-JVM **600-datapack-tick**
matrices passed original named-block witnesses and job-state gates. **Do not
promote to production or claim a causal performance improvement.** The
unresolved original template-restoration oracle remains false even in the
native baseline; per-entity identity/order and exact global world state are
not established.

Branch: `work/compiler-coverage`. Draft/unmerged PR #10. Default compiler
and native game behavior remain unchanged.

## 1. Pinned original inputs and target

Only the publisher ZIP was downloaded by the existing
`scripts/ci_typed_ir015_fetch.py` Modrinth metadata path. The SHA-256 of the
download and of each separately deployed copy must be:

```text
8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90
```

Original target `data/erb/function/restore/job_tick.mcfunction`, zero-based
source line index **4** (fifth command), exactly once:

```mcfunction
execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] if score @s erb.job = #active erb.job run scoreboard players set #needs_restore erb.tmp 1
```

This source is never edited, synthesized or replaced in the original datapack.
The deterministic test-only setup pack defines the one-TNT source world and
witness blocks; it does **not** rewrite any original Blastback file.

## 2. Required compiler integration repair

The pre-IR026 `TypedScoreIR.compile` returned the original function whenever
`typedRegionCount()==0`. That could silently discard a successfully emitted
fork-only program. IR026 extends the gate to retain a compiled program when
**either** a typed-score region **or** an actual compiled fork exists;
a non-emitted recognized plan never changes the native action.

To isolate the publisher target, `FC_TYPED_IR_FUNCTION_FILTER` optionally
restricts IR compilation to the exact identifier `erb:restore/job_tick`.
Unset/empty preserves the prior namespace-wide behavior, and no feature
is enabled by default.

The two compiler-bearing arms use identical flags, differing ONLY in
`FC_TYPED_IR_COMPILED_FORK`:
- `plan_only`: `FC_TYPED_IR_MODE=bytecode`,
  `FC_TYPED_IR_NAMESPACE=erb`, exact function filter,
  `FC_TYPED_IR_NATIVE_FORK_PLAN=true`,
  `FC_TYPED_IR_COMPILED_FORK=false`;
- `compiled`: same environment, except
  `FC_TYPED_IR_COMPILED_FORK=true`.

The `native` arm has no typed compilation/wrapper. All three disable
global selector indexes, score caches, direct-function scheduling, unrelated
legacy prototypes and test-only marker mutators. This is a research pilot;
there is no production flag change.

The original function's actual IR ledger in the plan-only arm:

```text
IR016 function=erb:restore/job_tick source_lines=18 typed_lines=7 typed_regions=2 opaque_barriers=11 singleton_barriers=2 dispatch_barriers=0 native_fork_plans=1 compiled_forks=0 direct_candidate=false layout=V1:1,V2:1,V3:1,S4:1,N5:1,V6:1,V7:1,S8:1,V9:1,J10:5,V15:1,V16:1,J17:2
```

The compiled arm changes **only** `native_fork_plans=1 compiled_forks=1`
and `N5:1` to **`C5:1`** at the exact source index; `J10:5` and `J17:2`
are unchanged neighboring generated scoreboard regions. Both compiler arms
retain `direct_candidate=false`.

## 3. Original-world experiment: independent 30-second windows

The existing source/template setup plants five named block witnesses:
gold, diamond, redstone, emerald, and stone. It verifies a complete
pre-event template clone, starts exactly one original tagged TNT entity
with 160-tick fuse, proves native entity visibility, observes 30 seconds
of real Minecraft ticks and inspects the original world.

An early attempt failed **before any acceptance** when the test marker probe
executed one score-add callback per marker, flooding RCON responses
after thousands of original markers were created. The corrected probe uses
one native `execute store result score ... if entity @e[...]` operation per
marker type; no datapack, compiler, selector or world state was modified to
resolve the test-harness failure.

Both independently booted three-JVM matrices passed:

- [30-second gate run #44929587147](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44929587147/attempts/1)
  / [evidence artifact 14717380904](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44929587147/artifacts/14717380904).
- [Independent run #44929587147 attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44929587147/attempts/2)
  / [artifact 14717212710](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44929587147/artifacts/14717212710).

| Recorded outcome | 30 s: native / plan-only / compiled | Independent 30 s: native / plan-only / compiled |
| --- | --- | --- |
| Blastback tick deltas | 602 / 600 / 647 | 600 / 601 / 601 |
| Named block witnesses present | 5/5 in every arm | 5/5 in every arm |
| `#active erb.job` | 1 / 1 / 1 | 1 / 1 / 1 |
| `#needs_restore erb.tmp` | 1 / 1 / 1 | 1 / 1 / 1 |
| Original TNT detonated | yes / yes / yes | yes / yes / yes |
| Original template equal | **false / false / false** | **false / false / false** |
| `erb.block` markers | 3278 / 3274 / 3278 | 3278 / 3278 / 3278 |
| Verified markers | 3244 / 3244 / 3226 | 3245 / 3250 / 3249 |
| Eligible markers | 34 / 30 / 52 | 33 / 28 / 29 |
| Generated fork executed fast path | — / 0 / **1,237** | — / 0 / **1,243** |
| Original selected native sources on fast path | — / 0 / **322,617** | — / 0 / **320,711** |

The compiled arm executed the original selector at the original source
position, without any fast-path original fallback, across more than 1,200
actual original function entries. But equal wall time produced unequal
tick exposures in the first matrix, so **these are descriptive snapshots,
not an identical-work CPU comparison**. Marker counts varied across native
and plan-only controls too; no exact equivalence is inferred.

## 4. Same-work follow-up: 600 original datapack ticks per arm

`scripts/ci_typed_ir026_tick_matched.py` confirms the TNT actor,
reads `#tick_id erb.cfg`, then stops each arm independently when that
score has advanced 600 ticks. The recorded timing jitter is at most a few
ticks; the snapshot query spans are bounded. All one-TNT sources and scene
setup are unchanged. It checks original block/template witnesses and
fake-holder job/restore flags for equality, confirms real compiled selector
scans and compares marker populations with a **2% exploratory guard**.
That percentage is a threshold for rejecting obviously incomparable
populations—not a proof that all markers are identical.

Both fresh, independent three-JVM matrices were accepted:

- [Matched-tick run #44930178901 attempt 1](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44930178901/attempts/1)
  / [evidence 14716844515](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44930178901/artifacts/14716844515).
- [Independent attempt 2](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44930178901/attempts/2)
  / [evidence 14717302154](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44930178901/artifacts/14717302154).

| Recorded outcome | 600 ticks A: native / plan-only / compiled | 600 ticks B: native / plan-only / compiled |
| --- | --- | --- |
| Actual stopped tick deltas | 601 / 602 / 600 | 602 / 600 / 601 |
| `erb.block` markers | 3278 / 3276 / 3278 | 3278 / 3278 / 3278 |
| Verified markers | 3254 / 3250 / 3242 | 3250 / 3256 / 3250 |
| Eligible markers | 24 / 26 / 36 | 28 / 22 / 28 |
| Job/restore fake-holder flags | **1/1 in every arm** | **1/1 in every arm** |
| Named block witnesses | 5/5 in every arm | 5/5 in every arm |
| Original full template equal | **false in every arm** | **false in every arm** |
| Compiled original fork executions | — / 0 / **1,244** | — / 0 / **1,245** |
| Compiled original selected native sources | — / 0 / **324,181** | — / 0 / **320,791** |

All arms independently satisfied the native tag-population invariant
`erb.block = erb.verified + erb.block,!erb.verified`. In the second
matched-tick experiment the compiled and native modes had exactly the
same aggregate `3278 / 3250 / 28` marker counts, while plan-only
differed by six in verified/eligible membership. This is compelling
bounded aggregate-state agreement, **not** proof of equality of per-entity
identity/ordering, every world block, feedback or all modded callbacks.

## 5. Prior compiler regression protection

The post-IR026 exact-function source changes and original publisher harness
were followed by a new
[default-off native regression matrix #44930538399](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/44930538399):

| Legacy acceptance suite | Native state parity |
| --- | ---: |
| IR016 source-positioned mixed typed/opaque IR | 126/126 observations |
| IR017 score guards and binary operations | 168/168 observations |
| IR018 dynamic self/source and native command barriers | 87/87 observations |
| IR019 native dispatch and callbacks | 84/84 observations |

All four jobs passed. These suites remain disabled by default and
check the previous native behaviors; they do not claim zero installed-code
overhead under an enabled compiler.

## 6. Decision and STOP gates

**PASS:** Original pinned selector `C5:1` actually executes; original
TNT detonates; all five named world witnesses remain; original job/restore
state flags agree; native tag accounting holds; two independent same-tick
matrices reproduce approximate marker population agreement; all four legacy
regressions are green.

**HOLD:** Production promotion, exact-world equivalence, speedup claims
and any general cached-membership backend. Original `template_equal=false`
in every native run, and differences in verified/eligible marker counts
persist in some comparisons, including the plan-only control. Exact world
restoration, full job completion, entity identity/order and all native
callback/error/trace corner cases have NOT been proved.

**Next work:** Resolve or scope the pre-existing original restoration oracle,
establish an independently justified work-equivalence check beyond
aggregate counts, and only then perform an **uninstrumented same-work**
CPU A/A placebo and A/B experiment. Never equate a 30-second wall-window
TPS difference to causal acceleration. No compiler or runtime entity index
should be promoted on the basis of this milestone.

All IR026 research workflows are archived **manual-only** after acceptance.
The branch remains `work/compiler-coverage`; draft PR #10 is unmerged.
