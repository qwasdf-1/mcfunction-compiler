#!/usr/bin/env python3
"""IR-017 real-publisher 215-block event: vanilla vs old/new typed ASM.

This is an *execution activation and semantic* study, never a CPU benchmark.
Each arm boots a new native Minecraft 26.3 Java25 JVM. The publisher Vein Miner
5.3.0 ZIP is identical, verified via independently pinned SHA-256. We record
event-local typed step counts but do not treat boot-to-boot differences as
performance, since the event work and Minecraft tick schedule are not paired.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import hashlib

import ci_typed_ir015_native as study
from ci_typed_ir015_coverage import ROOT, PINS

OUT = ROOT / "build/reports/COMPILER-IR-017-REAL"
ARMS = ("wrapper", "old_bytecode", "ir017_bytecode")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pin = PINS["veinminer"]
    path = Path(pin["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
        raise AssertionError("Original publisher ZIP absent or SHA-256 mismatch")
    report = {"milestone": "COMPILER-IR-017-REAL", "status": "started",
              "purpose": "original_workload_compiler_coverage_and_semantics",
              "publisher_sha256": pin["sha256"], "arms": [],
              "performance_claim": False, "production_promotion": False}
    previous = os.environ.get("FC_TYPED_IR_RANGE_GUARDS")
    try:
        for arm in ARMS:
            study.OUT = OUT / arm
            study.OUT.mkdir(parents=True, exist_ok=True)
            flag = arm == "ir017_bytecode"
            os.environ["FC_TYPED_IR_RANGE_GUARDS"] = str(flag).lower()
            mode = "wrapper" if arm == "wrapper" else "typed_ir"
            observation = study.run(mode)
            observation["arm"] = arm
            observation["range_guards_enabled"] = flag
            report["arms"].append(observation)
            (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        ref = report["arms"][0]["state"]
        if any(x["state"] != ref for x in report["arms"][1:]):
            raise AssertionError("Pinned publisher mining event diverged from vanilla wrapper")
        if any(not x["runtime_ir_execution_confirmed"] for x in report["arms"][1:]):
            raise AssertionError("Old or new actual JVM bytecode never executed")
        report["native_semantic_parity"] = True
        report["status"] = "accepted"
        report["coverage_delta_not_cpu"] = {
            "bytecode_regions_load": {
                arm["arm"]: arm.get("typed_ir_at_load", {}).get("bytecode_regions")
                for arm in report["arms"][1:]
            },
            "event_typed_steps": {
                arm["arm"]: arm.get("typed_ir_event_deltas", {}).get("executed_steps")
                for arm in report["arms"][1:]
            },
            "event_guarded_binary_steps": {
                arm["arm"]: arm.get("typed_ir_event_deltas", {}).get("guarded_binary_steps")
                for arm in report["arms"][1:]
            },
        }
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        if previous is None:
            os.environ.pop("FC_TYPED_IR_RANGE_GUARDS", None)
        else:
            os.environ["FC_TYPED_IR_RANGE_GUARDS"] = previous
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR017_REAL_SUMMARY " + json.dumps({
        "status": report["status"], "native_semantic_parity": report["native_semantic_parity"],
        "coverage_delta_not_cpu": report["coverage_delta_not_cpu"],
        "performance_claim": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
