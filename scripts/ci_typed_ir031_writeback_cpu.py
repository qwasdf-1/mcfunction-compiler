#!/usr/bin/env python3
"""IR-031 Gate B: source-specific Entity.load CPU exposure in original Vein Miner.

Runs three fresh Fabric/wrapper JVMs (PLAIN, EMPTY, TIMED) on the same pinned
publisher event. Sparse clocks surround only Entity.load invoked by
EntityDataAccessor.setData from the three exact unmounted Marker frontier
coordinate stores. This is cost attribution, not an optimization or A/B test.
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
OUT = ROOT / "build/reports/COMPILER-IR-031-WRITEBACK-CPU"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
MODES = ("plain", "empty", "timed")

sys.path.insert(0, str(ROOT / "scripts"))
from ci_typed_ir015_fetch import fetch  # noqa: E402
from ci_typed_ir030_source import PIN, inspect as inspect_original_source  # noqa: E402
from analyze_ir031_writeback_cpu import parse, project  # noqa: E402
from ci_typed_ir030_native_event import status_flag  # noqa: E402


def verify_event(event: dict, mode: str) -> dict:
    if event.get("datapack_sha256") != PIN:
        raise AssertionError(f"{mode}: original publisher SHA drift")
    if event.get("compiler_mode") != "wrapper" or event.get("stack") != "fabric":
        raise AssertionError(f"{mode}: required Fabric wrapper stack absent")
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
        raise AssertionError(f"{mode}: original world conservation failed")
    if not event.get("tick_pre_event_stability", {}).get("stable"):
        raise AssertionError(f"{mode}: pre-event host stability failed")
    cpu = event.get("server_thread_event_cpu") or {}
    if (
        not cpu.get("host_quality_pass")
        or not cpu.get("cpu_measurement_valid")
        or cpu.get("cgroup_nr_throttled_delta") != 0
        or cpu.get("server_thread_cpu_running_ns", 0) <= 0
    ):
        raise AssertionError(f"{mode}: invalid or throttled Server-thread CPU clock")

    if event.get("ir031_mode") != mode:
        raise AssertionError(f"{mode}: runner manifest IR031 mode drift")
    if not str(event.get("ir031_start_status", "")).startswith(
        f"IR031 started mode={mode}"
    ):
        raise AssertionError(f"{mode}: diagnostic failed to start")
    if not str(event.get("ir031_stop_status", "")).startswith(
        f"IR031 ended mode={mode}"
    ):
        raise AssertionError(f"{mode}: diagnostic failed to stop")

    if (
        event.get("command_callback_metrics_enabled")
        or event.get("compiler_exec_census_enabled")
        or event.get("compiler_acceptance_audit_enabled")
        or event.get("cpu004_mode") is not None
        or event.get("cpu005_mode") is not None
        or event.get("macro006_mode") is not None
        or event.get("jfr_cpu_capture_enabled")
        or event.get("jfr_execution_capture_enabled")
        or event.get("spark_capture_enabled")
        or event.get("selective_macro_arguments_metrics_enabled")
    ):
        raise AssertionError(f"{mode}: unexpected profiling contamination")

    before = event.get("compiler_status_before")
    after = event.get("compiler_status_after")
    if not before or not after:
        raise AssertionError(f"{mode}: missing compiler before/after status")
    for status in (before, after):
        if status_flag(status, "ir030_pos_get_enabled"):
            raise AssertionError(f"{mode}: IR030 getter candidate must be disabled")
        if status_flag(status, "ir030_pos_get_verify"):
            raise AssertionError(f"{mode}: IR030 verifier must be disabled")
        if status_flag(status, "selective_macro_arguments_enabled"):
            raise AssertionError(f"{mode}: selective macro arguments must be fixed off")
        for key in (
            "score_add_prototype_enabled", "score_add_metrics_enabled",
            "score_add_timing_enabled", "fused_region_prototype_enabled",
            "bytecode_region_prototype_enabled", "command_callback_metrics_enabled",
        ):
            if status_flag(status, key):
                raise AssertionError(f"{mode}: unexpected research feature active: {key}")

    return {
        "status": "accepted_original_event_entity_load_arm",
        "mode": mode,
        "work_units": 215,
        "queue_steps": 1952,
        "server_thread_cpu_running_ns": cpu["server_thread_cpu_running_ns"],
        "host_quality_pass": True,
        "cgroup_nr_throttled_delta": 0,
        "all_original_world_conservation_gates": True,
        "ir030_getter_disabled": True,
        "selective_macro_arguments_disabled_for_baseline_match": True,
        "all_other_research_profilers_disabled": True,
    }


def run_arm(mode: str) -> dict:
    previous = set(VEIN.glob("vein-*/results.json"))
    env = dict(os.environ)
    env.update({
        "GRADLE_USER_HOME": str(ROOT / "build/gradle-cache-ir031-writeback"),
        "GRADLE_RO_DEP_CACHE": str(Path.home() / ".gradle" / "caches"),
        "FC_IR031_MODE": mode,
        "FC_IR031_NAMESPACE": "vm",
        "FC_IR030_POS_GET": "false",
        "FC_IR030_POS_GET_VERIFY": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": "false",
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

    arm = {
        "mode": mode,
        "status": "started",
        "candidate_enabled": False,
        "original_publisher_sha256": PIN,
        "exact_source_site_entity_load_timing": True,
        "cpu_speedup_measured": False,
    }
    command = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper", "--side", "6",
        "--capture-timeout", "150", "--no-spark", "--capture-server-thread-cpu",
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(OUT / f"{mode}-readiness.json"),
    ]
    try:
        try:
            completed = subprocess.run(
                command, cwd=ROOT, env=env, text=True, capture_output=True,
                timeout=900, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"IR031 {mode} event timed out; do not retry") from exc
        (OUT / f"{mode}-runner.stdout.log").write_text(
            completed.stdout, encoding="utf-8")
        (OUT / f"{mode}-runner.stderr.log").write_text(
            completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(
                f"IR031 {mode} runner failed ({completed.returncode}): "
                f"{completed.stderr[-1800:]}")
        new = set(VEIN.glob("vein-*/results.json")) - previous
        if len(new) != 1:
            raise AssertionError(
                f"IR031 {mode}: exactly one new event manifest expected, found {len(new)}")
        manifest = new.pop()
        event = json.loads(manifest.read_text(encoding="utf-8"))
        arm["validation"] = verify_event(event, mode)
        shutil.copy2(manifest, OUT / f"{mode}-event.json")
        log_path = manifest.parent / "ir031.log"
        if not log_path.is_file():
            raise AssertionError(f"IR031 {mode}: exact Entity.load timing log missing")
        shutil.copy2(log_path, OUT / f"{mode}-ir031.log")
        arm["measurement"] = parse(OUT / f"{mode}-ir031.log", mode)
        arm["status"] = "accepted_original_event_entity_load_arm"
        print("IR031_WRITEBACK_ARM " + json.dumps({
            "mode": mode,
            "entity_load_calls": {
                axis: arm["measurement"]["rows"][axis]["entity_load_calls"]
                for axis in "xyz"
            },
            "server_thread_cpu_ns": arm["validation"]["server_thread_cpu_running_ns"],
            "host_quality": True,
        }, sort_keys=True), flush=True)
        return arm
    except Exception as exc:
        arm["status"] = "invalid_arm"
        arm["error"] = repr(exc)
        raise
    finally:
        (OUT / f"{mode}.json").write_text(
            json.dumps(arm, indent=2) + "\n", encoding="utf-8")


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "milestone": "COMPILER-IR-031-GATE-B",
        "status": "started",
        "publisher_sha256": PIN,
        "mode_order": list(MODES),
        "stride": 16,
        "expected_entity_loads_per_axis": 1940,
        "predeclared_candidate_screen": {
            "minimum_projected_entity_load_share": 0.05,
            "minimum_corrected_mean_to_empty_clock_ratio": 3.0,
        },
        "runtime_optimizer_implemented": False,
        "semantic_equivalence_proven": False,
        "cpu_speedup_measured": False,
        "production_promotion": False,
        "arms": {},
    }
    try:
        if not PACK.is_file():
            fetch("veinminer")
        if hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
            raise AssertionError("Original publisher archive SHA mismatch")
        source = inspect_original_source()
        if source["status"] != "verified_exact_original_source_only":
            raise AssertionError("Pinned original publisher source order failed")
        report["publisher_source_sites"] = source["commands"]

        for mode in MODES:
            report["arms"][mode] = run_arm(mode)
            (OUT / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")

        plain_cpu = report["arms"]["plain"]["validation"]["server_thread_cpu_running_ns"]
        report["analysis"] = project(
            report["arms"]["plain"]["measurement"],
            report["arms"]["empty"]["measurement"],
            report["arms"]["timed"]["measurement"],
            plain_cpu,
        )
        if report["analysis"]["candidate_research_warranted"]:
            report["status"] = "accepted_entity_load_cost_warrants_semantic_candidate_study"
        else:
            report["status"] = "accepted_entity_load_attribution_below_candidate_screen"
        print("IR031_WRITEBACK_SUMMARY " + json.dumps({
            "status": report["status"],
            "projected_event_cpu_fraction":
                report["analysis"]["signed_projected_entity_load_event_cpu_fraction"],
            "all_axes_above_clock_floor":
                report["analysis"]["all_axes_above_three_times_empty_clock_floor"],
            "candidate_research_warranted":
                report["analysis"]["candidate_research_warranted"],
            "cpu_speedup_measured": False,
        }, sort_keys=True), flush=True)
    except Exception as exc:
        report["status"] = "invalid_entity_load_attribution"
        report["error"] = repr(exc)
        raise
    finally:
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
