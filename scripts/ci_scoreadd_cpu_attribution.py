#!/usr/bin/env python3
"""SCHED-COMP-021: two independent Vein Miner CPU-time stack attribution boots.

This is a *mechanism diagnostic*, not a CPU performance experiment. The
JDK 25 CPU-time sampler runs in separate compiler-off and cached-ScoreAdd
servers; no counters or Spark. No hypothesis test is derived from two boots.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ci_scoreadd_workload_share import (  # noqa: E402
    EXPECTED_PACK_SHA, PACK, WORK_EXPECTED, QUEUE_STEPS_EXPECTED,
    STATE_FIELDS, verify_pack,
)
from analyze_veinminer_jfr_cpu import analyze_jfr  # noqa: E402

OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-COMP-021"
ARMS = (("off_jfr", "off"), ("cached_jfr", "score-add"))


def run_native(arm: str, mode: str) -> dict:
    stage = OUTPUT / f"premining-{arm}.json"
    command = [
        sys.executable, str(ROOT / "scripts" / "run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", mode,
        "--side", "6", "--capture-timeout", "150",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage),
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
        "--capture-server-thread-cpu", "--capture-jfr-cpu", "--no-spark",
    ]
    env = dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env["GRADLE_USER_HOME"] = str(OUTPUT / "gradle-user-home")
    env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE", None)
    result = subprocess.run(
        command, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=750, check=False)
    (OUTPUT / f"{arm}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (OUTPUT / f"{arm}.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(
            f"{arm}: native event failed exit={result.returncode}; "
            f"stderr={result.stderr[-3000:]!r}, stdout={result.stdout[-1200:]!r}")
    payload = json.loads(result.stdout)
    data = payload["results"]
    cpu = data.get("server_thread_event_cpu")
    if (data.get("compiler_mode") != mode
        or not data.get("valid_native_workload")
        or data.get("work_expected") != WORK_EXPECTED
        or data.get("queue_head_delta") != QUEUE_STEPS_EXPECTED
        or data.get("run_state_after") != 0
        or not data.get("tick_pre_event_stability", {}).get("stable")
        or not isinstance(cpu, dict)
        or not cpu.get("cpu_measurement_valid")
        or not cpu.get("host_quality_pass")
        or data.get("datapack_sha256") != EXPECTED_PACK_SHA
        or not data.get("jfr_cpu_capture_enabled")
        or data.get("spark_capture_enabled")
        or data.get("command_callback_metrics_enabled")
        or data.get("selective_macro_arguments_metrics_enabled")
        or data.get("score_add_executed_delta") is None):
        raise AssertionError(f"{arm}: invalid event, CPU, artifact, or sampling contract")
    compiled = data.get("queue_score_add_compiled")
    if mode == "off" and compiled not in (0, None):
        raise AssertionError("Compiler-off arm specialized commands")
    if mode == "score-add" and (type(compiled) is not int or compiled <= 0):
        raise AssertionError("Cached ScoreAdd arm has no compiled commands")
    profile_name = data.get("jfr_cpu_profile_path")
    if not isinstance(profile_name, str):
        raise AssertionError("Missing native JFR artifact path")
    profile = (ROOT / profile_name).resolve()
    if not profile.is_relative_to((ROOT / "build" / "benchmarks").resolve()):
        raise AssertionError("JFR profile escaped benchmark directory")
    if hashlib.sha256(profile.read_bytes()).hexdigest() != data.get("jfr_cpu_profile_sha256"):
        raise AssertionError("JFR file fingerprint mismatch")
    attribution = analyze_jfr(profile, cpu["server_thread_tid"])
    return {
        "arm": arm,
        "mode": mode,
        "pinned_pack": data["datapack_sha256"],
        "native_state": {key: data[key] for key in STATE_FIELDS},
        "compiler_queue_score_add_compiled": compiled,
        "server_thread_cpu_running_ns": cpu["server_thread_cpu_running_ns"],
        "server_thread_host_quality": cpu["host_quality_pass"],
        "jfr_profile_path": profile_name,
        "jfr_profile_sha256": data["jfr_cpu_profile_sha256"],
        "native_result_json": payload.get("output"),
        "sample_attribution": attribution,
        "event_seconds": data.get("operation_completion_seconds"),
    }


def interpret(records: dict[str, dict]) -> dict:
    if set(records) != {arm for arm, _ in ARMS}:
        raise AssertionError("Missing independent JFR arms")
    if {r["pinned_pack"] for r in records.values()} != {EXPECTED_PACK_SHA}:
        raise AssertionError("Publisher archive mismatch")
    if len({json.dumps(r["native_state"], sort_keys=True) for r in records.values()}) != 1:
        raise AssertionError("Native work/state not identical across arms")
    for name, mode in ARMS:
        r = records[name]
        attr = r["sample_attribution"]
        if (r["mode"] != mode or
            not r["server_thread_host_quality"] or
            r["server_thread_cpu_running_ns"] <= 0 or
            not attr["diagnostic_valid"]):
            raise AssertionError(f"Invalid sampled CPU arm: {name}")
    off = records["off_jfr"]["sample_attribution"]
    cached = records["cached_jfr"]["sample_attribution"]
    return {
        "diagnostic_valid": True,
        "valid_native_event_parity": True,
        "diagnostic_only": True,
        "per_arm_sampled_scoreadd_share": {
            "off": off["scoreadd_sampled_cpu_fraction"],
            "cached": cached["scoreadd_sampled_cpu_fraction"],
        },
        "per_arm_server_cpu_running_ns": {
            "off": records["off_jfr"]["server_thread_cpu_running_ns"],
            "cached": records["cached_jfr"]["server_thread_cpu_running_ns"],
        },
        "cached_ideal_scoreadd_elimination_upper_bound_from_samples": (
            cached["scoreadd_ideal_elimination_upper_bound_from_samples"]
        ),
        "interpretation": (
            "The cached arm's typed ScoreAdd CPUTimeSample fraction estimates the"
            " Server-thread on-CPU share spent inside the typed callback subtree."
            " This is an idealized upper bound for eliminating *all* such sampled"
            " work, not the achievable gain from a config cache, whose optimized"
            " region is narrower. Off and cached arms are independent, unpaired"
            " JFR diagnostics; CPU totals and shares are not causal comparisons."
        ),
        "limitations": (
            "JDK 25 CPUTimeSample is experimental, sampled stacks can omit"
            " frames (e.g. inlining), some samples can be lost/biased, and"
            " RCON boundary checks are part of the approximate capture window."
            " No confidence interval or significance is claimed from one"
            " profile per arm. The 11,124 direct-success count from SCHED-COMP-020"
            " belongs to a different instrumented JVM and cannot be assumed"
            " identical in either JFR event."
        ),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "diagnostic.json"
    report = {
        "study": "SCHED-COMP-021", "status": "started",
        "diagnostic_only": True, "noncausal": True,
        "records": {},
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        report["publisher_pack_sha256"] = verify_pack()
        for arm, mode in ARMS:
            print(f"SCHED-COMP-021 JFR ARM {arm}", flush=True)
            report["records"][arm] = run_native(arm, mode)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report["analysis"] = interpret(report["records"])
        report["status"] = "complete"
        print("SCHED-COMP-021 COMPLETE " + json.dumps(report["analysis"]), flush=True)
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = repr(exc)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
