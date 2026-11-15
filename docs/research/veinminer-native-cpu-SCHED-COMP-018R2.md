# SCHED-COMP-018R2 — bounded pre-mining RCON readiness and fresh Vein Miner CPU replication

**Status:** **All 30 independent Minecraft arms completed and passed gameplay/host gates; archived-data analysis recovered after a bookkeeping-only CI failure.** R2 verdict: **no material real-workload CPU or event-duration gain**. CI itself reported failure because the analyst expected redundant arm identity fields that were omitted from saved records; no gameplay or performance observations are missing. Earlier 018 and R1 partial datasets remain separate.

## Failure diagnosis and rationale

- Original [018 CI 43622114468](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43622114468) stopped after two complete triplets: a compiler-off control had mined **215 ores** but was still active (`vmr.run=1`, queue 1856/1952 steps) when its 60-second event observation expired.
- Independent R1 [CI 43633149821](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43633149821), raw [artifact 14129864002](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43633149821/artifacts/14129864002), implemented a fixed 150-second event cap and a permissive pre-event idle tick gate. Its three-arm preflight and **eight complete triplets** succeeded. Triplet 9 stopped **before any mining packet** when the cached arm's `forceload add` RCON command exceeded the shared `DrainingRconClient`'s 10-second socket timeout. The Minecraft log showed an approximately 11.5-second startup tick backlog before clean shutdown. This is an infrastructure/setup availability failure, not a valid cached-vs-off event CPU measurement.
- The eight R1 triplets are **descriptive only** and not used as R2 samples. A separate R2 random seed, output path, CI run and statistical report are required. R1's existing workflow is retained as *manual dispatch only* on this branch to avoid accidentally rerunning a superseded frozen design.

## Bounded setup-only intervention

The opt-in `--setup-rcon-timeout-seconds 45 --startup-readiness-record PATH` applies a **45-second RCON socket timeout to the initial `forceload add` command only**, then restores the original socket timeout in `finally`, before any player mining. A separate atomic JSON state record tracks `runner_created`, `rcon_ready`, `forceload_pending`, `forceload_completed`, and `mining_packet_started`; the irreversible `mining_started=true` marker is written **before** sending the first mining packet. Without these opt-in flags, the ordinary runner retains its old 10-second timeout.

**Every arm, including off-A, off-B and cached**, gets the exact same policy, with a predeclared maximum of **one fresh whole-JVM/world restart per arm** and **two such restarts total per phase** (separate caps in preflight and timing). A restart is permissible *only* when:

1. The child process exited nonzero with actual `TimeoutError: timed out` from the initial `rcon.command(f"forceload add...")` call.
2. Its stage JSON is present, parseable, protocol-matched and ends in `forceload_pending`; all stage events prove `mining_started=false`.
3. Both per-arm and phase-wide startup retry budgets remain.

A validly restarted arm uses a **new JVM/world**, never reuses an RCON socket whose command result is unknown. All failed and successful attempts, their stage history, arm, relative position, exit reason and whether a restart was allowed are recorded as `startup-attempts-{smoke,timing}.json` and per-attempt stage files in the uploaded CI artifact. An absent/corrupted record, pre-event idle tick failure, player-bot setup failure, 150-second event timeout, wrong ore/game state, mid-event RCON failure, workload integrity failure, or any error after `mining_packet_started` is **fatal, not retryable**. Exhausting the bounded restart budget stops the entire campaign. No post-hoc selection or deletion of boots is permitted.

If any restarts occur, the final comparison must explicitly report their frequency **by experimental arm** and be described as conditional on successful pre-mining readiness. A start-up failure imbalance between arms remains a substantive deployment concern even if event-conditioned CPU metrics look favorable.

## Unchanged scientific question and preregistered experiment

Does enabling the production-safe cached ScoreAdd callback reduce **Linux Minecraft Server-thread running CPU over a genuine 215-block native Vein Miner 5.3.0 mining event**, relative to compiler optimizations disabled with the same Fabric+compiler jar installed? Event wall completion is separate. The server, datapack, playerbot, world seed, native game actions, original `ExecutionContext`, command source, hardware/Java 25 environment, and publisher archive SHA-256 `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e` remain unchanged. No Spark, JFR, per-command instrumentation, alternative scheduler or fusion is enabled.

Use a fresh **three-arm preflight** then exactly **ten complete independent off-A/off-B/cached triplets**, with **30 fresh server boots** plus any eligible documented *pre-mining* restart boots. The frozen R2 seed is **26874021**; all six possible orderings plus four prespecified extra permutations, each arm appearing 3 or 4 times in each position. The same trial allocation is frozen before examining any R2 results. All work-completion and semantic gates from R1 remain, including **exact 215 ore operations**, `vmr.run=0`, queue-head delta 1952, absent remaining ore and markers, and matching full native state in each triplet.

The R1 idle pre-event gate is unchanged: **9 seconds of settling**, Minecraft `tick query` sample of ≥50 ticks, average ≤150 ms, P95 ≤600 ms. The post-event overload report (average ≥500 ms or P95 ≥2000 ms) is **diagnostic only**, not a ground for excluding heavy events. Each completed event must have valid thread identity, positive Server-thread schedstat running nanoseconds, zero sampled cgroup throttling and runqueue wait fraction ≤25%. Failures retain raw logs and the campaign is incomplete or inconclusive, never selectively replaced after mining begins.

Primary per-triplet effect is arithmetic `100×(CPU_cached/CPU_offA−1)`. Secondary is `100×(event_seconds_cached/event_seconds_offA−1)`. The **independent off-B/off-A placebo** must pass for both CPU and wall duration: each exact order-statistic ≥95%-coverage median confidence interval includes zero. For ten triplets, report exact **97.8516%-coverage** median intervals. A material effect requires upper confidence bound ≤−15% relative CPU (or independently for wall). A small interval wholly below zero is merely a screen; a failed host, workload, placebo, or incomplete-triplet gate prohibits a positive performance verdict. Reuse none of the 018/018R1 observations in statistical inference; report all R2 attempted restarts.

## Implementation and sources

- Failure evidence: [R1 CI #43633149821](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43633149821), [raw artifact 14129864002](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43633149821/artifacts/14129864002).
- `scripts/run_veinminer_profile.py`: opt-in forceload timeout and atomic before/after intervention stages.
- `scripts/ci_premining_readiness.py`: exact restart classification and caps.
- `scripts/ci_veinminer_native_cpu_r2.py`, `tests/test_veinminer_native_cpu_r2.py`: new seed, failure ledger, same paired CPU estimator.
- `.github/workflows/research-veinminer-native-cpu-r2.yml`: new CI experiment, immutable raw artifact `build/benchmarks/SCHED-COMP-018R2/`.

All production optimization defaults remain unchanged. The one-file production cache optimization is still isolated as draft [PR #15](https://github.com/qwasdf-1/mcfunction-compiler/pull/15).

## Completed R2 data and archived-data recovery (November 14, 2026)

**Authoritative original run:** [GitHub Actions #43641756371](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43641756371). **Raw immutable artifact:** [`sched-comp-018r2-veinminer-cpu-raw`, ID 14134496063](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/43641756371/artifacts/14134496063). The pinned reference, production build, unit tests, and three-arm preflight all passed. Ten complete triplets containing **30 fresh independent Minecraft runs** completed the actual 215-block player-bot event; all three arms in every triplet had matching native final game state, matching pack digest, valid treatment activation, and passed their individual host-quality gates. All 30 startup attempts completed on the first boot, with **zero readiness retries**, no startup failure imbalance, and no post-event severe tick overload flags.

**Important CI qualification:** The original workflow's timing job failed *after the 30th Minecraft run* on `KeyError: 'position'` during `analyze()`. The existing `run_arm` saved each arm under the correct name in the per-triplet `arms` dictionary, and separately persisted the preregistered `order` array, but accidentally omitted redundant `arm`, `triplet`, and `position` fields from the arm value. The repaired analyzer recovers this identity solely from the immutable dictionary key, triplet index, and frozen order, checking any explicitly present labels for agreement. It **does not impute, modify, drop, replace or rerun any observation**. A new regression test covers this exact archived-record shape and rejects contradictory explicit labels. The completed R2 data were independently reanalyzed directly from the preserved ZIP; the original CI run is still **red** because this is a post-archival reanalysis, not a claim that the historical workflow passed.

### Archived-data reanalysis: original, unchanged ten triplets

All outcomes below are signed **ordinary relative percentages**, comparing each run with the same-triplet compiler-off A control. Negative is lower CPU or faster event completion. The exact interval is the predeclared nonparametric 97.8516%-coverage median interval (2nd through 9th sorted among ten independently paired observations).

| Preregistered comparison | Median effect | Exact 97.85% median interval |
| --- | ---: | ---: |
| **Cached ScoreAdd vs compiler disabled — primary full-event Server-thread running CPU** | **+0.7831%** | **[−9.1110%, +8.9656%]** |
| Cached ScoreAdd vs compiler disabled — secondary event completion duration | +0.6941% | [−7.2468%, +7.0526%] |
| Compiler-off B vs identical compiler-off A — CPU A/A placebo | −0.5425% | [−9.7232%, +8.1010%] |
| Compiler-off B vs identical compiler-off A — event-duration A/A placebo | −0.2338% | [−8.8386%, +6.0850%] |

The CPU and duration placebo intervals both contain zero; every triplet passes host-quality and exact-work gates, so the previously preregistered analysis is admissible **after recovering the omitted redundant labels**. Both treatment intervals also contain zero: there is **no supported real-workload CPU saving and no supported event-duration change**. Both lower bounds lie above −15%, ruling out the predeclared material 15% median improvement on this 215-block Vein Miner workload at this confidence level. The original analyzer's intended decision function yields **`verdict=no_material_gain`** and **`event_latency_verdict=no_material_gain`**. The observed positive medians are also insufficient to claim a regression, because both treatment intervals include zero.

There are visible high-variance individual triplets (for example triplet 4 contains unusually high CPU in the off-A control); all ten were retained unmodified. This is consistent with baseline noise that is substantial relative to any real-workload benefit from caching. Critically, the **synthetic ~8.5% per-command CPU improvement from SCHED-COMP-016 is not equivalent to a whole-gameplay-event CPU improvement**, and this R2 experiment has now bounded the practical benefit for this specific publisher Vein Miner scenario.

**Decision:** Preserve the small, production-safe static environment-override cache as an *optional/simple local optimization* candidate (draft PR #15), but **do not promote a material real-gameplay performance claim** or pursue further repetitions of the identical Vein Miner workload merely to seek significance. If future compiler work is justified, prioritize a fundamentally different, well-defined representative workload or an implementation-level profile with semantic controls. More global queue/scheduler bypass experiments are not justified by this result.

The archived event data may be downloaded from the linked artifact. The standalone copy of the recovered analysis is also available as a downloadable JSON in the ChatGPT conversation that performed this recovery. This post-hoc analysis is limited to repairing the analyzer's data-schema bug and strictly follows the original frozen outcome definitions.
