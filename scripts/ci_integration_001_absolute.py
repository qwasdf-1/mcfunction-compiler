#!/usr/bin/env python3
"""Integration-001: same-host opt-in absolute checkpoint versus candidate."""
import json, os, statistics as stats, sys, time
from pathlib import Path
import ci_typed_ir017 as base
import ci_typed_ir047_cpu as wrap
import ci_typed_ir046 as native
from ci_typed_ir038 import stat
from ci_typed_ir008 import find_server_thread, server_cpu_ns
from benchmark_noise_telemetry import snapshot_jvm_environment, delta_environment

CANDIDATE=Path(__file__).resolve().parents[1]
MAIN=Path(sys.argv[1]).resolve()
OUT=CANDIDATE/("build/reports/INTEGRATION-001-ABSOLUTE-"+wrap.WORKLOAD.upper())
SCHEDULE=("main","candidate","candidate","main","candidate","main","main","candidate")
MIN_CPU=500_000_000
TARGET_CPU=3_000_000_000
LIMIT=.05
FIXTURES={wrap.NAME:wrap.SOURCE}
def setup(c):
    wrap.setup(c)
def verify_preflight(arm,index,r):
    root=MAIN if arm=="main" else CANDIDATE
    base.ROOT=root
    base.RUNS=root/"run"
    base.OUT=OUT
    base.FUNCTIONS=FIXTURES
    base.options=lambda mode:wrap.options(mode)|{"FC_TYPED_IR_DIAGNOSTICS":"true"}
    p,c,l=base.start("bytecode")
    try:
        setup(c)
        layout=base.inspect(c,wrap.NAME)
        assert layout["typed_regions"]==1 and layout["typed_lines"]==len(wrap.SOURCE),layout
        wrap.prepare(c,"reuse")
        before=c.command("functioncompiler ir008")
        wrap.batch(c,"reuse",128)
        state=wrap.validate(c,1,128)
        after=c.command("functioncompiler ir008")
        keys=(*native.KEYS,*wrap.PREFLIGHT_KEYS,"executed_steps","executed_regions","ir039_native_fallbacks")
        d={k:stat(after,k)-stat(before,k) for k in keys}
        n=(9 if wrap.WORKLOAD=="pure" else 8)*128
        assert tuple(d[k] for k in wrap.PREFLIGHT_KEYS)==(n,2*n,2*n,n),d
        assert d["executed_regions"]==128 and d["executed_steps"]==(128 if wrap.WORKLOAD=="pure" else 384) and d["ir039_native_fallbacks"]==0,d
        r["preflight"][arm]={"state":state,"delta":d,"layout":layout}
        if arm=="candidate":
            assert r["preflight"]["main"]["delta"]==d
            assert r["preflight"]["main"]["state"]==state
    finally:
        base.stop(p,c,l)
        (OUT/"bytecode.server.log").rename(OUT/f"preflight-{arm}.server.log")
        save(r)
def save(r):
    (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
def boot(arm,index,batches,r):
    root=MAIN if arm=="main" else CANDIDATE
    base.ROOT=root
    base.RUNS=root/"run"
    base.OUT=OUT
    base.FUNCTIONS=FIXTURES
    base.options=wrap.options
    proc,c,log=base.start("bytecode")
    b={"arm":arm,"index":index,"status":"started","calibration":[],"warmup":[],"holdout":[],"timed":[]}
    r["boots"].append(b)
    try:
        setup(c)
        b["status_reply"]=c.command("functioncompiler status")
        b["diagnostic_reply"]=c.command("functioncompiler ir008")
        thread=find_server_thread(proc.pid)
        def window(n):
            wrap.prepare(c,"reuse")
            e0=snapshot_jvm_environment(thread[0])
            t0=server_cpu_ns(thread);w0=time.monotonic_ns()
            for _ in range(n): wrap.batch(c,"reuse",1024)
            elapsed=server_cpu_ns(thread)-t0
            wall=time.monotonic_ns()-w0
            e1=snapshot_jvm_environment(thread[0])
            state=wrap.validate(c,n,1024)
            return {"cpu_ns":elapsed,"wall_ns":wall,"calls":n,
                    "state":state,"environment":delta_environment(e0,e1)}
        if batches is None:
            batches=8
            while batches<=32768:
                sample=window(batches)
                b["calibration"].append(sample)
                save(r)
                if sample["cpu_ns"]>=TARGET_CPU:break
                batches*=2
            if batches>32768:raise AssertionError("calibration unqualified")
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
        (OUT/"bytecode.server.log").rename(OUT/f"boot-{index}-{arm}.server.log")
        save(r)
        print("INTEGRATION_ABSOLUTE_BOOT "+json.dumps({k:b.get(k) for k in ("index","arm","status","fixed_batches","median_cpu_ns","parity")}),flush=True)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for key in list(os.environ):
        if key.startswith("FC_"):del os.environ[key]
    r={"status":"started","schedule":SCHEDULE,"boots":[],"limit":LIMIT,"production_promotion":False,"preflight":{},"workload":wrap.WORKLOAD,"baseline":"checkpoint/ir047-accepted","fixture_build":True}
    batches=None
    try:
        for arm in ("main","candidate"):verify_preflight(arm,0,r)
        for index,arm in enumerate(SCHEDULE):
            batches=boot(arm,index,batches,r)
        if any(b["status"]!="complete" for b in r["boots"]):
            r["status"]="inconclusive"
            print("INTEGRATION_ABSOLUTE_SUMMARY "+json.dumps({"status":r["status"],"gate_pass":False,"boot_statuses":[b["status"] for b in r["boots"]]}),flush=True)
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
        print("INTEGRATION_ABSOLUTE_SUMMARY "+json.dumps({"status":r["status"],"gate_pass":r["gate_pass"],"blocks":blocks}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e));raise
    finally:save(r)
if __name__=="__main__":main()
