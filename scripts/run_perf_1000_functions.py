#!/usr/bin/env python3
"""Benchmark compilation latency and memory stability with 1,000+ generated functions (PERF-008)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_runtime_probe import (
    RconClient,
    locate_official_server_jar,
)

REPORT_DIR = ROOT / "build" / "reports" / "benchmarks" / "PERF-008"
RCON_HOST = "127.0.0.1"
RCON_PASSWORD = "function-compiler-perf-1000"
MODES = (
    "fabric-off",
    "score-add-on",
    "fused-interpreted",
    "bytecode-emitted",
)
TOTAL_FUNCTIONS = 1024
OBJECTIVE = "fc_perf"


def mode_wrapper_enabled(mode: str) -> bool:
    return mode != "fabric-off"


def mode_score_add_enabled(mode: str) -> bool:
    return mode in {"score-add-on", "fused-interpreted", "bytecode-emitted"}


def mode_fused_enabled(mode: str) -> bool:
    return mode == "fused-interpreted"


def mode_bytecode_enabled(mode: str) -> bool:
    return mode == "bytecode-emitted"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind((RCON_HOST, 0))
        return int(sock.getsockname()[1])


def parse_status_values(status: str) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in re.findall(r"([a-z_]+)=(\d+)", status)
    }


def command(client: RconClient, text: str) -> str:
    return client.command(text)


def generate_function_pack(destination: Path) -> dict[str, object]:
    function_dir = destination / "data" / "perf_1000" / "function"
    function_dir.mkdir(parents=True, exist_ok=True)
    (destination / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "PERF-008 1000+ generated functions stress benchmark",
                    "min_format": [97, 1],
                    "max_format": [97, 1],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    expected_regions = 0
    expected_score_adds = 0
    pattern_counts = {0: 0, 1: 0, 2: 0, 3: 0}

    for i in range(TOTAL_FUNCTIONS):
        pattern = i % 4
        pattern_counts[pattern] += 1
        fn_file = function_dir / f"f_{i:04d}.mcfunction"
        lines: list[str] = []

        if pattern == 0:
            # Single contiguous block: 8 ScoreAdds -> 1 compiled region
            for step in range(1, 9):
                lines.append(f"scoreboard players add #var_{i} {OBJECTIVE} {step}\n")
            expected_regions += 1
            expected_score_adds += 8
        elif pattern == 1:
            # Dual block separated by say: 4 ScoreAdds + say + 4 ScoreAdds -> 2 compiled regions
            for step in range(1, 5):
                lines.append(f"scoreboard players add #var_{i} {OBJECTIVE} {step}\n")
            lines.append(f"say step_{i}\n")
            for step in range(5, 9):
                lines.append(f"scoreboard players add #var_{i} {OBJECTIVE} {step}\n")
            expected_regions += 2
            expected_score_adds += 8
        elif pattern == 2:
            # Triple block: 3 ScoreAdds + say + 3 ScoreAdds + say + 3 ScoreAdds -> 3 compiled regions
            for step in range(1, 4):
                lines.append(f"scoreboard players add #var_{i} {OBJECTIVE} {step}\n")
            lines.append(f"say a_{i}\n")
            for step in range(4, 7):
                lines.append(f"scoreboard players add #var_{i} {OBJECTIVE} {step}\n")
            lines.append(f"say b_{i}\n")
            for step in range(7, 10):
                lines.append(f"scoreboard players add #var_{i} {OBJECTIVE} {step}\n")
            expected_regions += 3
            expected_score_adds += 9
        else:
            # Uncompiled / vanilla pass-through: 0 compiled regions
            lines.append(f"say no-op_{i}\n")

        fn_file.write_text("".join(lines), encoding="utf-8")

    return {
        "total_functions": TOTAL_FUNCTIONS,
        "pattern_distribution": pattern_counts,
        "expected_regions": expected_regions,
        "expected_score_adds": expected_score_adds,
    }


def write_server_files(work: Path, rcon_port: int) -> dict[str, object]:
    world = work / "world"
    probe_pack = world / "datapacks" / "function_compiler_probe"
    shutil.copytree(ROOT / "src" / "main" / "resources" / "data", probe_pack / "data")
    (probe_pack / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "Function Compiler base probe",
                    "min_format": [97, 1],
                    "max_format": [97, 1],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    perf_pack = world / "datapacks" / "perf_1000"
    pack_stats = generate_function_pack(perf_pack)

    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    properties = {
        "enable-rcon": "true",
        "rcon.password": RCON_PASSWORD,
        "rcon.port": str(rcon_port),
        "broadcast-rcon-to-ops": "false",
        "server-ip": RCON_HOST,
        "server-port": str(free_port()),
        "level-name": "world",
        "level-seed": "264026",
        "online-mode": "false",
        "white-list": "false",
        "spawn-protection": "0",
        "max-players": "1",
        "view-distance": "4",
        "simulation-distance": "4",
        "sync-chunk-writes": "false",
        "pause-when-empty-seconds": "-1",
    }
    (work / "server.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()),
        encoding="utf-8",
    )
    return pack_stats


def configure_probe_environment(mode: str) -> dict[str, str]:
    env = dict(os.environ)
    for env_var, cache_path in (
        ("GRADLE_USER_HOME", ROOT / ".gradle-user-home"),
        ("GRADLE_RO_DEP_CACHE", Path.home() / ".gradle" / "caches"),
    ):
        if env_var not in env and cache_path.is_dir():
            env[env_var] = str(cache_path)

    env["FC_WRAPPER_PROBE"] = "true" if mode_wrapper_enabled(mode) else "false"
    env["FC_SCORE_ADD_PROTOTYPE"] = "true" if mode_score_add_enabled(mode) else "false"
    env["FC_SCORE_ADD_METRICS"] = "true" if mode_score_add_enabled(mode) else "false"
    env["FC_FUSED_REGION_PROTOTYPE"] = "true" if mode_fused_enabled(mode) else "false"
    env["FC_BYTECODE_REGION_PROTOTYPE"] = "true" if mode_bytecode_enabled(mode) else "false"
    env["FC_RUNTIME_TRACE"] = "false"
    return env


def start_server(mode: str, work: Path, log_path: Path) -> tuple[subprocess.Popen[bytes], object]:
    log_handle = log_path.open("wb")
    env = configure_probe_environment(mode)
    cmd = [str(ROOT / "gradlew"), "--no-daemon"]
    if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
        cmd.append("--offline")
    cmd.extend([f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}", "runServer"])
    process = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def wait_for_rcon_connection(process: subprocess.Popen[bytes], port: int, timeout: int = 240) -> RconClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited early with code {process.returncode}")
        try:
            return RconClient(RCON_HOST, port, RCON_PASSWORD)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(1)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def run_benchmark_for_mode(mode: str, run_id: str, pack_stats: dict[str, object]) -> dict[str, object]:
    work = ROOT / "run" / f"perf-1000-{run_id}-{mode}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rcon_port = free_port()
    write_server_files(work, rcon_port)
    log_path = REPORT_DIR / f"{run_id}-{mode}.server.log"
    process, log_handle = start_server(mode, work, log_path)
    client: RconClient | None = None
    try:
        t0 = time.monotonic()
        client = wait_for_rcon_connection(process, rcon_port)
        startup_duration_seconds = time.monotonic() - t0

        # Initialize objective
        command(client, f"scoreboard objectives add {OBJECTIVE} dummy")

        # Initial probe status
        status_initial_raw = command(client, "function_compiler_probe status")
        status_initial = parse_status_values(status_initial_raw)

        # First reload cycle measurement
        reload_start = time.monotonic()
        reload_response = command(client, "reload")
        reload_duration_ms = (time.monotonic() - reload_start) * 1000.0

        # Post-reload GC collect
        command(client, "function_compiler_probe collect")
        status_after_reload_raw = command(client, "function_compiler_probe status")
        status_after_reload = parse_status_values(status_after_reload_raw)

        # Verification sample execution across patterns (40 functions total)
        sample_indices = [
            0, 1, 2, 3,
            100, 101, 102, 103,
            200, 201, 202, 203,
            300, 301, 302, 303,
            400, 401, 402, 403,
            500, 501, 502, 503,
            600, 601, 602, 603,
            700, 701, 702, 703,
            800, 801, 802, 803,
            900, 901, 902, 903,
        ]
        sample_results: dict[str, int] = {}
        for idx in sample_indices:
            command(client, f"scoreboard players set #var_{idx} {OBJECTIVE} 0")
            command(client, f"function perf_1000:f_{idx:04d}")
            get_resp = command(client, f"scoreboard players get #var_{idx} {OBJECTIVE}")
            match = re.search(r"has (-?\d+)", get_resp)
            score = int(match.group(1)) if match else -999999
            sample_results[f"f_{idx:04d}"] = score

        # Verify sample scores match expected values:
        # pattern 0 -> 1+2+3+4+5+6+7+8 = 36
        # pattern 1 -> 1+2+3+4+5+6+7+8 = 36
        # pattern 2 -> 1+2+3+4+5+6+7+8+9 = 45
        # pattern 3 -> 0
        expected_score_map = {0: 36, 1: 36, 2: 45, 3: 0}
        parity_failures: list[str] = []
        for idx in sample_indices:
            pat = idx % 4
            expected = expected_score_map[pat]
            actual = sample_results[f"f_{idx:04d}"]
            if actual != expected:
                parity_failures.append(f"f_{idx:04d} (pat {pat}): expected {expected}, got {actual}")

        if parity_failures:
            raise RuntimeError(f"Sample parity failure in {mode}: {parity_failures}")

        # Post-execution status
        status_after_exec_raw = command(client, "function_compiler_probe status")
        status_after_exec = parse_status_values(status_after_exec_raw)

        # Second reload cycle to verify class retention stability
        reload2_start = time.monotonic()
        command(client, "reload")
        reload2_duration_ms = (time.monotonic() - reload2_start) * 1000.0
        command(client, "function_compiler_probe collect")
        status_after_reload2 = parse_status_values(command(client, "function_compiler_probe status"))

        command(client, "stop")
        process.wait(timeout=60)

        return {
            "mode": mode,
            "startup_duration_seconds": round(startup_duration_seconds, 2),
            "reload_duration_ms": round(reload_duration_ms, 2),
            "reload2_duration_ms": round(reload2_duration_ms, 2),
            "status_initial": status_initial,
            "status_after_reload": status_after_reload,
            "status_after_reload2": status_after_reload2,
            "status_after_exec": status_after_exec,
            "metaspace_initial_bytes": status_initial.get("metaspace_bytes_used", 0),
            "metaspace_after_reload_bytes": status_after_reload.get("metaspace_bytes_used", 0),
            "metaspace_after_reload2_bytes": status_after_reload2.get("metaspace_bytes_used", 0),
            "metaspace_growth_reload1_bytes": (
                status_after_reload.get("metaspace_bytes_used", 0)
                - status_initial.get("metaspace_bytes_used", 0)
            ),
            "metaspace_growth_reload2_bytes": (
                status_after_reload2.get("metaspace_bytes_used", 0)
                - status_after_reload.get("metaspace_bytes_used", 0)
            ),
            "bytecode_regions_compiled": status_after_reload.get("bytecode_regions_compiled", 0),
            "bytecode_class_bytes_emitted": status_after_reload.get("bytecode_class_bytes_emitted", 0),
            "bytecode_generated_classes_live": status_after_reload.get("bytecode_generated_classes_live", 0),
            "fused_regions_compiled": status_after_reload.get("fused_regions_compiled", 0),
            "score_add_compiled": status_after_reload.get("score_add_compiled", 0),
            "sample_parity_verified": True,
            "sample_verified_count": len(sample_indices),
        }
    finally:
        if client is not None:
            client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_handle.close()
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%dT%H%M%S", time.gmtime())

    # Pre-generate sample pack structure to inspect stats
    temp_pack = REPORT_DIR / "schema_inspect_pack"
    pack_stats = generate_function_pack(temp_pack)
    shutil.rmtree(temp_pack, ignore_errors=True)

    results: list[dict[str, object]] = []
    for mode in args.modes:
        print(f"Running PERF-008 benchmark for mode: {mode} ...", flush=True)
        res = run_benchmark_for_mode(mode, run_id, pack_stats)
        results.append(res)
        print(
            f"  {mode}: startup={res['startup_duration_seconds']}s, "
            f"reload={res['reload_duration_ms']}ms, "
            f"metaspace={res['metaspace_after_reload_bytes'] / (1024*1024):.2f} MiB, "
            f"bytecode_classes={res['bytecode_generated_classes_live']}",
            flush=True,
        )

    report = {
        "benchmark": "PERF-008",
        "description": "Large-scale compilation stress test with 1,000+ generated functions",
        "timestamp": run_id,
        "pack_stats": pack_stats,
        "modes": results,
    }

    report_path = REPORT_DIR / f"{run_id}.results.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport written to: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
