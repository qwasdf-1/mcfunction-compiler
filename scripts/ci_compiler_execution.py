#!/usr/bin/env python3
"""Two-arm, no-Spark dynamic entry/callback census on the pinned native event.

Not a causal speed benchmark. No scheduler Mixins or timing-based gate.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from analyze_compiler_execution import parse_exec_census, top_sites

ROOT = Path(__file__).resolve().parents[1]
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
OUT = ROOT / "build/benchmarks/COMPILER-EXEC-003"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
MODES = ("wrapper", "score-add")
TARGETS = (
    "vm:queue/drain",
    "vm:queue/enqueue_faces",
    "vm:queue/enqueue_diagonals",
    "vm:detection/upsert_target",
    "vm:detection/acquire_target",
    "vm:detection/verify_mined_stat",
    "vm:operation/claim",
    "vm:durability/damage_vanilla_pickaxe",
    "vm:admin/adjacency_faces",  # deliberate cold negative control
)


def run_arm(mode: str) -> dict:
    before = set(VEIN.glob("vein-*/results.json"))
    env = os.environ.copy()
    env["FC_COMPILER_EXEC_CENSUS"] = "true"
    env["FC_COMPILER_EXEC_CENSUS_NAMESPACE"] = "vm"
    env["FC_COMPILER_EXEC_CENSUS_FUNCTIONS"] = ",".join(TARGETS)
    command = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", mode, "--side", "6",
        "--no-spark",
    ]
    completed = subprocess.run(
        command, cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    (OUT / f"{mode}-runner.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"Native {mode} event failed; read archived runner log")
    new = set(VEIN.glob("vein-*/results.json")) - before
    if len(new) != 1:
        raise AssertionError(f"Expected exactly one native {mode} result, got {len(new)}")
    path = new.pop()
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("compiler_mode") != mode
        or result.get("datapack_sha256") != PIN
        or not result.get("valid_native_workload")
        or not result.get("compiler_exec_census_enabled")
        or result.get("compiler_exec_census_targets") != ",".join(TARGETS)
        or "FC_EXEC started" not in str(result.get("compiler_exec_census_start_status"))
        or "FC_EXEC ended" not in str(result.get("compiler_exec_census_stop_status"))
    ):
        raise AssertionError(f"Compiler {mode} event or census gates did not pass")
    census = parse_exec_census(path.parent / "exec-census.log")
    if census["namespace"] != "vm" or census["target_count"] != len(TARGETS):
        raise AssertionError("Census namespace or selected target count changed")
    if census["entries"] <= 0 or census["ordinary_callbacks"] <= 0:
        raise AssertionError("No native reached entries / ordinary callbacks recorded")
    per_function = {
        name: {
            "entry_reached": sum(
                row["entries"] for row in census["rows"] if row["function"] == name
            ),
            "ordinary_callbacks": sum(
                row["callbacks"] for row in census["rows"] if row["function"] == name
            ),
        }
        for name in TARGETS
    }
    if per_function["vm:queue/drain"]["entry_reached"] <= 0:
        raise AssertionError("Expected active queue/drain positive control")
    if per_function["vm:admin/adjacency_faces"]["entry_reached"] != 0:
        raise AssertionError("Unexpected admin command executed during mining window")
    # The data describe attempted entry processing; custom command executors
    # cannot be counted at Brigadier Command.run without changing semantics.
    if any(
        row["kind"] in {"custom_executor", "no_callback", "no_executable"}
        and row["callbacks"]
        for row in census["rows"]
    ):
        raise AssertionError("Unsupported custom executor counted as an ordinary callback")
    shutil.copy2(path.parent / "exec-census.log", OUT / f"{mode}-exec-census.log")
    output = {
        "mode": mode,
        "datapack_sha256": PIN,
        "valid_native_workload": True,
        "work_after": result.get("work_after"),
        "remaining_ore": result.get("remaining_ore"),
        "queue_head_delta": result.get("queue_head_delta"),
        "source_block_remains": result.get("source_block_remains"),
        "census": census,
        "selected_function_counts": per_function,
        "top_reached_sites": top_sites(census, 15),
        "not_a_speed_benchmark": True,
    }
    print("FC_EXEC_SUMMARY " + json.dumps({
        "mode": mode,
        "datapack_sha256": PIN,
        "valid_native_workload": True,
        "total_reached_entries": census["entries"],
        "ordinary_callbacks": census["ordinary_callbacks"],
        "function_counts": per_function,
        "top_reached_sites": output["top_reached_sites"],
        "note": "Entry reached is not terminal success; custom executors unmeasured.",
    }, sort_keys=True), flush=True)
    return output


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "study": "COMPILER-EXEC-003",
        "pin": PIN,
        "design": (
            "Opt-in, exact-function event-window entry-reaching counts, plus "
            "ordinary Brigadier callback entries. These are diagnostic not timing claims."
        ),
        "arms": {},
    }
    try:
        for mode in MODES:
            report["arms"][mode] = run_arm(mode)
            (OUT / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for key in ("work_after", "remaining_ore", "queue_head_delta", "source_block_remains"):
            a = report["arms"][MODES[0]][key]
            b = report["arms"][MODES[1]][key]
            if a is None or b is None or a != b:
                raise AssertionError(
                    f"Native workload parity field {key!r} differs: {a!r} vs {b!r}")
        report["native_pair_parity"] = True
    except Exception as exc:
        report["error"] = str(exc)
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise
    (OUT / "results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
