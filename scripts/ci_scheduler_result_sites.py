#!/usr/bin/env python3
"""SCHED-ATTR-028 Phase D: site-specific /execute result-callback census.

One new TIMED native Minecraft 26.3 event: no new CPU-clock reads, same
already-frozen 1/32 sampled ExecuteCommand parent. Site labels are recorded
inside the existing callback interval, which may add Mixin/counter overhead.
Interpret raw site CPU shares only, not an A/B effect or avoidable savings.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ci_scheduler_result_delegate import validate_native, EXPECTED_PACK_SHA, STATE_FIELDS, verify_pack

OUT=ROOT/"build"/"benchmarks"/"SCHED-ATTR-028-SITES"
FOUR=("SCORE_STORE","BOSSBAR_STORE","DATA_STORE","FUNCTION_CONDITION")
ALL=FOUR+("NO_SITE","MULTIPLE")


def interpret(data:dict)->dict:
    # This invokes the entire SCHED-ATTR-027 original native event + CPU
    # quality/clock/semantics validation and the SCHED-ATTR-028 delegate
    # histogram conservation. No control arm is fabricated.
    parent=validate_native(data,"timed")
    site=data.get("scheduler_result_site_trace")
    delegate=parent["trace"]
    if (data.get("scheduler_result_site_trace_enabled") is not True
            or not isinstance(site,dict) or site.get("mode")!="timed"
            or set(site.get("sites",{}))!=set(ALL)
            or site.get("nested")!=0
            or type(site.get("java_thread_id")) is not int
            or site["java_thread_id"]<=0):
        raise AssertionError("Missing or invalid exact callback-site runtime census")
    if delegate["calls"]<200:
        raise AssertionError("Not enough original selected result callbacks")
    if (site["callbacks"]!=delegate["calls"]
            or site["raw_cpu_ns"]!=delegate["raw_cpu_ns"]
            or sum(row["calls"] for row in site["sites"].values())!=site["callbacks"]
            or sum(row["raw_cpu_ns"] for row in site["sites"].values())!=site["raw_cpu_ns"]):
        raise AssertionError("Site counts/CPU do not conserve original callback interval")
    real=sum(site["sites"][p]["calls"] for p in FOUR)
    own=sum(g["calls"] for g in delegate["groups"] if
            g["type"]=="net.minecraft.server.commands.ExecuteCommand$$Lambda")
    empty=sum(g["calls"] for g in delegate["groups"] if g["type"]=="EMPTY")
    if (real!=own or site["sites"]["NO_SITE"]["calls"]!=empty
            or site["sites"]["MULTIPLE"]["calls"]!=0
            or own<30):
        raise AssertionError("Exact synthetic owner-site coverage is not exhaustive")
    measured_own=sum(site["sites"][p]["raw_cpu_ns"] for p in FOUR)
    expected_own=sum(g["raw_cpu_ns"] for g in delegate["groups"] if
            g["type"]=="net.minecraft.server.commands.ExecuteCommand$$Lambda")
    if measured_own!=expected_own:
        raise AssertionError("ExecuteCommand site CPU does not conserve owner-class CPU")

    ordered=sorted(FOUR,key=lambda p:site["sites"][p]["raw_cpu_ns"],reverse=True)
    rows=[]
    for name in ordered:
        r=site["sites"][name]
        rows.append({
            "site":name,
            "sampled_callbacks":r["calls"],
            "sampled_raw_inclusive_cpu_ns":r["raw_cpu_ns"],
            "share_of_ExecuteCommand_owned_sampled_calls":r["calls"]/own,
            "share_of_ExecuteCommand_owned_sampled_cpu":
                r["raw_cpu_ns"]/measured_own if measured_own else None,
            "share_of_all_sampled_result_callback_cpu":
                r["raw_cpu_ns"]/site["raw_cpu_ns"] if site["raw_cpu_ns"] else None,
            "mean_raw_cpu_ns_per_site_callback":
                r["raw_cpu_ns"]/r["calls"] if r["calls"] else None,
            "descriptive_only":True,
        })
    return {
        "valid_native_site_census":True,
        "independent_timed_jvm":True,
        "same_original_parent_ordinal_selection":True,
        "new_per_callback_cpu_clocks":0,
        "native_event_cpu_ns":parent["cpu"]["server_thread_cpu_running_ns"],
        "total_sampled_result_callbacks":site["callbacks"],
        "total_raw_sampled_result_callback_cpu_ns":site["raw_cpu_ns"],
        "ExecuteCommand_owned_sampled_callbacks":own,
        "ExecuteCommand_owned_sampled_callback_cpu_ns":measured_own,
        "no_op_empty_sampled_callbacks":empty,
        "multiple_or_unclassified_synthetic_site_calls":site["sites"]["MULTIPLE"]["calls"],
        "synthetic_sites_by_raw_callback_cpu":rows,
        "no_site_raw_callback_cpu_ns":site["sites"]["NO_SITE"]["raw_cpu_ns"],
        "decision":"descriptive_site_specific_result_callback_census",
        "limitations":(
            "Single timed native JVM and no new matched empty control:"
            " raw CPU measurements are original inclusive RESULT intervals,"
            " not control-adjusted causal effects. Site HEAD injections add"
            " a small uncalibrated counter overhead inside the interval."
            " Rates in the selected 1/32 parent ordinals may not represent"
            " all callback types. Each of the four synthetic sites can perform"
            " necessary scoreboard, bossbar, NBT/data or function-condition"
            " game-state updates, so CPU is NOT automagically recoverable."
            " No synthetic code was bypassed, cached, combined or altered."
        ),
    }


def main()->int:
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"diagnostic.json"
    report={"study":"SCHED-ATTR-028-SITES","status":"started",
            "diagnostic_only":True,"no_causal_speedup_inference":True}
    path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    try:
        report["publisher_sha256"]=verify_pack()
        cmd=[
            sys.executable,str(ROOT/"scripts"/"run_veinminer_profile.py"),
            "--stack","fabric","--compiler-mode","score-add","--side","6",
            "--no-spark","--capture-server-thread-cpu","--scheduler-path-census",
            "--scheduler-task-cpu-probe","timed","--scheduler-phase-cpu-probe","timed",
            "--scheduler-brigadier-plumbing","--scheduler-result-delegate-trace",
            "--scheduler-result-site-trace",
            "--capture-timeout","150","--setup-rcon-timeout-seconds","45",
            "--startup-readiness-record",str(OUT/"startup.json"),
            "--tick-stability-diagnostics","--pre-event-idle-seconds","9",
        ]
        env=os.environ.copy()
        env.pop("GRADLE_RO_DEP_CACHE",None)
        env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
        env["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
        print("SCHED-ATTR-028-SITES native TIMED event",flush=True)
        p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,
                         check=False,timeout=750)
        (OUT/"native.stdout.log").write_text(p.stdout,encoding="utf-8")
        (OUT/"native.stderr.log").write_text(p.stderr,encoding="utf-8")
        if p.returncode:
            raise RuntimeError(
                f"Native site census failed {p.returncode}:"
                f" stderr tail={p.stderr[-3500:]!r} stdout tail={p.stdout[-1500:]!r}")
        payload=json.loads(p.stdout)
        data=payload["results"]
        report["native_state"]={k:data[k] for k in STATE_FIELDS}
        report["raw_delegate"]=data["scheduler_result_delegate_trace"]
        report["raw_sites"]=data["scheduler_result_site_trace"]
        report["native_result_json"]=payload.get("output")
        report["analysis"]=interpret(data)
        report["status"]="complete"
        print("SCHED-ATTR-028-SITES COMPLETE "
              +json.dumps(report["analysis"]),flush=True)
    except BaseException as error:
        report["status"]="failed"
        report["error"]=repr(error)
        raise
    finally:
        path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
