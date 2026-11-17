"""The host gate: declared quiet-window precondition, per-arm noise rule, settle.

A benchmark campaign measures the host it runs on, so the harness carries the
host's admission rules as declared constants rather than leaving them to each
runner. Two rules are in force, both recorded from measured campaigns:

* **Quiet-window precondition** (``QUIET_LOAD_1M``): a confirmatory campaign
  starts only once the 1-minute load average is at or below the declared
  value. Introduced after campaigns failed their pre-declared reproducibility
  gates under a climbing host load, then diagnosed (batch 19, PERF-001
  attempts 4-5) as *self-induced*: sequential server boots ramp the load during
  the campaign. Waiting for the window is a precondition, never a relaxation of
  the campaign's own gate.

* **Per-arm noise rule** (``is_noisy``): an arm that starts while the 1-minute
  load average exceeds the CPU count is marked noisy and repeated once, with
  both results retained. This is a measurement-quality rule, not a filter:
  the noisy result stays in the report.

The host gate is also deliberately *insufficient* on its own: with the
precondition met, fresh-JVM variance at sub-millisecond scale can still fail a
tight reproducibility gate. That is a recorded limitation of the host, not
something the gate can fix, and a campaign whose own gate fails records the
failure as data.
"""

from __future__ import annotations

import os
import time

#: Declared quiet-window precondition: the 1-minute load average a campaign
#: start waits for. Chosen as the quietest floor observed across the campaigns
#: that motivated the rule (loads 3.5-4.0 at the quietest sustained window).
QUIET_LOAD_1M = 4.0

#: How long a campaign start or an inter-run settle will wait for the quiet
#: window before giving up (a give-up is a recorded campaign failure, never a
#: silent start under load).
SETTLE_TIMEOUT_SECONDS = 600.0

#: Poll interval while waiting for the quiet window.
POLL_SECONDS = 5.0


def load_average_1m() -> float:
    """Current 1-minute load average."""
    return os.getloadavg()[0]


def is_noisy(load_average_1m: float, cpu_count: int | None = None) -> bool:
    """The per-arm noise rule: a 1-minute load above the CPU count is noisy.

    Both the observed load and the verdict are recorded per arm so the rule is
    auditable from the report alone.
    """
    if cpu_count is None:
        cpu_count = os.cpu_count() or 1
    return load_average_1m > cpu_count


def wait_for_quiet_host(
    quiet_load: float = QUIET_LOAD_1M,
    timeout_seconds: float = SETTLE_TIMEOUT_SECONDS,
    poll_seconds: float = POLL_SECONDS,
) -> tuple[float, float]:
    """Wait until the 1-minute load average is at or below ``quiet_load``.

    Returns ``(observed_load, seconds_waited)``. When the timeout expires the
    current load is returned anyway so the caller records the precondition it
    actually ran under - a campaign that starts under load must be visible as
    such in its own report.
    """
    started = time.monotonic()
    load = load_average_1m()
    while load > quiet_load and time.monotonic() - started < timeout_seconds:
        time.sleep(poll_seconds)
        load = load_average_1m()
    return load, time.monotonic() - started


def settle_host(
    quiet_load: float = QUIET_LOAD_1M,
    timeout_seconds: float = SETTLE_TIMEOUT_SECONDS,
    poll_seconds: float = POLL_SECONDS,
) -> tuple[float, float]:
    """Inter-run settle: the same quiet-window wait, recorded per run.

    Used between successive runs inside one campaign so a run does not compete
    with the previous run's teardown (the diagnosed cause of the load ramp in
    batch 19's PERF-001 attempts).
    """
    return wait_for_quiet_host(quiet_load, timeout_seconds, poll_seconds)
