"""Engine-agnostic differential-oracle harness for Minecraft server-side projects.

This package is the shared home of the harness machinery that
`mc-mods/function-compiler`'s runtime probe and benchmark campaigns were
extracted from (roadmap step 6, batch 20, 2026-11-09). It is deliberately
engine-agnostic:

* `mod_stacks`        - pinned 26.3 Fabric mod artifacts and stack definitions.
* `paired_stats`      - exact sign/order-statistic paired-campaign analysis.
* `server_lifecycle`  - RCON clients, pinned server-jar location, packet-report
  generation, RCON readiness, and server-property helpers.
* `campaign`          - the counterbalanced-campaign primitives (port
  reservation, player connect, score waits, tick-query parsing).
* `host_gate`         - the declared quiet-window precondition, the per-arm
  host-noise rule, and the inter-run settle.

What is NOT here, by project decision: the headless protocol client. Each
project owns its own client pinned to its target protocol (see
`function-compiler/tests/runtime/player_bot.py`, pinned to 26.3 protocol 777),
and the modules here accept the client classes by injection. That keeps one
protocol pin per project and prevents a shared kit change from silently
re-targeting a live probe.

Version pinning: consuming projects assert `mc_harness.__version__` against
the version they were verified against, so a harness change cannot reach a
project's campaign unannounced.
"""

from __future__ import annotations

__version__ = "1.0.0"


def print_version() -> None:
    print(__version__)


def assert_version(expected: str) -> None:
    """Fail loudly when a project consumes a harness version it was not pinned to."""
    if __version__ != expected:
        raise RuntimeError(
            f"mc_harness version pin mismatch: this project is pinned to "
            f"{expected} but the harness at the resolved path is {__version__}"
        )
