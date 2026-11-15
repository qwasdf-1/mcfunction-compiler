#!/usr/bin/env python3
"""SCHED-BENCH-008: single-JVM crossover sensitivity (not a compiler A/B).

Each of 12 independently booted Fabric-only servers executes BOTH comparisons:
A vs identical N, and A vs a conditional-command treatment B. Each block uses
ABBA or BAAB windows, cancelling first-order linear time drift. Boot is the
independent analysis unit; within-boot windows must NEVER be treated as 48
independent observations. All measurements remain GC-inclusive.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import secrets
import shutil
import statistics
import subprocess
import time

import ci_compiler_off_stability as stable
from ci_compiler_off_paired import exact_median_interval
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    COMMANDS_PER_CALL, stage_artifacts, make_fixture, setup_server_properties,
    server_tid, read_score, invoke_function,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon
from benchmark_noise_telemetry import snapshot_jvm_environment, delta_environment

EXPERIMENT = "SCHED-BENCH-008"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
REPORT = OUT / "results.json"
SEED = 8008
N_BOOTS = 12
PERTURBED_LINES = 300
PREWARM_PER_FUNCTION = 500
MEASURED_CALLS_PER_WINDOW = 800
WINDOWS_PER_BOOT = 8
assert 0 < PERTURBED_LINES < COMMANDS_PER_CALL


def schedule() -> tuple[dict, ...]:
    rng = random.Random(SEED)
    # Exact balance: half of the boots use each block order, and both ABBA
    # orientations appear six times per control. Randomization is seeded.
    block_orders = rng.sample(["negative_first", "positive_first"] * (N_BOOTS//2), N_BOOTS)
    negative = rng.sample(["ABBA", "BAAB"] * (N_BOOTS//2), N_BOOTS)
    positive = rng.sample(["ABBA", "BAAB"] * (N_BOOTS//2), N_BOOTS)
    plans = []
    for i in range(N_BOOTS):
        blocks = []
        for kind in (("negative", "positive") if block_orders[i] == "negative_first"
                     else ("positive", "negative")):
            orientation = negative[i] if kind == "negative" else positive[i]
            names = {"A": "score_a", "B": "score_null" if kind == "negative"
                     else "score_treatment"}
            blocks.append({
                "kind": kind, "orientation": orientation,
                "functions": [names[ch] for ch in orientation],
            })
        plans.append({"boot": i, "blocks": blocks})
    return tuple(plans)


def make_crossover_fixture(workdir: Path) -> None:
    make_fixture(workdir)
    function_dir = workdir / "world" / "datapacks" / PACK / "data" / PACK / "function"
    baseline = (function_dir / "score.mcfunction").read_text(encoding="utf-8").splitlines()
    if len(baseline) != COMMANDS_PER_CALL:
        raise AssertionError("Baseline function line count changed")
    (function_dir / "score_a.mcfunction").write_text(
        "\n".join(baseline)+"\n", encoding="utf-8")
    (function_dir / "score_null.mcfunction").write_text(
        "\n".join(baseline)+"\n", encoding="utf-8")
    treatment = baseline.copy()
    for j in range(PERTURBED_LINES):
        treatment[j] = (f"execute if score {GATE} {OBJECTIVE} matches 1 run "
                        f"scoreboard players add {HOLDER} {OBJECTIVE} 1")
    (function_dir / "score_treatment.mcfunction").write_text(
        "\n".join(treatment)+"\n", encoding="utf-8")


def score_warmup(rcon: Rcon) -> list[dict]:
    observations = []
    for name in ("score_a", "score_null", "score_treatment"):
        rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        for _ in range(PREWARM_PER_FUNCTION):
            invoke_function(rcon, name)
        score = read_score(rcon)
        expected = PREWARM_PER_FUNCTION * COMMANDS_PER_CALL
        if score != expected:
            raise AssertionError(f"{name} prewarm parity: {score} vs {expected}")
        observations.append({"function": name, "calls": PREWARM_PER_FUNCTION,
                             "final_score": score})
    return observations


def measured_window(rcon: Rcon, pid: int, tid: int, family: str, ordinal: int) -> dict:
    before = snapshot_jvm_environment(pid)
    result = stable.take_cpu_window(
        rcon, pid, tid, family, MEASURED_CALLS_PER_WINDOW,
        stage=f"crossover_{ordinal:02d}",
    )
    after = snapshot_jvm_environment(pid)
    result["ordinal"] = ordinal
    result["noise_telemetry"] = delta_environment(before, after)
    return result


def run_boot(index: int, plan: dict, artifacts: dict) -> dict:
    workdir = RUN_ROOT / f"ci-bench008-{index:02d}-fabric"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(FABRIC_BASE, workdir)
    mods = workdir / "mods"
    mods.mkdir(exist_ok=True)
    api = Path(artifacts["api"])
    shutil.copy2(api, mods / api.name)
    make_crossover_fixture(workdir)
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    setup_server_properties(workdir, port, rcon_port, password)

    env = dict(os.environ)
    for flag in (
        "FC_WRAPPER_PROBE", "FC_SCORE_ADD_PROTOTYPE", "FC_SCORE_ADD_METRICS",
        "FC_SCORE_ADD_TIMING", "FC_FUSED_REGION_PROTOTYPE", "FC_BYTECODE_REGION_PROTOTYPE",
        "FC_SELECTIVE_MACRO_ARGUMENTS", "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS",
        "FC_COMMAND_CALLBACK_METRICS", "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES",
        "FC_FUNCTION_TIMING", "FC_RUNTIME_TRACE", "FC_SCHEDULER_RESEARCH",
    ):
        env[flag] = "false"
    command = ["java", *stable.JVM_ARGS, "-jar",
               str(workdir / "fabric-server-launch.jar"), "nogui"]
    boot = {"index": index, "plan": plan, "status": "started",
            "host_at_boot": stable.snapshot_host(), "blocks": []}
    logpath = OUT / f"boot-{index:02d}-fabric.log"
    print(f"BOOT {index+1}/{N_BOOTS} single JVM", flush=True)
    with logpath.open("w", encoding="utf-8") as logfile:
        process = subprocess.Popen(command, cwd=workdir, env=env,
                                   stdin=subprocess.PIPE, stdout=logfile,
                                   stderr=subprocess.STDOUT)
        rcon = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=180)
            if PACK not in rcon.command("datapack list enabled"):
                raise AssertionError("Crossover datapack not loaded")
            if "FC_PROBE" in rcon.command("functioncompiler status"):
                raise AssertionError("Unexpected compiler in Fabric-only control")
            for cmd in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1",
            ):
                rcon.command(cmd)
            pid, tid = process.pid, server_tid(process.pid)
            boot["family_prewarm"] = score_warmup(rcon)
            boot["qualification"] = stable.warmup_server(rcon, pid, tid)
            ordinal = 0
            for block in plan["blocks"]:
                measured = {"kind": block["kind"],
                            "orientation": block["orientation"], "windows": []}
                # The four windows are the complete crossover block, in
                # predeclared order. Never remove an individual noisy window.
                for family in block["functions"]:
                    result = measured_window(rcon, pid, tid, family, ordinal)
                    measured["windows"].append(result)
                    print(f"WINDOW boot={index} block={block['kind']} "
                          f"ord={ordinal} family={family} ns/line="
                          f"{result['cpu_ns_per_source_line']:.2f}", flush=True)
                    ordinal += 1
                boot["blocks"].append(measured)
            boot["status"] = "complete"
            boot["host_after_boot"] = stable.snapshot_host()
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
    return boot


def block_contrast(block: dict) -> float:
    windows = block["windows"]
    if len(windows) != 4 or block["orientation"] not in ("ABBA", "BAAB"):
        raise AssertionError("Incomplete or invalid crossover block")
    # Mean logs = log(geometric mean); two observations per arm.
    names = ["A" if w["family"] == "score_a" else "B" for w in windows]
    if "".join(names) != block["orientation"]:
        raise AssertionError("Observed functions differ from predeclared block")
    a = [math.log(w["cpu_ns_per_source_line"]) for w in windows if w["family"] == "score_a"]
    b = [math.log(w["cpu_ns_per_source_line"]) for w in windows if w["family"] != "score_a"]
    if len(a) != 2 or len(b) != 2:
        raise AssertionError("Not two windows per arm")
    return 100 * (statistics.mean(b) - statistics.mean(a))


def analyze(boots: list[dict]) -> dict:
    if len(boots) != N_BOOTS:
        raise AssertionError("Incomplete campaign: independent unit is boot")
    per_boot = []
    for index, boot in enumerate(boots):
        if boot["index"] != index or boot["status"] != "complete":
            raise AssertionError("Incomplete or reordered JVM boot")
        if len(boot["blocks"]) != 2 or {b["kind"] for b in boot["blocks"]} != {"negative", "positive"}:
            raise AssertionError("Each boot needs both controls")
        data = {}
        for block in boot["blocks"]:
            windows = block["windows"]
            if not all(w["exact_work"] for w in windows):
                raise AssertionError("Missing exact scoreboard parity")
            data[block["kind"]] = block_contrast(block)
        windows = [w for b in boot["blocks"] for w in b["windows"]]
        quality = (
            boot["qualification"]["qualification_stable"]
            and all(w["cgroup_nr_throttled_delta"] == 0 for w in windows)
            and all(w["runqueue_delay_fraction"] is not None and
                    w["runqueue_delay_fraction"] <= stable.MAX_RUNQUEUE_DELAY_FRACTION
                    for w in windows)
        )
        per_boot.append({"boot": index, "negative_log_percent": data["negative"],
                         "positive_log_percent": data["positive"], "quality_passed": quality,
                         "qualified": boot["qualification"]["qualification_stable"],
                         "peak_runqueue_delay_fraction": max(
                             w["runqueue_delay_fraction"] or 0 for w in windows)})
    by_kind = {}
    for kind in ("negative", "positive"):
        values = [p[f"{kind}_log_percent"] for p in per_boot]
        by_kind[kind] = {
            "n_independent_boots": len(values),
            "median_log_percent": statistics.median(values),
            "median_abs_log_percent": statistics.median(abs(v) for v in values),
            "exact_median_interval": exact_median_interval(values),
            "per_boot_log_percent": values,
        }
    null = by_kind["negative"]["exact_median_interval"]
    treatment = by_kind["positive"]["exact_median_interval"]
    quality_failures = [p["boot"] for p in per_boot if not p["quality_passed"]]
    negative_pass = null["lower"] <= 0 <= null["upper"]
    positive_pass = treatment["lower"] > 0
    if quality_failures:
        verdict = "inconclusive_quality"
    elif not negative_pass:
        verdict = "negative_control_excludes_zero"
    elif not positive_pass:
        verdict = "positive_control_not_detected"
    else:
        verdict = "control_screening_passed"
    return {
        "by_kind": by_kind, "per_boot": per_boot,
        "quality_failed_boot_ids": quality_failures,
        "negative_interval_includes_zero": negative_pass,
        "positive_interval_lower_above_zero": positive_pass,
        "verdict": verdict,
        "warning": "One positive-control dose and 12 independent boots do not measure 3-5% detection power.",
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plans = schedule()
    record = {
        "experiment": EXPERIMENT, "status": "started",
        "preregistration": {
            "seed": SEED, "n_independent_boots": N_BOOTS,
            "crossover_blocks_per_boot": 2, "windows_per_block": 4,
            "score_calls_per_window": MEASURED_CALLS_PER_WINDOW,
            "source_lines_per_call": COMMANDS_PER_CALL,
            "changed_lines_in_positive_control": PERTURBED_LINES,
            "warmup_calls_per_candidate": PREWARM_PER_FUNCTION,
            "block_assignment": plans,
            "analysis_unit": "boot (n=12), NOT window (n=96)",
            "primary": "within-boot ABBA/BAAB signed mean log CPU ratio, median over JVM boots",
            "decision": "negative 95%+ exact median interval contains 0; positive interval lower >0; all boot quality gates pass",
            "all_windows_retained": True, "no_jfr_in_timed_windows": True,
            "no_new_compiler_optimization": True,
        }, "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    try:
        artifacts = stage_artifacts()
        record["artifact_hashes"] = {k:v for k,v in artifacts.items() if k.endswith("_sha256")}
        for i, plan in enumerate(plans):
            boot = run_boot(i, plan, artifacts)
            record["boots"].append(boot)
            REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        record["analysis"] = analyze(record["boots"])
        record["status"] = "complete"
        print("SCHED-BENCH-008 COMPLETE " + json.dumps({
            "verdict": record["analysis"]["verdict"],
            "by_kind": record["analysis"]["by_kind"],
            "quality_failed_boot_ids": record["analysis"]["quality_failed_boot_ids"],
        }), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["failure"] = repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
