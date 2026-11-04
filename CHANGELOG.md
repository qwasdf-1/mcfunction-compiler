# Changelog

## Unreleased

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
