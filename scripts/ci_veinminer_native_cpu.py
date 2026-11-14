#!/usr/bin/env python3
"""SCHED-COMP-018 — real Vein Miner native/cached whole-event CPU trial.

Ten independent *triplets* of fresh Java 25 / Minecraft 26.3 Fabric boots:
OFF-A and byte-identical OFF-B placebo, plus cached ScoreAdd. The only
treatment difference is FC_SCORE_ADD_PROTOTYPE in the unchanged production
Vein Miner playerbot harness. Record Server-thread schedstat running CPU
around the native 215-block event and its separate wall-time completion.
No spark/agent/mcfunction execution counters; reject invalid/noisy trials
without dropping posthoc observations or re-randomizing assignments.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys

from ci_compiler_off_paired import exact_median_interval, snapshot_host

ROOT=Path(__file__).resolve().parents[1]
EXPERIMENT="SCHED-COMP-018"
OUT=ROOT/"build"/"benchmarks"/EXPERIMENT
REPORT=OUT/"results.json"
SMOKE=OUT/"smoke.json"
SEED=26874018
TRIPLETS=10
SIDE=6
AFFECTED=SIDE**3-1
CPU_MATERIAL_GAIN_PERCENT=15
EVENT_MATERIAL_GAIN_PERCENT=15
MODES=("off_a","off_b","cached")
PACK=ROOT/"references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PACK_SHA256="fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
STATE_FIELDS=(
    "player_mined_source_stat","work_after","work_expected",
    "run_state_after","queue_head_delta","remaining_ore",
    "source_block_remains","operation_markers_after","target_markers_after",
)


def plan()->tuple[tuple[str,str,str],...]:
    # 6 permutations give two observations of each arm at each position.
    # The four extra permutations bring those per-position counts to 3 or 4.
    permutations=list(itertools.permutations(MODES))
    extra=[
        ("off_a","off_b","cached"),
        ("off_b","cached","off_a"),
        ("cached","off_a","off_b"),
        ("cached","off_b","off_a"),
    ]
    rng=random.Random(SEED)
    orders=permutations+extra
    rng.shuffle(orders)
    return tuple(orders)


def verify_pack()->str:
    if not PACK.is_file():
        raise FileNotFoundError(f"Missing pinned publisher datapack: {PACK}")
    digest=hashlib.sha256(PACK.read_bytes()).hexdigest()
    if digest!=PACK_SHA256:
        raise AssertionError(f"Wrong publisher archive digest: {digest}")
    return digest


def percent(treatment:float,control:float)->float:
    if treatment<=0 or control<=0:
        raise AssertionError("Paired metrics must be positive")
    return 100*(treatment/control-1)


def run_arm(arm:str,triplet:int,position:int)->dict:
    if arm not in MODES:
        raise ValueError(arm)
    enabled=arm=="cached"
    cmd=[
        sys.executable,str(ROOT/"scripts/run_veinminer_profile.py"),
        "--stack","fabric",
        "--compiler-mode","score-add" if enabled else "off",
        "--side",str(SIDE),"--capture-timeout","60",
        "--no-spark","--capture-server-thread-cpu",
    ]
    env=dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE",None)
    env["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
    env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
    # Both baselines use exactly the same command and environment. The
    # only intervention is the production runner's score-add mode switch.
    complete=subprocess.run(cmd,cwd=ROOT,env=env,text=True,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            timeout=750,check=False)
    if complete.returncode!=0:
        raise RuntimeError(
            f"Triplet={triplet} position={position} arm={arm} "
            f"native event runner exit={complete.returncode};"
            f"stdout={complete.stdout[-2600:]!r};"
            f"stderr={complete.stderr[-2600:]!r}")
    payload=json.loads(complete.stdout)
    result=payload["results"]
    mode="score-add" if enabled else "off"
    if result.get("compiler_mode")!=mode:
        raise AssertionError(f"Incorrect optimizer mode {arm}: {result.get('compiler_mode')}")
    if not result.get("valid_native_workload"):
        raise AssertionError(f"Actual native mining work did not complete: {arm}")
    if result.get("fused_regions_compiled") not in (0,None):
        raise AssertionError(f"Fusion contaminated this comparison: {arm}")
    score_compiled=result.get("queue_score_add_compiled")
    if enabled:
        if not result.get("valid_score_add_profile") or not isinstance(score_compiled,int) or score_compiled<=0:
            raise AssertionError("Cached treatment had no typed ScoreAdd activation")
    elif score_compiled not in (0,None):
        raise AssertionError(f"Compiler-disabled baseline still specialized commands: {score_compiled}")
    cpu=result.get("server_thread_event_cpu")
    if not result.get("server_thread_event_cpu_enabled") or not isinstance(cpu,dict):
        raise AssertionError(f"No CPU sample for native event: {arm}")
    if not cpu.get("cpu_measurement_valid") or cpu.get("clock")!="linux_schedstat_ns":
        raise AssertionError(f"Unreliable Server-thread CPU accounting: {cpu}")
    cpu_ns=cpu.get("server_thread_cpu_running_ns")
    elapsed=result.get("operation_completion_seconds")
    if not isinstance(cpu_ns,int) or cpu_ns<=0 or not isinstance(elapsed,(int,float)) or elapsed<=0:
        raise AssertionError(f"Invalid CPU/event time for {arm}: {cpu}")
    if cpu.get("work_expected")!=AFFECTED:
        raise AssertionError(f"Event CPU worker denominator mismatch: {cpu}")
    return {
        "arm":arm,"triplet":triplet,"position":position,
        "profile_mode":mode,"output":payload.get("output"),
        "run_id":result.get("run_id"),"sha256":result.get("datapack_sha256"),
        "native_state":{k:result[k] for k in STATE_FIELDS},
        "server_thread_cpu_running_ns":cpu_ns,
        "server_thread_cpu_ns_per_ore":cpu["cpu_ns_per_affected_block"],
        "cpu_detail":cpu,"host_quality":cpu["host_quality_pass"],
        "event_completion_seconds":elapsed,
        "queue_score_add_compiled":score_compiled,
        "valid_native_workload":True,"valid_activation":True,
        "tick_query_after_capture":result.get("tick_query_after_capture"),
    }


def analyze(triplets:list[dict],frozen:tuple[tuple[str,str,str],...])->dict:
    if len(triplets)!=TRIPLETS or len(frozen)!=TRIPLETS:
        raise AssertionError("Incomplete independent triplet campaign")
    placebo_cpu=[]
    treatment_cpu=[]
    placebo_event=[]
    treatment_event=[]
    rows=[]
    for i,(rec,order) in enumerate(zip(triplets,frozen),1):
        if rec["index"]!=i or tuple(rec["order"])!=order:
            raise AssertionError("Reordered or missing triplet")
        arms=rec["arms"]
        if set(arms)!=set(MODES) or len(arms)!=3:
            raise AssertionError("Incomplete triplet arms")
        for pos,arm in enumerate(order):
            if arms[arm]["position"]!=pos or arms[arm]["triplet"]!=i:
                raise AssertionError(f"Wrong predeclared arm allocation {i}/{arm}")
        states=[tuple(sorted(arms[arm]["native_state"].items())) for arm in MODES]
        if len(set(states))!=1 or not all(arms[arm]["valid_native_workload"] for arm in MODES):
            raise AssertionError(f"Native mining work or player state diverged: {i}")
        if not all(arms[arm]["valid_activation"] for arm in MODES):
            raise AssertionError("Missing mode/compilation activation")
        if len({arms[arm]["sha256"] for arm in MODES})!=1:
            raise AssertionError("Datapack hashes differ within triplet")
        off_a,off_b,cached=(arms[k] for k in MODES)
        placebo_cpu.append(percent(off_b["server_thread_cpu_running_ns"],
                                   off_a["server_thread_cpu_running_ns"]))
        treatment_cpu.append(percent(cached["server_thread_cpu_running_ns"],
                                     off_a["server_thread_cpu_running_ns"]))
        placebo_event.append(percent(off_b["event_completion_seconds"],
                                     off_a["event_completion_seconds"]))
        treatment_event.append(percent(cached["event_completion_seconds"],
                                       off_a["event_completion_seconds"]))
        rows.append({
            "triplet":i,"order":list(order),
            "cpu_placebo_percent":placebo_cpu[-1],
            "cpu_cached_vs_off_percent":treatment_cpu[-1],
            "event_placebo_percent":placebo_event[-1],
            "event_cached_vs_off_percent":treatment_event[-1],
            "quality":all(arms[arm]["host_quality"] for arm in MODES),
            "same_ore_state":True,
        })
    ci_pc=exact_median_interval(placebo_cpu)
    ci_tc=exact_median_interval(treatment_cpu)
    ci_pe=exact_median_interval(placebo_event)
    ci_te=exact_median_interval(treatment_event)
    bad=[r["triplet"] for r in rows if not r["quality"]]
    placebo_valid=(ci_pc["lower"]<=0<=ci_pc["upper"]
                   and ci_pe["lower"]<=0<=ci_pe["upper"])
    def decision(interval:dict,threshold:int)->str:
        if interval["upper"]<=-threshold:
            return "material_gain_supported"
        if interval["upper"]<0:
            return "small_gain_supported"
        if interval["lower"]>0:
            return "regression_supported"
        if interval["lower"]>=-threshold:
            return "no_material_gain"
        return "inconclusive"
    if bad:
        verdict="inconclusive_host_quality"
    elif not placebo_valid:
        verdict="invalid_off_off_placebo"
    else:
        verdict=decision(ci_tc,CPU_MATERIAL_GAIN_PERCENT)
    event_verdict=(
        "not_validated" if bad or not placebo_valid
        else decision(ci_te,EVENT_MATERIAL_GAIN_PERCENT))
    return {
        "verdict":verdict,"event_latency_verdict":event_verdict,
        "all_triplets_retained":True,"n_independent_triplets":TRIPLETS,
        "host_quality_failed_triplets":bad,
        "a_a_cpu_interval_includes_zero":ci_pc["lower"]<=0<=ci_pc["upper"],
        "a_a_event_interval_includes_zero":ci_pe["lower"]<=0<=ci_pe["upper"],
        "primary":{
            "metric":"Server thread running CPU ns during the 215-block native event",
            "median_relative_percent":statistics.median(treatment_cpu),
            "exact_median_interval_percent":ci_tc,
            "material_gain_percent":CPU_MATERIAL_GAIN_PERCENT,
            "per_triplet_percent":treatment_cpu,
        },
        "negative_control_cpu":{
            "median_relative_percent":statistics.median(placebo_cpu),
            "exact_median_interval_percent":ci_pc,
            "per_triplet_percent":placebo_cpu,
        },
        "secondary_event_latency":{
            "median_relative_percent":statistics.median(treatment_event),
            "exact_median_interval_percent":ci_te,
            "material_gain_percent":EVENT_MATERIAL_GAIN_PERCENT,
            "per_triplet_percent":treatment_event,
        },
        "negative_control_latency":{
            "median_relative_percent":statistics.median(placebo_event),
            "exact_median_interval_percent":ci_pe,
            "per_triplet_percent":placebo_event,
        },
        "per_triplet":rows,
        "scope":"Same Fabric stack and installed compiler mod, optimizer off vs cached typed ScoreAdd",
        "cpu_scope":"Server thread CPU across the full native playerbot event, including unrelated vanilla ticks/RCON responses, not exclusive ScoreAdd CPU",
        "no_production_default_change":True,
    }


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",required=True,choices=("smoke","timing"))
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    orders=plan()
    report=SMOKE if args.phase=="smoke" else REPORT
    record={
        "experiment":EXPERIMENT,"phase":args.phase,"status":"started",
        "preregistration":{
            "seed":SEED,"triplets":TRIPLETS,"orders":orders,
            "publisher_archive_sha256":PACK_SHA256,"affected_blocks":AFFECTED,
            "primary":"Linux Server thread running CPU ns per native 215-ore event",
            "secondary":"native ore event completion seconds",
            "negative_controls":"compiler-off-A vs independently booted identical compiler-off-B, both CPU and event latency",
            "CI":"exact >=95%-coverage median interval of 10 independent triplets",
            "material_gain_percent":CPU_MATERIAL_GAIN_PERCENT,
            "host_quality":"no cgroup throttling and Server thread runqueue wait <=25% for all three arms",
            "no_posthoc_exclusions":True,
            "no_spark_no_function_metrics":True,
            "all_sources_byte_identical":True,
        },
        "triplets":[],
    }
    report.write_text(json.dumps(record,indent=2)+"\n")
    try:
        record["verified_archive_sha256"]=verify_pack()
        if args.phase=="smoke":
            record["smoke"]=run_arm("cached",0,0)
            if not record["smoke"]["valid_native_workload"]:
                raise AssertionError("Native CPU smoke failed")
            record["status"]="complete"
        else:
            smoke=json.loads(SMOKE.read_text())
            if smoke.get("status")!="complete":
                raise AssertionError("Preflight CPU measurement required before timing")
            for i,order in enumerate(orders,1):
                triplet={"index":i,"order":list(order),"arms":{},
                         "host_before":snapshot_host()}
                record["triplets"].append(triplet)
                report.write_text(json.dumps(record,indent=2)+"\n")
                for position,arm in enumerate(order):
                    print(f"REAL_EVENT_CPU triplet={i}/{TRIPLETS} position={position} arm={arm}",
                          flush=True)
                    triplet["arms"][arm]=run_arm(arm,i,position)
                    report.write_text(json.dumps(record,indent=2)+"\n")
                triplet["host_after"]=snapshot_host()
                if len({json.dumps(triplet["arms"][a]["native_state"],sort_keys=True)
                        for a in MODES})!=1:
                    raise AssertionError(f"Ore state diverged triplet {i}")
            record["analysis"]=analyze(record["triplets"],orders)
            record["status"]="complete"
        print("SCHED-COMP-018 COMPLETE "+json.dumps({
            "phase":args.phase,"status":record["status"],
            "analysis":record.get("analysis"),
            "smoke_cpu_ns":record.get("smoke",{}).get("server_thread_cpu_running_ns")
        }),flush=True)
    except BaseException as e:
        record["status"]="failed"
        record["failure"]=repr(e)
        raise
    finally:
        report.write_text(json.dumps(record,indent=2)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
