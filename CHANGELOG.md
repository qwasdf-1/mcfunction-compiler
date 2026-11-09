# Changelog

## Unreleased

- Scope the compiler-widening decision as a proposal (batch 21).
  `docs/v1/plans/compiler-coverage-widening-proposal-v0.1.md` records what the
  measurements already establish (selective macro arguments is the one
  cleared-gate, default-on mechanism at -81.72% sustained and -22% event
  completion; fused regions inconclusive at -15.64% with the interval uncertified
  and flat on the real Vein Miner workload; ScoreAdd slower everywhere it fires;
  bytecode refuted against fused; the predicate family measured with no sample
  reduction), the diagnosis the numbers support (the fuser's eligibility
  excludes forked contexts, which is where real selector-heavy tick functions
  spend their work, and ScoreAdd covers only literal fake holders), and four
  candidate hypotheses with falsifiable predictions, code surfaces, and the
  campaign that would decide each: H2-first a metrics-only inventory of
  addressable specialized work across the pinned real packs (days, no behavior
  change, ranks which pack each candidate would run on), H4 extending the one
  mechanism that has already cleared its gate, H1 fusing across the fork
  barrier (highest value, highest correctness risk, gated behind the ten-arm
  matrix), and H3 storage-holder ScoreAdd deprioritized because the mechanism
  has never shown a gain where it fires. The proposal is input to a decision,
  not a plan of record: roadmap step 4 stays open until one of its candidates
  produces a campaign decision. Registered in `docs/v1/plans/README.md`.

- Extract the engine-agnostic harness into a version-pinned sibling package
  (batch 20, roadmap step 6). `mc-mods/mc-tooling/mc-harness` v1.0.0 now owns
  the shared harness machinery that had been copied per project: the pinned
  26.3 Fabric mod-stack matrix (`mod_stacks`), the exact sign/order-statistic
  paired-campaign analysis (`paired_stats`), the server lifecycle - RCON
  clients including the split-response-draining variant, pinned server-jar
  location with SHA-256 verification, Mojang packet-report extraction, RCON
  readiness, and server-property helpers (`server_lifecycle`) - the
  counterbalanced-campaign primitives (`campaign`: port reservation, player
  connect with transient-close retry, score reads and workload waits, tick-query
  parsing, median windows), and the host gate (`host_gate`: the declared
  quiet-window precondition, the per-arm noise rule, the inter-run settle).
  The function-compiler runtime probe, both sustained campaign runners, the
  bytecode-vs-fused campaign, the Vein Miner campaign, and the PERF-001
  baseline campaign now consume it by path with an import-time version
  assertion, so a harness change cannot reach a recorded campaign unannounced;
  their duplicated local copies of these helpers were removed, and
  `paired_benchmark_analysis.py` was deleted (its consumer tests now
  run against the harness copy unchanged). Per the project guide the headless
  protocol client stays project-owned and pinned to 26.3 protocol 777
  (`tests/runtime/player_bot.py`), and the harness receives the client classes
  by injection, so no shared-kit change can re-target a live probe. Verified:
  the two-arm runtime probe smoke (mod-free-vanilla ↔ wrapper-on) passes
  end-to-end on the rewired imports, all 54 Python tests pass (including the
  new harness pin suite asserting the version, the wrapper bindings, the
  project-owned bot, and the workspace registration), the doc boundary check
  passes, and the docs link test passes with the campaign references rewired
  to the harness. Found and reported (not fixed here): a pre-existing
  IndentationError in `scripts/run_memory_load_analysis.py` (orphaned code
  after a return, line 448) that predates this batch and leaves the script
  unrunnable.

- Rerun the host-blocked campaigns under quiet-host conditions and record
  the outcomes (batch 19). PERF-001's baseline campaign ran attempts 4 and 5:
  attempt 4 (unchanged constants, quiet-start driver at 1-minute load <=
  4.0) failed the pre-declared gate at CV 0.070 with run medians 0.89-1.10
  ms - the JIT fix had removed the outliers; attempt 5 declared an inter-run
  settle from the diagnosed self-induced load ramp, every run started at
  load 3.55-3.99, and the CV was still 0.063 (medians 0.84-1.03 ms). That
  is the definitive diagnosis: the residual spread is intrinsic fresh-JVM
  variance at sub-millisecond scale, not host contention, so the gate is not
  reachable by waiting on this shared host; PERF-001 stays partial with its
  next action recorded (an idle/dedicated host or an execution-adjacent
  metric). PERF-016's fused sustained campaign reran screening and
  confirmatory under the quiet precondition: exact workload parity and
  activation in every arm (674/674 regions, 142 compiled, ~3.37M
  specialized commands), no noisy arms, and a -15.64% median with a 97.85%
  exact interval of -29.27% to -3.23% - decision `inconclusive` at the
  preselected 15% minimum, no-regression floor holding, fused_regions
  stays disabled. The quiet-host evidence reproduces the no-regression floor
  and a point estimate inside the first campaign's interval but confirms
  ten pairs cannot certify the gate. PERF-012's selective-macro sustained
  campaign reran under the same precondition and CLEARED its gate: the
  confirmatory phase (lb113 stack, ten counterbalanced pairs, seed 26871031,
  predeclared 15% minimum gain, no noisy arms, exact vanilla work parity and
  exact activation in every pair) measured an active-tick-average median of
  -81.72% with a 97.85% exact interval of -82.98% to -80.58% (per-pair range
  -83.45% to -80.15%; P95 median -81.15%, interval -83.63% to -77.89%) -
  decision `meets_threshold`, no-regression decision `no_regression_holds`;
  the screening phase recorded -79.58% with interval -82.88% to -78.01%.
  Selective macro arguments therefore has a cleared promotion-gate campaign
  on the sustained Vein Miner-shaped workload in addition to the
  event-completion campaigns that promoted `selective_macros=true`, so the
  one default-on optimization's no-regression floor now holds on both
  workload families. Scope recorded: one synthetic-but-Vein-Miner-shaped
  workload on the lb113 stack.

- Close the last coverage row, BC-06, with the pre-declared paired
  campaign, which measured the row's bytecode win claim as refuted (batch
  18). `scripts/run_bytecode_vs_fused_campaign.py` compares the canonical
  fused-interpreted and bytecode-emitted arms (wrapper and ScoreAdd
  specialization on in both, only the region prototype differing) on the
  declared 5,000-add sustained workload, with counterbalanced pairs, a
  predeclared seed, and the shared exact-median interval analysis.
  Activation diagnostics passed in both arms: 674 regions executed over
  674 active ticks each, 142 regions compiled, ~3.37M specialized
  commands inside the region, the other backend's counters at zero.
  Screening (five pairs) fixed the design at a +20.8% bytecode-slower
  median; the confirmatory phase (ten pairs, same seed 26871050,
  predeclared 5% minimum gain) measured bytecode 10.4% slower than fused
  at the paired median with the exact 97.86% interval 3.85% to 33.33%
  slower - decision does_not_meet_threshold, no-regression decision
  regression_proven; raw active-tick and p95 metrics agree in sign
  (+10.8% / +12.5%). The row's text records the measured finding, the
  matrix gained case BC-06, and the table is now **92 rows: 92 covered
  (R), 0 partial (P), 0 missing (—)** - fully covered, with PERF-001 the
  one matrix case still partial by its failed pre-declared baseline gate
  on this host. No default-on status changed: the bytecode backend stays
  gated, and this batch establishes it is not a performance win over
  fused interpretation on the declared workload.

- Close the last partial P0 semantic case, STATE-004, with the item-modify
  slot edges (batch 17). The case's remaining half was blocked at recording
  time on a confirmed 26.3 item-modifier id; batch 10 confirmed the
  datapack-defined `function_compiler_probe:st06_set_count` (count=5), so
  the half is now measured. New fixture
  `state_item_modify_slot_edges` replays the four slot edges (hotbar.0, the
  last hotbar slot, the offhand slot, and a cleared slot that must not
  match) through `item modify`, read back with `execute if items` against
  the probe player: measured on the pinned vanilla 26.3 server first, all
  three real slots read back count=5 (fold 64+32+16) and the empty slot
  does not match (+1, fold 113 at high quota), with a modify on the empty
  slot reporting `The target does not have slot hotbar.5` without aborting
  the remaining lines; the full ten-arm run of 2026-11-08 matches the
  0-16 map `0,0,0,0,0,0,64,64,64,64,96,96,96,96,112,112,112` exactly in
  every arm (the modify half costs more quota than the replace half, so
  the final +1 case fires only at the high-quota trace). Every P0 semantic
  case in the matrix is now recorded complete; only PERF-001 remains
  partial, by its failed pre-declared baseline gate (batch 16). The batch
  also found and removed a flaky harness key: the tick-order facts raced a
  real `#minecraft:tick` between two score reads, so the ordering fact now
  comes from a quiet sample (counter, observer, counter again, accepted
  only when the counter reads are equal), and the lifecycle comparison's
  error message now carries the differing keys.

- Run the pre-declared PERF-001 baseline campaign and record its failed
  gate (batch 16). `scripts/run_perf_001_baseline.py` runs seven fresh boots
  of the pinned, hash-verified official 26.3 server over the fixed
  5,000-line scoreboard fixture, verifies each run's exact final score, and
  gates a pre-declared run-median CV <= 5% with a declared host-noise rule
  and a JFR profile on the final run. Three campaigns were run and all
  three failed the gate on this host: CV 0.375 (50 warmup / 300 measured
  calls), 0.276 (same constants), and 0.275 (350 warmup / 1,000 measured,
  declared from the diagnosed variance source - 50 warmup calls leaves a
  fresh server's JIT far from tiered-compilation steady state), with the
  host load rising 6.4 -> 12.5, 5.4 -> 14.3 and 6.2 -> 16.6 during the
  campaigns and the run medians not tracking the load cleanly. The
  campaign now exits nonzero on its own gate failure. Recorded next action:
  rerun the identical pre-declared campaign on an idle host or under a
  tighter declared load precondition, or replace the RCON round-trip metric
  with an execution-adjacent measurement. PERF-001 stays partial and no
  throughput or baseline claim is made - the negative outcome is recorded
  data.

- Extend the PERF-001 baseline campaign record with attempts 4 and 5, and
  keep the pre-declared gate failure as the case's verdict. Attempt 4
  (unchanged constants, quiet-start driver at 1-minute load <= 4.0) failed
  the gate at CV 0.070 with run medians 0.89-1.10 ms - the earlier JIT fix
  had already removed the 2.4-2.9 ms outliers. Attempt 5 declared an
  inter-run settle from the diagnosed self-induced load ramp: every run
  then started at load 3.55-3.99, and the CV was still 0.063 (medians
  0.84-1.03 ms), which is the definitive diagnosis - the residual spread
  is intrinsic fresh-JVM variance at sub-millisecond scale, not host
  contention, so further attempts on this shared host cannot clear the
  pre-declared 5% gate by waiting. All five attempts, their per-run
  server logs and the JFR profiles are retained in
  build/benchmarks/PERF-001/, and the campaign exits nonzero on its own
  gate failure. PERF-001 stays partial; its next action is an idle or
  dedicated host, or an execution-adjacent metric. No throughput or
  baseline claim is made.

- Close the last two P0 selector-shape partial cases and fix the fork-limit
  defect they exposed (batch 15): SCORE-007 and QUOTA-009. Measured on the
  pinned vanilla 26.3 server first, then asserted in the full ten-arm run
  of 2026-11-08: scoreboard operations now have execute-store callback
  coverage (`execute store result` around an operation stores the
  operation's new target value, `execute store success` stores 1, a
  zero-match target operation stores 0 and creates nothing, a divide-by-zero
  operation stores 0 into both callbacks while the target keeps 7); and the
  fork modifier's selection surface gained a type-filtered selector with a
  same-tagged decoy, an all-outside distance filter, and a filtered
  distance subset, each swept over fork caps 1-12 with the arm maps
  compared exactly against vanilla. While writing these fixtures the run
  found a shipped-code defect: the compiled fork in
  `InlinedForkingCommand` checked `entities > forkLimit`, so a fork limit
  equal to the number of selected entities executed every branch one cap
  earlier than vanilla. Vanilla's fork budget includes the parent context -
  measured for N=1/2/3 selected entities in both the direct and the
  function path: below N the direct command reports the fork-limit error,
  at exactly N it runs no branch with no feedback, at N+1 or above all
  branches run - so the compiled fork now returns without forking at
  `entities >= forkLimit` and the now-unreachable
  `ERROR_FORK_LIMIT_REACHED` throw and its import were removed. The
  distance shapes also pin the world spawn first, because the `distance=`
  anchor is the command source at the randomized world spawn (the same
  unscoped fixture measured 1 in one fresh world and 101 in another). Only
  PERF-001 and STATE-004 remain partial, plus the BC-06 campaign row. No
  default-on status changed; the code change is a correctness fix toward
  vanilla parity, not an optimization.

- Close five partial P0 matrix cases by measuring the lifecycle-tag edges
  (batch 14): HOOK-002, HOOK-003, HOOK-004, HOOK-006 and HOOK-008. Measured
  on the pinned vanilla 26.3 server first and asserted in the full ten-arm
  run of 2026-11-08 with the `--concurrent-resource-reload` and
  `--whole-resource-reload-failure` probes: a tag listing the same member
  twice invokes it exactly once (vanilla collapses duplicate entries, the
  observable half of the row's no-duplicate-artifact oracle); a tag member
  naming an absent function fails the whole tag load, so invoking the tag
  reports `Can't find any functions for name ...` and the member never runs;
  a second datapack contributing to #minecraft:load runs its member once per
  reload, always after the first pack's member, recorded by a read-only
  copy of the shared count; a second #minecraft:tick member copies the
  accumulated count after the first member, pinning intra-tag order and
  once-per-tick invocation; the load and tick members' own command traces
  match vanilla exactly through /debug function with deterministic holders;
  and the concurrent reload overlap probe now runs a seventh queued request,
  with the first held while six newer generations publish in order
  (load counts 6 -> 12) and the held first publishing last (13), the forced
  whole-resource failure retaining the prior generation at 13. The batch
  also corrected a stale harness expectation: the concurrent macro
  specialization count advances 14 rather than the previously asserted 6,
  because the staged macro body carries two ScoreAdd-specializable lines and
  each publication recompiles both (the per-line doubling the DataStore and
  bossbar counters already record); the main-level load-count gates gained
  the seventh step. Four partial P0 cases remain (SCORE-007, QUOTA-009,
  PERF-001, STATE-004) plus the BC-06 campaign row. No default-on status
  changed and no performance claim is made - this batch is correctness and
  coverage only.

- Close ten partial P0 matrix cases by completing the shared
  callback-context x child-outcome matrix (batch 13): HOOK-001, HOOK-005,
  HOOK-009, SCORE-009 and CTRL-001/002/003/005/006/007. The common open end
  was "other return/error callback combinations"; the case oracles were
  enumerated as the six function-callback contexts (plain nested, `return
  run function`, `execute if function`, `execute unless function`, `execute
  store result/success function`) crossed with three child outcomes (return
  value, `return fail`, syntax exception), of which 15 of 18 cells already
  had ten-arm fixtures. The three missing cells were added as fixtures
  `function_compiler_probe:cbx_return_run_fail`, `cbx_return_run_fail_child`,
  `cbx_nested_fail` and `cbx_unless_success`, each asserted over the 0-16
  sequence-limit sweep with `/debug function` traces and run in the full
  ten-arm matrix of 2026-11-08 (mod-free vanilla, wrapper-off/on,
  score-add-on, instrument-only, score-add-timed, fused-interpreted,
  bytecode-emitted, bytecode-compile-failure, selective-macro-arguments),
  which matched vanilla exactly for direct-function state, results, traces,
  reloads and forks including all four fixtures. Measured 26.3 semantics
  recorded by this batch: a failed `return run` reports `Function ...
  returned 0`, discards the child's pending fused tail and ends the parent
  frame, discarding the parent's own pending `+1000` tail (score 31); a
  plain nested child that fails discards only its own tail while the
  parent's `+1000` tail resumes once (score 2031, two executing regions in
  fused and bytecode); and a child returning a value makes `execute unless
  function` false while the parent's region resumes (score 2002). Two
  harness defects were found and fixed in the process: the initial trace
  event-count gates were transcribed from the server's `Traced N
  command(s)` response, which excludes the child's `return fail`, so the
  harness now reads the trace file's `[C]` lines directly; and `run_case`
  gained an `expected_backend_regions` parameter so a case may assert its
  measured region count instead of only the single-region shape (the
  sibling cases carry lone-add children and therefore one region). Matrix
  cases HOOK-001, HOOK-005, HOOK-009, SCORE-009 and
  CTRL-001/002/003/005/006/007 are now recorded *complete*; that leaves
  nine partial P0 cases (HOOK-002/003/004/006/008, SCORE-007, QUOTA-009,
  PERF-001, STATE-004) plus the BC-06 campaign row. No default-on status
  changed and no performance claim is made - this batch is correctness and
  coverage only.

- Close the `MO-10` coverage row - the fork modifier under the pinned
  Bellows/Moonrise mod stacks - with a mod-stack probe that runs the full
  fork-order fixture (ordered nearest/furthest identity, the batch-11
  unordered-sort identity block, the cap sweep, and the
  candidate-freshness block) with the compiler enabled under three pinned,
  hash-verified stacks: `bellows113`, `bellows113-moonrise120` and
  `lbm113120` (lithium + Bellows 1.1.3 + Moonrise 1.2.0), each a fresh
  Gradle runServer. Every stack passed every fixture assertion, and each
  stack's recorded fixture result is exactly equal to the mod-free vanilla
  arm's recorded result from the batch-11 ten-arm run: Bellows's selector
  instrumentation and Moonrise's entity system rewrite change neither the
  arbitrary insertion-order resolution nor the random set semantics the
  fixture observes. The oracle is within-stack direct-vs-function parity -
  the modded server is its own reference, since a mod may legitimately
  change entity iteration order; the cross-stack equality is the recorded
  finding, not the oracle. The row's claim is scoped to the pinned stacks
  combining Bellows and Moonrise; c2me, ferritecore, bellows 1.1.2,
  Moonrise 1.2.1 and unpinned stacks are not claimed for fork semantics.
  Matrix case MO-10; row closed: MO-10. The table is now **92 rows: 91
  covered (R), 0 partial (P), 1 missing (—)**; the remaining row is BC-06.
  No default-on status changed and no performance claim is made - this
  batch is correctness and coverage only.

- Close the `MO-09` coverage row - the fork modifier's remaining selector
  shapes, the unordered sorts `sort=arbitrary` and `sort=random` - with new
  fixtures `mo09_fork_arbitrary_identity` and `mo09_fork_random_identity`
  plus an identity/freshness block in the harness fork-order fixture
  runner, verified across mod-free vanilla 26.3 and all nine Fabric
  runtime modes (ten arms) with the fork fixture result compared exactly
  against the vanilla arm. The oracle was pinned by measuring the pinned
  vanilla server first, and the measurement corrected the §11.2
  assumption that identity was unobservable: a two-branch
  `#fork_order_acc >< @s` swap chain with distinct actor values leaves a
  per-actor scoreboard fingerprint that decodes the selection order.
  Measured semantics: `sort=arbitrary` resolves candidates in entity
  insertion (summon) order - not position order, per a reverse-summon
  control - and is stable across repeated invocations, `/reload`, a
  server restart on the same world, and fresh worlds with different
  seeds, so it is asserted exactly (order (a, b) across trials, direct
  and function paths); `sort=random` is non-deterministic by design
  (24 trials covered all three candidate pairs 8/8/8, every trial
  exactly two distinct actors), so the row's claim for it is narrowed to
  per-trial set semantics plus a distinct-pair floor across trials
  proving the compiled fork delegates selection to vanilla's randomness.
  The fork cap includes the parent context: for a limit=2 selector cap 1
  reports the maximum-context error, cap 2 truncates silently, caps 3+
  fork both branches - the boundary QUOTA-009 recorded for the ordered
  sorts. Candidate-list freshness is asserted: killing a selected actor
  changes the next invocation's selection on both paths, and the
  canonical re-summon restores the pinned order. Cap fallback for the
  unordered sorts was already under QUOTA-009, which the row now cites
  alongside the new case. Matrix case MO-09; row closed: MO-09. The table
  is now **92 rows: 90 covered (R), 0 partial (P), 2 missing (—)**; the
  remaining rows are MO-10 and BC-06. No default-on status changed and no
  performance claim is made - this batch is correctness and coverage
  only.

- Close the `ST-06` coverage row - the `item modify` half of the gameplay
  item command family - with a differential fixture verified across
  mod-free vanilla 26.3 and all nine Fabric runtime modes (ten arms) with
  exact per-quota score parity, closing the row together with STATE-004's
  batch-6 `item replace` slot-edge half. The blocker had been a confirmed
  modifier id; measurement resolved it in three steps: the 26.3
  `minecraft:item_modifier` registry ships no built-in modifiers at all
  (`minecraft:set_lore` fails with "Can't find element ... in registry
  'minecraft:item_modifier'"); every id is datapack-defined at
  `data/<namespace>/item_modifier/<name>.json` as a single JSON object
  keyed by `type`, with the array form and the legacy `function` key both
  rejected by boot-fatal parse errors (what had earlier killed the probe
  server rather than merely rejecting the id); and with a well-formed file
  `item modify` returns result 1 on success, is idempotent in its result,
  and a store around it writes that result. Measured and recorded: a
  failing modify (a slot the target does not have) reports
  (success=false, result=0) to the store callback and does not abort the
  remaining function lines; an id the registry lacks is validated at
  command-parse time, so a function line referencing one fails the
  function load - the unknown-id edge is recorded in the fixture header
  rather than fixture-able; a malformed modifier file is boot-fatal for
  the whole datapack; and 26.3 mob equipment NBT lives at
  `equipment.mainhand` (no `HandItems`), materialising only once an item
  is placed. Specialization is proven by a new dedicated per-function
  item-command compile counter reading exactly the store-chain count (2)
  in the six compiling arms and exactly 0 in wrapper-off/on and
  selective-macro-arguments; bare item lines stay on the vanilla path and
  the fixture's `execute if items` conditions go through
  ItemPredicateParser. Matrix case ST-06; row closed: ST-06. The table is
  now **92 rows: 89 covered (R), 0 partial (P), 3 missing (—)**; the
  remaining rows are MO-09, MO-10 and BC-06. No default-on status changed
  and no performance claim is made - this batch is correctness and
  coverage only.

- Close the `ST-02` coverage row - the bossbar command family
  (`bossbar add/set/remove` and `get value|max|players` through the
  `StateMachineCommand` wrap) - with two differential fixtures verified
  across mod-free vanilla 26.3 and all nine Fabric runtime modes (ten arms)
  with exact per-quota score parity. The feasibility note expected a new
  RCON-feedback oracle type; measurement showed none is needed: bare
  `bossbar get <id>` is not a valid 26.3 form (the only getters are value,
  max and players), and each getter returns its value as the command result,
  so `execute store result score` folds bossbar state into the existing
  scoreboard oracle. Measured and recorded in the fixtures: `bossbar add`
  returns result 1 and fails on a duplicate id; `bossbar set value|max`
  returns the written number when the value changed and 0 with a
  nothing-changed failure otherwise (so the fixtures re-create fresh-bar
  defaults every iteration through a bare leading remove); a failing bossbar
  command does not abort the remaining function lines; `bossbar remove`
  returns 0 whether or not a bar was removed; and the unknown-bar edge is
  pinned by a store around a get on an absent bar writing 0 over the
  previous read's 43. Specialization is proven by new dedicated per-function
  bossbar compile counters, asserted at the store-chain counts (3 and 4) in
  the six compiling arms and exactly 0 in the rest; bare bossbar lines are
  not in the EXECUTE-stage parser list and stay on the vanilla path, like
  the other state-machine families outside tag/teleport/kill, and the
  set color/visible/name shapes have no 26.3 getter (client-rendered state),
  which the closure text scopes explicitly. Matrix case ST-02; row closed:
  ST-02. The table is now **92 rows: 88 covered (R), 1 partial (P), 3
  missing (—)**; the remaining rows are MO-09, MO-10 and BC-06, and the
  partial row is still ST-06's `item modify`. No default-on status changed
  and no performance claim is made - this batch is correctness and coverage
  only.

- Close the `MO-02` coverage row - the `DataStore` modifier around data
  commands (`execute store result/success storage <id> <path> <type> <scale>`)
  - with two differential fixtures verified across mod-free vanilla 26.3 and
  all nine Fabric runtime modes (ten arms) with exact per-quota score parity.
  A failing `data get` costs about eight quota points, so the success and
  failure halves are separate fixtures: `mo02_store_result` pins the scale, the
  `byte` type literal and the NBT tag suffix in one value ((byte)(200*2) =
  -112), and `mo02_store_failures` pins the measured failure semantics with
  exact `0L`/`0s` tag matches after seeding the path with 9. Specialization is
  proven by new dedicated per-function DataStore compile counters in probe
  status, asserted at least 2 in the six compiling arms and exactly 0 in the
  rest, because score parity alone is also produced by the vanilla fallback.
  Matrix case MO-02; row closed: MO-02. The table is now **92 rows: 87 covered
  (R), 1 partial (P), 4 missing (—)**; the remaining rows are MO-09, MO-10,
  ST-02 and BC-06, and the partial row is still ST-06's `item modify`. No
  default-on status changed and no performance claim is made - this batch is
  correctness and coverage only.

- Enabling that row exposed that the entire chained-modifier specialization
  pass had never executed at runtime. On 26.3, Brigadier's `ContextChain` gives
  every `execute ... run ...` command a trailing no-op modifier stage whose
  only node is `run`, and `parseModifiers` required a parser for every stage;
  no parser accepted `[run]`, so every chained command silently stayed on the
  vanilla path - including all the previously recorded `ScoreCondition`/
  `ScoreStore`/fork/claim rows whose parity a fallback produces trivially. The
  pass now skips the no-op `[run]` stage (only single-stage chains compile,
  because every parser requires the leading `execute` node) and charges
  vanilla's per-stage quota debits: one debit per modifier stage with a
  redirect modifier plus one per final source, a model that reproduces four
  independently measured quota maps exactly. The fixes that made the pass exact
  also corrected three latent, never-exercised defects: `DataStoreCommand` and
  `ScoreStoreCommand` double-fired the source result callback (the compiled
  entry's `ExecuteCommand`/`runExecutable` path already fires it once, matching
  vanilla); `ItemPredicateParser` double-inverted `unless items` (the vanilla
  redirect already applies the negation), which made every `unless items` line
  never fire; and the `fallbackChain.executeAll` fallback re-entered the
  wrapped command itself in a timing-only arm, so the wrapped commands' runtime
  gates now match the compile gate exactly. `DataStoreCommand` also now writes
  0 before rethrowing on any exception, matching vanilla's measured store
  semantics for result as well as success stores. The full ten-arm matrix
  re-verified every affected fixture against the vanilla-measured maps.

- Three measured findings changed the fixtures. `setblock` reports success 0 for
  an unchanged block ("Could not set the block"), so `ct02_store_specialized`
  resets the position to air before every store; without that reset, later quota
  iterations would assert the unchanged-block failure path. An `effect give`
  store under `execute store success` did not fit the 0-16 sweep (32 of its
  declared 48 by quota 16), so the second CT-02 case uses the
  accepted-`setblock` side, which complements ST-04's refused-`setblock` case
  instead of repeating it. A macro invocation with a missing key fails at
  expansion before any line of the callee runs, and a runtime command error
  inside a macro callee aborts neither the callee's remaining lines nor the
  caller; the CT-03 map records both.

- Correct the failing-read store semantics recorded by the storage batch. The
  earlier claim that a failing read "leaves the store unapplied" (DS-05 row,
  matrix case DATA-004, fixture header) is contradicted by measurement: vanilla
  writes 0 for a result store as well as a success store. The claim is
  corrected in all three places, and because `storage_store_and_errors`'s
  absent-path folds add 0 whether the store writes or skips, that sweep's later
  error cases are not observably taken - the falsifiable form of the claim now
  lives in `mo02_store_failures`. The batch-7 entry below remains as recorded
  history for its own numbers: §11 now reports 92 rows: 87 covered (R), 1
  partial (P), 4 missing (—).

- Correct the coverage table's generated row count. Every section separator ends
  in `R`, and the earlier closers counted those nine lines as data rows, so the
  batch-6 report said 101 rows / 91 covered / 9 missing where the table actually
  held 92 / 82 / 9. The same nine-line inflation affects the earlier changelog
  entries that say "101 rows" - each is nine too high in total, with the nine
  extra counted as covered. Those entries are left as recorded history rather
  than rewritten. The batch-7 closer excludes and normalises the separators; §11
  now reports **92 rows: 86 covered (R), 1 partial (P), 5 missing (—)**. The
  five remaining rows are MO-02, MO-09, MO-10, ST-02 and BC-06; the partial row
  is ST-06's `item modify`.

- Close the state-machine command rows with three differential fixtures verified
  across mod-free vanilla 26.3 and all nine Fabric runtime modes (ten arms
  including vanilla) with exact score-sequence parity. `state_effect_edges`
  reads the entity's own active effects, `state_setblock_edges` reads block
  states back with `execute if block`, and `state_item_slot_edges` reads the
  probe player's inventory with `execute if items`. Matrix cases STATE-002..004;
  rows closed: ST-03 and ST-04 outright, ST-06 for `item replace` with
  `item modify` recorded as still untested, because no 26.3 item-modifier id
  could be confirmed - neither `minecraft:set_lore` nor a datapack-defined
  `function_compiler_probe:probe_item_modifier`. The coverage table is now 101
  rows: 91 covered, 1 partial, 9 missing, and §11 is regenerated from the table
  rather than typed. The `P` entry is the first in the table's history, so §11's
  legend now explains what a recorded `Partial` proves.

- Five 26.3 behaviours were read from the server rather than assumed, and each
  one changed a fixture. An entity's active effects live at `active_effects` in
  snake case as `{duration, show_icon, amplifier, id}`; the pre-1.20.5 path
  `ActiveEffects[0].Amplifier` matches nothing. That list is **sorted by effect
  id**, not ordered by application, so the first effect fixture read two effects
  from one list and one of its digits was validated by the sort order rather
  than by a correct read - the fixture now keeps exactly one effect active at a
  time. The amplifier is a **signed byte**, so the command's maximum amplifier
  of 255 reads back as -1, which the fixture asserts. `effect give` refuses to
  **shorten** an active effect's duration as well as its amplifier, so a
  truncated sweep's leftover is harmless only because it is identical; a focused
  probe produced 80 against a longer-duration leftover and the fixture header
  now says so. A refused out-of-world `setblock` does **not** abort the rest of
  the function and `execute store success score` around it writes 0, which makes
  the refusal observable in a scoreboard, while `execute if block` at the same
  position aborts the command with an error and cannot be used as a negative
  predicate. The `effect clear` case is asserted with `execute unless data` on a
  path that no longer resolves.

- The quota budget, not the semantics, decided the effect fixture's shape.
  Clearing between cases left the last case unexecuted by quota 16 - the failure
  mode the oracle-health test exists to catch - so reading the amplifier and the
  duration from the same effect back to back removed a whole clear-and-give
  group and brought the final case in at quota 13. Charge is not uniform across
  lines: a two-predicate or `execute store` line costs more than a plain
  scoreboard line, so a long fixture silently drops its tail.

- A duplicate dict key silently overrode an encoded oracle. Encoding
  `state_effect_edges` added a second entry below the one it was meant to
  replace; Python keeps the last value in a dict literal, so the stale map stayed
  in effect and every arm failed against expectations nobody had updated. The
  loaded-module health checks could not see this, because importing had already
  collapsed the duplicate. `tests/test_runtime_probe_oracle_health.py` now
  parses the script with `ast` and fails on a repeated fixture key, verified
  against an injected duplicate.

- Correct the runtime-arm count recorded in the test matrix. The default matrix
  is **eight** arms; the full set is **ten** (nine Fabric modes plus
  mod-free-vanilla). Batch 6 quotes the count from the run actually made - all
  ten arms - rather than the phrase inherited from earlier rows.

- Clean generated build output once batch 6's evidence was recorded: probe
  reports and their temporary worlds under `build/reports/`, raw campaign output
  under `build/benchmarks/`, and the dev-run world under `run/`. The offline
  dependency cache (`.gradle-user-home`) and the compiled jar are kept, so the
  next runtime arm still builds offline. This freed roughly 200 MB.

- That cleanup was **too aggressive**, and the correction is recorded rather than
  hidden. Eleven maintained-documentation links pointed into the deleted trees:
  the exotic and redteam probe reports, the extreme-stress and memory-load
  artifacts, the datapack screening report, and four PERF-011 campaign files
  whose filenames embed pre-declared seeds. The repo's own doc-hygiene test
  failed on the first link, which is how it surfaced. Those citations are now
  durable prose naming the regenerating script, with the recorded verdicts kept
  as the citation; the PERF-011 note explicitly says the seeded campaign files
  must not be re-run to refresh them, because that would re-roll seeds on designs
  that are already decided. The architecture header now points at
  `docs/verification.md` instead of a dated report file, and
  `docs/verification.md` records where a compatibility-probe report is written
  and why the run id, not the file, is the durable reference.

- Refresh the v1 gate-status column in `docs/v1/plans/v1-production-roadmap.md`
  §6, which was dated 2026-11-04 and quoted two numbers batch 6 changed: the
  matrix is now 117 cases with 70 recorded complete and 19 partial (not 18 of
  98), and the coverage gate is now quantified - the table is enumerated (101
  rows: 91 covered, 1 partial, 9 missing), with the nine uncited rows and the
  partial row named.

- Close the last three client-packet-only coverage rows by **delegation contract**
  rather than by a differential oracle, which does not exist for them. `title`,
  `playsound`/`particle`/`stopsound` and the generic state-machine wrapper
  around them produce client packets only, so RCON cannot observe their effects.
  Accepted per the v1 plan as an explicit delegation claim, matrix case
  STATE-001; rows closed: ST-01, ST-05, ST-07. The table now records 89 covered,
  0 partial, 12 missing.

- Turn that contract into a measurement rather than prose.
  `function_compiler_probe status` now reports per-function specialization
  counters for three fixtures, asserted by a new `run_delegation_contract` pass
  in every runtime arm: a control fixture whose counters must be nonzero (so a
  zero reading on the others is evidence, not a broken counter), a
  selector-operand fixture, and the client-packet fixture, both of which must
  read zero in the compiled and executed directions. This is the falsifiable
  form of the claim batch 4 merely asserted - that the compiler declines
  entity-selector operands. Verified: 5 of 8 arms compile something (control=4)
  and report zero for both declined fixtures; `wrapper-off`/`wrapper-on` compile
  nothing and are recorded as not exercising the contract.

- Add `tests/test_delegation_contract_fixtures.py`, which checks the contract's
  wiring statically because the runtime check cannot: the status command must
  declare and report exactly the fixtures it checks, each fixture file must
  exist, the control must contain a specializable shape so its counter can move,
  the declined fixture must contain no fake holder at all, and the client-packet
  fixture must contain only client-packet commands. A renamed or emptied fixture
  would otherwise read zero and the contract would pass while proving nothing.

- Three findings recorded rather than smoothed over. (1) The contract check's
  first version failed on `wrapper-off`, which specializes nothing: an arm whose
  counters are all zero cannot be asked to prove a nonzero control. (2) The
  second version, gated on the `FC_SCORE_ADD_PROTOTYPE` flag, would have skipped
  `instrument-only`, which runs with the flag off yet still compiles four
  specialized commands - so the gate is the control's own reading, not the
  configuration. (3) The static test caught an ambiguous line in the declined
  fixture: a fake-holder target with a selector source, which the compiler
  declines only because of the source, so the fixture would have proven less
  than it claimed.

- Close four more coverage rows with selector-shaped scoreboard fixtures, all
  verified across mod-free vanilla 26.3 and the full ten-arm Fabric matrix.
  Four fixtures (`score_selector_mutation`, `score_selector_store`,
  `score_selector_operation`, `score_modifier_dispatch`) are invoked by name
  from `run_scoreboard_semantics`, each performing its own mutations and its own
  per-entity fold into one fake holder. Matrix cases SCORE-020..023; rows
  closed: SM-10 (multi-entity selector fan-out, including a limited selector),
  SM-13 (execute store with a selector target, creating each score), SO-07
  (operation fan-out onto a selector target and onto absent targets), SM-12
  (mutation in a modifier chain with a per-actor condition). Coverage table now
  101 rows: 86 covered, 0 partial, 15 missing.

- Record that these four rows are shapes the compiler *declines*, so their claim
  is about the fallback rather than an inlined evaluator, and that their
  expectations are derived arithmetically before the run confirms them rather
  than fitted to a failure message. Every derived expectation was confirmed
  exactly by the vanilla arm: 20, 20, 5636 and 60020.

- Close four more coverage rows with differential predicate fixtures, and fix
  a silent defect the batch first exposed in the harness rather than in the
  compiler. Four fixtures (`predicate_block_tag`, `predicate_block_state`,
  `predicate_item_stack`, `predicate_item_modifier`) run across mod-free vanilla
  26.3 and the full ten-arm Fabric matrix with exact score-sequence parity,
  adding matrix cases PRED-003..006 and closing PR-03, PR-04, PR-05 and MO-07.
  Coverage table now 101 rows: 82 covered, 0 partial, 19 missing.

- Add `tests/test_runtime_probe_oracle_health.py`, which checks the runtime
  probe's oracle table instead of a running server. It enforces that every
  registered fixture has an expectation (the runner returns early when
  `EXPECTED_SCORES` has no entry, so a missing entry is a fixture that can never
  fail), that no map is constant or all-zero, that each fixture's declared
  full-run value is reached at the top quota, and that the final case of each
  fixture is a branch that is taken.

- Record the truncation defect this batch found in its own fixtures. The quota
  sweep runs each fixture across `maxCommandSequenceLength` 0-16, and an
  `execute if items` line plus a two-predicate chain costs noticeably more of
  that budget than a block predicate, so the first drafts of three fixtures
  charged out mid-run and left their later cases unexecuted in every arm. That
  failure is invisible to the value comparison alone: a truncated tail of
  cases that take no branch scores the same as an executed tail. Every fixture
  now ends with a taken branch so its weight is an unconditional completion
  signal, and the new test enforces it.

- Note a 26.3 syntax fact confirmed against the vanilla parser rather than
  assumed: a count *range* in an item predicate is not `[count=1..]` or
  `[count=2..3]` (both fail to parse), nor `[count~1..]`; the range form is an
  SNBT object, `[count={"min":1,"max":3}]`.

- Run the first real-workload fused-region campaign (PERF-017) on the pinned
  Vein Miner 6x6x6 native event: ten counterbalanced pairs with exact workload
  parity (215/215 blocks, 1,952 `#head` increments), symmetric un-instrumentated
  arms, and confirmed activation (105 regions compiled; a separate metrics-on
  diagnostic measured 303 region executions and 16,833 specialized commands per
  event). The paired event-completion median is **+0.69%** with a 97.85% exact
  interval of **-3.92% to +2.74%**, decision `does_not_meet_threshold`. The
  fused engine is demonstrably active on a real datapack and produces no
  measurable gain there, so the fused-region real-world gate is closed rather
  than open and `fused_regions` remains disabled by default. Promotion would
  need a workload whose hot path is dominated by successful runs of specialized
  commands, which the current screen has not identified.

- Make `fused_regions` imply the scoreboard specialization pass and make the
  `score_add` disk flag effective when fusion is off. Previously
  `CompilerConfig.isScoreAddEnabled()` was dead code: `score_add=false` was
  ignored because the runtime default followed the master `enabled` switch.
  `FC_SCORE_ADD_PROTOTYPE=false` remains an explicit diagnostic override.
- Add `--adds-per-tick` to the PERF-016 sustained runner so the contiguous
  eligible block can be scaled without editing the checked-in fixture; the
  generated workload function is hash-recorded in the report.
- Add `scripts/screen_adjacent_regions.py`, a static tick-reachability screen
  for adjacent eligible runs in pinned datapacks, and record the screen of all
  19 pinned packs. The screen finds candidate runs in Blastback's generated
  block-state reader (32 adjacent `execute if block ... run scoreboard players
  set` commands per state table), Vein Miner's family detection (145 adjacent
  parsed candidates plus a one-time 19-add `@s` initialization), and Simple
  Timer's 36-command tick display/clock chain. Runtime activation and
  performance for these packs remain unmeasured; the screen is not proof that
  every command specializes.
- Complete three PERF-016 confirmatory campaigns on
  `tests/fixtures/function_compiler_fused_sustained`: Fabric at 5,000
  adds/active tick (10 pairs, median −19.72%, interval −30.30% to −12.90%),
  Fabric at a generated 20,000 adds/active tick (12 pairs, median −12.48%,
  interval −33.09% to +77.44%), and Lithium + Bellows 1.1.3 at 5,000
  adds/active tick (10 pairs, median −22.16%, interval −86.39% to −12.12%).
  Every arm passed exact workload parity and exact one-region-per-active-tick
  activation, and every interval overlaps the pre-declared 15% minimum gain, so
  all three are inconclusive and `fused_regions` stays disabled by default.
- Complete the pre-declared 16-pair PERF-016 campaign on Fabric at 20,000
  generated adds per active tick (seed 26873001, threshold 15%, parameters
  committed before the first arm). All sixteen pairs were negative with a
  −20.72% primary median, but the exact interval is −32.23% to −12.26% at
  97.87% coverage, so it does not clear the pre-declared minimum gain and the
  recorded decision is inconclusive; `fused_regions` stays disabled. The
  interval stayed wide because of per-pair spread rather than contaminated
  arms — the binding values are pairs 3 and 10, neither of them slow — and
  because sixteen pairs at 97.87% coverage select wider order-statistic ranks
  than twelve at 96.14%. Per the pre-declared consequence, no further attempt
  at this design is made on a seed re-roll; any next campaign needs a new
  pre-declaration whose rationale reduces variance.

- Re-run the 20,000-add Fabric confirmatory campaign (12 pairs, seed 26872001)
  behind a host-quietness gate, and record it as the fourth PERF-016 campaign.
  All twelve pairs were negative and no arm landed in the noisy run's 20–27 ms
  band (0 of 24 arms above a 16 ms median window, against 7 of 24 before),
  giving a −18.43% primary median with a −20.18% to −14.95% interval (96.14%
  coverage). The point estimate now clears the pre-declared 15% minimum gain,
  but the interval's upper edge misses it by 0.05 percentage points, so the
  campaign stays inconclusive under the decision rule as written and
  `fused_regions` remains disabled by default. The re-run confirms the noise
  diagnosis directly, and the host-state samples taken during it show bursts
  (max PSI cpu 12.79%) absorbed by the five-window median rather than by a
  perfectly quiet host.

- Diagnose the 20,000-add campaign's wide interval: it is workspace noise, not
  a compiler effect. The same fixture on the mod-free 26.3 server measures
  6.0–7.3 ms per window with GC pauses of ~1.5 ms every ~2.6 s, while the
  campaign's own mod-free vanilla reference arm measured 27.1 ms during the
  campaign and 6.4 ms in a quieter window. Injecting eight CPU-bound processes
  reproduces the inflated windows (5,000 adds: 2.2 → 3.6 ms; 20,000 adds:
  6.5 → 19.6 ms), and the host had only 39 MB of free swap, so other
  tenants' page-fault bursts also landed directly in the measurement. Add
  `scripts/diagnose_perf016_host_noise.py` so the workspace's noise floor can
  be measured before a campaign and contention can be reproduced on demand; a
  host-quietness gate is now a prerequisite for any attempt to separate from
  −15%, and folding it into the runner itself is the recorded next action.

- Run the pinned Engineering Auditor v1.5.0 pass-close review (119 findings:
  1 high, 97 medium, 21 low; 6 production, 113 tooling) and record per-finding
  dispositions in `docs/research/engineering-auditor-review-2026-10-29.md`,
  including the concrete follow-ups for the new `CompilerConfig.load` advisory
  and the new sustained-runner clone findings. No baseline or suppression added.
- Remove the fully merged and clean `feature/implementation-work` worktree; its
  branch held no commits absent from `main`.

- Extend the 21-arm compatibility matrix with NBT-predicate selector coverage:
  `compat_selector_nbt_match` and `compat_selector_nbt_no_match` pair a `Silent:1b`
  actor with a `Glowing:1b` actor inside a `dx/dy/dz` box, and all 21 arms
  (vanilla, Fabric, Bellows 1.1.2, Bellows 1.1.2+Moonrise 1.2.0, and
  Lithium+Bellows 1.1.3+Moonrise 1.2.0) select identical identities with
  `compatibility_parity_pass = true` (run `20261102T235411`). No previously
  recorded selector, NBT, scoreboard, callback-failure, or low-fork observation
  changed.

- Add `scripts/run_fused_region_sustained.py` (PERF-016): a paired no-Spark
  active-tick campaign that drives the checked-in adjacent-eligible
  `function_compiler_fused_sustained` fixture (5,000 contiguous fake-holder
  ScoreAdds per active tick), asserts exact `#fused` work parity with the
  mod-free vanilla reference, and proves path activation with
  `fused_regions_executed` equal to the active tick count.
- Record the PERF-016 fused-region campaign as inconclusive: the 10-pair
  confirmatory Fabric run passed exact workload parity and exact region
  activation in every pair, but its -19.72% median workload-attributable
  tick-average change has a 97.85% interval of -30.30% to -12.90% that overlaps
  the pre-declared 15% minimum, so `fused_regions` remains disabled. Full
  evidence, gates, limitations, and next actions are in
  `benchmarks/PERF-016-sustained-fused-region-active-tick.md`.
- Correct documentation claim drift: the fused-region feature reference and
  generated index no longer claim default-enabled promotion (the config default
  is `false` and no adjacent-eligible real workload had met the gate), the
  selective-macro reference now labels the 3-pair PERF-015 numbers as screening
  and cites the confirmatory 6-pair campaigns, the configuration reference
  documents the real fallback defaults, and README's fused-region heading and
  tick-time bullet match the promotion table.
- Regenerate the doc-hygiene ground-truth indexes after the status corrections.
- Establish the project documentation map, contribution conventions, and agent
  instructions around the provisional Minecraft 26.3 research plan.
- Pin a Minecraft 26.3 Fabric development toolchain and add a delegating
  function-wrapper runtime probe with custom-tag identity and low-quota checks.
- Add a disabled Bellows adapter for vanilla mob `home_pos` modify/remove
  semantics; the seven-arm compatibility matrix verifies init, merge, modify,
  and remove against vanilla.
- Add a disabled macro-expansion ScoreAdd prototype that retains vanilla's
  macro tuple LRU; the focused six-arm matrix verifies tuple churn, storage
  changes, hash collisions, argument errors, and per-function callbacks.
- Extend SCORE-007 with absent operation targets and multi-entity operation
  targets; the full six-mode runtime differential probe passes against vanilla.
- Expand Bellows selector parity coverage for distance, score/AABB, positive and
  negative tag constraints, and furthest `limit=1`; all seven arms pass.
- Verify Bellows `home_radius` modification/removal against vanilla alongside
  `home_pos`; all seven arms match, so the adapter stays scoped to `home_pos`.
- Add the first differential fixtures for the v1 coverage table and close five
  rows. Three new fixtures in the probe pack (`storage_value_shapes`,
  `storage_copy_paths`, `storage_store_and_errors`) are registered in
  `DIRECT_FIXTURES` and `EXTENDED_QUOTA_FIXTURES` and were run across mod-free
  vanilla 26.3 plus all nine Fabric runtime modes with exact score-sequence
  parity, adding matrix cases DATA-002/003/004. Coverage table now 101 rows:
  69 covered, 0 partial, 32 missing (was 28 before the partial-cited rows were
  narrowed, and 36 before this batch).

  Three findings recorded rather than papered over. The 26.3 `execute store
  result score` syntax rejects a scale argument, so the fixtures build their
  positional checksum with `scoreboard players operation` weights instead. The
  string member and the post-removal list read are exercised but their folds
  land beyond the 0-16 quota sweep, so they are not observed. And
  `execute store ... storage` (MO-02) stays open because the node arity that
  parser expects is unconfirmed - writing a fixture for it would produce a test
  that cannot load.
- Close nine more coverage rows with differential fixtures, and fix a
  load-time defect they found. Four fixtures (`score_holder_and_overflow`,
  `score_condition_absent`, `score_store_targets`, `leaf_and_tail_runs` plus
  three leaf helpers) run across mod-free vanilla 26.3 and the full ten-arm
  Fabric matrix with exact score-sequence parity, adding matrix cases
  SCORE-016..019 and closing SM-03, SM-11, SC-03, SC-05, SS-03, SS-04, LF-01,
  TC-01 and DS-05. Coverage table now 101 rows: 78 covered, 0 partial, 23
  missing.

- Fix a datapack-load crash found while building those fixtures.
  `ScoreAddPrototype.resolveStaticHolder` resolved a holder name before
  checking that it begins with `#`, and resolving a literal *player-name*
  holder consults the server's player list, which is null during a datapack
  load. `scoreboard players set FCFused <objective> N` therefore threw an NPE
  that failed the entire function load in every compiled arm, while vanilla
  loaded it fine. All seven call sites now decline any holder that does not
  begin with `#` before resolving, so the literal holder stays on the vanilla
  path; the new fixture proves both the fallback and the 32-bit INT wrap.

- Two process findings recorded rather than hidden. `score_store_targets`
  first used `scoreboard players get` as its inner command and produced an
  all-zero sequence in every arm, i.e. an oracle that can never fail; it was
  rebuilt around a data command with a known result value. And the storage
  batch's write-up claimed five closed rows when only four had closed, because
  a text edit searched for a string that did not occur and silently no-op'd;
  the coverage table's numbers are now regenerated from the table itself rather
  than edited by hand.
