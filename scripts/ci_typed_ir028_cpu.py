#!/usr/bin/env python3
"""IR028 RESEARCH-ONLY CPU A/A, A/B (opt-in), original Blastback complete event.

Prerequisite: independently accepted IR027 original/plan-only/compiled
stable stone-world, observed capture and full-volume completion oracle.
No profiler, mixin counters, selector replacement, tag index or caching.
The only A->B treatment is FC_TYPED_IR_COMPILED_FORK. Both modes compile
the same neighboring scoreboard regions. Four new Minecraft 26.3 Java25
servers run pre-registered ABBA order to detect noise and drift.

The published original natural-world IR026 workload is not identical to
this controlled full-stone event. Even clean data only supports a small
performance pilot; no production promotion or causal generalization.
"""
from __future__ import annotations
import json
import statistics
from pathlib import Path
import time

import ci_typed_ir026_blastback as base
import ci_typed_ir027_native_oracle as oracle
from ci_typed_ir013 import stop
from ci_server_event_cpu import (
    find_server_thread,read_thread_schedstat,cgroup_throttle_count,event_cpu_delta
)
from run_blastback_profile import score,region_matches_template

OUT=base.ROOT/"build/reports/COMPILER-IR-028-CPU"
RUN_ORDER=(("A1","plan_only"),("B1","compiled"),
           ("B2","compiled"),("A2","plan_only"))
TARGET_TICKS=600
IDLE_STABILIZE_TICKS=60
MAX_POLL_OVERSHOOT=25
MAX_WAIT_SECONDS=105
MAX_AA_RELATIVE_SPREAD=.08
MIN_INTERPRETABLE_EVENT_WORK=1000
BASE_OPTIONS=base.options

def mode_options(mode:str)->dict:
    env=BASE_OPTIONS(mode)
    # In A and B, both type-IR regions are identical; the ONLY treatment is
    # generated native-selector fork execution. No diagnostic counter/timing
    # stream operates within the CPU measurement window.
    env.update({
        "FC_TYPED_IR_DIAGNOSTICS":"false",
        # Queue epoch guard is SEMANTICALLY REQUIRED by the accepted IR027\n        # compiler path. Keep it enabled in both arms; it is not a probe.\n        "FC_TYPED_IR_REENTRANT_SAFE":"true",
        "FC_TYPED_IR_COMPILED_FORK":str(mode=="compiled").lower(),
        "FC_COMPILER_EXEC_CENSUS":"false",
        "FC_RUNTIME_TRACE":"false",
        "FC_BENCH_COMPILE_TIMING":"false",
        "FC_SCORE_ADD_METRICS":"false",
        "FC_COMMAND_CALLBACK_METRICS":"false",
        "FC_CPU020_MODE":"","FC_CPU021_MODE":"",
        "FC_CPU022_MODE":"","FC_CPU023_MODE":"",
    })
    return env

def run_arm(label:str,mode:str)->dict:
    base.OUT=OUT
    base.options=mode_options
    proc,client,log=base.launch(mode)
    result={
        "label":label,"mode":mode,"status":"started",
        "original_publisher_sha256":base.PIN,
        "original_datapack_unchanged":True,
        "controlled_fixture_not_earlier_natural_world":True,
        "compiler_diagnostics_during_cpu":False,
        "global_entity_index":False,
        "causal_speedup_claim":False,
    }
    try:
        result["setup"]=oracle.configure_stable_original_scene(client)
        before_idle=score(client,"#tick_id","erb.cfg")
        oracle.until(client,before_idle+IDLE_STABILIZE_TICKS,
                     time.monotonic()+MAX_WAIT_SECONDS)
        if not region_matches_template(client):
            raise AssertionError("Pre-event controlled scene drifted before CPU window")
        if oracle.count_native(
            client,"#fc027_count","@e[type=minecraft:marker,tag=erb.block]")!=0:
            raise AssertionError("Unexpected pre-event marker population")
        pid,tid=find_server_thread(proc.pid)
        result["server_thread_pid"]=pid
        result["server_thread_tid"]=tid
        tick0=score(client,"#tick_id","erb.cfg")
        cpu_before=read_thread_schedstat(pid,tid)
        throttled_before=cgroup_throttle_count()
        # The ENTIRE real capture+restore workload is inside the clock. A
        # post-summon CPU start would miss Blastback's very early capture
        # phase, which was observed at actor tick 0 in original IR027.
        result["native_tnt_spawn"],result["actor_checks"]=(
            base.verify_started_actor(client))
        marker_seen=oracle.count_native(
            client,"#fc027_count","@e[type=minecraft:marker,tag=erb.block]")
        result["actual_original_capture_markers_seen"]=marker_seen
        if marker_seen<MIN_INTERPRETABLE_EVENT_WORK:
            raise AssertionError("One original TNT did not produce substantial "
                                 "native capture markers before CPU window close")
        stopped=oracle.until(
            client,tick0+TARGET_TICKS,time.monotonic()+MAX_WAIT_SECONDS)
        cpu_after=read_thread_schedstat(pid,tid)
        throttled_after=cgroup_throttle_count()
        exposure=stopped-tick0
        if exposure-TARGET_TICKS>MAX_POLL_OVERSHOOT or exposure<TARGET_TICKS:
            raise AssertionError("CPU event tick exposure not comparable")
        result["event_ticks"]=exposure
        result["server_thread_cpu"]=event_cpu_delta(
            cpu_before,cpu_after,throttled_before,throttled_after)
        result["cpu_running_ns_per_datapack_tick"]=(
            result["server_thread_cpu"]["server_thread_cpu_running_ns"]/exposure)
        # NO diagnostic snapshot contributes to the CPU measurement above.
        after=oracle.observe(client,f"{label}@{TARGET_TICKS}",include_slices=True)
        result["post_cpu_original_scene"]=after
        for key in ("block","restore_job","job_marker","unresolved","verifying"):
            if after["marker_counts"][key]!=0:
                raise AssertionError(f"Original restored event still has {key} markers")
        if not after["whole_template_equal"] or not all(after["witnesses"].values()):
            raise AssertionError("Completed original world differs from pre-TNT template")
        result["native_tnt_remaining"]=oracle.count_native(
            client,"#fc027_count",
            "@e[type=minecraft:tnt,tag=fc_blastback_probe]")
        if result["native_tnt_remaining"]!=0:
            raise AssertionError("Original TNT did not detonate in CPU event")
        result["status"]="accepted_uninstrumented_completed_event_cpu_arm"
        print("IR028_CPU_ARM "+json.dumps({
            "label":label,"mode":mode,
            "ticks":exposure,
            "capture_markers_seen":marker_seen,
            "cpu_ns":result["server_thread_cpu"]["server_thread_cpu_running_ns"],
            "cpu_ns_per_tick":result["cpu_running_ns_per_datapack_tick"],
            "host_quality":result["server_thread_cpu"]["host_quality_pass"],
            "cgroup_throttled":result["server_thread_cpu"]["cgroup_nr_throttled_delta"],
            "world_restored":True,
            "diagnostics":False,
        },sort_keys=True),flush=True)
        return result
    except BaseException as exc:
        result["status"]="invalid_cpu_arm"
        result["error"]=repr(exc)
        raise
    finally:
        stop(proc,client,log)
        (OUT/(label+".json")).write_text(json.dumps(result,indent=2)+"\n")

def analyze(arms:dict)->dict:
    if set(arms)!={label for label,_ in RUN_ORDER}:
        raise AssertionError("Missing pre-registered CPU arm")
    if any(arms[label]["mode"]!=mode for label,mode in RUN_ORDER):
        raise AssertionError("Original pre-registered ABBA labels/modes changed")
    vals={label:arms[label]["cpu_running_ns_per_datapack_tick"]
          for label,_ in RUN_ORDER}
    aa=abs(vals["A1"]-vals["A2"])/statistics.mean(
        (vals["A1"],vals["A2"]))
    median_a=statistics.median((vals["A1"],vals["A2"]))
    median_b=statistics.median((vals["B1"],vals["B2"]))
    all_host_valid=all(a["server_thread_cpu"]["host_quality_pass"]
                       for a in arms.values())
    world_same=all(a["post_cpu_original_scene"]["whole_template_equal"]
                   and a["post_cpu_original_scene"]["marker_counts"]["block"]==0
                   for a in arms.values())
    return {
        "host_quality_pass_all":all_host_valid,
        "complete_world_restored_in_every_arm":world_same,
        "A_A_relative_spread":aa,
        "A_A_stable_by_8pct_threshold":aa<=MAX_AA_RELATIVE_SPREAD,
        "A_cpu_ns_per_tick_median":median_a,
        "B_cpu_ns_per_tick_median":median_b,
        "B_relative_cpu_change_observed":(median_b-median_a)/median_a,
        "B_pilot_speedup_fraction_observed":(median_a-median_b)/median_a,
        "same_original_tnt_count_per_arm":1,
        "same_original_bounded_fixture":True,
        "n_per_treatment":2,
        "no_production_promotion":True,
        "not_representative_of_natural_IR026_terrain":True,
        "causal_speedup_confirmed":False,
        "performance_promotion_eligible":False,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    publisher=base.original_publisher()
    report={
        "milestone":"COMPILER-IR-028","status":"started",
        "stage":"opt_in_completed_original_event_uninstrumented_cpu_AA_AB",
        "publisher":publisher,
        "run_order":[{"label":a,"mode":m} for a,m in RUN_ORDER],
        "arms":{},"analysis":None,
        "preregistered_AA_noise_threshold":MAX_AA_RELATIVE_SPREAD,
        "full_event_CPU_window_includes_capture_and_restoration":True,
        "general_causal_speedup_claim":False,
        "production_promotion":False,
    }
    try:
        for label,mode in RUN_ORDER:
            report["arms"][label]=run_arm(label,mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        report["analysis"]=analyze(report["arms"])
        a=report["analysis"]
        if not a["complete_world_restored_in_every_arm"]:
            raise AssertionError("Original full-volume completion parity failed")
        if not a["host_quality_pass_all"] or not a["A_A_stable_by_8pct_threshold"]:
            report["status"]="inconclusive_host_or_AA_control"
        else:
            report["status"]="accepted_uninstrumented_cpu_pilot_no_promotion"
        print("IR028_CPU_SUMMARY "+json.dumps({
            "status":report["status"],"order":RUN_ORDER,
            "A_A_relative_spread":a["A_A_relative_spread"],
            "pilot_cpu_change_fraction":a["B_relative_cpu_change_observed"],
            "host_quality":a["host_quality_pass_all"],
            "world_same":a["complete_world_restored_in_every_arm"],
            "speedup_promotion":False,
        },sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid_original_cpu_study"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
