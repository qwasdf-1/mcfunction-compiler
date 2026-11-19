#!/usr/bin/env python3
"""COMPILER-QUEUE-005: exact 3-function runtime call/entry census, no CPU claim."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from analyze_compiler_execution import parse_exec_census, top_sites

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/benchmarks/COMPILER-QUEUE-005-EXEC"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
TARGETS = (
    "vm:queue/enqueue_faces",
    "vm:queue/enqueue_diagonals",
    "vm:queue/enqueue_here",
    "vm:queue/enqueue_match",
    "vm:queue/append_here",
    "vm:admin/adjacency_faces",
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "results.json"
    before = set(VEIN.glob("vein-*/results.json"))
    env = os.environ.copy()
    env["FC_COMPILER_EXEC_CENSUS"] = "true"
    env["FC_COMPILER_EXEC_CENSUS_NAMESPACE"] = "vm"
    env["FC_COMPILER_EXEC_CENSUS_FUNCTIONS"] = ",".join(TARGETS)
    for key in ("FC_CPU004_MODE", "FC_CPU004_NAMESPACE", "FC_COMPILER_ACCEPTANCE_AUDIT"):
        env.pop(key, None)
    cmd = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper", "--side", "6",
        "--no-spark", "--capture-timeout", "150",
    ]
    complete = subprocess.run(
        cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=750
    )
    (OUT / "runner.stdout.log").write_text(complete.stdout, encoding="utf-8")
    (OUT / "runner.stderr.log").write_text(complete.stderr, encoding="utf-8")
    if complete.returncode:
        raise RuntimeError(
            f"QUEUE005 native event failed, exit={complete.returncode}, "
            f"stderr={complete.stderr[-1200:]!r}")
    new = set(VEIN.glob("vein-*/results.json")) - before
    if len(new) != 1:
        raise AssertionError(f"Expected one new native event, found {len(new)}")
    result_path = new.pop()
    state = json.loads(result_path.read_text(encoding="utf-8"))
    if (
        not state.get("valid_native_workload")
        or state.get("compiler_mode") != "wrapper"
        or state.get("datapack_sha256") != PIN
        or not state.get("compiler_exec_census_enabled")
        or state.get("compiler_exec_census_targets") != ",".join(TARGETS)
        or state.get("queue_head_delta") != 1952
        or state.get("work_after") != 215
        or state.get("run_state_after") != 0
    ):
        raise AssertionError("Pinned QUEUE005 native source/event/diagnostic gate failed")
    census = parse_exec_census(result_path.parent / "exec-census.log")
    if census["namespace"] != "vm" or census["target_count"] != len(TARGETS):
        raise AssertionError("Unexpected namespace or target count")
    counts = {
        name: {
            "entries": sum(r["entries"] for r in census["rows"] if r["function"] == name),
            "callbacks": sum(r["callbacks"] for r in census["rows"] if r["function"] == name),
            "sites": sum(1 for r in census["rows"] if r["function"] == name),
        } for name in TARGETS
    }
    if (counts["vm:queue/enqueue_faces"]["entries"] != 1296 or
        counts["vm:queue/enqueue_diagonals"]["entries"] != 4320 or
        counts["vm:admin/adjacency_faces"]["entries"] != 0):
        raise AssertionError("Parent entries or cold-control do not match accepted event")
    if counts["vm:queue/enqueue_here"]["entries"] != 5616:
        raise AssertionError("Expected 5,616 reached enqueue_here delegation entries")
    if counts["vm:queue/enqueue_match"]["entries"] != 5616:
        raise AssertionError("Expected 5,616 reached macro-predicate entries")
    append = [r for r in census["rows"] if r["function"] == "vm:queue/append_here"]
    if len(append) != 5:
        raise AssertionError(f"Pinned append_here body expected 5 commands, got {len(append)}")
    app_calls = {r["entries"] for r in append}
    if len(app_calls) != 1 or min(app_calls) <= 0:
        raise AssertionError("Expected all five append body entries to be reached equally")
    selected = {
        "source_sha256": PIN, "valid_native_workload": True,
        "functions": counts, "append_here_calls": next(iter(app_calls)),
        "append_here_site_rows": sorted(append, key=lambda r: r["index"]),
        "census": census, "no_cpu_or_speedup_claim": True,
    }
    shutil.copy2(result_path.parent / "exec-census.log", OUT / "exec-census.log")
    report_path.write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    print("QUEUE005_EXEC_SUMMARY " + json.dumps({
        "counts": counts, "append_here_calls": selected["append_here_calls"],
        "append_here_rows": selected["append_here_site_rows"],
        "source_sha256": PIN,
        "note": "Actual function entry reaching, not semantic success or CPU.",
    }, sort_keys=True), flush=True)
    print("QUEUE005_EXEC_TOP " + json.dumps(top_sites(census, 18)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
