#!/usr/bin/env python3
"""IR-032 Gate B: count exact Dynamic Lights tick-function calls, no CPU timing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-032-DYNAMIC-LIGHTS-CENSUS"
INVENTORY = ROOT / "build/reports/COMPILER-IR-032-DYNAMIC-LIGHTS-SOURCE/inventory.json"
PACK_SHA256 = "afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20"
NAMESPACE = "dynamic_lights_by_creepermeyt"
SECONDS = 18
SCENARIOS = ("stationary", "moving")
TARGETS = (
    "internal/tick",
    "internal/tickcheck",
    "internal/dynamiclight",
    "internal/common/dynamiclight",
    "internal/common/tickupdate",
    "internal/smart/dynamiclight",
    "internal/smart/tickupdate",
    "internal/smart/updatecheck",
    "internal/smart/summon",
    "internal/smart/create",
    "internal/smart/propagate",
    "internal/smart/compare",
    "internal/util/genforentitywithscore",
    "internal/util/asitem",
    "internal/util/asholder",
)


def parse_key_values(text: str) -> dict[str, str]:
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", text))


def parse_exec_census(path: Path, expected_callees: list[str]) -> dict:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    begin_lines = [line.split("FC_EXEC_BEGIN", 1)[1] for line in lines if "FC_EXEC_BEGIN" in line]
    end_lines = [line.split("FC_EXEC_END", 1)[1] for line in lines if "FC_EXEC_END" in line]
    if len(begin_lines) != 1 or len(end_lines) != 1:
        raise AssertionError(
            f"Expected one FC_EXEC_BEGIN and END, got {len(begin_lines)} / {len(end_lines)}")
    begin = parse_key_values(begin_lines[0])
    end = parse_key_values(end_lines[0])
    if begin.get("namespace") != NAMESPACE or end.get("namespace") != NAMESPACE:
        raise AssertionError("Execution census namespace mismatch")
    if int(begin.get("overflow", "-1")) != 0:
        raise AssertionError(f"Execution census site overflow: {begin!r}")

    rows = []
    callees = {}
    for line in lines:
        if "FC_EXEC_ROW" in line:
            rows.append(parse_key_values(line.split("FC_EXEC_ROW", 1)[1]))
        elif "FC_EXEC_CALLEE" in line:
            fields = parse_key_values(line.split("FC_EXEC_CALLEE", 1)[1])
            callees[fields["function"]] = int(fields["native_call_tasks"])

    if len(callees) != len(expected_callees):
        raise AssertionError(
            f"Expected {len(expected_callees)} callee counters, got {len(callees)}")
    if set(callees) != set(expected_callees):
        raise AssertionError("Native callee counter set differs from exact source graph")
    if len(rows) != int(begin.get("sites", "-1")):
        raise AssertionError(
            f"FC_EXEC_ROW count {len(rows)} differs from registered sites {begin.get('sites')}")
    if sum(int(row["entries"]) for row in rows) != int(begin["entries"]):
        raise AssertionError("Per-site entry counts do not reconcile to FC_EXEC_BEGIN")
    if sum(int(row["callbacks"]) for row in rows) != int(begin["callbacks"]):
        raise AssertionError("Per-site callback counts do not reconcile to FC_EXEC_BEGIN")
    if sum(callees.values()) != int(begin["native_calls"]):
        raise AssertionError("Per-callee native call counts do not reconcile to FC_EXEC_BEGIN")
    for key in ("entries", "callbacks", "native_calls"):
        if end.get(key) != begin.get(key):
            raise AssertionError(f"FC_EXEC_BEGIN/END {key} mismatch")

    target_entries = {}
    target_callbacks = {}
    for row in rows:
        name = row["function"]
        target_entries[name] = target_entries.get(name, 0) + int(row["entries"])
        target_callbacks[name] = target_callbacks.get(name, 0) + int(row["callbacks"])
    target_functions = sorted(target_entries)
    top_callees = sorted(
        ({"function": name, "native_call_tasks": count}
         for name, count in callees.items()),
        key=lambda row: row["native_call_tasks"],
        reverse=True,
    )
    return {
        "summary": begin,
        "end": end,
        "site_rows": rows,
        "callee_counts": callees,
        "target_function_entry_totals": target_entries,
        "target_function_callback_totals": target_callbacks,
        "target_functions_observed": target_functions,
        "top_callees": top_callees[:30],
        "total_function_call_tasks": sum(callees.values()),
    }


def run_scenario(scenario: str, callees: list[str]) -> dict:
    output_root = ROOT / "build/benchmarks/PERF-010"
    previous = set(output_root.glob("dynamic-lights-*/results.json"))
    env = dict(os.environ)
    env.update({
        "GRADLE_USER_HOME": str(ROOT / "build/gradle-cache-ir032-dynamic-lights"),
        "GRADLE_RO_DEP_CACHE": str(Path.home() / ".gradle" / "caches"),
        "FC_COMPILER_EXEC_CENSUS": "true",
        "FC_COMPILER_EXEC_CENSUS_NAMESPACE": NAMESPACE,
        "FC_COMPILER_EXEC_CENSUS_FUNCTIONS": ",".join(
            f"{NAMESPACE}:{name}" for name in TARGETS),
        "FC_COMPILER_EXEC_CENSUS_CALLEES": ",".join(callees),
        "FC_IR030_POS_GET": "false",
        "FC_IR030_POS_GET_VERIFY": "false",
        "FC_IR031_MODE": "",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_CPU005_MODE": "",
        "FC_CPU004_MODE": "",
        "FC_MACRO006_MODE": "",
    })
    for key in (
        "FC_TYPED_IR_MODE", "FC_TYPED_IR_NAMESPACE",
        "FC_TYPED_IR_FUNCTION_FILTER", "FC_COMPILER_ACCEPTANCE_NAMESPACE",
        "FC_COMPILER_EXEC_CENSUS_ALLOW_ALL",
    ):
        env.pop(key, None)

    command = [
        sys.executable, str(ROOT / "scripts/run_dynamic_lights_profile.py"),
        "--stack", "fabric",
        "--mode", "idle",
        "--wrapper", "on",
        "--datapack", "on",
        "--seconds", str(SECONDS),
        "--scenario", scenario,
        "--exec-census",
    ]
    result = {
        "scenario": scenario,
        "status": "started",
        "command": command,
        "source_sha256": PACK_SHA256,
        "census_target_functions": [f"{NAMESPACE}:{name}" for name in TARGETS],
        "census_callee_count": len(callees),
        "cpu_timing_enabled": False,
        "spark_sampling_enabled": False,
        "compiler_optimization_enabled": False,
    }
    try:
        completed = subprocess.run(
            command, cwd=ROOT, env=env, text=True,
            capture_output=True, timeout=1500, check=False)
        (OUT / f"{scenario}-runner.stdout.log").write_text(
            completed.stdout, encoding="utf-8")
        (OUT / f"{scenario}-runner.stderr.log").write_text(
            completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(
                f"Dynamic Lights {scenario} census runner failed ({completed.returncode}): "
                f"{completed.stderr[-1800:]}")
        new = set(output_root.glob("dynamic-lights-*/results.json")) - previous
        if len(new) != 1:
            raise AssertionError(
                f"Expected one new Dynamic Lights {scenario} result manifest, got {len(new)}")
        manifest_path = new.pop()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("datapack_sha256") != PACK_SHA256:
            raise AssertionError("Dynamic Lights publisher SHA changed in runtime manifest")
        if manifest.get("datapack") != "on" or manifest.get("stack") != "fabric":
            raise AssertionError("Dynamic Lights runtime stack/datapack mismatch")
        if not manifest.get("compiler_exec_census_enabled"):
            raise AssertionError("Runtime manifest did not attest execution census mode")
        if manifest.get("spark_sampling") is not None:
            raise AssertionError("Spark sampling unexpectedly active during execution census")
        motion = manifest.get("item_motion")
        if not motion or motion.get("scenario") != scenario:
            raise AssertionError("Runtime manifest lacks matched item-motion validation")
        if scenario == "moving" and motion.get("moved_item_count") != 24:
            raise AssertionError(f"Moving fixture failed to move all 24 items: {motion!r}")
        if scenario == "stationary" and motion.get("maximum_displacement_blocks", 1) > 0.05:
            raise AssertionError(f"Stationary fixture unexpectedly moved: {motion!r}")

        census_path = manifest_path.parent / "exec-census.log"
        if not census_path.is_file():
            raise AssertionError("Runner did not preserve the execution census log")
        shutil.copy2(manifest_path, OUT / f"{scenario}-results.json")
        shutil.copy2(census_path, OUT / f"{scenario}-exec-census.log")
        result["runtime_manifest"] = manifest
        result["census"] = parse_exec_census(census_path, callees)
        result["status"] = "accepted_dynamic_function_call_census"
        print("IR032_DYNAMIC_CENSUS " + json.dumps({
            "scenario": scenario,
            "status": result["status"],
            "items_moved": motion["moved_item_count"],
            "mean_displacement": motion["mean_displacement_blocks"],
            "total_function_call_tasks": result["census"]["total_function_call_tasks"],
            "top_callees": result["census"]["top_callees"][:10],
        }, sort_keys=True), flush=True)
        return result
    except Exception as exc:
        result["status"] = "invalid_census_run"
        result["error"] = repr(exc)
        raise
    finally:
        (OUT / f"{scenario}.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not INVENTORY.is_file():
        raise FileNotFoundError(f"Run exact publisher source census first: {INVENTORY}")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    if inventory.get("publisher_sha256") != PACK_SHA256:
        raise AssertionError("Source census and runtime publisher SHA differ")
    callees = inventory.get("tick_reachable_functions", [])
    if not callees or len(callees) > 96:
        raise AssertionError(f"Exact recurring tick callee allowlist size invalid: {len(callees)}")
    if any(not name.startswith(NAMESPACE + ":") for name in callees):
        raise AssertionError("Tick callee allowlist escaped exact Dynamic Lights namespace")
    known = set(callees)
    missing = [f"{NAMESPACE}:{name}" for name in TARGETS if f"{NAMESPACE}:{name}" not in known]
    if missing:
        raise AssertionError(f"Selected target functions missing from exact source graph: {missing}")

    report = {
        "milestone": "COMPILER-IR-032-GATE-B",
        "status": "started",
        "publisher_sha256": PACK_SHA256,
        "scenario_order": list(SCENARIOS),
        "seconds_per_scenario": SECONDS,
        "target_functions": [f"{NAMESPACE}:{name}" for name in TARGETS],
        "callee_allowlist": callees,
        "cpu_timing_enabled": False,
        "spark_sampling_enabled": False,
        "compiler_optimization_enabled": False,
        "results": {},
    }
    try:
        for scenario in SCENARIOS:
            report["results"][scenario] = run_scenario(scenario, callees)
            (OUT / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
        stationary = report["results"]["stationary"]["census"]["callee_counts"]
        moving = report["results"]["moving"]["census"]["callee_counts"]
        deltas = {
            name: moving.get(name, 0) - stationary.get(name, 0)
            for name in callees
        }
        report["moving_minus_stationary_function_call_tasks"] = dict(
            sorted(deltas.items(), key=lambda item: item[1], reverse=True))
        report["status"] = "accepted_dynamic_lights_stationary_vs_moving_function_census"
        report["cpu_hot_path_proven"] = False
        report["optimization_implemented"] = False
        print("IR032_DYNAMIC_CENSUS_SUMMARY " + json.dumps({
            "status": report["status"],
            "stationary_call_tasks": report["results"]["stationary"]["census"]["total_function_call_tasks"],
            "moving_call_tasks": report["results"]["moving"]["census"]["total_function_call_tasks"],
            "largest_moving_call_deltas": list(report["moving_minus_stationary_function_call_tasks"].items())[:12],
            "cpu_timing": False,
        }, sort_keys=True), flush=True)
    except Exception as exc:
        report["status"] = "invalid_dynamic_lights_census"
        report["error"] = repr(exc)
        raise
    finally:
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
