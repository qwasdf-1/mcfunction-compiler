#!/usr/bin/env python3
"""Diagnose measurement noise for the PERF-016 sustained fused-region fixture.

Runs the PERF-016 workload on a mod-free 26.3 server (the same fixture, the
same gamerules, the same 110/110-tick idle and warmup phases, and the same five
110-tick windows as `scripts/run_fused_region_sustained.py`), so a compiler
change cannot explain the result. It adds three things the campaign does not
record, per measurement window:

* `-Xlog:gc*,safepoint` on the server JVM, so GC pauses and safepoint totals can
  be compared against the window's tick times;
* the server process' major-fault counter and `VmSwap`;
* the host's global `pgmajfault` counter and `/proc/pressure/memory`.

With `--load N` it also injects `N` CPU-bound processes, which is the controlled
way to reproduce host contention and measure how the fixture's per-tick cost
responds to it. This is a diagnostic tool: its numbers measure the workspace's
noise floor, not the compiler's performance.

Example: compare the fixture's clean window cost against the same window under
injected load, which is the evidence behind the decision not to promote
`fused_regions` from a large-block campaign on a noisy host:

    python3 scripts/diagnose_perf016_host_noise.py --adds-per-tick 20000
    python3 scripts/diagnose_perf016_host_noise.py --adds-per-tick 5000 --load 8
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_fused_region_sustained import (  # noqa: E402
    IDLE_TICKS,
    IDLE_WINDOWS,
    MEASUREMENT_WINDOWS,
    RUN_ROOT,
    TICKS_PER_WINDOW,
    WARMUP_ACTIVE_TICKS,
    connect_player_when_ready,
    prepare_workdir,
    reserve_ports,
    score,
    setup_fixture,
    tick_metrics,
    wait_for_rcon,
    wait_for_score,
)
from run_runtime_probe import (  # noqa: E402
    SERVER_JAR_SHA256,
    generate_packet_ids,
    locate_official_server_jar,
)

def proc_faults(pid: int) -> tuple[int, int]:
    """Return (minor, major) fault counters from /proc/<pid>/stat.

    Zero-based field indices: 9 is minflt and 11 is majflt. This assumes the
    server's comm field contains no spaces, which holds for `java`.
    """
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split()
        return int(fields[9]), int(fields[11])
    except (OSError, IndexError, ValueError):
        return 0, 0


def proc_swap_kb(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmSwap:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def host_major_faults() -> int:
    try:
        for line in Path("/proc/vmstat").read_text().splitlines():
            if line.startswith("pgmajfault "):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


def memory_pressure() -> str:
    try:
        return Path("/proc/pressure/memory").read_text().strip().replace("\n", " ")
    except OSError:
        return "unavailable"


def load_average() -> str:
    try:
        return " ".join(Path("/proc/loadavg").read_text().split()[:3])
    except OSError:
        return "unavailable"


def start_load(processes: int) -> list[subprocess.Popen[bytes]]:
    """Spawn `processes` CPU-bound children; they are stopped in the finally block."""
    return [
        subprocess.Popen(
            [sys.executable, "-c", "while True: pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(processes)
    ]


def stop_load(burners: list[subprocess.Popen[bytes]]) -> None:
    for burner in burners:
        if burner.poll() is None:
            burner.terminate()
    for burner in burners:
        try:
            burner.wait(timeout=10)
        except subprocess.TimeoutExpired:
            burner.kill()


def gc_pause_summary(gc_log: Path) -> str:
    if not gc_log.exists():
        return "no gc log"
    pauses: list[float] = []
    for line in gc_log.read_text(errors="replace").splitlines():
        match = re.search(r"Pause (Young|Full|Remark|Cleanup).*?(\d+\.\d+)ms$", line)
        if match:
            pauses.append(float(match.group(2)))
    if not pauses:
        return "no pauses recorded"
    pauses.sort()
    total = sum(pauses)
    return (
        f"pauses={len(pauses)} total={total:.0f}ms max={pauses[-1]:.0f}ms "
        f"p50={pauses[len(pauses) // 2]:.0f}ms"
    )


def run_repeat(
    adds_per_tick: int,
    server_jar: Path,
    packet_ids,
    load_processes: int,
    retain: bool,
) -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work = RUN_ROOT / f"perf016-noise-{run_id}-{adds_per_tick}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    server_port, rcon_port = reserve_ports(2)
    password = f"perf016-noise-{run_id}"
    prepare_workdir(
        work,
        mode="vanilla",
        stack="fabric",
        server_port=server_port,
        rcon_port=rcon_port,
        password=password,
        adds_per_tick=adds_per_tick,
    )
    gc_log = work / "gc.log"
    log_handle = (work / "server.log").open("wb")
    command = [
        "java",
        "-Xms512M",
        "-Xmx2G",
        f"-Xlog:gc*,safepoint:file={gc_log}:time,uptime,level:filecount=1",
        "-jar",
        str(server_jar),
        "nogui",
    ]
    print(f"[{run_id}] adds_per_tick={adds_per_tick} load={load_processes}")
    print(f"    host load before run: {load_average()}")
    print(f"    memory pressure: {memory_pressure()}")
    burners: list[subprocess.Popen[bytes]] = []
    server: subprocess.Popen[bytes] | None = None
    try:
        if load_processes:
            burners = start_load(load_processes)
            time.sleep(1.0)
        server = subprocess.Popen(command, cwd=work, stdout=log_handle, stderr=subprocess.STDOUT)
        rcon = wait_for_rcon(server, rcon_port, password)
        connect_player_when_ready(server, server_port, packet_ids)
        rcon.command("gamemode spectator FCFused")
        rcon.command("tp FCFused 4 100 4")
        setup_fixture(rcon, mode="vanilla")
        start = score(rcon, "#server_ticks")
        wait_for_score(server, rcon, "#server_ticks", start + IDLE_TICKS)
        rcon.command("scoreboard players set #enabled fc_fused 1")
        wait_for_score(
            server, rcon, "#active_ticks", WARMUP_ACTIVE_TICKS, timeout_seconds=900
        )
        for index in range(1, MEASUREMENT_WINDOWS + 1):
            window_start = score(rcon, "#active_ticks")
            wall = time.monotonic()
            minor0, major0 = proc_faults(server.pid)
            host0 = host_major_faults()
            wait_for_score(
                server,
                rcon,
                "#active_ticks",
                window_start + TICKS_PER_WINDOW,
                timeout_seconds=900,
            )
            metrics = tick_metrics(rcon.command("tick query"))
            elapsed = time.monotonic() - wall
            minor1, major1 = proc_faults(server.pid)
            print(
                f"    window {index}: avg={metrics['tick_average_ms']:6.2f}ms "
                f"p95={metrics['tick_p95_ms']:6.2f}ms wall={elapsed:5.2f}s "
                f"ticks/s={TICKS_PER_WINDOW / elapsed:5.1f} "
                f"majflt=+{major1 - major0} minflt=+{(minor1 - minor0) // 1000}k "
                f"host_majflt=+{host_major_faults() - host0} "
                f"VmSwap={proc_swap_kb(server.pid)}kB"
            )
        print(f"    gc: {gc_pause_summary(gc_log)}")
        rcon.command("scoreboard players set #enabled fc_fused 0")
        idle: list[float] = []
        for _ in range(IDLE_WINDOWS):
            mark = score(rcon, "#server_ticks")
            wait_for_score(server, rcon, "#server_ticks", mark + IDLE_TICKS)
            idle.append(tick_metrics(rcon.command("tick query"))["tick_average_ms"])
        print(f"    idle windows (workload disabled): {[round(x, 2) for x in idle]}")
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        stop_load(burners)
        log_handle.close()
        if retain:
            print(f"    workdir retained for gc.log inspection: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adds-per-tick",
        type=int,
        required=True,
        help="contiguous eligible add block size; use the checked-in 5000 or 20000",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="independent server runs; default 1",
    )
    parser.add_argument(
        "--load",
        type=int,
        default=0,
        help="inject N CPU-bound processes during the run to reproduce contention",
    )
    parser.add_argument(
        "--retain",
        action="store_true",
        help="keep each disposable workdir (including gc.log) instead of deleting it",
    )
    args = parser.parse_args()
    if args.retain:
        print("workdirs are retained for gc.log inspection; remove them manually")
    if args.adds_per_tick < 2:
        parser.error("--adds-per-tick must be at least 2")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.load < 0:
        parser.error("--load must not be negative")

    server_jar = locate_official_server_jar()
    if hashlib.sha256(server_jar.read_bytes()).hexdigest() != SERVER_JAR_SHA256:
        raise SystemExit(f"Minecraft 26.3 server hash mismatch: {server_jar}")
    packet_ids = generate_packet_ids(server_jar)

    for _ in range(args.repeats):
        run_repeat(args.adds_per_tick, server_jar, packet_ids, args.load, args.retain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
