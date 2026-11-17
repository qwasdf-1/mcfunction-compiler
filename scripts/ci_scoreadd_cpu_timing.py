#!/usr/bin/env python3
"""SCHED-COMP-022: calibrated per-callback ThreadMXBean CPU time in real Vein Miner.

This is a diagnostic, NOT a paired speedup experiment. The three arms use
identical cached ScoreAdd behavior, but are independent JVM boots:
* plain: no per-callback CPU clock,
* empty: two adjacent CPU clock reads, then the real typed callback,
* timed: two CPU clock reads bracketing the real typed callback.

Their aggregate difference is a noisy overhead-controlled CPU attribution
estimate. It is not an exact timer or an empirical optimizer speedup.
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
    EXPECTED_PACK_SHA, STATE_FIELDS, WORK_EXPECTED,
    QUEUE_STEPS_EXPECTED, verify_pack,
)

OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-COMP-022"
ARMS = (("plain", "off"), ("empty_control", "empty"), ("timed_callback", "timed"))
MAX_PROBE_COUNT_RELATIVE_DIFFERENCE = 0.10
MAX_TIMED_ZERO_DELTA_FRACTION = 0.20


def run_native(arm: str, mode: str) -> dict:
    stage = OUTPUT / f"premining-{arm}.json"
    command = [
        sys.executable, str(ROOT / "scripts" / "run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "score-add", "--side", "6",
        "--no-spark", "--capture-server-thread-cpu",
        "--scoreadd-cpu-probe", mode,
        "--capture-timeout", "150", "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage),
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
    ]
    env = os.environ.copy()
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE", None)
    env["GRADLE_USER_HOME"] = str(OUTPUT / "gradle-user-home")
    # Runner explicitly sets FC_SCORE_ADD_CPU_PROBE in the child JVM.
    done = subprocess.run(
        command, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=750, check=False,
    )
    (OUTPUT / f"{arm}.stdout.log").write_text(done.stdout, encoding="utf-8")
    (OUTPUT / f"{arm}.stderr.log").write_text(done.stderr, encoding="utf-8")
    if done.returncode:
        raise RuntimeError(
            f"{arm} native event failed (exit {done.returncode}): "
            f"{done.stderr[-3200:]!r}; stdout tail {done.stdout[-1400:]!r}"
        )
    payload = json.loads(done.stdout)
    data = payload["results"]
    cpu = data.get("server_thread_event_cpu")
    if not (
        data.get("valid_native_workload")
        and data.get("valid_score_add_profile")
        and data.get("work_expected") == WORK_EXPECTED
        and data.get("queue_head_delta") == QUEUE_STEPS_EXPECTED
        and data.get("run_state_after") == 0
        and data.get("tick_pre_event_stability", {}).get("stable")
        and isinstance(cpu, dict)
        and cpu.get("cpu_measurement_valid")
        and cpu.get("host_quality_pass")
        and data.get("datapack_sha256") == EXPECTED_PACK_SHA
        and data.get("compiler_mode") == "score-add"
        and data.get("score_add_cpu_probe_mode") == mode
        and not data.get("spark_capture_enabled")
        and not data.get("jfr_cpu_capture_enabled")
        and not data.get("command_callback_metrics_enabled")
        and not data.get("selective_macro_arguments_metrics_enabled")
        and data.get("queue_score_add_compiled") == 4
    ):
        raise AssertionError(f"{arm}: invalid event, host, fixture or compiler setup")
    probe = data.get("score_add_cpu_probe")
    if mode == "off":
        if probe is not None:
            raise AssertionError("Plain CPU arm unexpectedly instrumented")
    else:
        if not isinstance(probe, dict) or probe.get("mode") != mode:
            raise AssertionError(f"{arm}: missing typed CPU probe")
        entries = probe.get("callback_samples")
        successes = probe.get("direct_successes")
        measured = probe.get("measured_cpu_ns")
        zeros = probe.get("zero_delta_samples")
        if (type(entries) is not int or entries < 1000
            or successes != entries
            or type(measured) is not int or measured < 0
            or measured > cpu["server_thread_cpu_running_ns"]
            or type(zeros) is not int or not 0 <= zeros <= entries):
            raise AssertionError(f"{arm}: bad typed CPU sample count/clock bounds")
    return {
        "arm": arm,
        "mode": mode,
        "publisher_sha256": data["datapack_sha256"],
        "native_state": {k: data[k] for k in STATE_FIELDS},
        "queue_score_add_compiled": data["queue_score_add_compiled"],
        "server_thread_cpu_running_ns": cpu["server_thread_cpu_running_ns"],
        "host_quality_pass": cpu["host_quality_pass"],
        "event_completion_seconds": data.get("operation_completion_seconds"),
        "probe": probe,
        "native_result_json": payload.get("output"),
        "probe_clock": "JDK ThreadMXBean.getCurrentThreadCpuTime",
    }


def interpret(records: dict[str, dict]) -> dict:
    if set(records) != {name for name, _ in ARMS}:
        raise AssertionError("Missing one or more independent calibration arms")
    if {r["publisher_sha256"] for r in records.values()} != {EXPECTED_PACK_SHA}:
        raise AssertionError("Different publisher datapack across arms")
    if len({json.dumps(r["native_state"], sort_keys=True) for r in records.values()}) != 1:
        raise AssertionError("Different ore work/final state across arms")
    for name, mode in ARMS:
        rec = records[name]
        if (rec["mode"] != mode or not rec["host_quality_pass"]
            or rec["server_thread_cpu_running_ns"] <= 0
            or rec["queue_score_add_compiled"] != 4):
            raise AssertionError(f"Invalid native arm {name}")
        if (rec["probe"] is None) != (mode == "off"):
            raise AssertionError(f"Probe unexpected in {name}")

    ctrl = records["empty_control"]["probe"]
    timed = records["timed_callback"]["probe"]
    ctrl_n = ctrl["callback_samples"]
    timed_n = timed["callback_samples"]
    if (abs(ctrl_n - timed_n) / max(ctrl_n, timed_n)
            > MAX_PROBE_COUNT_RELATIVE_DIFFERENCE):
        raise AssertionError("Typed callback exposure differs by >10% between arms")

    ctrl_avg = ctrl["measured_cpu_ns"] / ctrl_n
    timed_avg = timed["measured_cpu_ns"] / timed_n
    signed_corrected = timed_avg - ctrl_avg
    zero_fraction = timed["zero_delta_samples"] / timed_n
    corrected_fraction = (
        signed_corrected * timed_n / records["timed_callback"]["server_thread_cpu_running_ns"]
    )
    estimable = signed_corrected > 0 and zero_fraction <= MAX_TIMED_ZERO_DELTA_FRACTION
    # Preserve signed differences: clamping at zero would silently manufacture
    # a one-sided favorable estimate on a noisy control comparison.
    return {
        "diagnostic_valid": True,
        "event_parity_verified": True,
        "independent_jvm_arms": True,
        "plain_server_cpu_ns": records["plain"]["server_thread_cpu_running_ns"],
        "empty_control_server_cpu_ns": records["empty_control"]["server_thread_cpu_running_ns"],
        "timed_server_cpu_ns": records["timed_callback"]["server_thread_cpu_running_ns"],
        "empty_control_samples": ctrl_n,
        "timed_callback_samples": timed_n,
        "empty_control_cpu_ns_per_pair": ctrl_avg,
        "timed_cpu_ns_per_callback_including_clock": timed_avg,
        "signed_overhead_corrected_cpu_ns_per_callback": signed_corrected,
        "signed_overhead_corrected_callback_share_of_timed_server_cpu": corrected_fraction,
        "timed_zero_delta_fraction": zero_fraction,
        "calibration_interpretable": estimable,
        "decision": (
            "diagnostic_only_control_separated"
            if estimable else "inconclusive_clock_floor_or_negative_correction"
        ),
        "limitations": (
            "ThreadMXBean reports on-CPU time with nanosecond precision, not"
            " nanosecond accuracy. Empty and timed arms run in independent JVMs;"
            " their mean difference includes JIT/host/command-mix differences."
            " The directSuccess counter itself is inside timed brackets but"
            " outside empty brackets; its overhead biases the estimate upward."
            " A callback includes scoreboard mutation, feedback and descendants,"
            " not the narrow config flag-cache code. Uninstrumented total CPU"
            " is a reference only: these three independent boots cannot yield"
            " a causal A/B speedup or confidence interval."
        ),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "diagnostic.json"
    report: dict = {
        "study": "SCHED-COMP-022",
        "status": "started",
        "diagnostic_only": True,
        "noncausal": True,
        "arms": [a for a, _ in ARMS],
        "records": {},
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        report["publisher_pack_sha256"] = verify_pack()
        for arm, mode in ARMS:
            print(f"SCHED-COMP-022 CPU ATTRIBUTION ARM {arm}", flush=True)
            report["records"][arm] = run_native(arm, mode)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report["analysis"] = interpret(report["records"])
        report["status"] = "complete"
        print("SCHED-COMP-022 COMPLETE " + json.dumps(report["analysis"]), flush=True)
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
