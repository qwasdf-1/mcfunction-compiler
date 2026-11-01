# Verification workflow

This project adapts a bounded evidence loop from the workspace's Pokémon
Platform and Luminary projects. Their runtime-specific commands, Engineering
Auditor versions, baselines, and release gates do not apply here. The compiler
uses the following project-specific loop.

## Work loop

1. **Explore the risk surface.** Read the relevant project references and exact
   target source once; inspect existing code, tests, Mixin hooks, and mod
   interception points before adding another path.
2. **State the behavior claim.** Identify the vanilla behavior at risk, target
   build, ownership boundary, likely compatibility impact, required docs, and
   completion evidence. Ask when command semantics or the acceptable behavior
   remain ambiguous.
3. **Choose the oracle before the change.** Specify a deterministic vanilla
   comparison, a focused unit or integration case, quota/trace checks, and a
   rollback or fallback path. Record open design branches as open decisions.
4. **Make a coherent, reversible change.** Keep the original parsed action and
   vanilla execution available. Do not replay already completed side effects.
5. **Verify the narrow contract first.** Run focused deterministic checks for
   the changed risk surface. Then run target-matched integration checks when
   the runtime hook, reload lifecycle, command context, or world behavior is
   involved.
6. **Measure only after parity.** Benchmarks are a separate evidence step. Pin
   the workload and environment, include warm/cold behavior and allocation or
   reload costs where relevant, and report uncertainty and regressions.
7. **Review and record.** Review the final diff and, when configured, run the
   scoped Engineering Auditor review early enough to resolve findings and
   again at pass close. Update the focused reference and test matrix, record
   exact build/tool fingerprints and results, and leave failed or unrun required
   checks visible. Fix defects in the touched boundary or give each deferred
   issue a concrete next action.

Keep heavy builds and server runs sequential when concurrent work would corrupt
their evidence. Reuse completed evidence only for an unchanged configuration
and risk surface.

## Testing evidence

Each layer answers a different question:

| Evidence | What it can establish | What it cannot establish alone |
|---|---|---|
| Static/source inspection | A symbol, branch, call path, or bytecode fact exists in a pinned artifact. | Runtime parity, successful integration, or speedup. |
| Unit tests | The tested helper or IR rule behaves for its fixtures. | Vanilla command behavior or full scheduler parity. |
| Differential/golden tests | The selected observable behavior matches a vanilla reference for the recorded cases. | Coverage for untested commands, contexts, quotas, mods, or targets. |
| Runtime integration checks | Hook, reload, tags, frames, callbacks, tracing, and server lifecycle work for the tested setup. | Compatibility with untested versions or mod sets. |
| Benchmarks | Performance for the measured workload and environment after correctness checks. | Correctness, general datapack speedup, or unmeasured workloads. |
| Engineering Auditor (EA) | Findings from the pinned auditor's supported static review profile. | Command semantics, runtime safety, test coverage, or unsupported-language correctness. |

The vanilla differential harness and small-quota cases are the primary semantic
oracles. Assert in-world state and engine callbacks/results; RCON or console
text alone is insufficient. Preserve minimized failing fixtures and record
whether a failure came from the game, adapter, harness, or build setup.

For an optimization, vanilla 26.3's observable behavior is the reference for
the supported command/context: effects, results, callbacks, errors, tracing,
quota stops, and reload behavior must match. Also run the same mod stack with
the optimization disabled and enabled to catch bypassed hooks and integration
regressions. If the mod itself differs from vanilla, record that difference and
resolve a reviewed adapter/compatibility policy; do not silently redefine the
vanilla behavior contract based on the mod's output. Keep the optimization
disabled for any unverified path.

The test matrix's status is per case. A passing subset does not close its whole
phase or establish production readiness. Keep the exact Minecraft build,
datapack, mod list, JVM settings, and observation method with the result.

## Engineering Auditor policy

EA is an additional static-review signal, separate from correctness tests and
runtime qualification.

- The project uses the shared Engineering Auditor v1.5.0 worktree at commit
  `d014177acf6b3c3cefc425252229d81fbea62150`. Run the pinned report-only
  review with `bash scripts/run_ea_review.sh`; it verifies both version and
  commit and writes its machine report under ignored build output.
- The current invocation uses EA's `gating` detector profile as an inventory,
  not the `gate` command. There is no project baseline, no detector
  suppression, and no pass/fail threshold. Findings require human review.
- Confirm scan coverage for Java, Gradle/Groovy, Mixins, resources, and test
  code before widening this into a gate. EA recognizes Java and several
  documentation/tooling formats here, but it does not replace review of
  Minecraft method contracts, mixin injection points, `.mcfunction` behavior,
  or unsupported build/resource formats.
- Until those limits and the individual findings are resolved, describe EA
  output as an advisory review; do not claim an EA gate or a clean audit.
- For a configured implementation pass, run the scoped review early enough to
  fix findings and again at pass close. Do not accept open required findings as
  a pass.
- Resolve each production finding or record an individual disposition tied to
  the affected source, evidence, and residual risk. Do not use blanket
  suppression, a project-wide baseline, or an automatic retained-debt ratchet
  to conceal unresolved findings.
- Do not copy the pinned EA version or gate command from another repository.
  Adopt a project-specific pin and invocation only after tool support and
  reproducibility are verified.

The first pinned report-only scan and individual finding review are recorded in
[`research/engineering-auditor-review-2026-10-29.md`](research/engineering-auditor-review-2026-10-29.md).
The report identifies maintainability and structure work; it did not establish
Minecraft command correctness or full language coverage.

## Current prototype commands

The pinned development toolchain and target are in
[`research/toolchain.lock`](research/toolchain.lock). With Java 25 available:

```sh
./gradlew build
python3 -m unittest discover -s tests -p 'test_*.py'
GRADLE_USER_HOME="$PWD/.gradle-user-home" \
GRADLE_RO_DEP_CACHE="$HOME/.gradle/caches" \
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py \
  --whole-resource-reload-failure
```

The full probe runs nine Fabric modes (wrapper-off, wrapper-on, ScoreAdd-on,
instrument-only, timed ScoreAdd, fused-interpreted, emitted-bytecode,
bytecode-compile-failure, and selective-macro-arguments) plus the mod-free,
fingerprinted official Minecraft 26.3 server. The compile-failure mode injects
backend compilation failures and checks fallback to the original queue entries.
It compares direct `/function` state and RCON feedback for 16 fixtures,
including nested returns, bounded recursion through
compiled regions, and changing the
sequence-limit game rule during execution. It sweeps zero, one, two, and four
matching entities across fork limits 1–12. A four-actor overflow function also
checks that no partial branch effects leak through a failed fork expansion and
that the following queued command executes exactly once. A separate sequence
limit sweep of a four-target `execute` followed by a function command matches
vanilla at limits 0–16; the later entry stays stopped through limit 7 and
executes at limit 8 in all nine Fabric modes and vanilla. It also runs an isolated lifecycle
datapack that checks `#minecraft:load`, `#minecraft:tick`, macro arguments, five
changed function/tag reload generations, and an ordinary function's removal
and re-addition. Fabric diagnostics verify wrapper/tag identity, parse counts,
and the per-function ScoreAdd count across removal/re-addition; the mod-free
vanilla arm verifies the same observable outcomes. An earlier full eight-arm
run changed `macro_add` during the first reload and reused the same inline
argument tuple (`amount:37`) before and after. Its marker changed from 1 to 10 in vanilla and every
Fabric arm; all five macro-specializing modes recorded a new compilation count
(13 to 14).
The held-reload submatrix also includes the selective argument candidate with
vanilla and same-stack compiler-off. While preparation is blocked, the macro
returns score 37 with old marker 10 and the selected-path counter advances
once; after publication, the new marker 303 appears and the counter advances
once again. The combined concurrent and failed-reload command is:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py \
  --modes mod-free-vanilla wrapper-off wrapper-on score-add-on \
  instrument-only score-add-timed fused-interpreted bytecode-emitted \
  bytecode-compile-failure selective-macro-arguments \
  --concurrent-resource-reload \
  --whole-resource-reload-failure
```

The gate holds request A after preparing generation A while B, C, D, E, and F
publish. B produces (direct=404, probe_v2=808, tag=404, macro marker=404); C
produces (direct=505, probe_v2=909, tag=909, macro marker=505); D produces
(direct=606, probe_v2=1010, tag=606, macro marker=606); E produces
(direct=707, probe_v2=1111, tag=1111, macro marker=707); F produces
(direct=808, probe_v2=1212, tag=808, macro marker=808). Releasing A then
publishes its prepared generation last (direct=303, probe_v2=707, tag=707,
macro marker=303). Mod-free vanilla reloads B through F, then A sequentially
as the reference. In all nine Fabric runtime modes the load tag advances once for
each of the six publications, every intermediate and final state matches
vanilla, and macro specialization counters increase by six in each applicable
mode. In the full run the load count advances from 10 to 16. The forced
whole-resource failure after A publishes retains the same direct, tag, and
macro state. The selective-macro-arguments mode is included: its selected-path
counter advances after each of B through F, A, and the failed reload while the
published macro remains at marker 303. The full report is
`build/reports/runtime-probe/concurrent-resource-reload-results.json`.
Seven-or-more-request interleavings and other macro failure shapes remain open.

The forced whole-resource failure stages a macro body with marker 909. The old
published macro remains at score 37/marker 303, and the selective argument path
runs once after failure. The same three arms match for the old and new
generations. A normal reload that omits both a malformed ordinary function
and an unterminated macro template, while keeping the valid datapack and macro
callable, matches vanilla in all nine Fabric runtime modes. The whole-resource
reload failure is also covered. The six-request overlap stages B, C, D, E, and
F while A is held, confirms each publication, then releases A and confirms A
publishes last, matching vanilla in all nine Fabric runtime modes. The report is
`build/reports/runtime-probe/concurrent-resource-reload-results.json`.
Seven-or-more-request interleavings and macro failure shapes beyond the staged
body plus selective-argument path remain open. For
bytecode-emitted, the 25-cycle failure-retention run generated 17,816 bytes of
class output during the failed reload; after GC the live class count remained
17, the loader identity stayed 327177752, and metaspace grew 20,808 bytes. An
updated rerun across the expanded 88-trace suite retained 38 live classes across
all 29 cycles, classloader identity 327177752, metaspace peak growth 983,088
bytes (~0.94 MiB), and emitted 39,715 class bytes during reload failure with
zero retained classes post-GC and 16,304 bytes metaspace delta. The report is
`build/reports/runtime-probe/whole-resource-reload-failure-results.json`.
Repeat the bytecode failure-retention case with:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py \
  --modes mod-free-vanilla bytecode-emitted --reload-cycles 25 \
  --whole-resource-reload-failure
```

The separate general eight-mode failure run logs
`Reload failed; keeping old data`, keeps the prior function library and tag
state, and does not publish changed resources or the new
function. The ScoreAdd-on, both timing arms,
fused-interpreted, and emitted-bytecode also run the full fixture suite and check state,
feedback, quota, lifecycle, callback, and
trace parity. The instrument-only timer delegates to vanilla; timed ScoreAdd
runs the disabled prototype. Exact `/debug function` traces for flat, nested,
fused error/continuation, nested fused-region, and `return fail`, `return 7`,
and nested `return run function` frame-discard fixtures match in the full ten
arms (mod-free vanilla plus nine Fabric modes). That run also matches exact
vanilla traces for a stored function result, successful and failing
`execute if/unless function` callbacks, and `return run`. Nested
`CommandSyntaxException` probes also match
exactly: a `return run function` child continues after its error while the
parent's trailing command is discarded; an errored `execute if function` call
preserves child side effects, evaluates false, and allows the outer following
command; and an errored `execute unless function` takes the inverted branch and
reaches score 14. The `unless` sequence-limit map and all 17 per-limit debug
traces match in vanilla and all nine Fabric modes; its state map and high-quota
trace also match across all 16 compatibility arms in run `20261029T014306`.
Paired `execute store result/success` calls preserve child score effects but
leave both seeded destinations unchanged after the nested syntax error. Its
0–16 state map and six-event trace match in the ten-arm runtime matrix and all
16 compatibility arms in run `20261029T020726`. The `return run function` and
`execute if function` maps remain `0,0,1,1,1,3…` and `0,0,0,0,2,3…`. The Fabric and vanilla probe servers use matching 2 GB heaps;
the Gradle daemon is capped at 1 GB. These values are recorded in the report.

CTRL-007 now includes isolated-call failures with pending fused tails. In the
`execute if function` case, the child adds 1, returns failure, and has an
adjacent `+100/+100` tail; its failed result skips the parent's conditional
`+1000`, while the parent's following `+10/+20` tail runs exactly once. State
31 and the five-event `/debug function` trace match byte-for-byte in mod-free
vanilla and all nine Fabric modes. In the `execute store success` case, a
parent seeded with success value 1 calls a child that adds 1, returns failure,
and has the same pending tail. The child tail is discarded, the stored success
becomes 0, and the parent's `+10/+20` tail runs once; state 32 and the exact
six-event trace match vanilla in all ten arms. Fused-interpreted and
emitted-bytecode each record exactly one executed region for the parent
continuation in both cases. The results are in
`build/reports/runtime-probe/results.json`.

The paired `execute store result` case seeds its destination to `-1`, calls a
child that adds 1 and returns 7 with a pending `+100/+100` tail, then resumes
the parent's `+10/+20` tail. The return value is stored as 7, the child tail is
discarded, and the final score is 32. The exact six-event trace matches vanilla
in all ten arms; fused-interpreted and emitted-bytecode each execute one parent
continuation region. That earlier full run compared 84 `/debug function` traces
per arm.

The paired failed `execute store result` case seeds its destination to `-1`
and calls a child that adds 1, returns failure, and has a pending `+100/+100`
tail. The callback stores 0, discards the child's tail, and resumes the parent
tail once at score 32. All ten arms match the exact six-event vanilla trace;
fused-interpreted and emitted-bytecode each execute one parent continuation
region.

The paired successful `execute store success` case seeds its destination to 1,
then calls a child that adds 1, returns 7, and has a pending `+100/+100` tail.
The command's success flag is 1, the child's pending tail is discarded, and
the parent's `+10/+20` continuation runs once at score 32. All ten arms match
the exact six-event vanilla trace; fused and bytecode each execute one parent
continuation region. This checks that `execute store success` records command
success independently of the child's numeric return value.

The nested result propagation case tests an `execute store result` caller
invoking a wrapper that uses `return run function` to call a child that adds 4,
returns 7, and has a pending `+100/+100` tail; the wrapper had added 2 before
`return run` and also has a pending `+100/+100` tail. Stored result receives 7,
both pending tails are discarded, and the parent's `+10/+20` continuation runs
once at final score 37. All ten arms match the exact eight-event vanilla trace;
fused-interpreted and emitted-bytecode each execute one parent continuation
region.

Paired nested `execute store success` cases test the same wrapper/child
continuation structure under `execute store success`. When the child returns 7,
the stored success flag is 1; when the child returns failure, the stored success
flag is 0. In both cases, both pending `+100/+100` tails are discarded, and the
parent's `+10/+20` continuation runs once at final score 37. All ten arms match
the exact eight-event vanilla traces, and fused-interpreted and emitted-bytecode
each execute one parent continuation region per case. The full run compares 88
`/debug function` traces per arm; report:
`build/reports/runtime-probe/results.json`.

The `execute unless function` return-failure case covers the inverse branch
outcome: the child adds 1 and returns failure, so the `+1000` branch runs; the
child's pending `+100/+100` tail is discarded and the parent's `+10/+20` tail
runs once. All ten arms reach score 1032 with the exact six-event trace, and
fused-interpreted/emitted-bytecode each execute one parent continuation region.
That earlier run compared 84 `/debug function` traces per arm.

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py \
  --modes mod-free-vanilla wrapper-off wrapper-on score-add-on \
  instrument-only score-add-timed fused-interpreted bytecode-emitted \
  bytecode-compile-failure selective-macro-arguments
```

The helper-path queue/cost trace
matches wrapper-off/on at configured sequence limits 0–7. The custom helper
spends one unit before entering the function queue, so observed queue-start
values range from 0–6; queue yields and completions are separate events. The
suite also compares scoreboard set/add, selectors/wildcards, integer bounds,
remove/reset, objective recreation, and `execute store success`. It asserts that
removing from an absent score creates -4, an absent operation source is created
at 0 without changing its target, and a missing-objective compiled add stores
success/result 0 before the function continues. It also checks operation into
an absent target and an operation applied to four selected targets. Pure vanilla
still does not expose per-debit events. `FC_GRADLE_OFFLINE=true`
keeps the Gradle server launches on cached dependencies. Fabric classes, logs, and worlds
are written under ignored `build/` and `run/`; the vanilla world is created in a
temporary directory and removed automatically. Capture durable findings in
maintained research notes, then remove stale generated output when the
investigation is complete.

For the selector, Bellows NBT, and nested-callback compatibility matrix, run:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_compatibility_probe.py
```

The default matrix starts 21 clean arms: vanilla; five Fabric arms (wrapper-off,
wrapper-on, ScoreAdd, fused, bytecode); five Bellows 1.1.2 arms; five
Bellows 1.1.2+Moonrise 1.2.0 arms; and five Lithium+Bellows 1.1.3+Moonrise
1.2.0 arms. It verifies selected identities
and order-sensitive effects for positive-tag AABB cases, distance filters,
score filters combined with AABBs, positive/negative tag constraints, and
nearest/furthest limited ordering. It also checks ordinary entity NBT updates,
Bellows tag-index maintenance, and the compiled literal ScoreAdd entry.
Compiler-off/on pairs match. For mob `home_pos`, the probe asserts vanilla's
exact init/merge/modify/remove values and checks that all Bellows profiles
match them. Separate `home_radius` cases check modification, removal, and the
corresponding `home_pos` state across all tested arms. The adapter covers the
filtered modify/remove helper; Bellows' merge path falls back to vanilla when
its filtered setter declines. These focused cases do not close the broader
Bellows selector or filtered-NBT matrix. The default matrix also tests nested
syntax errors through `execute unless function` and paired
`execute store result/success` calls. Their 0–16 state maps and high-quota
traces match across all 16 arms in runs `20261029T014306` and
`20261029T020726`. To run only the Bellows+Moonrise extension, use:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_compatibility_probe.py --modes \
  vanilla bellows-moonrise120-off bellows-moonrise120-on \
  bellows-moonrise120-score-add-on bellows-moonrise120-fused-interpreted \
  bellows-moonrise120-bytecode-emitted
```

The selected run `20261028T151204` passed all six arms. It compares vanilla
with Bellows 1.1.2 + Moonrise 1.2.0 wrapper-off/on, ScoreAdd, fused, and
bytecode. A separate five-arm bytecode extension also covers vanilla, Fabric
wrapper-off/bytecode, and Bellows wrapper-off/bytecode. These focused runs add
backend and mod-stack evidence; they do not close untested selector or filtered
NBT shapes.

The full default run `20261028T152121` passed all 16 arms. It found no failed
pairwise compiler-off/on comparisons and no vanilla parity mismatch for the
selected Bellows or Bellows + Moonrise 1.2.0 cases. The pinned Moonrise jar is
`Moonrise-Fabric-1.2.0+61c1328.jar` with SHA-256
`cb4890a8aeb61115b4b57aff3d4ec26c96ffdb4194d28fd7ed9d1365db3aa4d6`.

Each of the 15 Fabric-based arms loads a Fabric-only `fc_probe_leaf` fixture
unknown to the compiler. The focused six-arm run `20261028T151747` and the full
16-arm run both pass: the function stores the leaf's return value 7, executes
it once, and preserves a total of 15 from four eligible ScoreAdds surrounding
it. ScoreAdd executes four callbacks; fused and bytecode each execute two
regions. Vanilla is not asked to load the modded command; compiler-off Fabric
is the oracle for that leaf, while shared behavior matches the vanilla
reference.

To run only the selected Lithium+Bellows 1.1.3+Moonrise 1.2.0 extension:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_compatibility_probe.py --modes \
  vanilla fabric-off lbm113120-off lbm113120-on lbm113120-score-add-on \
  lbm113120-fused-interpreted lbm113120-bytecode-emitted
```

Run `20261029T154729` passed all seven arms and their selected vanilla and
same-stack pair checks, including selector order, entity NBT, tag-index updates,
`home_pos`/`home_radius`, and modded-leaf behavior. This is selected fixture
coverage on the pinned stack, not general support for every mod path.

For the focused macro behavior differential, run:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py --macro-only \
  --macro-modes mod-free-vanilla wrapper-off selective-macro-arguments
```

This compares mod-free vanilla, same-stack compiler-off Fabric, and the Fabric
arm that enables the selective argument prototype. It covers inline and
storage macro arguments, tuple-cache churn and collisions, missing and
malformed arguments, entity custom data, multi-parameter macros, multi-function
and ordinary-function fallbacks, block-entity provider and alternate-path
fallbacks, `/debug function` traces, and sequence quota behavior. The runner
checks the candidate against both references and records the exact mod artifact
hashes in its report.

To repeat this fixture on a pinned compatibility stack, add `--macro-stack`
with one of `fabric`, `lithium`, `bellows`, `bellows-moonrise120`, `bellows113`,
`bellows113-moonrise120`, `bellows113-moonrise`, `lm`, `lb`, `lbm120`, `lb113`,
`lbm113`, or `lbm113120`. For example:

```sh
FC_GRADLE_OFFLINE=true python3 scripts/run_runtime_probe.py --macro-only \
  --macro-modes mod-free-vanilla wrapper-off selective-macro-arguments \
  --macro-stack lb113
```

The fixture passes both vanilla and same-stack compiler-off comparisons on
Fabric, Lithium 0.26.2, Bellows 1.1.2, Bellows+Moonrise 1.2.0,
Lithium+Moonrise 1.2.1, Lithium+Bellows, and Lithium+Bellows+Moonrise 1.2.0.
The focused run `20261029T054345` adds Lithium+Bellows 1.1.3 and passes against
both mod-free vanilla and its same-stack compiler-off arm. Bellows+Moonrise
1.1.3+Moonrise 1.2.0 also passes the focused three-arm fixture in run
`20261029T070635`; vanilla, same-stack compiler-off, and selective-macro
outcomes match, with selected-call counts of 2 direct, 2 fallback, 3 debug,
and 20 in the quota sweep. A repeat on Bellows 1.1.3+Moonrise 1.2.1 fails
before the candidate runs: Bellows' `MoonriseEntityLookupMixin` expects the
missing `EntityLookup.entityById` field. The earlier Bellows 1.1.2+Moonrise
1.2.1 profile has the same startup incompatibility. The passing result
establishes fixture-level parity for the tested 1.2.0 stack, not compatibility
with every mod-provided macro path or performance by itself. The separate
randomized PERF-011 campaign provides the real-workload evidence.

The full macro-probe matrix is available with `--macro-only`; it adds the
wrapper, ScoreAdd, fused, bytecode, and timer arms to vanilla and selective
macro mode.

The default run is eight arms in total (mod-free vanilla plus seven Fabric
modes). The separate injected-failure run starts only the vanilla reference
and the forced-failure Fabric arm; it observed 30 compile failures, zero
emitted or executed bytecode regions, and successful fallback execution. A
25-cycle `--reload-cycles 25` run additionally checks generated-class retention
after GC; these extended checks are not part of every default invocation.
