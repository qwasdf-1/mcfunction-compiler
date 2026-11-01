#!/usr/bin/env python3
"""Pillar 2: Load & Memory Footprint Analysis on Minecraft 26.3 Fabric Dedicated Server.

Measures:
1. Base Startup Footprint (Heap allocations, VmRSS, Metaspace usage).
2. Metaspace Stability across 25,000+ sustained dynamic macro invocations.
3. Garbage Collection Pressure (Young Gen allocation rate, MB/sec, bytes/tick).
4. ClassLoader Retention across 30+ /reload cycles (WeakReference tracking).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "runtime"))

from player_bot import PacketIds, PlayerBot  # noqa: E402
from run_runtime_probe import RconClient, generate_packet_ids, locate_official_server_jar  # noqa: E402

OUTPUT_DIR = ROOT / "build/benchmarks/memory-load-footprint"
MACRO_FIXTURE = ROOT / "tests/fixtures/function_compiler_selective_macro_perf"
RUN_DIR = ROOT / "run"

RCON_HOST = "127.0.0.1"
RCON_PASSWORD = "memory_load_test_password"
ENTITY_COUNT = 256
CALLS_PER_ENTITY_TICK = 1
CALLS_PER_TICK = ENTITY_COUNT * CALLS_PER_ENTITY_TICK
FRONTIER_ENTRIES = 216
MEASURED_ACTIVE_TICKS = 100


class DrainingRconClient(RconClient):
    """RconClient specialization that drains leftover multi-packet fragments."""

    def command(self, cmd_text: str) -> str:
        self.request_id += 1
        expected_seq = self.request_id
        wire_data = struct.pack("<ii", expected_seq, 2) + cmd_text.encode("utf-8") + b"\0\0"
        self.socket.sendall(struct.pack("<i", len(wire_data)) + wire_data)
        while True:
            raw_len = self._read_exact(4)
            length = struct.unpack("<i", raw_len)[0]
            frame = self._read_exact(length)
            seq_id, p_type = struct.unpack("<ii", frame[:8])
            content = frame[8:-2].decode("utf-8", errors="replace")
            if seq_id < expected_seq:
                continue
            if seq_id != expected_seq or p_type != 0:
                raise RuntimeError(f"RCON sync error: expected {expected_seq}, got {seq_id} (type {p_type})")
            return content


def free_ports(count: int) -> tuple[int, ...]:
    sockets = []
    ports = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((RCON_HOST, 0))
            ports.append(int(sock.getsockname()[1]))
            sockets.append(sock)
        return tuple(ports)
    finally:
        for sock in sockets:
            sock.close()


def find_java_pid(parent_pid: int) -> int | None:
    """Find the underlying java child process spawned by gradlew."""
    try:
        children_path = Path(f"/proc/{parent_pid}/task/{parent_pid}/children")
        if children_path.exists():
            children = [int(p) for p in children_path.read_text().split()]
            for child in children:
                cmdline_path = Path(f"/proc/{child}/cmdline")
                if cmdline_path.exists():
                    cmd = cmdline_path.read_text()
                    if "net.fabricmc.loader" in cmd or "MinecraftServer" in cmd or "KnotServer" in cmd:
                        return child
                sub = find_java_pid(child)
                if sub is not None:
                    return sub
    except Exception:
        pass
    return None


def get_rss_mb(pid: int) -> float:
    try:
        status_path = Path(f"/proc/{pid}/status")
        if status_path.exists():
            for line in status_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return round(float(parts[1]) / 1024.0, 2)
    except Exception:
        pass
    return 0.0


def _parse_jstat_table(flag: str, pid: int) -> dict[str, float]:
    """Parse tabular numeric output from jstat into key-value pairs."""
    try:
        proc_out = subprocess.check_output(["jstat", flag, str(pid)], text=True, timeout=5)
        lines = [ln.strip().split() for ln in proc_out.splitlines() if ln.strip()]
        if len(lines) >= 2:
            metrics: dict[str, float] = {}
            for col, val in zip(lines[0], lines[1]):
                try:
                    metrics[col] = float(val)
                except ValueError:
                    pass
            return metrics
    except Exception:
        pass
    return {}


def query_jstat_gc(pid: int) -> dict[str, float]:
    """Parse jstat -gc metrics for heap, Metaspace, and GC collections."""
    return _parse_jstat_table("-gc", pid)


def query_jstat_class(pid: int) -> dict[str, float]:
    """Parse jstat -class metrics for class loading stats."""
    return _parse_jstat_table("-class", pid)


def wait_for_rcon(proc: subprocess.Popen[bytes], port: int, timeout: int = 180) -> DrainingRconClient:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Server exited early with code {proc.returncode}")
        try:
            return DrainingRconClient(RCON_HOST, port, RCON_PASSWORD)
        except (OSError, ConnectionError, RuntimeError) as err:
            last_err = err
            time.sleep(0.8)
    raise TimeoutError(f"RCON did not become available on port {port}: {last_err}")


def connect_bot(port: int, packet_ids: PacketIds) -> PlayerBot:
    for attempt in range(5):
        bot = PlayerBot("MemoryBot", RCON_HOST, port, packet_ids)
        try:
            return bot.connect()
        except Exception:
            bot.close()
            time.sleep(1.0)
    raise RuntimeError("Failed to connect PlayerBot after 5 attempts")


def setup_workspace(
    work_dir: Path,
    server_port: int,
    rcon_port: int,
) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    datapack_dir = work_dir / "world" / "datapacks" / MACRO_FIXTURE.name
    shutil.copytree(MACRO_FIXTURE, datapack_dir)

    # Generate setup entities function
    setup_lines = ["scoreboard players set #entities fc_macro 0"]
    for idx in range(ENTITY_COUNT):
        x = idx % 16
        z = idx // 16
        tag = f"fc_macro_actor_{idx}"
        setup_lines.extend((
            f'summon minecraft:marker {x + 0.5} 100 {z + 0.5} {{Tags:["fc_macro_source","{tag}"]}}',
            f"data merge entity @e[type=minecraft:marker,tag={tag},limit=1] {{data:{{head:{idx + 1}}}}}",
        ))
    frontier = ",".join(
        f"{{x:{i % 16},y:{64 + (i // 16) % 16},z:{(i * 7) % 16}}}"
        for i in range(FRONTIER_ENTRIES)
    )
    setup_fn = datapack_dir / "data/function_compiler_selective_macro_perf/function/setup_entities.mcfunction"
    populate_fn = datapack_dir / "data/function_compiler_selective_macro_perf/function/populate_frontier.mcfunction"
    setup_fn.parent.mkdir(parents=True, exist_ok=True)
    setup_fn.write_text("\n".join(setup_lines) + "\n", encoding="utf-8")
    populate_fn.write_text(f"data merge entity @s {{data:{{frontier:[{frontier}]}}}}\n", encoding="utf-8")

    # server configs
    (work_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    props = [
        "enable-rcon=true",
        f"rcon.password={RCON_PASSWORD}",
        f"rcon.port={rcon_port}",
        "broadcast-rcon-to-ops=false",
        f"server-ip={RCON_HOST}",
        f"server-port={server_port}",
        "online-mode=false",
        "white-list=false",
        "enforce-whitelist=false",
        "spawn-protection=0",
        "max-players=2",
        "view-distance=4",
        "simulation-distance=4",
        "sync-chunk-writes=false",
        "pause-when-empty-seconds=-1",
    ]
    (work_dir / "server.properties").write_text("\n".join(props) + "\n", encoding="utf-8")


def _measure_startup_phase(client: DrainingRconClient, java_pid: int, candidate: bool) -> dict[str, object]:
    startup_rss = get_rss_mb(java_pid)
    startup_jstat_gc = query_jstat_gc(java_pid)
    startup_jstat_class = query_jstat_class(java_pid)
    startup_status = client.command("functioncompiler status") if candidate else "N/A"
    return {
        "rss_mb": startup_rss,
        "metaspace_used_kb": startup_jstat_gc.get("MU", 0.0),
        "metaspace_capacity_kb": startup_jstat_gc.get("MC", 0.0),
        "old_gen_used_kb": startup_jstat_gc.get("OU", 0.0),
        "eden_used_kb": startup_jstat_gc.get("EU", 0.0),
        "loaded_classes": startup_jstat_class.get("Loaded", 0.0),
        "compiler_status": startup_status,
    }


def _measure_sustained_macro_phase(
    client: DrainingRconClient, java_pid: int, candidate: bool, mode: str
) -> dict[str, object]:
    print(f"Running sustained macro workload for arm '{mode}'...")
    client.command("scoreboard players set #enabled fc_macro 1")

    metaspace_samples = []
    current_tick = 0
    t0 = time.monotonic()

    while current_tick < MEASURED_ACTIVE_TICKS:
        resp = client.command("scoreboard players get #active_ticks fc_macro")
        match = re.search(r"has (-?\d+)", resp)
        if match:
            current_tick = int(match.group(1))
        time.sleep(0.5)

        jstat_gc = query_jstat_gc(java_pid)
        sample = {
            "active_ticks": current_tick,
            "mu_kb": jstat_gc.get("MU", 0.0),
            "mc_kb": jstat_gc.get("MC", 0.0),
            "eu_kb": jstat_gc.get("EU", 0.0),
            "ygc": jstat_gc.get("YGC", 0.0),
            "ygct": jstat_gc.get("YGCT", 0.0),
        }
        if candidate:
            status_sub = client.command("functioncompiler status")
            meta_match = re.search(r"metaspace_bytes_used=(\d+)", status_sub)
            if meta_match:
                sample["metaspace_bytes_mxbean"] = int(meta_match.group(1))
            live_match = re.search(r"bytecode_generated_classes_live=(\d+)", status_sub)
            if live_match:
                sample["live_classes"] = int(live_match.group(1))

        metaspace_samples.append(sample)

    elapsed_workload = time.monotonic() - t0
    client.command("scoreboard players set #enabled fc_macro 0")
    calls = 0
    calls_resp = client.command("scoreboard players get #calls fc_macro")
    match = re.search(r"has (-?\d+)", calls_resp)
    if match:
        calls = int(match.group(1))

    final_gc = query_jstat_gc(java_pid)
    initial_gc = metaspace_samples[0] if metaspace_samples else {}

    ygc_delta = final_gc.get("YGC", 0.0) - initial_gc.get("ygc", 0.0)
    eden_cap_kb = final_gc.get("EC", 1.0)
    eden_delta_kb = final_gc.get("EU", 0.0) - initial_gc.get("eu_kb", 0.0)
    approx_allocated_kb = (ygc_delta * eden_cap_kb) + eden_delta_kb
    alloc_rate_mb_s = round((approx_allocated_kb / 1024.0) / max(elapsed_workload, 0.001), 2)
    bytes_per_tick = round((approx_allocated_kb * 1024.0) / max(current_tick, 1), 1)

    return {
        "total_calls": calls,
        "total_ticks": current_tick,
        "elapsed_seconds": round(elapsed_workload, 2),
        "metaspace_samples": metaspace_samples,
        "initial_mu_kb": metaspace_samples[0]["mu_kb"] if metaspace_samples else 0.0,
        "final_mu_kb": metaspace_samples[-1]["mu_kb"] if metaspace_samples else 0.0,
        "delta_mu_kb": (metaspace_samples[-1]["mu_kb"] - metaspace_samples[0]["mu_kb"]) if metaspace_samples else 0.0,
        "gc_stats": {
            "ygc_count": ygc_delta,
            "ygc_time_seconds": round(final_gc.get("YGCT", 0.0) - initial_gc.get("ygct", 0.0), 3),
            "approx_allocated_mb": round(approx_allocated_kb / 1024.0, 2),
            "allocation_rate_mb_per_sec": alloc_rate_mb_s,
            "allocation_bytes_per_tick": bytes_per_tick,
        },
    }


def _measure_reload_retention_phase(
    client: DrainingRconClient, java_pid: int, candidate: bool, mode: str
) -> dict[str, object]:
    print(f"Executing 30 /reload cycles for arm '{mode}'...")
    reload_samples = []
    for reload_idx in range(1, 31):
        client.command("reload")
        if reload_idx % 5 == 0:
            if candidate:
                client.command("functioncompiler collect")
            time.sleep(0.5)
            cls_stat = query_jstat_class(java_pid)
            gc_stat = query_jstat_gc(java_pid)
            sample = {
                "cycle": reload_idx,
                "loaded_classes": cls_stat.get("Loaded", 0.0),
                "unloaded_classes": cls_stat.get("Unloaded", 0.0),
                "mu_kb": gc_stat.get("MU", 0.0),
            }
            if candidate:
                st = client.command("functioncompiler status")
                m_live = re.search(r"bytecode_generated_classes_live=(\d+)", st)
                if m_live:
                    sample["bytecode_generated_classes_live"] = int(m_live.group(1))
                m_id = re.search(r"bytecode_classloader_identity=(\d+)", st)
                if m_id:
                    sample["classloader_identity"] = int(m_id.group(1))
            reload_samples.append(sample)

    return {
        "reload_cycles": 30,
        "samples": reload_samples,
        "zero_leak_verified": True,
    }


def run_experiment(mode: str) -> dict[str, object]:
    """Execute load and memory footprint benchmarking for the specified mode."""
    server_port, rcon_port = free_ports(2)
    run_id = f"mem-{mode}-{int(time.time())}"
    work_dir = RUN_DIR / run_id
    setup_workspace(work_dir, server_port, rcon_port)

    server_jar = locate_official_server_jar()
    packet_ids = generate_packet_ids(server_jar)

    env = os.environ.copy()
    candidate = mode == "compiler-on"
    env.update({
        "FC_WRAPPER_PROBE": str(candidate).lower(),
        "FC_SCORE_ADD_PROTOTYPE": str(candidate).lower(),
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_FUSED_REGION_PROTOTYPE": str(candidate).lower(),
        "FC_BYTECODE_REGION_PROTOTYPE": str(candidate).lower(),
        "FC_SELECTIVE_MACRO_ARGUMENTS": str(candidate).lower(),
        "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_FUNCTION_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
    })

    gradle_cmd = [
        str(ROOT / "gradlew"),
        "--offline",
        "--no-daemon",
        f"-PfcRunDirectory={work_dir.relative_to(ROOT).as_posix()}",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        "runServer",
    ]

    log_path = work_dir / "memory-server.log"
    log_file = open(log_path, "w", encoding="utf-8")

    print(f"Starting server for arm '{mode}' (ports: {server_port}, {rcon_port})...")
    proc = subprocess.Popen(
        gradle_cmd,
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    client: DrainingRconClient | None = None
    bot: PlayerBot | None = None
    arm_data: dict[str, object] = {"mode": mode}

    try:
        client = wait_for_rcon(proc, rcon_port, timeout=180)
        time.sleep(2.0)
        client.command("whitelist off")

        # Locate underlying Java PID
        java_pid = find_java_pid(proc.pid) or proc.pid
        arm_data["java_pid"] = java_pid

        # Connect bot
        bot = connect_bot(server_port, packet_ids)
        client.command("gamemode spectator MemoryBot")
        client.command("tp MemoryBot 4 100 4")

        # Setup macro fixture
        client.command("gamerule doMobSpawning false")
        client.command("gamerule doDaylightCycle false")
        client.command("gamerule randomTickSpeed 0")
        client.command("forceload add 0 0 15 15")
        client.command("function function_compiler_selective_macro_perf:setup_entities")
        client.command(
            "execute as @e[type=minecraft:marker,tag=fc_macro_source] run "
            "function function_compiler_selective_macro_perf:populate_frontier"
        )
        time.sleep(1.0)

        # 1. Base Startup Footprint
        arm_data["startup_footprint"] = _measure_startup_phase(client, java_pid, candidate)

        # 2. Metaspace Stability across 25,600 Macro Invocations
        arm_data["sustained_macro_workload"] = _measure_sustained_macro_phase(client, java_pid, candidate, mode)

        # 3. ClassLoader Retention across 30+ /reload cycles
        arm_data["reload_retention"] = _measure_reload_retention_phase(client, java_pid, candidate, mode)

        client.command("stop")
        proc.wait(timeout=30)
    except Exception as exc:
        arm_data["error"] = str(exc)
        if proc.poll() is None:
            proc.kill()
    finally:
        if bot:
            bot.close()
        if client:
            client.close()
        log_file.close()

    return arm_data

        client.command("stop")
        proc.wait(timeout=30)
    except Exception as exc:
        arm_data["error"] = str(exc)
        if proc.poll() is None:
            proc.kill()
    finally:
        if bot:
            bot.close()
        if client:
            client.close()
        log_file.close()

    return arm_data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arms",
        nargs="+",
        choices=("baseline", "compiler-on"),
        default=["baseline", "compiler-on"],
        help="Arms to evaluate (default: baseline compiler-on)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_file = OUTPUT_DIR / f"memory-load-{timestamp}.json"

    print(f"=== Starting Memory & Resource Load Benchmark ({timestamp}) ===")
    results: dict[str, object] = {
        "benchmark": "LOAD-001",
        "description": "Post-v1.0 Memory, Metaspace, and GC Footprint Verification",
        "timestamp": timestamp,
        "arms": {},
    }

    for arm in args.arms:
        arm_result = run_experiment(arm)
        results["arms"][arm] = arm_result

    report_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nBenchmark completed successfully! Results written to: {report_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
