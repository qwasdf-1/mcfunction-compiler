#!/usr/bin/env python3
"""Execute extreme environment stress testing with constrained memory (-Xmx512M)

and 5 simultaneous large real-world datapacks.
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
import time

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_DIR = ROOT / "references/real-world/candidates"
OUTPUT_DIR = ROOT / "build/benchmarks/extreme-stress-test"
RUN_BASE = ROOT / "run/extreme-stress-test"

FIVE_DATAPACKS = [
    "blazeandcaves-advancements-1.21.1-26.3.zip",
    "VeinMiner-5.3.0+26.3.zip",
    "datapack-function-library-v5.1.0-26.1-26.3.zip",
    "dynamic-torches-5.4-26.3.zip",
    "hostile-mobs-improve-over-time-2.3-26.3.zip",
]

RCON_HOST = "127.0.0.1"
RCON_PASSWORD = "fc_stress_password"


class RconClient:
    def __init__(self, host: str, port: int, password: str) -> None:
        self.socket = socket.create_connection((host, port), timeout=5)
        self.socket.settimeout(15)
        self.request_id = 0
        response_id, response_type, _ = self._request(3, password)
        if response_id == -1 or response_type != 2:
            raise RuntimeError("RCON authentication failed")

    def close(self) -> None:
        try:
            self.socket.close()
        except OSError:
            pass

    def command(self, cmd: str) -> str:
        response_id, response_type, response = self._request(2, cmd)
        if response_id != self.request_id or response_type != 0:
            raise RuntimeError(
                f"Unexpected RCON command response id={response_id} type={response_type}"
            )
        return response

    def _request(self, packet_type: int, body: str) -> tuple[int, int, str]:
        self.request_id += 1
        packet_id = self.request_id
        encoded = body.encode("utf-8") + b"\0\0"
        payload = struct.pack("<ii", packet_id, packet_type) + encoded
        self.socket.sendall(struct.pack("<i", len(payload)) + payload)

        packet_length = struct.unpack("<i", self._read_exact(4))[0]
        packet = self._read_exact(packet_length)
        response_id, response_type = struct.unpack("<ii", packet[:8])
        response_body = packet[8:-2].decode("utf-8", errors="replace")
        return response_id, response_type, response_body

    def _read_exact(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self.socket.recv(length - len(chunks))
            if not chunk:
                raise ConnectionError("RCON closed before sending full packet")
            chunks.extend(chunk)
        return bytes(chunks)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind((RCON_HOST, 0))
        return int(sock.getsockname()[1])


def wait_for_rcon(
    process: subprocess.Popen[bytes], port: int, timeout: int = 180
) -> RconClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited early with code {process.returncode}")
        try:
            return RconClient(RCON_HOST, port, RCON_PASSWORD)
        except (OSError, ConnectionError, RuntimeError) as err:
            last_error = err
            time.sleep(1.0)
    raise TimeoutError(f"RCON did not become available on port {port}: {last_error}")


def parse_tick_query(response: str) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {
        "tick_average_ms": None,
        "tick_p50_ms": None,
        "tick_p95_ms": None,
        "tick_p99_ms": None,
    }
    avg = re.search(r"Average time per tick: ([0-9.]+)ms", response)
    p50 = re.search(r"P50: ([0-9.]+)ms", response)
    p95 = re.search(r"P95: ([0-9.]+)ms", response)
    p99 = re.search(r"P99: ([0-9.]+)ms", response)
    if avg:
        metrics["tick_average_ms"] = float(avg.group(1))
    if p50:
        metrics["tick_p50_ms"] = float(p50.group(1))
    if p95:
        metrics["tick_p95_ms"] = float(p95.group(1))
    if p99:
        metrics["tick_p99_ms"] = float(p99.group(1))
    return metrics


def get_process_memory_mb(pid: int) -> float:
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return float(parts[1]) / 1024.0
    except (OSError, IndexError, ValueError):
        pass
    return 0.0


def setup_stress_directory(
    work_dir: Path, rcon_port: int, server_port: int
) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    datapacks_dir = work_dir / "world/datapacks"
    datapacks_dir.mkdir(parents=True, exist_ok=True)
    for pack_name in FIVE_DATAPACKS:
        src = CANDIDATES_DIR / pack_name
        if src.exists():
            shutil.copy2(src, datapacks_dir / pack_name)
        else:
            raise FileNotFoundError(f"Missing required test datapack: {src}")

    (work_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    props = (
        f"enable-rcon=true\n"
        f"rcon.password={RCON_PASSWORD}\n"
        f"rcon.port={rcon_port}\n"
        f"server-port={server_port}\n"
        f"online-mode=false\n"
        f"white-list=false\n"
        f"max-tick-time=120000\n"
        f"difficulty=normal\n"
        f"spawn-protection=0\n"
        f"sync-chunk-writes=false\n"
    )
    (work_dir / "server.properties").write_text(props, encoding="utf-8")


def run_stress_arm(
    mode: str, jvm_mem: str = "-Xms256M,-Xmx512M"
) -> dict[str, object]:
    rcon_port = free_port()
    server_port = free_port()
    work_dir = RUN_BASE / mode
    setup_stress_directory(work_dir, rcon_port, server_port)

    env = os.environ.copy()
    if mode == "fabric-off":
        env["FC_WRAPPER_PROBE"] = "false"
        env["FC_FUSED_REGION_PROTOTYPE"] = "false"
        env["FC_SELECTIVE_MACRO_ARGUMENTS"] = "false"
        env["FC_BYTECODE_REGION_PROTOTYPE"] = "false"
    else:
        env["FC_WRAPPER_PROBE"] = "true"
        env["FC_FUSED_REGION_PROTOTYPE"] = "true"
        env["FC_SELECTIVE_MACRO_ARGUMENTS"] = "true"
        env["FC_BYTECODE_REGION_PROTOTYPE"] = "false"

    gradle_cmd = [
        str(ROOT / "gradlew"),
        "--no-daemon",
        "--offline",
        f"-PfcRunDirectory={work_dir.relative_to(ROOT).as_posix()}",
        f"-PfcJvmArgs={jvm_mem}",
        "runServer",
    ]

    log_path = work_dir / "stress-server.log"
    log_file = open(log_path, "w", encoding="utf-8")
    start_time = time.monotonic()

    proc = subprocess.Popen(
        gradle_cmd,
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    arm_result: dict[str, object] = {
        "mode": mode,
        "jvm_memory_args": jvm_mem,
        "server_booted": False,
        "datapacks_enabled_count": 0,
        "reload_latencies_seconds": [],
        "tick_metrics": {},
        "peak_rss_mb": 0.0,
        "oom_observed": False,
    }

    client = None
    try:
        client = wait_for_rcon(proc, rcon_port, timeout=180)
        boot_duration = round(time.monotonic() - start_time, 2)
        arm_result["server_booted"] = True
        arm_result["boot_duration_seconds"] = boot_duration

        # Query enabled datapacks
        dp_list = client.command("datapack list")
        matches = re.findall(r"file/([a-zA-Z0-9_\-\.\+]+)", dp_list)
        arm_result["datapacks_enabled_count"] = len(matches)
        arm_result["datapacks_enabled"] = matches

        # Allow ticks to stabilize
        time.sleep(3.0)

        # Execute 3 consecutive /reload cycles
        reload_latencies = []
        for i in range(3):
            r_start = time.monotonic()
            resp = client.command("reload")
            r_dur = round(time.monotonic() - r_start, 3)
            reload_latencies.append(r_dur)
            time.sleep(1.0)
        arm_result["reload_latencies_seconds"] = reload_latencies

        # Query tick performance
        tick_resp = client.command("tick query")
        arm_result["tick_metrics"] = parse_tick_query(tick_resp)

        # Inspect memory via /functioncompiler status if enabled
        if mode != "fabric-off":
            status_resp = client.command("functioncompiler status")
            arm_result["compiler_status"] = status_resp
            metrics_resp = client.command("functioncompiler metrics")
            arm_result["compiler_metrics"] = metrics_resp

        # Peak RSS
        arm_result["peak_rss_mb"] = round(get_process_memory_mb(proc.pid), 2)

        client.command("stop")
        proc.wait(timeout=30)
    except Exception as exc:
        arm_result["error"] = str(exc)
        if proc.poll() is None:
            proc.kill()
    finally:
        if client:
            client.close()
        log_file.close()

    # Check for OOM in log
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="ignore")
        if "OutOfMemoryError" in log_text or "java.lang.OutOfMemoryError" in log_text:
            arm_result["oom_observed"] = True

    return arm_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jvm-mem",
        default="-Xms256M,-Xmx512M",
        help="JVM heap arguments (default: -Xms256M,-Xmx512M)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_file = OUTPUT_DIR / f"stress-test-{timestamp}.json"

    print(f"=== Starting Extreme Stress Test Campaign ({timestamp}) ===")
    print(f"Config: 5 Large Datapacks, Memory Constraint: {args.jvm_mem}")

    results = {
        "benchmark": "EXTREME-STRESS-TEST",
        "timestamp": timestamp,
        "jvm_memory": args.jvm_mem,
        "datapacks": FIVE_DATAPACKS,
        "arms": {},
    }

    for mode in ["fabric-off", "fabric-on"]:
        print(f"-> Running Arm: {mode} ...")
        arm_res = run_stress_arm(mode, jvm_mem=args.jvm_mem)
        results["arms"][mode] = arm_res
        print(
            f"   Booted: {arm_res.get('server_booted')}, "
            f"Datapacks: {arm_res.get('datapacks_enabled_count')}, "
            f"Reloads: {arm_res.get('reload_latencies_seconds')}, "
            f"OOM: {arm_res.get('oom_observed')}"
        )

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Stress test completed. Report written to {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
