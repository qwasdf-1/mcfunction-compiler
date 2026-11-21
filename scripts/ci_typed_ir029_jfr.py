#!/usr/bin/env python3
"""IR029 JFR stack attribution of original Blastback plan-only vs compiled fork.

This is a separate profile, not an uninstrumented CPU benchmark. Four fresh
Java25/Minecraft26.3 servers run A-B-B-A with the same unchanged original
publisher and the IR027 controlled stone fixture. JFR profile sampling starts
before the original one-TNT capture+restore event and stops at 600 datapack
ticks. We inspect Server-thread ExecutionSample stacks only.

The report compares inclusive stack-presence fractions. These categories
overlap; do not sum them or interpret them as exclusive CPU percentages.
JFR sampling perturbs execution and cannot revise IR028 CPU numbers.
"""
from __future__ import annotations
import json
import os
import shutil
import statistics
import subprocess
import time
from collections import Counter
from pathlib import Path

import ci_typed_ir026_blastback as base
import ci_typed_ir027_native_oracle as oracle
import ci_typed_ir028_cpu as cpu
from ci_server_event_cpu import find_server_thread
from run_blastback_profile import score

OUT=base.ROOT/"build/reports/COMPILER-IR-029-JFR"
RUN_ORDER=(("A1","plan_only"),("B1","compiled"),
           ("B2","compiled"),("A2","plan_only"))
TARGET_TICKS=600
MAX_WAIT_SECONDS=105
MIN_SAMPLES=300
MIN_CAPTURE_MARKERS=1000
PROFILE_NAME="IR029"
STACK_DEPTH=64

# These are inclusive stack-presence categories, not disjoint costs.
TARGETS={
    "build_contexts":lambda c,m:"BuildContexts" in c,
    "brigadier_run_modifier":lambda c,m:c.endswith("ContextChain") and m=="runModifier",
    "entity_selector_find":lambda c,m:c.endswith("EntitySelector") and m=="findEntities",
    "source_with_entity":lambda c,m:c.endswith("CommandSourceStack") and m=="withEntity",
    "compiled_executor_run":lambda c,m:c=="dev.functioncompiler.CompilerForkExecutor025" and m=="run",
    "compiled_generated_action":lambda c,m:c.startswith("dev.functioncompiler.CompiledFork025$Generated") and m=="execute",
    "scoreboard_player_lookup":lambda c,m:c.endswith("Scoreboard") and m=="getPlayerScoreInfo",
    "continuation_schedule":lambda c,m:c.endswith("ContinuationTask") and m=="schedule",
    "array_list_add":lambda c,m:c=="java.util.ArrayList" and m=="add",
    "array_list_grow":lambda c,m:c=="java.util.ArrayList" and m=="grow",
    "entity_type_try_cast":lambda c,m:c.endswith("EntityType") and m=="tryCast",
    "selector_option_predicate":lambda c,m:c.endswith("EntitySelectorOptions") and m.startswith("lambda$bootStrap$"),
    "hash_set_contains":lambda c,m:c=="java.util.HashSet" and m=="contains",
    "hash_map_contains_key":lambda c,m:c=="java.util.HashMap" and m=="containsKey",
}

def java_tool(name:str)->str:
    home=os.environ.get("JAVA_HOME")
    candidate=Path(home)/"bin"/name if home else None
    if candidate is not None and candidate.is_file():
        return str(candidate)
    found=shutil.which(name)
    if found is None:
        raise RuntimeError(f"Java tool {name} not found in JAVA_HOME or PATH")
    return found

def attach(pid:int,*args:str)->str:
    result=subprocess.run([java_tool("jcmd"),str(pid),*args],
                          capture_output=True,text=True,timeout=30)
    output=(result.stdout or "")+(result.stderr or "")
    if result.returncode!=0:
        raise RuntimeError(f"jcmd {args[0]} failed ({result.returncode}): {output}")
    return output.strip()

def start_recording(pid:int)->str:
    output=attach(pid,"JFR.start",f"name={PROFILE_NAME}",
                  "settings=profile","disk=true","dumponexit=false",
                  "maxage=3m","maxsize=64m")
    if "Started recording" not in output:
        raise RuntimeError(f"JFR did not confirm start: {output}")
    return output

def dump_recording(pid:int,path:Path)->str:
    output=attach(pid,"JFR.dump",f"name={PROFILE_NAME}",f"filename={path}")
    if "Dumped recording" not in output or not path.is_file() or path.stat().st_size==0:
        raise RuntimeError(f"JFR dump missing or empty: {output}")
    stopped=attach(pid,"JFR.stop",f"name={PROFILE_NAME}")
    if "Stopped recording" not in stopped:
        raise RuntimeError(f"JFR did not confirm stop: {stopped}")
    return output

def frame_identity(frame:dict)->tuple[str,str]:
    method=frame.get("method") or {}
    typ=method.get("type") or {}
    # JFR JSON can render some names as internal slash-separated names and
    # others as dotted binary names. Normalize before exact class matching.
    return str(typ.get("name") or "").replace("/", "."),str(method.get("name") or "")

def summarize_jfr(path:Path,server_tid:int)->dict:
    printed=subprocess.run(
        [java_tool("jfr"),"print","--json","--events","jdk.ExecutionSample",
         "--stack-depth",str(STACK_DEPTH),str(path)],
        capture_output=True,text=True,timeout=120)
    if printed.returncode!=0:
        raise RuntimeError("jfr print failed: "+(printed.stderr or printed.stdout)[-4000:])
    payload=json.loads(printed.stdout)
    events=payload.get("recording",{}).get("events")
    if not isinstance(events,list):
        raise AssertionError("Unexpected JFR JSON schema: recording.events missing")
    server=[]
    for event in events:
        if event.get("type")!="jdk.ExecutionSample":
            continue
        values=event.get("values") or {}
        thread=values.get("sampledThread") or {}
        if int(thread.get("osThreadId",-1))!=server_tid:
            continue
        server.append(values)
    runnable=[e for e in server if e.get("state")=="STATE_RUNNABLE"]
    if len(runnable)<MIN_SAMPLES:
        raise AssertionError(
            f"Only {len(runnable)} runnable Server-thread JFR samples; "
            f"need at least {MIN_SAMPLES} (all-thread events={len(events)})")
    inclusive=Counter()
    leaf=Counter()
    generated_samples=[]
    identities_by_event=[]
    for event in runnable:
        frames=(event.get("stackTrace") or {}).get("frames") or []
        identities=[frame_identity(frame) for frame in frames]
        identities_by_event.append(identities)
        if identities:
            leaf[identities[0][0]+"."+identities[0][1]]+=1
        for key,predicate in TARGETS.items():
            if any(predicate(c,m) for c,m in identities):
                inclusive[key]+=1
        if any(TARGETS["compiled_generated_action"](c,m) for c,m in identities):
            generated_samples.append(identities)
    nested=Counter()
    for identities in generated_samples:
        for key,predicate in TARGETS.items():
            if key in ("compiled_executor_run","compiled_generated_action"):
                continue
            if any(predicate(c,m) for c,m in identities):
                nested[key]+=1
    return {
        "recording_bytes":path.stat().st_size,
        "execution_sample_events_all_threads":len(events),
        "server_thread_os_tid":server_tid,
        "server_thread_execution_samples":len(server),
        "server_thread_runnable_samples":len(runnable),
        "server_thread_nonrunnable_samples":len(server)-len(runnable),
        "inclusive_stack_sample_counts":dict(inclusive),
        "inclusive_stack_sample_fractions":{
            key:inclusive[key]/len(runnable) for key in TARGETS},
        "compiled_action_runnable_samples":len(generated_samples),
        "compiled_action_sample_fraction":len(generated_samples)/len(runnable),
        "compiled_action_nested_stack_sample_counts":dict(nested),
        "compiled_action_nested_stack_sample_fractions":{
            key:nested[key]/len(generated_samples) if generated_samples else 0.0
            for key in TARGETS if key not in ("compiled_executor_run","compiled_generated_action")},
        "top_leaf_frames":[{"frame":name,"samples":count}
                           for name,count in leaf.most_common(20)],
        "categories_are_overlapping":True,
        "jfr_profile_is_not_cpu_benchmark":True,
    }

def run_arm(label:str,mode:str)->dict:
    base.OUT=OUT
    base.options=cpu.mode_options
    proc,client,log=base.launch(mode)
    result={"label":label,"mode":mode,"status":"started",
            "publisher_sha256":base.PIN,"original_publisher_unchanged":True,
            "fixture":"IR027 controlled full-stone 17-cube",
            "profile":"JFR settings=profile, jdk.ExecutionSample",
            "cpu_speedup_claim":False}
    recording=OUT/(label+".jfr")
    recording_started=False
    pid=None
    try:
        result["pre_scene"]=oracle.configure_stable_original_scene(client)
        flags=cpu.mode_options(mode)
        expected={
            "FC_TYPED_IR_MODE":"bytecode",
            "FC_TYPED_IR_NAMESPACE":"erb",
            "FC_TYPED_IR_FUNCTION_FILTER":base.TARGET,
            "FC_TYPED_IR_NATIVE_FORK_PLAN":"true",
            "FC_TYPED_IR_COMPILED_FORK":str(mode=="compiled").lower(),
            "FC_TYPED_IR_REENTRANT_SAFE":"true",
            "FC_TYPED_IR_DIAGNOSTICS":"false",
        }
        for key,value in expected.items():
            if flags.get(key)!=value:
                raise AssertionError(f"Unexpected JFR arm flag {key}={flags.get(key)!r}, expected {value!r}")
        result["compiler_mode_flags"]={key:flags.get(key) for key in expected}
        pid,tid=find_server_thread(proc.pid)
        result["server_pid"]=pid
        result["server_thread_tid"]=tid
        result["jfr_start"]=start_recording(pid)
        recording_started=True
        tick0=score(client,"#tick_id","erb.cfg")
        result["event_start_tick"]=tick0
        result["native_tnt_spawn"],result["actor_checks"]=(
            base.verify_started_actor(client))
        deadline=time.monotonic()+20
        marker_seen=0
        samples=0
        while marker_seen<MIN_CAPTURE_MARKERS:
            marker_seen=max(marker_seen,oracle.count_native(
                client,"#fc027_count",
                "@e[type=minecraft:marker,tag=erb.block]"))
            samples+=1
            if marker_seen>=MIN_CAPTURE_MARKERS:break
            if time.monotonic()>deadline:
                raise AssertionError("Original publisher capture marker witness absent")
            time.sleep(.2)
        result["capture_markers_sampled"]=marker_seen
        result["capture_probe_attempts"]=samples
        stopped=oracle.until(client,tick0+TARGET_TICKS,
                             time.monotonic()+MAX_WAIT_SECONDS)
        result["event_tick_exposure"]=stopped-tick0
        if result["event_tick_exposure"]<TARGET_TICKS or result["event_tick_exposure"]>TARGET_TICKS+25:
            raise AssertionError("JFR event exposure exceeded tick tolerance")
        result["jfr_dump"]=dump_recording(pid,recording)
        recording_started=False
        result["profile"]=summarize_jfr(recording,tid)
        after=oracle.observe(client,f"{label}@{TARGET_TICKS}",include_slices=True)
        result["post_event_original_state"]=after
        for key in ("block","restore_job","job_marker","unresolved","verifying"):
            if after["marker_counts"][key]!=0:
                raise AssertionError("Original event incomplete: "+key)
        if not after["whole_template_equal"] or not all(after["witnesses"].values()):
            raise AssertionError("Original full-volume template not restored")
        result["native_tnt_remaining"]=oracle.count_native(
            client,"#fc027_count",
            "@e[type=minecraft:tnt,tag=fc_blastback_probe]")
        if result["native_tnt_remaining"]!=0:
            raise AssertionError("Original TNT still present after event")
        result["status"]="accepted_original_event_jfr_profile"
        print("IR029_JFR_ARM "+json.dumps({
            "label":label,"mode":mode,
            "server_samples":result["profile"]["server_thread_runnable_samples"],
            "capture_markers":marker_seen,
            "template_restored":True,
            "profile_fractions":result["profile"]["inclusive_stack_sample_fractions"],
            "cpu_claim":False},sort_keys=True),flush=True)
        return result
    except BaseException as exc:
        result["status"]="invalid_jfr_profile_arm"
        result["error"]=repr(exc)
        raise
    finally:
        if recording_started and pid is not None:
            try:attach(pid,"JFR.stop",f"name={PROFILE_NAME}")
            except BaseException:pass
        cpu.stop(proc,client,log)
        (OUT/(label+".json")).write_text(json.dumps(result,indent=2)+"\n")

def analyze(arms:dict)->dict:
    if set(arms)!={label for label,_ in RUN_ORDER}:
        raise AssertionError("Missing JFR profile arm")
    result={"inclusive_profile_fractions":{},
            "server_thread_sample_counts":{},
            "top_leaf_frames":{},
            "categories_overlap":True,
            "causal_cpu_claim":False}
    for label,_ in RUN_ORDER:
        profile=arms[label]["profile"]
        result["server_thread_sample_counts"][label]=profile["server_thread_runnable_samples"]
        result["top_leaf_frames"][label]=profile["top_leaf_frames"]
    for mode in ("plan_only","compiled"):
        labels=[label for label,arm_mode in RUN_ORDER if arm_mode==mode]
        result["inclusive_profile_fractions"][mode]={
            key:statistics.mean(
                arms[label]["profile"]["inclusive_stack_sample_fractions"][key]
                for label in labels)
            for key in TARGETS}
    a=result["inclusive_profile_fractions"]["plan_only"]
    b=result["inclusive_profile_fractions"]["compiled"]
    result["compiled_minus_plan_sample_fraction"]={key:b[key]-a[key] for key in TARGETS}
    result["compiled_path_sampled"]=any(
        arms[label]["profile"]["inclusive_stack_sample_counts"].get(
            "compiled_executor_run",0)>0
        or arms[label]["profile"]["inclusive_stack_sample_counts"].get(
            "compiled_generated_action",0)>0
        for label,mode in RUN_ORDER if mode=="compiled")
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.options=cpu.mode_options
    report={"milestone":"COMPILER-IR-029","status":"started",
            "study":"jfr_stack_attribution_not_cpu_benchmark",
            "publisher":base.original_publisher(),
            "run_order":[{"label":a,"mode":m} for a,m in RUN_ORDER],
            "arms":{},"analysis":None,"cpu_claim":False,
            "profile_overhead_present":True}
    try:
        for label,mode in RUN_ORDER:
            report["arms"][label]=run_arm(label,mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        report["analysis"]=analyze(report["arms"])
        report["status"]="accepted_jfr_attribution_profile"
        print("IR029_JFR_SUMMARY "+json.dumps({
            "status":report["status"],
            "sample_counts":report["analysis"]["server_thread_sample_counts"],
            "profile_fractions":report["analysis"]["inclusive_profile_fractions"],
            "compiled_path_sampled":report["analysis"]["compiled_path_sampled"],
            "cpu_claim":False},sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid_jfr_attribution_profile"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
