#!/usr/bin/env python3
"""Two native, diagnostic-only Vein Miner acceptance arms. Not a speed benchmark."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from analyze_compiler_acceptance import parse_acceptance_log

ROOT = Path(__file__).resolve().parents[1]
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
OUT = ROOT / "build/benchmarks/COMPILER-ACCEPTANCE-002"
PACK_SHA = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
MODES = ("selective-macro", "score-add")


def run_arm(mode: str) -> dict:
    before = set(VEIN.glob("vein-*/results.json"))
    cmd = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", mode, "--side", "6", "--no-spark",
    ]
    if mode == "selective-macro":
        cmd.append("--count-selective-macro-arguments")
    env = os.environ.copy()
    env["FC_COMPILER_ACCEPTANCE_AUDIT"] = "true"
    env["FC_COMPILER_ACCEPTANCE_NAMESPACE"] = "vm"
    completed = subprocess.run(cmd, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUT / f"{mode}-runner.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"{mode} native event failed: see runner log")
    after = set(VEIN.glob("vein-*/results.json"))
    new = after - before
    if len(new) != 1:
        raise RuntimeError(f"Expected one new {mode} result, got {len(new)}")
    result_path = new.pop()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if (not result.get("valid_native_workload")
            or result.get("datapack_sha256") != PACK_SHA
            or result.get("compiler_mode") != mode
            or not result.get("compiler_acceptance_audit_enabled")):
        raise AssertionError(f"Native event or source pin not accepted: {mode}")
    # The full audit is collected after the server shuts down.
    result_dir = result_path.parent
    audit = parse_acceptance_log(result_dir / "acceptance.log")
    if audit["namespace"] != "vm":
        raise AssertionError("Acceptance census was not restricted to vm")
    shutil.copy2(result_dir / "acceptance.log", OUT / f"{mode}-acceptance.log")
    if mode == "selective-macro":
        if audit["outcomes"].get("macro_parser_gate_off", 0) <= 0:
            raise AssertionError("Macro-disabled parser control did not activate")
        if result.get("selective_macro_argument_calls_delta", 0) <= 0:
            raise AssertionError("Selective macro fast-path control did not activate")
    else:
        installed = (
            audit["outcomes"].get("bare_terminal_installed", 0)
            + audit["outcomes"].get("chain_terminal_only", 0)
            + audit["outcomes"].get("chain_fully_lowered", 0)
        )
        if installed <= 0:
            raise AssertionError("Enabled compiler produced no accepted candidates")
    return {
        "mode": mode,
        "native_workload_valid": result["valid_native_workload"],
        "source_sha256": result["datapack_sha256"],
        "compiler_mode": result["compiler_mode"],
        "selective_argument_hits": result.get("selective_macro_argument_calls_delta"),
        "score_add_executed_delta": result.get("score_add_executed_delta"),
        "acceptance": audit,
        "timing_not_comparable": True,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "study": "COMPILER-ACCEPTANCE-002",
        "interpretation": (
            "Parser acceptance/install counts and macro expansion/cache occurrences "
            "are not per-command execution, exclusive CPU, or potential speedup."
        ),
        "arms": {},
    }
    try:
        for mode in MODES:
            report["arms"][mode] = run_arm(mode)
            audit = report["arms"][mode]["acceptance"]
            missed = [
                row for row in audit["rows"]
                if row["outcome"] in (
                    "bare_declined", "chain_executable_declined", "chain_terminal_only")
            ]
            missed.sort(key=lambda row: (-row["count"], row["function"], row["input"]))
            print("FC_ACCEPTANCE_SUMMARY " + json.dumps({
                "mode": mode,
                "source_sha256": report["arms"][mode]["source_sha256"],
                "native_workload_valid": report["arms"][mode]["native_workload_valid"],
                "selective_argument_hits": report["arms"][mode]["selective_argument_hits"],
                "outcomes": audit["outcomes"],
                "top_missed_patterns_by_compile_attempts": missed[:15],
                "note": "Counts are parser/expansion events, not command execution or CPU.",
            }, sort_keys=True), flush=True)
            (OUT / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        report["error"] = str(exc)
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
