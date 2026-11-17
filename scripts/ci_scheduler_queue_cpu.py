#!/usr/bin/env python3
"""SCHED-ATTR-023: isolate queue-loop CPU from dequeued entry execution.

Three independent native Vein Miner JVMs with identical cached ScoreAdd:
plain / empty clock-pairs / timed real intervals. CPU on the Server thread
is from Linux schedstat, no JFR/Spark, no per-command execution counters.

These are overlapping nested clocks. The timed outer queue interval includes
all inner entry CPU, so a *difference* is an instrumented queue-loop residual.
It includes timer overhead and cannot be interpreted as all scheduler CPU or
the CPU recoverable through a general scheduler replacement.
"""
from __future__ import annotations

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

OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-ATTR-023"
ARMS = (("plain", "off"), ("empty_control", "empty"), ("timed_queue", "timed"))
MAX_COUNT_RELATIVE_DIFFERENCE = 0.25
MAX_TIMED_ZERO_DELTA_FRACTION = 0.20
MAX_EVENT_CPU_PERTURBATION_FRACTION = 0.30


def run_native(arm: str, mode: str) -> dict:
    stage = OUTPUT / f"premining-{arm}.json"
    command = [
        sys.executable, str(ROOT / "scripts" / "run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "score-add", "--side", "6",
        "--no-spark", "--capture-server-thread-cpu",
        "--scheduler-cpu-harness", "--scheduler-queue-cpu-probe", mode,
        "--capture-timeout", "150", "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage),
        "--tick-stability-diagnostics", "--pre-event-idle-seconds", "9",
    ]
    env = os.environ.copy()
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE", None)
    env.pop("FC_SCORE_ADD_CPU_PROBE", None)
    env["GRADLE_USER_HOME"] = str(OUTPUT / "gradle-user-home")
    result = subprocess.run(
        command, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=750, check=False,
    )
    (OUTPUT / f"{arm}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (OUTPUT / f"{arm}.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(
            f"{arm} native workload exited {result.returncode}:"
            f" stderr={result.stderr[-3500:]!r}, stdout={result.stdout[-1200:]!r}"
        )
    payload = json.loads(result.stdout)
    data = payload["results"]
    cpu = data.get("server_thread_event_cpu")
    probe = data.get("scheduler_cpu_probe")
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
        and data.get("queue_score_add_compiled") == 4
        and data.get("scheduler_cpu_probe_harness") is True
        and data.get("scheduler_cpu_probe_mode") == mode
        and not data.get("spark_capture_enabled")
        and not data.get("jfr_cpu_capture_enabled")
        and not data.get("command_callback_metrics_enabled")
        and not data.get("selective_macro_arguments_metrics_enabled")
        and isinstance(probe, dict) and probe.get("mode") == mode
        and probe.get("sessions_started") == 1
        and probe.get("sessions_ended") == 1
        and probe.get("nested_queue_events") == 0
        and probe.get("nested_entry_events") == 0
    ):
        raise AssertionError(f"{arm}: native event/probe state/host quality failed")
    if mode == "off":
        if any(probe.get(field) for field in (
                "queue_samples", "entry_samples", "queue_cpu_ns",
                "entry_cpu_ns", "queue_zero_deltas", "entry_zero_deltas")):
            raise AssertionError("Plain arm recorded unexpected CPU clock work")
    else:
        q, e = probe.get("queue_samples"), probe.get("entry_samples")
        q_ns, e_ns = probe.get("queue_cpu_ns"), probe.get("entry_cpu_ns")
        qz, ez = probe.get("queue_zero_deltas"), probe.get("entry_zero_deltas")
        if not (
            probe.get("clock_ready")
            and type(q) is int and q >= 20
            and type(e) is int and e >= 100
            and type(q_ns) is int and q_ns >= 0
            and type(e_ns) is int and e_ns >= 0
            and type(qz) is int and 0 <= qz <= q
            and type(ez) is int and 0 <= ez <= e
            and type(probe.get("java_thread_id")) is int
            and probe["java_thread_id"] > 0
        ):
            raise AssertionError(f"{arm}: invalid CPU clock support/counters")
        if mode == "timed" and not (
                q_ns >= e_ns and q_ns <= cpu["server_thread_cpu_running_ns"]):
            raise AssertionError(f"{arm}: overlapping CPU clocks inconsistent with /proc")
    return {
        "arm": arm, "mode": mode,
        "publisher_sha256": data["datapack_sha256"],
        "native_state": {k: data[k] for k in STATE_FIELDS},
        "queue_score_add_compiled": data["queue_score_add_compiled"],
        "server_thread_cpu_running_ns": cpu["server_thread_cpu_running_ns"],
        "host_quality_pass": cpu["host_quality_pass"],
        "event_completion_seconds": data["operation_completion_seconds"],
        "probe": probe,
        "native_result_json": payload.get("output"),
    }


def interpret(records: dict[str, dict]) -> dict:
    if set(records) != {name for name, _ in ARMS}:
        raise AssertionError("Three independent arms required; no partial result")
    if {r["publisher_sha256"] for r in records.values()} != {EXPECTED_PACK_SHA}:
        raise AssertionError("Publisher ZIP hash differs")
    if len({json.dumps(r["native_state"], sort_keys=True) for r in records.values()}) != 1:
        raise AssertionError("Ore/queue state differs across arms")
    for name, mode in ARMS:
        arm = records[name]
        if (arm["mode"] != mode or not arm["host_quality_pass"]
            or arm["server_thread_cpu_running_ns"] <= 0
            or arm["queue_score_add_compiled"] != 4):
            raise AssertionError(f"Missing native clock/quality/activation in {name}")
        if arm["probe"]["mode"] != mode:
            raise AssertionError(f"Wrong instrumentation mode in {name}")
        if arm["probe"]["nested_queue_events"] or arm["probe"]["nested_entry_events"]:
            raise AssertionError("Nested sampling would double-count queue CPU")

    plain_cpu = records["plain"]["server_thread_cpu_running_ns"]
    timed_cpu = records["timed_queue"]["server_thread_cpu_running_ns"]
    control = records["empty_control"]["probe"]
    timed = records["timed_queue"]["probe"]

    for label in ("queue_samples", "entry_samples"):
        a, b = control[label], timed[label]
        if min(a, b) <= 0 or abs(a - b) / max(a, b) > MAX_COUNT_RELATIVE_DIFFERENCE:
            raise AssertionError(f"Independent control/treatment {label} exposure >25% different")

    for label in ("queue", "entry"):
        n = timed[f"{label}_samples"]
        zeros = timed[f"{label}_zero_deltas"]
        if zeros / n > MAX_TIMED_ZERO_DELTA_FRACTION:
            raise AssertionError(f"{label} CPU clock cannot resolve enough events")

    measured_queue = timed["queue_cpu_ns"]
    measured_entries = timed["entry_cpu_ns"]
    if measured_entries > measured_queue or measured_queue > timed_cpu:
        raise AssertionError("Inclusive nested clocks exceed Server-thread CPU")

    raw_residual = measured_queue - measured_entries
    # Clock-read cost estimate is a *sensitivity calculation* only. The empty
    # arm's two back-to-back clock calls don't include all Mixin/aggregation
    # overhead, so neither 2x this value nor the signed residual is an exact
    # correction or a guaranteed upper/lower bound on scheduler cost.
    clock_pair_per_entry = (
        control["entry_cpu_ns"] / control["entry_samples"])
    clock_pair_per_queue = (
        control["queue_cpu_ns"] / control["queue_samples"])
    estimated_two_entry_clock_cost = 2 * clock_pair_per_entry * timed["entry_samples"]
    sensitivity_residual = raw_residual - estimated_two_entry_clock_cost
    total_cpu_ratio = abs(timed_cpu - plain_cpu) / plain_cpu
    perturbation_acceptable = total_cpu_ratio <= MAX_EVENT_CPU_PERTURBATION_FRACTION
    return {
        "diagnostic_valid": perturbation_acceptable,
        "event_parity_verified": True,
        "independent_jvm_arms": True,
        "plain_server_cpu_ns": plain_cpu,
        "empty_server_cpu_ns": records["empty_control"]["server_thread_cpu_running_ns"],
        "timed_server_cpu_ns": timed_cpu,
        "timed_queue_invocations": timed["queue_samples"],
        "timed_dequeued_entry_executions": timed["entry_samples"],
        "timed_outer_runcommandqueue_cpu_ns": measured_queue,
        "timed_inner_entry_execution_cpu_ns": measured_entries,
        "raw_queue_loop_residual_ns": raw_residual,
        "raw_queue_loop_residual_fraction_of_event_cpu": raw_residual / timed_cpu,
        "inclusive_queue_fraction_of_event_cpu": measured_queue / timed_cpu,
        "dequeued_entries_fraction_of_event_cpu": measured_entries / timed_cpu,
        "empty_control_cpu_ns_per_queue_clock_pair": clock_pair_per_queue,
        "empty_control_cpu_ns_per_entry_clock_pair": clock_pair_per_entry,
        "estimated_two_entry_clock_cost_ns": estimated_two_entry_clock_cost,
        "sensitivity_residual_minus_two_entry_clocks_ns": sensitivity_residual,
        "sensitivity_fraction_of_event_cpu": sensitivity_residual / timed_cpu,
        "timed_queue_zero_fraction": timed["queue_zero_deltas"] / timed["queue_samples"],
        "timed_entry_zero_fraction": timed["entry_zero_deltas"] / timed["entry_samples"],
        "observed_timed_vs_plain_cpu_difference_fraction": total_cpu_ratio,
        "instrumentation_perturbation_gate_pass": perturbation_acceptable,
        "decision": (
            "valid_nested_queue_cost_screen"
            if perturbation_acceptable else "inconclusive_large_instrumentation_or_host_variance"
        ),
        "limitations": (
            "The inclusive runCommandQueue timer also includes game command and"
            " world work performed by queued entries, so it is NOT exclusive"
            " scheduler CPU. The residual (outer-inner) excludes entry execution"
            " but INCLUDES nested timer reads and Mixin/aggregation overhead,"
            " plus any framework work not directly inside the entry. The"
            " two-read empty control yields an approximate clock cost but no"
            " rigorous subtraction of all instrumentation. All three arms"
            " are independent JVMs, not paired treatment/control. The extra"
            " RCON begin/end delimit a slightly wider diagnostic CPU window"
            " than earlier mining event studies; no speedup or exact avoidable"
            " overhead, CI, or Amdahl hard bound is claimed."
        ),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "diagnostic.json"
    report: dict = {
        "study": "SCHED-ATTR-023",
        "status": "started",
        "diagnostic_only": True,
        "no_causal_speedup_inference": True,
        "arms": [a for a, _ in ARMS],
        "records": {},
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        report["publisher_pack_sha256"] = verify_pack()
        for arm, mode in ARMS:
            print(f"SCHED-ATTR-023 CPU ARM {arm}", flush=True)
            report["records"][arm] = run_native(arm, mode)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report["analysis"] = interpret(report["records"])
        if not report["analysis"]["diagnostic_valid"]:
            report["status"] = "inconclusive_quality"
        else:
            report["status"] = "complete"
        print("SCHED-ATTR-023 " + report["status"].upper()
              + " " + json.dumps(report["analysis"]), flush=True)
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = repr(exc)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
