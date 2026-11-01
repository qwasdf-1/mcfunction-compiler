# Changelog

## Unreleased

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
