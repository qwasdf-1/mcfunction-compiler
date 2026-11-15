#!/usr/bin/env python3
"""SCHED-COMP-016: compare a production-safe immutable-env cache to original getenv.

Separate reload/parity JVMs gate all timing. Twelve fresh 26.3 Minecraft JVMs,
each with byte-identical native, native placebo, typed-original getenv, and
typed-cached command bodies, run 4 balanced ABBA/BAAB comparisons. The full
vanilla ExecutionContext and command-response paths are unchanged.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import statistics
import subprocess
import time
from ci_compiler_off_paired import exact_median_interval, cpu_run_delay, snapshot_host
import ci_compiler_off_stability as stable
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    stage_artifacts, make_fixture, setup_server_properties, server_tid,
    server_cpu_time_ns, read_score)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon

EXPERIMENT="SCHED-COMP-016"
OUT=ROOT/"build"/"benchmarks"/EXPERIMENT
SEED=16016
BOOTS=12
LENGTHS=(4,16,256,2000)
PRIMARY_LENGTH=2000
DIAG_CALLS=20
PREWARM_CALLS=120
WINDOW_CALLS=220
KINDS=("negative","legacy_vs_native","cached_vs_legacy","cached_vs_native")
NS={"native":"fc_cache_native","null":"fc_cache_native_null",
    "legacy":"fc_cache_legacy","cached":"fc_cache_cached"}
PAIRS={"negative":("native","null"),
       "legacy_vs_native":("native","legacy"),
       "cached_vs_legacy":("legacy","cached"),
       "cached_vs_native":("native","cached")}
RULE="minecraft:max_command_sequence_length"


def fid(arm:str,length:int)->str:
    if arm not in NS or length not in LENGTHS:raise ValueError((arm,length))
    return f"{NS[arm]}:score_{length}"


def plan()->tuple[dict,...]:
    rng=random.Random(SEED)
    rotations=[KINDS[i:]+KINDS[:i] for i in range(4)]*3
    rng.shuffle(rotations)
    orientations={kind:rng.sample(["ABBA","BAAB"]*6,BOOTS) for kind in KINDS}
    return tuple({"boot":i,"blocks":[{
        "kind":kind,
        "orientation":orientations[kind][i],
        "arms":[PAIRS[kind][0 if ch=="A" else 1]
                for ch in orientations[kind][i]]
    } for kind in rotations[i]]} for i in range(BOOTS))


def prepare(work:Path)->None:
    make_fixture(work)
    pack=work/"world"/"datapacks"/PACK
    for length in LENGTHS:
        content=(f"scoreboard players add {HOLDER} {OBJECTIVE} 1\n")*length
        for namespace in NS.values():
            dest=pack/"data"/namespace/"function"
            dest.mkdir(parents=True,exist_ok=True)
            (dest/f"score_{length}.mcfunction").write_text(content,encoding="utf-8")
    cfg=work/"config"
    cfg.mkdir(exist_ok=True)
    (cfg/"function-compiler.json").write_text(json.dumps({
        "enabled":True,"score_add":True,"fused_regions":False,
        "selective_macros":False,"tiered_bytecode":False,
        "tiered_threshold":5,
        "excluded_namespaces":[NS["native"],NS["null"]]
    },indent=2)+"\n",encoding="utf-8")


def rewrite_config(work:Path,value:bool)->None:
    path=work/"config"/"function-compiler.json"
    data=json.loads(path.read_text())
    data["enabled"]=True
    data["score_add"]=value
    path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")


def stat(text:str,key:str)->int:
    m=re.search(rf"(?:^|\s){re.escape(key)}=(\d+)(?:\s|$)",text)
    if m is None:raise AssertionError(f"Missing {key}: {text!r}")
    return int(m.group(1))


def activation(rcon:Rcon)->dict:
    observed={}
    for n in LENGTHS:
        for arm in NS:
            reply=rcon.command(f"functioncompiler stats {fid(arm,n)}")
            compiled=stat(reply,"score_add_compiled")
            want=n if arm in ("legacy","cached") else 0
            if compiled!=want:
                raise AssertionError(f"Wrong specialized activation {arm}/{n}: {compiled} != {want}")
            observed[fid(arm,n)]=compiled
    return observed


def invoke(rcon:Rcon,arm:str,n:int)->None:
    response=rcon.command(f"function {fid(arm,n)}")
    if not response.startswith("Running function "):
        raise AssertionError(f"Function not running {arm}/{n}: {response!r}")


def exact_work(rcon:Rcon,arm:str,n:int,calls:int)->dict:
    score=read_score(rcon)
    expected=n*calls
    if score!=expected:raise AssertionError(f"Score mismatch {arm}: {score} != {expected}")
    return {"score":score,"expected":expected,"exact_work":True}


def read_quota(rcon:Rcon)->int:
    result=rcon.command(f"gamerule {RULE}")
    if "max_command_sequence_length" not in result:
        raise AssertionError(f"Gamerule not recognized: {result}")
    numbers=re.findall(r"-?\d+",result)
    if not numbers:raise AssertionError(f"No quota readback: {result}")
    return int(numbers[-1])


def quota_parity(rcon:Rcon)->list[dict]:
    original=read_quota(rcon)
    rows=[]
    try:
        for n in (2,3,4,8,16,32,64):
            set_reply=rcon.command(f"gamerule {RULE} {n}")
            if read_quota(rcon)!=n:
                raise AssertionError(f"Gamerule set did not take effect: {n} {set_reply}")
            samples={}
            for arm in ("native","legacy","cached"):
                rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
                invoke(rcon,arm,16)
                samples[arm]=read_score(rcon)
            if len(set(samples.values()))!=1:
                raise AssertionError(f"Command-quota semantics differ at {n}: {samples}")
            if n==2 and samples["native"]>=16:
                raise AssertionError("Low quota did not truncate execution")
            if n>=32 and samples["native"]!=16:
                raise AssertionError("High quota failed to finish all commands")
            rows.append({"quota":n,"readback":n,"scores":samples})
    finally:
        rcon.command(f"gamerule {RULE} {original}")
        if read_quota(rcon)!=original:raise AssertionError("Gamerule restoration failed")
    return rows


def reload_semantics(rcon:Rcon,work:Path)->dict:
    """Proof of config on/off/on in SAME compiled function, no override."""
    records=[]
    for active in (True,False,True):
        rewrite_config(work,active)
        reply=rcon.command("function_compiler_probe reload")
        status=rcon.command("function_compiler_probe status")
        target="true" if active else "false"
        if f"score_add_prototype_enabled={target}" not in status:
            raise AssertionError(f"Live config toggle ignored: {status}")
        before=stat(status,"score_add_executed")
        rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        invoke(rcon,"cached",4)
        exact_work(rcon,"cached",4,1)
        after=stat(rcon.command("function_compiler_probe status"),"score_add_executed")
        delta=after-before
        expected=4 if active else 0
        if delta!=expected:
            raise AssertionError(f"Wrong live execution under config {active}: {delta} vs {expected}")
        records.append({"active":active,"reload_response":reply,"score":4,
                        "typed_executed_delta":delta,"status_active":target})
    return {"on_off_on":records,"proven":True}


def frozen_override_semantics(rcon:Rcon,work:Path)->dict:
    """Fixed env=true must win even when configuration is toggled false."""
    rewrite_config(work,False)
    reload_reply=rcon.command("function_compiler_probe reload")
    status=rcon.command("function_compiler_probe status")
    if "score_add_prototype_enabled=true" not in status:
        raise AssertionError("Explicit env override lost to reloadable config")
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    for _ in range(DIAG_CALLS):
        invoke(rcon,"cached",4)
    exact_work(rcon,"cached",4,DIAG_CALLS)
    rewrite_config(work,True)
    rcon.command("function_compiler_probe reload")
    return {"config_score_add":False,"env_score_add":True,"verified":True,
            "reload_reply":reload_reply}


def window(rcon:Rcon,pid:int,tid:int,arm:str)->dict:
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    cpu0,clock=server_cpu_time_ns(pid,tid)
    delay0=cpu_run_delay(pid,tid)
    host0=snapshot_host()
    start=time.perf_counter_ns()
    for _ in range(WINDOW_CALLS):invoke(rcon,arm,PRIMARY_LENGTH)
    wall=time.perf_counter_ns()-start
    host1=snapshot_host()
    delay1=cpu_run_delay(pid,tid)
    cpu1,clock1=server_cpu_time_ns(pid,tid)
    if clock!=clock1 or cpu1<=cpu0:raise AssertionError("CPU counter inconsistency")
    check=exact_work(rcon,arm,PRIMARY_LENGTH,WINDOW_CALLS)
    cpu=cpu1-cpu0
    waited=max(0,delay1-delay0) if delay0 is not None and delay1 is not None else None
    c0,c1=host0.get("cgroup_cpu_stat",{}),host1.get("cgroup_cpu_stat",{})
    throttle=(c1["nr_throttled"]-c0["nr_throttled"]
              if "nr_throttled" in c0 and "nr_throttled" in c1 else None)
    return {"arm":arm,"cpu_ns_per_command":cpu/(WINDOW_CALLS*PRIMARY_LENGTH),
            "server_thread_cpu_ns":cpu,"clock":clock,
            "wall_seconds":wall/1e9,
            "cgroup_nr_throttled_delta":throttle,
            "runqueue_delay_fraction":(
                waited/(waited+cpu) if waited is not None else None),**check}


def run_boot(index:int,artifacts:dict,phase:str,assignment:dict|None=None)->dict:
    work=RUN_ROOT/f"ci-cache016-{phase}-{index:02d}"
    if work.exists():shutil.rmtree(work)
    shutil.copytree(FABRIC_BASE,work)
    mods=work/"mods"
    mods.mkdir(exist_ok=True)
    for name in ("api","compiler"):
        path=Path(artifacts[name])
        shutil.copy2(path,mods/path.name)
    prepare(work)
    port,rport=unused_port(),unused_port()
    pwd=secrets.token_hex(20)
    setup_server_properties(work,port,rport,pwd)
    env=dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE":"true",
        "FC_SCORE_ADD_PROTOTYPE":"true",
        "FC_SCORE_ADD_METRICS":"false",
        "FC_SCORE_ADD_TIMING":"false",
        "FC_SCORE_ADD_LEGACY_NAMESPACE":NS["legacy"],
        "FC_FUSED_REGION_PROTOTYPE":"false",
        "FC_BYTECODE_REGION_PROTOTYPE":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS":"false",
        "FC_COMMAND_CALLBACK_METRICS":"false",
        "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES":"false",
        "FC_FUNCTION_TIMING":"false",
        "FC_RUNTIME_TRACE":"false",
    })
    if phase=="reload":
        env.pop("FC_SCORE_ADD_PROTOTYPE",None)
        env["FC_SCORE_ADD_METRICS"]="true"  # instrumentation only in this boot
    record={"index":index,"phase":phase,"status":"started",
            "host_before":snapshot_host(),"blocks":[]}
    if assignment is not None:record["assignment"]=assignment
    logfile=OUT/f"boot-{phase}-{index:02d}.log"
    print(f"016 BOOT {index} phase={phase}",flush=True)
    with logfile.open("w",encoding="utf-8") as log:
        proc=subprocess.Popen(["java",*stable.JVM_ARGS,"-jar",
             str(work/"fabric-server-launch.jar"),"nogui"],
             cwd=work,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
        rcon=None
        try:
            rcon=wait_for_rcon(proc,rport,pwd,timeout_seconds=180)
            status=rcon.command("function_compiler_probe status")
            if ("wrapped=true" not in status
                    or "score_add_prototype_enabled=true" not in status
                    or "fused_region_prototype_enabled=false" not in status):
                raise AssertionError(f"Unexpected compiler flags: {status}")
            record["activation"]=activation(rcon)
            for command in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1"
            ):
                rcon.command(command)
            if phase=="reload":
                record["reload"]=reload_semantics(rcon,work)
            elif phase=="diagnostic":
                record["quota"]=quota_parity(rcon)
                record["explicit_override"]=frozen_override_semantics(rcon,work)
                for arm in NS:
                    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
                    for _ in range(DIAG_CALLS):invoke(rcon,arm,PRIMARY_LENGTH)
                    exact_work(rcon,arm,PRIMARY_LENGTH,DIAG_CALLS)
            else:
                pid,tid=proc.pid,server_tid(proc.pid)
                record["qualification"]=stable.warmup_server(rcon,pid,tid)
                for arm in NS:
                    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
                    for _ in range(PREWARM_CALLS):invoke(rcon,arm,PRIMARY_LENGTH)
                    exact_work(rcon,arm,PRIMARY_LENGTH,PREWARM_CALLS)
                for block in assignment["blocks"]:
                    samples=[window(rcon,pid,tid,arm) for arm in block["arms"]]
                    record["blocks"].append({
                        "kind":block["kind"],"orientation":block["orientation"],
                        "windows":samples})
                if "score_add_metrics_enabled=false" not in status or (
                        "score_add_timing_enabled=false" not in status):
                    raise AssertionError("Timing measurements contaminated by instrumentation")
            record["host_after"]=snapshot_host()
            record["status"]="complete"
        finally:
            if rcon is not None:
                try:rcon.command("stop")
                except (RuntimeError,OSError):pass
                rcon.close()
            try:proc.wait(timeout=35)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
    return record


def contrast(block:dict,frozen:dict)->float:
    if block["kind"]!=frozen["kind"] or block["orientation"]!=frozen["orientation"]:
        raise AssertionError("Wrong preregistered crossover block")
    if len(block["windows"])!=4:raise AssertionError("Incomplete ABBA/BAAB")
    arms=PAIRS[block["kind"]]
    if [w["arm"] for w in block["windows"]]!=frozen["arms"]:
        raise AssertionError("Wrong predeclared arm order")
    a=[math.log(w["cpu_ns_per_command"]) for w in block["windows"] if w["arm"]==arms[0]]
    b=[math.log(w["cpu_ns_per_command"]) for w in block["windows"] if w["arm"]==arms[1]]
    if len(a)!=2 or len(b)!=2:raise AssertionError("Missing paired samples")
    return 100*(statistics.mean(b)-statistics.mean(a))


def analyze(boots:list[dict],frozen:tuple[dict,...])->dict:
    if len(boots)!=BOOTS:raise AssertionError("All 12 JVMs must be retained")
    rows=[]
    for i,boot in enumerate(boots):
        if boot["index"]!=i or boot["status"]!="complete":
            raise AssertionError(f"Invalid JVM boot {i}")
        expected={x["kind"]:x for x in frozen[i]["blocks"]}
        if len(boot["blocks"])!=len(KINDS):
            raise AssertionError("Missing contrast block")
        contrasts={x["kind"]:contrast(x,expected[x["kind"]]) for x in boot["blocks"]}
        if set(contrasts)!=set(KINDS):raise AssertionError("Contrast missing")
        windows=[w for block in boot["blocks"] for w in block["windows"]]
        if not all(w["exact_work"] for w in windows):
            raise AssertionError("Score integrity failed")
        quality=(boot["qualification"]["qualification_stable"]
                 and all(w["cgroup_nr_throttled_delta"]==0 for w in windows)
                 and all(w["runqueue_delay_fraction"] is not None
                         and w["runqueue_delay_fraction"]<=stable.MAX_RUNQUEUE_DELAY_FRACTION
                         for w in windows))
        rows.append({"boot":i,"quality":quality,"contrasts":contrasts})
    kinds={}
    for name in KINDS:
        values=[r["contrasts"][name] for r in rows]
        kinds[name]={"median_signed_log_percent":statistics.median(values),
                     "exact_median_interval":exact_median_interval(values),
                     "boot_contrasts":values,"n_independent_boots":BOOTS}
    failed=[r["boot"] for r in rows if not r["quality"]]
    placebo=kinds["negative"]["exact_median_interval"]
    valid_null=placebo["lower"]<=0<=placebo["upper"]
    direct=kinds["cached_vs_native"]["exact_median_interval"]
    if failed:verdict="inconclusive_quality"
    elif not valid_null:verdict="invalid_a_a_control"
    elif direct["upper"]<=-15:verdict="cached_path_material_gain_vs_native_supported"
    elif direct["upper"]<0:verdict="cached_path_small_gain_vs_native_supported"
    elif direct["lower"]>0:verdict="cached_path_regression_vs_native_supported"
    elif direct["lower"]>=-15:verdict="no_material_gain_vs_native"
    else:verdict="inconclusive"
    return {"verdict":verdict,"quality_failed_boots":failed,
            "negative_interval_includes_zero":valid_null,
            "by_kind":kinds,"per_boot":rows,
            "scope":"Literal fake-holder scoreboard add, independent JVM bootstrap",
            "production_claim":"Requires full semantic/reload parity and a real-datapack test"}


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",required=True,choices=("reload","diagnostic","timing"))
    phase=parser.parse_args().phase
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/f"{phase}.json"
    assignments=plan()
    record={"experiment":EXPERIMENT,"phase":phase,"status":"started",
            "boots":[],"preregistration":{
                "seed":SEED,"n_independent_timing_boots":BOOTS,
                "primary_length":PRIMARY_LENGTH,"calls_per_window":WINDOW_CALLS,
                "prewarm_calls_per_arm":PREWARM_CALLS,
                "four_contrasts":KINDS,"assignments":assignments,
                "placebo_required":True,"no_fusion":True,
                "all_boots_and_windows_retained":True,
                "command_work_per_window":PRIMARY_LENGTH*WINDOW_CALLS,
                "threshold_signed_log_percent":-15,
                "quality":"stable warmup, 0 cgroup throttle, <=25% runqueue delay"}}
    target.write_text(json.dumps(record,indent=2)+"\n")
    try:
        artifacts=stage_artifacts()
        record["artifact_hashes"]={k:v for k,v in artifacts.items() if k.endswith("_sha256")}
        if phase!="timing":
            record["boots"].append(run_boot(0,artifacts,phase))
        else:
            for required in ("reload","diagnostic"):
                prior=json.loads((OUT/f"{required}.json").read_text())
                if prior["status"]!="complete":
                    raise AssertionError(f"Missing {required} semantic preflight")
            for i,assignment in enumerate(assignments):
                result=run_boot(i,artifacts,"timing",assignment)
                record["boots"].append(result)
                target.write_text(json.dumps(record,indent=2)+"\n")
            record["analysis"]=analyze(record["boots"],assignments)
        record["status"]="complete"
        print("SCHED-COMP-016 COMPLETE "+json.dumps({
            "phase":phase,"status":record["status"],
            "reload":record["boots"][0].get("reload") if phase=="reload" else None,
            "quota":record["boots"][0].get("quota") if phase=="diagnostic" else None,
            "analysis":record.get("analysis"),
        }),flush=True)
    except BaseException as exc:
        record["status"]="failed"
        record["error"]=repr(exc)
        raise
    finally:
        target.write_text(json.dumps(record,indent=2)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
