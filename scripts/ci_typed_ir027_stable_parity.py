#!/usr/bin/env python3
"""IR027 ORIGINAL PUBLISHER controlled full-restoration semantic comparison.

A new, separately identified *solid-stone* research fixture has a proven
no-TNT unchanged template and native one-TNT capture+complete restoration.
Three separate Minecraft 26.3 JVMs load EXACT unedited publisher SHA bytes.
Native, plan-only and emitted compiled fork modes all:
 (1) prove a tagged original TNT actor,
 (2) observe the original publisher's own nonzero capture markers,
 (3) finish all block and job markers, with detonated TNT,
 (4) match every block in the 17^3 source/template at 600 AND 900 ticks,
 (5) preserve original five named witness blocks and normalized scoreboard.

This is a semantics gate, NOT a CPU benchmark; original IR026 natural-terrain
workload is not comparable to this new controlled stone fixture.
"""
from __future__ import annotations
import json,time
from pathlib import Path
import ci_typed_ir026_blastback as base
import ci_typed_ir027_native_oracle as oracle
from ci_typed_ir013 import stop,stat
from run_blastback_profile import score

OUT=base.ROOT/"build/reports/COMPILER-IR-027-COMPLETED"
MODES=("native","plan_only","compiled")
CHECKPOINTS=(600,900)
MAX_WAIT_SECONDS=145
REQUIRED_GONE=(
    "block","eligible","verified","unresolved","verifying","restore_job",
    "job_marker","segment","group_member","danger_zone","protected_item",
    "verify_wait","retry_3plus",
)
STATUS_EQUAL=("saved","groups","capturing","queued","explosions","paused")
SNAPSHOT_FIELDS=("whole_template_equal","marker_counts","witnesses")

def checkpoint_accepted(s:dict)->bool:
    markers=s["marker_counts"]
    return (s["whole_template_equal"]
            and all(markers[key]==0 for key in REQUIRED_GONE)
            and all(s["witnesses"].values())
            and all(s["publisher_counters"].get(k) in (0,None)
                    for k in STATUS_EQUAL)
            and s["publisher_counters"].get("needs_restore") in (0,None))

def arm(mode:str):
    base.OUT=OUT
    proc,client,log=base.launch(mode)
    report={"mode":mode,"status":"started","publisher_sha256":base.PIN,
            "publisher_bytes_unchanged":True,
            "controlled_stone_scene_distinct_from_IR026":True,
            "full_restoration_claim_limited_to_test_volume":True,
            "cpu_speedup_claim":False,
            "independent_gameplay_state_claim":False,
            "checkpoints":[]}
    try:
        report["pre_scene"]=oracle.configure_stable_original_scene(client)
        report["compiled_source_ledger"]=base.ledger_gate(client,mode)
        report["original_tnt_spawn"],report["tnt_observations"]=(
            base.verify_started_actor(client))
        actor_tick=score(client,"#tick_id","erb.cfg")
        report["actor_tick"]=actor_tick
        report["original_capture_witness"]=oracle.prove_original_capture_activity(
            client,actor_tick)
        deadline=time.monotonic()+MAX_WAIT_SECONDS
        for dt in CHECKPOINTS:
            tick=oracle.until(client,actor_tick+dt,deadline)
            state=oracle.observe(client,f"{mode}@{dt}",include_slices=True)
            state["target_actor_relative_tick"]=dt
            state["actual_actor_relative_tick"]=tick-actor_tick
            if not checkpoint_accepted(state):
                raise AssertionError(
                    "Original publisher's complete native state fails in "
                    +mode+" @"+str(dt)+": "+json.dumps({
                        "markers":state["marker_counts"],
                        "failed_y":state["failed_y_slices"],
                        "status":state["publisher_counters"]}))
            report["checkpoints"].append(state)
        report["native_tnt_remaining"]=oracle.count_native(
            client,"#fc027_count",
            "@e[type=minecraft:tnt,tag=fc_blastback_probe]")
        if report["native_tnt_remaining"]!=0:
            raise AssertionError("Real TNT still exists at completion checkpoint")
        if mode!="native":
            diag=client.command("functioncompiler ir025")
            report["fork_diagnostics"]=diag
            if not diag.startswith("IR025 enabled="):
                raise AssertionError("No live compiler fork diagnostic")
            if mode=="compiled":
                if "IR025 enabled=true" not in diag:
                    raise AssertionError("Compiler fork is disabled")
                for key in ("compiled_forks","executed_forks",
                            "selector_scans","selected_sources"):
                    if stat(diag,key)<=0:
                        raise AssertionError("Compiled original fork not executed "
                                             +key+" "+diag)
                if stat(diag,"native_fallbacks")!=0:
                    raise AssertionError(
                        "Original compiled fork unexpectedly ran the full native action")
            else:
                if "IR025 enabled=false" not in diag or stat(diag,"executed_forks")!=0:
                    raise AssertionError("Plan-only arm accidentally compiled fork execution")
            report["compiled_source_ledger_after"]=base.ledger_gate(client,mode)
        report["status"]="accepted_original_publisher_full_volume_restoration_arm"
        print("IR027_COMPLETED_ARM "+json.dumps({
            "mode":mode,"checkpoints":CHECKPOINTS,
            "original_capture":report["original_capture_witness"],
            "source_ledger":report["compiled_source_ledger"],
            "fork":report.get("fork_diagnostics","native"),
            "template_equal":True,
            "all_original_job_and_block_markers_gone":True,
            "tnt_detonated":True,"cpu_claim":False},
            sort_keys=True),flush=True)
        return report
    except BaseException as exc:
        report["status"]="invalid_original_publisher_restoration_arm"
        report["error"]=repr(exc)
        raise
    finally:
        stop(proc,client,log)
        (OUT/(mode+".json")).write_text(json.dumps(report,indent=2)+"\n")

def normalized(s:dict)->dict:
    return {"template":s["whole_template_equal"],
            "y_slices":s["y_slice_equal"],
            "witnesses":s["witnesses"],
            "markers":{key:s["marker_counts"][key] for key in REQUIRED_GONE},
            "finish_counters":{
                 key:s["publisher_counters"].get(key)
                 for key in (*STATUS_EQUAL,"needs_restore")}}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    publisher=base.original_publisher()
    report={"milestone":"COMPILER-IR-027","status":"started",
            "stage":"completed_original_publisher_full_world_volume_semantic_parity",
            "publisher":publisher,"arms":{},
            "same_original_17cube_scene":True,
            "no_tnt_stability_proved_separately":True,
            "performance_claim":False,"production_promotion":False}
    try:
        # The source+same world must be compared on new independent native,
        # plan-only and compiled server JVMs; no synthetic function rewriting.
        for mode in MODES:
            report["arms"][mode]=arm(mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        native=report["arms"]["native"]["checkpoints"]
        for mode in MODES[1:]:
            compare=report["arms"][mode]["checkpoints"]
            report.setdefault("comparisons",{})[mode]=[]
            for expected,observed in zip(native,compare,strict=True):
                a=normalized(expected)
                b=normalized(observed)
                diff={"target":expected["target_actor_relative_tick"],
                      "native":a,"comparison":b,
                      "normalized_equal":a==b}
                report["comparisons"][mode].append(diff)
                if a!=b:
                    raise AssertionError("Completed original Blastback world-state "
                                         "diverged: "+mode+" "+json.dumps(diff))
        report["status"]="accepted_original_complete_world_volume_native_parity"
        report["same_work_restoration_gate"]=True
        print("IR027_COMPLETED_SUMMARY "+json.dumps({
            "status":report["status"],"publisher_sha256":base.PIN,
            "modes":MODES,"full_volume_matches":{m:True for m in MODES},
            "checkpoint_ticks":CHECKPOINTS,
            "original_capture_proven_all_modes":True,
            "original_tnt_finished_all_modes":True,
            "compiled_native_selector_executed":True,
            "cpu_claim":False,"global_entity_index":False,
        },sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid_original_completion_parity"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
