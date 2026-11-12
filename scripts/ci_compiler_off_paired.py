#!/usr/bin/env python3
"""SCHED-HOOK-003: counterbalanced, paired, production-server hook cost study.

Primary question: does merely installing the function compiler (all optimizers
OFF) increase the server-thread CPU time of vanilla scoreboard functions,
relative to an otherwise identical Fabric API server?

Predeclared: five ABBA/BAAB blocks, ten adjacent A/B pairs, same GitHub host,
each boot gets two score measurements bracketing two conditional controls,
warmup 300 / measured 1600 calls per function, 2000 commands per call.
JFR is OFF throughout the campaign. Every result retained; failures and noisy
pairs are never silently discarded. This is a research screening/confirmation
attempt, not a production promotion benchmark.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, OBJECTIVE, HOLDER, GATE, COMMANDS_PER_CALL,
    FABRIC_BASE, stage_artifacts, make_fixture, setup_server_properties,
    server_tid, server_cpu_time_ns, read_score, invoke_function,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon
from mc_harness.host_gate import is_noisy

OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-HOOK-003"
REPORT = OUTPUT / "results.json"
BLOCK_ORDERS = (
    ("fabric", "compiler", "compiler", "fabric"),
    ("compiler", "fabric", "fabric", "compiler"),
    ("fabric", "compiler", "compiler", "fabric"),
    ("compiler", "fabric", "fabric", "compiler"),
    ("fabric", "compiler", "compiler", "fabric"),
)
BOOT_SEQUENCE = tuple(mode for block in BLOCK_ORDERS for mode in block)
PAIRS = 10
WARMUP_CALLS = 300
MEASURED_CALLS = 1600
JVM_ARGS = ("-Xms512M", "-Xmx2G")
MAX_WITHIN_BOOT_SCORE_DRIFT_PERCENT = 12.0
MAX_PAIR_LOAD_DIFFERENCE = 1.0
MAX_PAIR_REFERENCE_DRIFT_PERCENT = 20.0
CPU_REGRESSION_THRESHOLD_PERCENT = 5.0
MAX_NOISY_PAIR_COUNT = 0
QUIET_HOST_SETTLE_SECONDS = 25.0
FAMILIES = ("score", "condition_true", "condition_false")
WINDOW_ORDER = ("score", "condition_true", "condition_false", "score")
ROOT.mkdir(parents=True, exist_ok=True)


def snapshot_host() -> dict:
    """Record contention measures, including cgroup CPU throttling if exposed."""
    data = {"loadavg_1m": round(os.getloadavg()[0], 3),
            "cpu_count": os.cpu_count() or 1}
    data["host_load_noisy"] = is_noisy(data["loadavg_1m"], data["cpu_count"])
    cg = Path("/sys/fs/cgroup/cpu.stat")
    if cg.is_file():
        counters = {}
        for line in cg.read_text().splitlines():
            fields = line.split()
            if len(fields) == 2:
                try:
                    counters[fields[0]] = int(fields[1])
                except ValueError:
                    continue
        data["cgroup_cpu_stat"] = counters
    cpu_pressure = Path("/proc/pressure/cpu")
    if cpu_pressure.exists():
        data["cpu_pressure"] = cpu_pressure.read_text().strip()
    return data


def cpu_run_delay(pid: int, tid: int) -> int | None:
    p = Path(f"/proc/{pid}/task/{tid}/schedstat")
    if not p.exists():
        return None
    fields = p.read_text().split()
    return int(fields[1]) if len(fields) > 1 else None


def measure_window(rcon: Rcon, pid: int, tid: int, family: str) -> dict:
    """Measure one native command family with exact final-score verification."""
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    for _ in range(WARMUP_CALLS):
        invoke_function(rcon, family)
    expected_warmup = (WARMUP_CALLS * COMMANDS_PER_CALL
                       if family != "condition_false" else 0)
    if read_score(rcon) != expected_warmup:
        raise AssertionError(f"Warmup integrity failure: {family}")

    host_before = snapshot_host()
    run_delay_before = cpu_run_delay(pid, tid)
    cpu_before, clock = server_cpu_time_ns(pid, tid)
    wall_before = time.perf_counter_ns()
    timings = [invoke_function(rcon, family) for _ in range(MEASURED_CALLS)]
    wall_elapsed_ns = time.perf_counter_ns() - wall_before
    cpu_after, clock_after = server_cpu_time_ns(pid, tid)
    run_delay_after = cpu_run_delay(pid, tid)
    host_after = snapshot_host()
    if clock != clock_after or cpu_after < cpu_before:
        raise AssertionError(f"Invalid server thread CPU clock: {clock, clock_after}")
    expected = ((WARMUP_CALLS + MEASURED_CALLS) * COMMANDS_PER_CALL
                if family != "condition_false" else 0)
    actual = read_score(rcon)
    if actual != expected:
        raise AssertionError(f"Command integrity failure: {family}; "
                             f"expected {expected}, got {actual}")
    cpu_ns = cpu_after - cpu_before
    cg0 = host_before.get("cgroup_cpu_stat", {})
    cg1 = host_after.get("cgroup_cpu_stat", {})
    cgroup_delta = {key: cg1[key] - value for key, value in cg0.items()
                    if key in cg1}
    lines = COMMANDS_PER_CALL * MEASURED_CALLS
    return {
        "family": family,
        "cpu_ns": cpu_ns,
        "cpu_ns_per_source_line": cpu_ns / lines,
        "measured_calls": MEASURED_CALLS,
        "measured_source_lines": lines,
        "rcon_median_ms": round(statistics.median(timings), 5),
        "rcon_p95_ms": round(sorted(timings)[int(.95 * (len(timings)-1))], 5),
        "wall_time_seconds": wall_elapsed_ns / 1e9,
        "cpu_clock": clock,
        "server_thread_runqueue_delay_ns": (
            run_delay_after - run_delay_before
            if run_delay_before is not None and run_delay_after is not None
            else None
        ),
        "cgroup_cpu_stat_delta": cgroup_delta,
        "loadavg_before": host_before["loadavg_1m"],
        "loadavg_after": host_after["loadavg_1m"],
        "host_noisy": host_before["host_load_noisy"] or host_after["host_load_noisy"],
        "expected_score": expected,
        "final_score": actual,
        "exact_workload": True,
    }


def start_boot(boot: int, mode: str, artifacts: dict) -> dict:
    """Run one fresh JVM, matching all JVM args, datapacks and Fabric API bits."""
    workdir = RUN_ROOT / f"ci-paired-hooks-{boot:02d}-{mode}"
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
    password = __import__("secrets").token_hex(20)
    setup_server_properties(workdir, port, rcon_port, password)
    cmd = ["java", *JVM_ARGS, "-jar",
           str(workdir / "fabric-server-launch.jar"), "nogui"]
    env = dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES": "false",
        "FC_FUNCTION_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHEDULER_RESEARCH": "false",
    })
    log_file = OUTPUT / f"boot-{boot:02d}-{mode}.log"
    result = {"boot": boot, "mode": mode, "status": "started",
              "windows": [], "host_before_boot": snapshot_host()}
    print(f"BOOT {boot:02d}/{len(BOOT_SEQUENCE)-1:02d} mode={mode} "
          f"load={result['host_before_boot']['loadavg_1m']}", flush=True)
    with log_file.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=workdir, env=env,
                                   stdin=subprocess.PIPE, stdout=log,
                                   stderr=subprocess.STDOUT)
        rcon = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=180)
            enabled = rcon.command("datapack list enabled")
            if "fc_sched_cross_mode" not in enabled:
                raise AssertionError("Generated benchmark datapack not enabled")
            status = rcon.command("functioncompiler status")
            if mode == "compiler":
                if "wrapped=false" not in status:
                    raise AssertionError(f"Compiler wrapper unexpectedly enabled: {status!r}")
                result["compiler_status"] = status
            elif "FC_PROBE" in status:
                raise AssertionError("Compiler command found in baseline Fabric-only arm")
            for key, value in (
                (f"scoreboard objectives add {OBJECTIVE} dummy", None),
                (f"scoreboard players set {HOLDER} {OBJECTIVE} 0", None),
                (f"scoreboard players set {GATE} {OBJECTIVE} 1", None),
            ):
                rcon.command(key)
            pid, tid = process.pid, server_tid(process.pid)
            # Idle control: record, don't subtract, since background work
            # may vary under active workload.
            t0 = time.perf_counter_ns()
            c0 = server_cpu_time_ns(pid, tid)[0]
            time.sleep(1.25)
            result["idle_cpu_ns_per_second"] = (
                (server_cpu_time_ns(pid, tid)[0] - c0) /
                ((time.perf_counter_ns() - t0) / 1e9)
            )
            for index, family in enumerate(WINDOW_ORDER):
                window = measure_window(rcon, pid, tid, family)
                window["ordinal"] = index
                result["windows"].append(window)
                print(f"MEASURE boot={boot} mode={mode} family={family} "
                      f"ordinal={index} cpu_ns/line="
                      f"{window['cpu_ns_per_source_line']:.2f} "
                      f"noisy={window['host_noisy']} exact=true", flush=True)
            score_windows = [w for w in result["windows"] if w["family"] == "score"]
            a, b = [w["cpu_ns_per_source_line"] for w in score_windows]
            result["score_cpu_ns_per_line"] = (a + b) / 2.0
            result["within_boot_score_drift_percent"] = (
                100.0 * (b - a) / ((a + b) / 2.0)
            )
            result["conditional_true_cpu_ns_per_line"] = next(
                w["cpu_ns_per_source_line"] for w in result["windows"]
                if w["family"] == "condition_true"
            )
            result["conditional_false_cpu_ns_per_line"] = next(
                w["cpu_ns_per_source_line"] for w in result["windows"]
                if w["family"] == "condition_false"
            )
            result["host_after_boot"] = snapshot_host()
            result["any_noisy_window"] = any(w["host_noisy"] for w in result["windows"])
            result["status"] = "complete"
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


def exact_median_interval(values: list[float], coverage: float = .95) -> dict:
    """Distribution-free two-sided exact binomial CI for population median.

    Rank-based interval: smallest index k for which conservative coverage
    1 - 2*P[Binomial(n,.5) <= k-1] reaches the declared threshold.
    n=10 -> second through ninth ordered values (97.85% coverage).
    """
    vals = sorted(values)
    n = len(vals)
    valid = []
    for k in range(1, n // 2 + 1):
        tail = sum(math.comb(n, i) for i in range(k)) / 2**n
        prob = 1.0 - 2.0*tail
        if prob >= coverage:
            valid.append((k, prob))
    if not valid:
        return {"lower": vals[0], "upper": vals[-1],
                "coverage": 1.0 - 2 / 2**n, "order_stats": [1, n]}
    k, achieved = valid[-1]
    return {"lower": vals[k-1], "upper": vals[n-k],
            "coverage": achieved, "order_stats": [k, n-k+1]}


def evaluate_pairs(boots: list[dict]) -> dict:
    if len(boots) != len(BOOT_SEQUENCE):
        raise AssertionError("Partial boots cannot be scored as a full campaign")
    pairs = []
    for p in range(PAIRS):
        group = boots[p*2:p*2+2]
        by_mode = {a["mode"]: a for a in group}
        if set(by_mode) != {"compiler", "fabric"}:
            raise AssertionError(f"Unpaired arms in pair {p}: {list(by_mode)}")
        a, b = by_mode["fabric"], by_mode["compiler"]
        data = {
            "pair": p,
            "order": [arm["mode"] for arm in group],
            "fabric_score_cpu_ns_per_line": a["score_cpu_ns_per_line"],
            "compiler_score_cpu_ns_per_line": b["score_cpu_ns_per_line"],
            "score_delta_percent": 100*(b["score_cpu_ns_per_line"] /
                                       a["score_cpu_ns_per_line"] - 1.0),
            "condition_true_delta_percent": 100*(
                b["conditional_true_cpu_ns_per_line"] /
                a["conditional_true_cpu_ns_per_line"]-1.0),
            "condition_false_delta_percent": 100*(
                b["conditional_false_cpu_ns_per_line"] /
                a["conditional_false_cpu_ns_per_line"]-1.0),
            "load_difference": abs(a["host_before_boot"]["loadavg_1m"] -
                                   b["host_before_boot"]["loadavg_1m"]),
            "both_arms_quiet": not (a["any_noisy_window"] or b["any_noisy_window"]),
            "within_boot_drift_max_percent": max(
                abs(a["within_boot_score_drift_percent"]),
                abs(b["within_boot_score_drift_percent"]),
            ),
        }
        data["quality_passed"] = (
            data["both_arms_quiet"]
            and data["load_difference"] <= MAX_PAIR_LOAD_DIFFERENCE
            and data["within_boot_drift_max_percent"] <= MAX_WITHIN_BOOT_SCORE_DRIFT_PERCENT
        )
        pairs.append(data)
    changes = [p["score_delta_percent"] for p in pairs]
    ci = exact_median_interval(changes)
    noisy = [p["pair"] for p in pairs if not p["quality_passed"]]
    all_quiet = len(noisy) <= MAX_NOISY_PAIR_COUNT
    # The outcome is declared using *all* ten pairs. Never discard noisy
    # values, choose good windows or re-run until statistical significance.
    if not all_quiet:
        verdict = "inconclusive_host_or_stability_gate"
    elif ci["lower"] > CPU_REGRESSION_THRESHOLD_PERCENT:
        verdict = "compiler_off_regression_above_5_percent_supported"
    elif ci["upper"] < -CPU_REGRESSION_THRESHOLD_PERCENT:
        verdict = "compiler_off_faster_above_5_percent_supported"
    elif ci["lower"] >= -CPU_REGRESSION_THRESHOLD_PERCENT and ci["upper"] <= CPU_REGRESSION_THRESHOLD_PERCENT:
        verdict = "within_predeclared_5_percent_equivalence_band"
    else:
        verdict = "inconclusive_effect_interval"
    return {
        "pairs": pairs,
        "primary": {
            "n_pairs": PAIRS, "per_pair_score_delta_percent": changes,
            "median_score_delta_percent": statistics.median(changes),
            "exact_median_interval": ci,
            "threshold_percent": CPU_REGRESSION_THRESHOLD_PERCENT,
            "median_fabric_cpu_ns_per_line": statistics.median(
                b["score_cpu_ns_per_line"] for b in boots if b["mode"] == "fabric"
            ),
            "median_compiler_cpu_ns_per_line": statistics.median(
                b["score_cpu_ns_per_line"] for b in boots if b["mode"] == "compiler"
            ),
        },
        "secondary": {
            name: {
                "median_paired_delta_percent": statistics.median(
                    p[name] for p in pairs
                ),
                "exact_median_interval": exact_median_interval(
                    [p[name] for p in pairs]
                )
            }
            for name in ("condition_true_delta_percent",
                         "condition_false_delta_percent")
        },
        "quality_gate": {
            "host_quiet_requirement": "all 10 pairs",
            "noisy_or_unstable_pair_ids": noisy,
            "quality_passed": all_quiet,
            "max_load_difference": MAX_PAIR_LOAD_DIFFERENCE,
            "max_within_boot_score_drift_percent": MAX_WITHIN_BOOT_SCORE_DRIFT_PERCENT,
        },
        "verdict": verdict,
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    artifacts = stage_artifacts()
    record: dict = {
        "experiment": "SCHED-HOOK-003",
        "status": "started",
        "declared_before_measurement": {
            "question": "CPU overhead attributable to installing the disabled compiler on Fabric API",
            "mode_order": BOOT_SEQUENCE,
            "blocks": BLOCK_ORDERS,
            "windows_per_boot": WINDOW_ORDER,
            "warmup_calls_per_window": WARMUP_CALLS,
            "measured_calls_per_window": MEASURED_CALLS,
            "lines_per_function": COMMANDS_PER_CALL,
            "jfr_in_timing": False,
            "primary_metric": "server-thread CPU ns per native scoreboard source line; "
                              "mean of two windows per boot",
            "primary_effect": "paired percentage change compiler-off vs Fabric-only",
            "primary_interval": "two-sided conservative exact 95%+ median order-stat interval",
            "minimum_material_regression_percent": CPU_REGRESSION_THRESHOLD_PERCENT,
            "quality_gate_max_noisy_pairs": MAX_NOISY_PAIR_COUNT,
            "quality_gate_max_pair_load_diff": MAX_PAIR_LOAD_DIFFERENCE,
            "quality_gate_max_within_boot_drift_percent": MAX_WITHIN_BOOT_SCORE_DRIFT_PERCENT,
            "screening": True,
        },
        "artifact_hashes": {k:v for k,v in artifacts.items() if k.endswith("_sha256")},
        "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    try:
        for boot, mode in enumerate(BOOT_SEQUENCE):
            # Fresh dedicated world per boot, but both arms of each pair
            # share host, Minecraft/Fabric/API bits and JVM settings.
            item = start_boot(boot, mode, artifacts)
            record["boots"].append(item)
            REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
            if boot % 2 == 1:
                pair = record["boots"][-2:]
                by_mode = {z["mode"]: z for z in pair}
                a = by_mode["fabric"]["score_cpu_ns_per_line"]
                b = by_mode["compiler"]["score_cpu_ns_per_line"]
                print(f"PAIR {boot//2+1}/{PAIRS} delta="
                      f"{100*(b/a-1):+.2f}% fabric={a:.2f} compiler={b:.2f}"
                      f" noisy={any(z['any_noisy_window'] for z in pair)}",
                      flush=True)
        record["analysis"] = evaluate_pairs(record["boots"])
        record["status"] = "complete"
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        print("SCHED-HOOK-003 FINISHED "+json.dumps({
            "verdict": record["analysis"]["verdict"],
            "median_percent": record["analysis"]["primary"]["median_score_delta_percent"],
            "exact_interval": record["analysis"]["primary"]["exact_median_interval"],
            "quality": record["analysis"]["quality_gate"],
        }), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["failure"] = repr(exc)
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
