#!/usr/bin/env python3
"""IR027 ORIGINAL-PUBLISHER native completion oracle forensic.

NO optimizer, NO CPU study, NO datapack edits. Two separately booted native
Minecraft 26.3 JVMs, one no-event placebo (template stability) and one
unchanged original one-TNT publisher. Observe native scoreboard status/collect,
remaining/verified/failed block markers, and per-y-slice template equality
at natural tick checkpoints. Explicitly preserve a blocked native outcome.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import ci_typed_ir026_blastback as base
from ci_typed_ir013 import stop
from ci_typed_ir017 import nullable_score
from run_blastback_profile import score, region_matches_template

ROOT=base.ROOT
OUT=ROOT/"build/reports/COMPILER-IR-027-NATIVE-ORACLE"
TICK_TARGETS=(600,1200,2400)
NO_EVENT_TICKS=600
MAX_WAIT_SECONDS=210
MAX_SNAPSHOT_TICKS=80
MAX_POLL_OVERSHOOT=30
COUNTERS={
    "bpt":("#bpt","erb.cfg"),
    "enabled":("#enabled","erb.cfg"),
    "groups_active":("#groups_active","erb.cfg"),
    "captures_active":("#captures_active","erb.cfg"),
    "verification_active":("#verification_active","erb.cfg"),
    "protected_active":("#protected_active","erb.cfg"),
    "watchers_active":("#watchers_active","erb.cfg"),
    "unresolved_active":("#unresolved_active","erb.cfg"),
    "restore_due":("#restore_due","erb.tmp"),
    "needs_restore":("#needs_restore","erb.tmp"),
    "active_job":("#active","erb.job"),
    "capturing":("#capturing","erb.tmp"),
    "queued":("#queued","erb.tmp"),
    "groups":("#groups","erb.tmp"),
    "saved":("#saved","erb.tmp"),
    "explosions":("#explosions","erb.tmp"),
    "paused":("#paused","erb.tmp"),
    "effective":("#effective","erb.tmp"),
    "max_group":("#max_group","erb.tmp"),
    "max_quiet":("#max_quiet","erb.tmp"),
}
SELECTORS={
    **base.MARKERS,
    "unresolved":"@e[type=minecraft:marker,tag=erb.block,tag=erb.unresolved]",
    "verifying":"@e[type=minecraft:marker,tag=erb.block,tag=erb.verifying]",
    "audited":"@e[type=minecraft:marker,tag=erb.block,tag=erb.audit_done]",
    "retry_3plus":"@e[type=minecraft:marker,tag=erb.block,scores={erb.retry=3..}]",
    "verify_wait":"@e[type=minecraft:marker,tag=erb.block,scores={erb.verify=1..}]",
    "fluid_eligible":"@e[type=minecraft:marker,tag=erb.block,tag=erb.fluid,tag=!erb.verified]",
    "late_eligible":"@e[type=minecraft:marker,tag=erb.block,tag=erb.late,tag=!erb.verified]",
    "job_marker":"@e[type=minecraft:marker,tag=erb.job_marker]",
    "restore_job":"@e[type=minecraft:marker,tag=erb.restore_job]",
    "segment":"@e[type=minecraft:marker,tag=erb.segment]",
    "group_member":"@e[type=minecraft:marker,tag=erb.group_member]",
    "danger_zone":"@e[type=minecraft:marker,tag=erb.danger_zone]",
    "protected_item":"@e[type=minecraft:item,tag=erb.protected]",
}

def count_native(client,holder:str,selector:str)->int:
    client.command(f"scoreboard players set {holder} fc_probe 0")
    client.command(f"execute store result score {holder} fc_probe "
                   f"if entity {selector}")
    count=score(client,holder,"fc_probe")
    if count<0:raise AssertionError("Negative native entity count")
    return count

def observe(client,label:str,include_slices:bool)->dict:
    start=score(client,"#tick_id","erb.cfg")
    # This is the publisher's own read-only-to-gameplay status routine. It
    # updates its scratch statistics but does not change original entities.
    response=client.command("function erb:status/collect")
    status={key:nullable_score(client,holder,objective)
            for key,(holder,objective) in COUNTERS.items()}
    markers={key:count_native(client,"#fc027_count",selector)
             for key,selector in SELECTORS.items()}
    whole=region_matches_template(client)
    slices={}
    if include_slices:
        for y in range(56,73):
            client.command(
                "execute store success score #fc027_slice fc_probe run "
                f"execute if blocks -4 {y} -4 12 {y} 12 64 {y} 32 all")
            slices[str(y)]=score(client,"#fc027_slice","fc_probe")==1
    witnesses=base.native_witnesses(client)
    end=score(client,"#tick_id","erb.cfg")
    if end-start>MAX_SNAPSHOT_TICKS:
        raise AssertionError(
            f"Diagnostic observations advanced {end-start} datapack ticks")
    if markers["block"]!=markers["verified"]+markers["eligible"]:
        raise AssertionError("Original live marker tag cardinality inconsistent")
    if any(not match for match in witnesses.values()):
        raise AssertionError("Original injected block witness changed")
    report={
        "label":label,"tick_start":start,"tick_end":end,
        "observation_tick_span":end-start,"original_status_response":response,
        "publisher_counters":status,"marker_counts":markers,
        "whole_template_equal":whole,"y_slice_equal":slices,
        "failed_y_slices":[int(y) for y,passed in slices.items() if not passed],
        "witnesses":witnesses,
    }
    print("IR027_NATIVE_ORACLE_CHECKPOINT "+json.dumps({
       "label":label,"ticks":start,"status":{k:status.get(k) for k in (
           "groups_active","groups","saved","verification_active",
           "bpt","effective","paused","max_quiet","needs_restore")},
       "markers":markers,
       "template":whole,"failed_y":report["failed_y_slices"]},
       sort_keys=True),flush=True)
    return report

def until(client,target:int,deadline:float):
    while True:
        now=score(client,"#tick_id","erb.cfg")
        if now>=target:
            if now-target>MAX_POLL_OVERSHOOT:
                raise AssertionError("Tick poll skipped too far beyond checkpoint")
            return now
        if time.monotonic()>deadline:
            raise AssertionError(f"Original server stopped progressing at {now}, "
                                  f"target={target}")
        time.sleep(.22)

def configure_stable_original_scene(client)->dict:
    """New research fixture, NOT the earlier naturally generated IR026 scene.

    The full source and template are fixed stone rather than a single stone
    plane over naturally generated caves/water; the original Blastback pack
    remains byte-identical. The no-event arm must show long-term template
    stability before a TNT arm is considered interpretable.
    """
    for cmd in (
        "gamerule sendCommandFeedback false",
        "gamerule doMobSpawning false",
        "gamerule doDaylightCycle false",
        "gamerule doWeatherCycle false",
        "gamerule randomTickSpeed 0",
        "gamerule maxEntityCramming 10000",
        "difficulty peaceful",
        "scoreboard objectives add fc_probe dummy",
        "forceload add -16 -16 16 16",
        "forceload add 64 32",
        # New *controlled* fixture. Never claim that it replicates IR026's
        # natural-world terrain mix or its prior CPU/work denominator.
        "fill -4 56 -4 12 72 12 minecraft:stone",
    ):
        client.command(cmd)
    for block,pos in base.WITNESSES.items():
        if block!="stone":
            x,y,z=pos
            client.command(f"setblock {x} {y} {z} minecraft:{block}")
    attempts=[]
    for _ in range(3):
        result=client.command(
            "clone -4 56 -4 12 72 12 64 56 32 replace force")
        match=region_matches_template(client)
        witnesses=base.native_witnesses(client)
        attempts.append({"clone":result,"full_template_equal":match,
                         "witnesses":witnesses})
        if match and all(witnesses.values()):
            return {"scene":"controlled_full_stone_17_cube",
                    "original_publisher_unchanged":True,
                    "natural_IR026_terrain_comparability_claim":False,
                    "pre_event_clone_attempts":attempts}
        time.sleep(.2)
    raise AssertionError("Controlled fixed stone scene did not initialize: "
                         +repr(attempts))

def prove_original_capture_activity(client,actor_start_tick:int)->dict:
    """Observe one original saved-block/restore-job marker AFTER spawning TNT.

    A vanished TNT and a restored stone template alone could be a false
    positive if an obstructed TNT never triggered Blastback. This checkpoint
    samples native selectors for at most 360 original datapack ticks and
    requires publisher-owned capture/restore marker evidence. The counters
    are read-only observations through vanilla selectors, not debug callbacks.
    """
    deadline=time.monotonic()+60
    sampled=0
    maximum_blocks=0
    maximum_jobs=0
    first_observed=None
    last_tick=actor_start_tick
    while last_tick-actor_start_tick<360:
        last_tick=score(client,"#tick_id","erb.cfg")
        block=count_native(client,"#fc027_count",
                           "@e[type=minecraft:marker,tag=erb.block]")
        job=count_native(client,"#fc027_count",
                         "@e[type=minecraft:marker,tag=erb.restore_job]")
        sampled+=1
        maximum_blocks=max(maximum_blocks,block)
        maximum_jobs=max(maximum_jobs,job)
        if (block>0 or job>0) and first_observed is None:
            first_observed={"delta_tick":last_tick-actor_start_tick,
                            "block":block,"restore_jobs":job}
            break
        if time.monotonic()>deadline:
            raise AssertionError("Original TNT event did not generate observable "
                                 "publisher capture markers within 60 seconds")
        time.sleep(.25)
    report={
        "first_original_capture":first_observed,
        "sampled_native_selectors":sampled,
        "max_original_block_markers":maximum_blocks,
        "max_original_restore_jobs":maximum_jobs,
        "last_actor_relative_tick":last_tick-actor_start_tick,
        "compiled_code_used":False,
    }
    if first_observed is None:
        raise AssertionError("No native original Blastback capture or restoration "
                             "activity proved after tagged TNT actor")
    print("IR027_NATIVE_CAPTURE_WITNESS "+json.dumps(report,sort_keys=True),
          flush=True)
    return report

def run(mode:str)->dict:
    if mode not in ("no_tnt","native_tnt"):
        raise ValueError("No compiler arms admitted in source restoration diagnosis")
    base.OUT=OUT
    proc,client,log=base.launch("native")
    result={"mode":mode,"status":"started","sha256":base.PIN,
            "original_tnt_mode":mode=="native_tnt",
            "native_only":True,"compiler_executed":False,
            "cpu_claim":False,"full_restoration_claim":False,
            "checkpoints":[]}
    try:
        result["pre_event_scene"]=configure_stable_original_scene(client)
        if not region_matches_template(client):
            raise AssertionError("Original source differs from template before event")
        start=score(client,"#tick_id","erb.cfg")
        result["event_before_tick"]=start
        if mode=="native_tnt":
            result["native_tnt_spawn"],result["tnt_observations"]=(
                base.verify_started_actor(client))
            start=score(client,"#tick_id","erb.cfg")
            result["event_before_tick"]=start
            result["original_capture_witness"]=prove_original_capture_activity(
                client,start)
        targets=(NO_EVENT_TICKS,) if mode=="no_tnt" else TICK_TARGETS
        deadline=time.monotonic()+MAX_WAIT_SECONDS
        for delta in targets:
            now=until(client,start+delta,deadline)
            check=observe(client,f"{mode}@{delta}",include_slices=True)
            check["target_event_delta"]=delta
            check["actual_start_tick_delta"]=now-start
            result["checkpoints"].append(check)
        if mode=="no_tnt":
            if not result["checkpoints"][-1]["whole_template_equal"]:
                raise AssertionError(
                    "No-TNT control source/template changed by natural world activity")
            if result["checkpoints"][-1]["marker_counts"]["block"]!=0:
                raise AssertionError("No TNT spawned but Blastback block markers exist")
        else:
            result["tnt_remaining_after"]=count_native(
                client,"#fc027_count",
                "@e[type=minecraft:tnt,tag=fc_blastback_probe]")
            if result["tnt_remaining_after"]!=0:
                raise AssertionError("The originally spawned TNT actor never detonated")
            last=result["checkpoints"][-1]
            saved=last["marker_counts"]["block"]
            jobs=last["marker_counts"]["restore_job"]
            # Valid *completion* is stronger than one function's scratch
            # score. Original finish_job_macro cleans remaining block and job
            # markers after auditing. If not complete, preserve all evidence
            # rather than declaring a compiler or oracle failure.
            result["original_job_complete"]=(saved==0 and jobs==0)
            result["original_template_restored"]=last["whole_template_equal"]
            if result["original_job_complete"] and result["original_template_restored"]:
                result["status"]="original_native_complete_and_restored"
            elif result["original_job_complete"]:
                result["status"]="native_job_complete_but_template_different"
            else:
                result["status"]="native_restore_not_complete"
        if mode=="no_tnt":result["status"]="no_event_template_stable"
        print("IR027_NATIVE_ORACLE_ARM "+json.dumps({
            "mode":mode,"status":result["status"],
            "checkpoints":len(result["checkpoints"]),
            "final_markers":result["checkpoints"][-1]["marker_counts"],
            "final_template":result["checkpoints"][-1]["whole_template_equal"],
            "no_compiler":True},sort_keys=True),flush=True)
        return result
    except BaseException as exc:
        result["status"]="invalid_forensic_arm"
        result["error"]=repr(exc)
        raise
    finally:
        stop(proc,client,log)
        (OUT/(mode+".json")).write_text(json.dumps(result,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    publisher=base.original_publisher()
    report={"milestone":"COMPILER-IR-027","status":"started",
            "study":"original_unmodified_publisher_completion_oracle",
            "publisher":publisher,"arms":{},
            "performance_claim":False,"production_promotion":False,
            "no_compiler_modes":True}
    try:
        report["arms"]["no_tnt"]=run("no_tnt")
        report["arms"]["native_tnt"]=run("native_tnt")
        outcome=report["arms"]["native_tnt"]["status"]
        if outcome=="original_native_complete_and_restored":
            report["status"]="native_completion_oracle_found"
            report["cpu_promotion_gate_open"]=False
        else:
            report["status"]="native_completion_oracle_blocked"
            report["blocked_reason"]=outcome
            report["cpu_promotion_gate_open"]=False
        print("IR027_NATIVE_ORACLE_SUMMARY "+json.dumps({
            "status":report["status"],"native_result":outcome,
            "no_event_template_stable":True,
            "completion_ticks":TICK_TARGETS,
            "cpu_study_authorized":False},sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid_native_oracle_investigation"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
