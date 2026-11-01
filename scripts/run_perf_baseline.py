#!/usr/bin/env python3
"""Capture a warm, mod-free Minecraft 26.3 scoreboard execution profile."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

# Reuse the pinned vanilla artifact, datapack preparation, and RCON protocol
# from the runtime differential harness.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_runtime_probe import (  # noqa: E402
    LEVEL,
    SERVER_JAR_SHA256,
    RconClient,
    locate_official_server_jar,
    prepare_vanilla_files,
    wait_for_rcon,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "build" / "benchmarks" / "PERF-001"
FUNCTION_LINES = 5_000
WARMUP_CALLS = 50
MEASURED_CALLS = 1_000
BENCH_OBJECTIVE = "fc_perf"
BENCH_HOLDER = "#fcperf"
BENCH_FUNCTION = "function_compiler_perf:scoreboard"


def java_version() -> str:
    result = subprocess.run(
        ["java", "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    return result.stdout.strip()


def prepare_fixture(server_dir: Path) -> tuple[Path, str]:
    prepare_vanilla_files(server_dir)
    datapack_root = server_dir / "probe-world" / "datapacks" / "function_compiler_probe"
    function_path = datapack_root / "data" / "function_compiler_perf" / "function" / "scoreboard.mcfunction"
    function_path.parent.mkdir(parents=True, exist_ok=True)
    function_path.write_text(
        "".join(
            f"scoreboard players add {BENCH_HOLDER} {BENCH_OBJECTIVE} 1\n"
            for _ in range(FUNCTION_LINES)
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(function_path.read_bytes()).hexdigest()
    return function_path, digest


def main() -> int:
    server_jar = locate_official_server_jar()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    jfr_path = (REPORT_DIR / "vanilla-scoreboard.jfr").resolve()
    jfr_path.unlink(missing_ok=True)
    log_path = REPORT_DIR / "vanilla-scoreboard.server.log"
    expected_score = FUNCTION_LINES * (WARMUP_CALLS + MEASURED_CALLS)

    with tempfile.TemporaryDirectory(prefix="function-compiler-perf-001-") as temp:
        server_dir = Path(temp)
        _, fixture_hash = prepare_fixture(server_dir)
        log_handle = log_path.open("wb")
        process = subprocess.Popen(
            [
                "java",
                "-Xms512M",
                "-Xmx2G",
                "-jar",
                str(server_jar),
                "nogui",
            ],
            cwd=server_dir,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        client: RconClient | None = None
        measurements_ns: list[int] = []
        recording_started = False
        score_response = ""
        verified_score = None
        try:
            client = wait_for_rcon(process)
            enabled = client.command("datapack list enabled")
            if "function_compiler_probe" not in enabled:
                available = client.command("datapack list available")
                if "function_compiler_probe" not in available:
                    raise RuntimeError(
                        f"Probe fixture datapack is not available: {available!r}"
                    )
                enable_response = client.command(
                    "datapack enable file/function_compiler_probe"
                )
                if "Unknown" in enable_response or "Could not" in enable_response:
                    raise RuntimeError(
                        f"Could not enable probe fixture datapack: {enable_response!r}"
                    )
                client.command("reload")
                time.sleep(2)
                enabled = client.command("datapack list enabled")
                if "function_compiler_probe" not in enabled:
                    raise RuntimeError(
                        f"Probe fixture datapack did not enable: {enabled!r}"
                    )

            objective = client.command(f"scoreboard objectives add {BENCH_OBJECTIVE} dummy")
            if "Unknown" in objective or "Incorrect" in objective:
                raise RuntimeError(f"Could not create benchmark objective: {objective!r}")
            quota = client.command(f"gamerule {LEVEL} 65536")
            if "65536" not in quota:
                raise RuntimeError(f"Could not set benchmark quota: {quota!r}")
            client.command(f"scoreboard players set {BENCH_HOLDER} {BENCH_OBJECTIVE} 0")

            for _ in range(WARMUP_CALLS):
                response = client.command(f"function {BENCH_FUNCTION}")
                if not response.startswith("Running function "):
                    raise RuntimeError(f"Warmup function did not run: {response!r}")

            recording = subprocess.run(
                [
                    "jcmd",
                    str(process.pid),
                    "JFR.start",
                    "name=PERF001",
                    "settings=profile",
                    f"filename={jfr_path}",
                    "dumponexit=true",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if recording.returncode != 0 or "Started recording" not in recording.stdout:
                raise RuntimeError(f"Could not start JFR recording: {recording.stdout!r}")
            recording_started = True

            for _ in range(MEASURED_CALLS):
                started = time.perf_counter_ns()
                response = client.command(f"function {BENCH_FUNCTION}")
                measurements_ns.append(time.perf_counter_ns() - started)
                if not response.startswith("Running function "):
                    raise RuntimeError(f"Measured function did not run: {response!r}")

            stopped = subprocess.run(
                ["jcmd", str(process.pid), "JFR.stop", "name=PERF001"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if stopped.returncode != 0 or "Stopped recording" not in stopped.stdout:
                raise RuntimeError(f"Could not stop JFR recording: {stopped.stdout!r}")
            recording_started = False

            score_response = client.command(
                f"scoreboard players get {BENCH_HOLDER} {BENCH_OBJECTIVE}"
            )
            score_match = re.search(r"has (-?\d+)", score_response)
            if score_match is None or int(score_match.group(1)) != expected_score:
                raise RuntimeError(
                    f"Unexpected benchmark score {score_response!r}; expected {expected_score}"
                )
            verified_score = int(score_match.group(1))
            client.command("stop")
            process.wait(timeout=45)
        finally:
            if recording_started and process.poll() is None:
                subprocess.run(
                    ["jcmd", str(process.pid), "JFR.stop", "name=PERF001"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
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

    ordered = sorted(measurements_ns)
    report = {
        "benchmark": "PERF-001",
        "purpose": "warm vanilla CPU profile; not an optimization comparison",
        "minecraft": "26.3 official server",
        "server_jar_sha256": SERVER_JAR_SHA256,
        "java_version": java_version(),
        "host": platform.platform(),
        "cpu_count": os.cpu_count(),
        "jvm_args": ["-Xms512M", "-Xmx2G"],
        "jfr_settings": "profile",
        "jfr_started_after_warmup": True,
        "fixture": BENCH_FUNCTION,
        "fixture_lines": FUNCTION_LINES,
        "fixture_sha256": fixture_hash,
        "quota": 65536,
        "warmup_calls": WARMUP_CALLS,
        "measured_calls": MEASURED_CALLS,
        "expected_total_score": expected_score,
        "verified_total_score": verified_score,
        "score_response": score_response,
        "rcon_round_trip_ns_per_call": measurements_ns,
        "rcon_round_trip_median_ns": ordered[len(ordered) // 2],
        "rcon_round_trip_p95_ns": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "rcon_round_trip_p99_ns": ordered[math.ceil(len(ordered) * 0.99) - 1],
        "rcon_round_trip_is_not_execution_only": True,
        "jfr_path": str(jfr_path.relative_to(ROOT)),
        "server_log_path": str(log_path.relative_to(ROOT)),
    }
    result_path = REPORT_DIR / "results.json"
    result_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    console_report = {
        key: value
        for key, value in report.items()
        if key != "rcon_round_trip_ns_per_call"
    }
    console_report["rcon_round_trip_samples_saved"] = len(measurements_ns)
    print(json.dumps(console_report, indent=2))
    print(f"PERF-001 JFR profile: {jfr_path}")
    print(f"PERF-001 run metadata: {result_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Performance baseline failed: {error}", file=sys.stderr)
        raise
