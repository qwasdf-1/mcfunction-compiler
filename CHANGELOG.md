# Changelog

## Unreleased

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
