#!/usr/bin/env python3
"""SCHED-ATTR-024: actual execution-path call counts during a native Vein Miner event.

One opt-in counters-only Minecraft boot, not a timing A/B experiment. Census
includes playerbot mining, datapack execution and event-window RCON polling;
it cannot isolate exact CPU cost of any task method.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ci_scoreadd_workload_share import (  # noqa: E402
    EXPECTED_PACK_SHA, STATE_FIELDS, WORK_EXPECTED,
    QUEUE_STEPS_EXPECTED, verify_pack,
)

OUT = ROOT/"build"/"benchmarks"/"SCHED-ATTR-024"
COUNTS=("queue_entries","build_contexts","execute_command",
        "call_function","continuation")

def analyze(data:dict)->dict:
    cpu=data.get("server_thread_event_cpu")
    census=data.get("scheduler_path_census")
    if not (
        data.get("valid_native_workload")
        and data.get("valid_score_add_profile")
        and data.get("work_expected")==WORK_EXPECTED
        and data.get("queue_head_delta")==QUEUE_STEPS_EXPECTED
        and data.get("run_state_after")==0
        and data.get("tick_pre_event_stability",{}).get("stable")
        and isinstance(cpu,dict) and cpu.get("cpu_measurement_valid")
        and cpu.get("host_quality_pass")
        and data.get("datapack_sha256")==EXPECTED_PACK_SHA
        and data.get("compiler_mode")=="score-add"
        and data.get("queue_score_add_compiled")==4
        and data.get("scheduler_path_census_enabled") is True
        and isinstance(census,dict)
        and census.get("session_count")==1
        and type(census.get("owner_java_thread_id")) is int
        and census["owner_java_thread_id"]>0
        and not data.get("spark_capture_enabled")
        and not data.get("jfr_cpu_capture_enabled")
        and not data.get("command_callback_metrics_enabled")
        and not data.get("selective_macro_arguments_metrics_enabled")
    ):
        raise AssertionError("SCHED-ATTR-024 native event, host, or probe activation failed")
    if any(type(census.get(k)) is not int or census[k]<0 for k in COUNTS):
        raise AssertionError("Method path counters absent/negative")
    if census["queue_entries"]<1000:
        raise AssertionError("No meaningful event-window queue coverage")
    if census["execute_command"]==0 or census["build_contexts"]==0:
        raise AssertionError("No leaf/context hook activation; cannot classify task paths")
    total=census["queue_entries"]
    named=sum(census[k] for k in COUNTS if k!="queue_entries")
    # Named task-method calls are potentially overlapping or may occur
    # outside a queue action. No disjoint sum or exact residual is asserted.
    return {
        "valid_census":True,
        "workload_parity":True,
        "native_ore_operations":WORK_EXPECTED,
        "native_queue_head_advances":QUEUE_STEPS_EXPECTED,
        "queue_entries":total,
        "task_method_entries":{k:census[k] for k in COUNTS if k!="queue_entries"},
        "task_calls_per_dequeued_entry":{
            k:census[k]/total for k in COUNTS if k!="queue_entries"
        },
        "named_task_call_sum":named,
        "named_calls_are_disjoint":False,
        "event_server_thread_cpu_ns":cpu["server_thread_cpu_running_ns"],
        "cpu_by_task_method_ns":None,
        "note":"counts of method entries, not a CPU-time breakdown; no mutually exclusive categories or clock reads",
    }

def main()->int:
    OUT.mkdir(parents=True,exist_ok=True)
    report={"study":"SCHED-ATTR-024","status":"started","diagnostic_only":True}
    (OUT/"diagnostic.json").write_text(json.dumps(report,indent=2)+"\n")
    try:
        report["publisher_sha256"]=verify_pack()
        cmd=[
            sys.executable,str(ROOT/"scripts"/"run_veinminer_profile.py"),
            "--stack","fabric","--compiler-mode","score-add","--side","6",
            "--no-spark","--capture-server-thread-cpu","--scheduler-path-census",
            "--capture-timeout","150","--setup-rcon-timeout-seconds","45",
            "--startup-readiness-record",str(OUT/"startup-census.json"),
            "--tick-stability-diagnostics","--pre-event-idle-seconds","9",
        ]
        env=os.environ.copy()
        env.pop("GRADLE_RO_DEP_CACHE",None)
        env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
        env["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
        proc=subprocess.run(cmd,cwd=ROOT,env=env,text=True,
                            capture_output=True,timeout=750,check=False)
        (OUT/"native.stdout.log").write_text(proc.stdout,encoding="utf-8")
        (OUT/"native.stderr.log").write_text(proc.stderr,encoding="utf-8")
        if proc.returncode:
            raise RuntimeError(f"Native event exited {proc.returncode}: {proc.stderr[-3000:]!r}; stdout tail {proc.stdout[-1400:]!r}")
        result=json.loads(proc.stdout)
        data=result["results"]
        report["native_state"]={k:data[k] for k in STATE_FIELDS}
        report["raw_census"]=data["scheduler_path_census"]
        report["native_result_json"]=result.get("output")
        report["analysis"]=analyze(data)
        report["status"]="complete"
        print("SCHED-ATTR-024 COMPLETE "+json.dumps(report["analysis"]),flush=True)
    except BaseException as e:
        report["status"]="failed"
        report["error"]=repr(e)
        raise
    finally:
        (OUT/"diagnostic.json").write_text(json.dumps(report,indent=2)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
