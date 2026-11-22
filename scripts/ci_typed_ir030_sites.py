#!/usr/bin/env python3
"""IR-030 Gate C1: exact native execution counts for the three pinned Pos sites.

One fresh compiler-wrapper (no optimizer) Java25/Minecraft26.3 event. CPU005
plain mode records invocation cardinality only; it reads no CPU clocks. The
three axis counters match the full original command line at BuildContexts
instantiation and the actual native Brigadier leaf callback.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-030-SITES"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"

sys.path.insert(0, str(ROOT / "scripts"))
from analyze_queue_cpu005 import parse_cpu005  # noqa: E402
from analyze_typed_ir030_sites import parse_site_rows  # noqa: E402
from ci_typed_ir030_source import inspect as inspect_original_source  # noqa: E402
from ci_typed_ir015_fetch import fetch  # noqa: E402


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    if not PACK.is_file():
        fetch("veinminer")
    if hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
        raise AssertionError("Pinned original Vein Miner archive SHA mismatch")
    source = inspect_original_source()
    previous = set(VEIN.glob("vein-*/results.json"))
    stage = OUT / "premining.json"
    env = dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env["GRADLE_USER_HOME"] = str(ROOT / "build/gradle-cache-ir030-sites")
    env["FC_CPU005_MODE"] = "plain"
    env["FC_CPU005_NAMESPACE"] = "vm"
    for key in (
        "FC_CPU004_MODE", "FC_CPU004_NAMESPACE",
        "FC_COMPILER_ACCEPTANCE_AUDIT", "FC_COMPILER_EXEC_CENSUS",
        "FC_COMMAND_CALLBACK_METRICS", "FC_SCORE_ADD_LEGACY_NAMESPACE",
        "FC_TYPED_IR_MODE", "FC_TYPED_IR_NAMESPACE",
        "FC_TYPED_IR_FUNCTION_FILTER", "FC_IR030_POS_GET",
    ):
        env.pop(key, None)
    command = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper", "--side", "6",
        "--capture-timeout", "150", "--no-spark", "--capture-server-thread-cpu",
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage),
    ]
    try:
        completed = subprocess.run(
            command, cwd=ROOT, env=env, text=True,
            capture_output=True, timeout=900, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("IR030 source-site native event timed out; do not retry") from exc
    (OUT / "runner.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (OUT / "runner.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(
            f"IR030 native event failed ({completed.returncode}): "
            f"{completed.stderr[-2000:]}")
    new = set(VEIN.glob("vein-*/results.json")) - previous
    if len(new) != 1:
        raise AssertionError(f"Expected exactly one new native event result, got {len(new)}")
    event_path = new.pop()
    event = json.loads(event_path.read_text(encoding="utf-8"))
    cpu = event.get("server_thread_event_cpu") or {}
    if (
        event.get("compiler_mode") != "wrapper"
        or event.get("cpu005_mode") != "plain"
        or "FC_CPU005 started mode=plain" not in str(event.get("cpu005_start_status"))
        or "FC_CPU005 ended mode=plain" not in str(event.get("cpu005_stop_status"))
        or event.get("datapack_sha256") != PIN
        or not event.get("valid_native_workload")
        or event.get("queue_head_delta") != 1952
        or event.get("work_after") != 215
        or event.get("run_state_after") != 0
        or event.get("event_timeout_reached")
        or not event.get("tick_pre_event_stability", {}).get("stable")
        or not cpu.get("cpu_measurement_valid")
        or not cpu.get("host_quality_pass")
        or event.get("jfr_cpu_capture_enabled")
        or event.get("jfr_execution_capture_enabled")
    ):
        raise AssertionError("IR030 native event, host, or instrumentation gates failed")
    raw_log = event_path.parent / "cpu005.log"
    if not raw_log.is_file():
        raise AssertionError("CPU005 plain-mode native site-count log missing")
    aggregate = parse_cpu005(raw_log, "plain")
    site_counts = parse_site_rows(raw_log.read_text(encoding="utf-8"))
    if aggregate["rows"]["append_data_get_leaf"]["calls"] != sum(site_counts.values()):
        raise AssertionError("Three exact source-site counts do not reconcile with aggregate leaf count")
    shutil.copy2(raw_log, OUT / "cpu005-site-counts.log")
    shutil.copy2(event_path, OUT / "native-event.json")
    report = {
        "milestone": "COMPILER-IR-030-GATE-C1",
        "status": "accepted_exact_source_site_exposure",
        "publisher_sha256": PIN,
        "source_order_status": source["status"],
        "append_here_call_sites": source["append_here_call_sites"],
        "enqueue_match_call_sites": source["enqueue_match_call_sites"],
        "minecraft": "26.3",
        "java": "25",
        "compiler_mode": "wrapper (no command optimizer)",
        "counter_mode": "CPU005 plain; no per-callback CPU clock reads",
        "native_event": {
            "work_after": event["work_after"],
            "queue_head_delta": event["queue_head_delta"],
            "run_state_after": event["run_state_after"],
            "server_thread_cpu_ns_descriptive_only": cpu["server_thread_cpu_running_ns"],
            "host_quality_pass": cpu["host_quality_pass"],
        },
        "exact_source_site_calls": site_counts,
        "aggregate_data_get_leaf_calls": aggregate["rows"]["append_data_get_leaf"]["calls"],
        "source_sites_sum_to_aggregate": True,
        "runtime_optimization_enabled": False,
        "semantic_equivalence_proven": False,
        "cpu_speedup_measured": False,
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IR030_SOURCE_SITES_ACCEPTED " + json.dumps({
        "site_calls": site_counts,
        "aggregate": report["aggregate_data_get_leaf_calls"],
        "work": report["native_event"]["work_after"],
        "queue_steps": report["native_event"]["queue_head_delta"],
    }), flush=True)
    return report


if __name__ == "__main__":
    run()
