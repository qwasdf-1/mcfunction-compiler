#!/usr/bin/env python3
"""IR-023 original-world passive marker mutation/visibility census.

CONTROL and PLAIN each use one new original publisher JVM. Both run IR022's
exact selector observer in UNWRAPPED CONTROL mode. IR023 CONTROL records no
counters; PLAIN counts original native tag, load, removal, storage and tracking
events. It does NOT intercept entityTags() direct set modifications, determine
individual combined-predicate rejections or implement any selector replacement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
import zipfile

from ci_server_event_cpu import (
    find_server_thread, read_thread_schedstat, cgroup_throttle_count, event_cpu_delta
)
from ci_typed_ir019_blastback import (
    setup, stop, ROOT, PACK, PINS, WITNESSES,
    block_matches, region_matches_template, score
)
from ci_typed_ir022_cpu import parse_cpu022, EXACT_ORIGINAL_LINE, WINDOW_SECONDS

OUT=ROOT/"build/reports/COMPILER-IR-023-NATIVE"
PIN=PINS["blastback"]["sha256"]
MODES=("control","plain")
METRICS=(
    "add_block_attempt","add_block_changed","add_block_noop",
    "add_verified_attempt","add_verified_changed","add_verified_noop",
    "remove_block_attempt","remove_block_changed","remove_block_noop",
    "remove_verified_attempt","remove_verified_changed","remove_verified_noop",
    "eligible_entered","eligible_left",
    "marker_load","load_with_block","load_eligible",
    "marker_manager_added","manager_added_with_block","manager_added_eligible",
    "marker_tracked","tracked_with_block","tracked_eligible",
    "marker_untracked","untracked_with_block","untracked_eligible",
    "marker_removed","removed_with_block","removed_eligible",
    "removed_unloaded_chunk","removed_changed_dimension",
    "removed_killed","removed_discarded","removed_other","invalid"
)

def parse_cpu023(raw: str, mode: str)->dict[str,int]:
    start=0
    end=0
    rows={}
    for line in raw.splitlines():
        if "FC_CPU023_BEGIN mode=" in line:
            start+=1
            if "FC_CPU023_BEGIN mode="+mode not in line:
                raise AssertionError("IR023 began with wrong mode")
        elif "FC_CPU023_END mode=" in line:
            end+=1
            if "FC_CPU023_END mode="+mode not in line:
                raise AssertionError("IR023 ended with wrong mode")
        elif "FC_CPU023_ROW " in line:
            items=dict(re.findall(r"(\w+)=(\S+)",line.split("FC_CPU023_ROW ",1)[1]))
            name=items.get("kind")
            if name not in METRICS or name in rows:
                raise AssertionError("Unexpected/duplicate IR023 counter: "+str(name))
            try: rows[name]=int(items["count"])
            except (KeyError,ValueError) as exc: raise AssertionError("Bad IR023 row") from exc
    if start!=1 or end!=1 or set(rows)!=set(METRICS):
        raise AssertionError("Incomplete IR023 counter dump")
    if any(x<0 for x in rows.values()) or rows["invalid"]:
        raise AssertionError("Negative/invalid IR023 counters")
    if mode=="control" and any(rows.values()):
        raise AssertionError("IR023 CONTROL must leave all counters at zero")
    for op in ("add","remove"):
        for tag in ("block","verified"):
            key=f"{op}_{tag}"
            if rows[f"{key}_attempt"]!=rows[f"{key}_changed"]+rows[f"{key}_noop"]:
                raise AssertionError(f"IR023 successful/no-op conservation failure: {key}")
    if rows["eligible_entered"]>rows["add_block_changed"]+rows["remove_verified_changed"]:
        raise AssertionError("IR023 entering membership transition impossible")
    if rows["eligible_left"]>rows["remove_block_changed"]+rows["add_verified_changed"]:
        raise AssertionError("IR023 leaving membership transition impossible")
    for head,values in {
        "marker_load":("load_with_block","load_eligible"),
        "marker_manager_added":("manager_added_with_block","manager_added_eligible"),
        "marker_tracked":("tracked_with_block","tracked_eligible"),
        "marker_untracked":("untracked_with_block","untracked_eligible"),
        "marker_removed":("removed_with_block","removed_eligible")
    }.items():
        if any(rows[v]>rows[head] for v in values):
            raise AssertionError(f"IR023 event/cardinality impossible for {head}")
    if rows["marker_removed"]!=sum(rows[f"removed_{r}"] for r in
        ("unloaded_chunk","changed_dimension","killed","discarded","other")):
        raise AssertionError("IR023 removal-reason accounting does not reconcile")
    return rows

def run_arm(mode: str)->dict:
    output=OUT/mode
    output.mkdir(parents=True,exist_ok=True)
    proc,client,log=setup(cpu_mode=mode,output=output,cpu_family="023")
    report={"mode":mode,"status":"started","original_publisher_sha256":PIN,
            "no_compiler":True,"cpu023_passive_counting": mode=="plain","full_restoration_claim":False,
            "causal_speedup_claim":False,"window_seconds":WINDOW_SECONDS}
    try:
        for command in (
            "gamerule sendCommandFeedback false",
            "gamerule doMobSpawning false",
            "gamerule doDaylightCycle false",
            "gamerule randomTickSpeed 0",
            "gamerule maxEntityCramming 10000",
            "difficulty peaceful",
            "scoreboard objectives add fc_probe dummy",
            "forceload add -16 -16 16 16",
            "forceload add 64 32",
            "fill -4 63 -4 12 63 12 minecraft:stone",
        ):
            client.command(command)
        for block,position in WITNESSES.items():
            if block=="stone":continue
            x,y,z=position
            client.command(f"setblock {x} {y} {z} minecraft:{block}")
        # Fluid/block tick work during first world load can change source
        # while the 17^3 template clone is being established. Repeat only
        # this PRE-event setup, at most 3 attempts. No unsuccessful timed
        # event is dropped or retried, and pre-event source/template equality
        # remains an absolute admission gate for all three arms.
        clone_attempts=[]
        before={}
        before_template=False
        for _ in range(3):
            response=client.command("clone -4 56 -4 12 72 12 64 56 32 replace force")
            before={block:block_matches(client,block,*pos)
                    for block,pos in WITNESSES.items()}
            before_template=region_matches_template(client)
            clone_attempts.append({
                "clone_response":response,"template_equal":before_template,
                "all_named_witnesses":all(before.values())})
            if all(before.values()) and before_template:break
            time.sleep(0.2)
        report["pre_event_clone_attempts"]=clone_attempts
        if not all(before.values()) or not before_template:
            raise AssertionError(
                f"Original Blastback pre-event fixture invalid after bounded preparation "
                f"{clone_attempts!r}; witnesses={before!r}")
        report["original_world_before"]={"witnesses":before,"template_equal":before_template}
        # Actor setup and observation MUST finish before the clock/census
        # begins, so a flaky RCON presence probe cannot contaminate TIMED.
        # The bounded retries are PRE-EVENT only; failed game work is never
        # omitted, and all three arms must still accept exactly one TNT.
        minecraft_pid,server_tid=find_server_thread(proc.pid)
        spawn=client.command(
            'summon minecraft:tnt 4 64 4 {Fuse:160s,Tags:["fc_blastback_probe"]}')
        if "Summoned new" not in spawn:
            raise AssertionError(f"Original native TNT summon declined: {spawn!r}")
        actor=0
        actor_probes=[]
        for _ in range(12):
            client.command("scoreboard players set #ir022_tnt fc_probe 0")
            client.command("execute as @e[type=minecraft:tnt,tag=fc_blastback_probe] "
                           "run scoreboard players add #ir022_tnt fc_probe 1")
            actor=score(client,"#ir022_tnt","fc_probe")
            actor_probes.append(actor)
            if actor==1:break
            time.sleep(0.1)
        report["pre_event_actor_probes"]=actor_probes
        if actor!=1:
            raise AssertionError(
                f"Original native TNT not observed before CPU window: {actor_probes!r} {spawn!r}")
        tick_before=score(client,"#tick_id","erb.cfg")
        status=client.command("functioncompiler cpu022-start")
        if "FC_CPU022 started mode=control" not in status:
            raise AssertionError(f"Native original-clock mode unavailable: {status!r}")
        stage=client.command("functioncompiler cpu023-start")
        if f"FC_CPU023 started mode={mode}" not in stage:
            raise AssertionError(f"Native IR023 observer unavailable: {stage!r}")
        cpu_before=read_thread_schedstat(minecraft_pid,server_tid)
        throttle_before=cgroup_throttle_count()
        time.sleep(WINDOW_SECONDS)
        cpu_after=read_thread_schedstat(minecraft_pid,server_tid)
        throttle_after=cgroup_throttle_count()
        stage=client.command("functioncompiler cpu023-stop")
        if f"FC_CPU023 ended mode={mode}" not in stage:
            raise AssertionError(f"IR023 stop failed: {stage!r}")
        status=client.command("functioncompiler cpu022-stop")
        if "FC_CPU022 ended mode=control" not in status:
            raise AssertionError(f"Native original-clock stop unavailable: {status!r}")
        tick_after=score(client,"#tick_id","erb.cfg")
        after={block:block_matches(client,block,*pos) for block,pos in WITNESSES.items()}
        report["original_world_after"]={
            "witnesses":after,
            "template_equal":region_matches_template(client)
        }
        report["native_actor_seen"]=actor
        report["tick_before"]=tick_before
        report["tick_after"]=tick_after
        report["tick_delta"]=tick_after-tick_before
        report["server_thread_cpu"]=event_cpu_delta(
            cpu_before,cpu_after,throttle_before,throttle_after)
        time.sleep(0.3)
        raw=(output/"server.log").read_text(errors="replace")
        raw_rows="\n".join(line for line in raw.splitlines() if "FC_CPU022_" in line)
        (output/"clock-rows.log").write_text(raw_rows+"\n",encoding="utf-8")
        rows=parse_cpu022(raw_rows,"control")
        report["cpu_rows"]=rows
        report["mutation_rows"]=parse_cpu023(raw,mode)
        # Native source and exact-candidate selection must actually run.
        if report["tick_delta"]<100 or rows["selector_find_entire"]["visits"]<50:
            raise AssertionError(f"No original native selector event in {mode}")
        for kind in ("selector_build_predicate","selector_gather_entities",
                     "selector_sort_and_limit"):
            if rows[kind]["visits"]<50:
                raise AssertionError(f"Native original selector stage absent in {mode}: {kind}")
        if rows["selector_find_entire"]["outputs"]<1000:
            raise AssertionError("The original one-TNT datapack did not select meaningful entities")
        if rows["native_type_try_cast"]["visits"] or rows["native_composite_predicate"]["visits"]:
            raise AssertionError("Control arm changed the native type or predicate objects")
        if not report["server_thread_cpu"]["cpu_measurement_valid"]:
            raise AssertionError("Invalid native server CPU clock")
        report["status"]="accepted_native_descriptive_arm"
        print("IR023_MUTATION_ARM "+json.dumps({
            "mode":mode,"tick_delta":report["tick_delta"],
            "cpu_ns":report["server_thread_cpu"]["server_thread_cpu_running_ns"],
            "host_quality_pass":report["server_thread_cpu"]["host_quality_pass"],
            "rows":rows,"mutations":report["mutation_rows"],"native_actor_seen":actor
        },sort_keys=True),flush=True)
        return report
    except BaseException as failure:
        report["status"]="invalid"
        report["error"]=repr(failure)
        raise
    finally:
        stop(proc,client,log)
        (output/"results.json").write_text(json.dumps(report,indent=2)+"\n")



def main()->None:
    OUT.mkdir(parents=True,exist_ok=True)
    if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest()!=PIN:
        raise AssertionError("Exact original Blastback publisher ZIP pin mismatch")
    with zipfile.ZipFile(PACK) as archive:
        original=archive.read("data/erb/function/restore/job_tick.mcfunction").decode("utf-8")
    commands=[x.strip() for x in original.splitlines() if x.strip() and
              not x.lstrip().startswith("#")]
    if len(commands)<5 or commands[4]!=EXACT_ORIGINAL_LINE or commands.count(EXACT_ORIGINAL_LINE)!=1:
        raise AssertionError("Exact original Blastback restore/job_tick selector source changed")
    results={"milestone":"COMPILER-IR-023","stage":"native_passive_tag_and_lifecycle_census",
             "publisher_sha256":PIN,"status":"started","arms":{},
             "original_selector_022_unwrapped_in_both_arms":True,
             "real_world_tag_mutation_complete":False,
             "direct_mutable_tag_set_writes_observable":False,
             "selector_replacement":False,"causal_speedup_claim":False,
             "full_restoration_claim":False}
    try:
        for mode in MODES:
            results["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")
        c=results["arms"]["control"]
        p=results["arms"]["plain"]
        q0=c["cpu_rows"]["selector_find_entire"]
        q1=p["cpu_rows"]["selector_find_entire"]
        if min(q0["visits"],q1["visits"])<50 or max(q0["visits"],q1["visits"])/min(
                q0["visits"],q1["visits"])>1.5:
            raise AssertionError("Original selector workload exposure diverged")
        if min(q0["outputs"],q1["outputs"])<1000 or max(q0["outputs"],q1["outputs"])/min(
                q0["outputs"],q1["outputs"])>1.5:
            raise AssertionError("Original native selector outputs diverged")
        native=p["mutation_rows"]
        if native["marker_manager_added"]<=0 or native["marker_tracked"]<=0:
            raise AssertionError("No observed original marker storage lifecycle")
        if native["add_block_changed"]<=0:
            raise AssertionError("Original Blastback produced no tracked block tags")
        selectors=q1["visits"]
        results["analysis"]={
            "selector_visits":selectors,
            "selected_sources":q1["outputs"],
            "tag_add_success":native["add_block_changed"]+native["add_verified_changed"],
            "tag_remove_success":native["remove_block_changed"]+native["remove_verified_changed"],
            "effective_tag_eligibility_transitions":native["eligible_entered"]+native["eligible_left"],
            "successful_watched_tag_changes_per_selector":
                (native["add_block_changed"]+native["add_verified_changed"]+
                 native["remove_block_changed"]+native["remove_verified_changed"])/selectors,
            "tracked_lifecycle_events": native["marker_manager_added"]+
                native["marker_removed"]+native["marker_tracked"]+native["marker_untracked"],
            "original_tag_set_direct_writes_not_observable":True,
            "native_load_events_observed":native["marker_load"],
            "causal_cpu_claim":False,
            "index_admissibility_not_proved":True,
        }
        results["status"]="accepted_bounded_partial_mutation_census"
        print("IR023_MUTATION_SUMMARY "+json.dumps(results["analysis"],sort_keys=True),flush=True)
    except BaseException as exc:
        results["status"]="invalid"
        results["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")


if __name__=="__main__":
    main()
