#!/usr/bin/env python3
"""COMPILER-IR-026 Stage B: tick-matched original publisher game-state study.

Run the SHA256-pinned unmodified Blastback source in three fresh original,
typed plan-only and compiled-fork Minecraft 26.3 JVMs. Stop at the same
observed datapack tick count, NOT the same elapsed wall-clock time.

Only observable witness, template, fake-score and entity/tag population
properties are checked. Because the original Blastback restoration oracle is
unresolved and entity ordering/identity are not compared, even an accepted
tick-matched gate DOES NOT certify complete behavioral equivalence or CPU gains.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import ci_typed_ir026_blastback as base
from ci_typed_ir013 import stop, stat
from run_blastback_profile import score

ROOT=base.ROOT
OUT=ROOT/"build/reports/COMPILER-IR-026-TICK-MATCHED"
MODES=base.MODES
TARGET_TICKS=600
MAX_SAMPLE_OVERSHOOT=20
MAX_OBSERVATION_SECONDS=100
MAX_MARKER_RELATIVE_DEVIATION=0.02
WATCHED=(("active_job","active_job"),("needs_restore","needs_restore"))

def run_arm(mode:str):
    proc,client,log=base.launch(mode)
    report={
        "mode":mode,"status":"started","original_publisher_sha256":base.PIN,
        "stop_rule":"datapack_tick_count","target_delta_ticks":TARGET_TICKS,
        "wallclock_performance_claim":False,"complete_restoration_claim":False,
        "original_datapack_mutated":False,"original_selector_replacement":False,
    }
    try:
        report["setup"]=base.configure_original_scene(client)
        report["original_ledger"]=base.ledger_gate(client,mode)
        report["before"]=base.snapshot(client)
        if not all(report["before"]["witnesses"].values()):
            raise AssertionError("Original five-block source witnesses missing")
        report["actor_spawn"],report["actor_checks"]=base.verify_started_actor(client)
        tick0=score(client,"#tick_id","erb.cfg")
        report["actor_tick_before"]=tick0
        target=tick0+TARGET_TICKS
        start=time.monotonic()
        checkpoints=[]
        while True:
            ticks=score(client,"#tick_id","erb.cfg")
            if ticks>=target:break
            if time.monotonic()-start>MAX_OBSERVATION_SECONDS:
                raise AssertionError(
                    f"Native publisher insufficient ticks {mode}: {ticks-tick0}")
            if len(checkpoints)<12 and (not checkpoints or ticks-tick0>=
                (len(checkpoints)+1)*50):
                checkpoints.append({"delta":ticks-tick0})
            time.sleep(.20)
        report["tick_at_stop_request"]=ticks
        report["tick_stop_overshoot"]=ticks-target
        if report["tick_stop_overshoot"]>MAX_SAMPLE_OVERSHOOT:
            raise AssertionError("Tick-matched observation overshot target: "
                                 +repr(report["tick_stop_overshoot"]))
        report["after"]=base.snapshot(client)
        report["tick_at_snapshot_end"]=report["after"]["scoreboard"]["tick_id"]
        report["snapshot_read_span"] = (
            report["tick_at_snapshot_end"]-ticks)
        if report["snapshot_read_span"]>MAX_SAMPLE_OVERSHOOT:
            raise AssertionError("Native snapshot took too many datapack ticks")
        client.command("scoreboard players set #ir026_tnt fc_probe 0")
        client.command(
            "execute as @e[type=minecraft:tnt,tag=fc_blastback_probe] "
            "run scoreboard players add #ir026_tnt fc_probe 1")
        report["tnt_remaining"]=score(client,"#ir026_tnt","fc_probe")
        if report["tnt_remaining"]!=0:
            raise AssertionError("One original TNT did not complete detonation")
        markers=report["after"]["marker_counts"]
        # Strict population accounting: every erb.block marker is either
        # verified or eligible (original @e tag criterion). Equalities
        # are measured independently, with no shared compiler membership cache.
        if markers["block"]<1000 or markers["block"]!=(
            markers["verified"]+markers["eligible"]):
            raise AssertionError("Original entity tag membership conservation failed")
        if mode!="native":
            diag=client.command("functioncompiler ir025")
            report["compiled_fork_diagnostics"]=diag
            if not diag.startswith("IR025 enabled="):
                raise AssertionError("Missing original target compiler diagnostics")
            if mode=="compiled":
                for key in ("compiled_forks","executed_forks",
                            "selector_scans","selected_sources","passing_sources"):
                    if stat(diag,key)<=0:
                        raise AssertionError(
                            f"Compiled fork not exercised by original {mode}: {key} {diag}")
            else:
                if stat(diag,"executed_forks")!=0:
                    raise AssertionError("Plan-only original fork ran compiled logic")
        report["status"]="accepted_original_tick_matched_arm"
        report["observed_wall_seconds_informational"] = time.monotonic()-start
        print("IR026_TICK_MATCHED_ARM "+json.dumps({
            "mode":mode,"actual_target_ticks":ticks-tick0,
            "snapshot_read_span":report["snapshot_read_span"],
            "marker_counts":markers,
            "witnesses":report["after"]["witnesses"],
            "template_equal":report["after"]["template_equal"],
            "scoreboard":report["after"]["scoreboard"],
            "fork":report.get("compiled_fork_diagnostics"),
            "no_speedup_claim":True
        },sort_keys=True),flush=True)
        return report
    except BaseException as exc:
        report["status"]="invalid_original_tick_matched_arm"
        report["error"]=repr(exc)
        raise
    finally:
        stop(proc,client,log)
        (OUT/(mode+".json")).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

def compare(a:dict,b:dict)->dict:
    aa=a["after"]
    bb=b["after"]
    markers={key:{
        "native":aa["marker_counts"][key],
        "comparison":bb["marker_counts"][key],
        "absolute_difference":bb["marker_counts"][key]-aa["marker_counts"][key]
    } for key in base.MARKERS}
    block_fraction=abs(markers["block"]["absolute_difference"])/max(
        1,markers["block"]["native"])
    verified_fraction=abs(markers["verified"]["absolute_difference"])/max(
        1,markers["verified"]["native"])
    fake_scores_equal={key:aa["scoreboard"][key]==bb["scoreboard"][key]
                       for key in ("active_job","needs_restore")}
    return {
        "witnesses_match":aa["witnesses"]==bb["witnesses"],
        "template_status_matches":aa["template_equal"]==bb["template_equal"],
        "fake_scores_match":fake_scores_equal,
        "markers":markers,
        "block_relative_deviation":block_fraction,
        "verified_relative_deviation":verified_fraction,
        "coarse_entity_population_within_2percent":(
            block_fraction<=MAX_MARKER_RELATIVE_DEVIATION and
            verified_fraction<=MAX_MARKER_RELATIVE_DEVIATION),
        "eligible_exact_equality_claim":False,
        "exact_marker_identity_order_claim":False,
        "full_world_equivalence_claim":False,
        "same_tick_count_requested":True,
        "causal_speedup_claim":False,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    publisher=base.original_publisher()
    report={
        "milestone":"COMPILER-IR-026",
        "stage":"original_publisher_tick_matched_native_semantic_gate",
        "publisher":publisher,"status":"started","arms":{},"comparisons":{},
        "same_work_basis":"original_datapack_600_ticks_from_actor_confirmed",
        "performance_claim":False,"full_restoration_claim":False,
        "production_promotion":False,
    }
    try:
        base.OUT=OUT  # all three reports are segregated from wall-clock stage
        for mode in MODES:
            report["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        original=report["arms"]["native"]
        for mode in MODES[1:]:
            result=compare(original,report["arms"][mode])
            report["comparisons"][mode]=result
            if not result["witnesses_match"] or not result["template_status_matches"]:
                raise AssertionError(
                    "Original game blocks/template diverged under matching ticks "
                    +mode+" "+json.dumps(result))
            if not all(result["fake_scores_match"].values()):
                raise AssertionError(
                    "Original job/restore score status differs under matched ticks: "
                    +mode+" "+json.dumps(result))
            if not result["coarse_entity_population_within_2percent"]:
                raise AssertionError(
                    "Original marker population differs by >2 percent in "
                    +mode+" "+json.dumps(result))
        report["status"]="accepted_bounded_original_tick_matched_gate"
        report["same_work_tick_gate"]=True
        report["complete_behavioral_equivalence"]=False
        print("IR026_TICK_MATCHED_SUMMARY "+json.dumps({
            "status":report["status"],
            "publisher_sha256":base.PIN,
            "tick_deltas":{m:report["arms"][m]["tick_at_stop_request"]-
                          report["arms"][m]["actor_tick_before"] for m in MODES},
            "marker_counts":{m:report["arms"][m]["after"]["marker_counts"]
                             for m in MODES},
            "witness_parity":{m:report["comparisons"][m]["witnesses_match"]
                              for m in MODES[1:]},
            "no_speedup_claim":True,
            "no_full_restoration_claim":True,
        },sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid_original_tick_matched_gate"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
