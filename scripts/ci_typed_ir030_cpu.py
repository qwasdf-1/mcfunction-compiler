#!/usr/bin/env python3
"""IR-030 Gate D: preregistered original-world, uninstrumented CPU A/B pilot.

Four independent Minecraft 26.3/Java25 Fabric wrapper JVMs run the identical
215-unit original pinned Vein Miner event in A1-B1-B2-A2 order. Only
FC_IR030_POS_GET differs across A and B. All native snapshot verification,
per-callback research counters, JFR, Spark, callback census and other compiler
optimizers are disabled. This is descriptive pilot evidence, not promotion.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-030-CPU"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
RUN_ORDER = (("A1", False), ("B1", True), ("B2", True), ("A2", False))
AA_NOISE_LIMIT = 0.08
PROMOTION_EFFECT_THRESHOLD = 0.15

sys.path.insert(0, str(ROOT / "scripts"))
from ci_typed_ir015_fetch import fetch  # noqa: E402
from ci_typed_ir030_source import PIN, inspect as inspect_original_source  # noqa: E402
from ci_typed_ir030_native_event import status_flag, status_int  # noqa: E402


def check_timed_event(event: dict, treatment: bool) -> dict:
    if event.get("datapack_sha256") != PIN:
        raise AssertionError("CPU arm publisher SHA drift")
    if event.get("compiler_mode") != "wrapper" or event.get("stack") != "fabric":
        raise AssertionError("CPU arm changed compiler stack")
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
        raise AssertionError("CPU arm original-world conservation failed")
    if not event.get("tick_pre_event_stability", {}).get("stable"):
        raise AssertionError("CPU arm pre-event host instability")
    cpu = event.get("server_thread_event_cpu") or {}
    if (
        not cpu.get("host_quality_pass")
        or not cpu.get("cpu_measurement_valid")
        or cpu.get("cgroup_nr_throttled_delta") != 0
        or cpu.get("server_thread_cpu_running_ns", 0) <= 0
    ):
        raise AssertionError("Invalid Server-thread CPU clock or throttling")
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
    ):
        raise AssertionError("Unexpected compiler/source/profiler timing contamination")

    before = event.get("compiler_status_before")
    after = event.get("compiler_status_after")
    if not before or not after:
        raise AssertionError("CPU arm compiler status missing")
    for status in (before, after):
        if status_flag(status, "ir030_pos_get_enabled") != treatment:
            raise AssertionError("CPU arm treatment misconfigured")
        if status_flag(status, "ir030_pos_get_verify"):
            raise AssertionError("Native snapshot verifier contaminated CPU arm")
        for key in (
            "score_add_prototype_enabled", "score_add_metrics_enabled",
            "score_add_timing_enabled", "fused_region_prototype_enabled",
            "bytecode_region_prototype_enabled", "command_callback_metrics_enabled",
        ):
            if status_flag(status, key):
                raise AssertionError(f"Other compiler optimizer/diagnostic active: {key}")
    compiled = {axis: status_int(after, f"ir030_pos_compiled_{axis}")
                for axis in "xyz"}
    expected = dict.fromkeys("xyz", 1 if treatment else 0)
    if compiled != expected:
        raise AssertionError(f"CPU arm exact-terminal admission drift: {compiled!r}")
    # The B path really does bypass native reads, but the research counters
    # must be entirely off in BOTH timed arms, including fallback counters.
    diagnostics = {
        key: status_int(after, key) - status_int(before, key)
        for key in (
            *(f"ir030_pos_fast_{axis}" for axis in "xyz"),
            "ir030_pos_verified", "ir030_pos_verify_mismatches",
            "ir030_pos_invalid_targets", "ir030_pos_fallback_vehicle",
            "ir030_pos_fallback_entity_type", "ir030_pos_fallback_nonfinite",
        )
    }
    if any(diagnostics.values()):
        raise AssertionError(
            f"IR030 per-callback research diagnostics were live in CPU arm: {diagnostics!r}")

    return {
        "valid_native_workload": True,
        "exact_terminal_compiled": compiled,
        "candidate_enabled": treatment,
        "candidate_verification_enabled": False,
        "per_callback_research_diagnostics": False,
        "all_source_ore_marker_and_queue_gates_pass": True,
        "host_quality_pass": True,
        "cgroup_nr_throttled_delta": 0,
        "server_thread_cpu_running_ns": cpu["server_thread_cpu_running_ns"],
        "server_thread_cpu_ns_per_work_unit": (
            cpu["server_thread_cpu_running_ns"] / 215),
        "original_work_units": 215,
        "queue_steps": 1952,
        "native_snapshot_verification_was_disabled": True,
    }


def run_arm(label: str, treatment: bool) -> dict:
    old_paths = set(VEIN.glob("vein-*/results.json"))
    env = dict(os.environ)
    env.update({
        "GRADLE_USER_HOME": str(ROOT / "build/gradle-cache-ir030-cpu"),
        "GRADLE_RO_DEP_CACHE": str(Path.home() / ".gradle" / "caches"),
        "FC_IR030_POS_GET": "true" if treatment else "false",
        "FC_IR030_POS_GET_VERIFY": "false",
        # Same exact allowlist in both arms; only the enable flag changes.
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
        "FC_CPU005_MODE": "", "FC_CPU004_MODE": "", "FC_MACRO006_MODE": "",
    })
    for key in (
        "FC_COMPILER_EXEC_CENSUS", "FC_COMPILER_ACCEPTANCE_NAMESPACE",
        "FC_TYPED_IR_MODE", "FC_TYPED_IR_NAMESPACE",
        "FC_TYPED_IR_FUNCTION_FILTER",
    ):
        env.pop(key, None)
    options = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper", "--side", "6",
        "--capture-timeout", "150", "--no-spark", "--capture-server-thread-cpu",
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(OUT / f"{label}-readiness.json"),
    ]
    arm = {
        "label": label,
        "treatment": "direct_pos_get" if treatment else "native_pos_get",
        "candidate_enabled": treatment,
        "status": "started",
        "same_installed_research_jar": True,
        "original_publisher_sha256": PIN,
        "diagnostic_counters_during_timing": False,
        "cpu_speedup_confirmed": False,
    }
    try:
        try:
            completed = subprocess.run(
                options, cwd=ROOT, env=env, text=True, capture_output=True,
                timeout=900, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"CPU arm {label} timed out; do not retry") from exc
        (OUT / f"{label}-runner.stdout.log").write_text(
            completed.stdout, encoding="utf-8")
        (OUT / f"{label}-runner.stderr.log").write_text(
            completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(
                f"CPU arm {label} original event failed ({completed.returncode}): "
                f"{completed.stderr[-1800:]}")
        new = set(VEIN.glob("vein-*/results.json")) - old_paths
        if len(new) != 1:
            raise AssertionError(
                f"CPU arm {label} produced {len(new)} new manifests, expected 1")
        manifest = new.pop()
        event = json.loads(manifest.read_text(encoding="utf-8"))
        shutil.copy2(manifest, OUT / f"{label}-native-event.json")
        arm["validation"] = check_timed_event(event, treatment)
        arm["status"] = "accepted_native_event_cpu_arm"
        print("IR030_CPU_ARM " + json.dumps({
            "label": label, "candidate": treatment,
            "server_thread_cpu_ns":
                arm["validation"]["server_thread_cpu_running_ns"],
            "original_work": 215, "queue_steps": 1952,
            "host_quality": True,
            "research_counters": False,
        }, sort_keys=True), flush=True)
        return arm
    except Exception as exc:
        arm["status"] = "invalid_arm"
        arm["error"] = repr(exc)
        raise
    finally:
        (OUT / f"{label}.json").write_text(
            json.dumps(arm, indent=2) + "\n", encoding="utf-8")


def analyze(arms: dict[str, dict]) -> dict:
    if set(arms) != {label for label, _ in RUN_ORDER}:
        raise AssertionError("Incomplete pre-registered four-arm study")
    if any(arms[label]["candidate_enabled"] != enabled for label, enabled in RUN_ORDER):
        raise AssertionError("CPU treatment order altered")
    if any(arms[label]["status"] != "accepted_native_event_cpu_arm"
           for label, _ in RUN_ORDER):
        raise AssertionError("One or more original CPU arms were rejected")
    vals = {
        label: arms[label]["validation"]["server_thread_cpu_ns_per_work_unit"]
        for label, _ in RUN_ORDER
    }
    median_a = statistics.median((vals["A1"], vals["A2"]))
    median_b = statistics.median((vals["B1"], vals["B2"]))
    aa_spread = abs(vals["A1"] - vals["A2"]) / median_a
    reduction = (median_a - median_b) / median_a
    return {
        "description": "4 fresh original-event JVMs, same jar, ABBA order, descriptive only",
        "treatment_order": [
            {"arm": label, "candidate_enabled": enabled} for label, enabled in RUN_ORDER
        ],
        "cpu_ns_per_affected_block": vals,
        "original_event_cpu_median_native_ns_per_block": median_a,
        "original_event_cpu_median_candidate_ns_per_block": median_b,
        "A_A_relative_spread": aa_spread,
        "A_A_stable_within_8pct": aa_spread <= AA_NOISE_LIMIT,
        "relative_candidate_cpu_reduction_observed": reduction,
        "candidate_to_AA_spread_ratio": (
            abs(reduction) / aa_spread if aa_spread else None),
        "all_original_gameplay_gates_passed": True,
        "all_host_quality_gates_passed": True,
        "research_profiling_disabled": True,
        "promotion_effect_threshold": PROMOTION_EFFECT_THRESHOLD,
        "meets_raw_15pct_threshold": reduction >= PROMOTION_EFFECT_THRESHOLD,
        "independent_replication_completed": False,
        "causal_speedup_confirmed": False,
        "production_promotion": False,
        "n_per_treatment": 2,
    }


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "milestone": "COMPILER-IR-030-GATE-D",
        "status": "started",
        "run_order": [
            {"arm": label, "candidate_enabled": treatment}
            for label, treatment in RUN_ORDER
        ],
        "publisher_sha256": PIN,
        "uninstrumented_cpu_window": True,
        "preregistered_AA_maximum_spread": AA_NOISE_LIMIT,
        "preregistered_promotion_threshold": PROMOTION_EFFECT_THRESHOLD,
        "promote_candidate": False,
        "results": {},
    }
    try:
        if not PACK.is_file():
            fetch("veinminer")
        if hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
            raise AssertionError("Publisher archive SHA drift")
        source = inspect_original_source()
        if source["status"] != "verified_exact_original_source_only":
            raise AssertionError("Original publisher command order drift")
        report["source_command_order_verified"] = True
        for label, treatment in RUN_ORDER:
            report["results"][label] = run_arm(label, treatment)
            (OUT / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report["analysis"] = analyze(report["results"])
        if report["analysis"]["A_A_stable_within_8pct"]:
            report["status"] = "accepted_uninstrumented_cpu_pilot_no_promotion"
        else:
            report["status"] = "inconclusive_AA_instability_no_promotion"
        print("IR030_CPU_SUMMARY " + json.dumps({
            "status": report["status"],
            "A_A_relative_spread": report["analysis"]["A_A_relative_spread"],
            "relative_candidate_cpu_reduction_observed":
                report["analysis"]["relative_candidate_cpu_reduction_observed"],
            "sample_count": 4,
            "promotion": False,
        }, sort_keys=True), flush=True)
    except Exception as exc:
        report["status"] = "invalid_cpu_study"
        report["error"] = repr(exc)
        raise
    finally:
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
