#!/usr/bin/env python3
"""COMPILER-MACRO-006: bounded independent JVM CPU-clock attribution (no optimizer).

Three fresh Fabric/Minecraft 26.3 Java 25 native Vein Miner boots.
All use the shipped selective-macro fast path with all other lowering OFF; the only
between-arm change is sparse clock recording of vm:queue/load_next.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from analyze_macro_load_cpu006 import parse_macro006, interpret

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/benchmarks/COMPILER-MACRO-006"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
ARMS = ("plain", "empty", "timed")
STATE_FIELDS = (
    "player_mined_source_stat", "work_after", "work_expected",
    "run_state_after", "queue_head_delta", "remaining_ore",
    "source_block_remains", "operation_markers_after", "target_markers_after",
)
NAME = "data/vm/function/queue/load_next.mcfunction"


def verify_source() -> dict:
    if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
        raise AssertionError("Missing or wrong original Vein Miner ZIP SHA-256")
    with zipfile.ZipFile(PACK) as archive:
        if NAME not in archive.namelist():
            raise AssertionError("Pinned queue/load_next macro source absent")
        source = archive.read(NAME).decode("utf-8")
        lines = [line.strip() for line in source.splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) != 2:
        raise AssertionError(f"Expected exactly two load_next macro lines, got {len(lines)}")
    copies = [line for line in lines
              if line.startswith("$data modify entity @s data.cursor set from entity @s data.frontier[$(")]
    returns = [line for line in lines
               if line.startswith("$execute unless data entity @s data.frontier[$(")
               and line.endswith(" run return run function vm:operation/complete")]
    if len(copies) != 1 or len(returns) != 1:
        raise AssertionError(f"Expected one indexed NBT copy and one indexed return guard: {lines}")
    variables = [re.findall(r"\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)", line)
                 for line in (copies[0], returns[0])]
    if len(variables[0]) != 1 or variables[0] != variables[1]:
        raise AssertionError(f"Macro indices must use the same one parameter: {variables}")
    result = {
        "publisher_sha256": PIN, "function_source": NAME,
        "macro_parameter": variables[0][0], "source_lines": lines,
        "only_two_indexed_nbt_commands": True,
    }
    print("MACRO006_SOURCE " + json.dumps(result, sort_keys=True), flush=True)
    return result


def run_arm(mode: str) -> dict:
    prev = set(VEIN.glob("vein-*/results.json"))
    readiness = OUT / f"{mode}-startup-stage.json"
    env = dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env["GRADLE_USER_HOME"] = str(ROOT / "build/gradle-cache-macro006")
    env["FC_MACRO006_MODE"] = mode
    env["FC_MACRO006_NAMESPACE"] = "vm"
    for key in (
        "FC_CPU004_MODE", "FC_CPU004_NAMESPACE",
        "FC_CPU005_MODE", "FC_CPU005_NAMESPACE",
        "FC_COMPILER_EXEC_CENSUS", "FC_COMPILER_ACCEPTANCE_AUDIT",
        "FC_COMMAND_CALLBACK_METRICS", "FC_SCORE_ADD_LEGACY_NAMESPACE",
    ):
        env.pop(key, None)
    command = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "selective-macro",
        "--side", "6", "--capture-timeout", "150",
        "--no-spark", "--capture-server-thread-cpu",
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(readiness),
    ]
    try:
        process = subprocess.run(
            command, cwd=ROOT, env=env, text=True, capture_output=True,
            timeout=750, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{mode}: native Minecraft process timed out; no retry after mining")
    (OUT / f"{mode}-stdout.log").write_text(process.stdout, encoding="utf-8")
    (OUT / f"{mode}-stderr.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(
            f"{mode}: native Minecraft event failed exit={process.returncode}, "
            f"stderr_tail={process.stderr[-2000:]!r}")
    new = set(VEIN.glob("vein-*/results.json")) - prev
    if len(new) != 1:
        raise AssertionError(f"Expected one complete native run, got {len(new)}")
    native_path = new.pop()
    native = json.loads(native_path.read_text(encoding="utf-8"))
    cpu = native.get("server_thread_event_cpu")
    if (
        native.get("compiler_mode") != "selective-macro"
        or native.get("macro006_mode") != mode
        or "FC_MACRO006 started mode=" + mode not in str(native.get("macro006_start_status"))
        or "FC_MACRO006 ended mode=" + mode not in str(native.get("macro006_stop_status"))
        or native.get("datapack_sha256") != PIN
        or not native.get("valid_native_workload")
        or native.get("work_after") != 215
        or native.get("queue_head_delta") != 1952
        or native.get("run_state_after") != 0
        or native.get("remaining_ore") != 0
        or native.get("source_block_remains") != 0
        or native.get("event_timeout_reached")
        or not native.get("tick_pre_event_stability", {}).get("stable")
        or not isinstance(cpu, dict)
        or not cpu.get("cpu_measurement_valid")
        or not cpu.get("host_quality_pass")
        or cpu.get("server_thread_cpu_running_ns", 0) <= 0
        or native.get("compiler_exec_census_enabled")
        or native.get("compiler_acceptance_audit_enabled")
        or native.get("jfr_cpu_capture_enabled")
        or native.get("command_callback_metrics_enabled")
    ):
        raise AssertionError(f"{mode}: workload, source, event window, or CPU quality invalid")
    source_log = native_path.parent / "macro006.log"
    if not source_log.is_file():
        raise AssertionError("No event-window macro CPU dump archived")
    census = parse_macro006(source_log, mode)
    shutil.copy2(source_log, OUT / f"{mode}-macro006.log")
    print("MACRO006_ARM " + json.dumps({
        "mode": mode,
        "streams": census["rows"],
        "cache_hits": census["cache_hits"],
        "server_thread_cpu_running_ns": cpu["server_thread_cpu_running_ns"],
        "native_game_state_valid": True,
    }, sort_keys=True), flush=True)
    return {
        "mode": mode, "source_sha256": PIN,
        "state": {key: native[key] for key in STATE_FIELDS},
        "cpu": cpu, "streams": census,
        "event_seconds_descriptive": native.get("operation_completion_seconds"),
        "diagnostic_only": True,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "results.json"
    report = {
        "study": "COMPILER-MACRO-006", "status": "started",
        "publisher_sha256": PIN, "arms": {},
        "noncausal": True,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        report["source"] = verify_source()
        for mode in ARMS:
            report["arms"][mode] = run_arm(mode)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if len({json.dumps(a["state"], sort_keys=True) for a in report["arms"].values()}) != 1:
            raise AssertionError("Native final game state parity failed")
        report["analysis"] = interpret(
            *(report["arms"][m]["streams"] for m in ARMS),
            cpu_ns=report["arms"]["timed"]["cpu"]["server_thread_cpu_running_ns"],
        )
        report["status"] = "accepted"
        print("MACRO006_SUMMARY " + json.dumps(report["analysis"], sort_keys=True), flush=True)
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
