#!/usr/bin/env python3
"""IR047: isolate preflight reuse with IR046 enabled in both arms."""
from __future__ import annotations
import json,statistics as stats,os
import ci_typed_ir017 as base
import ci_typed_ir042_attribution as protocol
import ci_typed_ir041 as prior
import ci_typed_ir046 as native
from ci_typed_ir038 import stat
from ci_typed_ir047 import PREFLIGHT_KEYS

WORKLOAD=os.environ.get("FC_IR047_WORKLOAD","pure")
if WORKLOAD not in ("pure","mixed"):raise ValueError(WORKLOAD)
OUT=base.ROOT/("build/reports/COMPILER-IR-047-CPU-"+WORKLOAD.upper())
ARMS=("base","reuse")
SOURCE=native.wrap()+["scoreboard players add #x fc_ir 1"]
if WORKLOAD=="mixed":SOURCE=["scoreboard players set @s fc_cursor 7153",*SOURCE]
NAME="ir017_ir046_"+WORKLOAD
DIAGNOSTIC=False
ORIGINAL_SETUP=prior.setup

def options(mode):
    flags=protocol.options(mode)
    flags.update({"FC_TYPED_IR046_BENCHMARK":"true","FC_TYPED_IR_GUARD_RUN_REUSE":"true",
        "FC_TYPED_IR047_BENCHMARK":"true","FC_TYPED_IR_GUARD_PREFLIGHT_REUSE":"true",
        "FC_TYPED_IR047_TEST_OBSERVER":"false",
        "FC_TYPED_IR042_BENCHMARK":"false","FC_TYPED_IR040_BENCHMARK":"true",
        "FC_TYPED_IR_GUARD_TERMINAL":"false","FC_TYPED_IR_DISPATCH":"false",
        "FC_TYPED_IR_NATIVE_STORE":"false","FC_TYPED_IR_DATAFLOW":"true",
        "FC_TYPED_IR_SELF_HOLDER":"true","FC_TYPED_IR_COMPOUND_SCORE":"true",
        "FC_TYPED_IR_EXTENDED_SCORE":"true","FC_TYPED_IR_REENTRANT_SAFE":"true",
        "FC_TYPED_IR_DIAGNOSTICS":str(DIAGNOSTIC).lower(),"FC_IR041_COMPILE_TIMING":"false",
        "FC_TYPED_IR046_TEST_OBSERVER":"false","FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"false",
        "FC_TYPED_IR_ARITHMETIC":"false"})
    return flags

def setup(client):
    native.establish(client)
    return ORIGINAL_SETUP(client)

def prepare(client,arm):
    reply=client.command("fc_ir012_direct off")
    if "enabled=false" not in reply:raise AssertionError("direct enabled "+reply)
    expected="true" if arm=="reuse" else "false"
    reply=client.command("fc_ir046_reuse on")
    if "reuse=true" not in reply:raise AssertionError("IR046 baseline drift "+reply)
    reply=client.command("fc_ir047_preflight "+("on" if arm=="reuse" else "off"))
    if "preflight="+expected not in reply:raise AssertionError("toggle failed "+reply)
    prior.prepare(client,"compound")
    native.set_score(client,native.SELECTOR,"fc_radius",12)
    native.set_score(client,native.SELECTOR,"fc_cursor",1)

def batch(client,arm,calls=protocol.CALLS):
    token="wrap_"+WORKLOAD
    reply=client.command(f"execute as {native.SELECTOR} at @s run fc_ir040_batch {token} {calls}")
    if f"IR040_BATCH {token} {calls}" not in reply:raise AssertionError("batch failed "+reply)

def validate(client,batches,calls=protocol.CALLS):
    state={"x":base.nullable_score(client,"#x","fc_ir"),
           "radius":base.nullable_score(client,native.SELECTOR,"fc_radius"),
           "cursor":base.nullable_score(client,native.SELECTOR,"fc_cursor")}
    expected={"x":calls*batches,"radius":12,"cursor":1 if WORKLOAD=="pure" else 0}
    if state!=expected:raise AssertionError(f"exact work mismatch {state} != {expected}")
    return state

def preflight():
    global DIAGNOSTIC
    DIAGNOSTIC=True
    proc,client,log=base.start("bytecode")
    r={}
    try:
        r["freeze"]=setup(client)
        layout=base.inspect(client,NAME)
        if layout["typed_lines"]!=len(SOURCE) or layout["typed_regions"]!=1:
            raise AssertionError("layout "+str(layout))
        r["layout"]=layout
        r["arms"]={}
        for arm in ARMS:
            prepare(client,arm)
            before=client.command("functioncompiler ir008")
            batch(client,arm,128)
            state=validate(client,1,128)
            after=client.command("functioncompiler ir008")
            keys=(*native.KEYS,*PREFLIGHT_KEYS,"executed_steps","executed_regions","ir039_native_fallbacks")
            d={k:stat(after,k)-stat(before,k) for k in keys}
            if d["executed_regions"]!=128 or d["executed_steps"]!=(128 if WORKLOAD=="pure" else 384):
                raise AssertionError("work counts "+str(d))
            if d["ir039_native_fallbacks"]:raise AssertionError("unexpected fallback "+str(d))
            expected=(9*128,10*128) if WORKLOAD=="pure" else (8*128,8*128)
            if (d["ir046_boundaries"],d["ir046_present_reuse"])!=expected:
                raise AssertionError("IR046 baseline drift "+str(d))
            if d["ir046_absent_reuse"] or min(d["ir046_invalidations"],1)!=1:
                raise AssertionError("invalidations "+str(d))
            n=expected[0] if arm=="reuse" else 0
            if tuple(d[k] for k in PREFLIGHT_KEYS)!=(n,2*n,2*n,n):
                raise AssertionError("IR047 preflight path mismatch "+str(d))
            r["arms"][arm]={"state":state,"delta":d}
    finally:
        protocol.stop(proc,client,log,"diagnostic")
        DIAGNOSTIC=False
        protocol.save("diagnostic-preflight",r)
    print("IR047_CPU_PREFLIGHT "+json.dumps(r),flush=True)
    return r

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=protocol.OUT=OUT
    base.FUNCTIONS={NAME:SOURCE}
    base.options=options
    prior.setup=setup
    protocol.ARMS=ARMS
    protocol.PAIRS=(("base","base"),("base","reuse"),("reuse","reuse"))
    protocol.TOP_LEVEL_LINES=len(SOURCE)
    # Same fixed 750ms calibration and 500ms minimum, but shorter
    # exact wrap functions need more calls than the old 64-line workload.
    protocol.MAX_BATCHES=8192
    protocol.prepare=prepare
    protocol.batch=batch
    protocol.validate=validate
    r={"status":"started","workload":WORKLOAD,"source_lines":len(SOURCE),
       "boots":[],"production_promotion":False}
    try:
        r["preflight"]=preflight()
        for boot in range(protocol.BOOTS):
            r["boots"].append(protocol.run_boot(boot))
            protocol.save("results",r)
        blocks=[b for boot in r["boots"] for b in boot["blocks"]]
        aa=max((abs(b["reduction"]) for b in blocks if b["a"]==b["b"]),default=None)
        treatment=[b for b in blocks if (b["a"],b["b"])==ARMS]
        reductions=[b["reduction"] for b in treatment]
        medians=[stats.median([b["reduction"] for b in boot["blocks"] if (b["a"],b["b"])==ARMS])
                 for boot in r["boots"] if any((b["a"],b["b"])==ARMS for b in boot["blocks"])]
        accepted=(all(b["status"]=="complete" for b in r["boots"]) and aa is not None
            and aa<=protocol.AA_LIMIT and len(reductions)==2*protocol.BOOTS
            and min(reductions)>0 and min(medians)>=max(protocol.MIN_REDUCTION,2*aa)
            and all(s["cpu_ns"]>=protocol.MIN_CPU_NS for b in treatment for s in b["samples"]))
        r["summary"]={"workload":WORKLOAD,"boot_statuses":[b["status"] for b in r["boots"]],
            "max_absolute_aa":aa,"paired_reductions":reductions,"boot_medians":medians,
            "median_reduction":stats.median(reductions) if reductions else None,
            "pilot_gate_pass":bool(accepted),"general_datapack_speedup":False}
        r["status"]="complete"
        print("IR047_CPU_SUMMARY "+json.dumps(r["summary"]),flush=True)
    except BaseException as error:
        r.update(status="invalid",error=repr(error))
        raise
    finally:
        protocol.save("results",r)
if __name__=="__main__":main()
