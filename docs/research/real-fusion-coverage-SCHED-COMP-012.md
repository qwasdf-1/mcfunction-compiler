# SCHED-COMP-012 — Two bounded real-datapack fusion-coverage evaluations

**Status:** Preregistered protocol, before execution. This closes real-workload fusion discovery and returns to the original scheduler-architecture question.

## Why only these two

PERF-016's 19-pack static screen found two promising candidate forms:

- **Blastback Hotfix 3, Minecraft 26.3**, pinned publisher version `dMtA8r0n`, expected SHA-256 `8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90`: generated block-state reader, ~32 adjacent `execute if block ... run scoreboard players set` lines. This is a **capture-triggered**, not idle tick, path. The earlier 1-TNT restoration test failed; full native-state integrity is not presently established.
- **Simple Timer**: a tick-reachable ~36-command display/clock candidate. The original archive was kept in an ignored local directory, so its exact fingerprint is not recoverable from git. The new diagnostic selects the most recently published *pre-November 3, 2026* Modrinth `simple_timer` ZIP advertising MC 26.2 or 26.3; its version ID, release date, downloaded SHA-256 and content are recorded. **Do not claim it is the same ZIP as the original screen unless the fingerprint/candidate matches.** Do not silently substitute `simple-timer1`, a different project.

The scanner reports *potentially* fusable runs. In 26.3 runtime, actual fusion requires a matching FusableCommand after Brigadier parsing and at least two adjacent eligible queue entries. Static regex hits alone are not a performance result.

## Phase A — one diagnostic boot per pack

Run the pinned official 26.3 Fabric production server, Java 25, compiler installed, ScoreAdd and fusion enabled, no selective-macro or ASM backend. Enable ScoreAdd metrics **only for this diagnostic**, including new per-function fused-region **execution** counts in `functioncompiler stats <id>` (the old counters only recorded compiled regions). Query targeted functions' compiled counts and **before/after execution deltas**.

- Simple Timer: connect one native headless player, attempt the pack's `timer.start` trigger, allow at least ~32 seconds of naturally scheduled activity. A separate one-command tick witness checks that at least 300 real server ticks occurred; log activation response and objectives. Do not manually invoke the candidate function to manufacture a success.
- Blastback: create the publisher's existing 17×17×17 witness/template setup, summon one TNT, allow 75 seconds of natural capture/restoration, then query target reader function counts and inspect the source/template match. This initial run is *coverage-only*, **not valid for performance**, because full restoration and remaining queues are not certified.
- If the pack fails to load, candidates have no compiled region, or target regions have zero executed delta, report `not_eligible` and do **not** run that pack's performance comparison.
- All selected function IDs, compiler status, tick counts, command responses, production hashes, logs, and original downloader SHA-256 are saved.

A positive executed delta proves the region ran at least once in the specified native scenario; it does **not** prove the fraction of all commands/CPU spent there.

## Phase B — bounded Simple Timer tick impact, only after Phase A

Run six pairs of fresh Minecraft JVMs, seed **12012**, exactly 3 in each baseline→fused / fused→baseline order. Same datapack, seed, player, witness, compiler, JVM flags, and fixed elapsed window. ScoreAdd remains enabled in both arms; only fused-region compilation differs. **Execution counters and Spark/JFR are off during timing**.

Primary exploratory measurement: Linux server-thread running CPU nanoseconds divided by the number of witnessed active server ticks (minimum 300, paired count difference ≤15). This is *whole-server CPU per tick*, not CPU time of the candidate function. Also preserve raw `/tick query` as secondary context, not the primary endpoint.

One paired percent effect = `100*(fused_CPU_per_tick/ScoreAdd_CPU_per_tick - 1)`. Analyze all six independent pairs, with distribution-free exact >=95% median interval. Only an interval entirely at/below **−15%** constitutes a material screening gain, not a production promotion. The presence of a native player and equal tick work does not guarantee identical actionbar content, so this is **bounded tick workload parity**, not full cross-client behavioral certification. If more complete timer output parity cannot be established, retain the performance screen as exploratory only.

No Blastback performance campaign should run unless it first passes a **separate full native restoration gate**, including queue drain and witness/template state. Stop after this activation check if it does not; the data are a compatibility/coverage finding, not a benchmark.

## Scope boundary and next experiment

**No third real-datapack search.** After 012, return to the primary architecture question:

> How much of hot-function CPU overhead is due to vanilla queue scheduling and continuation management, beyond parsed-command execution, and does alternative scheduler control beat the best vanilla-scheduler compiler with full semantic parity?

The next study is **SCHED-ARCH-013**: quantitatively split scheduler bookkeeping from runtime command work on the *same eligible function body*, and compare (1) vanilla baseline, (2) typed command specialization under vanilla scheduler, (3) fused scheduler entries retaining the vanilla queue, and (4) an opt-in scheduler-bypassing executor only if equivalence tests cover quotas, forks, nested calls, return, trace, callback timing and reload. Do not build a general scheduler replacement based solely on ScoreAdd microbenchmarks. The architecture is justified only if the extra scheduler-bypassing component yields a material incremental end-to-end benefit on qualifying workloads.

**Implementation:** `scripts/ci_fetch_real_fusion_packs.py`, `scripts/ci_real_fusion_coverage.py`; unit contracts `tests/test_real_fusion_coverage.py`. CI archives `build/benchmarks/SCHED-COMP-012/`.
