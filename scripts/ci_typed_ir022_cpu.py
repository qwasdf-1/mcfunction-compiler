#!/usr/bin/env python3
"""IR-022: exact original Blastback entity-selector candidate/type/filter/result study.

CONTROL uses unwrapped Mojang EntityTypeTest and Predicate objects.
PLAIN/EMPTY/TIMED use strictly delegating count/timing wrappers; these
diagnostic wrappers MAY perturb performance and are NOT compiler rewrites.
No native selector, scoreboard or function semantics are intentionally changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
import zipfile

from ci_server_event_cpu import (
    find_server_thread, read_thread_schedstat, cgroup_throttle_count,
    event_cpu_delta,
)
from ci_typed_ir019_blastback import (
    setup, stop, ROOT, PACK, PINS, WITNESSES,
    block_matches, region_matches_template, score,
)

OUT=ROOT/"build/reports/COMPILER-IR-022-CPU"
MODES=("control","plain","empty","timed")
WINDOW_SECONDS=30
STREAMS={
    "selector_find_entire":16,
    "selector_build_predicate":16,
    "selector_gather_entities":16,
    "native_type_try_cast":256,
    "native_composite_predicate":128,
    "selector_sort_and_limit":16,
}
MIN_SAMPLES={
    "selector_find_entire":24,
    "selector_build_predicate":24,
    "selector_gather_entities":24,
    "native_type_try_cast":8,
    "native_composite_predicate":128,
    "selector_sort_and_limit":24,
}
EXACT_ORIGINAL_LINE=(
    "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] "
    "if score @s erb.job = #active erb.job "
    "run scoreboard players set #needs_restore erb.tmp 1"
)
PIN=PINS["blastback"]["sha256"]


def parse_cpu021(text: str, mode: str)->dict:
    rows={}
    started=False
    ended=False
    for line in text.splitlines():
        if "FC_CPU021_BEGIN mode=" in line:
            if started:raise ValueError("Multiple IR022 BEGIN markers")
            started="FC_CPU021_BEGIN mode="+mode in line
        if "FC_CPU021_END mode=" in line:
            if ended:raise ValueError("Multiple IR022 END markers")
            ended="FC_CPU021_END mode="+mode in line
        if "FC_CPU021_ROW " in line:
            body=line.split("FC_CPU021_ROW ",1)[1]
            data=dict(re.findall(r"(\w+)=(\S+)",body))
            kind=data.get("kind")
            if kind not in STREAMS or kind in rows:
                raise AssertionError(f"Unexpected/duplicate IR022 native stream {kind}")
            rows[kind]={k:int(data[k]) for k in ("stride","visits","samples",
                                                 "cpu_ns","invalid","passed","outputs","max_outputs")}
    if not started or not ended or set(rows)!=set(STREAMS):
        raise AssertionError("Incomplete IR022 native start/stop CPU stream dump")
    for label,row in rows.items():
        if row["stride"]!=STREAMS[label]:
            raise AssertionError(f"Changed original clock stride: {label} {row}")
        if any(row[x]<0 for x in ("visits","samples","cpu_ns","invalid",
                                  "passed","outputs","max_outputs")):
            raise AssertionError(f"Negative selector accounting: {label} {row}")
        if row["invalid"] or row["max_outputs"]>row["outputs"]:
            raise AssertionError(f"Bad native selector stage: {label} {row}")
        is_wrapped=label in ("native_type_try_cast","native_composite_predicate")
        if mode=="control" and is_wrapped:
            if any(row[k] for k in ("visits","samples","cpu_ns","passed")):
                raise AssertionError(f"Control altered native filter identity: {label}")
        elif not is_wrapped and row["visits"]<=0:
            raise AssertionError(f"Missing native selector stage: {label}")
        elif is_wrapped and mode!="control" and label=="native_composite_predicate" and row["visits"]<1000:
            raise AssertionError(f"No real original combined tag predicate tests: {row}")
        expected=row["visits"]//row["stride"] if mode in ("empty","timed") else 0
        if row["samples"]!=expected:
            raise AssertionError(f"Missing sampled native stage: {mode}/{label} "
                                 f"{row['samples']} != {expected}")
        if mode in ("control","plain") and row["cpu_ns"]!=0:
            raise AssertionError(f"Unrequested Java CPU clock read: {mode}/{label}")
        if mode in ("empty","timed") and row["visits"] and row["samples"]<MIN_SAMPLES[label]:
            raise AssertionError(f"Underpowered original stage: {mode}/{label} {row}")
    return rows


def analysis(arms: dict)->dict:
    if set(arms)!=set(MODES):
        raise AssertionError("Requires one unwrapped CONTROL and three original diagnostic JVMs")
    results={}
    for kind in STREAMS:
        original=arms["control"]["cpu_rows"][kind]
        plain=arms["plain"]["cpu_rows"][kind]
        empty=arms["empty"]["cpu_rows"][kind]
        timed=arms["timed"]["cpu_rows"][kind]
        counts=[plain["visits"],empty["visits"],timed["visits"]]
        if kind=="native_type_try_cast" and max(counts)==0:
            results[kind]={"not_observed":True,
                           "reason":"Native storage prefilter may avoid tryCast for this exact type"}
            continue
        if min(counts)<=0 or max(counts)/min(counts)>1.50:
            raise AssertionError(f"Unequal original stage exposures {kind}: {counts}")
        if kind not in ("native_type_try_cast","native_composite_predicate"):
            all_counts=counts+[original["visits"]]
            if min(all_counts)<=0 or max(all_counts)/min(all_counts)>1.50:
                raise AssertionError(f"Original CONTROL vs wrappers differ in {kind}: {all_counts}")
        # Crucially, the delegated original predicate is not invoked for
        # nonmatching entity-type candidates. We do NOT pretend its count
        # reveals type-filter rejections, tag-only rejections or raw entities.
        mean_empty=empty["cpu_ns"]/empty["samples"]
        mean_timed=timed["cpu_ns"]/timed["samples"]
        signed=mean_timed-mean_empty
        results[kind]={
            "visits":{m:arms[m]["cpu_rows"][kind]["visits"] for m in MODES},
            "passed":{m:arms[m]["cpu_rows"][kind]["passed"] for m in MODES},
            "outputs":{m:arms[m]["cpu_rows"][kind]["outputs"] for m in MODES},
            "max_native_result":timed["max_outputs"],
            "empty_clock_mean_ns":mean_empty,
            "timed_method_inclusive_mean_ns":mean_timed,
            "signed_corrected_ns_per_call":signed,
            "signed_projection_server_cpu_fraction":
                signed*timed["visits"]/
                arms["timed"]["server_thread_cpu"]["server_thread_cpu_running_ns"],
            "original_unwrapped_control":kind not in ("native_type_try_cast",
                                                       "native_composite_predicate"),
            "removable_cpu_claim":False,
        }
    for mode in MODES:
        rows=arms[mode]["cpu_rows"]
        if rows["selector_find_entire"]["outputs"]<1000 or rows["selector_gather_entities"]["outputs"]<1000:
            raise AssertionError(f"Original large selector workload absent: {mode}")
        if rows["selector_find_entire"]["outputs"]!=rows["selector_sort_and_limit"]["passed"]:
            raise AssertionError(f"Native returned/sorted entity count diverged: {mode}")
        if rows["selector_gather_entities"]["outputs"]!=rows["selector_sort_and_limit"]["outputs"]:
            raise AssertionError(f"Native entity gathering/result pre-sort differs: {mode}")
        if mode!="control":
            if rows["native_composite_predicate"]["passed"]!=rows["selector_gather_entities"]["outputs"]:
                raise AssertionError(f"Original delegated combined selector predicate vs gathered outputs differ: {mode}")
            if rows["native_type_try_cast"]["visits"] and (
                    rows["native_type_try_cast"]["passed"]<rows["native_composite_predicate"]["visits"]):
                raise AssertionError("Delegated type candidates smaller than original predicate attempts")
    return {
        "status":"accepted_original_native_descriptive_selector_022",
        "four_independent_jvms":True,
        "control_uses_original_native_type_and_predicate_identity":True,
        "diagnostic_proxy_objects_are_perturbing_observers":True,
        "nested_inclusive_methods_not_additive":True,
        "type_rejected_total_not_directly_observed":True,
        "tag_only_rejected_total_not_directly_observed":True,
        "causal_speedup_claim":False,
        "world_restoration_claim":False,
        "native_clock":"ThreadMXBean current-thread CPU and /proc Server-thread schedstat",
        "rows":results
    }


def run_arm(mode: str)->dict:
    output=OUT/mode
    output.mkdir(parents=True,exist_ok=True)
    proc,client,log=setup(cpu_mode=mode,output=output,cpu_family="022")
    report={"mode":mode,"status":"started","original_publisher_sha256":PIN,
            "no_compiler":True,"full_restoration_claim":False,
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
        status=client.command("functioncompiler cpu021-start")
        if f"FC_CPU021 started mode={mode}" not in status:
            raise AssertionError(f"Native original-clock mode unavailable: {status!r}")
        cpu_before=read_thread_schedstat(minecraft_pid,server_tid)
        throttle_before=cgroup_throttle_count()
        time.sleep(WINDOW_SECONDS)
        cpu_after=read_thread_schedstat(minecraft_pid,server_tid)
        throttle_after=cgroup_throttle_count()
        status=client.command("functioncompiler cpu021-stop")
        if f"FC_CPU021 ended mode={mode}" not in status:
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
        raw_rows="\n".join(line for line in raw.splitlines() if "FC_CPU021_" in line)
        (output/"clock-rows.log").write_text(raw_rows+"\n",encoding="utf-8")
        rows=parse_cpu021(raw_rows,mode)
        report["cpu_rows"]=rows
        # Native source and exact-candidate selection must actually run.
        if report["tick_delta"]<100 or rows["selector_find_entire"]["visits"]<50:
            raise AssertionError(f"No original native selector event in {mode}")
        for kind in ("selector_build_predicate","selector_gather_entities",
                     "selector_sort_and_limit"):
            if rows[kind]["visits"]<50:
                raise AssertionError(f"Native original selector stage absent in {mode}: {kind}")
        if rows["selector_find_entire"]["outputs"]<1000:
            raise AssertionError("The original one-TNT datapack did not select meaningful entities")
        if mode!="control" and rows["native_composite_predicate"]["visits"]<1000:
            raise AssertionError("Delegated original combined predicate was not evaluated")
        if mode=="control" and (rows["native_type_try_cast"]["visits"] or
                                rows["native_composite_predicate"]["visits"]):
            raise AssertionError("Control arm changed the native type or predicate objects")
        if not report["server_thread_cpu"]["cpu_measurement_valid"]:
            raise AssertionError("Invalid native server CPU clock")
        report["status"]="accepted_native_descriptive_arm"
        print("IR022_CPU_ARM "+json.dumps({
            "mode":mode,"tick_delta":report["tick_delta"],
            "cpu_ns":report["server_thread_cpu"]["server_thread_cpu_running_ns"],
            "host_quality_pass":report["server_thread_cpu"]["host_quality_pass"],
            "rows":rows,"native_actor_seen":actor
        },sort_keys=True),flush=True)
        return report
    except BaseException as failure:
        report["status"]="invalid"
        report["error"]=repr(failure)
        raise
    finally:
        stop(proc,client,log)
        (output/"results.json").write_text(json.dumps(report,indent=2)+"\n")


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest()!=PIN:
        raise AssertionError("Exact original Blastback publisher ZIP pin mismatch")
    # Compare the selector command byte-for-byte to the ORIGINAL untouched
    # publisher source, not merely to a coincidentally matching regex.
    with zipfile.ZipFile(PACK) as z:
        raw=z.read("data/erb/function/restore/job_tick.mcfunction").decode("utf-8")
    lines=[line.strip() for line in raw.splitlines()
           if line.strip() and not line.lstrip().startswith("#")]
    if len(lines)<5 or lines[4]!=EXACT_ORIGINAL_LINE or lines.count(EXACT_ORIGINAL_LINE)!=1:
        raise AssertionError("Expected original restore/job_tick command at source index 4")
    results={"milestone":"COMPILER-IR-022","stage":"original_blastback_selector_022_candidate_cost",
             "status":"started","source_sha256":PIN,"arms":{},
             "speedup_claim":False,"new_compiled_opcode":False,
             "type_and_predicate_delegated_once":True,
             "full_restoration_claim":False}
    try:
        for mode in MODES:
            results["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")
        results["analysis"]=analysis(results["arms"])
        results["status"]="accepted_descriptive"
        print("IR022_CPU_SUMMARY "+json.dumps(results["analysis"],sort_keys=True),flush=True)
    except BaseException as failure:
        results["status"]="invalid"
        results["error"]=repr(failure)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")


if __name__=="__main__":
    main()
