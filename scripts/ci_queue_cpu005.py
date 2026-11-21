#!/usr/bin/env python3
"""COMPILER-CPU-005: three fresh, diagnostic-only native Vein Miner CPU boots."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from analyze_queue_cpu005 import parse_cpu005, projection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/benchmarks/COMPILER-CPU-005"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
ARMS = ("plain", "empty", "timed")
STATE_FIELDS = (
    "player_mined_source_stat", "work_after", "work_expected",
    "run_state_after", "queue_head_delta", "remaining_ore",
    "source_block_remains", "operation_markers_after", "target_markers_after",
)
APPEND = (
    "tp @s ~ ~ ~",
    "data modify entity @s data.frontier append value {x:0,y:0,z:0}",
    "execute store result entity @s data.frontier[-1].x int 1 run data get entity @s Pos[0]",
    "execute store result entity @s data.frontier[-1].y int 1 run data get entity @s Pos[1]",
    "execute store result entity @s data.frontier[-1].z int 1 run data get entity @s Pos[2]",
)
PREDICATE = (
    "$execute unless block ~ ~ ~ #vm:excluded_blocks if block ~ ~ ~ #$(match) "
    "run function vm:queue/append_here"
)


def verify_original_source() -> dict:
    if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
        raise AssertionError("Missing or wrong publisher archive SHA-256")
    occurrences = {line: [] for line in (*APPEND, PREDICATE)}
    with zipfile.ZipFile(PACK) as archive:
        for path in archive.namelist():
            if not path.startswith("data/") or not path.endswith(".mcfunction"):
                continue
            for line in archive.read(path).decode("utf-8").splitlines():
                key = line.strip()
                if key in occurrences:
                    occurrences[key].append(path)
    append_path = "data/vm/function/queue/append_here.mcfunction"
    macro_path = "data/vm/function/queue/enqueue_match.mcfunction"
    for line in APPEND:
        if occurrences[line] != [append_path]:
            raise AssertionError(f"ExecuteCommand text not unique to pinned append site: {line!r} {occurrences[line]}")
    if occurrences[PREDICATE] != [macro_path]:
        raise AssertionError("Pinned macro predicate command or uniqueness changed")
    return {
        "publisher_sha256": PIN, "macro_unique": True,
        "all_five_append_command_inputs_unique": True,
        "exact_command_inputs": list(APPEND),
    }


def run_arm(mode: str) -> dict:
    previous = set(VEIN.glob("vein-*/results.json"))
    stage = OUT / f"{mode}-premining.json"
    env = dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env["GRADLE_USER_HOME"] = str(ROOT / "build/gradle-cache-cpu005")
    env["FC_CPU005_MODE"] = mode
    env["FC_CPU005_NAMESPACE"] = "vm"
    for key in (
        "FC_CPU004_MODE", "FC_CPU004_NAMESPACE",
        "FC_COMPILER_ACCEPTANCE_AUDIT", "FC_COMPILER_EXEC_CENSUS",
        "FC_COMMAND_CALLBACK_METRICS", "FC_SCORE_ADD_LEGACY_NAMESPACE",
    ):
        env.pop(key, None)
    cmd = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper", "--side", "6",
        "--capture-timeout", "150", "--no-spark", "--capture-server-thread-cpu",
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage),
    ]
    try:
        completed = subprocess.run(
            cmd, cwd=ROOT, env=env, text=True, capture_output=True,
            timeout=750, check=False
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{mode}: native process deadline expired; no event retry")
    (OUT / f"{mode}-runner.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (OUT / f"{mode}-runner.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(
            f"{mode}: native event error {completed.returncode}, "
            f"stderr={completed.stderr[-1700:]!r}")
    new = set(VEIN.glob("vein-*/results.json")) - previous
    if len(new) != 1:
        raise AssertionError(f"{mode}: expected one completed native event, got {len(new)}")
    path = new.pop()
    data = json.loads(path.read_text(encoding="utf-8"))
    cpu = data.get("server_thread_event_cpu")
    if (
        data.get("compiler_mode") != "wrapper"
        or data.get("cpu005_mode") != mode
        or "FC_CPU005 started mode=" + mode not in str(data.get("cpu005_start_status"))
        or "FC_CPU005 ended mode=" + mode not in str(data.get("cpu005_stop_status"))
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
        or data.get("compiler_exec_census_enabled")
        or data.get("compiler_acceptance_audit_enabled")
        or data.get("jfr_cpu_capture_enabled")
        or data.get("command_callback_metrics_enabled")
    ):
        raise AssertionError(f"{mode}: native gameplay, clocks, CPU, or gate invalid")
    original = path.parent / "cpu005.log"
    raw = original.read_text(encoding="utf-8")
    print("FC_CPU005_RAW mode=" + mode + "\n" + raw, flush=True)
    stream = parse_cpu005(original, mode)
    shutil.copy2(original, OUT / f"{mode}-cpu005.log")
    return {
        "mode": mode,
        "native_state": {k: data[k] for k in STATE_FIELDS},
        "publisher_sha256": PIN,
        "clock_streams": stream,
        "cpu": cpu,
        "event_seconds_descriptive": data.get("operation_completion_seconds"),
        "timing_noncausal": True,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "results.json"
    report = {
        "study": "COMPILER-CPU-005", "status": "started",
        "arms": {}, "interpretation": "Diagnostic CPU clocks; no compiler optimization.",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        report["source"] = verify_original_source()
        for mode in ARMS:
            report["arms"][mode] = run_arm(mode)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        states = [json.dumps(r["native_state"], sort_keys=True)
                  for r in report["arms"].values()]
        if len(set(states)) != 1:
            raise AssertionError("Native final state differs between independent JVM boots")
        analysis = projection(
            *(report["arms"][name]["clock_streams"] for name in ARMS),
            cpu_ns=report["arms"]["timed"]["cpu"]["server_thread_cpu_running_ns"],
        )
        report["analysis"] = analysis
        report["status"] = "accepted"
        print("FC_CPU005_SUMMARY " + json.dumps(analysis, sort_keys=True), flush=True)
    except Exception as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
