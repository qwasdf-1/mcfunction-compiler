#!/usr/bin/env python3
"""SCHED-COMP-011: real Vein Miner native event, fused vs ScoreAdd alone.

Runs the existing pinned ore-mining player-bot harness rather than a synthetic
function. Timed modes are symmetric (no Spark, per-command metrics or JFR).
Constructor-stage compilation wall times are separately observed via the
research-only FC_BENCH_COMPILE_TIMING flag, which is off the execution path.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys

from ci_compiler_off_paired import exact_median_interval
from ci_compiler_off_paired import snapshot_host

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "SCHED-COMP-011"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
REPORT = OUT / "results.json"
PAIR_COUNT = 10
SEED = 26874011
SIDELENGTH = 6
MINIMUM_GAIN_PERCENT = 15.0
NATIVE_PACK_PATH = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
NATIVE_PACK_SHA256 = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
ARMS = ("score-add", "fused")
STATE_FIELDS = (
    "player_mined_source_stat", "work_after", "work_expected",
    "run_state_after", "queue_head_delta", "remaining_ore",
    "source_block_remains", "operation_markers_after", "target_markers_after",
)
CONTEXT_METRICS = ("tick_average_ms", "tick_p95_ms")


def allocation() -> tuple[tuple[str, str], ...]:
    rng = random.Random(SEED)
    # Counterbalance exactly five in each order, deterministic before launch.
    values = [("score-add", "fused")] * (PAIR_COUNT//2) + [
        ("fused", "score-add")] * (PAIR_COUNT//2)
    rng.shuffle(values)
    return tuple(values)


def stats_int(status: str | None, name: str) -> int | None:
    import re
    if status is None:
        return None
    m = re.search(rf"\b{re.escape(name)}=(\d+)\b", status)
    return int(m.group(1)) if m else None


def run_profile(mode: str, pair: int, position: int) -> dict:
    if mode not in ARMS:
        raise ValueError(mode)
    profile_mode = "fused-timed" if mode == "fused" else "score-add"
    command = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", profile_mode,
        "--side", str(SIDELENGTH), "--capture-timeout", "60", "--no-spark",
    ]
    env = dict(os.environ)
    env["FC_BENCH_COMPILE_TIMING"] = "true"
    # All other performance-relevant run flags are supplied by the exact same
    # native profile runner; mode is the deliberate compiler intervention.
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=600, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Pair {pair}, arm {mode}: native profile failed "
                           f"exit={completed.returncode}; stdout={completed.stdout[-1800:]!r}; "
                           f"stderr={completed.stderr[-1800:]!r}")
    profile = json.loads(completed.stdout)
    result = profile["results"]
    if result.get("compiler_mode") != profile_mode:
        raise AssertionError(f"Unexpected compiler profile mode {result.get('compiler_mode')}")
    if not result.get("valid_native_workload"):
        raise AssertionError(f"Native ore event semantic gate failed for {mode}")
    if mode == "fused" and not result.get("valid_fused_timed_profile"):
        raise AssertionError("Timed fused compiler compilation/activation gate failed")
    if mode == "score-add" and not result.get("valid_score_add_profile"):
        raise AssertionError("ScoreAdd compilation gate failed")
    compiled_regions = result.get("fused_regions_compiled")
    if mode == "fused":
        if not isinstance(compiled_regions, int) or compiled_regions <= 0:
            raise AssertionError("Fused mode compiled no regions")
        if (result.get("vm_detection_acquire_target_fused_compiled") or 0) <= 0:
            raise AssertionError("No fusion in pinned Vein Miner detection/acquire_target")
    elif compiled_regions != 0:
        raise AssertionError("ScoreAdd-only baseline unexpectedly compiled fused regions")
    score_ns = result.get("score_add_compile_wall_ns")
    fuse_ns = result.get("fused_compile_wall_ns")
    if not isinstance(score_ns, int) or score_ns <= 0:
        raise AssertionError("ScoreAdd compilation timings absent")
    if not isinstance(fuse_ns, int) or fuse_ns < 0:
        raise AssertionError("Fusion compilation timings absent")
    if mode == "score-add" and fuse_ns:
        raise AssertionError("Fusion compilation time nonzero in baseline")
    if mode == "fused" and fuse_ns == 0:
        raise AssertionError("Fusion compilation time zero in treatment")
    if not isinstance(result.get("launch_to_rcon_seconds"), (int, float)):
        raise AssertionError("Missing boot readiness timing")

    state = {key: result[key] for key in STATE_FIELDS}
    return {
        "pair": pair, "position": position, "mode": mode, "profile_mode": profile_mode,
        "run_id": result.get("run_id"), "output": profile.get("output"),
        "event_completion_seconds": result["operation_completion_seconds"],
        "parity_state": state, "fused_regions_compiled": compiled_regions,
        "vm_detection_acquire_target_fused_compiled":
            result.get("vm_detection_acquire_target_fused_compiled"),
        "score_add_compile_wall_ns": score_ns, "fused_compile_wall_ns": fuse_ns,
        "launch_to_rcon_seconds": result["launch_to_rcon_seconds"],
        "tick_query_after_capture": result.get("tick_query_after_capture"),
        "exact_native_workload": True,
        "profile_valid": True,
    }


def paired_percentage(fused: float, baseline: float) -> float:
    if fused <= 0 or baseline <= 0:
        raise AssertionError("Nonpositive timing")
    return 100 * (fused / baseline - 1)


def analyze(pairs: list[dict]) -> dict:
    if len(pairs) != PAIR_COUNT:
        raise AssertionError("Incomplete campaign")
    contrast = []
    boot_delta = []
    compile_extra = []
    paired = []
    for index, pair in enumerate(pairs, 1):
        if pair["index"] != index or len(pair["arms"]) != 2:
            raise AssertionError("Incomplete or reordered pair")
        a = pair["arms"]["score-add"]
        b = pair["arms"]["fused"]
        if a["parity_state"] != b["parity_state"]:
            raise AssertionError(f"Native work differs in pair {index}")
        if not (a["exact_native_workload"] and b["exact_native_workload"]
                and a["profile_valid"] and b["profile_valid"]):
            raise AssertionError(f"Native semantic gate failed in pair {index}")
        pct = paired_percentage(b["event_completion_seconds"],a["event_completion_seconds"])
        contrast.append(pct)
        boot_delta.append(b["launch_to_rcon_seconds"] - a["launch_to_rcon_seconds"])
        compile_extra.append(
            (b["score_add_compile_wall_ns"]+b["fused_compile_wall_ns"]
             - a["score_add_compile_wall_ns"])/1e6
        )
        paired.append({
            "index": index, "order": pair["order"],
            "event_percent": pct,
            "scoreadd_event_seconds": a["event_completion_seconds"],
            "fused_event_seconds": b["event_completion_seconds"],
            "readiness_delta_seconds": boot_delta[-1],
            "incremental_compilation_wall_ms": compile_extra[-1],
            "full_state_parity": True,
        })
    interval = exact_median_interval(contrast)
    if interval["upper"] <= -MINIMUM_GAIN_PERCENT:
        verdict = "real_event_gain_at_least_15pct_supported"
    elif interval["lower"] > 0:
        verdict = "real_event_regression_supported"
    elif interval["lower"] >= -MINIMUM_GAIN_PERCENT:
        verdict = "does_not_meet_15pct_gain"
    else:
        verdict = "real_event_inconclusive"
    return {
        "verdict": verdict, "paired": paired,
        "n_pairs": len(contrast), "all_pairs_retained": True,
        "primary": {
            "metric": "native event completion seconds", "median_percent": statistics.median(contrast),
            "exact_median_interval_percent": interval,
            "minimum_gain_percent": MINIMUM_GAIN_PERCENT,
        },
        "secondary": {
            "median_launch_to_rcon_delta_seconds": statistics.median(boot_delta),
            "median_incremental_compile_stage_wall_ms": statistics.median(compile_extra),
            "additional_compilation_cost_is_not_boot_cost": True,
            "compiler_stage_wall_time_is_not_cpu_time": True,
        },
        "caution": (
            "Fresh-boot paired real-world latency may be affected by host noise. "
            "Constructor stage wall times omit macro instantiation and JVM startup, "
            "and include wall-clock preemption. Do not mix them with server-thread CPU."
        ),
    }


def main() -> int:
    import hashlib
    OUT.mkdir(parents=True, exist_ok=True)
    orders = allocation()
    record = {
        "experiment": EXPERIMENT, "status": "started",
        "preregistration": {
            "seed": SEED, "pairs": PAIR_COUNT, "orders": orders,
            "datapack": str(NATIVE_PACK_PATH.relative_to(ROOT)),
            "datapack_sha256_expected": NATIVE_PACK_SHA256,
            "workload": "native survival-player Vein Miner 6x6x6 ore event",
            "primary": "fused vs typed ScoreAdd native event completion seconds",
            "minimum_gain_percent": MINIMUM_GAIN_PERCENT,
            "confidence_interval": "exact order-stat median interval >=95%",
            "secondary": "RCON startup readiness and opt-in constructor compile-stage wall time",
            "symmetric_no_spark_no_execution_counters": True,
            "no_exclusions": True,
            "no_production_default_change": True,
        },
        "pairs": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n")
    try:
        if not NATIVE_PACK_PATH.is_file():
            raise FileNotFoundError(f"Native datapack not present at {NATIVE_PACK_PATH}")
        actual = hashlib.sha256(NATIVE_PACK_PATH.read_bytes()).hexdigest()
        if actual != NATIVE_PACK_SHA256:
            raise AssertionError(f"Pinned Vein Miner datapack fingerprint mismatch: {actual}")
        for index, order in enumerate(orders, 1):
            pair = {"index": index, "order": list(order), "arms": {},
                    "host_before": snapshot_host()}
            record["pairs"].append(pair)
            REPORT.write_text(json.dumps(record,indent=2)+"\n")
            for position, mode in enumerate(order):
                print(f"REAL_EVENT pair={index}/{PAIR_COUNT} pos={position} arm={mode}",
                      flush=True)
                pair["arms"][mode] = run_profile(mode, index, position)
                REPORT.write_text(json.dumps(record,indent=2)+"\n")
            pair["host_after"] = snapshot_host()
            if pair["arms"]["score-add"]["parity_state"] != pair["arms"]["fused"]["parity_state"]:
                raise AssertionError(f"Parities diverged in pair {index}")
        record["analysis"] = analyze(record["pairs"])
        record["status"] = "complete"
        print("SCHED-COMP-011 COMPLETE " + json.dumps(record["analysis"]), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["failure"] = repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(record,indent=2)+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
