# mc-harness: Engine-Agnostic Differential-Oracle Harness

> **Frozen at 1.0.0, vendored.** This is the harness every recorded Function
> Compiler campaign was verified against, copied unchanged (code identical since
> the 1.0.0 extraction) from the maintainers' shared mc-mods tooling so this
> repository builds and runs on its own. It is not changed; new measurement
> machinery lives outside this repository.

Shared harness machinery for Minecraft server-side projects that run
**differential** measurements against a pinned, hash-verified official server
and optimization-mod stacks. Extracted from
Function Compiler's runtime probe and benchmark
campaigns (roadmap step 6, batch 20, 2026-11-09) so the harness had one
canonical, version-pinned home instead of per-runner copies.

## Modules

| Module | Contents |
| --- | --- |
| `mc_harness.mod_stacks` | Pinned 26.3 Fabric mod artifacts (filename + SHA-256) and stack definitions; per-project jar-directory resolution and pin verification |
| `mc_harness.paired_stats` | Exact sign/order-statistic paired-campaign analysis (median paired change, discrete-coverage interval, promotion decision, no-regression floor) |
| `mc_harness.server_lifecycle` | RCON client (plus the split-response-draining variant), pinned official server-jar location + fingerprint verification, Mojang `packets.json` report extraction, RCON readiness wait, EULA/property helpers |
| `mc_harness.campaign` | Counterbalanced-campaign primitives: free-port reservation, player connect with transient-close retry, score reads and workload-progress waits, `/tick query` parsing, per-label median windows |
| `mc_harness.host_gate` | The declared quiet-window precondition, the per-arm host-noise rule (load > CPU count), and the inter-run settle, with their recorded rationale |

## What is deliberately not here

**The headless protocol client stays project-owned.** Each consuming project
keeps its own client pinned to its target Minecraft protocol (for 26.3 that is
protocol 777 with position-confirmation framing) so a shared-kit change can
never silently re-target a live probe or campaign. The modules here accept the
client and packet-ID classes by injection:

```python
from mc_harness.server_lifecycle import generate_packet_ids
from player_bot import PacketIds  # project-owned, protocol-pinned

packet_ids = generate_packet_ids(server_jar, PacketIds)
```

Likewise the fixture content, expected maps, arm configurations, and campaign
designs (pairs, seeds, predeclared thresholds) stay in each project: the
harness provides the machinery, never the experiment.

## Version pinning

`mc_harness.__version__` is the pin. Consuming projects assert it at import
time (`mc_harness.assert_version("1.0.0")`) and record the pinned version in
their docs, so a harness update cannot reach a project's recorded campaign
unannounced.

## Consumption

Function Compiler's scripts import the package by path (no installation required):

```python
MC_HARNESS_ROOT = Path(__file__).resolve().parents[1] / "vendor" / "mc-harness"
sys.path.insert(0, str(MC_HARNESS_ROOT))
from mc_harness import assert_version
assert_version("1.0.0")
```
