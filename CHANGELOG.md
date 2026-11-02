# Changelog

## Unreleased

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
