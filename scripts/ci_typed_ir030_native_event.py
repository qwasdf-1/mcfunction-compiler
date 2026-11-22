#!/usr/bin/env python3
"""IR-030 Gate C3: verify exact original publisher gameplay with candidate enabled.

One fresh Minecraft 26.3 Java25 Fabric/wrapper event with the unchanged SHA-
pinned Vein Miner archive. A strictly allowlisted native-vs-direct Pos verifier
runs in the inner callback, while the outer execute store stays native. This is
a diagnostic correctness event, NEVER a CPU-speedup measurement.
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-030-ORIGINAL-EVENT"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
EXPECTED_PER_AXIS = 1940
EXPECTED_TOTAL = 3 * EXPECTED_PER_AXIS

sys.path.insert(0, str(ROOT / "scripts"))
from ci_typed_ir015_fetch import fetch  # noqa: E402
from ci_typed_ir030_source import PIN, inspect as inspect_original_source  # noqa: E402


def status_int(status: str, key: str) -> int:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)(?:\s|$)", status)
    if match is None:
        raise ValueError(f"Missing status counter: {key}")
    return int(match.group(1))


def status_flag(status: str, key: str) -> bool:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(true|false)(?:\s|$)", status)
    if match is None:
        raise ValueError(f"Missing status gate: {key}")
    return match.group(1) == "true"


def verify_event(event: dict) -> dict:
    if event.get("datapack_sha256") != PIN:
        raise AssertionError("Original publisher SHA drift")
    if event.get("compiler_mode") != "wrapper" or event.get("stack") != "fabric":
        raise AssertionError("Required standalone Fabric wrapper mode absent")
    if (
        not event.get("valid_native_workload")
        or event.get("work_after") != 215
        or event.get("queue_head_delta") != 1952
        or event.get("run_state_after") != 0
        or event.get("remaining_ore") != 0
        or event.get("source_block_remains") != 0
        or event.get("operation_markers_after") != 0
        or event.get("target_markers_after") != 0
        or event.get("event_timeout_reached")
    ):
        raise AssertionError("Original gameplay completion/parity gates failed")
    if not event.get("tick_pre_event_stability", {}).get("stable"):
        raise AssertionError("Pre-event host stability failed")
    cpu = event.get("server_thread_event_cpu") or {}
    if not cpu.get("host_quality_pass") or not cpu.get("cpu_measurement_valid"):
        raise AssertionError("Invalid Server-thread host-quality clock")
    if (
        event.get("command_callback_metrics_enabled")
        or event.get("compiler_exec_census_enabled")
        or event.get("compiler_acceptance_audit_enabled")
        or event.get("cpu005_mode") is not None
        or event.get("jfr_cpu_capture_enabled")
        or event.get("jfr_execution_capture_enabled")
        or event.get("spark_capture_enabled")
    ):
        raise AssertionError("Unexpected simultaneous profiling instrumentation")

    before = event.get("compiler_status_before")
    after = event.get("compiler_status_after")
    if not before or not after:
        raise AssertionError("Required before/after compiler status unavailable")
    for status in (before, after):
        if not status_flag(status, "ir030_pos_get_enabled"):
            raise AssertionError("Candidate disabled inside original-event JVM")
        if not status_flag(status, "ir030_pos_get_verify"):
            raise AssertionError("Native differential verification disabled")
        if (
            status_flag(status, "score_add_prototype_enabled")
            or status_flag(status, "score_add_metrics_enabled")
            or status_flag(status, "score_add_timing_enabled")
            or status_flag(status, "fused_region_prototype_enabled")
            or status_flag(status, "bytecode_region_prototype_enabled")
        ):
            raise AssertionError("Another research optimizer/metric enabled")

    compiled = {
        axis: status_int(after, f"ir030_pos_compiled_{axis}")
        for axis in "xyz"
    }
    fast = {
        axis: status_int(after, f"ir030_pos_fast_{axis}")
              - status_int(before, f"ir030_pos_fast_{axis}")
        for axis in "xyz"
    }
    verified = status_int(after, "ir030_pos_verified") - status_int(
        before, "ir030_pos_verified")
    mismatches = status_int(after, "ir030_pos_verify_mismatches") - status_int(
        before, "ir030_pos_verify_mismatches")
    fallback = {
        category: status_int(after, f"ir030_pos_fallback_{category}") - status_int(
            before, f"ir030_pos_fallback_{category}")
        for category in ("vehicle", "entity_type", "nonfinite")
    }
    invalid = status_int(after, "ir030_pos_invalid_targets") - status_int(
        before, "ir030_pos_invalid_targets")
    if compiled != dict.fromkeys("xyz", 1):
        raise AssertionError(f"Expected exactly three admitted terminals: {compiled!r}")
    if fast != dict.fromkeys("xyz", EXPECTED_PER_AXIS):
        raise AssertionError(f"Authentic Pos site coverage drift: {fast!r}")
    if verified != EXPECTED_TOTAL or mismatches != 0:
        raise AssertionError(
            f"Native/candidate original-event read mismatch: "
            f"verified={verified}, expected={EXPECTED_TOTAL}, mismatches={mismatches}")
    if any(fallback.values()) or invalid:
        raise AssertionError(
            f"Original event left exact Marker fast path: fallback={fallback!r} invalid={invalid}")
    return {
        "status": "accepted_original_publisher_candidate_native_verification",
        "exact_accepted_terminals": compiled,
        "exact_fast_calls": fast,
        "native_snapshot_verifications": verified,
        "snapshot_result_feedback_mismatches": mismatches,
        "fallbacks": fallback,
        "invalid_targets": invalid,
        "work_units": event["work_after"],
        "queue_steps": event["queue_head_delta"],
        "all_original_world_conservation_gates": True,
        "host_quality_pass": cpu["host_quality_pass"],
        "server_thread_cpu_ns_descriptive_only": cpu["server_thread_cpu_running_ns"],
        "speedup_measured": False,
    }


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "milestone": "COMPILER-IR-030-GATE-C3",
        "status": "started",
        "publisher_sha256": PIN,
        "runtime_optimizer_default_enabled": False,
        "diagnostic_native_snapshot_on_every_candidate_read": True,
        "cpu_speedup_measured": False,
    }
    try:
        if not PACK.is_file():
            fetch("veinminer")
        if hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
            raise AssertionError("Pinned Vein Miner original ZIP hash mismatch")
        source = inspect_original_source()
        if source["status"] != "verified_exact_original_source_only":
            raise AssertionError("Original publisher source order not verified")
        report["publisher_source_sites"] = source["commands"]
        previous = set(VEIN.glob("vein-*/results.json"))
        env = dict(os.environ)
        env.update({
            "GRADLE_USER_HOME": str(ROOT / "build/gradle-cache-ir030-original"),
            "GRADLE_RO_DEP_CACHE": str(Path.home() / ".gradle" / "caches"),
            "FC_IR030_POS_GET": "true",
            "FC_IR030_POS_GET_VERIFY": "true",
            "FC_IR030_POS_GET_FUNCTIONS": "vm:queue/append_here",
            "FC_SCORE_ADD_PROTOTYPE": "false",
            "FC_SCORE_ADD_METRICS": "false",
            "FC_SCORE_ADD_TIMING": "false",
            "FC_FUSED_REGION_PROTOTYPE": "false",
            "FC_BYTECODE_REGION_PROTOTYPE": "false",
            "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
            "FC_COMMAND_CALLBACK_METRICS": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
            "FC_RUNTIME_TRACE": "false",
            "FC_CPU005_MODE": "",
            "FC_CPU004_MODE": "",
            "FC_MACRO006_MODE": "",
        })
        for key in (
            "FC_COMPILER_EXEC_CENSUS", "FC_COMPILER_ACCEPTANCE_NAMESPACE",
            "FC_TYPED_IR_MODE", "FC_TYPED_IR_NAMESPACE",
            "FC_TYPED_IR_FUNCTION_FILTER",
        ):
            env.pop(key, None)
        start = OUT / "readiness.json"
        command = [
            sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
            "--stack", "fabric", "--compiler-mode", "wrapper", "--side", "6",
            "--capture-timeout", "150", "--no-spark", "--capture-server-thread-cpu",
            "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
            "--setup-rcon-timeout-seconds", "45",
            "--startup-readiness-record", str(start),
        ]
        try:
            completed = subprocess.run(
                command, cwd=ROOT, env=env, text=True,
                capture_output=True, timeout=900, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Native event timed out; no unattended retry") from exc
        (OUT / "runner.stdout.log").write_text(
            completed.stdout, encoding="utf-8")
        (OUT / "runner.stderr.log").write_text(
            completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(
                f"Original event runner failed ({completed.returncode}): "
                f"{completed.stderr[-1500:]}")
        new = set(VEIN.glob("vein-*/results.json")) - previous
        if len(new) != 1:
            raise AssertionError(
                f"Exactly one new original event manifest expected; found {len(new)}")
        event_path = new.pop()
        event = json.loads(event_path.read_text(encoding="utf-8"))
        shutil.copy2(event_path, OUT / "native-event.json")
        report["verification"] = verify_event(event)
        report["status"] = report["verification"]["status"]
        print("IR030_ORIGINAL_EVENT_ACCEPTED " + json.dumps(
            report["verification"], sort_keys=True), flush=True)
    except Exception as exc:
        report["status"] = "invalid"
        report["error"] = repr(exc)
        raise
    finally:
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
