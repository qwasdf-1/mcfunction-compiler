# Tick-heavy datapack workload candidates

**Research date:** 2026-10-28  
**Target:** Minecraft Java 26.3, server-side  
**Status:** Dynamic Lights has the largest multi-pair tick-profile campaign.
Spawn Animations has a short burst pilot. Blastback has a separate no-TNT
dispatcher pilot that reaches one real ScoreAdd entry, while its TNT event
still fails world-restoration validation. A pinned Vein Miner 5.3.0 26.3
datapack is the first substantial event-driven candidate whose tick-drained
traversal contains eligible direct fake-holder ScoreAdds. Native mining,
compiler-off/on parity, and specialized invocation have passed on controlled
veins. Five-pair Fabric, Fabric+Lithium, and Fabric+Lithium+Moonrise 1.2.1
campaigns are complete; none shows a reliable speedup. The Lithium and
Lithium+Moonrise ScoreAdd medians trend slower, with wide ranges and large
outliers. Generic callback accounting is now verified on a Vein Miner event.
Bellows 1.1.2 stacks historically failed the native workload gate. Bellows
1.1.3 alone passes the 4×4×4 retest, and Lithium+Bellows 1.1.3 passes the
full 6×6×6 event (215/215 blocks). Five no-Spark selective-macro and five
ScoreAdd screening pairs on Lithium+Bellows 1.1.3 pass exact workload parity.
Neither establishes a gain: selective macro has a −18.83% median but a range
through +24.37%; ScoreAdd has a +3.60% slower median and a range through
+91.11%. On Bellows 1.1.3 + Moonrise 1.2.0, the focused macro fixture and
native Vein Miner control both pass. Five selective-macro pairs show a −20.11%
median event-completion change (93.75% interval −36.67% to +7.01%); screening
only. Bellows 1.1.3 + Moonrise 1.2.1 still fails server startup on a Bellows
Mixin shadow mismatch.

This audit separates continuous tick load from event-triggered command bursts.
They test different compiler behavior and should not be combined into one
workload score. A datapack's popularity or world-generation size does not by
itself establish function-execution cost.

## Shortlist

| Workload | Target status | Why it belongs | Profile design and limits |
|---|---|---|---|
| [Dynamic Lights by CreepermeYT](https://modrinth.com/datapack/dynamic-lights-creepermeyt/version/v1.4.6-mc1.17.x-26.3) 1.4.6 | Exact 26.3 artifact already pinned and tested | Modrinth's hosting guide flags Dynamic Lights as processing invisible light blocks each tick for entities. This project already confirmed a recurring scheduled function path in three vanilla on/off profile pairs. | Keep as the continuous per-entity selector workload. Add moving sources and a survival-like entity mix after the stationary baseline. Existing evidence does not establish its absolute cost. |
| [Everything Clings](https://modrinth.com/datapack/everything-clings) 1.0.0 | Exact 26.3 archive pinned and loaded; profile fixture failed its population-retention check | Its tick root selects non-player, non-marker entities, checks player distance, then calls a function that computes and writes horizontal motion. The publisher says hundreds of dropped items can cost server performance. | Defer comparison profiles. Controlled NoAI pig counts fell from 8 to 2 in a two-second capture, 8 to 2 in a four-second capture, and 32 to 12 in an 18-second capture. Spark trees were valid, but the population was not stable enough for a matched comparison. |
| [Bigger Every Kill](https://modrinth.com/datapack/bigger-every-kill) 1.0.0 | Rejected on exact 26.3 runtime load despite its project page listing support | The archive has a global non-player tick scan, stale-score guard, and storage-argument function, but the official server rejects its advancement JSON during registry loading (`conditions.entity` has the wrong shape). | Do not profile this artifact. Reconsider only after an upstream 26.3-compatible release is published; keep its pin as a compatibility finding, not a runnable workload. |
| [Blastback](https://modrinth.com/datapack/blastback/version/dMtA8r0n) Hotfix 3 | Exact 26.3 artifact loads. Its 1-TNT event still fails restoration validation; a separate no-TNT dispatcher pilot passes two paired Fabric compiler-off/ScoreAdd profiles. | The archive contains 21,318 functions and about 269,000 non-comment command lines. Its tick tag enters one dispatcher, which increments `#tick_id` through a literal fake-holder ScoreAdd on every dispatch. The publisher describes capture, restoration, verification, and cleanup pumps that stop when idle. | The no-TNT pilot verifies one compiled `erb:runtime_tick` ScoreAdd, exact `#tick_id` deltas in both profile pairs, and 340 specialized-entry executions in a separate instrumented diagnostic. It is a lightweight path pilot, not a heavy event workload or performance decision. The 1-TNT event still leaves 3,273 saved-block markers, a restore job, and protected-item state after a 180-second capture plus a five-minute drain; its 17×17×17 source volume differs from the untouched template. Keep the event profile deferred. |
| [Tschipcraft Spawn Animations](https://modrinth.com/datapack/spawn-animations) 1.11.6 | Exact artifact loaded on 26.3; one short all-thread burst pilot completed | In the pilot, 24 zombies remained present, six were in the active animation state at profile start, and none remained active after six seconds. The Server thread tree contained 47 thread nodes and 288 ms weighted in `ServerFunctionManager.execute`. | Valid path pilot for a transient spawn burst; not a stable cost estimate. The six-second sample was mostly idle by its end. Add repeated controlled waves before comparison runs. See [PERF-010 evidence](real-world-profile-targets.md#spawn-animations-burst-pilot-and-other-screening). |
| [Vein Miner](https://modrinth.com/datapack/vein_miner) 5.3.0 | Exact 26.3 datapack release pinned; GPL-3.0-only; 76 functions, 147 archive entries | The archive has three direct literal fake-holder ScoreAdd sites: `vm:player/register` (`#next_id`), `vm:detection/ray_step` (`#ray`), and `vm:queue/drain` (`#head`). The native 6×6×6 survival-player mining event completes 215 blocks and advances `#head` 1,952 times. An instrumented run also records 4,212 `#ray` additions, for 6,164 observed callbacks across the two event hot-path entries. Five-pair campaigns on Fabric, Fabric+Lithium, and Fabric+Lithium+Moonrise 1.2.1 match exact workload state. No adjacent eligible pair exists in the archive. | Selected and validated as the real event-driven direct-ScoreAdd workload on three supported test stacks. Fabric shows no reliable gain (−0.19% completion and +0.31% weighted function samples). Lithium and Lithium+Moonrise medians trend slower (+12.47%/+12.46% and +19.98%/+21.62%), but ranges are wide and cross zero; neither proves a stable regression or gain. The Moonrise campaign included a temporary dormant diagnostic mixin, so it is directional evidence. Compiler-off controls on Bellows 1.1.2 and Lithium+Bellows 1.1.2 fail native workload integrity (0/63 each); Lithium+Bellows+Moonrise 1.2.0 fails (0/215). These are datapack/mod workload failures, not compiler comparisons or general proof that Bellows breaks functions. Keep ScoreAdd disabled. Bellows-only 1.1.3 passes the pinned native 4×4×4 fixture; Lithium+Bellows 1.1.3 passes 6×6×6 (215/215). Five-pair no-Spark screens on Lithium+Bellows 1.1.3 pass exact parity for selective macro and ScoreAdd. Selective macro has a −18.83% median event-completion change but a −20.62% to +24.37% interval; ScoreAdd has a +3.60% slower median and a −2.04% to +91.11% interval. Both are screening only, not promotion evidence. Bellows 1.1.3 + Moonrise 1.2.0 passes the native Vein Miner 6×6×6 control and a five-pair selective-macro screen with exact workload parity; its −20.11% median completion change has a 93.75% interval from −36.67% to +7.01%, so remains screening evidence. Bellows 1.1.3 + Moonrise 1.2.1 fails startup on a missing `EntityLookup.entityById` shadow. An opt-in 4×4×4 Lithium callback diagnostic counted 7,116 generic and 1,122 optimized leaf callbacks (8,238 total); the optimized count matched the independent ScoreAdd counter. This single instrumented event is attribution data, not performance evidence. Artifact SHA-256: `fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e`. |
| [VeinMiner by Miraculixx](https://modrinth.com/datapack/veinminer) | Exact 26.3 datapack archive pinned; AGPL-3.0-only | This is a separate, older datapack artifact from the selected `vein_miner` 5.3.0 project. Its `1.3.6` archive has a 28-function tick-reachable graph but no direct literal fake-holder ScoreAdd commands. The user reports it works with Lithium+Bellows 1.1.2, while 5.3.0 stalls; the only visible difference noted was that 1.3.6 mined the vein in one tick while 5.3.0 spread work across ticks. | Retain as a negative eligibility finding; it is a compatibility cross-check, not a direct parity comparator. Do not substitute its mod build. Artifact SHA-256: `d0575fadca3fe41c8630e3748e7234a3f46c6280c9e9e4776710c7c6d2b1d605`. |
| [Incendium Legacy](https://modrinth.com/datapack/incendium/versions) | 26.3 artifact is listed | Modrinth's hosting guide flags Incendium's command-based gameplay features; the project is also a large Nether world-generation pack. | Excluded from this AI-assisted project unless Stardust Labs grants permission: its [license](https://github.com/Stardust-Labs-MC/license) explicitly prohibits using its works to test or debug AI systems. |

## Relevant packs deferred by target version

Modrinth's hosting guide also flags the following projects for recurring
command cost, but their current project pages do not list Minecraft 26.3:

- [Vanilla Refresh](https://modrinth.com/datapack/vanilla-refresh) is listed for
  26.2 and older. Its source describes a broad set of gameplay features, and
  Modrinth reports that it runs `execute` and other commands every tick.
- [Deeper Dark](https://modrinth.com/datapack/deeper_dark) is listed for 26.2
  and older. Modrinth describes tick functions for sculk conversions, portal
  checks, and new items.
- [True Ending](https://modrinth.com/datapack/true-ending) is listed for 26.1.x
  and older. Modrinth reports possible ongoing performance impact after the
  dragon fight.

These are reasonable future targets if exact 26.3 artifacts appear. Running
them under 26.3 without author support would mix command-compiler results with
unsupported-pack behavior. A separate 26.2 campaign could be useful, but it
would not establish the 26.3 target result.

## Evidence basis and test selection

The Modrinth [datapack hosting guide](https://support.modrinth.com/en/articles/14030919-datapacks-on-modrinth-hosting)
names Dynamic Lights, Incendium, Spawn Animations, True Ending, Vanilla Refresh,
Vein Miner, and Deeper Dark among datapacks reported to cause performance
issues. Its descriptions are a useful screening source, not an independent
benchmark or proof that every supported release has the same cost. Exact
archives must still be pinned, inspected for their active function tags, and
validated on the target server.

Pinned archive fingerprints for the exact candidate archives screened locally:

| Artifact | Version | SHA-256 |
|---|---|---|
| Everything Clings | 1.0.0, Minecraft 26.3 | `dcb9f5398f4840375f5ade0fe47f596071644a7a447dd0d9a6e99737d71e5c75` |
| Blastback Hotfix 3 | Minecraft 26.3 | `8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90` |
| Bigger Every Kill | 1.0.0, claimed Minecraft 26.3; rejected at registry load | `dc9406bb8152a1b08e8772e32db7080dd6ca87bdf1e8271f40daf34726115013` |
| Day Night Length | Minecraft 26.3 | `2d489be4a35711ebed9cf5ffdd72fabe56aa2f065d19e6cfaa9d8f133803e49a` |
| Dynamic Torches | 5.4, Minecraft 26.3 | `0bbc23c4fafa8fb76aa60ef02140d39e6e5306c9c0b5322391dbe4815eb03594` |
| Hostile Mobs Improve Over Time | 2.3, Minecraft 26.3 | `605a72ceee727a04dd8d524a8a2ceb9eb8d0e893e5dc4ad805419ccbe9191b6b` |
| Better Days Display | 1.2, Minecraft 26.3 | `19c5fcfaba9fca2ab7b01606105e8612aab172eaadf978c6615fb3d1b666730e` |
| Simple Timer | 1.2, Minecraft 26.3 | `54bc3dc9fa195f8356758dfd24446c0f052c4cec544027f40dcfbe75ca96f8e8` |
| Player Health Indicator | 2.4.0, Minecraft 26.3 | `2e93052aa77e2dd0f646fb8cb4041f6ef74470513e7ebd446a1e0abe7d3fb5db` |
| Bookshelf Generation Module | 4.2.1, Minecraft 26.3 | `1865b9d4f52eafd41eea90549b12ed5aada40fc99fec22bd574b9905eb98f75f` |
| Datapack Function Library | 5.1.0, Minecraft 26.1–26.3 | `fccaaeec3a6af331bd03075dcd662ab6d78490f9c37bb79ca60d01fe3dd9b865` |

The local archive copies are stored only under the ignored
`references/real-world/` tree. Their licenses and upstream claims remain
distinct from project measurements.

Use these workload classes:

1. **Continuous per-entity tick path:** Dynamic Lights, then Everything Clings
   after a population-stable fixture is found.
2. **Event-driven large command burst:** Blastback's TNT event remains
   deferred until its default 1-TNT restoration job drains and its saved source
   volume matches the untouched template. Its no-TNT dispatcher pilot is a
   separate, already profiled recurring path.
3. **Spawn burst:** Spawn Animations, with repeated controlled hostile-mob
   arrivals and a stable active-animation population.
4. **Player-triggered traversal burst:** VeinMiner, with deterministic vein
   shapes, tool state, and one player action per run.
5. **Worldgen plus command gameplay:** Incendium only if upstream permission
   for this project is obtained; pre-generate the Nether for the function arm.

Bigger Every Kill remains a useful future macro-and-entity-scan shape, but its
currently pinned archive is not a valid 26.3 workload. Do not patch the archive
locally and present that as upstream support.

## Additional exact 26.3 archive screening

These smaller or narrower packs provide useful future controls and workload
shapes. They do not currently add another eligible fake-holder ScoreAdd path.

| Workload | Exact archive finding | Use |
|---|---|---|
| [Hostile Mobs Improve Over Time](https://modrinth.com/datapack/hostile-mobs-improve-over-time) 2.3 | The exact 26.3 zip has a recurring one-second schedule plus per-player and entity ability work. The live paths contain no direct literal fake-holder additions; an otherwise eligible-looking `global.mcfunction` is not referenced by the archive's load, tick, or scheduled function paths. License is ARR. | A useful future selector, nested-call, and player-scaling profile after a dedicated setup/validation fixture is built. Keep the archive local and do not treat its unreachable `global` function as optimizer coverage. SHA-256: `605a72ceee727a04dd8d524a8a2ceb9eb8d0e893e5dc4ad805419ccbe9191b6b`. |
| [Better Days Display](https://modrinth.com/datapack/better-days-display/) 1.2 | Exact 26.3 archive with 124 functions and a per-player tick loop. Its timer additions are player-targeted and only run on a day change or active countdown; no direct literal fake-holder add appears in the scanned functions. | A per-player tick-scaling profile candidate, but no current ScoreAdd/fused coverage. SHA-256: `19c5fcfaba9fca2ab7b01606105e8612aab172eaadf978c6615fb3d1b666730e`. |
| [Simple Timer](https://modrinth.com/datapack/simple-timer1) 1.2 | Exact 26.3 archive with a 51-line tick function that updates a shared scoreboard timer and sends actionbar output. Scoreboard adds sit inside `execute` commands, so they do not match the current direct-entry prototype; license is ARR. | A compact command-loop control, not a large-scale pack or current optimization target. SHA-256: `54bc3dc9fa195f8356758dfd24446c0f052c4cec544027f40dcfbe75ca96f8e8`. |
| [Dynamic Torches](https://modrinth.com/datapack/dynamic-torches) 5.4 | Exact 26.3 archive with a tick entry that scans and tags entity classes, creates/removes light markers, and performs block checks. It has no direct literal fake-holder addition. | A smaller dynamic-light alternative for a future entity-scaling profile; it does not cover the current ScoreAdd specialization. SHA-256: `0bbc23c4fafa8fb76aa60ef02140d39e6e5306c9c0b5322391dbe4815eb03594`. |
| [Longer Days Datapack, Day and Night Length](https://modrinth.com/datapack/longer-days-datapack) | The pinned archive named Day Night Length has five functions and an active tick tag. Its small time-query loop has no eligible fake-holder add. | A lightweight control, not a tick-heavy target. SHA-256: `2d489be4a35711ebed9cf5ffdd72fabe56aa2f065d19e6cfaa9d8f133803e49a`. |
| [Player Health Indicator](https://modrinth.com/datapack/show-player-health) 2.4.0 | Its 26.3 archive registers a load function but no tick function tag. | Exclude from continuous tick profiles. SHA-256: `2e93052aa77e2dd0f646fb8cb4041f6ef74470513e7ebd446a1e0abe7d3fb5db`. |
| [Bookshelf Generation Module](https://modrinth.com/datapack/bookshelf-generation) 4.2.1 | Its 26.3 archive has a `process/tick` helper but no `#minecraft:tick` tag; it is a library module, not a standalone active workload. | Use only with an explicitly constructed generation task, not as an idle tick pack. SHA-256: `1865b9d4f52eafd41eea90549b12ed5aada40fc99fec22bd574b9905eb98f75f`. |
| [Datapack Function Library](https://modrinth.com/datapack/datapack-function-library) 5.1.0 | The exact 26.1–26.3 archive contains 98 `.mcfunction` files and is LGPL-3.0-or-later, but has no tick tag and no direct literal fake-holder `scoreboard players add` entries. Its reusable tick helpers run only when a host pack invokes them. | Candidate for selector/NBT integration coverage after building a documented host scenario; it does not provide an active real-world optimizer workload as shipped. SHA-256: `fccaaeec3a6af331bd03075dcd662ab6d78490f9c37bb79ca60d01fe3dd9b865`. |

For each candidate, pin the actual datapack archive and its SHA-256, record the
Minecraft support declaration, inspect `#minecraft:tick`, `#minecraft:load`,
and scheduled-function entry paths, and prove the selected path ran before
profiling.
Use Spark CPU trees to attribute code paths and `/tick query` for whole-server
tick distributions. Keep workload activation, setup, warmup, capture, and
post-capture observations distinct. World generation, idle tick load, and
event bursts are separate result groups.

## Additional source screening for optimizer eligibility

The exact matcher used by the current ScoreAdd prototype requires a direct
`scoreboard players add` command with one literal fake-player target beginning
with `#`, an objective, and an integer amount. A fused or bytecode region needs
at least two such commands adjacent in one function. A project-level claim of
tick cost or an eligible-looking command in an unreachable helper is not enough.

Two additional 26.3 leads were source-screened on 2026-10-28:

| Candidate | Source finding | Decision |
|---|---|---|
| [D Better Schedule](https://modrinth.com/datapack/d-better-schedule) | The Modrinth page lists 26.3 support and MIT licensing. In source commit [`334e271e6b00a96c25cad7053a131afd9b12fb3e`](https://github.com/Dahesor/D-Better-Schedule/tree/334e271e6b00a96c25cad7053a131afd9b12fb3e), the `new_player` advancement's `tick` criterion calls `z_private/uid/new`, which increments literal fake-player `#UID` once for a player's first matching tick. This is one reachable eligible ScoreAdd entry. The regular tick root instead increments `@a`, which the current matcher excludes. The source has 61 function files and no adjacent direct fake-player additions. | A source-level candidate for a one-time-per-player ScoreAdd/advancement path, pending an exact release archive pin and 26.3 runtime check. It does not cover fused/bytecode regions or provide a repeated tick-heavy eligible path. |
| [A* Pathfinding](https://modrinth.com/datapack/a-star-pathfinding) | Its Modrinth page lists 26.3 and GPL-3.0-only. The inspected source has 18 functions and an on-demand recursive path search, but no direct fake-player `ScoreAdd`. The loop mostly uses scoreboard `operation` commands on markers, which are outside the current prototype. | A possible recursive fallback workload, not current optimizer coverage; it is event-invoked rather than a tick workload. |

The source scan found D Better Schedule as one additional static candidate,
with a reachable but one-time-per-player `#UID` addition. Its exact release
archive has not yet been pinned or runtime-checked. For repeatable active
ScoreAdd profiling, Vein Miner remains the validated workload and Blastback
remains the lightweight dispatcher example. The scanned archives and source
have no adjacent eligible pair, so the fused/bytecode real-datapack gate
remains open. Do not replace that gate with a synthetic sidecar.
