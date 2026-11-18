#!/usr/bin/env python3
"""SCHED-ATTR-028: classify actual Minecraft result-callback delegate classes.

Three independent native 26.3 Vein Miner boots: same OFF/EMPTY/TIMED original
SCHED-ATTR-027 phase clock selection, plus POST-timing class lookup only on
the selected result callbacks. No new hot CPU clocks, no callback replacement.

Runtime bytecode already proves Brigadier's ResultConsumer is one stateless
adapter which dispatches to CommandContext.getSource().callback().onResult.
This study classifies THAT underlying CommandResultCallback, not the adapter.
A chain lambda is labelled as a chain owner, not decomposed into descendants.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ci_scheduler_plumbing_cpu import (  # noqa: E402
    ARMS, EXPECTED_PACK_SHA, STATE_FIELDS, WORK_EXPECTED,
    QUEUE_STEPS_EXPECTED, verify_pack,
    validate_native as validate_parent, interpret as interpret_parent,
)

OUT=ROOT/"build"/"benchmarks"/"SCHED-ATTR-028"
MIN_DOMINANT_GROUP_SAMPLES=30
MAX_GROUP_OVERFLOW_FRACTION=0.05
MAX_MATCHED_MAJOR_GROUP_EXPOSURE_DIFFERENCE=0.15


def validate_native(data:dict,mode:str)->dict:
    parent=validate_parent(data,mode)
    trace=data.get("scheduler_result_delegate_trace")
    if (data.get("scheduler_result_delegate_trace_enabled") is not True
            or not isinstance(trace,dict) or trace.get("mode")!=mode
            or type(trace.get("calls")) is not int
            or type(trace.get("timed_samples")) is not int
            or type(trace.get("raw_cpu_ns")) is not int
            or not isinstance(trace.get("groups"),list)):
        raise AssertionError("Missing native callback delegate classification")
    if trace["calls"]<0 or trace["timed_samples"]<0 or trace["raw_cpu_ns"]<0:
        raise AssertionError("Negative callback delegate accounting")
    groups=trace["groups"]
    keys=("calls","raw_cpu_ns","timed_samples","success","failure")
    if any(not isinstance(g,dict) or not isinstance(g.get("type"),str)
           or not g["type"] or any(type(g.get(k)) is not int or g[k]<0 for k in keys)
           for g in groups):
        raise AssertionError("Malformed callback delegate breakdown")
    if len({g["type"] for g in groups})!=len(groups):
        raise AssertionError("Duplicate callback delegate class label")
    for key,total_field in (
        ("calls","calls"),("raw_cpu_ns","raw_cpu_ns"),
        ("timed_samples","timed_samples"),("success","success"),
        ("failure","failure")):
        if sum(g[key] for g in groups)!=trace[total_field]:
            raise AssertionError(f"Callback class histogram failed {key} conservation")
    if (trace["calls"]!=trace["success"]+trace["failure"]
            or trace.get("non_execution_source")!=0):
        raise AssertionError("Callback classifications disagree with source/outcome")
    if mode=="off":
        if trace["calls"] or trace["raw_cpu_ns"] or groups:
            raise AssertionError("Plain arm accidentally collected delegate types")
    else:
        result=parent["plumbing"]["streams"]["result"]
        if trace["calls"]!=result["samples"]:
            raise AssertionError("Delegate census missed sampled result-consumer call")
        if trace["success"]!=parent["plumbing"]["callback_outcome"]["success"]:
            raise AssertionError("Delegate success count mismatched original results")
        if trace["failure"]!=parent["plumbing"]["callback_outcome"]["failure"]:
            raise AssertionError("Delegate failure count mismatched original results")
        if mode=="timed":
            if (trace["timed_samples"]!=result["samples"]
                    or trace["raw_cpu_ns"]!=result["cpu_ns"]):
                raise AssertionError("Delegate CPU sum differs from original measured interval")
        elif trace["timed_samples"]!=0 or trace["raw_cpu_ns"]!=0:
            raise AssertionError("Empty arm measured delegate real CPU instead of two clock reads")
        if trace.get("java_thread_id",0)<=0:
            raise AssertionError("Callback trace did not run on server thread")
    return {**parent,"trace":trace}


def run_native(arm:str, mode:str)->dict:
    args=[
        sys.executable,str(ROOT/"scripts"/"run_veinminer_profile.py"),
        "--stack","fabric","--compiler-mode","score-add","--side","6",
        "--no-spark","--capture-server-thread-cpu","--scheduler-path-census",
        "--scheduler-task-cpu-probe",mode,"--scheduler-phase-cpu-probe",mode,
        "--scheduler-brigadier-plumbing","--scheduler-result-delegate-trace",
        "--capture-timeout","150","--setup-rcon-timeout-seconds","45",
        "--startup-readiness-record",str(OUT/f"startup-{arm}.json"),
        "--tick-stability-diagnostics","--pre-event-idle-seconds","9",
    ]
    env=os.environ.copy()
    env.pop("GRADLE_RO_DEP_CACHE",None)
    env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
    env["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
    proc=subprocess.run(args,cwd=ROOT,env=env,text=True,capture_output=True,
                        timeout=750,check=False)
    (OUT/f"{arm}.stdout.log").write_text(proc.stdout,encoding="utf-8")
    (OUT/f"{arm}.stderr.log").write_text(proc.stderr,encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(
            f"{arm} native mining run failed {proc.returncode}:"
            f" stderr={proc.stderr[-3000:]!r} stdout={proc.stdout[-1500:]!r}")
    payload=json.loads(proc.stdout)
    data=payload["results"]
    valid=validate_native(data,mode)
    return {
        "arm":arm,"mode":mode,"publisher_sha256":data["datapack_sha256"],
        "native_state":{k:data[k] for k in STATE_FIELDS},
        "server_thread_cpu_running_ns":valid["cpu"]["server_thread_cpu_running_ns"],
        "host_quality_pass":valid["cpu"]["host_quality_pass"],
        "event_completion_seconds":data["operation_completion_seconds"],
        "queue_score_add_compiled":data["queue_score_add_compiled"],
        "census":valid["census"],"probe":valid["probe"],
        "phase_probe":valid["phase"],"plumbing_probe":valid["plumbing"],
        "delegate_trace":valid["trace"],
        "native_result_json":payload.get("output"),
    }


def interpret(records:dict[str,dict])->dict:
    prior=interpret_parent(records)
    if not prior["diagnostic_valid"]:
        return {"diagnostic_valid":False,"decision":"rejected_parent_cpu_quality",
                "parent_quality":prior}
    timed=records["timed_tasks"]
    empty=records["empty_control"]
    a=empty["delegate_trace"]
    b=timed["delegate_trace"]
    if b["calls"]<200 or a["calls"]<200:
        raise AssertionError("Insufficient selected result-consumer calls")
    if abs(a["calls"]-b["calls"])/max(a["calls"],b["calls"])>0.15:
        raise AssertionError("Mismatched independently booted callback populations")
    empty_by={g["type"]:g for g in a["groups"]}
    timed_by={g["type"]:g for g in b["groups"]}
    overflow=timed_by.get("OTHER",{}).get("calls",0)/b["calls"]
    if overflow>MAX_GROUP_OVERFLOW_FRACTION:
        raise AssertionError("Too many callback delegate classes overflowed census capacity")

    baseline=prior["brigadier_plumbing"]["result_consumer"]["empty_mean_clock_pair_ns"]
    multiplier=(
        timed["probe"]["streams"]["execute"]["calls"]
        /timed["probe"]["streams"]["execute"]["samples"])
    total_cpu=timed["server_thread_cpu_running_ns"]
    result=[]
    for name,g in sorted(
        timed_by.items(),key=lambda item: (-item[1]["raw_cpu_ns"],-item[1]["calls"],item[0])
    ):
        ctrl_calls=empty_by.get(name,{}).get("calls",0)
        major=g["calls"]>=MIN_DOMINANT_GROUP_SAMPLES
        matched=(ctrl_calls>0 and
                 abs(ctrl_calls-g["calls"])/max(ctrl_calls,g["calls"])
                 <=MAX_MATCHED_MAJOR_GROUP_EXPOSURE_DIFFERENCE)
        # Uniform EMPTY clock-pair mean is a sensitivity correction only:
        # we did not measure a separate empty cost for each callback class.
        signed_control_ns=g["raw_cpu_ns"]-baseline*g["calls"]
        result.append({
            "delegate_owner_class":name,
            "observed_timed_callbacks":g["calls"],
            "observed_empty_callbacks":ctrl_calls,
            "observed_success":g["success"],
            "observed_failure":g["failure"],
            "timed_raw_callback_cpu_ns":g["raw_cpu_ns"],
            "sampled_raw_cpu_fraction_of_all_callbacks":
                g["raw_cpu_ns"]/b["raw_cpu_ns"] if b["raw_cpu_ns"] else None,
            "sampled_callback_count_fraction":g["calls"]/b["calls"],
            "timed_mean_inclusive_ns":g["raw_cpu_ns"]/g["calls"],
            "signed_uniform_control_sensitivity_ns":signed_control_ns,
            "projected_inclusive_server_cpu_fraction_sensitivity":
                signed_control_ns*multiplier/total_cpu,
            "adequately_exposed_for_descriptive_group_screen":major and matched,
            "classification_limit":(
                "owner group only: distinct lambda sites and chained callback leaves"
                " may be merged" if "$$Lambda" in name else
                "concrete delegate class; class name alone does not prove effects"
            ),
        })
    return {
        **prior,
        "diagnostic_valid":True,
        "delegate_breakdown_valid":True,
        "observed_selected_callbacks":b["calls"],
        "observed_selected_callback_cpu_ns":b["raw_cpu_ns"],
        "callback_types_sorted_by_observed_cpu":result,
        "ranked_groups":len(result),
        "truncated_delegate_fraction":overflow,
        "parent_callback_inclusive_cpu_fraction_sensitivity":
            prior["brigadier_plumbing"]["result_consumer"]
                 ["projected_fraction_of_timed_server_cpu"],
        "decision":"descriptive_underlying_result_delegate_class_attribution",
        "limitations":(
            prior["limitations"]
            + " Results identify actual CommandResultCallback implementations"
            " behind ExecutionCommandSource.resultConsumer's common stateless"
            " Brigadier adapter, not separate ResultConsumer classes. JVM"
            " lambda class owners merge callsites, and CommandResultCallback.chain"
            " may hide leaf delegates. Raw group CPU sums come from the SAME"
            " selected original callback clock intervals. Group-specific EMPTY"
            " clock costs were not measured; a shared EMPTY mean subtraction is"
            " sensitivity only. All callback work includes semantic side effects."
            " No callback suppression, causal speedup, exclusive CPU or tested"
            " implementation optimization is implied."
        ),
    }


def main()->int:
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"diagnostic.json"
    report={"study":"SCHED-ATTR-028","status":"started",
            "diagnostic_only":True,"noncausal":True,"records":{},
            "arms":[a for a,_ in ARMS]}
    path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    try:
        report["publisher_pack_sha256"]=verify_pack()
        for name,mode in ARMS:
            print(f"SCHED-ATTR-028 CALLBACK ARM {name}",flush=True)
            report["records"][name]=run_native(name,mode)
            path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        report["analysis"]=interpret(report["records"])
        report["status"]=("complete" if report["analysis"]["diagnostic_valid"]
                          else "inconclusive_quality")
        print("SCHED-ATTR-028 "+report["status"].upper()+" "
              +json.dumps(report["analysis"]),flush=True)
    except BaseException as e:
        report["status"]="failed"
        report["error"]=repr(e)
        raise
    finally:
        path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return 0 if report["status"]=="complete" else 1

if __name__=="__main__":
    raise SystemExit(main())
