#!/usr/bin/env python3
"""SCHED-ATTR-025: sparse, calibrated inclusive CPU cost of four real task paths.

The native Vein Miner fixture is identical across three fresh Minecraft JVMs.
Only 1 in 32 method calls has CPU clock reads, never all 194k queue entries.
PLAIN keeps the same path-census counters; EMPTY clocks back-to-back before
sampled work; TIMED clocks around the sampled method execution.

Independent boots are not a causal optimization experiment. The projections
are inclusive sampled estimates, not a disjoint CPU partition.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ci_scoreadd_workload_share import (
    EXPECTED_PACK_SHA, STATE_FIELDS, WORK_EXPECTED, QUEUE_STEPS_EXPECTED, verify_pack,
)

OUT=ROOT/"build"/"benchmarks"/"SCHED-ATTR-025"
ARMS=(("plain","off"),("empty_control","empty"),("timed_tasks","timed"))
PATHS=("build","execute","call","continuation")
CENSUS_KEYS={"build":"build_contexts","execute":"execute_command",
             "call":"call_function","continuation":"continuation"}
DENOMINATOR=32
MIN_SAMPLES_PER_PATH=200
MAX_RELATIVE_CALL_DIFFERENCE=0.10
MAX_RELATIVE_SAMPLE_DIFFERENCE=0.15
MAX_TIMED_ZERO_FRACTION=0.20
MAX_EVENT_CPU_PERTURBATION=0.30


def validate_native(data:dict,mode:str)->dict:
    cpu=data.get("server_thread_event_cpu")
    probe=data.get("scheduler_task_cpu_probe")
    census=data.get("scheduler_path_census")
    if not (
        data.get("valid_native_workload")
        and data.get("valid_score_add_profile")
        and data.get("work_expected")==WORK_EXPECTED
        and data.get("queue_head_delta")==QUEUE_STEPS_EXPECTED
        and data.get("run_state_after")==0
        and data.get("tick_pre_event_stability",{}).get("stable")
        and data.get("datapack_sha256")==EXPECTED_PACK_SHA
        and data.get("compiler_mode")=="score-add"
        and data.get("queue_score_add_compiled")==4
        and isinstance(cpu,dict) and cpu.get("cpu_measurement_valid")
        and cpu.get("host_quality_pass")
        and cpu["server_thread_cpu_running_ns"]>0
        and data.get("scheduler_path_census_enabled") is True
        and isinstance(census,dict) and census.get("session_count")==1
        and census.get("queue_entries",0)>1000
        and isinstance(probe,dict) and probe.get("mode")==mode
        and probe.get("sample_denominator")==DENOMINATOR
        and not data.get("spark_capture_enabled")
        and not data.get("jfr_cpu_capture_enabled")
        and not data.get("command_callback_metrics_enabled")
        and not data.get("selective_macro_arguments_metrics_enabled")
    ):
        raise AssertionError("Native event, host, census, or CPU clock activation invalid")
    streams=probe.get("streams")
    if not isinstance(streams,dict) or set(streams)!=set(PATHS):
        raise AssertionError("Missing one or more task method streams")
    for name in PATHS:
        stat=streams[name]
        if not isinstance(stat,dict):
            raise AssertionError(f"Missing task stream {name}")
        if stat["nested"]!=0 or stat["final_depth"]!=0:
            raise AssertionError(f"Nested or leaking sampled method scope: {name}")
        if mode=="off":
            if any(stat.values()):
                raise AssertionError(f"Clock probe active in baseline: {name}")
        else:
            if not probe.get("clock_ready") or probe.get("owner_java_thread_id",0)<=0:
                raise AssertionError("ThreadMXBean clock unavailable or wrong thread")
            if (stat["calls"]<5000
                    or stat["calls"]!=census[CENSUS_KEYS[name]]
                    or stat["samples"]<MIN_SAMPLES_PER_PATH
                    or not (0<=stat["zero_deltas"]<=stat["samples"])
                    or stat["cpu_ns"]<0
                    or stat["cpu_ns"]>cpu["server_thread_cpu_running_ns"]):
                raise AssertionError(f"Invalid sparse clock sample in {name}: {stat}")
            # A fixed ordinal hash must produce roughly a 1/32 selection;
            # loose 25% gate avoids unplanned selection of favorable subsets.
            expected=stat["calls"]/DENOMINATOR
            if abs(stat["samples"]-expected)/expected>0.25:
                raise AssertionError(f"Sampling rate drifted from 1/32 in {name}")
    return {"cpu":cpu,"probe":probe,"census":census}


def run_native(arm:str,mode:str)->dict:
    cmd=[
        sys.executable,str(ROOT/"scripts"/"run_veinminer_profile.py"),
        "--stack","fabric","--compiler-mode","score-add","--side","6",
        "--no-spark","--capture-server-thread-cpu",
        "--scheduler-path-census","--scheduler-task-cpu-probe",mode,
        "--capture-timeout","150","--setup-rcon-timeout-seconds","45",
        "--startup-readiness-record",str(OUT/f"startup-{arm}.json"),
        "--tick-stability-diagnostics","--pre-event-idle-seconds","9",
    ]
    env=os.environ.copy()
    env.pop("GRADLE_RO_DEP_CACHE",None)
    env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
    env["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
    done=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,
                        timeout=750,check=False)
    (OUT/f"{arm}.stdout.log").write_text(done.stdout,encoding="utf-8")
    (OUT/f"{arm}.stderr.log").write_text(done.stderr,encoding="utf-8")
    if done.returncode:
        raise RuntimeError(
            f"{arm} native event failed (exit {done.returncode}): "
            f"{done.stderr[-3000:]!r}; stdout tail {done.stdout[-1000:]!r}")
    payload=json.loads(done.stdout)
    data=payload["results"]
    validated=validate_native(data,mode)
    return {
        "arm":arm,"mode":mode,"publisher_sha256":data["datapack_sha256"],
        "native_state":{k:data[k] for k in STATE_FIELDS},
        "server_thread_cpu_running_ns":
            validated["cpu"]["server_thread_cpu_running_ns"],
        "host_quality_pass":validated["cpu"]["host_quality_pass"],
        "event_completion_seconds":data["operation_completion_seconds"],
        "queue_score_add_compiled":data["queue_score_add_compiled"],
        "census":validated["census"],"probe":validated["probe"],
        "native_result_json":payload.get("output"),
    }


def interpret(records:dict[str,dict])->dict:
    if set(records)!={name for name,_ in ARMS}:
        raise AssertionError("Missing a whole independent calibration arm")
    if {r["publisher_sha256"] for r in records.values()}!={EXPECTED_PACK_SHA}:
        raise AssertionError("Different original publisher archive")
    if len({json.dumps(r["native_state"],sort_keys=True) for r in records.values()})!=1:
        raise AssertionError("Native final world/scoreboard state differs")
    for name,mode in ARMS:
        r=records[name]
        if r["mode"]!=mode or not r["host_quality_pass"]:
            raise AssertionError(f"Invalid mode or host in {name}")

    plain=records["plain"]
    control=records["empty_control"]
    timed=records["timed_tasks"]
    cpu_total=timed["server_thread_cpu_running_ns"]
    cpu_shift=abs(cpu_total-plain["server_thread_cpu_running_ns"])/plain["server_thread_cpu_running_ns"]
    if cpu_shift>MAX_EVENT_CPU_PERTURBATION:
        return {
            "diagnostic_valid":False,
            "decision":"inconclusive_instrumentation_or_host_variance",
            "observed_timed_plain_cpu_shift":cpu_shift,
            "limitations":"Separate JVM boots cannot establish instrumented overhead causally",
        }

    analysis={}
    for name in PATHS:
        a=control["probe"]["streams"][name]
        b=timed["probe"]["streams"][name]
        for key in ("calls","samples"):
            if (abs(a[key]-b[key])/max(a[key],b[key])
                    > (MAX_RELATIVE_CALL_DIFFERENCE if key=="calls"
                       else MAX_RELATIVE_SAMPLE_DIFFERENCE)):
                raise AssertionError(f"{name} clock exposure unmatched: {key}")
        ctrl_mean=a["cpu_ns"]/a["samples"]
        timed_mean=b["cpu_ns"]/b["samples"]
        signed=timed_mean-ctrl_mean
        zero_fraction=b["zero_deltas"]/b["samples"]
        clock_resolved=signed>0 and zero_fraction<=MAX_TIMED_ZERO_FRACTION
        fraction=signed*b["calls"]/cpu_total
        analysis[name]={
            "control_total_calls":a["calls"],
            "timed_total_calls":b["calls"],
            "control_sampled_calls":a["samples"],
            "timed_sampled_calls":b["samples"],
            "empty_clock_pair_mean_ns":ctrl_mean,
            "timed_inclusive_sample_mean_ns":timed_mean,
            "signed_clock_corrected_ns_per_call":signed,
            "projected_inclusive_cpu_ns":signed*b["calls"],
            "projected_fraction_of_timed_server_cpu":fraction,
            "timed_zero_delta_fraction":zero_fraction,
            "clock_resolved":clock_resolved,
            "decision":("descriptive_inclusive_cost_only" if clock_resolved
                        else "inconclusive_clock_floor_or_negative_estimate"),
        }
    return {
        "diagnostic_valid":True,
        "workload_parity_verified":True,
        "independent_jvm_arms":True,
        "sample_denominator":DENOMINATOR,
        "plain_server_cpu_ns":plain["server_thread_cpu_running_ns"],
        "empty_server_cpu_ns":control["server_thread_cpu_running_ns"],
        "timed_server_cpu_ns":cpu_total,
        "observed_timed_plain_cpu_shift":cpu_shift,
        "paths":analysis,
        "decision":"method_cpu_sample_screen",
        "limitations":(
            "Sparse ordinal-hash selection is not proven representative of all"
            " dynamic path costs; sample mean and projection can be biased."
            " ThreadMXBean nanosecond precision is not nanosecond accuracy."
            " Independent JVM boots may have different JIT and host states."
            " CPU intervals are INCLUSIVE and may overlap between task methods,"
            " so DO NOT SUM the projected fractions as a disjoint breakdown."
            " Empty clock-pair control omits Mixin/aggregation CPU outside reads."
            " Neither whole-event CPU differences nor projected method CPU"
            " fractions are causal savings or an avoidable scheduler upper bound."
        ),
    }


def main()->int:
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"diagnostic.json"
    report={
        "study":"SCHED-ATTR-025",
        "status":"started",
        "noncausal":True,
        "diagnostic_only":True,
        "arms":[n for n,_ in ARMS],
        "records":{},
    }
    path.write_text(json.dumps(report,indent=2)+"\n")
    try:
        report["publisher_pack_sha256"]=verify_pack()
        for name,mode in ARMS:
            print(f"SCHED-ATTR-025 CPU ARM {name}",flush=True)
            report["records"][name]=run_native(name,mode)
            path.write_text(json.dumps(report,indent=2)+"\n")
        report["analysis"]=interpret(report["records"])
        report["status"]=("complete" if report["analysis"]["diagnostic_valid"]
                          else "inconclusive_quality")
        print("SCHED-ATTR-025 "+report["status"].upper()+" "
              +json.dumps(report["analysis"]),flush=True)
    except BaseException as error:
        report["status"]="failed"
        report["error"]=repr(error)
        raise
    finally:
        path.write_text(json.dumps(report,indent=2)+"\n")
    return 0 if report["status"]=="complete" else 1

if __name__=="__main__":
    raise SystemExit(main())
