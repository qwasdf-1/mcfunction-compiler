#!/usr/bin/env python3
"""IR-032 Gate C: fresh Dynamic Lights CPU arms and separate descriptive JFR.

Never run the execution census or callback timers inside a CPU arm. Stationary
and moving represent distinct real workloads, not an optimizer A/B. JFR data
is separately sampled and its overlapping stack categories are never summed.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-032-GATE-C"
BENCH = ROOT / "build/benchmarks/PERF-010"
PUBLISHER_PIN = "afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20"
PATCHED_PIN = "c649d206faac63a773ce5dec06ec531128d1f6feaa104ad4e28a18143706d083"
RUNS = (("S1", "stationary", False), ("M1", "moving", False),
        ("M2", "moving", False), ("S2", "stationary", False),
        ("S_JFR", "stationary", True), ("M_JFR", "moving", True))
SECONDS = 18
MIN_TICKS = 300
MAX_TICKS = 380
MAX_WITHIN_SCENARIO_SPREAD = 0.08
MIN_JFR_RUNNABLE_SAMPLES = 150

sys.path.insert(0, str(ROOT / "scripts"))
from ci_ir032_dynamic_lights_census import verify_clean_minecraft_26_3_environment  # noqa: E402
from ci_ir032_dynamic_lights_source import census as source_census  # noqa: E402
from run_dynamic_lights_profile import PACK, sha256  # noqa: E402


# Broad, inclusive, possibly overlapping stack-presence groups, NOT costs.
# Precise hotspot identification still uses top leaf frames and original source.
GROUPS = {
    "block_and_fill": lambda c, m: (
        c.endswith(("FillCommand", "SetBlockCommand", "BlockInput"))
        or (c.endswith(("ServerLevel", "Level", "LevelChunk")) and
            m in ("setBlock", "setBlockState", "sendBlockUpdated"))),
    "execute_and_selectors": lambda c, m: (
        "BuildContexts" in c or c.endswith((
            "EntitySelector", "EntitySelectorOptions", "ExecuteCommand"))
        or (c.endswith("ContextChain") and m == "runModifier")),
    "scoreboard_and_tag": lambda c, m: (
        "Scoreboard" in c or c.endswith(("ScoreboardCommand", "TagCommand"))
        or (c.endswith("Entity") and m in ("addTag", "removeTag"))),
    "function_and_queue": lambda c, m: (
        c.endswith(("ServerFunctionManager", "FunctionCommand", "CallFunction",
                    "ContinuationTask", "ExecutionContext", "FunctionEntry"))),
    "entity_data_nbt": lambda c, m: (
        "DataCommands" in c or "DataAccessor" in c or "NbtPath" in c
        or (c.endswith("Entity") and m in ("load", "saveWithoutId"))),
    "entity_world_iteration": lambda c, m: (
        c.endswith(("ServerLevel", "Level")) and
        m in ("getEntities", "getEntitiesOfClass")),
}


def normalize_frame(frame: dict) -> tuple[str, str]:
    method = frame.get("method") or {}
    klass = (method.get("type") or {}).get("name") or ""
    return str(klass).replace("/", "."), str(method.get("name") or "")


def summarize_jfr(path: Path, server_tid: int) -> dict:
    process = subprocess.run(
        ["jfr", "print", "--json", "--events", "jdk.ExecutionSample",
         "--stack-depth", "96", str(path)],
        capture_output=True, text=True, timeout=180, check=False)
    if process.returncode != 0:
        raise RuntimeError(f"JFR print failed: {process.stderr[-3000:]}")
    events = json.loads(process.stdout).get("recording", {}).get("events", [])
    server = []
    for event in events:
        if event.get("type") != "jdk.ExecutionSample":
            continue
        values = event.get("values") or {}
        thread = values.get("sampledThread") or {}
        if int(thread.get("osThreadId", -1)) == server_tid:
            server.append(values)
    runnable = [s for s in server if s.get("state") == "STATE_RUNNABLE"]
    counts = Counter()
    leaf = Counter()
    examples = {}
    for sample in runnable:
        frames = [normalize_frame(f) for f in
                  (sample.get("stackTrace") or {}).get("frames") or []]
        if frames:
            leaf[".".join(frames[0])] += 1
        for name, predicate in GROUPS.items():
            if any(predicate(c, m) for c, m in frames):
                counts[name] += 1
                if name not in examples:
                    examples[name] = [".".join(x) for x in frames[:12]]
    n = len(runnable)
    return {
        "recording_sha256": sha256(path),
        "recording_bytes": path.stat().st_size,
        "server_thread_os_tid": server_tid,
        "all_server_thread_execution_samples": len(server),
        "runnable_server_thread_samples": n,
        "minimum_runnable_samples": MIN_JFR_RUNNABLE_SAMPLES,
        "coverage_sufficient": n >= MIN_JFR_RUNNABLE_SAMPLES,
        "inclusive_sample_counts": dict(counts),
        "inclusive_sample_fractions": {
            name: counts[name] / n if n else 0.0 for name in GROUPS
        },
        "example_stacks": examples,
        "top_leaf_frames": [
            {"frame": name, "samples": count} for name, count in leaf.most_common(30)
        ],
        "categories_overlap": True,
        "samples_are_not_exclusive_cpu_times": True,
        "jfr_is_separate_from_uninstrumented_cpu": True,
    }


def check_result(data: dict, scenario: str, jfr: bool) -> dict:
    if data.get("datapack_sha256") != PUBLISHER_PIN:
        raise AssertionError("Wrong original publisher SHA")
    if (data.get("runtime_pack_sha256") != PATCHED_PIN
            or data.get("runtime_pack_is_publisher_byte_exact") is not False):
        raise AssertionError("Benchmark-only upstream patch drift or byte-exact mislabel")
    if (data.get("stack") != "fabric" or data.get("function_compiler_wrapper") != "on"
            or data.get("mode") != "idle" or data.get("profile_seconds") != SECONDS):
        raise AssertionError("Dynamic Lights original scenario/config drift")
    if scenario not in data.get("scenario", "") or data["item_motion"]["scenario"] != scenario:
        raise AssertionError("Stationary/moving scenario mismatch")
    if not data.get("gate_c_cpu_capture_enabled") or data.get("gate_c_jfr_capture_enabled") != jfr:
        raise AssertionError("Unexpected CPU/JFR capture modes")
    if (data.get("compiler_exec_census_enabled")
            or data.get("spark") is not None or data.get("spark_sampling") is not None):
        raise AssertionError("CPU arm contaminated by census or Spark")
    verify_clean_minecraft_26_3_environment(data)
    if (data.get("tracked_items_before_profile") != 24
            or data.get("tracked_items_after_profile") != 24
            or data.get("tagged_torch_sources_before_profile") != 24
            or data.get("tagged_torch_sources_after_profile") != 24):
        raise AssertionError("Missing Dynamic Lights source items")
    if data.get("pre_window_host_stability", {}).get("stable") is not True:
        raise AssertionError("Pre-window host tick gate failed")
    cpu = data.get("server_thread_cpu") or {}
    ticks = data.get("game_ticks_during_window")
    if (not isinstance(ticks, int) or not MIN_TICKS <= ticks <= MAX_TICKS
            or not cpu.get("cpu_measurement_valid")
            or not cpu.get("host_quality_pass")
            or cpu.get("cgroup_nr_throttled_delta") != 0
            or cpu.get("server_thread_cpu_running_ns", 0) <= 0
            or cpu.get("game_ticks_during_window") != ticks):
        raise AssertionError("Invalid Server-thread CPU, cgroup, or tick-window evidence")
    if jfr:
        if not data.get("jfr_path") or not data.get("jfr_sha256"):
            raise AssertionError("JFR arm produced no profile")
    elif data.get("jfr_path") is not None:
        raise AssertionError("Uninstrumented CPU arm has a JFR recording")
    return {
        "scenario": scenario, "jfr": jfr, "game_ticks": ticks,
        "server_thread_pid": cpu["server_thread_pid"],
        "server_thread_tid": cpu["server_thread_tid"],
        "running_cpu_ns": cpu["server_thread_cpu_running_ns"],
        "cpu_ns_per_tick": cpu["server_thread_cpu_ns_per_game_tick"],
        "runqueue_wait_fraction": cpu["server_thread_runqueue_wait_fraction"],
        "host_quality_pass": True, "all_source_guards_pass": True,
        "publisher_sha256": PUBLISHER_PIN, "runtime_pack_sha256": PATCHED_PIN,
    }


def run_arm(label: str, scenario: str, jfr: bool) -> dict:
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
    command = [
        sys.executable, str(ROOT / "scripts/run_dynamic_lights_profile.py"),
        "--stack", "fabric", "--wrapper", "on", "--datapack", "on",
        "--mode", "idle", "--no-spark", "--capture-server-thread-cpu",
        "--apply-ir032-upstream-hotfix", "--seconds", str(SECONDS),
        "--scenario", scenario,
    ]
    if jfr:
        command.append("--jfr-server-thread")
    log = OUT / f"{label}.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.run(
            command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
            timeout=1100, check=False)
    if process.returncode != 0:
        raise RuntimeError(
            f"IR-032 Gate C {label} failed (exit {process.returncode}); "
            f"log tail: {log.read_text(errors='replace')[-4000:]}")
    after = {p.resolve() for p in BENCH.glob("dynamic-lights-*/results.json")}
    new_results = sorted(after - before)
    if len(new_results) != 1:
        raise AssertionError(f"Expected exactly one new Minecraft run, got {new_results!r}")
    result_path = new_results[0]
    data = json.loads(result_path.read_text(encoding="utf-8"))
    record = check_result(data, scenario, jfr)
    record["label"] = label
    record["source_results_path"] = str(result_path.relative_to(ROOT))
    shutil.copy2(result_path, OUT / f"{label}.json")
    if jfr:
        profile = ROOT / data["jfr_path"]
        if not profile.is_file() or sha256(profile) != data["jfr_sha256"]:
            raise AssertionError(f"JFR evidence mismatch: {profile}")
        shutil.copy2(profile, OUT / f"{label}.jfr")
        record["jfr"] = summarize_jfr(OUT / f"{label}.jfr", record["server_thread_tid"])
        (OUT / f"{label}-jfr-summary.json").write_text(
            json.dumps(record["jfr"], indent=2) + "\n", encoding="utf-8")
    print(f"IR-032 Gate C {label}: {record['cpu_ns_per_tick']/1e6:.3f} ms/tick; "
          f"{record['game_ticks']} ticks", flush=True)
    return record


def compute_cpu_screen(records: list[dict]) -> dict:
    cpu = [x for x in records if not x["jfr"]]
    if [x["label"] for x in cpu] != ["S1", "M1", "M2", "S2"]:
        raise AssertionError("IR-032 Gate C non-JFR arms must be S-M-M-S")
    values = {
        scenario: [x["cpu_ns_per_tick"] for x in cpu if x["scenario"] == scenario]
        for scenario in ("stationary", "moving")
    }
    med = {scenario: statistics.median(xs) for scenario, xs in values.items()}
    spread = {
        scenario: abs(xs[0] - xs[1]) / statistics.mean(xs)
        for scenario, xs in values.items()
    }
    return {
        "order": [x["label"] for x in cpu],
        "cpu_ns_per_game_tick": values,
        "median_cpu_ns_per_game_tick": med,
        "moving_minus_stationary_fraction": med["moving"] / med["stationary"] - 1,
        "within_scenario_relative_spread": spread,
        "noise_threshold": MAX_WITHIN_SCENARIO_SPREAD,
        "noise_screen_pass": all(v <= MAX_WITHIN_SCENARIO_SPREAD for v in spread.values()),
        "decision": "descriptive workload-cost contrast only; no optimizer tested",
        "not_causal_optimization_evidence": True,
        "not_a_15_percent_promotion_test": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Preserve exact publisher and the already-accepted overlay/patch contract.
    if not PACK.is_file() or sha256(PACK) != PUBLISHER_PIN:
        raise RuntimeError("Pinned original Dynamic Lights publisher archive missing")
    source_census(PACK)
    records = []
    try:
        for label, scenario, jfr in RUNS:
            record = run_arm(label, scenario, jfr)
            records.append(record)
            (OUT / "partial-results.json").write_text(
                json.dumps(records, indent=2) + "\n", encoding="utf-8")
    finally:
        (OUT / "partial-results.json").write_text(
            json.dumps(records, indent=2) + "\n", encoding="utf-8")
    screen = compute_cpu_screen(records)
    summary = {
        "milestone": "COMPILER-IR-032 Gate C",
        "publisher_sha256": PUBLISHER_PIN,
        "patched_runtime_sha256": PATCHED_PIN,
        "experiment_type": "controlled baseline workload CPU + separate JFR attribution",
        "run_order": [x[0] for x in RUNS],
        "cpu_screen": screen,
        "runs": records,
        "promotion_decision": "not applicable: no compiler optimization implemented",
        "source_workflow_is_manual_only": True,
    }
    (OUT / "results.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not all(x.get("coverage_sufficient") for x in
               (records[-2]["jfr"], records[-1]["jfr"])):
        raise RuntimeError("JFR sample coverage below preregistered minimum")
    print(json.dumps(screen, indent=2))


if __name__ == "__main__":
    main()
