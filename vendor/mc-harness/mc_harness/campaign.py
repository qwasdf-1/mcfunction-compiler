"""Counterbalanced-campaign primitives shared by benchmark runners.

Extracted (roadmap step 6, batch 20) from
`function-compiler/scripts/run_fused_region_sustained.py` and
`function-compiler/scripts/run_selective_macro_sustained.py`, where the two
runners had grown byte-identical copies of these helpers (they differed only
in the probe player's name and the fixture's scoreboard objective). Both are
now parameters, and the protocol client class is injected so each project pins
its own client (AGENTS.md: the protocol client remains project-owned).
"""

from __future__ import annotations

import re
import socket
import statistics
import subprocess
import time
from typing import Any

HOST = "127.0.0.1"


def reserve_ports(count: int, host: str = HOST) -> tuple[int, ...]:
    """Reserve ``count`` distinct free ports by binding and holding them briefly."""
    reservations: list[socket.socket] = []
    try:
        while len(reservations) < count:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.bind((host, 0))
            if any(probe.getsockname()[1] == item.getsockname()[1] for item in reservations):
                probe.close()
                continue
            reservations.append(probe)
        return tuple(int(item.getsockname()[1]) for item in reservations)
    finally:
        for probe in reservations:
            probe.close()


def connect_player_when_ready(
    process: subprocess.Popen[bytes],
    server_port: int,
    packet_ids: Any,
    *,
    player_name: str,
    player_bot_cls: Any,
    host: str = HOST,
    attempts: int = 3,
) -> tuple[Any, int]:
    """Let dedicated-server startup settle and retry transient login closes."""
    time.sleep(1.0)
    attempt_count = 0
    last_error: Exception | None = None
    while attempt_count < attempts:
        if process.poll() is not None:
            raise RuntimeError(
                f"Minecraft exited before player login with code {process.returncode}"
            )
        attempt_count += 1
        bot = player_bot_cls(player_name, host, server_port, packet_ids)
        try:
            return bot.connect(), attempt_count
        except (ConnectionError, RuntimeError) as error:
            bot.close()
            last_error = error
            if "server closed the player connection" not in str(error):
                raise
            if attempt_count < attempts:
                time.sleep(1.0)
    raise RuntimeError(
        f"Minecraft closed all {attempts} player login attempts; last error: {last_error}"
    )


def score(rcon: Any, holder: str, objective: str) -> int:
    """Read a scoreboard holder's score; the holder/objective are per fixture."""
    response = rcon.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not read {holder} {objective}: {response!r}")
    return int(match.group(1))


def wait_for_score(
    process: subprocess.Popen[bytes],
    rcon: Any,
    holder: str,
    objective: str,
    target: int,
    timeout_seconds: int = 240,
) -> int:
    """Wait until the holder's score reaches the target (workload progress gate)."""
    deadline = time.monotonic() + timeout_seconds
    current = score(rcon, holder, objective)
    while current < target and time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft exited while waiting for {holder}")
        time.sleep(0.2)
        current = score(rcon, holder, objective)
    if current < target:
        raise TimeoutError(f"{holder} reached {current}; expected at least {target}")
    return current


def tick_metrics(response: str) -> dict[str, float]:
    """Parse a ``/tick query`` summary into named millisecond metrics."""
    patterns = {
        "tick_average_ms": r"Average time per tick: ([0-9.]+)ms",
        "tick_p50_ms": r"P50: ([0-9.]+)ms",
        "tick_p95_ms": r"P95: ([0-9.]+)ms",
        "tick_p99_ms": r"P99: ([0-9.]+)ms",
    }
    parsed: dict[str, float] = {}
    for label, pattern in patterns.items():
        match = re.search(pattern, response)
        if match is None:
            raise RuntimeError(f"Could not parse {label} from /tick query: {response!r}")
        parsed[label] = float(match.group(1))
    return parsed


def median_window(windows: list[dict[str, float]]) -> dict[str, float]:
    """Per-label median across several sampled tick-query windows.

    Sampling several full windows and taking the median keeps one GC pause or
    JIT hiccup from defining an arm.
    """
    if not windows:
        raise ValueError("median_window requires at least one window")
    labels = windows[0]
    return {
        label: statistics.median(float(window[label]) for window in windows)
        for label in labels
    }
