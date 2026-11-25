#!/usr/bin/env python3
"""IR042 five-mode same-JVM attribution with calibrated >=500ms CPU windows."""
from __future__ import annotations
import json, re, statistics as stats, time, math
from pathlib import Path
import ci_typed_ir017 as base
import ci_typed_ir041 as prior
from ci_typed_ir008 import find_server_thread, server_cpu_ns
from ci_typed_ir038 import stat
from benchmark_noise_telemetry import snapshot_jvm_environment,delta_environment

OUT=base.ROOT/"build/reports/COMPILER-IR-042-ATTRIBUTION"
ARMS=("native","interp","base","flow","direct")
CONTRASTS=(("native","interp"),("interp","base"),("base","flow"),("flow","direct"),("native","flow"))
PAIRS=(("native","native"),("native","interp"),("interp","interp"),("interp","base"),
       ("base","base"),("base","flow"),("flow","flow"),("flow","direct"),("direct","direct"),("native","flow"))
CALLS=1024
START_BATCHES=8
MAX_BATCHES=256
MIN_CPU_NS=500_000_000
CALIBRATION_TARGET_NS=750_000_000
MIN_ROUNDS=6
MAX_ROUNDS=12
STABLE_WINDOWS=6
HOLDOUT_ROUNDS=2
AA_LIMIT=.05
MIN_REDUCTION=.05
BOOTS=2
DIAGNOSTIC=False
SOURCE=prior.COMMANDS["compound"]
ORIGINAL_FIXTURE=base.fixture

def options(mode):
    flags=prior.options(mode)
    flags.update({"FC_TYPED_IR042_BENCHMARK":"true","FC_IR041_COMPILE_TIMING":str(DIAGNOSTIC).lower(),
        "FC_TYPED_IR_DIAGNOSTICS":str(DIAGNOSTIC).lower(),"FC_TYPED_IR_COST_POLICY":"",
        "FC_IR042_COMPILE_TARGET":"","FC_COMPILER_EXEC_CENSUS":"false"})
    return flags

def fixture(work):
    ORIGINAL_FIXTURE(work)
    folder=work/"world/datapacks"/base.PACK/"data/fc_native/function"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"ir017_ir040_perf.mcfunction").write_text("\n".join(SOURCE)+"\n")

def prepare(client,arm):
    answer=client.command("fc_ir012_direct "+("on" if arm=="direct" else "off"))
    if "enabled="+str(arm=="direct").lower() not in answer:
        raise AssertionError("scheduler toggle failed: "+answer)
    prior.prepare(client,"compound")

def batch(client,arm,calls=CALLS):
    response=client.command(f"fc_ir040_batch {arm} {calls}")
    if f"IR040_BATCH {arm} {calls}" not in response:raise AssertionError("batch failed: "+response)

def validate(client,batches,calls=CALLS):
    actual={k:base.nullable_score(client,"#"+k,"fc_ir") for k in ("x","g","y","result","observed")}
    expected={"x":48*calls*batches,"g":7,"y":9,"result":0,"observed":0}
    if actual!=expected:raise AssertionError(f"exact work mismatch {actual} != {expected}")
    return actual

def save(name,r):
    (OUT/(name+".json")).write_text(json.dumps(r,indent=2)+"\n")

def stop(proc,client,log,name):
    base.stop(proc,client,log)
    p=OUT/"bytecode.server.log"
    if p.exists():p.rename(OUT/(name+".server.log"))

def preflight():
    global DIAGNOSTIC
    DIAGNOSTIC=True
    proc,client,log=base.start("bytecode")
    r={}
    try:
        r["freeze"]=prior.setup(client)
        ids={"interp":"ir017_ir042_interp","base":"ir017_ir040_perf_base","flow":"ir017_ir040_perf"}
        layouts={arm:base.inspect(client,p) for arm,p in ids.items()}
        for arm,layout in layouts.items():
            if layout["typed_lines"]!=64 or ("layout=I1:64" if arm=="interp" else "layout=J1:64") not in layout["raw"]:
                raise AssertionError("wrong actual backend: "+repr(layout))
        if "no ledger entry" not in client.command("functioncompiler ir016 fc_native:ir017_ir040_perf"):
            raise AssertionError("native twin compiled")
        r["layouts"]=layouts
        r["arms"]={}
        for arm in ARMS:
            prepare(client,arm)
            before=client.command("functioncompiler ir008")
            batch(client,arm,128)
            state=validate(client,1,128)
            after=client.command("functioncompiler ir008")
            delta={k:stat(after,k)-stat(before,k) for k in
                   ("executed_regions","ir040_proofs","ir040_operand_reads_reused","direct_function_executed")}
            if (delta["executed_regions"]>0)!=(arm!="native"):
                raise AssertionError("typed path mismatch "+repr(delta))
            for key in ("ir040_proofs","ir040_operand_reads_reused"):
                if (delta[key]>0)!=(arm in ("flow","direct")):
                    raise AssertionError("dataflow isolation mismatch")
            if (delta["direct_function_executed"]>0)!=(arm=="direct"):
                raise AssertionError("scheduler not isolated")
            r["arms"][arm]={"state":state,"deltas":delta}
    finally:
        stop(proc,client,log,"diagnostic")
        DIAGNOSTIC=False
        save("diagnostic-preflight",r)
    raw=(OUT/"diagnostic.server.log").read_text(errors="replace")
    timing={}
    for phase,pattern in (
            ("typed",r"IR041_COMPILE function=(\S+) source_lines=\d+ wall_ns=(\d+) thread_cpu_ns=(-?\d+)"),
            ("adapter",r"IR042_ADAPTER function=(\S+) wall_ns=(\d+) thread_cpu_ns=(-?\d+)")):
        for fid,wall,cpu in re.findall(pattern,raw):
            timing.setdefault(fid,{})[phase]={"wall_ns":int(wall),"cpu_ns":int(cpu)}
    if set(timing)!={"fc_ir:"+p for p in ids.values()} or any(set(x)!={"typed","adapter"} for x in timing.values()):
        raise AssertionError("compile phase evidence incomplete: "+repr(timing))
    r["compile_phases"]=timing
    save("diagnostic-preflight",r)
    print("IR042_ATTR_PREFLIGHT "+json.dumps(r),flush=True)
    return r

def cost(s):return s["cpu_ns"]/s["top_level_lines"]
def spread(samples):
    v=[cost(s) for s in samples]
    return (max(v)-min(v))/stats.median(v)

def qualified(history):
    return all(len(history[a])>=MIN_ROUNDS and spread(history[a][-STABLE_WINDOWS:])<=AA_LIMIT
               and min(s["cpu_ns"] for s in history[a][-STABLE_WINDOWS:])>=MIN_CPU_NS for a in ARMS)

def aa_pass(blocks):
    return bool(blocks) and all(abs(b["reduction"])<=AA_LIMIT and
        min(s["cpu_ns"] for s in b["samples"])>=MIN_CPU_NS for b in blocks)

def run_boot(boot):
    proc,client,log=base.start("bytecode")
    report={"boot":boot,"calibration":[],"warmup":{a:[] for a in ARMS},
            "holdout":{a:[] for a in ARMS},"blocks":[],"status":"started"}
    def archive():save(f"boot-{boot}",report)
    try:
        thread=find_server_thread(proc.pid)
        report["freeze"]=prior.setup(client)
        def window(arm,batches):
            prepare(client,arm)
            e0=snapshot_jvm_environment(thread[0])
            cpu0=server_cpu_ns(thread)
            wall0=time.monotonic_ns()
            for _ in range(batches):batch(client,arm)
            wall=time.monotonic_ns()-wall0
            cpu=server_cpu_ns(thread)-cpu0
            e1=snapshot_jvm_environment(thread[0])
            if cpu<=0:raise AssertionError("invalid CPU clock")
            return {"arm":arm,"cpu_ns":cpu,"wall_ns":wall,"batches":batches,
                    "top_level_lines":64*CALLS*batches,"state":validate(client,batches),
                    "environment":delta_environment(e0,e1)}
        # Calibrate before treatment; same number of calls in ALL arms.
        batches=START_BATCHES
        while batches<=MAX_BATCHES:
            order=ARMS if boot==0 else ARMS[::-1]
            samples=[window(a,batches) for a in order]
            report["calibration"].append({"batches":batches,"samples":samples})
            archive()
            if min(s["cpu_ns"] for s in samples)>=CALIBRATION_TARGET_NS:break
            batches*=2
        if batches>MAX_BATCHES:
            report["status"]="calibration_unqualified"
            return report
        report["fixed_batches"]=batches
        print("IR042_CALIBRATION "+json.dumps({"boot":boot,"batches":batches,
            "fastest_cpu_ns":min(s["cpu_ns"] for s in samples)}),flush=True)
        for i in range(MAX_ROUNDS):
            offset=(i+boot)%len(ARMS)
            for a in ARMS[offset:]+ARMS[:offset]:
                report["warmup"][a].append(window(a,batches))
            archive()
            print("IR042_WARMUP "+json.dumps({"boot":boot,"round":i+1,
                "spreads":{a:spread(report["warmup"][a][-STABLE_WINDOWS:]) for a in ARMS}}),flush=True)
            if qualified(report["warmup"]):break
        if not qualified(report["warmup"]):
            report["status"]="warmup_unqualified"
            return report
        for i in range(HOLDOUT_ROUNDS):
            for a in (ARMS[::-1] if (i+boot)%2 else ARMS):
                report["holdout"][a].append(window(a,batches))
        if any(spread(report["warmup"][a][-STABLE_WINDOWS:]+report["holdout"][a])>AA_LIMIT or
               min(s["cpu_ns"] for s in report["holdout"][a])<MIN_CPU_NS for a in ARMS):
            report["status"]="holdout_unqualified"
            return report
        def record(a,b,order,phase):
            block=prior.paired(a,b,order,lambda arm:window(arm,batches))
            block["phase"]=phase
            report["blocks"].append(block)
            archive()
            print("IR042_ATTR_BLOCK "+json.dumps({k:v for k,v in block.items() if k!="samples"}|{"boot":boot}),flush=True)
            return block
        controls=[record(a,a,"ABBA" if (i+boot)%2==0 else "BAAB","qualification") for i,a in enumerate(ARMS)]
        if not aa_pass(controls):
            report["status"]="placebo_unqualified"
            return report
        for order in (("ABBA","BAAB") if boot==0 else ("BAAB","ABBA")):
            for a,b in (PAIRS if order=="ABBA" else PAIRS[::-1]):
                record(a,b,order,"measurement")
        report["status"]="complete" if aa_pass([b for b in report["blocks"] if b["a"]==b["b"]]) else "measurement_placebo_failed"
        return report
    finally:
        stop(proc,client,log,f"boot-{boot}")
        archive()

def analyze(boots,compile_phases):
    all_blocks=[b for boot in boots for b in boot["blocks"]]
    aa=max((abs(b["reduction"]) for b in all_blocks if b["a"]==b["b"]),default=None)
    complete=len(boots)==BOOTS and all(boot["status"]=="complete" for boot in boots)
    out={"boot_statuses":[x["status"] for x in boots],"max_absolute_aa":aa,"findings":{},
         "general_datapack_speedup":False}
    for a,b in CONTRASTS:
        blocks=[x for x in all_blocks if (x["a"],x["b"])==(a,b)]
        reductions=[x["reduction"] for x in blocks]
        per_boot=[stats.median([x["reduction"] for x in boot["blocks"] if (x["a"],x["b"])==(a,b)])
                  for boot in boots if any((x["a"],x["b"])==(a,b) for x in boot["blocks"])]
        accepted=(complete and aa is not None and aa<=AA_LIMIT and len(blocks)==2*BOOTS
            and min(reductions)>0 and min(per_boot)>=max(MIN_REDUCTION,2*aa)
            and all(s["cpu_ns"]>=MIN_CPU_NS for x in blocks for s in x["samples"]))
        finding={"paired_reductions":reductions,"boot_medians":per_boot,"pilot_gate_pass":bool(accepted),
                 "median_reduction":stats.median(reductions) if reductions else None}
        if accepted:
            saving=64*stats.median(x["a_ns_per_line"]-x["b_ns_per_line"] for x in blocks)
            finding["estimated_cpu_saved_per_function_call_ns"]=saving
            # Only cumulative native->flow/interpreter use full observed
            # post-parse compiler cost. Cold probe excludes load/JIT/memory.
            if a=="native" and b in ("interp","flow"):
                fid="fc_ir:ir017_ir042_interp" if b=="interp" else "fc_ir:ir017_ir040_perf"
                phases=compile_phases[fid]
                cpu=[phase["cpu_ns"] for phase in phases.values()]
                if min(cpu)>=0 and saving>0:
                    finding["illustrative_post_parse_break_even_calls"]=math.ceil(sum(cpu)/saving)
                    finding["compile_cpu_ns"]=sum(cpu)
        out["findings"][a+"_vs_"+b]=finding
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS={p:SOURCE for p in ("ir017_ir040_perf","ir017_ir040_perf_base","ir017_ir042_interp")}
    base.fixture=fixture
    base.options=options
    r={"status":"started","boots":[],"production_promotion":False}
    try:
        r["preflight"]=preflight()
        for boot in range(BOOTS):
            r["boots"].append(run_boot(boot))
            save("results",r)
        r["summary"]=analyze(r["boots"],r["preflight"]["compile_phases"])
        r["status"]="complete"
        print("IR042_ATTR_SUMMARY "+json.dumps(r["summary"]),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        save("results",r)
if __name__=="__main__":main()
