#!/usr/bin/env python3
"""IR043 same-JVM native vs typed dispatch with IR042 calibrated gates."""
from __future__ import annotations
import json,statistics as stats
import ci_typed_ir017 as base
import ci_typed_ir042_attribution as protocol
import ci_typed_ir041 as prior
from ci_typed_ir038 import stat

OUT=base.ROOT/"build/reports/COMPILER-IR-043-CPU"
ARMS=("native","typed")
SOURCE=[
    "execute if score #g fc_ir matches 0 run function fc_native:ir043_child",
    "execute if score #g fc_ir matches 7 run function fc_native:ir043_child",
    "execute if score #g fc_ir matches 5.. if score #g fc_ir matches ..4 run function fc_native:ir043_child",
    "execute if score #g fc_ir matches 5.. if score #g fc_ir matches 1.. if score #g fc_ir < #y fc_ir if score #y fc_ir > #g fc_ir run function fc_native:ir043_child",
]*16
CHILD=["scoreboard players add #x fc_ir 1"]
DIAGNOSTIC=False
ORIGINAL_FIXTURE=base.fixture

def options(mode):
    flags=protocol.options(mode)
    flags.update({"FC_TYPED_IR043_BENCHMARK":"true","FC_TYPED_IR_DISPATCH":"true",
        "FC_TYPED_IR_DIAGNOSTICS":str(DIAGNOSTIC).lower(),
        "FC_IR041_COMPILE_TIMING":"false","FC_TYPED_IR040_BENCHMARK":"true",
        "FC_TYPED_IR042_BENCHMARK":"false","FC_TYPED_IR_ARITHMETIC":"false"})
    return flags

def fixture(work):
    ORIGINAL_FIXTURE(work)
    folder=work/"world/datapacks"/base.PACK/"data/fc_native/function"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"ir017_ir043_perf.mcfunction").write_text("\n".join(SOURCE)+"\n")
    (folder/"ir043_child.mcfunction").write_text("\n".join(CHILD)+"\n")

def prepare(client,arm):
    answer=client.command("fc_ir012_direct off")
    if "enabled=false" not in answer:raise AssertionError("direct scheduler unexpectedly on")
    prior.prepare(client,"compound")

def batch(client,arm,calls=protocol.CALLS):
    return ORIGINAL_BATCH(client,"dispatch_"+arm,calls)

def validate(client,batches,calls=protocol.CALLS):
    state={k:base.nullable_score(client,"#"+k,"fc_ir") for k in ("x","g","y","result","observed")}
    expected={"x":32*calls*batches,"g":7,"y":9,"result":0,"observed":0}
    if state!=expected:raise AssertionError(f"exact work mismatch: {state} != {expected}")
    return state

def preflight():
    global DIAGNOSTIC
    DIAGNOSTIC=True
    proc,client,log=base.start("bytecode")
    r={}
    try:
        r["freeze"]=prior.setup(client)
        layout=client.command("functioncompiler ir016 fc_ir:ir017_ir043_perf")
        if stat(layout,"typed_calls")!=64 or "direct_candidate=false" not in layout:
            raise AssertionError("dispatch layout mismatch "+layout)
        if "no ledger entry" not in client.command("functioncompiler ir016 fc_native:ir017_ir043_perf"):
            raise AssertionError("native twin compiled")
        r["layout"]=layout
        r["arms"]={}
        for arm in ARMS:
            prepare(client,arm)
            before=client.command("functioncompiler ir008")
            batch(client,arm,128)
            state=validate(client,1,128)
            after=client.command("functioncompiler ir008")
            d={k:stat(after,k)-stat(before,k) for k in
                 ("ir043_entered","ir043_calls","ir043_skipped","ir043_fallbacks",
                  "ir043_reused","ir043_proofs","ir043_empty_debits")}
            if arm=="native" and any(d.values()):raise AssertionError("native dispatch path drift")
            if arm=="typed":
                if (d["ir043_entered"],d["ir043_calls"],d["ir043_skipped"],d["ir043_fallbacks"])!=(8192,4096,4096,0):
                    raise AssertionError("typed path counts mismatch "+repr(d))
                if not(d["ir043_reused"]>0 and d["ir043_proofs"]>0):raise AssertionError("no dataflow")
            r["arms"][arm]={"state":state,"delta":d}
    finally:
        protocol.stop(proc,client,log,"diagnostic")
        DIAGNOSTIC=False
        protocol.save("diagnostic-preflight",r)
    print("IR043_CPU_PREFLIGHT "+json.dumps(r),flush=True)
    return r

ORIGINAL_BATCH=protocol.batch

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=protocol.OUT=OUT
    base.FUNCTIONS={"ir017_ir043_perf":SOURCE}
    base.fixture=fixture
    base.options=options
    protocol.ARMS=ARMS
    protocol.PAIRS=(("native","native"),("native","typed"),("typed","typed"))
    protocol.prepare=prepare
    protocol.batch=batch
    protocol.validate=validate
    r={"status":"started","boots":[],"production_promotion":False}
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
        r["summary"]={"boot_statuses":[b["status"] for b in r["boots"]],"max_absolute_aa":aa,
            "paired_reductions":reductions,"boot_medians":medians,
            "median_reduction":stats.median(reductions) if reductions else None,
            "pilot_gate_pass":bool(accepted),"general_datapack_speedup":False}
        r["status"]="complete"
        print("IR043_CPU_SUMMARY "+json.dumps(r["summary"]),flush=True)
    except BaseException as error:
        r.update(status="invalid",error=repr(error))
        raise
    finally:
        protocol.save("results",r)
if __name__=="__main__":main()
