# COMPILER-IR-032 — Dynamic Lights: controlled execution census

**Status (2026-11-23): Gate A source inventory accepted; Gate B controlled stationary-versus-moving execution census accepted. NO CPU HOTSPOT OR SPEEDUP ESTABLISHED. NO OPTIMIZER IMPLEMENTED.** Branch: work/compiler-coverage; PR #10 remains draft and unmerged.

This begins a separate, recurring tick-workload investigation after IR-030's below-threshold coordinate getter and IR-031's rejected entity writeback hypothesis.

## 1. Exact source and benchmark provenance

The pinned publisher is Dynamic Lights by CreepermeYT v1.4.6, Modrinth version 9JACtwPz, SHA-256:

    afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20

Minecraft 26.3 applies both the pack_1_21_6 overlay and pack_26_3 overlay in declared order. The static census found 94 function IDs and 92 tick-reachable IDs. Runtime compiled-function census registered 92 callee counters across 532 command sites.

**Important distinction: the executed pack is NOT byte-identical to the original publisher ZIP.** A documented benchmark-only patch removes two stale calls to deleted internal/util/overloadcheck in the two singular/plural internal/tick source files. The patch corresponds to upstream commit b3ea1239 and changes no other workload logic. Both arms used an identical patched pack with SHA-256:

    c649d206faac63a773ce5dec06ec531128d1f6feaa104ad4e28a18143706d083

The source archive, explicit patch manifest, and both identical patched runtime ZIPs are in the evidence artifact. Never describe the measured execution as publisher-byte-exact.

## 2. Rejected setup attempts and corrected fixture

Two failures were treated as invalid runs, not performance observations.

- [Run #45247809315](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45247809315) used obsolete gamerule names. The corrected 26.3 harness sets and reads back minecraft:spawn_mobs=false and minecraft:advance_time=false.
- [Run #45251499535](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45251499535) detected 38 item entities in the stationary control instead of exactly 24. The corrected runner performs one explicitly recorded post-warmup, pre-measurement purge of UNTAGGED dropped items. It never removes the 24 individually tagged torch actors and does no cleanup during measurement.

The accepted [run #45252138451](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45252138451) used fresh Minecraft 26.3 / Java 25 Fabric servers, four fixed-position creative player bots holding stone, 24 dropped torches on a controlled stone platform, the same Smart preset, same seed, same 18-second windows, and no compiled optimizer. The profiler was an execution-count census only: no Spark, JFR, source timers, callback CPU clocks, or per-function timing.

The one-time purge removed 51 untagged item entities from the stationary server and 52 from the moving server. These were outside the source fixture; their precise origin was not isolated. Both before and after measurement, the servers independently verified EXACTLY four player holders, 24 torch item entities, and zero other light sources. Natural mob spawning and daylight advancement remained disabled. The stationary 24 items stayed still (0.00 blocks displacement); the moving 24 all exceeded one block of motion (mean displacement 15.87 blocks). All source actors remained tagged and recognized.

The earlier [run #45244588431](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45244588431) did report a complete census, but lacked these strict environmental guards. It is provisional historical diagnostic evidence, not an independent clean replication.

## 3. Accepted Gate B: observed native execution counts

Both arms registered the same 532 sites and 92 callees without overflow. Each completed exactly 360 Dynamic Lights ticks.

| Metric / 360 ticks | Stationary | Moving | Change |
|---|---:|---:|---:|
| Command-site entries | 257,400 | 285,373 | +27,973 (+10.87%) |
| Executed command callbacks | 61,200 | 72,379 | +11,179 (+18.27%) |
| Native function-call tasks | 83,880 | 91,134 | +7,254 (+8.65%) |
| Single-dispatch entries | 0 | 4,716 | +4,716 |
| Complex-dispatch entries | 75,600 | 77,327 | +1,727 |

The tick and tickcheck functions each executed 360 native call tasks in both arms, so the difference is not caused by running extra scheduled ticks.

| Function suffix under dynamic_lights_by_creepermeyt namespace | Stationary tasks | Moving tasks | Change |
|---|---:|---:|---:|
| internal/smart/updatecheck | 10,080 | 11,391 | +1,311 |
| internal/smart/delete | 1,080 | 2,011 | +931 |
| internal/smart/summon | 10,080 | 10,999 | +919 |
| internal/smart/place/place_high | 0 | 524 | +524 |
| internal/smart/create_c1 | 0 | 524 | +524 |
| internal/smart/as_new | 0 | 515 | +515 |
| internal/smart/summon_c1 | 0 | 515 | +515 |
| internal/smart/create | 1,080 | 1,501 | +421 |
| internal/smart/compare | 10,080 | 10,484 | +404 |
| internal/smart/propagate | 720 | 974 | +254 |
| internal/common/dynamiclight | 8,640 | 8,640 | 0 |
| internal/util/genforentitywithscore | 8,640 | 8,640 | 0 |
| internal/util/asholder | 1,440 | 1,440 | 0 |

All counts are function-call TASKS, not CPU durations. Command-site entries include conditional instructions that may not enter their callbacks. Movement also activates different control-flow branches: this is not merely an increased number of otherwise identical commands. None of these measurements establishes a new CPU optimization opportunity.

## 4. Gate C: target CPU attribution, not an implementation

The now-controlled workload justifies a narrow uninstrumented CPU/method-attribution investigation:

1. Repeat the same patched runtime pack, exact population, fixed seed, 18-second stationary/moving windows in separately measured fresh JVMs. No research execution census or callback counters in the timing arms. Confirm host quality and task counts independently, not by mixing high-overhead counters with CPU.
2. In a separate profiler arm, split native work among fill/block updates, execute/selectors, scoreboard/tag mutation, and function call scheduling. The increased smart/delete and newly enabled smart/as_new/place_high paths are promising places to inspect, not proof of expensive or removable costs.
3. Select an actual measured hot method and only then consider an opt-in exact-shape compiler candidate with its own native failure, feedback, quota, side-effect and restoration oracle. Use uninstrumented ABBA and an A/A noise control to test the established 15% full-event improvement bar. Do not relax thresholds or merge PR #10.

**Decision:** Gate A and Gate B accepted as static and dynamic COUNT evidence. CPU attribution and semantic optimization feasibility remain open. No tag index, fill shortcut, selector cache, production-default behavior change, or compiler implementation was authorized by the census.

## 5. Gate C prepared experiment — not yet executed or accepted

The opt-in Gate C runner and [manual-only CPU/JFR workflow](../../.github/workflows/research-typed-ir032-gate-c.yml) are committed to the same research branch. **There is no Gate C native dataset yet.** Passing Python tests or regular build CI does not establish CPU cost or a hotspot.

### Precommitted run separation

- **CPU baseline:** four fresh Fabric JVMs in stationary–moving–moving–stationary order, each with the same patched runtime ZIP, Smart preset, four stone-holding players, 24 tagged torches, fixed seed and 18-second measurement. Wrapper remains active for configuration equivalence; all compiler optimizers, execution census, Spark and JFR are off. The two-call upstream hotfix and c649d206... SHA remain mandatory; this is not a publisher-byte-exact run.
- **CPU clock:** identify the real Minecraft Server-thread PID/TID beneath Gradle, read Linux schedstat running CPU before and after the window, and require zero cgroup throttling and no more than 25% runqueue-wait share. Pre-window tick-query stability is an environmental admission check, not a treatment-outcome filter. Record game-time queries as a tick-work proxy with 300–380 ticks per nominal 18 seconds. RCON read boundaries are not an atomic exact function-call count; those come from the separate Gate B census.
- **Descriptive CPU comparison:** normalize observed Server-thread CPU by observed game-time tick delta; report per-arm values, within-scenario two-run spread and a predeclared 8% noise screen. Report stationary and moving data even when noisy. Moving executes different native code, so its CPU difference is **not an optimization effect** and is not a 15% promotion test.
- **JFR method attribution:** two further fresh JVMs, one stationary and one moving, with the same environment and population checks, no Spark/census/callback counters. Only these arms attach JFR. Filter runnable ExecutionSample stacks to the exact Linux Server-thread OS TID; require at least 150 samples per profile. Report inclusive overlapping categories for block/fill, execute/selector, score/tag, function scheduling, entity data/NBT, and entity iteration. Retain full recordings and top leaf frames. The JFR sampling arms must never be compared as uninstrumented CPU arms.
- **Failure policy:** retain raw logs and partial manifests on rejection; no silent retries, no selection of only the cleanest arms, and no threshold changes after observing results.

The coordinator is scripts/ci_ir032_gate_c.py; it reuses scripts/run_dynamic_lights_profile.py. Tests are in tests/test_ir032_gate_c.py. The workflow is **manual-only**; ordinary PR CI runs only lightweight Python validation.

### Interpretive stopping rules

1. If controlled CPU arms do not establish a reproducible movement-related difference above noise, stop the movement-specific compiler hypothesis. Do not promote count differences into CPU savings.
2. If JFR finds a hot native method, audit the exact original commands and separate necessary side effects from genuinely removable compiler overhead. Inclusive categories cannot be added or treated as exclusive CPU costs.
3. Any later opt-in exact-shape compiler action needs separate semantic tests (errors, feedback, quotas, side effects, restoration) and a new uninstrumented causal A/B plus A/A noise controls. The **15% whole-event promotion threshold remains unchanged**.

**Disposition:** Gate C protocol and manual workflow prepared; no Gate C native observations, optimizer implementation or production-default change. Draft PR #10 remains unmerged.

---

## Evidence links

- [Static source and overlay census #45132719718](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45132719718)
- [Accepted clean stationarity/motion census #45252138451](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45252138451)
- [Complete raw two-server artifacts](https://github.com/qwasdf-1/mcfunction-compiler/actions/runs/45252138451/artifacts/14856898565)
- [Research source script](../../scripts/ci_ir032_dynamic_lights_source.py)
- [Original-gameplay runner](../../scripts/run_dynamic_lights_profile.py)
- [Manual execution workflow](../../.github/workflows/research-typed-ir032-execution.yml)
