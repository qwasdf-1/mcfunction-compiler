# SCHED-COMP-017 — Cached vs legacy ScoreAdd in a real Vein Miner event

**Status:** Preregistered, not yet interpreted. This is the real-datapack follow-up to SCHED-COMP-016's production-safe immutable environment override caching. It does not alter any production defaults.

## Hypothesis and measurement

The 015 controlled CPU study found repeated ScoreAdd environment lookups costly. The 016 controlled study tests dynamic config semantics and directly compares cached typed ScoreAdd to vanilla. **This study** asks whether caching those immutable environment overrides changes end-to-end **native Vein Miner 5.3.0** mining-event completion time once the game has substantial real work and tick pacing.

Use exact publisher-pinned `VeinMiner-5.3.0+26.3.zip`, version `5jzz5SkG`, SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`, retrieved and verified before any experiment. Same native survival-player playerbot mining a **6×6×6 ore block** (215 naturally affected blocks), using the previously calibrated official Minecraft 26.3 Fabric server and Java 25. No artificial function invocation substitutes for the player action.

The two arms run **the same `run_veinminer_profile.py --stack fabric --compiler-mode score-add --side 6 --capture-timeout 60 --no-spark`**; the only difference is:

- **Legacy:** set research-only `FC_SCORE_ADD_LEGACY_NAMESPACE=vm`. Within `vm` functions, the `ScoreAddCommand` checks flags through the old `System.getenv` path on every execution.
- **Cached:** ensure `FC_SCORE_ADD_LEGACY_NAMESPACE` is **absent**. The same `vm` functions use the new static-cache immutable environment-override path.

Both arms install the same compiler build, keep typed ScoreAdd enabled, turn off fusion, bytecode, selective macros, per-command metrics, JFR and Spark, and retain vanilla function scheduling. The existing native event runner internally sets the same explicit `FC_SCORE_ADD_PROTOTYPE=true`, timing false and ScoreAdd metrics false for both. An inherited research flag changes only the allowlisted old/new config checks; score mutation and Brigadier feedback semantics are identical. All publisher `vm` ScoreAdd candidates must have positive compilation counts.

## Paired design and gates

Ten pairs of **fresh independent JVMs**, seed `26874017`, exactly five in legacy→cached order and five in cached→legacy order. Every arm runs a fully fresh world/server/playerbot. Do **not** exclude slow boots, negative effects or timing outliers after observing results.

Primary endpoint: the existing harness's `operation_completion_seconds` for the 6×6×6 native mining event, analyzed as arithmetic `100×(cached_seconds/legacy_seconds−1)` for each pair. A negative value is faster; a positive value is slower. Report median of ten paired percentages and exact distribution-free **97.85% coverage** median interval; the materiality screening threshold is **15% relative improvement**, requiring the interval's upper bound ≤−15.

Hard validity gates per run: `valid_native_workload`, `valid_score_add_profile`, nonzero `vm` ScoreAdd compilation, **zero fusion**, positive duration, and exact parity for `player_mined_source_stat`, `work_after`, `work_expected`, `run_state_after`, `queue_head_delta`, `remaining_ore`, `source_block_remains`, `operation_markers_after` and `target_markers_after` within each pair. A pair with mismatched work invalidates the complete comparison, not just that pair. Preserve all raw event JSON and server logs and paired host load/context snapshots. No additional instrumentation is allowed to vary between arms.

A valid interval entirely below zero but not wholly past the 15% threshold is a **small screening gain only**. If the interval overlaps zero, report inconclusive (or no material gain by the declared threshold when its lower bound is above −15) rather than claim caching improves real play.

### Scope limits

This is a **cached-vs-legacy ScoreAdd** real-datapack result, not cached-vs-vanilla/compiler-off. Whole-event completion is not exclusive server-thread CPU; tick, playerbot protocol and server scheduling may dominate. The `FC_SCORE_ADD_LEGACY_NAMESPACE=vm` choice deliberately covers exactly the publisher's `vm` namespace, not all functions in all datapacks. A valid negative result in the real event would bound practical benefit without invalidating the earlier controlled microbenchmark.

**Files:** `scripts/ci_veinminer_cache_event.py`, `tests/test_veinminer_cache_event.py`, `.github/workflows/research-veinminer-cache-event.yml`. Run outputs `build/benchmarks/SCHED-COMP-017/results.json` and the original Vein Miner harness per-run source logs.
