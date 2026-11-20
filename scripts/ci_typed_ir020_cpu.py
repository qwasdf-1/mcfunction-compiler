#!/usr/bin/env python3
"""IR-020: calibrated original Blastback selector-fork CPU cost screen.

Three INDEPENDENT native Java25/Minecraft26.3 JVMs, original pinned publisher,
same original one-TNT capture/restore fixture, fixed 30s capture window, exact
native method boundaries, explicitly opted in at process startup.
PLAIN = count calls, NO CPU clock; EMPTY = 2 adjacent clock reads at sampled
ordinals; TIMED = the original method wrapped with the same clock.
The three spans overlap: build and execute are separate queue phases, leaf is
nested INSIDE execute. No scheduler/scoreboard/compiler changes or speedup claim.
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

OUT=ROOT/"build/reports/COMPILER-IR-020-CPU"
MODES=("plain","empty","timed")
WINDOW_SECONDS=30
STREAMS={
    "restore_selector_build":16,
    "restore_terminal_execute":128,
    "restore_scoreboard_leaf":128,
}
MIN_SAMPLES={
    "restore_selector_build":24,
    "restore_terminal_execute":128,
    "restore_scoreboard_leaf":128,
}
EXACT_ORIGINAL_LINE=(
    "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] "
    "if score @s erb.job = #active erb.job "
    "run scoreboard players set #needs_restore erb.tmp 1"
)
PIN=PINS["blastback"]["sha256"]


def parse_cpu020(text: str, mode: str)->dict:
    rows={}
    started=False
    ended=False
    for line in text.splitlines():
        if "FC_CPU020_BEGIN mode=" in line:
            if started:raise ValueError("Multiple IR020 BEGIN markers")
            started="FC_CPU020_BEGIN mode="+mode in line
        if "FC_CPU020_END mode=" in line:
            if ended:raise ValueError("Multiple IR020 END markers")
            ended="FC_CPU020_END mode="+mode in line
        if "FC_CPU020_ROW " in line:
            body=line.split("FC_CPU020_ROW ",1)[1]
            data=dict(re.findall(r"(\w+)=(\S+)",body))
            kind=data.get("kind")
            if kind not in STREAMS or kind in rows:
                raise AssertionError(f"Unexpected/duplicate IR020 native stream {kind}")
            rows[kind]={k:int(data[k]) for k in ("stride","visits","samples",
                                                 "cpu_ns","invalid")}
    if not started or not ended or set(rows)!=set(STREAMS):
        raise AssertionError("Incomplete IR020 native start/stop CPU stream dump")
    for label,row in rows.items():
        if row["stride"]!=STREAMS[label]:
            raise AssertionError(f"Changed native sampling stride: {label} {row}")
        if row["invalid"]!=0 or row["visits"]<=0 or row["cpu_ns"]<0:
            raise AssertionError(f"Bad native CPU stream {label}: {row}")
        expected=row["visits"]//row["stride"] if mode!="plain" else 0
        if row["samples"]!=expected:
            raise AssertionError(f"Original native CPU samples missing: {mode} {label} "
                                 f"{row['samples']} vs {expected}")
        if mode=="plain" and row["cpu_ns"]!=0:
            raise AssertionError("PLAIN CPU sampled without consent")
        if mode!="plain" and row["samples"]<MIN_SAMPLES[label]:
            raise AssertionError(f"Underpowered native CPU stream {mode}/{label}: {row}")
    return rows


def analysis(arms:dict)->dict:
    if set(arms)!=set(MODES):
        raise AssertionError("Expected three original JVM arms")
    corrected={}
    for label in STREAMS:
        plain=arms["plain"]["cpu_rows"][label]
        empty=arms["empty"]["cpu_rows"][label]
        timed=arms["timed"]["cpu_rows"][label]
        # Same 30-second window, NOT an equal-work causal experiment. Require
        # comparable orders of exposure, never silently normalize mismatched
        # workloads into a treatment speedup.
        counts=[row["visits"] for row in (plain,empty,timed)]
        if min(counts)<=0 or max(counts)/min(counts)>1.50:
            raise AssertionError(f"Noncomparable {label} exposures: {counts}")
        # Native selector source is entered once; the original callback must
        # fan out to many per-entity context branches. Do not claim callbacks
        # are successful matching-score writes.
        if label=="restore_scoreboard_leaf" and min(counts)<1000:
            raise AssertionError("Original high-fanout restore workload not reached")
        avg_e=empty["cpu_ns"]/empty["samples"]
        avg_t=timed["cpu_ns"]/timed["samples"]
        signed=avg_t-avg_e
        corrected[label]={
            "visits":{"plain":counts[0],"empty":counts[1],"timed":counts[2]},
            "empty_clock_mean_ns":avg_e,
            "timed_method_inclusive_mean_ns":avg_t,
            "signed_subtracted_ns_per_call":signed,
            "signed_descriptive_projected_cpu_ns":signed*timed["visits"],
            "signed_fraction_of_timed_server_cpu":
                signed*timed["visits"]/
                arms["timed"]["server_thread_cpu"]["server_thread_cpu_running_ns"],
            "sampling_stride":STREAMS[label],
            "exclusive_or_removable_cpu_claim":False,
        }
    return {
        "status":"descriptive_native_cpu_screen_accepted",
        "native_method_clocks":"ThreadMXBean current-thread CPU ns",
        "whole_window_cpu_clock":"Linux /proc Server-thread schedstat ns",
        "all_arms_original_unmodified_publisher":True,
        "same_original_gameplay_or_restoration_completion":False,
        "causal_speedup_claim":False,
        "no_disjoint_summation":True,
        "nested_relation":"restore_scoreboard_leaf is inside restore_terminal_execute",
        "three_independent_jvms":True,
        "rows":corrected,
    }


def run_arm(mode: str)->dict:
    output=OUT/mode
    output.mkdir(parents=True,exist_ok=True)
    proc,client,log=setup(cpu_mode=mode,output=output)
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
        minecraft_pid,server_tid=find_server_thread(proc.pid)
        tick_before=score(client,"#tick_id","erb.cfg")
        status=client.command("functioncompiler cpu020-start")
        if f"FC_CPU020 started mode={mode}" not in status:
            raise AssertionError(f"Native original-clock mode unavailable: {status!r}")
        cpu_before=read_thread_schedstat(minecraft_pid,server_tid)
        throttle_before=cgroup_throttle_count()
        # Same native direct tagged actor from IR-019 accepted capture study.
        spawn=client.command(
            'summon minecraft:tnt 4 64 4 {Fuse:160s,Tags:["fc_blastback_probe"]}')
        if "Summoned new" not in spawn:
            raise AssertionError(f"Original native TNT summon declined: {spawn!r}")
        client.command("scoreboard players set #ir020_tnt fc_probe 0")
        client.command("execute as @e[type=minecraft:tnt,tag=fc_blastback_probe] "
                       "run scoreboard players add #ir020_tnt fc_probe 1")
        actor=score(client,"#ir020_tnt","fc_probe")
        if actor!=1:
            raise AssertionError("Expected one original in-world TNT actor")
        time.sleep(WINDOW_SECONDS)
        cpu_after=read_thread_schedstat(minecraft_pid,server_tid)
        throttle_after=cgroup_throttle_count()
        status=client.command("functioncompiler cpu020-stop")
        if f"FC_CPU020 ended mode={mode}" not in status:
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
        raw_rows="\n".join(line for line in raw.splitlines() if "FC_CPU020_" in line)
        (output/"clock-rows.log").write_text(raw_rows+"\n",encoding="utf-8")
        rows=parse_cpu020(raw_rows,mode)
        report["cpu_rows"]=rows
        # Each stream selected only the exact original source command, and
        # the recorded visits must prove real high-fanout original execution.
        if report["tick_delta"]<100 or rows["restore_selector_build"]["visits"]<50:
            raise AssertionError(f"No real restoring/selector workload in {mode}")
        if rows["restore_scoreboard_leaf"]["visits"]<1000:
            raise AssertionError(f"Original high-fanout leaf work not activated: {mode}")
        if rows["restore_scoreboard_leaf"]["visits"] < rows["restore_selector_build"]["visits"]:
            raise AssertionError("Original selector did not produce forked callback work")
        if not report["server_thread_cpu"]["cpu_measurement_valid"]:
            raise AssertionError("Invalid native server CPU clock")
        report["status"]="accepted_native_descriptive_arm"
        print("IR020_CPU_ARM "+json.dumps({
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
    results={"milestone":"COMPILER-IR-020","stage":"original_blastback_restore_cpu",
             "status":"started","source_sha256":PIN,"arms":{},
             "speedup_claim":False,"new_compiled_opcode":False,
             "full_restoration_claim":False}
    try:
        for mode in MODES:
            results["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")
        results["analysis"]=analysis(results["arms"])
        results["status"]="accepted_descriptive"
        print("IR020_CPU_SUMMARY "+json.dumps(results["analysis"],sort_keys=True),flush=True)
    except BaseException as failure:
        results["status"]="invalid"
        results["error"]=repr(failure)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")


if __name__=="__main__":
    main()
