# Current state

The repository is a research-transition codebase for a Minecraft 26.3 Fabric
server-side function compiler. It includes opt-in wrappers, selective macro
argument handling, fused interpreted prototype regions, and an opt-in ASM
bytecode backend. Defaults and promotions must track the measured evidence in
`docs/research/implementation-audit-2026-11.md`, not broad campaign claims.

Selective macro extraction is the only optimization with real-event confirmatory
parity and performance promotion evidence (-22.34% on Fabric, -22.06% on
Lithium; Belows is supported but less stable). Fused region prototype code is
present and a 2026-11-03 static screen found adjacent candidate runs in pinned
packs, but no candidate has runtime-confirmed specialization or a measured
real-world gain; it remains disabled by default. Tiered bytecode is present but
opt-in; the bounded reload and Metaspace evidence only supports continued
experimentation, not blanket production claims.

## Verified

- The official Minecraft 26.3 server artifact and Loom-produced classfiles are
  fingerprinted in [source-versions.lock](research/source-versions.lock).
- Exact class inspection records queue checks, quota debits and callers,
  function construction, reload, tag, macro, and debug paths in
  [26.3-internals.md](research/26.3-internals.md).
- The project is pinned to Minecraft 26.3, Java 25, Fabric Loader 0.20.1,
  Fabric API 0.165.0+26.3, Fabric Loom 1.18.4, and Gradle 9.7.1. The dedicated
  development server starts with this combination.
- compileJava succeeds. The runtime probe launches separate wrapper-off and
  wrapper-on servers with the project mod and datapack fixture, then starts
  the fingerprinted official Minecraft 26.3 server with the same fixture.
- In both modes, the fixture is found in its custom function tag. With the
  wrapper enabled, tag lookup returns the same wrapper instance as direct
  function lookup, and wrapper instantiation delegates to the original
  PlainTextFunction result.
- For the same direct `/function` command, mod-free vanilla and nine Fabric modes (wrapper-off, wrapper-on, ScoreAdd-on,
  instrument-only, timed ScoreAdd, fused-interpreted, emitted-bytecode,
  bytecode-compile-failure, and selective-macro-arguments)
  return the same RCON feedback and scoreboard state for 16
  fixtures: empty, one-entry, three-entry, two-stage/four-source execute,
  nested calls, return value, `return run`, stored function result,
  `execute if function`, nested return, vanilla and compiled-region recursion,
  and a function that changes
  its active sequence limit. The first eight use sequence limits 0–7; the
  longer return, isolated-call, nested-return, recursive, and rule-change
  fixtures use 0–16.
- The disabled emitted-bytecode prototype passes the selected runtime suite
  against the official 26.3 vanilla reference. This run covers all 16 direct
  function fixtures, fork limits 1–12, scoreboard edge and fallback cases,
  function and macro lifecycle, five reload generations plus function
  removal/re-addition, and flat/nested debug traces. ASM emits hidden nestmate
  classes with bounded 256-command methods and calls the same command bridge as
  the interpreted region. Exact 26.3 inspection confirmed that
  `UnboundEntryAction.execute` erases its first argument to `Object`; the
  emitted bridge uses that descriptor. A separate injected-failure run forced
  30 region-compilation failures: zero bytecode regions were emitted or run,
  the original queue entries remained callable, and the ScoreAdd fallback
  continued to execute. This verifies fallback for the injected compiler
  failure path, not arbitrary VM linkage or verifier failures.
- A six-arm modded-command run compares vanilla, Fabric wrapper-off/on,
  ScoreAdd, fused, and bytecode. A Fabric-only unknown command runs once,
  `execute store result` captures its return value 7, and four surrounding
  eligible ScoreAdds produce the expected total 15. ScoreAdd reports four
  executed callbacks; fused and bytecode each report two executed regions
  around the unrecognized command. All same-stack semantic comparisons pass.
- A 25-cycle bytecode reload run passed with changed function bodies and tag
  membership followed by removal and re-addition. After each explicit GC, the
  bytecode arm retained the same 15 live generated classes and the same
  defining classloader identity. Metaspace rose from 121,166,816 to a maximum
  of 122,245,624 bytes (about 1.03 MiB), below the test's 16 MiB guard. The
  bytecode arm's median reload completion was 169.7 ms, versus 164.0 ms for
  wrapper-off and 153.6 ms for vanilla. This is bounded evidence for this
  fixture and JVM. A 25-cycle run followed by an injected failed reload emitted
  17,816 additional bytecode class bytes but retained the same 17 live classes
  after GC, kept classloader identity 327177752, and grew metaspace by 20,808
  bytes. An updated 2026-10-30 rerun across the full 88-trace fixture set confirmed
  identical lifecycle stability: exactly 38 live generated classes retained
  across all 29 reload cycles, stable classloader identity 327177752, metaspace
  growth bounded at 983,088 bytes (~0.94 MiB), medians 173.1 ms bytecode,
  172.0 ms wrapper-off, and 141.6 ms vanilla, and an injected whole-resource reload
  failure that emitted 39,715 class bytes with zero leaked classes post-GC and
  16,304 bytes metaspace delta (`build/reports/runtime-probe/whole-resource-reload-failure-results.json`).
  A six-request overlap gate now passes in all nine Fabric runtime modes:
  generation A is held while B, C, D, E, and F publish in order; A publishes
  last after release. In the full run, the load tag advances from 10 to 16;
  each intermediate/final generation matches vanilla. All six macro-specializing
  modes record six corresponding specialization updates. The candidate's
  selected-path counter advances at each publication, including F (31→32), and
  after the forced failure while retaining marker 303. The report is
  `build/reports/runtime-probe/concurrent-resource-reload-results.json`.
  Seven-or-more-request interleavings and other macro failure shapes remain open.
- Both malformed-function reload paths have runtime evidence. A malformed
  ordinary `.mcfunction` and an unterminated macro template are each logged
  and omitted while reload completes and valid functions remain callable,
  matching vanilla in all nine Fabric runtime modes. A test-only Fabric listener
  forces a whole resource reload future to fail in each of the nine Fabric
  modes. The earlier isolated run retained its old library at load count 9,
  direct and tag scores 77, and omitted changed resources and the newly added
  function. In the later six-request overlap plus failure run, the failed
  reload retained the published A generation after all six publications. Both results
  match their vanilla pre-failure snapshots.
- The full eight-arm reload suite previously verified the inline macro tuple
  across five body/tag generations and a held async reload. A new focused
  three-arm run (vanilla, compiler-off, selective macro candidate) uses the
  entity-data provider during sequential, held, and failed reloads. During the
  held reload the old body returns score 37/marker 10; after publication the new
  body returns score 37/marker 303. The selective-path counter advances once
  during preparation and once after publication. A forced whole-resource reload
  failure stages marker 909 but retains the old published macro at
  score 37/marker 303; the selective path still runs after failure. A full
  nine-mode run with whole-resource failure and a six-request overlap matches
  vanilla: A is held while B, C, D, E, and F publish in order, then A publishes
  last. The selective-macro arm advances its selected-path counter through all
  six publications and after the failed reload while the old macro stays at
  marker 303. Seven-or-more-request races and other macro failure shapes remain
  open.
- A full eight-arm runtime rerun changed a macro body during the first of five
  reload generations and reused the inline argument tuple (`amount:37`) before
  and after reload. Vanilla and all nine Fabric modes returned score 37 and
  observed the body marker change from 1 to 10. In the five macro-specializing
  modes, the `macro_add` specialization counter advanced from 13 to 14 after
  reload. The focused entity-provider reload run adds the selective-path
  coverage above.
- Opt-in ordinary leaf-callback accounting passes its exact fixture in
  wrapper, ScoreAdd, fused, and bytecode modes: the generic wrapper records 7
  generic callbacks; each ScoreAdd-backed mode records 5 generic plus 2
  optimized callbacks, with identical final state. On a native 4×4×4 Vein
  Miner event under Lithium, the diagnostic counted 8,238 ordinary leaf
  callbacks: 7,116 generic and 1,122 optimized ScoreAdds. That optimized count
  matches the independent ScoreAdd execution counter and splits into 480
  queue-drain plus 642 ray-step calls. Modifier operations and custom command
  executors are excluded. Callback wrappers perturb execution, so these counts
  are attribution data, not timing evidence.
- The execute as @e[...] at @s fixture produces scores 0 at limits 0–3, then
  1, 2, 3, and 4 at limits 4–7. This matches one function-call debit,
  two modifier-stage debits, and one leaf debit per selected armor stand; exact
  per-debit events are not instrumented in pure vanilla.
- The empty-function trace stays at the top-level frame with score 0 for
  limits 0–7. The one-entry fixture runs no body command at limits 0–1 and
  runs its sole add from limit 2 onward. Full `/debug function` traces and
  results match mod-free vanilla across all nine Fabric modes.
- The four-entity `execute as … at …` trace shows no successful leaf at
  limits 0–3, then one, two, three, and four completed leaves at limits 4–7.
  Scores and full trace text match mod-free vanilla in every Fabric mode.
- The three-add `quota_three` baseline produces scores `0,0,1,2,3,3,3,3` at
  limits 0–7. Low-quota `/debug function` traces show no body entries at 0–1,
  one add at 2, two at 3, and all three from 4 onward. Vanilla and all nine
  Fabric modes match the full trace text and command results.
- A new `quota_execute_four_followup` fixture puts a `+10` function entry after
  the same four-actor execute. Across sequence limits 0–16, vanilla and all
  nine Fabric modes match: scores are 0 at 0–3, 1/2/3/4 at 4–7, then 14 at
  8–16. The queued `+10` remains stopped at limit 7 and executes at limit 8;
  exact per-debit vanilla events remain unavailable.
- The same one-entry inner function run directly produces 0 at limits 0–1 and
  1 at limits 2–7. The outer function that calls it and then adds 10 produces
  0 at limits 0–2, 1 at limit 3, and 11 at limits 4–7. State and RCON feedback
  match across all ten arms: mod-free vanilla plus wrapper-off, wrapper-on,
  ScoreAdd-on, instrument-only, timed ScoreAdd, fused-interpreted,
  emitted-bytecode, bytecode-compile-failure, and selective-macro-arguments.
- `debug function` traces for the nested outer fixture now sweep limits 0–7.
  The outer frame appears at all limits, the child call appears at limit 2, its
  `+1` command completes at limit 3, and the outer `+10` completes at limit 4.
  Scores, command events, and trace text match mod-free vanilla byte-for-byte
  across all nine Fabric runtime modes. The vanilla process still does not
  expose individual quota debit events.
- The direct `quota_nested_inner` trace sweep matches the same direct
  one-entry behavior at limits 0–7; the nested outer sweep shows the additional
  function-call debit before that child entry. This direct-versus-nested trace
  comparison matches vanilla in all nine Fabric modes.
- The assertion-backed extended probe now passes across mod-free vanilla and all nine Fabric modes.
  `quota_return_value` yields score states `0,0,1,1,1,1,1,1` at limits 0–7;
  `quota_return_run` yields `0,0,1,11,11,11,11,11`. The stored-result fixture
  yields `0,0,0,0,1`, then 17 at limits 5–16; the `execute if function`
  fixture yields `0,0,0,1,1`, then 11 at limits 5–16. The four-entity fork
  fixture yields `0,0,0,0,4` at fork limits 1,2,3,4,8. Expected-state and
  cross-mode RCON assertions are in the harness.
- Nested return-frame behavior matches at limits 0–16: the nested outer
  fixture produces `0,0,0,1,11`, then 1011 for limits 5–16. The recursive
  fixture terminates with monotonic scores from 0 through 4 as the quota grows.
  A second recursive fixture performs two adjacent ScoreAdds per frame and
  recurses until score 6. Its exact 0–16 map matches vanilla in all nine
  Fabric modes; fused and bytecode execution counters each advance by 33 over
  the quota sweep. The forced bytecode compile-failure arm also matches vanilla.
  A function that lowers `max_command_sequence_length` during execution
  produces matching states `0,0,1,1,11`, then 111 for limits 5–16. In those
  latter cases, a subsequent invocation runs with the new limit of 1 and
  executes no body entries. This matches 26.3's `ExecutionContext` constructor,
  which initializes the context quota from the limit captured at creation.
- Fork coverage now configures zero, one, two, or four matching actors and
  sweeps `minecraft:max_command_forks` from 1 through 12. Mod-free vanilla and
  all nine Fabric modes agree for all 48 configurations, including
  the first threshold that completes each selector expansion. Order-sensitive probes with three
  actors and `limit=2` confirm nearest and furthest selection order at fork
  caps 1–4 in all ten runtime arms (mod-free vanilla plus nine Fabric modes). Random and arbitrary sorting visit all
  three actors at high caps and match low-cap branch counts in direct and
  function paths: caps 1–2 execute none, while caps 3–4 execute two; the
  function follow-up runs once at every cap. For all four sorts, direct
  `/execute` at cap 1 returns `Maximum number of contexts (1) reached` and cap
  2 returns an empty RCON response. The queued `/function` call reports its
  generic invocation response. A four-actor overflow fixture checks that no
  excess branch effects occur and the following queue entry adds 10 exactly
  once at fork caps 1–12. The low-cap cases also match in the full 16-arm
  compatibility run (`20261029T011410`): vanilla, all Fabric compiler modes,
  Bellows 1.1.2 modes, and Bellows + Moonrise 1.2.0 modes. Other selector
  shapes and broader interactions between selector forms and mod stacks
  remain open.
- `/debug function` output matches byte-for-byte across all ten arms (mod-free
  vanilla plus nine Fabric modes) for a three-command function and a nested
  outer/inner call; each trace
  contains the same function nesting, command results, and result callbacks.
  A full 26.3 differential rerun adds exact trace parity for a stored function
  result (`quota_return_result`, score 17, four command events), success/failure
  isolated calls (`quota_execute_if_function`, score 11, four events), and
  `return run` (`quota_return_run`, score 11, two events). Each trace matches
  mod-free vanilla byte-for-byte in wrapper-off/on, ScoreAdd, both timer arms,
  fused-interpreted, and emitted-bytecode modes. Nested syntax-error cases also
  match across all ten runtime arms (mod-free vanilla plus nine Fabric modes): `return run function` preserves the
  child's later `+2` and discards the parent's trailing `+4` (score 3);
  `execute if function` preserves the child `+2`, treats the errored call as
  false, skips its `+10` branch, then runs the outer `+1` (score 3); and
  `execute unless function` takes the inverted branch after the same child error
  and reaches score 14. Their 0–16 state maps match vanilla. The `unless` case
  also has byte-identical debug traces at every sequence limit in all ten arms
  (mod-free vanilla plus nine Fabric modes). Compatibility run `20261029T014306` matched the unless state
  map and high-quota trace across all 16 vanilla, Fabric, Bellows 1.1.2, and
  Bellows + Moonrise 1.2.0 arms. A second fixture runs the same erroring child
  under `execute store result` and `execute store success`: the child applies
  each completed `+2`, while both seeded store destinations remain `-1` after
  the syntax error. Across limits 0–4 no child effect runs, limits 5–8 apply one
  `+2`, and limits 9–16 apply both. Its six-event trace and state map match
  vanilla in all ten runtime arms (mod-free vanilla plus nine Fabric modes) and all 16 compatibility arms in run
  `20261029T020726`. Other callback and failure combinations remain open.
  The Fabric-only helper-path queue/cost trace matches between wrapper-off/on.
  Configured helper limits 0–7 expose queue-start values 0–6 because the
  helper command itself spends one unit; yielded and completed queues are
  recorded separately. Vanilla's built-in function path remains uninstrumented
  for individual debits.
- Scoreboard P0 fixtures pass across vanilla and all nine Fabric modes: literal
  set produces -17; add creates an absent score at 7 and changes an existing
  5 to 12; a missing-objective command returns its exact error and leaves the
  following +10 action running; reset removes a seeded score; four selected
  entities receive score 5 each (aggregate 20); wildcard reset
  removes scores only from the named objective; wildcard-target `+=` changes
  seeded scores 3 and 5 to 10 and 12 and creates the source fake holder in
  the target objective at 7. This newly covered operation matches the
  mod-free vanilla reference and all nine Fabric modes. Signed 32-bit overflow
  wraps min-1 to 2,147,483,647 and max+1 to -2,147,483,648; remove/reset and
  delete/recreate clear stale scores. `execute store success` records 0 for
  `return fail` and a missing-score getter, and 1 for a successful scoreboard
  set. A new missing-objective failure fixture runs a literal add through both
  `execute store success` and `execute store result`: both seeded targets
  become 0, then the trailing +10 runs. The results match mod-free vanilla and
  all nine Fabric modes, including fused-interpreted. Exact command feedback and
  measured state match across all ten runtime arms (mod-free vanilla plus nine Fabric modes). Removing 4 from an absent
  score creates it at -4; using an absent operation source creates that score
  at 0 and leaves the target unchanged at 12. An operation into an absent
  target copies the existing source value 13. Applying an operation to the
  four-entity target selector gives each entity score 2. A zero-match operation
  source leaves its target unchanged; four matching sources fan out and move
  the seeded target from 10 to 30, then a following +7 runs once. All listed
  outcomes match mod-free vanilla and all nine Fabric modes. A mixed selector
  target containing one absent score and three scores of 2 produces one score
  of 3 and three of 5 after adding 3. A disjoint two-target by two-source
  selector operation changes both targets from 10 to 18 and preserves source
  scores 3 and 5. A four-source selector with three scores of 5 and one absent
  score adds 15 to a target of 10 and creates the missing source score at 0.
  These new cases match every mode's vanilla scoreboard state
  and RCON observations. All nine scoreboard operation operators (`=`, `+=`,
  `-=`, `*=`, `/=`, `%=`, `<`, `>`, `><`) match; divide/remainder by zero
  leave a seeded target unchanged at 7, and `INT_MAX * 2` wraps to -2. Every
  operator is also tested once with an absent source score and once with an
  absent target score; score creation and resulting values match vanilla in
  all ten runtime arms (mod-free vanilla plus nine Fabric modes). The
  additional target cases exercise vanilla fallback
  while ScoreAdd is enabled; the prototype does not optimize scoreboard
  operations.
- The runtime Mixin counter observed one parse of `quota_three` at startup and
  still one after repeated execution in all nine Fabric modes. The
  wrapper-on server instantiated it 490 times through the direct and
  scoreboard fixture run. The counter advanced once on each full datapack
  reload, including five lifecycle generations that changed function content
  and tag membership plus a removal and re-addition of the function. In exact
  26.3 vanilla bytecode, `PlainTextFunction.instantiate` is `aload_0; areturn`,
  so ordinary invocation returns the existing function object without parsing.
- A temporary test-only datapack verifies the `#minecraft:load` function runs
  once on initialization and once on each of seven reloads, while the
  `#minecraft:tick` function continues to advance. All ten arms (mod-free
  vanilla plus nine Fabric modes)
  observe the same counts and function/tag results. In Fabric, lookup and tag
  membership resolve the same current wrapper instance after each reload,
  including when `probe` is removed and re-added. The diagnostic parse counter
  advances once per reload, from 2 after test-pack enablement to 9 after the
  seven lifecycle reloads. The per-function ScoreAdd compile counter reaches
  7 after the five body/tag generations, stays at 7 while `probe` is absent,
  and reaches 8 after re-addition in ScoreAdd and timer arms; wrapper-only arms
  stay at zero.
- Vanilla's `MacroFunction` and equality-aware eight-entry LRU remain the source
  of truth. In ScoreAdd-on and timer modes only, the builder wrapper delegates
  to `MacroFunction.instantiate`, then specializes eligible `PlainTextFunction`
  entries for that expansion; wrapper-only modes leave macros unwrapped. The
  focused eight-arm macro matrix matches vanilla for 11 inline values (score 56),
  storage values changed from 2 to 7 (scores 58 and 65), ten-tuple LRU churn,
  hash-colliding compounds `{a:0,c:1}` and `{a:1,c:0}` (both hash 195), and
  missing/malformed argument errors with no score changes. The prototype
  specializes 13 `macro_add` callbacks and 26 `macro_pair` callbacks in both
  ScoreAdd-on and timed ScoreAdd; instrument-only timing records those same
  per-function counts while delegating callback behavior to vanilla. This is
  parity evidence for the fixtures, not a speedup result or a general macro
  backend.

The focused macro-specialization run passed in vanilla, wrapper-off/on,
ScoreAdd-on, instrument-only, and timed ScoreAdd modes. It records vanilla
parity for expanded state, exact macro error feedback, equality-keyed cache
reuse, and per-function callbacks. The macro specialization remains disabled
by default and has not been benchmarked. The full eight-arm runtime suite was
rerun after the macro wrapper change and passed its direct-function, quota,
scoreboard, lifecycle, fallback, and trace assertions as well.
- A valid vanilla fallback command (`say`) between scoreboard actions resumes
  the function and yields score 11 in all ten runtime arms (mod-free vanilla plus nine Fabric modes). A runtime
  missing-score getter raises its command error, then the following function
  action executes and yields score 1 in all ten runtime arms (mod-free vanilla plus nine Fabric modes).
- The exact-source Math.max(1, gameRuleValue) behavior is confirmed in the
  direct-function results too: limits 0 and 1 both complete no body lines for
  the three-entry function.
- The first exploratory PERF-001 capture profiles mod-free vanilla 26.3 after
  50 warmup calls of a fixed 5,000-line scoreboard function. The measured run
  applied and verified 5.25 million updates; the one-second JFR recording has
  101 execution samples. These samples are exploratory, not a stable baseline
  distribution or a speedup result. A local Spark standalone-agent capture
  against the same fixture also verified the capture path.
- The PERF-010 runner uses the pinned Dynamic Lights by CreepermeYT 1.4.6
  datapack, Spark 1.10.194, four connected headless players, and 24 stationary
  dropped torch sources. Three valid vanilla datapack-on/off pairs now have
  all-thread call trees. Each on tree samples the scheduled function path
  (`FunctionCallback.handle` to `ServerFunctionManager.execute`) at 716–756 ms
  weighted sample time; the off trees have no such path. Median post-profile
  P50/P95/P99 MSPT is 6.4/9.7/12.0 on and 4.9/7.6/9.7 off, but one pair
  reverses sharply. This confirms recurring command work, not a stable cost
  estimate. Details and run IDs are in the
  [PERF-010 evidence report](research/real-world-profile-targets.md).
- Corrected all-thread datapack-on CPU profile pairs are also available for
  Fabric, Lithium, and Lithium+Moonrise. Each profile has 44–47 thread nodes,
  preserves all 24 torch sources, and samples the scheduled function path.
  Weighted `ServerFunctionManager.execute` samples are 812/756 ms for Fabric,
  524/1,960 ms for Lithium, and 620/772 ms for Lithium+Moonrise (wrapper off/on).
  These single-pair captures have noisy MSPT and are not optimization or
  wrapper-cost evidence; datapack-off controls and randomized repeats remain.
- The Blastback profiler now separates its no-TNT tick-dispatch path from the
  still-failing 1-TNT restoration event. Two Fabric compiler-off/ScoreAdd
  pairs match `#tick_id` deltas exactly (460 and 461); the ScoreAdd arms report
  one compiled `erb:runtime_tick` command. `ServerFunctionManager.execute`
  weighted samples were lower in both optimized captures, but two short runs
  are not enough to make a performance claim. The no-TNT scenario still has
  one active group. A 2026-11-03 static screen found adjacent candidate runs in
  the archive's generated block-state reader (32 `execute if block ... run
  scoreboard players set` commands per state table), reached from
  `erb:capture/store` during capture scans; runtime specialization and
  performance remain unmeasured.
- Earlier CPU profiles used a `Server thread` filter that resolved to an empty
  thread set in standalone-agent runs. Those files have metadata and health
  metrics, not CPU call trees. The runner now samples all threads and rejects
  captures with no thread sample nodes. Older Bellows-related workload and
  wrapper checks remain useful for compatibility screening, but their CPU
  files must not be used for profile comparisons.
- The Function Compiler wrapper probe passes its identity and delegation
  checks across the tested Fabric, Lithium, Bellows, Lithium+Bellows,
  Lithium+Moonrise, and Moonrise 1.2.0 combined stacks. A wrapper probe pass
  verifies the current delegating hook only; it is not evidence of optimization.
- The expanded nine-arm compatibility probe compares vanilla, Fabric
  wrapper-off/on, ScoreAdd-on, fused-interpreted, Bellows wrapper-off/on,
  Bellows+ScoreAdd, and Bellows+fused-interpreted.
  Positive-tag `dx/dy/dz` selection across two boxes, nearest `limit=1`,
  nearest-sorted order-dependent effects, positive-tag distance filtering,
  score plus AABB filtering, positive/negative tag constraints with an AABB,
  furthest `limit=1`, and NBT-predicate selection (`nbt={Silent:1b}` and
  `nbt={Glowing:1b}` in a `dx/dy/dz` box, each selecting exactly its own actor
  in run `20261102T235411`) all select the same entity identities as vanilla.
  Common entity NBT modify/merge/remove, entity-tag cache updates, and literal
  ScoreAdd state/feedback also match across the compiler-off/on pairs. The
  Bellows adapter now restores vanilla mob `home_pos` values for
  initialization, merge, modify, and remove in all four Bellows arms. Separate
  `home_radius` modify/remove cases preserve the exact vanilla radius and
  position values in all nine arms. The runner is
  `scripts/run_compatibility_probe.py`; generated server worlds and reports
  are ignored.
- The full 16-arm compatibility run `20261028T152121` passed: vanilla, five
  Fabric arms, five Bellows 1.1.2 arms, and five Bellows + Moonrise 1.2.0
  arms. No pairwise or vanilla-vs-Bellows semantic checks failed. The tested
  selector identities/order, entity-data, tag-index, `home_pos`, and
  `home_radius` cases match; the Fabric-only modded leaf also matches compiler
  off across all 15 Fabric-based arms. This command-level result does not
  change the separate finding that Bellows-containing stacks produce no output
  for the selected Dynamic Lights workload.
- The opt-in ScoreAdd differential probe matches the exact final score and
  feedback for its covered literal fake-holder fixture across vanilla, Fabric
  wrapper-off/on, and the specialized path. The specialization leaves vanilla
  scheduling, quota, trace, and result callback machinery in place and falls
  back to the original command when recognition is uncertain. This is scoped
  fixture evidence, not blanket parity for all scoreboard commands or mods.
- The opt-in fused interpreted region passes the ten-arm runtime matrix (mod-free
  vanilla plus nine Fabric modes) and the
  nine-arm compatibility matrix. It groups adjacent literal fake-holder
  ScoreAdd commands in ordinary functions, checks the active quota before each
  command, and preserves one result, error, and trace callback per source
  command. The six-command fused error fixture changes the score, fails on a
  missing objective, then executes two more commands inside the region, a
  native `say`, and the next queued ScoreAdd without replaying the earlier
  effect. All ten arms (mod-free vanilla plus nine Fabric modes) reach score 22 and produce the same complete
  debug trace as vanilla. A small CallFunction trace adapter reports the
  original logical function entry count. A nested outer/inner fixture with
  fused regions on both sides of the nested call includes a missing-objective
  error after two mutations. Both later fused adds and the native `say`
  fallbacks still run; all ten runtime arms (mod-free vanilla plus nine Fabric modes) reach score 165 with the same 12 command
  events and error callback as vanilla. Twelve frame/callback-discard cases also
  match vanilla traces: `return fail` and `return 7` each discard a pending
  fused region and retain score 1; nested `return run function` returns 7 from
  its child, discards pending inner and outer regions, and leaves score 31; an
  `execute if function` child that adds 1 then returns failure skips the
  conditional `+1000` and the child's pending `+100/+100` region, then resumes
  the parent's pending `+10/+20` region exactly once. All ten runtime arms
  finish at score 31 with the same five-event trace; fused and bytecode counters
  each advance by exactly one region. An `execute store success` call whose
  child adds 1 then returns failure stores 0, discards the child's pending
  `+100/+100` region, and resumes the parent's `+10/+20` tail once; all ten
  arms finish at score 32 with the same six-event trace, and fused/bytecode
  each execute one parent continuation region. An `execute store result` call
  whose child adds 1 then returns 7 stores 7,
  discards the child's pending `+100/+100` tail, and resumes the parent's
  `+10/+20` tail once. All ten arms finish at score 32 with the same
  six-event trace; fused and bytecode each execute one parent continuation
  region. An `execute store result` call whose child adds 1 then returns
  failure stores 0, discards the child's pending `+100/+100` tail, and resumes
  the parent's `+10/+20` tail once. All ten arms finish at score 32 with the
  same six-event trace; fused and bytecode each execute one parent continuation
  region. An `execute unless function` child that adds 1 then returns failure
  takes its `+1000` branch, skips its pending `+100/+100` child tail, and
  resumes the parent's `+10/+20` tail once. All ten arms reach score 1032 with
  the same six-event trace; fused and bytecode each execute one parent region.
  An `execute store success` child that returns 7 stores success value 1,
  discards its pending child tail, and resumes the parent's tail once; all ten
  arms reach score 32 with the same six-event trace, and fused/bytecode each
  execute one parent continuation region. A nested `execute store result` call
  around a wrapper using `return run function` to invoke a child returning 7
  stores result 7, discards pending child and wrapper `+100/+100` tails, and
  resumes the parent's `+10/+20` tail once; all ten arms finish at score 37
  with the same eight-event trace, and fused/bytecode each execute one parent
  continuation region. A paired nested `execute store success` call around the
  same wrapper returning 7 stores success value 1, discards pending tails, and
  resumes the parent's tail at score 37 with the identical eight-event trace;
  a failed counterpart whose child returns failure stores success value 0,
  discards both pending tails, and resumes the parent tail at score 37 with
  the matching eight-event trace. Fused and bytecode each execute one parent
  continuation region in both cases. The ten-arm run compares 88
  `/debug function` traces per arm.
  Evidence: `build/reports/runtime-probe/results.json`.
  Fabric and Bellows fused runs retain the
  original PlainTextFunction; the Bellows run also matches compiler-off
  selector and entity-NBT paths.
  Macro expansions retain Minecraft's native cache and are not fused.
- PERF-004 compared instrument-only vanilla delegation, ScoreAdd, fused
  interpreted, and emitted bytecode in five randomized trials per arm. Every
  trial verified 5,250,000 scoreboard updates. Median full-function queue times
  were 2.500 ms, 2.784 ms, 1.537 ms, and 1.890 ms respectively. Emitted
  bytecode was 24.4% faster than the delegate but 23.0% slower than fused
  interpreted on this static fixture, so there is no evidence to select it over
  the simpler backend. All prototypes remain disabled; timer overhead and
  broader workload coverage remain limitations.
- PERF-005/006 completed five randomized trials in five arms: vanilla, Fabric
  with compiler features off, Bellows with compiler features off, fused
  interpretation, and Bellows plus fused interpretation. All 20
  non-vanilla arm/trial normalized outputs match vanilla. Bellows lowered the
  inclusive `ServerFunctionManager.execute` sample share by a paired median
  67.6% on the controlled entity-NBT fixture, in all five trials. The compiler
  prototype did not reduce sampled function share on selector or NBT work, and
  whole-server tick timings were variable. No prototype is promoted. See the
  [PERF-005/006 report](../benchmarks/PERF-005-006-bellows-selector-nbt.md).
- PERF-002 completed five independent RCON-driven trials in each of four arms with verified
  score deltas: vanilla, Fabric wrapper-off, Fabric wrapper-only, and the
  ScoreAdd prototype. Median RCON-driven throughput was 1.736M fixture
  commands/s for vanilla and 1.736M for ScoreAdd (+0.008%); trial variation is
  substantial. RCON does not provide exact server-thread elapsed time, so this
  does not close the performance gate.
- The PERF-002-TIMING follow-up completed five trials each for an
  instrumentation-only vanilla callback and the ScoreAdd callback. Each trial
  timed exactly five million server-thread callbacks and verified the score
  delta. Median callback wall time was 221.14 ns/action for the delegated
  vanilla command and 130.48 ns/action for ScoreAdd (41.0% lower); RCON median
  throughput was 1.51M/s versus 1.30M/s, with high trial variation. The
  `System.nanoTime` and counter overhead is present in both arms and has not
  been separately calibrated. The timer excludes context construction, queue
  scheduling, quota, tracing, and the rest of function execution. This is
  promising callback-level evidence, not a whole-function or vanilla-server
  speedup. See the [timing report](../benchmarks/README.md#server-thread-callback-timer-follow-up).
- PERF-002-FUNCTION-TIMING completed five randomized trials per arm, with 5
  million measured actions and exactly 1,000 timed function queues per trial.
  Every post-timing score matched 5.25 million. Median queue time was 2.635
  ms/function for the vanilla delegate and 3.024 ms for ScoreAdd (14.8%
  slower); RCON throughput was 14.4% lower for ScoreAdd. The timer starts at
  the target `FunctionCommand.queueFunctions` call and stops when
  `ExecutionContext.runCommandQueue` returns. It includes instantiation,
  queue processing, quota, callbacks, and tracing, but excludes RCON and
  `/function` parsing. This broader measurement does not confirm the earlier
  callback-only gain. Keep ScoreAdd disabled; the single fixture still needs
  broader CPU/allocation evidence and input/mod parity. See the
  [full-function timing report](../benchmarks/README.md#earlier-perf-002-server-thread-function-queue-timing).
- One Spark CPU and allocation profile per arm was captured separately on a
  10-million-action tick workload. Estimated allocation was about 337 B/action
  for vanilla, 464 for Fabric wrapper-off, 453 for wrapper-only, and 401 for
  ScoreAdd. CPU samples show less argument/name-resolution work in the
  specialized path, but the sample count is insufficient to claim a repeatable
  CPU improvement. See the [PERF-002 report](../benchmarks/README.md#perf-002-literal-fake-holder-scoreadd-prototype).
- PERF-002 now also includes three randomized trials for an opt-in
  `fused-interpreted` arm with exact 1,625,000-action score checks per trial.
  Median RCON throughput was 1.496M actions/s fused and 1.462M/s vanilla, with
  respective ranges 0.785–1.644M and 1.429–1.698M. The Fabric-off, wrapper-only,
  and ScoreAdd medians were 0.706M, 0.951M, and 1.112M actions/s; their ranges
  were also wide. One CPU and allocation profile per arm is retained. This
  pilot is too noisy to establish a gain, and fused remains disabled.
- PERF-003's three-trial RCON-only pilot passes exact score checks but is too
  noisy to establish a throughput gain. A separate matched server-thread timer
  then completed two randomized five-trial sets for the vanilla-command delegate,
  ScoreAdd, and fused region. Across ten trials per arm, median queue times
  were 3.399 ms, 3.147 ms, and 2.014 ms respectively; fused was 40.8% lower
  than the delegate and 36.0% lower than ScoreAdd. Every trial verified the
  exact 5.25-million score. Fused was faster in both randomized sets, but this
  is still evidence for one static 5,000-command fixture; timer-overhead
  calibration, allocation/reload costs, and broader semantic gates remain open.
  Vein Miner now supplies a real native-trigger workload for direct ScoreAdd.
  A 2026-11-03 static screen found adjacent candidate runs in several pinned
  packs, but none has runtime-confirmed specialization or a measured real-world
  fused/bytecode comparison. Keep it disabled.
  See the [PERF-003 timing report](../benchmarks/README.md#perf-003-server-thread-queue-timing).
- The pinned Dynamic Lights 1.4.6 pack has no literal fake-holder `#` ScoreAdd
  commands, so the current fused prototype has no eligible work in that
  real-world workload. Existing Dynamic Lights profiles validate its scheduled
  function path, but they are not optimization evidence. Blastback Hotfix 3's
  no-TNT tick dispatcher provides one eligible add in `erb:runtime_tick`.
  Two same-stack Fabric compiler-off/ScoreAdd pairs match exact `#tick_id`
  deltas at 460 and 461; exact probe stats confirm one compiled entry. Weighted
  `ServerFunctionManager.execute` samples are lower in both ScoreAdd captures.
  A separate instrumented diagnostic counted 340 executions of the specialized
  entry, matching the `#tick_id` delta; its timing is excluded from comparisons.
  Four more randomized 12-second pairs on Lithium, Bellows, Lithium+Bellows,
  and Lithium+Bellows+Moonrise 1.2.0 each passed the no-event gate and compiled
  one command in the optimized arm. Tick counts match in three pairs and differ
  by one in the Lithium pair; Spark samples move both directions. These short
  captures are path coverage, not a performance decision. The scenario has one
  active group and does not
  cover the TNT restoration event, which still fails its integrity gate. A
  2026-11-03 static screen found a 32-command adjacent candidate in the
  archive's generated block-state reader, but runtime specialization and
  performance remain unmeasured. Keep both prototypes disabled pending broader
  workload, compatibility, and P0 gates.
- A pinned [Vein Miner 5.3.0 26.3 datapack](research/tick-heavy-datapack-candidates.md)
  supplies a native, event-driven ScoreAdd workload. An isolated vanilla 26.3
  server used the pack's crouch-and-break trigger: the ray tracker selected
  the exposed ore block, a survival player with a diamond pickaxe mined it via
  native start/stop destroy packets, and the pack's tick queue removes the
  remaining ore. Vanilla, Fabric compiler-off, and Fabric ScoreAdd-on 4×4×4
  runs finish with 63 work and 480 `#head` increments. A larger 6×6×6 vanilla
  run finishes 215 work items and 1,952 increments. Five seeded randomized
  Fabric compiler-off/ScoreAdd pairs at 6×6×6 all match exact work, queue,
  block, and operation state. Median paired changes are −0.19% event completion
  time and +0.31% weighted `ServerFunctionManager.execute` samples; ranges are
  broad, so there is no robust performance gain. A separate instrumented run
  compiles one `vm:queue/drain` ScoreAdd and executes it 1,952 times, matching
  the pack counter. Generic callback accounting is verified on the native
  4×4×4 event. The later Lithium+Bellows 1.1.3 native event and ScoreAdd screen
  also pass workload and activation checks, with no reliable performance gain.
  A 2026-11-03 static screen found 145 adjacent parsed candidates in
  `vm:detection/acquire_target` plus a one-time 19-add `@s` initialization, so
  the archive is a static fused candidate even though runtime specialization
  and performance are unmeasured. The direct-ScoreAdd workload is covered on
  Fabric, Fabric+Lithium, Fabric+Lithium+Moonrise 1.2.1, and Lithium+Bellows
  1.1.3.
- The Vein Miner native-trigger campaign also ran five randomized 6×6×6 pairs
  on Fabric + Lithium 0.26.2. All ten arms completed 215 work items, advanced
  `#head` by 1,952, removed the ore, and ended with no operation markers; each
  pair's full recorded state matched. ScoreAdd medians were +12.47% in event
  completion, +12.46% in weighted `ServerFunctionManager.execute` samples,
  +15.79% average tick time, and +6.06% P95 tick time. The relative ranges are
  wide and pair 5 is a large outlier, so this is a regression signal to
  investigate, not a stable performance estimate. No gain was observed.
- Five additional randomized pairs on Lithium 0.26.2 + Moonrise 1.2.1 also
  match exact 215-block workload state in every arm. ScoreAdd medians trend
  slower by +19.98% completion time, +21.62% weighted function samples,
  +37.67% average tick time, and +30.53% P95 tick time, but every metric's
  range crosses zero. This is not a robust regression estimate and shows no
  speedup. The campaign carried a temporary dormant diagnostic mixin in both
  arms, so treat it as directional evidence.
- Reconstructed Spark call paths in all 15 valid compiler-off Vein Miner
  captures identify `FunctionCommand` macro argument construction followed by
  full entity NBT serialization (`Entity.saveWithoutId`). The pack repeatedly
  calls `function ... with entity @s data` while draining its queue, although
  the target macros consume only a few fields. A bounded selective-argument
  prototype now addresses this path and retains vanilla fallback for unsupported
  shapes. It remains disabled by default.
- A vanilla queue-size sweep now includes 4×4×4, 5×5×5, and two 6×6×6 native
  Vein Miner runs. All pass workload integrity. Inclusive Spark samples along
  the macro-argument path to `Entity.saveWithoutId` rise from 436 to 2,708 to
  8,728–9,268 while work rises 63→124→215. This supports a selective macro-
  argument prototype but is not exact timing or randomized performance proof.
  An 8×8×8 attempt ended when Minecraft's watchdog terminated the server and
  is excluded. The research candidate is limited to a single resolved macro
  call using `with entity @s data` when all top-level macro parameters exist;
  all other paths retain vanilla argument construction. The disabled prototype
  passes a focused three-arm differential (mod-free vanilla, same-stack
  compiler-off, and selective candidate) on Fabric, Lithium 0.26.2, Bellows
  1.1.2, Bellows+Moonrise 1.2.0, Lithium+Moonrise 1.2.1, Lithium+Bellows, and
  Lithium+Bellows+Moonrise 1.2.0. Focused run `20261029T054345` also passes against vanilla and same-stack compiler-off on Lithium+Bellows 1.1.3. Each report records the pinned mod hashes.
  The fixture includes inline and storage values, tuple-cache collisions and
  churn, missing/malformed arguments, entity-provider fallbacks, debug traces,
  and sequence quotas. A wrong-typed present entity field (`amount` as a
  string) now matches vanilla's nested macro error trace and continuation state
  in mod-free vanilla, compiler-off, and the selected path on Lithium+Bellows
  1.1.3; its selected-path counter advances once. The same three-arm run copies
  a nested entity compound with an int array and string list into storage, then
  reads back all six nested values identically; the selected-path counter
  advances once for this case too. The wrong-type and composite cases also
  match on Lithium+Bellows 1.1.3+Moonrise 1.2.0, including both selected-path
  counter increments. Bellows+Moonrise 1.2.1 remains excluded because that
  stack does not start. A wrong-typed storage-provider argument also matches
  vanilla state and exact nested `/debug function` trace on both Lithium+
  Bellows 1.1.3 and Lithium+Bellows 1.1.3+Moonrise 1.2.0. The candidate's
  entity fast-path counter remains at zero for this alternate provider, proving
  that the native fallback handled it. Reports are
  `build/reports/runtime-probe/macro-20261029T182217.results.json` and
  `build/reports/runtime-probe/macro-20261029T182321.results.json`. The
  nested entity path `data.nested` also falls back on both stacks, returns the
  nested value, matches vanilla's state and full debug trace, and leaves the
  fast-path counter at zero. Reports are
  `build/reports/runtime-probe/macro-20261029T182921.results.json` and
  `build/reports/runtime-probe/macro-20261029T183028.results.json`. A
  wrong-typed block-provider argument (`with block ... data`) also matches vanilla
  state and exact nested `/debug function` trace across all ten runtime modes,
  leaving the candidate's fast-path counter at zero. An alternate entity
  custom-data path (`data.custom_args`) similarly falls back, returns the nested
  value 9, matches vanilla state and full debug trace, and leaves the fast-path
  counter at zero. Full report is `build/reports/runtime-probe/results.json`. The
  candidate was also exercised by Vein Miner.
- Fifteen randomized PERF-011 pairs on Fabric, Lithium, and Lithium+Moonrise
  (26.3, Vein Miner 5.3.0, 6×6×6) matched exact compiler-off workload state:
  each arm processed 215 blocks, advanced `#head` by 1,952, emptied the ore
  volume, and cleared operation and target markers. Selective macro's paired
  median completion changes were −23.61% on Fabric, −34.75% on Lithium, and
  −34.50% on Lithium+Moonrise. Weighted `ServerFunctionManager.execute`
  medians changed −24.86%, −36.14%, and −36.83%, respectively. The reconstructed
  macro-argument path to `Entity.saveWithoutId` fell by median 81.02%, 84.51%,
  and 83.10%. Completion and function samples fell in 14/15 pairs. Tick query
  deltas remain noisy and are not a broad server MSPT result. The bounded
  prototype stays disabled pending remaining P0 semantic, compatibility,
  reload and memory gates.
- PERF-011's historical completion measurements ran with Spark sampling active
  at 4 ms. The profile runner now has a no-Spark mode, and the randomized
  campaign uses it for primary timing so Spark call-path attribution is kept in
  separate runs. A single no-Spark Fabric/selective-macro 4×4×4 smoke event
  passed native integrity (63/63 blocks, 480 queue increments, no remaining
  ore or markers) in 3.88 s. This validates the unprofiled runner only; it is
  not an optimization comparison, and the post-event tick query does not
  establish an MSPT gain.
- Compiler-off Vein Miner controls fail the native workload gate on Bellows
  1.1.2: Bellows alone and Lithium+Bellows at 4×4×4 each process 0/63 blocks;
  Lithium+Bellows+Moonrise 1.2.0 at 6×6×6 processes 0/215. In the last
  run the player mined the source, but the queue advanced once, no ore work
  completed, all 215 ores remained, and the operation marker persisted. These
  establish a datapack/mod baseline incompatibility, not compiler behavior or
  parity. Bellows 1.1.3 is pinned separately, and its release notes mention
  fixes to NBT paths in data commands. Its Bellows-only compiler-off 4×4×4
  workload passes: 63/63 blocks, 480 queue increments, and clean operation
  state. Lithium+Bellows 1.1.3 now passes the compiler-off 6×6×6 native
  workload (215/215 blocks, 1,952 queue increments, clean state). Five
  no-Spark selective-macro screening pairs also pass exact state parity on that
  stack; the median completion change is −18.83%, but the interval spans
  −20.62% to +24.37%, so this is not a confirmed gain. The focused macro
  fixture also passes on Bellows 1.1.3 + Moonrise 1.2.0, and its Vein Miner
  native control processes 215/215 blocks with 1,952 queue increments. Five
  selective-macro pairs on this stack pass exact state; median event completion
  improves 20.11%, but the 93.75% interval is −36.67% to +7.01%, so this is
  screening only. Bellows 1.1.3 + Moonrise 1.2.1 still fails startup on a
  missing `EntityLookup.entityById` shadow. Five no-Spark ScoreAdd screening pairs
  also pass parity; their median event time is 3.60% slower, with a range from
  −2.04% to +91.11%. This is inconclusive and does not justify enabling it.
  the old 1.1.2 failures stay historical and Moonrise 1.2.1 with Bellows 1.1.2
  remains startup-incompatible.
- The selected selector/NBT compatibility matrix now also covers the working
  Lithium 0.26.2 + Bellows 1.1.3 + Moonrise 1.2.0 stack. Seven arms in run
  `20261029T154729`—vanilla, Fabric-off, and five compiler modes—match for
  selected selector identities/order, entity NBT, tag-index updates,
  `home_pos`/`home_radius`, and the unknown modded command. All compiler modes
  match the same-stack off arm, including ScoreAdd, fused, and bytecode. This
  extends only the selected probe cases; broader selector/provider coverage
  remains open.
- A separate manual 26.3 check, with Function Compiler absent, reports that
  Vein Miner 5.3.0 completes under Lithium 0.26.2 alone but stalls under
  Lithium 0.26.2 + Bellows 1.1.2. The pinned no-underscore Miraculixx
  VeinMiner 1.3.6 datapack works on the combined stack. The only visible
  difference the user noted was that 1.3.6 mines its vein in one tick while
  5.3.0 spreads work across multiple ticks. This strengthens the narrow
  datapack/mod compatibility finding, but
  does not isolate a cause or make the distinct pack a direct parity control.
- Static screening of Vein Miner finds three literal fake-holder `ScoreAdd`
  sites in 76 functions. The native event exercises the ray-step and queue-head
  sites. A separate instrumented 6×6×6 run records 4,212 `#ray` calls and
  1,952 `#head` calls, 6,164 specialized callbacks across those two entries.
  The third site assigns player IDs outside the measured mining event. An
  aligned 4×4×4 callback-accounting run counts ordinary generic callbacks too;
  its single-event result is summarized above and is not a cross-pack estimate.
- Source screening found [D Better Schedule](research/tick-heavy-datapack-candidates.md)
  as a possible one-shot ScoreAdd path: its player-tick advancement calls a
  helper that increments `#UID` once per player. This is only a source-level
  lead; its exact release archive has not been pinned or runtime-checked, and
  it provides neither repeated eligible work nor an adjacent fused region.
- Bellows 1.1.2's filtered modify/remove path left mob `home_pos`
  unchanged while reporting success. The adapter now matches vanilla for the
  tested init, merge, modify, and remove values across Bellows wrapper-off/on
  and Bellows+ScoreAdd. A passenger nested-tag write reports success but
  leaves state unchanged in vanilla and all tested Fabric arms. Broader
  filtered NBT behavior remains open; see the
  [Bellows audit](research/bellows-audit.md).
- A five-arm compatibility run (vanilla, Fabric compiler-off/bytecode,
  Bellows compiler-off/bytecode) passes selector, entity-NBT, ScoreAdd,
  feedback, and home-radius comparisons. Bellows bytecode mode also preserves
  the adapter's vanilla home-position values for init, merge, modify, and
  remove. This extends the interpreted-backend matrix only for the selected
  bytecode arms; other combined compatibility modes remain open.
- The selected datapack workload is not compatible with all tested stacks.
  Bellows 1.1.2 and Lithium+Bellows keep all items tracked but produce no
  torch-source tags or light markers. Bellows 1.1.2 plus Moonrise 1.2.1 fails
  startup on a missing Bellows mixin shadow field; Moonrise 1.2.0 boots but
  still produces no datapack output. Exact versions and details are recorded
  in the [PERF-010 evidence report](research/real-world-profile-targets.md).
- The Dynamic Lights by darpanshete 1.0.0 artifact advertised for 26.3 did not
  load its functions on the exact server: its pack metadata is invalid for the
  declared format range and both its load and tick functions were unknown. It
  is excluded from profile comparisons. See the
  [real-world profile audit](research/real-world-profile-targets.md).
- Multi-Entity Inlined Selector Forking (`execute as @e[...]`) evaluates
  multi-entity selectors in-process within [`InlinedForkingCommand.java`](../src/main/java/dev/functioncompiler/InlinedForkingCommand.java),
  tracks the active `ExecutionContext` on the server thread via thread-safe,
  re-entrant [`ExecutionContextBridge.java`](../src/main/java/dev/functioncompiler/ExecutionContextBridge.java),
  debits context cost per entity (`incrementCost()`), respects `commandQuota`,
  enforces `forkLimit()`, and folds downstream context transformations (`at @s`,
  `positioned`, etc.) without intermediate queue task scheduling. Differential
  verification across `vanilla`, `fabric-on`, and `bytecode-emitted` confirms
  100.0% parity on zero matching entities, 4-entity executions (score 40),
  downstream coordinate offsets, upstream `execute store result` (sum 6), and
  quota stopping sweeps (0, 1, 2, 3, 4, 5, 8).
  **Batch-8 correction (26.3):** this repository's snapshot inherited that
  claim from upstream verification whose arm vocabulary does not match this
  repository's ten-arm matrix, and on 26.3 the entire chained-modifier pass —
  including this command — was dead code until batch 8 (the no-op `[run]`
  chain stage declined every chained command; see the batch-8 entry in the
  [coverage table](reference/features/command-coverage.md)). Batch 8 re-verified
  the fork-limit and fork-order fixtures across all ten arms with the pass
  enabled; single-stage `as`/`at`/`on` selector forks now compile and run on
  26.3, while multi-stage chains (a second modifier stage without the leading
  `execute` node) still decline and remain on the vanilla path.
- The Exotic Adversarial Red-Team QA campaign evaluates four failure domains
  across six dedicated server arms: `vanilla`, `fabric-on`, `ferritecore`,
  `c2me`, `lbmfc` (Lithium + Bellows + Moonrise + FerriteCore), and
  `lbfc-c2me` (Lithium + Bellows + FerriteCore + C2ME). All four target
  vectors achieved 100% differential parity against vanilla: Vector 1 verifies
  NBT compaction under FerriteCore and concurrent chunk coordinate evaluation under
  C2ME; Vector 2 verifies 100-frame deep mutual tail recursion and 50-frame
  macro recursion trampoline integrity without stack overflows; Vector 3 verifies
  unloaded chunk boundary mutations and multi-dimension portal traversals; and
  Vector 4 proves zero output leakage or message corruption under output
  suppression and silent command sources. Full details and methodology are
  documented in [exotic-adversarial-probe-report.md](reference/benchmarks/exotic-adversarial-probe-report.md).
- Batch 8 closed the MO-02 coverage row and enabled the chained-modifier
  specialization pass, which batch 8 found had never executed on 26.3 (the
  no-op `[run]` chain stage declined every chained command). Measured on the
  pinned vanilla server: the 26.3 storage-store tree is
  `execute store (result|success) storage <target> <path> <type> <scale> run
  <command>` with a required double scale that multiplies, and a failing
  `data get` reports `(success=false, result=0)` to the store callback, so a
  result store writes 0 exactly as a success store does — both overwrite the
  previous content with a zero of the declared type. Vanilla's quota-debit
  model is one debit per modifier stage with a redirect modifier plus one per
  final source; the model reproduces the measured quota maps of
  `mo02_store_result`, `mo02_store_failures`, `quota_three` and the four-actor
  `as`/`at` fixture exactly. The two MO-02 fixtures and every other fixture
  containing single-stage modifier chains match vanilla in all ten arms with
  exact score sequences, command results, debug traces, reload generations and
  fork limits, and the dedicated DataStore compile counters read at least 2
  lines per fixture in the six compiling arms and exactly 0 in vanilla,
  wrapper-off/on and selective-macro-arguments. See the batch-8 record in the
  [coverage table](reference/features/command-coverage.md).
- Batch 9 closed the ST-02 bossbar row with two differential fixtures
  (`st02_bossbar_ops`, `st02_bossbar_values`) matching vanilla in all ten
  arms with exact per-quota score parity, and the dedicated per-function
  bossbar compile counters reading exactly the store-chain counts (6 and 8,
  two events per chained line per generation) in the six compiling arms and
  exactly 0 in vanilla, wrapper-off/on and selective-macro-arguments.
  Measured on the pinned vanilla server: bare `bossbar get <id>` is not a
  valid 26.3 form; `bossbar get value|max|players` and
  `bossbar set value|max` return their values as command results, so the
  row folded into the existing scoreboard oracle with no new oracle type; a
  failing bossbar command does not abort the remaining function lines; and a
  store around a get on an unknown bar writes 0. Bare bossbar lines are not
  in the EXECUTE-stage parser list and stay on the vanilla path, like the
  other state-machine families outside tag/teleport/kill. See the batch-9
  record in the [coverage table](reference/features/command-coverage.md).
- Batch 10 closed the ST-06 `item modify` half with a differential fixture
  (`st06_item_modify`) plus a datapack-defined modifier
  (`st06_set_count`, `set_count 5`) matching vanilla in all ten arms with
  exact per-quota score parity, and the dedicated per-function item-command
  compile counter reading exactly the store-chain count (2) in the six
  compiling arms and exactly 0 in wrapper-off/on and
  selective-macro-arguments. Measured on the pinned vanilla server: the
  26.3 `minecraft:item_modifier` registry ships no built-in modifiers;
  ids are datapack-defined at `data/<ns>/item_modifier/<name>.json` as a
  single object keyed by `type` (array and legacy `function` forms are
  boot-fatal); `item modify` returns result 1 and is idempotent; a failing
  modify writes 0 to a store and does not abort; and an unknown id fails
  at command-parse time, failing the function load. Row closed with
  STATE-004: the table is now 92 rows, 89 covered, 0 partial, 3 missing.
  See the batch-10 record in the
  [coverage table](reference/features/command-coverage.md).
- Batch 11 closed the MO-09 unordered fork selector sorts with new fixtures
  (`mo09_fork_arbitrary_identity`, `mo09_fork_random_identity`) plus an
  identity/freshness block in the harness fork-order fixture runner,
  matching vanilla in all ten arms with the fork fixture result compared
  exactly against the vanilla arm. Measured on the pinned vanilla server
  before the oracle was pinned: `sort=arbitrary` resolves candidates in
  entity insertion (summon) order, not position order, and is stable
  across repeated invocations, `/reload`, a server restart on the same
  world, and fresh worlds with different seeds, so it is asserted exactly;
  `sort=random` is non-deterministic by design (24 trials covered all
  three candidate pairs 8/8/8 with every trial exactly two distinct
  actors), so the row's claim for it is narrowed to per-trial set
  semantics plus a distinct-pair floor across 16 trials per path. The
  fork cap includes the parent context (cap 1 errors, cap 2 truncates
  silently, caps 3+ fork both branches), and candidate-list freshness is
  asserted by killing a selected actor and re-summoning the canonical
  set. Row closed: the table is now 92 rows, 90 covered, 0 partial,
  2 missing. See the batch-11 record in the
  [coverage table](reference/features/command-coverage.md).
- Batch 12 closed the MO-10 fork mod-stack row with a probe running the
  full fork-order fixture, compiler enabled, under three pinned
  hash-verified stacks (`bellows113`, `bellows113-moonrise120`,
  `lbm113120`), each a fresh Gradle runServer. Every stack passed every
  assertion and each stack's recorded fixture result is exactly equal to
  the mod-free vanilla arm's recorded result from the batch-11 ten-arm
  run: Bellows's selector instrumentation and Moonrise's entity system
  rewrite change neither the arbitrary insertion-order resolution nor the
  random set semantics the fixture observes. The oracle is within-stack
  direct-vs-function parity (the modded server is its own reference); the
  claim is scoped to the pinned stacks combining Bellows and Moonrise.
  Row closed: the table is now 92 rows, 91 covered, 0 partial, 1 missing.
  See the batch-12 record in the
  [coverage table](reference/features/command-coverage.md).

- Batch 13 closed ten partial P0 matrix cases by completing the shared
  callback-context x child-outcome matrix (HOOK-001, HOOK-005, HOOK-009,
  SCORE-009 and CTRL-001/002/003/005/006/007). The six function-callback
  contexts crossed with three child outcomes gave 18 cells, of which 15
  already had ten-arm fixtures; the three missing cells became fixtures
  `cbx_return_run_fail`, `cbx_return_run_fail_child`, `cbx_nested_fail` and
  `cbx_unless_success`, measured on the pinned vanilla 26.3 server first
  and asserted over the 0-16 sequence-limit sweep with `/debug function`
  traces in the full ten-arm run of 2026-11-08, which matched vanilla
  exactly for direct-function state, results, traces, reloads and forks.
  Measured semantics: a failed `return run` ends the parent frame (score
  31, both pending tails discarded); a plain nested failing child discards
  only its own tail (score 2031, two executing regions in fused and
  bytecode); a value-returning child skips the `execute unless` branch
  (score 2002). Nine partial P0 cases remain (HOOK-002/003/004/006/008,
  SCORE-007, QUOTA-009, PERF-001, STATE-004) plus the BC-06 campaign row;
  the coverage table itself is unchanged at 92 rows, 91 R, 0 P, 1 missing.
  See the batch-13 record in the
  [coverage table](reference/features/command-coverage.md).

- Batch 14 closed the lifecycle-tag cases HOOK-002, HOOK-003, HOOK-004,
  HOOK-006 and HOOK-008. Measured on the pinned vanilla server first and
  asserted in the full ten-arm run of 2026-11-08 with the
  concurrent-resource-reload and whole-resource-reload-failure probes:
  duplicate tag entries invoke a member exactly once; a tag member naming
  an absent function fails the whole tag load (`Can't find any functions
  for name ...` at invocation, member untouched); a second datapack's
  #minecraft:load member runs once per reload, always after the first
  pack's member (read-only count copy: 1 at the initial enable, 13 after
  seven publications); a second #minecraft:tick member pins intra-tag
  order (observer copy equals the counter every sample, 20 ticks/s); the
  load/tick members' own command traces match vanilla; and the overlap
  probe runs a seventh queued request (load counts 6 -> 12 for the held
  first plus six publications, 13 after the held first publishes last;
  the forced whole-resource failure retains the generation at 13). The
  batch also corrected the concurrent macro specialization expectation
  from a stale +6 to the measured +14 (two ScoreAdd lines per staged
  macro body, recompiled twice per publication). Four partial P0 cases
  remain (SCORE-007, QUOTA-009, PERF-001, STATE-004) plus the BC-06
  campaign row; the coverage table is unchanged at 92 rows, 91 R, 0 P,
  1 missing. See the batch-14 record in the
  [coverage table](reference/features/command-coverage.md).

- Batch 15 closed SCORE-007 and QUOTA-009 and fixed the fork-limit defect
  they exposed. New cells: operations under the execute-store callbacks
  (`store result` stores the operation's new target value, `store success`
  stores 1, a zero-match target stores 0, divide-by-zero stores 0 with the
  target preserved) and three further fork selector shapes (type filter
  with a same-tagged decoy, all-outside distance filter, filtered distance
  subset, each swept over caps 1-12). The run found the compiled fork
  forking one cap early at `limit == selected` - vanilla's fork budget
  includes the parent context (N entities need N+1; exactly N runs no
  branch silently) - and `InlinedForkingCommand` now skips silently at
  `entities >= forkLimit`; the unreachable fork-limit throw and its import
  were removed. The distance shapes pin the world spawn first because
  `distance=` anchors at the randomized spawn. All ten arms of the
  2026-11-08 run match vanilla. Two partial P0 cases remain (PERF-001,
  STATE-004) plus the BC-06 campaign row; the coverage table is unchanged
  at 92 rows, 91 R, 0 P, 1 missing. See the batch-15 record in the
  [coverage table](reference/features/command-coverage.md).

- The batch-16 PERF-001 campaign is recorded as a negative result: three
  pre-declared seven-run baseline distributions over the fixed 5,000-line
  fixture all failed their run-median CV <= 5% gate on this host (CV 0.375,
  0.276, 0.275; host load rising during each campaign; run medians not
  tracking the load cleanly), and the campaign now exits nonzero on a gate
  failure. Recorded next action: rerun on an idle host or under a tighter
  declared load precondition, or replace the RCON round-trip metric with an
  execution-adjacent measurement. PERF-001 stays partial and no baseline
  claim is made. See the batch-16 record in the
  [coverage table](reference/features/command-coverage.md).

- Batch 18 closed the last coverage row, BC-06, with the pre-declared paired
  campaign (scripts/run_bytecode_vs_fused_campaign.py): bytecode versus
  fused interpretation on the declared 5,000-add sustained workload, both
  arms activating exactly (one region per active tick, ~3.37M specialized
  commands inside the region in each), ten counterbalanced pairs with the
  predeclared seed and a predeclared 5% minimum gain. The measured finding
  refutes the row's win claim: bytecode is 10.4% slower than fused at the
  paired median with the exact 97.86% interval 3.85% to 33.33% slower
  (decision does_not_meet_threshold, no-regression decision
  regression_proven); the screening phase (five pairs, median +20.8%) fixed
  the confirmatory design before it ran. The row's text records the
  measured finding and the matrix gained case BC-06, so the table is now
  **92 rows: 92 covered (R), 0 partial (P), 0 missing (—)** - fully covered,
  with PERF-001 the one matrix case still partial by its failed
  pre-declared baseline gate on this host. See the batch-18 record in the
  [coverage table](reference/features/command-coverage.md).

- Batch 20 completed roadmap step 6: the engine-agnostic harness was extracted
  into a version-pinned sibling package,
  [`mc-harness`](../../mc-tooling/mc-harness/README.md) v1.0.0 in the
  `mc-tooling` workspace. It owns the machinery that had been copied per
  project: the pinned 26.3 Fabric mod-stack matrix, the exact
  sign/order-statistic paired-campaign analysis, the server lifecycle (RCON
  clients including the split-response-draining variant, pinned server-jar
  location with SHA-256 verification, Mojang packet-report extraction, RCON
  readiness, server-property helpers), the counterbalanced-campaign
  primitives (port reservation, player connect with transient-close retry,
  score reads and workload waits, tick-query parsing, median windows), and the
  host gate (quiet-window precondition, per-arm noise rule, inter-run settle).
  The runtime probe, both sustained campaign runners, the bytecode-vs-fused
  campaign, the Vein Miner campaign and the PERF-001 baseline campaign consume
  it by path with an import-time version assertion
  (`mc_harness.assert_version("1.0.0")`); their duplicated local copies were
  removed and `paired_benchmark_analysis.py` was deleted, with its
  tests now running against the harness copy unchanged. Per the project guide
  the headless protocol client stays project-owned and pinned to 26.3 protocol
  777 (`tests/runtime/player_bot.py`); the harness receives the client classes
  by injection so no shared-kit change can re-target a live probe. Verified:
  the two-arm runtime probe smoke passes end-to-end on the rewired imports,
  all 54 Python tests pass (including the new harness pin suite), and the doc
  boundary and doc link checks pass. A pre-existing IndentationError in
  `scripts/run_memory_load_analysis.py` (line 448) was found during the
  compile sweep and is reported separately; it predates this batch. See the
  batch-20 record in the
  [coverage table](reference/features/command-coverage.md).

- Batch 21 scoped the compiler-widening decision as a proposal,
  [`docs/v1/plans/compiler-coverage-widening-proposal-v0.1.md`](v1/plans/compiler-coverage-widening-proposal-v0.1.md).
  It records the four mechanisms' verdicts (selective macro arguments the one
  cleared-gate mechanism, default-on; fused regions inconclusive at -15.64%
  with the 97.85% interval uncertified and flat on the real Vein Miner
  workload; ScoreAdd slower everywhere it fires; bytecode refuted against
  fused; the predicate family measured with no sample-share reduction), the
  diagnosis the numbers support (the fuser's eligibility rule excludes forked
  contexts, which is where real selector-heavy tick functions spend their
  work, and ScoreAdd covers only the literal fake-holder family), and four
  candidate hypotheses with falsifiable predictions, code surfaces, and the
  campaign that would decide each: a metrics-only inventory of addressable
  specialized work across the pinned real packs (days, no behavior change),
  extending the one mechanism that has already cleared its gate, fusing
  across the fork barrier (highest value, highest correctness risk, gated
  behind the ten-arm matrix), and storage-holder ScoreAdd deprioritized. The
  proposal is input to a decision, not a plan of record; roadmap step 4 stays
  open until one of its candidates produces a campaign decision, and no
  default-on status changes. Registered in `docs/v1/plans/README.md`.

- Batch 22 ran the compiler-widening proposal's first step: a metrics-only
  specialization inventory of the pinned real datapacks
  (`scripts/run_specialization_inventory.py`, hermetic and SHA-256-pinned).
  It walks the functions reachable from `minecraft:tick`/`minecraft:load`
  (including Dynamic Lights' self-rescheduling `schedule function ... 1t`
  loop), classifies commands against the fuser's real eligibility rule
  (forked `execute` contexts are not fusable; non-forked context modifiers
  are; `function` calls count only when the target is a pure leaf), and ranks
  the packs: Vein Miner 250 adjacent tick commands in 23 runs (longest 144),
  Spawn Animations 143 in 35, Dynamic Lights 14 in 4, Everything Clings 8
  in 2. A runtime confirmation on Vein Miner's native event (Fabric, fused
  mode, no Spark) passed the workload gate (63/63 blocks, 480 queue-head
  increments) and recorded 164 fused regions compiled and 718 executed during
  the event, with 5,860 ScoreAdd executions. Finding: addressability is not
  the binding constraint - the engine fires on the top-ranked real pack and
  the recorded paired result is still flat (+0.69%, interval -3.92% to
  +2.74%, `does_not_meet_threshold`); the fork barrier is real (23.0% of Vein
  Miner's reachable `execute` lines are forked) but the non-forked pool is
  large enough that "the specializers never fire" is not supported. The
  macro-extension pool is narrow (10 `function ... with` call sites in Vein
  Miner tick functions, none in the other three). The proposal was amended
  with the census result (§3.1) and a new next step: a time-share attribution
  pass before sizing H1 or H4. No default-on status changed; no matrix rows
  changed. Batch 23 later corrected these census counts (see the batch-23
  entry): Vein Miner 266 adjacent tick commands in 27 runs, Spawn Animations
  165 in 36, Dynamic Lights 80 in 19; Vein Miner's fork share is 23.4%. See
  the
  [benchmarks record](../benchmarks/README.md#h2-first-specialization-inventory-2026-11-09).

- Batch 23 completed the compiler-widening proposal's time-share attribution
  and decided the H1/H4 branch. `scripts/attribute_specialization_share.py`
  parses Spark profiles and partitions server-thread self weight by the nearest
  enclosing leaf command family, with macro argument construction
  (`FunctionCommand$2.arguments` / `getArgumentTag`, including the
  `DataCommands.getSingleTag` helper) separated from `data` commands,
  `ServerFunctionManager.execute` resetting function-body attribution,
  `ContinuationTask` marking runtime forks, and blocking syscall /
  `Thread.sleep` / `park` samples split out as idle. Fresh Spark captures:
  Vein Miner side 6 with the compiler off (19,960 sampled weight, 215/215
  work), Spawn Animations 1.11.6 on the vanilla server (11,876, 24 actors), and
  Dynamic Lights 1.4.6 with the compiler off (29,516, 26 markers). Wall shares are 7.1% idle / 88.5% function time / 27.4%
  macro-argument / 58.7% addressable leaf for Vein Miner, 87.4% / 3.1% / 0% /
  1.3% for Spawn Animations, and 60.3% / 9.7% / 0% / 0.6% for Dynamic Lights;
  active-tick shares are 95.2% / 29.4% / 63.2%, 24.6% / 0% / 10.4%, and 24.4%
  / 0% / 1.6%. Runtime forked samples are 0.0–0.2%, so H1 is dead on these
  packs: the hot Vein Miner `execute` chain is non-forked and its cost is macro
  argument construction. H4 is the only >15% pool. The existing selective
  macro mechanism already covers the shape: a side-6 diagnostic recorded
  215/215 work, 11,701 attempted / 11,701 used calls, and zero unsupported
  providers, entity paths, storage sources, missing custom data, resolution
  fallbacks, or missing keys, so no code extension is needed. The batch also
  corrected the census (macro-body `$` normalization, `scoreboard players
  remove`, inner-`execute` calls): Vein Miner 266 adjacent tick commands in 27
  runs, Spawn Animations 165 in 36, Dynamic Lights 80 in 19, Everything Clings
  8 in 2, superseding batch 22's 250/143/14. PERF-017's fused arm set
  `FC_SELECTIVE_MACRO_ARGUMENTS=false`, so it did not test the shipped default;
  the 126.7 ms selective-macro diagnostic tick query is not a timing
  comparison. No default-on status or matrix row changed. The next step was a
  predeclared compiler-off vs selective-macro campaign on Vein Miner side 6.
  At batch 23 the runner forced the hit counter on its selective timing arm;
  batch 24 fixed that and predeclared the campaign (see the batch-24 entry).
  See the
  [benchmarks record](../benchmarks/README.md#time-share-attribution-and-the-h4-decision-2026-11-09).

- Batch 26 ran the predeclared H4 screening on Vein Miner 5.3.0 side 6 (plain
  Fabric stack, native event, no Spark, seed 26871031) under the wired
  quiet-window gate (observed 1-minute load 3.946). The activation diagnostic
  intercepted 11,753 attempted and 11,753 used macro calls with zero fallback
  counters (215/215 work), and all five counterbalanced pairs held exact
  workload parity with no noisy arms. Median event completion change is
  −30.03% with the exact 93.75% interval −32.64% to −21.27%
  (`screening_only`, `no_regression_holds`); the post-event `tick_average_ms`
  median is −25.03% (−30.62% to −2.60%). The interval lies entirely beyond the
  predeclared 15% gate, so the predeclared ten-pair confirmatory (same seed,
  `--minimum-gain-percent 15`, event completion primary) is next. No
  default-on status or matrix row changed. See the
  [benchmarks record](../benchmarks/README.md#time-share-attribution-and-the-h4-decision-2026-11-09).

- Batch 25 wired the harness's declared host gate into
  `run_veinminer_campaign.py`, which previously had none: the campaign start
  waits for the declared quiet window (1-minute load at or below 4.0, recorded
  as `quiet_window`; a give-up is a recorded failure, never a silent start
  under load), every arm is preceded by an inter-run settle so sequential
  server boots do not ramp the load (the batch-19 diagnosis), each arm records
  its settle outcome, start load, and `noisy_by_declared_rule` verdict under
  `host`, and a noisy arm is repeated once with both results retained in
  `noisy_arm_repeats`, matching the bytecode-vs-fused campaign's rule. The H4
  campaign has not run; the host's 1-minute load was 53.69 when batch 25
  landed, so the quiet-window gate correctly blocks a start.

- Batch 24 predeclared the H4 real-workload campaign and fixed the Vein Miner
  campaign runner's timing arm. `run_veinminer_campaign.py` no longer forces
  the selective-macro hit counter on its timing arms; both arms are
  uninstrumented, and a one-time metrics-on activation diagnostic (recorded as
  `activation_diagnostic`) proves the fast path fires and supplies the
  campaign's selective-macro counters. The gate is fixed before the first arm:
  compiler off vs the shipped `selective_macros` default on Vein Miner 5.3.0,
  Fabric stack, side 6, native event; primary metric
  `operation_completion_seconds` with a 15% minimum median reduction and the
  95% exact paired interval entirely beyond it; post-event `tick_average_ms`
  reported alongside as corroboration only; five screening pairs then a
  predeclared ten-pair confirmatory campaign; seed 26871031; exact workload
  parity in every pair; the declared quiet-window host gate.
  `tests/test_veinminer_campaign_runner.py` (10 tests) pins the uninstrumented
  arm construction and the activation gates. No default-on status or matrix
  row changed. The campaign has not run; it waits for a quiet host because
  PERF-001 showed this shared host's fresh-JVM variance can block a 5% gate.
  See the
  [benchmarks record](../benchmarks/README.md#time-share-attribution-and-the-h4-decision-2026-11-09).

- Batch 17 closed STATE-004 with the item-modify slot edges using the
  batch-10 confirmed modifier id (fixture state_item_modify_slot_edges:
  hotbar.0, hotbar.8 and weapon.offhand read back count=5 after
  st06_set_count, the cleared slot does not match, and a modify on the
  empty slot reports "The target does not have slot hotbar.5" without
  aborting the remaining lines; measured on the pinned vanilla server
  first and matched in all ten arms of the 2026-11-08 run, map
  0,0,0,0,0,0,64,64,64,64,96,96,96,96,112,112,112 with the complete fold 113
  at high quota). Every P0 semantic case is now recorded complete; only
  PERF-001 remains partial by its failed pre-declared baseline gate. The
  batch also removed a flaky tick-order key (the ordering fact now comes
  from a quiet sample). See the batch-17 record in the
  [coverage table](reference/features/command-coverage.md).

## Limits of this evidence

The wrapper-off server is a control for the wrapper transformation: it still
runs Fabric Loader, Fabric API, and the probe mod. The separate vanilla control
uses the fingerprinted official server jar with the fixture datapack. Its
observable oracle is scoreboard state plus RCON feedback; the vanilla process
is not instrumented for individual quota debits.

Beyond the specific direct-function, scoreboard, debug, and compatibility
fixtures above, the runtime check does not cover additional fork error paths,
concurrent or erroring reloads, all callback failure paths, or broad semantic
execution under compatibility mods. The ScoreAdd performance gate remains
open: callback and full-function timers include matched measurement overhead,
and the 5-million-action full-function comparison found ScoreAdd 14.8% slower
by median. CPU/allocation profiles remain single captures per arm. The
prototype remains disabled by
default. The Bellows 1.1.2 mob `home_pos` adapter passes the focused vanilla
differential cases while preserving the existing Bellows path for unrelated
data. The Bellows `VillagerDataFinalized` filtered no-op also matched vanilla
(`1b` after a successful set-to-`0b`) across all ten Bellows compiler modes,
including Moonrise 1.2.0. Other filtered NBT paths remain unverified and should
stay on vanilla execution until their own adapters and parity checks pass. A mod's divergent
result does not redefine the parity target. The three valid vanilla datapack
on/off pairs identify a recurring scheduled-function path, but their MSPT
variation is too high to estimate cost. Earlier mod-stack Spark files with no
sample trees must be recaptured before CPU comparison. Bellows stacks whose
workload output differs are excluded from datapack performance comparisons.

The probe output and temporary worlds are generated under ignored build/ and
run/ directories. Their results are summarized in maintained research notes;
they may be removed after an investigation. The ignored project Gradle cache
is currently retained because it contains the pinned 26.3 dependencies needed
for offline rebuilds in this environment. Remove leftover run/<id> directories
from interrupted server runs after confirming that no server remains active.

## Roadmap position and next evidence gates

The full phase roadmap and exit gates are in section 13 of the
[v0.1 plan](v1/plans/minecraft-function-compiler-research-and-implementation-spec-v0.1.md#13-engineering-roadmap-work-packages-and-deliverables);
the [test matrix](v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv)
tracks each concrete case. Phase 0 is partially complete. Its direct-function
baseline now includes nested return/recursion, zero/one/many fork selections,
fork limits 1–12, dynamic sequence-limit changes, scoreboard edge cases,
macro hash collisions and argument errors, fallback resumption, runtime syntax
errors, `/debug function` trace parity, fork overflow continuation, an
order-sensitive nearest fork-limit case, and focused Bellows selector/NBT
compatibility. Remaining Phase 0 work includes other selector-shape
combinations, exact vanilla cost-debit traces, additional callback failure
cases, broader compatibility-mod semantics, and filtered-NBT compatibility
beyond the verified Bellows `home_pos` adapter. Selected low-cap fork overflow
and feedback behavior now matches across the 16 vanilla, Fabric, Bellows, and
Bellows + Moonrise arms.
Phase 1 wrapper lifecycle covers five content/tag generations, removal and
re-addition, load/tick tags, macro fallback, tracing, and wrapper identity;
one held background reload now covers old-to-new function, tag, and macro
publication. A six-request out-of-order sequence also matches vanilla in all
  nine runtime modes; seven-or-more-request races and macro failure shapes
  beyond the staged-body/selective-argument case remain open.

Phase 0 now has full ten-arm state and RCON results for the 16 direct fixtures,
including nested return, recursion, dynamic quota changes, scoreboard edge
cases, and all zero/one/two/four fork-match counts across limits 1–12. Nearest
and furthest selector order is verified with order-sensitive scoreboard swaps
at fork caps 1–4; `random` and `arbitrary` selection visit all three actors in
direct and function paths. The low-cap fork cases additionally match across all
16 compatibility arms, including Bellows 1.1.2 and Bellows + Moonrise 1.2.0.
Debug function traces match for flat and nested functions. The wrapper-only
lifecycle probe also covers five body/tag reload generations,
removal/re-addition, load/tick tags, macro hash collisions, and macro errors.
Remaining semantic gates include other selector-shape combinations, additional
callback and failure paths, broader compatibility-mod execution, and
filtered-NBT behavior beyond the verified Bellows `home_pos` cases.
These gates remain before enabling an optimization. The ScoreAdd prototype was
implemented as an explicitly disabled research candidate; its narrow fixture
parity check does not waive any remaining baseline or compatibility gate.

For profiling, repeat PERF-010 with randomized order and a second scenario that
adds movement or entity activity, then recapture the compatible Fabric and
mod-stack arms with the corrected all-thread runner. Repeat the Blastback
no-TNT ScoreAdd pairs on selected mod stacks and add entity-rich eligible
workloads; keep the TNT event profile gated on source-volume restoration. Add
datapack-off controls for the new Fabric/Lithium/Lithium+Moonrise pairs. Spawn Animations now has a
six-second all-thread vanilla burst pilot: 24 zombies remained, six were in its
active state at sample start and none at the end; 47 thread nodes include 288
ms weighted in `ServerFunctionManager.execute`. This validates a transient
function path, not a stable cost estimate. Everything Clings loads but its
controlled entity population fell during every pilot, so its profiles are not
comparison evidence. Bigger Every Kill is rejected because its exact archive
fails 26.3 registry loading. Blastback Hotfix 3 loads and produces a sampled
TNT function path, but the default 1-TNT scenario still had 3,273 saved-block
markers and a restore job after a 180-second capture plus a five-minute drain;
the full region comparison failed. It is not valid for comparison profiles
until the restore completes. A separate no-TNT dispatcher pilot verifies one
real ScoreAdd command in `erb:runtime_tick`; its two paired captures show
matching tick counters but are too short and lightweight for a performance
decision. Incendium is excluded under the upstream AI-project restriction.
PERF-002 now has matched callback and function-queue server-thread timers. The
full-function comparison does not establish a gain and includes timer overhead
that has not been independently calibrated. The shared [benchmarking
protocol](benchmarking.md) now separates semantic parity, path activation,
workload integrity, unprofiled primary timing, and Spark attribution. Its
paired-analysis helper reports an exact order-statistic interval for the
median paired change and its achieved coverage; five-pair runs remain screening
pilots, and practical gain thresholds are selected per optimization before
confirmation. The Lithium+Bellows 1.1.3 selective-macro threshold is 15% faster;
its fixed 23-pair Vein Miner confirmation is complete. All 46 arms passed exact
workload parity (215 blocks and 1,952 `#head` increments each). Median paired
event completion was 19.27% faster; 21 pairs were faster and 16 met the 15%
threshold. The pair range was −46.80% to +45.98%, and the 96.531% exact median
interval was −27.09% to −13.03%. This supports a faster median but does not
establish the preselected 15% minimum; the decision is inconclusive for
promotion and the candidate remains disabled.
PERF-012 now has a sustained controlled fixture modeled on Vein Miner's queue:
256 marker entities, distinct changing macro arguments, and a 216-entry
coordinate frontier per entity. Two complete smoke pairs and four pairs from
an interrupted five-pair campaign pass exact vanilla work parity. Across
those six exploratory pairs, the median active-tick-average change is
−82.25%, with a 96.875% exact median interval from −86.57% to −1.81%. It does
not establish the selected 15% minimum gain, and the interrupted campaign has
no standalone performance decision. The confirmatory campaign that removed
the interruption ran on 2026-11-09 under a declared quiet-host precondition:
ten counterbalanced pairs on lb113 with seed 26871031 and the predeclared 15%
minimum gain, exact vanilla work parity in every pair, exact activation
(54,528 selected argument calls), and no noisy arms. The primary
active-tick-average median paired change is −81.72% with a 97.85% exact
interval of −82.98% to −80.58% (per-pair range −83.45% to −80.15%) — decision
`meets_threshold`, no-regression decision `no_regression_holds`; the P95
agrees (−81.15% median, interval −83.63% to −77.89%). Selective macro
arguments therefore has a cleared promotion-gate campaign on the sustained
workload in addition to the event-completion campaigns, and since
`selective_macros` is the one default-on optimization the shipped default's
no-regression floor now holds there as well. Scope: one
synthetic-but-Vein-Miner-shaped workload on the lb113 stack (256 marker
entities, changing macro arguments, a 216-entry coordinate frontier per
entity); the other stacks' event-completion campaigns stand as recorded.
Historical PERF-011 event times had Spark sampling active; new primary
campaigns use the no-Spark arm.
PERF-016 now supplies the adjacent-eligible fused-region workload. The checked-in
`tests/fixtures/function_compiler_fused_sustained` fixture applies 5,000
contiguous eligible adds per active tick, and
`scripts/run_fused_region_sustained.py` drives it through mod-free vanilla,
same-stack compiler-off, a separate activation diagnostic, and counterbalanced
paired timing arms with no Spark and no compiler counters. The confirmatory
10-pair Fabric campaign passed exact workload parity in every arm (5,000 adds
per active tick) and exact activation (94 regions compiled at load; one region
executed per active tick, matching the active tick count). Its workload-
attributable tick average (active-phase `/tick query` median minus the same
server's post-workload idle median, aggregated as the median of five sampled
windows per arm) has a −19.72% median paired change with a 97.85% exact
interval from −30.30% to −12.90%. That interval overlaps the pre-declared 15%
minimum gain, so the campaign decision is inconclusive and `fused_regions`
stays disabled by default. A second confirmatory campaign, rerun on
2026-11-09 under a declared quiet-host precondition (the runner starts only
once the 1-minute load average is ≤ 4.0; no arm was noisy and no rerun was
needed), reproduced the shape: exact workload parity in every arm, exact
activation (674 regions executed over 674 active ticks, 142 compiled, ~3.37M
specialized commands), a −15.64% median with a 97.85% exact interval of
−29.27% to −3.23% — still `inconclusive` at the preselected 15% minimum,
with the no-regression floor holding in both campaigns. The recorded next
action is a larger-pair campaign on an idle or dedicated host whose pair
count would be declared from the screening spread, never from the outcome. The 5-pair screening pilot (single-window design)
had a −22.86% median and a −86.55% to 0.00% interval and is retained as
screening only. Full evidence, gates, limitations, and next actions:
[PERF-016 report](../benchmarks/PERF-016-sustained-fused-region-active-tick.md).
PERF-017 is the first real-datapack fused-region measurement, on the pinned
Vein Miner 6×6×6 native event: ten counterbalanced pairs with exact workload
parity (215/215 blocks, 1,952 `#head` increments) and confirmed activation (105
regions compiled; a separate metrics-on diagnostic measured 303 region
executions and 16,833 specialized commands per event). The paired
event-completion median is +0.69% with a 97.85% exact interval from −3.92% to
+2.74%, so the fused engine delivers no measurable gain on this workload and
the decision is `does_not_meet_threshold`. The fused-region real-world gate
therefore stays open, and `fused_regions` remains disabled by default. See
[PERF-017 report](../benchmarks/PERF-017-veinminer-fused-region-campaign.md).
Bellows 1.1.2's compiler-off Vein Miner workload fails on Bellows,
Lithium+Bellows, and Lithium+Bellows+Moonrise 1.2.0. On Bellows 1.1.3,
Bellows-only 4×4×4 and Lithium+Bellows 6×6×6 native controls pass. A separate
two activation diagnostics counted 9,546 and 9,547 selective-macro hits in
the Lithium+Bellows event. Five no-Spark screening pairs show an −18.83% median completion
change, but the 93.75% interval is −20.62% to +24.37%. The fixed 23-pair
confirmation now supports a faster median but does not meet the 15% threshold.
A separate ScoreAdd screen passes exact parity but has a +3.60%
median event-time change and a +91.11% slower outlier; its interval is too wide
for a regression claim. Bellows 1.1.3 + Moonrise 1.2.0 passes the focused macro
fixture and native Vein Miner control; its five-pair selective-macro screen has
a −20.11% median event-completion change and a −36.67% to +7.01% interval, so
no confirmatory gain is established. Moonrise 1.2.1 remains startup-incompatible
with Bellows 1.1.3.
The Fabric-only
campaign shows no robust ScoreAdd gain; Fabric+Lithium and
Fabric+Lithium+Moonrise medians trend slower, but wide ranges and the temporary
Moonrise diagnostic mixin mean neither establishes a reliable causal
regression. No tested Vein Miner stack shows a real-world ScoreAdd speedup. The
direct-ScoreAdd workload and Vein Miner callback-accounting requirements are
satisfied on the existing stacks, including the new Bellows 1.1.3 native event
and ScoreAdd screen; neither prototype shows a reliable gain on this stack. A
2026-11-03 static screen found adjacent candidates in several pinned packs, but
none has runtime-confirmed specialization or a measured real-world
fused/bytecode comparison. Keep ScoreAdd disabled and pause expansion of
that optimization until profiling identifies a costly target.
PERF-005/006 show parity on controlled selector/NBT fixtures but no compiler
sample reduction. Continue backend comparisons only on workloads with eligible
commands. PERF-004 found emitted bytecode slower than fused interpreted on the
measured static fixture; no backend promotion is justified. The fused-region
queue-timing gate shows lower medians across two randomized sets, but does not
close the real-world region-performance or full parity gates.
