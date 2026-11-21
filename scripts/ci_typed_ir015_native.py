#!/usr/bin/env python3
"""IR-015 bounded real Vein Miner event: wrapper baseline vs guarded typed ASM.

Two independent *untimed* native Minecraft JVMs run the original SHA-pinned
ore-mining event; exact final game state is compared. Never infer speedup from
independent boot durations. Record compiler IR load and actual event counters.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

from ci_veinminer_fusion_event import STATE_FIELDS
from ci_typed_ir015_coverage import ROOT, PINS

OUT = ROOT / "build/reports/COMPILER-IR-015-NATIVE"
STUDY_MODES = ("wrapper", "typed_ir")
IR_COUNTERS = (
    "compiled_regions", "bytecode_regions", "executed_regions",
    "executed_steps", "binary_steps", "conditional_steps",
    "guarded_binary_steps",
    "fallback_steps", "reentrant_yields", "reentrant_queued_steps",
)


def counted(response: str, key: str) -> int:
    hit = re.search(rf"\b{re.escape(key)}=(\d+)", response)
    if hit is None:
        raise AssertionError(f"No IR diagnostic {key} in {response!r}")
    return int(hit.group(1))


def options(mode: str) -> dict[str, str]:
    if mode not in STUDY_MODES:
        raise ValueError(mode)
    typed = mode == "typed_ir"
    return {
        "FC_TYPED_IR_MODE": "bytecode" if typed else "",
        "FC_TYPED_IR_NAMESPACE": "vm" if typed else "",
        "FC_TYPED_IR_DIAGNOSTICS": "true" if typed else "false",
        "FC_TYPED_IR_REENTRANT_SAFE": "true" if typed else "false",
        "FC_TYPED_IR_DIRECT_FUNCTION": "false",
        "FC_TYPED_IR_SCORE_CACHE": "false",
        "FC_TYPED_IR_SINGLETON_FEEDBACK": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_RUNTIME_TRACE": "false",
    }


def run(mode: str) -> dict:
    readiness = OUT / (mode + ".readiness.json")
    cmd = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "wrapper",
        "--side", "6", "--no-spark", "--capture-timeout", "105",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(readiness),
    ]
    env = dict(os.environ)
    env.update(options(mode))
    process = subprocess.run(cmd, cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             check=False, timeout=750)
    (OUT / f"{mode}.stdout.json").write_text(process.stdout)
    (OUT / f"{mode}.stderr.txt").write_text(process.stderr)
    if process.returncode:
        raise RuntimeError(f"{mode} event invalid: exit={process.returncode}; "
                           f"stderr={process.stderr[-2000:]!r}; "
                           f"stdout={process.stdout[-2000:]!r}")
    payload = json.loads(process.stdout)
    result = payload["results"]
    if not result["valid_native_workload"]:
        raise AssertionError(f"{mode}: native 215-ore work not accepted")
    if result["work_expected"] != 215 or result["work_after"] != 215:
        raise AssertionError(f"{mode}: unexpected work {result['work_after']}")
    if result["remaining_ore"] or result["operation_markers_after"]:
        raise AssertionError(f"{mode}: incomplete native cleanup")
    state = {k: result[k] for k in STATE_FIELDS}
    answer = {
        "mode": mode, "work_verified": True, "state": state,
        "publisher_sha256": PINS["veinminer"]["sha256"],
        "profile_report": payload["output"],
        "native_event_counter_scope": "after setup and before external post-event RCON",
    }
    if mode == "typed_ir":
        before, after = result.get("typed_ir_status_before"), result.get("typed_ir_status_after")
        if not before or not after or "IR008 mode=bytecode namespace=vm" not in after:
            raise AssertionError(f"Typed compiler not active: {before!r} => {after!r}")
        pre = {k: counted(before, k) for k in IR_COUNTERS}
        post = {k: counted(after, k) for k in IR_COUNTERS}
        delta = {k: post[k] - pre[k] for k in IR_COUNTERS}
        if any(v < 0 for v in delta.values()):
            raise AssertionError("Compiler execution counters decreased")
        answer["typed_ir_at_load"] = {
            k: post[k] for k in ("compiled_regions", "bytecode_regions")
        }
        answer["typed_ir_event_deltas"] = delta
        answer["runtime_ir_execution_confirmed"] = delta["executed_steps"] > 0
        answer["direct_whole_function_scheduler_enabled"] = False
    (OUT / (mode + ".summary.json")).write_text(json.dumps(answer, indent=2) + "\n")
    print("IR015_REAL_EVENT " + json.dumps(answer, sort_keys=True), flush=True)
    return answer


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"milestone": "COMPILER-IR-015", "status": "started",
              "purpose": "real_event_coverage_and_semantics_not_performance",
              "modes": [], "production_promotion": False}
    try:
        if not Path(PINS["veinminer"]["path"]).is_file():
            raise FileNotFoundError("Original pinned source unavailable")
        import hashlib
        actual = hashlib.sha256(Path(PINS["veinminer"]["path"]).read_bytes()).hexdigest()
        if actual != PINS["veinminer"]["sha256"]:
            raise AssertionError("Original publisher SHA mismatch")
        for mode in STUDY_MODES:
            result["modes"].append(run(mode))
            (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        a, b = result["modes"]
        if a["state"] != b["state"]:
            differences = {key: {"baseline": a["state"][key], "compiled": b["state"][key]}
                           for key in STATE_FIELDS if a["state"][key] != b["state"][key]}
            raise AssertionError(f"Real Vein Miner event parity mismatch: {differences}")
        result["status"] = "accepted"
        result["native_parity"] = True
        result["runtime_ir_execution_confirmed"] = b["runtime_ir_execution_confirmed"]
        result["performance_claim"] = False
    except BaseException as error:
        result["status"] = "invalid"
        result["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print("IR015_REAL_SUMMARY " + json.dumps({
        "status": result["status"],
        "native_parity": result.get("native_parity"),
        "executed_typed_ir": result.get("runtime_ir_execution_confirmed"),
        "production_promotion": False,
        "performance_claim": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
