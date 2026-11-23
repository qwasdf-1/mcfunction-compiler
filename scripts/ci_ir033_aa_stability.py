#!/usr/bin/env python3
"""IR-033: bounded no-treatment A/A stability qualification for compiler CPU research.

All six native arms are deliberately IDENTICAL; placebo A/B labels only test
whether the measurement apparatus invents a purported treatment effect.
No compiler candidate and no JFR/Spark/callback/census measurement.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-033-AA-STABILITY"
BENCH = ROOT / "build/benchmarks/PERF-010"
SECONDS = 60
MIN_TICKS, MAX_TICKS = 1120, 1260
# Fixed upfront. False treatment must be smaller than a 5% development signal.
MAX_PLACEBO_EFFECT = 0.05
# Individual neighboring-run spreads and six-run range, all predeclared.
MAX_ADJACENT_SPREAD = 0.08
MAX_FULL_RANGE = 0.10
# Intentionally pseudo-treatment labels. All configs and gameplay are identical.
RUN_ORDER = ("A1", "B1", "B2", "A2", "A3", "B3")
PAIRS = (("A1", "B1"), ("B2", "A2"), ("A3", "B3"))

sys.path.insert(0, str(ROOT / "scripts"))
from ci_ir032_gate_c import (PUBLISHER_PIN, PATCHED_PIN, check_result)  # noqa: E402
from ci_ir032_dynamic_lights_source import census as source_census  # noqa: E402
from run_dynamic_lights_profile import PACK, sha256  # noqa: E402


def predeclared_screen(records: list[dict]) -> dict:
    if [r["label"] for r in records] != list(RUN_ORDER):
        raise AssertionError("A/A order drift")
    for r in records:
        if r["scenario"] != "stationary" or r["jfr"] is not False:
            raise AssertionError("Non-identical or instrumented A/A arm")
        if r["game_ticks"] < MIN_TICKS or r["game_ticks"] > MAX_TICKS:
            raise AssertionError("A/A tick-window drift")
    by_label = {r["label"]: r["cpu_ns_per_tick"] for r in records}
    if min(by_label.values()) <= 0:
        raise AssertionError("CPU sample missing")
    placebo_a = [by_label[k] for k in ("A1", "A2", "A3")]
    placebo_b = [by_label[k] for k in ("B1", "B2", "B3")]
    delta = statistics.median(placebo_b) / statistics.median(placebo_a) - 1
    pair_spreads = {
        f"{a}/{b}": abs(by_label[a] - by_label[b]) /
                    statistics.mean((by_label[a], by_label[b]))
        for a, b in PAIRS
    }
    full_range = (max(by_label.values()) - min(by_label.values())) / statistics.mean(by_label.values())
    passes = {
        "placebo_effect_below_5pct": abs(delta) <= MAX_PLACEBO_EFFECT,
        "all_adjacent_pairs_below_8pct": all(v <= MAX_ADJACENT_SPREAD for v in pair_spreads.values()),
        "six_arm_range_below_10pct": full_range <= MAX_FULL_RANGE,
    }
    return {
        "run_order": list(RUN_ORDER),
        "all_arms_same_uninstrumented_stationary_config": True,
        "placebo_labels_are_not_compiler_modes": True,
        "cpu_ns_per_tick": by_label,
        "pseudo_a_median_ns_per_tick": statistics.median(placebo_a),
        "pseudo_b_median_ns_per_tick": statistics.median(placebo_b),
        "placebo_effect_fraction": delta,
        "adjacent_pair_relative_spreads": pair_spreads,
        "full_range_relative_to_mean": full_range,
        "thresholds": {
            "absolute_placebo_effect": MAX_PLACEBO_EFFECT,
            "adjacent_pair_spread": MAX_ADJACENT_SPREAD,
            "full_range": MAX_FULL_RANGE,
        },
        "screens": passes,
        "noise_qualification_pass": all(passes.values()),
        "is_not_causal_compiler_optimization_evidence": True,
        "cannot_certify_five_percent_detection_power_from_six_arms": True,
    }


def run_arm(label: str) -> dict:
    before = {p.resolve() for p in BENCH.glob("dynamic-lights-*/results.json")}
    env = dict(os.environ)
    env.update({
        "FC_COMPILER_EXEC_CENSUS": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES": "false",
        "FC_FUNCTION_TIMING": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_IR030_POS_GET": "false",
        "FC_IR030_POS_GET_VERIFY": "false",
        "FC_IR031_MODE": "",
        "FC_TYPED_IR_MODE": "off",
        "FC_RUNTIME_TRACE": "false",
    })
    cmd = [
        sys.executable, str(ROOT / "scripts/run_dynamic_lights_profile.py"),
        "--stack", "fabric", "--wrapper", "on", "--datapack", "on",
        "--mode", "idle", "--scenario", "stationary", "--seconds", str(SECONDS),
        "--no-spark", "--capture-server-thread-cpu", "--apply-ir032-upstream-hotfix",
    ]
    log = OUT / f"{label}.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.run(cmd, cwd=ROOT, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, timeout=1300, check=False)
    if process.returncode:
        raise RuntimeError(
            f"IR-033 {label} exited {process.returncode}: "
            f"{log.read_text(errors='replace')[-4000:]}")
    after = {p.resolve() for p in BENCH.glob("dynamic-lights-*/results.json")}
    created = sorted(after - before)
    if len(created) != 1:
        raise AssertionError(f"Exactly one native server result required for {label}: {created!r}")
    path = created[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    record = check_result(
        data, "stationary", False, seconds=SECONDS,
        min_ticks=MIN_TICKS, max_ticks=MAX_TICKS)
    record.update({
        "label": label,
        "placebo_arm": label[0],
        "source_results_path": str(path.relative_to(ROOT)),
        "config_fingerprint": "identical_stone_players_24_static_torches_no_compiler_diagnostics",
    })
    shutil.copy2(path, OUT / f"{label}.json")
    print(f"IR-033 {label} placebo {label[0]}: "
          f"{record['cpu_ns_per_tick']/1e6:.4f} ms/tick "
          f"over {record['game_ticks']} ticks", flush=True)
    return record


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not PACK.is_file() or sha256(PACK) != PUBLISHER_PIN:
        raise RuntimeError("Missing exact Dynamic Lights original publisher archive")
    source_census(PACK)
    results = []
    try:
        for label in RUN_ORDER:
            results.append(run_arm(label))
            (OUT / "partial-results.json").write_text(
                json.dumps(results, indent=2) + "\n", encoding="utf-8")
    finally:
        (OUT / "partial-results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8")
    screen = predeclared_screen(results)
    summary = {
        "milestone": "COMPILER-IR-033",
        "experiment": "identical uninstrumented placebo-labelled A/A stability",
        "publisher_sha256": PUBLISHER_PIN,
        "runtime_pack_sha256": PATCHED_PIN,
        "seconds_per_window": SECONDS,
        "run_order": list(RUN_ORDER),
        "run_results": results,
        "screen": screen,
        "workflow_trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "research_only": True,
        "production_defaults_unchanged": True,
    }
    (OUT / "results.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("IR033_AA_SCREEN " + json.dumps(screen), flush=True)
    if not screen["noise_qualification_pass"]:
        raise RuntimeError("IR-033 no-treatment A/A stability qualification failed")
    print("IR-033 A/A stability screen passed (not a compiler speedup)", flush=True)


if __name__ == "__main__":
    main()
