#!/usr/bin/env python3
"""IR-018: pinned real Vein Miner 215-block gameplay, old vs selector-aware IR.

Three separate Minecraft 26.3/Java25 JVMs execute identical original publisher
source; no CPU timing, claimed speedup, or production promotion. Both compiler
arms retain IR-017 ranged-guard support; only FC_TYPED_IR_SELF_HOLDER changes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import ci_typed_ir015_native as study
from ci_typed_ir015_coverage import ROOT, PINS

OUT = ROOT / "build/reports/COMPILER-IR-018-REAL"
ARMS = ("wrapper", "old_bytecode", "self_bytecode")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pin=PINS["veinminer"]
    source=Path(pin["path"])
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=pin["sha256"]:
        raise AssertionError("Pinned original Vein Miner ZIP missing or SHA-256 mismatch")
    result={"milestone":"COMPILER-IR-018-REAL","status":"started",
            "publisher_sha256":pin["sha256"],
            "arms":[],"performance_claim":False,"production_promotion":False}
    before={k:os.environ.get(k) for k in ("FC_TYPED_IR_SELF_HOLDER",
                                        "FC_TYPED_IR_RANGE_GUARDS")}
    try:
        for arm in ARMS:
            study.OUT=OUT/arm
            study.OUT.mkdir(parents=True,exist_ok=True)
            os.environ["FC_TYPED_IR_SELF_HOLDER"]=str(arm=="self_bytecode").lower()
            os.environ["FC_TYPED_IR_RANGE_GUARDS"]="true"
            mode="wrapper" if arm=="wrapper" else "typed_ir"
            data=study.run(mode)
            data["arm"]=arm
            data["self_holder_feature"]=arm=="self_bytecode"
            result["arms"].append(data)
            (OUT/"results.json").write_text(json.dumps(result,indent=2)+"\n")
        reference=result["arms"][0]["state"]
        for arm in result["arms"][1:]:
            if arm["state"]!=reference:
                bad={k:{"baseline":reference[k],"compiled":arm["state"][k]}
                     for k in reference if reference[k]!=arm["state"][k]}
                raise AssertionError(f"Real mining state divergence {arm['arm']}: {bad}")
            if not arm["runtime_ir_execution_confirmed"]:
                raise AssertionError(f"No real compiled execution: {arm['arm']}")
        result["status"]="accepted"
        result["native_semantic_parity"]=True
        result["bytecode_coverage_not_cpu"]={
            arm["arm"]:{
                "compiled_load":arm.get("typed_ir_at_load"),
                "event":arm.get("typed_ir_event_deltas"),
            } for arm in result["arms"][1:]
        }
    except BaseException as error:
        result["status"]="invalid"
        result["error"]=repr(error)
        raise
    finally:
        for key,value in before.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
        (OUT/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    print("IR018_REAL_SUMMARY "+json.dumps({
        "status":result["status"],"native_semantic_parity":True,
        "bytecode_coverage_not_cpu":result["bytecode_coverage_not_cpu"],
        "performance_claim":False,"production_promotion":False
    },sort_keys=True),flush=True)


if __name__ == "__main__":
    main()
