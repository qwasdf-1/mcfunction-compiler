# PERF-005/006: Bellows selector and entity-NBT profiles

**Run:** 2026-10-28, five randomized repetitions per arm  
**Raw evidence:** ignored `build/benchmarks/PERF-005-006/20261028T160417Z/`  
**Decision:** Parity passed for the measured cases. Bellows reduced sampled function cost in the entity-NBT workload. The fused compiler prototype did not show a repeatable reduction and remains disabled.

## Method

The run started a fresh Minecraft server and world for each arm. It ran two
controlled tick workloads, randomizing both mode order and workload order by
seed `20261028`. Each workload warmed for four seconds, then Spark sampled all
threads for 18 seconds at 1 ms. The server used `-Xms1G -Xmx2G`; the test
machine was an Intel Core i7-10700 (8 cores / 16 threads), x86_64 Linux, with
OpenJDK 25.0.4.1. One stationary headless player kept the test area active.

| Arm | Server and enabled features |
|---|---|
| Vanilla | Official Mojang 26.3 dedicated server; no compiler mod |
| Fabric off | Project Fabric runtime and dev mod loaded; all compiler features off |
| Bellows off | Fabric off plus Bellows 1.1.2 |
| Fused interpreted | Fabric with ScoreAdd and fused-interpreted prototypes on; no Bellows |
| Bellows + fused interpreted | Bellows plus the same compiler prototypes |

The official vanilla server SHA-256 was
`d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64`.
Bellows 1.1.2 was pinned to
`d0c7218e7e368c7d1473483881540ff78554853ff0a4f0bab098df6b3c753b67` and Spark
1.10.194 standalone agent to
`a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9`.
Compiler metric counters, compiler timers, runtime tracing, and function
timers were disabled during capture. The compiler arms verified four compiled
ScoreAdd entries and at least one compiled fused region before profiling.

Each tick repeated its selected workload eight times. The selector fixture
issued an AABB/nearest query capped at 16, a negative-tag/distance/furthest
query capped at 12, and a random query capped at 8. The NBT fixture read each
zombie's Health into a score, set NoAI to `1b`, and counted the update. Both
workloads ran over the same 64 stationary zombies. A four-command literal
fake-holder ScoreAdd function ran eight times per active tick to exercise the
compiler path in compiler-enabled arms.

## Parity

All 25 server arms passed their setup and output checks. All 20 non-vanilla
arm/trial comparisons matched that trial's vanilla result:

- Selector counts per active tick were 128 for the box query, 96 for the
  furthest query, and 64 for the random query; ScoreAdd totals were 32.
- NBT operations updated all 64 entities eight times per active tick (512
  updates); every zombie retained `NoAI:1b`, and every Health score was 20000.
  ScoreAdd totals were 32.

The random selector checks cardinality, not selected identity, because each
independent server has a separate random state. The selector fixture also
records aggregate counts rather than per-entity identity. These profiles do
not replace the separate identity- and order-sensitive compatibility matrix.

## Results

`/tick query` values below are the median of five per-run medians. MAD is the
median absolute deviation of per-run average tick time. Spark's function share
is the median per-run proportion of inclusive weighted
`ServerFunctionManager.execute` samples within all server-thread samples.

| Workload | Arm | Avg tick ms (MAD) | P50 tick ms | P95 tick ms | Function sample share |
|---|---|---:|---:|---:|---:|
| Selector | Vanilla | 5.8 (2.0) | 4.6 | 16.2 | 1.73% |
| Selector | Fabric off | 4.4 (0.3) | 4.0 | 5.9 | 0.98% |
| Selector | Bellows off | 4.2 (0.3) | 3.9 | 6.3 | 1.16% |
| Selector | Fused interpreted | 5.1 (0.5) | 4.8 | 7.7 | 1.15% |
| Selector | Bellows + fused interpreted | 5.4 (0.3) | 4.4 | 12.3 | 1.06% |
| Entity NBT | Vanilla | 10.1 (2.2) | 8.7 | 16.8 | 16.92% |
| Entity NBT | Fabric off | 10.0 (1.4) | 8.8 | 16.4 | 13.63% |
| Entity NBT | Bellows off | 5.8 (0.5) | 4.8 | 11.9 | 4.29% |
| Entity NBT | Fused interpreted | 10.8 (1.7) | 8.5 | 18.0 | 13.63% |
| Entity NBT | Bellows + fused interpreted | 6.9 (0.4) | 5.5 | 13.2 | 4.21% |

Across the five paired runs, Bellows-only reduced the entity-NBT function
sample share by a median 67.6% relative to Fabric off; every pair was lower
(range: 43.4%–77.2% lower). The paired median average-tick change was 30.6%
lower, with all five pairs lower. This is evidence for Bellows on this exact
repeated NBT fixture, not a general claim about other entity-data paths.

The fused compiler did not reduce the sampled function share. Relative to
Fabric off, the paired median share changed by +17.3% on the selector workload
and +2.3% on entity NBT. Adding it to Bellows changed the share by +2.8% and
+8.5%, respectively. Bellows-only selector results did not show a repeatable
gain: the paired median function-share change was +35.5% (range -83.5% to
+119.6%). Paired average-tick changes for fused versus Fabric off were +22.7%
on selectors and -5.3% on entity NBT. Adding fused interpretation to Bellows
changed paired average tick time by +31.7% on selectors and +25.0% on NBT,
though individual runs varied. These measurements do not establish a compiler
speedup; keep ScoreAdd and fused execution disabled.

## Limits and next steps

This is a synthetic, high-repeat control workload, not a real datapack. The
vanilla arm uses Mojang's standalone server while every other arm uses the
project's Fabric runtime; the Fabric-off arm isolates compiler features, not
Fabric Loader or Fabric API. Spark values are sampling estimates and `/tick
query` is a whole-server rolling window. This result does not close PERF-007
by itself. The separate PERF-011 Vein Miner campaign supplies native
direct-ScoreAdd workload coverage on Fabric, Lithium, Lithium+Moonrise, and
Lithium+Bellows 1.1.3. Its callback counter and the Bellows 1.1.3 queue counter
match the datapack work count. The Bellows 1.1.3 ScoreAdd screen has no
reliable gain; its Moonrise combinations still need native validation. No
screened pack has an adjacent eligible pair for real-world fused/bytecode
measurements.

The full JSON manifest, trial order, per-profile hashes, Spark files, and
individual trial values are retained locally in the raw evidence directory.
