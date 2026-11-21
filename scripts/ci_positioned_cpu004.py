#!/usr/bin/env python3
"""COMPILER-CPU-004: three fresh native diagnostic boots, no compiler/JFR/Spark."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from analyze_positioned_cpu004 import parse_cpu004, diagnostic_projection

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
OUT = ROOT / "build/benchmarks/COMPILER-CPU-004"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
ARMS = ("plain", "empty", "timed")
STATE_FIELDS = (
    "player_mined_source_stat", "work_after", "work_expected",
    "run_state_after", "queue_head_delta", "remaining_ore",
    "source_block_remains", "operation_markers_after", "target_markers_after",
)


def run_arm(mode: str) -> dict:
    before = set(VEIN.glob("vein-*/results.json"))
    stage_file = OUT / f"{mode}-premining.json"
    command = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper",
        "--side", "6", "--capture-timeout", "150",
        "--no-spark", "--capture-server-thread-cpu",
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage_file),
    ]
    env = dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE", None)
    # Keep Gradle dependency caches out of the uploaded CPU004 research artifact.
    env["GRADLE_USER_HOME"] = str(ROOT / "build/gradle-cache-cpu004")
    env["FC_CPU004_MODE"] = mode
    env["FC_CPU004_NAMESPACE"] = "vm"
    for key in ("FC_COMPILER_EXEC_CENSUS", "FC_COMPILER_ACCEPTANCE_AUDIT",
                "FC_SCORE_ADD_LEGACY_NAMESPACE", "FC_COMMAND_CALLBACK_METRICS"):
        env.pop(key, None)
    try:
        process = subprocess.run(
            command, cwd=ROOT, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=750, check=False
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{mode}: whole native process timed out; no retry")
    (OUT / f"{mode}-runner.log").write_text(process.stdout, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"{mode}: native event failed; see runner log")
    new = set(VEIN.glob("vein-*/results.json")) - before
    if len(new) != 1:
        raise AssertionError(f"{mode}: expected one completed native event, got {len(new)}")
    path = new.pop()
    data = json.loads(path.read_text(encoding="utf-8"))
    cpu = data.get("server_thread_event_cpu")
    if (
        data.get("compiler_mode") != "wrapper"
        or data.get("cpu004_mode") != mode
        or "FC_CPU004 started mode=" + mode not in str(data.get("cpu004_start_status"))
        or "FC_CPU004 ended mode=" + mode not in str(data.get("cpu004_stop_status"))
        or data.get("datapack_sha256") != PIN
        or not data.get("valid_native_workload")
        or data.get("queue_head_delta") != 1952
        or data.get("work_after") != 215
        or data.get("run_state_after") != 0
        or data.get("event_timeout_reached")
        or not data.get("tick_pre_event_stability", {}).get("stable")
        or not isinstance(cpu, dict)
        or not cpu.get("cpu_measurement_valid")
        or not cpu.get("host_quality_pass")
        or cpu.get("server_thread_cpu_running_ns", 0) <= 0
    ):
        raise AssertionError(f"{mode}: failed native CPU / workload / source / gate checks")
    if any(data.get(key) is not None and data.get(key) is True
           for key in ("compiler_exec_census_enabled", "compiler_acceptance_audit_enabled",
                       "command_callback_metrics_enabled", "jfr_cpu_capture_enabled")):
        raise AssertionError("Unexpected additional diagnostic mode")
    raw_log = (path.parent / "cpu004.log").read_text(encoding="utf-8")
    print("FC_CPU004_RAW mode=" + mode + "\n" + raw_log, flush=True)
    census = parse_cpu004(path.parent / "cpu004.log", mode)
    shutil.copy2(path.parent / "cpu004.log", OUT / f"{mode}-cpu004.log")
    record = {
        "mode": mode,
        "native_state": {k: data[k] for k in STATE_FIELDS},
        "compiler_mode": data["compiler_mode"],
        "cpu": cpu,
        "clock_census": census,
        "publisher_pin": data["datapack_sha256"],
        "event_seconds_descriptive": data.get("operation_completion_seconds"),
        "host_quality": True,
        "timing_is_diagnostic": True,
    }
    print("FC_CPU004_ARM " + json.dumps({
        "mode": mode,
        "state_valid": True,
        "clock_rows": census["rows"],
        "server_cpu_ns": cpu["server_thread_cpu_running_ns"],
    }, sort_keys=True), flush=True)
    return record


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "study": "COMPILER-CPU-004", "status": "started",
        "publisher_pin": PIN, "arms": {},
        "interpretation": "Descriptive CPU method clock screen, not a causal speedup.",
    }
    target = OUT / "results.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        import hashlib
        if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
            raise AssertionError("Missing/wrong SHA-pinned original publisher datapack")
        for mode in ARMS:
            report["arms"][mode] = run_arm(mode)
            target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        values = list(report["arms"].values())
        if len({json.dumps(x["native_state"], sort_keys=True) for x in values}) != 1:
            raise AssertionError("The three events ended in different Minecraft native states")
        analysis = diagnostic_projection(
            *(report["arms"][mode]["clock_census"] for mode in ARMS),
            timed_server_cpu_ns=report["arms"]["timed"]["cpu"]["server_thread_cpu_running_ns"]
        )
        report["analysis"] = analysis
        report["status"] = "accepted"
        print("FC_CPU004_SUMMARY " + json.dumps(analysis, sort_keys=True), flush=True)
    except Exception as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
