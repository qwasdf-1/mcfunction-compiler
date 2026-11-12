#!/usr/bin/env python3
"""SCHED-HOOK-004: stability-first paired Fabric-vs-compiler-off CPU experiment.

The full campaign is predeclared, not tuned based on observed results. Warm each
fresh JVM with all three native command families, then repeat fixed scoreboard
CPU qualification windows until a stable plateau or a fixed cap. Run two
consecutive timed scoreboard windows and condition-true/false controls. Twenty
fresh boots form ten balanced adjacent AB/BA pairs on one Actions runner.

SCHED-HOOK-003's load-average noise gate often failed because *our own* server
launches raised the load. This experiment retains that diagnostic, but uses
direct server-thread scheduling delay and cgroup CPU throttling as its separately
declared host-quality gate. Its result must NOT be merged statistically with 003.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import secrets
import shutil
import statistics
import subprocess
import sys
import time

from ci_compiler_off_paired import (
    BOOT_SEQUENCE,
    PAIRS,
    exact_median_interval,
    snapshot_host,
    cpu_run_delay,
)
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    COMMANDS_PER_CALL, stage_artifacts, make_fixture, setup_server_properties,
    server_tid, server_cpu_time_ns, read_score, invoke_function,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon
from mc_harness.host_gate import is_noisy

EXPERIMENT = "SCHED-HOOK-004"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
REPORT = OUT / "results.json"

JVM_ARGS = ("-Xms512M", "-Xmx2G")
PREWARM_CALLS_PER_FAMILY = 800
QUALIFICATION_CALLS = 1000
QUALIFICATION_MIN_WINDOWS = 6
QUALIFICATION_MAX_WINDOWS = 18
QUALIFICATION_TAIL_WINDOWS = 4
QUALIFICATION_MAX_REL_DEVIATION = .06
QUALIFICATION_MAX_TAIL_TREND = .04
TIMED_SCORE_CALLS = 1600
TIMED_CONTROL_CALLS = 800
SCORE_DRIFT_LIMIT = .08
MAX_RUNQUEUE_DELAY_FRACTION = .25
MAX_PAIR_DELAY_FRACTION_DIFFERENCE = .10
MAX_PAIR_LOAD_DIFFERENCE = 1.0
MIN_MATERIAL_EFFECT_PERCENT = 5.0
# Never posthoc reclassify noisy / unstable pairs: every pair is reported.
MAX_FAILED_PAIRS_FOR_DECISION = 0

WINDOWS = ("score_early", "score_late", "condition_true", "condition_false")


def quality_constants() -> dict:
    return {
        "primary_effect": "within-pair (compiler-off / Fabric-only - 1) * 100",
        "n_pairs": PAIRS,
        "boot_order": BOOT_SEQUENCE,
        "all_pairs_retained": True,
        "confidence_interval": "conservative exact >=95% order-stat median interval",
        "material_effect_percent": MIN_MATERIAL_EFFECT_PERCENT,
        "prewarm_calls_per_family": PREWARM_CALLS_PER_FAMILY,
        "qualification_calls_per_window": QUALIFICATION_CALLS,
        "qualification_min_windows": QUALIFICATION_MIN_WINDOWS,
        "qualification_max_windows": QUALIFICATION_MAX_WINDOWS,
        "qualification_tail_windows": QUALIFICATION_TAIL_WINDOWS,
        "qualification_max_relative_deviation": QUALIFICATION_MAX_REL_DEVIATION,
        "qualification_max_early_late_trend": QUALIFICATION_MAX_TAIL_TREND,
        "timed_score_calls_per_window": TIMED_SCORE_CALLS,
        "timed_control_calls_per_window": TIMED_CONTROL_CALLS,
        "max_within_boot_score_drift": SCORE_DRIFT_LIMIT,
        "max_per_window_runqueue_delay_fraction": MAX_RUNQUEUE_DELAY_FRACTION,
        "max_adjacent_pair_delay_fraction_difference": MAX_PAIR_DELAY_FRACTION_DIFFERENCE,
        "max_adjacent_pair_loadavg_difference": MAX_PAIR_LOAD_DIFFERENCE,
        "cgroup_throttle_events_allowed": 0,
        "max_failed_pairs_for_decision": MAX_FAILED_PAIRS_FOR_DECISION,
        "jfr_in_timed_windows": False,
        "notes": [
            "Warmup and qualification windows are diagnostic, not data for the primary effect.",
            "No optional arm exclusion, selective repeats, or posthoc noise filtering.",
            "Load average > number of CPUs is retained as a historical diagnostic, "
            "not the new study's quality rejection criterion.",
        ],
    }


def qualification_is_stable(values: list[float]) -> bool:
    """Only a fixed 4-window tail is tested, not the whole warmup history.

    This stopping rule is identical for both modes and must be met after at
    least six windows. It tests for a plateau but does not prove the JIT is idle.
    """
    if len(values) < QUALIFICATION_MIN_WINDOWS:
        return False
    tail = values[-QUALIFICATION_TAIL_WINDOWS:]
    center = statistics.median(tail)
    if center <= 0:
        return False
    max_deviation = max(abs(v / center - 1) for v in tail)
    trend = abs(tail[-1] / tail[0] - 1)
    return (max_deviation <= QUALIFICATION_MAX_REL_DEVIATION
            and trend <= QUALIFICATION_MAX_TAIL_TREND)


def take_cpu_window(rcon: Rcon, pid: int, tid: int,
                    family: str, calls: int, *, stage: str) -> dict:
    """Fully verify executed work; report CPU, external wait, throttling."""
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    cpu0, clock = server_cpu_time_ns(pid, tid)
    delay0 = cpu_run_delay(pid, tid)
    host0 = snapshot_host()
    wall0 = time.perf_counter_ns()
    latencies = [invoke_function(rcon, family) for _ in range(calls)]
    wall_ns = time.perf_counter_ns() - wall0
    host1 = snapshot_host()
    delay1 = cpu_run_delay(pid, tid)
    cpu1, clock1 = server_cpu_time_ns(pid, tid)
    if cpu1 <= cpu0 or clock != clock1:
        raise AssertionError(f"CPU counter invalid for {stage} {family}")
    expected = calls * COMMANDS_PER_CALL if family != "condition_false" else 0
    actual = read_score(rcon)
    if actual != expected:
        raise AssertionError(f"Integrity failure {stage} {family}: {actual} != {expected}")
    cpu_ns = cpu1 - cpu0
    waited_ns = max(0, delay1 - delay0) if delay0 is not None and delay1 is not None else None
    delay_fraction = (
        waited_ns / (waited_ns + cpu_ns)
        if waited_ns is not None else None
    )
    before_cg = host0.get("cgroup_cpu_stat", {})
    after_cg = host1.get("cgroup_cpu_stat", {})
    throttled = (after_cg["nr_throttled"] - before_cg["nr_throttled"]
                 if "nr_throttled" in before_cg and "nr_throttled" in after_cg
                 else None)
    return {
        "stage": stage, "family": family,
        "calls": calls, "source_lines": calls * COMMANDS_PER_CALL,
        "server_thread_cpu_ns": cpu_ns,
        "cpu_ns_per_source_line": cpu_ns / (calls * COMMANDS_PER_CALL),
        "server_thread_runqueue_delay_ns": waited_ns,
        "runqueue_delay_fraction": delay_fraction,
        "cgroup_nr_throttled_delta": throttled,
        "loadavg_before": host0["loadavg_1m"],
        "loadavg_after": host1["loadavg_1m"],
        "historical_loadavg_gate_failed": is_noisy(
            max(host0["loadavg_1m"], host1["loadavg_1m"]),
            host0["cpu_count"],
        ),
        "wall_seconds": wall_ns / 1e9,
        "rcon_median_ms": statistics.median(latencies),
        "cpu_clock": clock,
        "final_score": actual,
        "expected_score": expected,
        "exact_work": True,
    }


def warmup_server(rcon: Rcon, pid: int, tid: int) -> dict:
    """Prewarm all shared execution paths before score plateau qualification."""
    prewarm = []
    for family in ("condition_true", "condition_false", "score"):
        rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        for _ in range(PREWARM_CALLS_PER_FAMILY):
            invoke_function(rcon, family)
        score = read_score(rcon)
        expected = (PREWARM_CALLS_PER_FAMILY * COMMANDS_PER_CALL
                    if family != "condition_false" else 0)
        if score != expected:
            raise AssertionError(f"Prewarm exact-work failure {family}: {score} != {expected}")
        prewarm.append({"family": family, "calls": PREWARM_CALLS_PER_FAMILY,
                        "score": score})
    qualification = []
    values = []
    for n in range(QUALIFICATION_MAX_WINDOWS):
        window = take_cpu_window(
            rcon, pid, tid, "score", QUALIFICATION_CALLS,
            stage=f"qualification_{n+1}",
        )
        qualification.append(window)
        values.append(window["cpu_ns_per_source_line"])
        if qualification_is_stable(values):
            break
    qualified = qualification_is_stable(values)
    tail = values[-QUALIFICATION_TAIL_WINDOWS:]
    print(
        f"WARMUP windows={len(values)} stable={qualified} "
        f"tail_cpu_ns_per_line={[round(v, 2) for v in tail]}",
        flush=True,
    )
    return {
        "prewarm": prewarm,
        "qualification": qualification,
        "windows_needed": len(qualification),
        "qualification_stable": qualified,
        "qualification_tail": tail,
    }


def run_boot(index: int, mode: str, artifacts: dict) -> dict:
    workdir = RUN_ROOT / f"ci-stable-hooks-{index:02d}-{mode}"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(FABRIC_BASE, workdir)
    mods = workdir / "mods"
    mods.mkdir(exist_ok=True)
    api = Path(artifacts["api"])
    shutil.copy2(api, mods / api.name)
    if mode == "compiler":
        compiler = Path(artifacts["compiler"])
        shutil.copy2(compiler, mods / compiler.name)
    make_fixture(workdir)
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    setup_server_properties(workdir, port, rcon_port, password)

    env = dict(os.environ)
    for flag in (
        "FC_WRAPPER_PROBE", "FC_SCORE_ADD_PROTOTYPE", "FC_SCORE_ADD_METRICS",
        "FC_SCORE_ADD_TIMING", "FC_FUSED_REGION_PROTOTYPE",
        "FC_BYTECODE_REGION_PROTOTYPE", "FC_SELECTIVE_MACRO_ARGUMENTS",
        "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS",
        "FC_COMMAND_CALLBACK_METRICS", "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES",
        "FC_FUNCTION_TIMING", "FC_RUNTIME_TRACE", "FC_SCHEDULER_RESEARCH",
    ):
        env[flag] = "false"
    command = [
        "java", *JVM_ARGS, "-jar",
        str(workdir / "fabric-server-launch.jar"), "nogui",
    ]
    result = {"boot": index, "mode": mode, "status": "started",
              "host_at_boot": snapshot_host(), "timed_windows": []}
    logpath = OUT / f"boot-{index:02d}-{mode}.log"
    print(f"BOOT {index+1}/{len(BOOT_SEQUENCE)} {mode} "
          f"starting at load={result['host_at_boot']['loadavg_1m']}",
          flush=True)
    with logpath.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, cwd=workdir, env=env, stdin=subprocess.PIPE,
            stdout=log, stderr=subprocess.STDOUT,
        )
        rcon: Rcon | None = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=180)
            if PACK not in rcon.command("datapack list enabled"):
                raise AssertionError("Native benchmark pack not loaded")
            status = rcon.command("functioncompiler status")
            if mode == "compiler":
                if "wrapped=false" not in status:
                    raise AssertionError(f"Compiler wrapper not off: {status!r}")
                result["compiler_status"] = status
            elif "FC_PROBE" in status:
                raise AssertionError("Compiler unexpectedly installed in reference arm")
            for cmd in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1",
            ):
                rcon.command(cmd)
            pid, tid = process.pid, server_tid(process.pid)
            result["warmup"] = warmup_server(rcon, pid, tid)
            # Score windows are adjacent: controls cannot confound the JIT
            # progression between score_early and score_late.
            for index_in_boot, name in enumerate(WINDOWS):
                family = ("score" if name.startswith("score") else name)
                calls = TIMED_SCORE_CALLS if family == "score" else TIMED_CONTROL_CALLS
                w = take_cpu_window(
                    rcon, pid, tid, family, calls,
                    stage=name,
                )
                result["timed_windows"].append(w)
                print(
                    f"MEASURE boot={index} mode={mode} {name} "
                    f"cpu_ns/line={w['cpu_ns_per_source_line']:.2f} "
                    f"runqueue={w['runqueue_delay_fraction']:.3f} "
                    f"throttled={w['cgroup_nr_throttled_delta']}",
                    flush=True,
                )
            score_windows = result["timed_windows"][:2]
            score_values = [w["cpu_ns_per_source_line"] for w in score_windows]
            result["score_cpu_ns_per_line"] = statistics.mean(score_values)
            result["score_within_boot_drift"] = abs(
                score_values[1] / score_values[0] - 1.0
            )
            timed_delays = [w["runqueue_delay_fraction"] for w in score_windows]
            result["mean_score_runqueue_delay_fraction"] = (
                statistics.mean(timed_delays) if all(v is not None for v in timed_delays)
                else None
            )
            result["boot_quality"] = {
                "qualification_stable": result["warmup"]["qualification_stable"],
                "timed_score_drift_passed":
                    result["score_within_boot_drift"] <= SCORE_DRIFT_LIMIT,
                "thread_wait_passed": all(
                    v is not None and v <= MAX_RUNQUEUE_DELAY_FRACTION
                    for v in timed_delays
                ),
                "cpu_throttling_passed": all(
                    w["cgroup_nr_throttled_delta"] == 0 for w in score_windows
                ),
                "historical_loadavg_noisy": any(
                    w["historical_loadavg_gate_failed"] for w in score_windows
                ),
            }
            result["boot_quality"]["passed"] = all(
                v for k, v in result["boot_quality"].items()
                if k not in ("passed", "historical_loadavg_noisy")
            )
            result["host_after_boot"] = snapshot_host()
            result["status"] = "complete"
            print(
                f"BOOT_RESULT {index} {mode} cpu_ns/line="
                f"{result['score_cpu_ns_per_line']:.2f} "
                f"stable={result['warmup']['qualification_stable']} "
                f"drift={100*result['score_within_boot_drift']:.1f}% "
                f"quality={result['boot_quality']['passed']}",
                flush=True,
            )
        finally:
            if rcon is not None:
                try:
                    rcon.command("stop")
                except (OSError, RuntimeError):
                    pass
                rcon.close()
            try:
                process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return result


def analyze(boots: list[dict]) -> dict:
    if len(boots) != len(BOOT_SEQUENCE):
        raise AssertionError("Incomplete campaign")
    pairs = []
    for i in range(PAIRS):
        arms = boots[i*2:i*2+2]
        by_mode = {item["mode"]: item for item in arms}
        if set(by_mode) != {"fabric", "compiler"}:
            raise AssertionError(f"Invalid pair {i}: {arms}")
        f, c = by_mode["fabric"], by_mode["compiler"]
        load_diff = abs(
            f["host_at_boot"]["loadavg_1m"] -
            c["host_at_boot"]["loadavg_1m"]
        )
        delay_f = f["mean_score_runqueue_delay_fraction"]
        delay_c = c["mean_score_runqueue_delay_fraction"]
        delay_diff = (
            abs(delay_f - delay_c)
            if delay_f is not None and delay_c is not None else None
        )
        passed = (
            f["boot_quality"]["passed"]
            and c["boot_quality"]["passed"]
            and load_diff <= MAX_PAIR_LOAD_DIFFERENCE
            and delay_diff is not None
            and delay_diff <= MAX_PAIR_DELAY_FRACTION_DIFFERENCE
        )
        pairs.append({
            "pair": i+1,
            "order": [item["mode"] for item in arms],
            "fabric_ns_per_line": f["score_cpu_ns_per_line"],
            "compiler_off_ns_per_line": c["score_cpu_ns_per_line"],
            "cpu_difference_percent": 100 * (
                c["score_cpu_ns_per_line"] /
                f["score_cpu_ns_per_line"] - 1
            ),
            "qualifying_load_difference": load_diff,
            "runqueue_delay_fraction_difference": delay_diff,
            "quality_passed": passed,
        })
    changes = [p["cpu_difference_percent"] for p in pairs]
    ci = exact_median_interval(changes)
    bad = [p["pair"] for p in pairs if not p["quality_passed"]]
    if len(bad) > MAX_FAILED_PAIRS_FOR_DECISION:
        verdict = "inconclusive_quality_gate"
    elif ci["lower"] > MIN_MATERIAL_EFFECT_PERCENT:
        verdict = "regression_above_5_percent_supported"
    elif ci["upper"] < -MIN_MATERIAL_EFFECT_PERCENT:
        verdict = "improvement_above_5_percent_supported"
    elif ci["lower"] >= -MIN_MATERIAL_EFFECT_PERCENT and ci["upper"] <= MIN_MATERIAL_EFFECT_PERCENT:
        verdict = "within_5_percent_equivalence_band"
    else:
        verdict = "inconclusive_effect_interval"
    return {
        "pairs": pairs,
        "primary": {
            "median_paired_percent": statistics.median(changes),
            "paired_percent_changes": changes,
            "exact_interval": ci,
            "median_fabric_ns_per_line": statistics.median(
                b["score_cpu_ns_per_line"] for b in boots if b["mode"] == "fabric"
            ),
            "median_compiler_off_ns_per_line": statistics.median(
                b["score_cpu_ns_per_line"] for b in boots if b["mode"] == "compiler"
            ),
        },
        "warmup": {
            "qualified_boots": sum(
                b["warmup"]["qualification_stable"] for b in boots
            ),
            "boots_total": len(boots),
            "qualification_window_counts": [
                b["warmup"]["windows_needed"] for b in boots
            ],
            "median_early_late_score_drift_percent": statistics.median(
                100*b["score_within_boot_drift"] for b in boots
            ),
        },
        "quality": {
            "passing_pairs": PAIRS-len(bad),
            "failed_pair_ids": bad,
            "all_quality_gates_passed": not bad,
            "legacy_loadavg_noisy_boots": [
                b["boot"] for b in boots
                if b["boot_quality"]["historical_loadavg_noisy"]
            ],
        },
        "verdict": verdict,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts = stage_artifacts()
    record = {
        "experiment": EXPERIMENT,
        "status": "started",
        "declarations": quality_constants(),
        "artifact_hashes": {
            k:v for k,v in artifacts.items() if k.endswith("_sha256")
        },
        "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    try:
        for idx, mode in enumerate(BOOT_SEQUENCE):
            boot = run_boot(idx, mode, artifacts)
            record["boots"].append(boot)
            REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
            if idx%2 == 1:
                a,b = record["boots"][-2:]
                f = a if a["mode"] == "fabric" else b
                c = a if a["mode"] == "compiler" else b
                print(
                    f"PAIR {idx//2+1}/{PAIRS} delta="
                    f"{100*(c['score_cpu_ns_per_line']/f['score_cpu_ns_per_line']-1):+.2f}% "
                    f"qualified={f['boot_quality']['passed'] and c['boot_quality']['passed']}",
                    flush=True,
                )
        record["analysis"] = analyze(record["boots"])
        record["status"] = "complete"
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        print("SCHED-HOOK-004 COMPLETE "+json.dumps(record["analysis"]), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["failure"] = repr(exc)
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
