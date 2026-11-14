# SCHED-COMP-018 — Native Vein Miner event: compiler disabled versus cached ScoreAdd, with true Server-thread CPU

**Status:** Preregistered and implemented. No 018 performance result until the native CPU preflight, ten complete independent triplets, placebo, exact-gameplay-parity, and host-quality gates have passed.

## Why this is the next experiment

SCHED-COMP-016's direct 12-JVM synthetic scoreboard benchmark found the production-safe immutable environment override cache improved typed ScoreAdd by **−8.923 signed log-%**, roughly **8.5% less Server-thread running CPU** than native scoreboard callback execution on the exact literal 2,000-command fixture. Its predeclared decision was `cached_path_small_gain_vs_native_supported`, not the 15-log-% material-gain threshold.

The real Vein Miner SCHED-COMP-017 playerbot experiment then completed **10 cached-versus-original ScoreAdd pairs**, with exactly matched ore work. Overall mining-event time median change was **−0.3543%**, exact 97.85% interval **[−3.4707%, +5.9461%]**, so no material event-duration improvement was demonstrated. 017 did **not** compare against compiler-disabled execution or measure actual server-thread CPU.

**Question in 018:** Does having cached typed ScoreAdd **enabled instead of compiler optimizers disabled** reduce the server's running CPU while completing the *same* real player-driven Vein Miner 5.3.0 event? Does it alter event duration? These are distinct metrics. No global scheduler replacement is evaluated.

## Source, intervention, and scenario

Use the same exact publisher Vein Miner 5.3.0+26.3 ZIP as 017, pinned digest `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. A genuine survival player-bot mines the source ore from a 6×6×6 coal ore cube; native Vein Miner processes 215 further blocks. Same Minecraft 26.3 Fabric+API server, Java 25, mod build, world seed, player, commands, server flags and Datapack ZIP for **all** arms. Launch fresh JVM/world for each trial.

A single unchanged compiled mod jar is installed on every arm. `--compiler-mode off` disables all function compiler optimization modes through the existing runner's original flags. This baseline is **compiler optimizers OFF while the compiler mod remains installed**, not Minecraft without Fabric and not a pure vanilla server. `--compiler-mode score-add` enables the optimized typed ScoreAdd callback with the SCHED-COMP-016 cached immutable environment flags; no fusion, bytecode, selective macros, Spark/JFR, or per-command counters in the treatment. All arms preserve the ordinary vanilla `ExecutionContext` scheduler.

## Native event CPU measurement (new, opt-in)

`run_veinminer_profile.py --capture-server-thread-cpu` locates Minecraft's unique thread named `Server thread` **within the process tree of the Gradle-launched server**, not Gradle's own process. It takes Linux `/proc/PID/task/TID/schedstat` running-nanoseconds before the bot starts destroying the first block and immediately after the harness first observes all expected ore work complete. It also records server-thread runqueue-wait nanoseconds, number of timeslices, and Linux cgroup `cpu.stat` number of throttled intervals for a host-quality gate.

The clock must identify the same live PID/TID at both samples and remain monotonic; missing or invalid CPU counters **fail the run rather than substituting wall time**. The measurement is restricted to actual Server-thread running CPU. However, its window covers full Minecraft ticks, the player's actions, unrelated vanilla processing, and RCON state polling—not only ScoreAdd callbacks. The time to poll and observe completion makes a small boundary error; the *same* mechanism is used across arms.

CPU measurement is **not a JFR or callback instrumentation hook**; only two Linux kernel counters are read at the event boundaries. This cannot assign an exclusive CPU fraction to Vein Miner or claim a percentage of command dispatch without further tracing.

## Preflight and preregistered design

Before the campaign, one fresh compiler-off and one fresh cached trial must both (i) execute the verified native playerbot mining scenario; (ii) return identical ore-work state; (iii) provide valid Server-thread CPU clocks; and (iv) demonstrate that the cached treatment actually specialized the `vm` namespace ScoreAdd commands while the compiler-off baseline did not. A failed preflight blocks the full study.

Exactly **10 independent triplets**, each containing **three independent fresh boot+world+playerbot runs**:
- A: `off_a` (compiler optimization disabled)
- A′: `off_b` (byte-for-byte identical compiler-off settings, a real independent A/A negative control)
- B: `cached` (cached typed ScoreAdd optimization enabled).

Frozen seed **26874018**. Use all six possible orders once, plus four prespecified permutations, randomized only before the first run, so each arm appears at each temporal slot either 3 or 4 times across ten triplets. All 30 runs, including slow outliers, are retained. A and A′ have the same executable, source datapack, runtime environment, measured native event, and code path; the labels are for allocation and placebo measurement only.

Hard per-arm gates: pinned archive fingerprint, `valid_native_workload`, positive Server-thread CPU nanoseconds and event time, positive treatment compiled `vm:queue/drain` ScoreAdd commands, zero specialization in both off arms, no fusion. Within each triplet require the entire native state tuple (`player_mined_source_stat`, `work_after`, `work_expected`, `run_state_after`, `queue_head_delta`, `remaining_ore`, `source_block_remains`, `operation_markers_after`, `target_markers_after`) to match. Every event must complete 215 ore operations.

For host quality, no sampled cgroup CPU throttling and Server-thread runqueue-wait fraction ≤25% in **every arm**. Retain noisy records but declare `inconclusive_host_quality`; do not selectively exclude, retry, or change permutations to manufacture a clean result. Similarly, compare independent A′/A placebo for **both** Server-thread CPU and event time; the exact median intervals must each contain zero or the campaign is invalid. Keep full raw per-arm logs and host snapshots.

## Predeclared outcomes

**Primary:** for each triplet, `100×(B Server-thread running CPU ns / A CPU ns − 1)`. One observation per triplet, not per tick/window. Report median percent and exact order-statistic **97.8516%-coverage** confidence interval for the population median with ten complete triplets. A meaningful gain requires interval upper ≤**−15% ordinary relative CPU**. An interval wholly below zero but above −15% is only a small supported real-workload CPU screening gain, **not** a production promotion on its own. If interval contains zero, no supported CPU benefit.

**Secondary:** `100×(B event completion seconds / A event seconds − 1)`, with the same paired exact interval and a −15% materiality threshold. A tick-paced event may have unchanged wall duration even if Server-thread CPU falls. Conversely, a duration change with inconclusive CPU cannot by itself prove command-level optimization benefit.

**Negative control:** independently fresh off_b/off_a contrasts for both primary and secondary metrics, with exact 97.85% intervals. If either placebo fails, report `invalid_off_off_placebo` and do not interpret positive treatment findings. The preregistered control checks operate on population-median intervals, not every individual pair.

No posthoc exclusions. Report complete triplet effects and all raw records, including anomalies and noisy observations.

## Scope and promotion

The result estimates full-event Server-thread CPU under the exact native Vein Miner playerbot fixture on a fixed cloud-runner class, **not** CPU per typed command or actual player-perceived gains across Minecraft worlds. It is an independent, higher-level screen of the clean production implementation extracted in draft PR #15. It cannot establish performance of Blastback, Simple Timer, every modded datapack, or all runtime semantics; broad semantic tests and other real-world workloads are still necessary before merging the change by default.

**Research files:** `scripts/ci_server_event_cpu.py`, `scripts/ci_veinminer_native_cpu.py`, optional CPU flag added to `scripts/run_veinminer_profile.py`, `tests/test_veinminer_native_cpu.py`; workflow `.github/workflows/research-veinminer-native-cpu.yml`; raw artifacts `build/benchmarks/SCHED-COMP-018/{smoke,results}.json` plus per-run server logs.
