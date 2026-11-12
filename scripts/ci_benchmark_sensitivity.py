#!/usr/bin/env python3
"""SCHED-BENCH-007: randomized-block measurement sensitivity.

Negative control: identical ordinary scoreboard functions on the same Fabric
stack. Positive control: 300 of 2,000 score lines use a semantically equivalent
execute-if-score prefix. Both arms increment the scoreboard exactly 2,000x.
The perturbation is intentionally NOT asserted to be a 3/5/10% CPU effect.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import statistics

import ci_compiler_off_stability as stable
from ci_compiler_off_paired import exact_median_interval
from benchmark_noise_telemetry import snapshot_jvm_environment, delta_environment

EXPERIMENT = "SCHED-BENCH-007"
OUT = stable.ROOT / "build" / "benchmarks" / EXPERIMENT
REPORT = OUT / "results.json"
SEED = 7007
PAIRS_PER_CONTROL = 10
POSITIVE_REPLACED_LINES = 300
assert 0 < POSITIVE_REPLACED_LINES < stable.COMMANDS_PER_CALL

_original_fixture = stable.make_fixture
_original_window = stable.take_cpu_window
_active_plan: tuple[dict, ...] = ()


def plan() -> tuple[dict, ...]:
    """Seeded control order and independently balanced within-pair order."""
    rng = random.Random(SEED)
    controls = ["AA"] * PAIRS_PER_CONTROL + ["AB"] * PAIRS_PER_CONTROL
    rng.shuffle(controls)
    orders = {
        name: rng.sample(["AB", "BA"] * (PAIRS_PER_CONTROL // 2), PAIRS_PER_CONTROL)
        for name in ("AA", "AB")
    }
    indices = {"AA": 0, "AB": 0}
    sequence = []
    for kind in controls:
        order = orders[kind][indices[kind]]
        indices[kind] += 1
        for arm in order:
            sequence.append({
                "pair": len(sequence) // 2 + 1 if len(sequence) % 2 == 0
                        else sequence[-1]["pair"],
                "kind": kind, "arm": arm,
                "modified_lines": POSITIVE_REPLACED_LINES if kind == "AB" and arm == "B" else 0,
            })
    return tuple(sequence)


def fixture(workdir: Path) -> None:
    """Keep the 2,000 source lines and exact scoreboard increments constant."""
    _original_fixture(workdir)
    import re
    match = re.match(r"ci-stable-hooks-(\d+)-fabric$", workdir.name)
    if match is None:
        raise AssertionError(f"Unexpected run path: {workdir}")
    config = _active_plan[int(match.group(1))]
    count = config["modified_lines"]
    if not count:
        return
    target = workdir / "world" / "datapacks" / stable.PACK / "data" / stable.PACK / "function" / "score.mcfunction"
    lines = target.read_text(encoding="utf-8").splitlines()
    if len(lines) != stable.COMMANDS_PER_CALL:
        raise AssertionError("Positive control source-line count changed")
    for index in range(count):
        lines[index] = (
            f"execute if score {stable.GATE} {stable.OBJECTIVE} matches 1 run "
            f"scoreboard players add {stable.HOLDER} {stable.OBJECTIVE} 1"
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert len(target.read_text(encoding="utf-8").splitlines()) == stable.COMMANDS_PER_CALL


def monitored_window(rcon, pid: int, tid: int, family: str, calls: int, *, stage: str):
    before = snapshot_jvm_environment(pid)
    result = _original_window(rcon, pid, tid, family, calls, stage=stage)
    result["noise_telemetry"] = delta_environment(before, snapshot_jvm_environment(pid))
    return result


def pair_quality(first: dict, second: dict) -> bool:
    load = abs(first["host_at_boot"]["loadavg_1m"] - second["host_at_boot"]["loadavg_1m"])
    delays = [x["mean_score_runqueue_delay_fraction"] for x in (first, second)]
    return (first["boot_quality"]["passed"] and second["boot_quality"]["passed"]
            and load <= stable.MAX_PAIR_LOAD_DIFFERENCE
            and all(d is not None for d in delays)
            and abs(delays[0] - delays[1]) <= stable.MAX_PAIR_DELAY_FRACTION_DIFFERENCE)


def analyze(boots: list[dict], sequence: tuple[dict, ...]) -> dict:
    if len(sequence) != 4 * PAIRS_PER_CONTROL or len(boots) != len(sequence):
        raise AssertionError("Incomplete campaign; do not analyze partial controls")
    pairs = []
    for i in range(0, len(boots), 2):
        a, b = boots[i:i+2]
        left, right = sequence[i:i+2]
        if (left["kind"] != right["kind"] or
            set((left["arm"], right["arm"])) != {"A", "B"}):
            raise AssertionError("Invalid plan pairing")
        if a["mode"] != "fabric" or b["mode"] != "fabric":
            raise AssertionError("Must run both arms on the same stack")
        by_arm = {left["arm"]: a, right["arm"]: b}
        baseline = by_arm["A"]["score_cpu_ns_per_line"]
        candidate = by_arm["B"]["score_cpu_ns_per_line"]
        if baseline <= 0 or candidate <= 0:
            raise AssertionError("Invalid CPU sample")
        pairs.append({
            "pair": left["pair"], "kind": left["kind"],
            "order": [left["arm"], right["arm"]],
            "a_ns_per_line": baseline, "b_ns_per_line": candidate,
            "b_over_a_percent": 100 * (candidate / baseline - 1),
            "b_over_a_log_percent": 100 * math.log(candidate / baseline),
            "first_over_second_percent": 100 * (b["score_cpu_ns_per_line"] /
                                                   a["score_cpu_ns_per_line"] - 1),
            "quality_passed": pair_quality(a, b),
            "modified_lines_a": left["modified_lines"] if left["arm"] == "A"
                                else right["modified_lines"],
            "modified_lines_b": right["modified_lines"] if right["arm"] == "B"
                                else left["modified_lines"],
        })
    controls = {}
    for kind in ("AA", "AB"):
        subset = [p for p in pairs if p["kind"] == kind]
        values = [p["b_over_a_log_percent"] for p in subset]
        interval = exact_median_interval(values)
        controls[kind] = {
            "n_pairs": len(subset),
            "median_log_percent": statistics.median(values),
            "exact_interval_log_percent": interval,
            "median_absolute_log_percent": statistics.median(abs(x) for x in values),
            "failed_quality_pairs": [p["pair"] for p in subset if not p["quality_passed"]],
            "all_pairs_retained": True,
        }
    null_interval = controls["AA"]["exact_interval_log_percent"]
    positive_interval = controls["AB"]["exact_interval_log_percent"]
    negative_pass = null_interval["lower"] <= 0 <= null_interval["upper"]
    positive_pass = positive_interval["lower"] > 0
    quality_pass = all(p["quality_passed"] for p in pairs)
    if not quality_pass:
        verdict = "inconclusive_quality"
    elif not negative_pass:
        verdict = "failed_negative_control_false_effect"
    elif not positive_pass:
        verdict = "failed_positive_control_detection"
    else:
        verdict = "passed_defined_control_detections"
    return {
        "pairs": pairs,
        "controls": controls,
        "negative_interval_includes_zero": negative_pass,
        "positive_interval_excludes_zero_in_expected_direction": positive_pass,
        "all_quality_gates_passed": quality_pass,
        "verdict": verdict,
        "warning": (
            "A single A/A and A/B campaign does NOT establish frequentist power, "
            "false-positive rates, or detection thresholds for 3/5/10% effects."
        ),
    }


def main() -> int:
    global _active_plan
    _active_plan = plan()
    OUT.mkdir(parents=True, exist_ok=True)
    stable.OUT = OUT
    stable.make_fixture = fixture
    stable.take_cpu_window = monitored_window
    os.environ.pop("FC_BENCH_GC_LOG", None)
    record = {
        "experiment": EXPERIMENT, "status": "started",
        "declarations": {
            "seed": SEED, "pair_count_per_control": PAIRS_PER_CONTROL,
            "plan": _active_plan,
            "perturbation": "replace first 300 of 2000 score commands with execute-if-score-true equivalents",
            "preserved_source_lines_and_score_updates_per_call": stable.COMMANDS_PER_CALL,
            "primary": "median within-pair signed log(B CPU / A CPU), percent units",
            "interval": "conservative exact >=95% median order-stat interval",
            "negative_pass": "A/A median interval includes zero",
            "positive_pass": "A/B median interval lower bound > zero",
            "quality_pass": "all pairs pass predefined boot and host quality checks",
            "quality_failures_retained": True,
            "no_early_stopping": True,
            "no_production_code_change": True,
            "positive_effect_size_is_unknown_before_measurement": True,
        },
        "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    try:
        artifacts = stable.stage_artifacts()
        record["artifact_hashes"] = {k:v for k,v in artifacts.items() if k.endswith("_sha256")}
        for idx, config in enumerate(_active_plan):
            boot = stable.run_boot(idx, "fabric", artifacts)
            boot["control"] = config
            record["boots"].append(boot)
            REPORT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            if idx % 2:
                print(f"CONTROL pair={config['pair']}/{len(_active_plan)//2} "
                      f"kind={config['kind']} order="
                      f"{_active_plan[idx-1]['arm']}{config['arm']}", flush=True)
        record["analysis"] = analyze(record["boots"], _active_plan)
        record["status"] = "complete"
        print("SCHED-BENCH-007 " + json.dumps(
            {"verdict": record["analysis"]["verdict"],
             "controls": record["analysis"]["controls"]}), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
