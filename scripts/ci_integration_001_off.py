#!/usr/bin/env python3
"""Integration-001: installed/default-off main and candidate on the same host."""
import json, os, statistics as stats, sys, time
from pathlib import Path
import ci_typed_ir017 as base
from ci_typed_ir008 import find_server_thread, server_cpu_ns
from benchmark_noise_telemetry import snapshot_jvm_environment, delta_environment

CANDIDATE=Path(__file__).resolve().parents[1]
MAIN=Path(sys.argv[1]).resolve()
OUT=CANDIDATE/"build/reports/INTEGRATION-001-OFF"
SCHEDULE=("main","candidate","candidate","main","candidate","main","main","candidate")
QUOTAS=(1,2,3,4,5,8,12,24,64,65536)
BLOCK=[
    "scoreboard players add #x fc_ir 1",
    "execute if score #g fc_ir matches 7 if score #x fc_ir matches 1.. run scoreboard players add #z fc_ir 1",
    "execute if score #g fc_ir matches 7 run function fc_ir:integration_child",
    "function fc_ir:integration_child",
]
BLOCKS=1024
FIXTURES={"integration_child":["scoreboard players add #y fc_ir 1"],
          "integration_small":BLOCK*8,"integration_perf":BLOCK*BLOCKS}
MIN_CPU=500_000_000
TARGET_CPU=3_000_000_000
LIMIT=.05
def reset(c):
    c.command("gamerule minecraft:max_command_sequence_length 65536")
    for h,v in (("x",0),("y",0),("z",0),("g",7)):
        c.command(f"scoreboard players set #{h} fc_ir {v}")
def snapshot(c):
    return {h:base.nullable_score(c,"#"+h,"fc_ir") for h in ("x","y","z","g")}
def expected(n):
    return {"x":n,"y":2*n,"z":n,"g":7}
def invoke(c,name):
    return c.command("function fc_ir:"+name)
def parity(c):
    cases={}
    for q in QUOTAS:
        reset(c)
        c.command(f"gamerule minecraft:max_command_sequence_length {q}")
        invoke(c,"integration_small")
        c.command("gamerule minecraft:max_command_sequence_length 65536")
        cases[str(q)]=snapshot(c)
    if cases["65536"]!=expected(8):
        raise AssertionError("small native workload not fully executed "+str(cases))
    return cases
def save(r):
    (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
def boot(arm,index,batches,r):
    root=MAIN if arm=="main" else CANDIDATE
    base.ROOT=root
    base.RUNS=root/"run"
    base.OUT=OUT
    base.FUNCTIONS=FIXTURES
    base.options=lambda mode:{}
    proc,c,log=base.start("native")
    b={"arm":arm,"index":index,"status":"started","calibration":[],"warmup":[],"holdout":[],"timed":[]}
    r["boots"].append(b)
    try:
        status=c.command("functioncompiler status")
        if "wrapper_enabled=false" not in status:
            raise AssertionError("not default-off "+status)
        b["status_reply"]=status
        if "frozen" not in c.command("tick freeze").lower():
            raise AssertionError("tick freeze failed")
        b["parity"]=parity(c)
        if index and b["parity"]!=r["boots"][0]["parity"]:
            raise AssertionError("native default-off parity mismatch")
        thread=find_server_thread(proc.pid)
        def window(n):
            reset(c)
            e0=snapshot_jvm_environment(thread[0])
            t0=server_cpu_ns(thread);w0=time.monotonic_ns()
            for _ in range(n): invoke(c,"integration_perf")
            elapsed=server_cpu_ns(thread)-t0
            wall=time.monotonic_ns()-w0
            e1=snapshot_jvm_environment(thread[0])
            state=snapshot(c)
            if state!=expected(n*BLOCKS):
                raise AssertionError("exact work mismatch "+str(state))
            return {"cpu_ns":elapsed,"wall_ns":wall,"calls":n,
                    "state":state,"environment":delta_environment(e0,e1)}
        if batches is None:
            batches=8
            while batches<=4096:
                sample=window(batches)
                b["calibration"].append(sample)
                save(r)
                if sample["cpu_ns"]>=TARGET_CPU:break
                batches*=2
            if batches>4096:raise AssertionError("calibration unqualified")
        b["fixed_batches"]=batches
        def spread(samples):
            v=[s["cpu_ns"] for s in samples]
            return (max(v)-min(v))/stats.median(v)
        for _ in range(24):
            b["warmup"].append(window(batches));save(r)
            last=b["warmup"][-6:]
            if len(last)==6 and min(s["cpu_ns"] for s in last)>=MIN_CPU and spread(last)<=LIMIT:break
        else:
            b["status"]="warmup_unqualified";return batches
        b["holdout"]=[window(batches) for _ in range(2)]
        if spread(b["warmup"][-6:]+b["holdout"])>LIMIT or min(s["cpu_ns"] for s in b["holdout"])<MIN_CPU:
            b["status"]="holdout_unqualified";return batches
        b["timed"]=[window(batches) for _ in range(8)]
        if min(s["cpu_ns"] for s in b["timed"])<MIN_CPU or spread(b["timed"])>LIMIT:
            b["status"]="timed_unqualified";return batches
        b["median_cpu_ns"]=stats.median(s["cpu_ns"] for s in b["timed"])
        b["status"]="complete"
        return batches
    finally:
        base.stop(proc,c,log)
        (OUT/"native.server.log").rename(OUT/f"boot-{index}-{arm}.server.log")
        save(r)
        print("INTEGRATION_OFF_BOOT "+json.dumps({k:b.get(k) for k in ("index","arm","status","fixed_batches","median_cpu_ns","parity")}),flush=True)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for key in list(os.environ):
        if key.startswith("FC_"):del os.environ[key]
    r={"status":"started","schedule":SCHEDULE,"boots":[],"limit":LIMIT,"production_promotion":False}
    batches=None
    try:
        for index,arm in enumerate(SCHEDULE):
            batches=boot(arm,index,batches,r)
        if any(b["status"]!="complete" for b in r["boots"]):
            r["status"]="inconclusive"
            print("INTEGRATION_OFF_SUMMARY "+json.dumps({"status":r["status"],"gate_pass":False,"boot_statuses":[b["status"] for b in r["boots"]]}),flush=True)
            return
        blocks=[]
        for i in (0,4):
            m=[x["median_cpu_ns"] for x in r["boots"][i:i+4] if x["arm"]=="main"]
            c=[x["median_cpu_ns"] for x in r["boots"][i:i+4] if x["arm"]=="candidate"]
            blocks.append({"main_aa":abs(m[1]/m[0]-1),"candidate_aa":abs(c[1]/c[0]-1),
                           "candidate_over_main":stats.median(c)/stats.median(m)})
        r["blocks"]=blocks
        qualified=all(max(b["main_aa"],b["candidate_aa"])<=LIMIT for b in blocks)
        r["gate_pass"]=qualified and all(b["candidate_over_main"]<=1+LIMIT for b in blocks)
        r["status"]="accepted" if r["gate_pass"] else ("regression" if qualified else "inconclusive")
        print("INTEGRATION_OFF_SUMMARY "+json.dumps({"status":r["status"],"gate_pass":r["gate_pass"],"blocks":blocks}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e));raise
    finally:save(r)
if __name__=="__main__":main()
