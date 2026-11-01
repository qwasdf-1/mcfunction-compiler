# Correctness tests

The test matrix in `docs/v1/plans/` is the validation inventory. The runtime
harness in `scripts/run_runtime_probe.py` compares 16 direct function
fixtures against mod-free vanilla 26.3: empty, one-entry, three-entry,
two-stage execute over four tagged armor stands, nested inner/outer calls,
return value, `return run`, stored function result, `execute if function`,
nested return, vanilla and compiled-region recursion, and an in-function
gamerule change. The compiled recursion fixture asserts that fused and emitted
bytecode backends execute their regions, not just that their final state
matches. It compares
scoreboard state and RCON feedback across mod-free vanilla, wrapper-off,
wrapper-on, ScoreAdd-on, timer-only, timed ScoreAdd, fused-interpreted, and
emitted-bytecode modes. A selective injected compile-failure mode checks
fallback through original queue entries. The basic
fixtures use sequence limits 0–7; return-result,
isolated-call, nested-return, recursion, and gamerule-change fixtures use
0–16. A separate fork fixture compares zero, one, two, and four matches at
`minecraft:max_command_forks` limits 1–12. The harness also checks
wrapper/tag identity, original-function retention, and delegated versus compiled
instantiation. Server and RCON ports are
selected dynamically so other local Minecraft projects can keep their servers
running during a probe.

A fork-order fixture uses three entities and a `limit=2` selector. Nearest and
furthest sorting use scoreboard swaps to expose the selected entities and their
order: caps 1–2 execute neither branch, while caps 3–4 execute the expected two
in order. Random and arbitrary sorting check branch counts at the same caps;
caps 1–2 execute no branch, caps 3–4 execute two, and a function follow-up runs
once at every cap. These cases match mod-free vanilla in all nine Fabric
modes. Selected actor identities are not compared for random or arbitrary
ordering.

The same four sorts and fork caps 1–4 also run in all 16 arms of
`scripts/run_compatibility_probe.py`, including Bellows 1.1.2 and Bellows +
Moonrise 1.2.0 with compiler wrapper, ScoreAdd, fused, and bytecode modes.
Run `20261029T011410` matched vanilla for every recorded low-cap outcome and
had no failed pairwise compatibility comparisons. Other selector shapes and
broader selector/mod-stack combinations remain open.

The probe counts `CommandFunction.fromLines` for `quota_three`. It currently
asserts that the count is one at startup and remains unchanged through the
direct fixture calls in both Fabric modes. Reload-generation behavior is also
measured: after the lifecycle pack is enabled, the count advances once for
each of five resource reloads.

The temporary lifecycle datapack in `tests/fixtures/function_compiler_lifecycle`
checks load and tick tags, macro inline and storage arguments, colliding macro
tuple hashes with LRU churn, missing/malformed argument errors, five changed
function/tag reload generations, wrapper/tag identity, and reuse of the same
macro argument tuple across a body-changing reload. The selective-argument
probe also compares a present but wrong-typed entity value through vanilla,
compiler-off, and candidate paths, including exact nested error traces and
single-execution checks around the failure. It also copies a nested compound
containing an int array and string list through the entity-data provider, then
reads back each nested value. A malformed value from the storage provider
checks vanilla error continuation and confirms that the entity-only fast path
counter stays at zero. These cases pass three-way comparison on Lithium+Bellows
1.1.3 and Lithium+Bellows 1.1.3+Moonrise 1.2.0. A nested `data.nested` entity
path also takes the native fallback, returns the nested macro value, and keeps
the selected-path counter at zero on both stacks. These fixtures stay outside
`src/main/resources` so the tick workload does not run in the mod itself.

The harness uses scoreboard state as its semantic oracle and RCON feedback as
a secondary observation. It also compares `/debug function` output for flat
and nested functions across all ten arms (mod-free vanilla plus nine Fabric
modes), including per-command results,
fused nested error continuation, and `return fail`, `return 7`, and nested
`return run function` cases that discard pending fused regions. A separate
10-arm run adds an isolated `execute if function` child that returns failure
while a child fused tail is pending; the parent tail resumes once, score 31 and
the complete five-event trace match vanilla, and fused/bytecode each execute
one parent continuation region. A second case calls a child through `execute
store success`; it adds 1 and returns failure with a child tail pending. The
store becomes 0, the child tail is discarded, and the parent tail resumes
once. Score 32 and the exact six-event trace match vanilla in all ten arms;
fused/bytecode each execute one parent continuation region.
An `execute store result` case stores a successful child return value of 7,
discards that child's pending `+100/+100` tail, and resumes the parent's
`+10/+20` tail once. All ten arms finish at score 32 with the exact six-event
trace; fused/bytecode each execute one parent continuation region. Each arm
now compares 84 `/debug function` traces. A failed `execute store result` child
also stores 0, discards its `+100/+100` tail, and resumes the parent tail once;
all ten arms match at score 32 with the exact six-event trace, and
fused/bytecode each execute one parent continuation region. An `execute unless function` child
that returns failure takes the `+1000` branch, discards its `+100/+100` child
tail, and resumes the parent's `+10/+20` tail once; all ten arms match at
score 1032 with the exact six-event trace, and fused/bytecode each execute one
parent continuation region. Nested
`CommandSyntaxException` cases inside `return run function`, `execute if
function`, and `execute unless function` also check child continuation, callback outcome,
and parent continuation against vanilla, with sequence-limit sweeps from 0–16.
The `unless` case checks all 17 per-limit debug traces in all ten arms
(mod-free vanilla plus nine Fabric modes). A paired `execute store result/success`
case verifies that destinations remain unchanged when the child reports a
syntax error while its completed score effects persist. Its state map and
six-event trace match in all ten arms (mod-free vanilla plus nine Fabric modes).
Compatibility runs `20261029T014306` and `20261029T020726`
check these callback outcomes across all 16 vanilla, Fabric, Bellows, and
Bellows + Moonrise arms. It compares the Fabric helper-path queue/cost trace
with wrapper off and on.
The scoreboard cases cover literal set/add, absent and existing holders,
missing objectives, selector and wildcard operands, signed integer overflow,
remove/reset, objective recreation, and `execute store success`. Wildcard
target operations cover creation of the source fake holder in the target
objective; selector operations cover mixed existing/absent targets and a
disjoint two-target by two-source cross product. All nine scoreboard operation
operators are checked with present operands, absent targets, absent sources,
zero divisors, signed overflow, and a selector source containing a mix of
scored and unscored entities. The helper
trace runs at configured sequence limits 0–7; its queue starts at 0–6 because
the helper command spends one unit first. The vanilla process does not expose
per-debit instrumentation. It also checks that a valid fallback command
resumes the function and that a runtime syntax error does not suppress the
following function entry. The suite still does not cover all scoreboard edge
variants, every selector-shape/fork-limit combination, mod-specific fork
failure behavior, every callback failure path, other frame-discard triggers,
overlapping or failed-reload retention cases, or broad semantic execution with
compatibility mods and every optimized backend. Keep those cases open before
enabling optimized paths.

`scripts/run_compatibility_probe.py` defaults to 16 vanilla, Fabric, ScoreAdd,
fused, bytecode, Bellows 1.1.2, and Bellows + Moonrise 1.2.0 arms using
disposable worlds. Fabric arms also load a test namespace with the unknown `fc_probe_leaf`
command and `CustomCommandExecutor` `fc_probe_control_flow` fixtures (`CTRL-008`).
Its functions check stored result, single invocation, and eligible ScoreAdd
regions before and after the modded commands in compiler-off, wrapper, ScoreAdd,
fused, and bytecode modes, verifying that continuing and frame-discarding custom
mod commands execute cleanly without double execution. The runner checks
positive-tag selectors with spatial boxes, nearest/furthest limits and
order-sensitive effects; entity data modify/merge/remove; Bellows' entity-tag
index after NBT tag writes; and literal/fused ScoreAdd state and feedback. The
Bellows adapter restores the verified mob `home_pos` results to vanilla
behavior.
Run it with the pinned offline Gradle cache:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_compatibility_probe.py
```

These are focused checks, not full support for every mod stack. See
[`docs/research/bellows-audit.md`](../docs/research/bellows-audit.md) and the
P0 compatibility rows in the test matrix.

`tests/runtime/player_bot.py` contains a project-owned minimal protocol client
for offline 26.3 profiling servers. `scripts/run_spawn_animations_profile.py`
generates its packet-ID report from the exact server jar and drives the pinned
real-world datapack with headless players. The profile runner is separate from
the semantic correctness harness; it does not establish compiler correctness.

The shared paired-analysis helper has unit coverage for exact interval
confidence, screening-only decisions, threshold classification, and paired
percent changes. Run it with:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```
