#!/usr/bin/env python3
"""IR-026 first original-publisher Blastback native/plan-only/compiled fork gate.

Three separate new Minecraft 26.3/Java25 JVMs use the SAME SHA256-pinned,
untouched Blastback-Hotfix-3-26.3.zip, world seed, source template, TNT source
and observation window. The plan-only and compiled arms are configured
identically apart from FC_TYPED_IR_COMPILED_FORK. The compiler is explicitly
limited to erb:restore/job_tick to isolate the exact original selector.

Correctness-only. Original Blastback's full restoration oracle is known to
be unresolved. The status must NOT be a CPU/performance, full restoration,
all-entity identity, or complete parity claim; only bounded witness-state
and original selector execution are checked.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import zipfile

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir013 import stop, stat
from ci_typed_ir015_coverage import PINS
from ci_typed_ir017 import nullable_score
from ci_typed_ir019_blastback import WITNESSES
from ci_typed_ir022_cpu import EXACT_ORIGINAL_LINE
from run_blastback_profile import (
    write_setup_pack, score, block_matches, region_matches_template
)

OUT=ROOT/"build/reports/COMPILER-IR-026-BLASTBACK"
PACK=Path(PINS["blastback"]["path"])
PIN=PINS["blastback"]["sha256"]
TARGET="erb:restore/job_tick"
MODES=("native","plan_only","compiled")
WINDOW_SECONDS=30
EXPECTED_SOURCE_INDEX=4  # zero-based actual publisher line
MIN_TICKS=100
MAX_TICK_EXPOSURE_RATIO=1.50
SCORES=(
    ("tick_id","#tick_id","erb.cfg"),
    ("active_job","#active","erb.job"),
    ("needs_restore","#needs_restore","erb.tmp"),
)
MARKERS={
    "block":"@e[type=minecraft:marker,tag=erb.block]",
    "verified":"@e[type=minecraft:marker,tag=erb.verified]",
    "eligible":"@e[type=minecraft:marker,tag=erb.block,tag=!erb.verified]",
}
DISABLED_FLAGS={
    "FC_SCORE_ADD_PROTOTYPE":"false",
    "FC_FUSED_REGION_PROTOTYPE":"false",
    "FC_BYTECODE_REGION_PROTOTYPE":"false",
    "FC_DIRECT_SCHEDULER_PROTOTYPE":"false",
    "FC_TYPED_IR_DIRECT_FUNCTION":"false",
    "FC_TYPED_IR_SCORE_CACHE":"false",
    "FC_TYPED_IR_SINGLETON_FEEDBACK":"false",
    "FC_SELECTIVE_MACRO_ARGUMENTS":"false",
    "FC_COMPILER_EXEC_CENSUS":"false",
    "FC_IR023_VISIBILITY_HARNESS":"false",
    "FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"false",
    "FC_CPU022_MODE":"",
    "FC_CPU023_MODE":"",
}

def original_publisher() -> dict:
    if not PACK.is_file():
        raise AssertionError("Exact original publisher archive has not been fetched")
    data=PACK.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual!=PIN:
        raise AssertionError(f"Original Blastback publisher SHA-256 mismatch: {actual}")
    with zipfile.ZipFile(PACK) as archive:
        original=archive.read("data/erb/function/restore/job_tick.mcfunction").decode("utf-8")
        names=archive.namelist()
    commands=[line.strip() for line in original.splitlines()
              if line.strip() and not line.lstrip().startswith("#")]
    if len(commands)<=EXPECTED_SOURCE_INDEX:
        raise AssertionError("Publisher restore function too short")
    if commands[EXPECTED_SOURCE_INDEX]!=EXACT_ORIGINAL_LINE:
        raise AssertionError("Original exact target selector changed or shifted")
    if commands.count(EXACT_ORIGINAL_LINE)!=1:
        raise AssertionError("Publisher has ambiguous identical target selector lines")
    return {
        "sha256":actual,"archive_bytes":len(data),"archive_members":len(names),
        "original_restore_function":TARGET,
        "target_source_index_zero_based":EXPECTED_SOURCE_INDEX,
        "original_target_source":EXACT_ORIGINAL_LINE,
        "original_restore_command_count":len(commands),
        "datapack_mutated":False,
    }

def options(mode:str)->dict[str,str]:
    if mode not in MODES:raise ValueError("Unknown IR026 mode")
    enabled=mode!="native"
    return {
        **DISABLED_FLAGS,
        "FC_WRAPPER_PROBE":str(enabled).lower(),
        "FC_TYPED_IR_MODE":"bytecode" if enabled else "",
        "FC_TYPED_IR_NAMESPACE":"erb" if enabled else "",
        "FC_TYPED_IR_FUNCTION_FILTER":TARGET if enabled else "",
        "FC_TYPED_IR_NATIVE_FORK_PLAN":str(enabled).lower(),
        "FC_TYPED_IR_COMPILED_FORK":str(mode=="compiled").lower(),
        "FC_TYPED_IR_REENTRANT_SAFE":"true",
        "FC_TYPED_IR_DIAGNOSTICS":str(enabled).lower(),
    }

def launch(mode:str):
    OUT.mkdir(parents=True,exist_ok=True)
    RUNS.mkdir(parents=True,exist_ok=True)
    work=RUNS/("ci-ir026-blastback-"+mode)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    packs=work/"world/datapacks"
    packs.mkdir(parents=True)
    dest=packs/"blastback.zip"
    shutil.copyfile(PACK,dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=PIN:
        raise AssertionError("Original publisher bytes changed during fixture deployment")
    write_setup_pack(packs/"function_compiler_benchmark",1)
    (work/"eula.txt").write_text("eula=true\n",encoding="utf-8")
    port,rcon_port=unused_port(),unused_port()
    password=secrets.token_hex(16)
    (work/"server.properties").write_text("\n".join([
        "online-mode=false","enable-rcon=true",
        "broadcast-rcon-to-ops=false","level-name=world",
        "level-seed=264010","pause-when-empty-seconds=-1",
        "view-distance=4","simulation-distance=4",
        "max-tick-time=-1","max-players=1",
        f"server-port={port}",f"rcon.port={rcon_port}",
        f"rcon.password={password}"])+"\n",encoding="utf-8")
    env=dict(os.environ)
    env.update(options(mode))
    command=[str(ROOT/"gradlew"),"--no-daemon",
             "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
             "-PfcJvmArgs=-Xms512M,-Xmx3G",
             f"-PfcRunDirectory={work.relative_to(ROOT)}","runServer"]
    log=(OUT/(mode+".server.log")).open("w",encoding="utf-8")
    proc=subprocess.Popen(command,cwd=ROOT,env=env,
                          stdout=log,stderr=subprocess.STDOUT,
                          stdin=subprocess.PIPE)
    try:
        client=wait_for_rcon(proc,rcon_port,password,timeout_seconds=300)
        listed=client.command("datapack list enabled")
        if "blastback" not in listed.lower():
            raise AssertionError(f"Original publisher unavailable in {mode}: {listed}")
        return proc,client,log
    except BaseException:
        proc.terminate()
        proc.wait(timeout=40)
        log.close()
        raise

def native_witnesses(client)->dict[str,bool]:
    return {name:block_matches(client,name,*point)
            for name,point in WITNESSES.items()}

def marker_counts(client)->dict[str,int]:
    result={}
    for name,selector in MARKERS.items():
        holder="#fc026_"+name
        client.command(f"scoreboard players set {holder} fc_probe 0")
        client.command(f"execute as {selector} run "
                       f"scoreboard players add {holder} fc_probe 1")
        result[name]=score(client,holder,"fc_probe")
    return result

def snapshot(client)->dict:
    return {
        "witnesses":native_witnesses(client),
        "template_equal":region_matches_template(client),
        "marker_counts":marker_counts(client),
        "scoreboard":{key:nullable_score(client,holder,objective)
                      for key,holder,objective in SCORES},
    }

def configure_original_scene(client)->dict:
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
    for block,point in WITNESSES.items():
        if block!="stone":
            client.command(f"setblock {point[0]} {point[1]} "
                           f"{point[2]} minecraft:{block}")
    attempts=[]
    for _ in range(3):
        response=client.command(
            "clone -4 56 -4 12 72 12 64 56 32 replace force")
        before=native_witnesses(client)
        template=region_matches_template(client)
        attempts.append({"response":response,"witnesses":before,
                         "template_equal":template})
        if all(before.values()) and template:
            break
        time.sleep(.2)
    else:
        raise AssertionError("Pre-TNT original source/template fixture invalid: "
                             + repr(attempts))
    return {"clone_attempts":attempts,"before_witnesses":before,
            "before_template_equal":template}

def ledger_gate(client,mode)->str | None:
    if mode=="native": return None
    reply=client.command(f"functioncompiler ir016 {TARGET}")
    if not reply.startswith("IR016 function="+TARGET):
        raise AssertionError("IR026 original restore function compiler ledger missing: "
                             +repr(reply))
    def field(key):
        match=re.search(r"\b"+key+r"=(\d+)",reply)
        if not match:raise AssertionError("Missing IR026 ledger field "+key)
        return int(match.group(1))
    if field("native_fork_plans")!=1:
        raise AssertionError("Exact original Blastback fork wasn't admitted: "+reply)
    if field("compiled_forks")!=(1 if mode=="compiled" else 0):
        raise AssertionError("Original fork compiled/retained unexpectedly: "+reply)
    if ("C5:1" if mode=="compiled" else "N5:1") not in reply:
        raise AssertionError("Original fork lost original source slot: "+reply)
    if "direct_candidate=true" in reply:
        raise AssertionError("Real original Blastback function entered direct scheduler")
    return reply

def verify_started_actor(client)->tuple[str,list[int]]:
    spawn=client.command(
        'summon minecraft:tnt 4 64 4 {Fuse:160s,Tags:["fc_blastback_probe"]}')
    if "Summoned new" not in spawn:
        raise AssertionError("Original native one-TNT summon failed: "+spawn)
    observed=[]
    for _ in range(12):
        client.command("scoreboard players set #ir026_tnt fc_probe 0")
        client.command(
            "execute as @e[type=minecraft:tnt,tag=fc_blastback_probe] "
            "run scoreboard players add #ir026_tnt fc_probe 1")
        found=score(client,"#ir026_tnt","fc_probe")
        observed.append(found)
        if found==1:return spawn,observed
        time.sleep(.1)
    raise AssertionError("Original one-TNT actor never became visible: "+repr(observed))

def run_arm(mode:str)->dict:
    proc,client,log=launch(mode)
    report={
        "mode":mode,"status":"started","original_publisher_sha256":PIN,
        "original_datapack_unchanged":True,"compiler_only_target":TARGET,
        "window_seconds":WINDOW_SECONDS,
        "causal_speedup_claim":False,"full_restoration_claim":False,
        "whole_world_semantic_equivalence_claim":False,
        "original_terminal_and_selector_reused":True,
        "global_entity_index":False,
    }
    try:
        report["pre_event_fixture"]=configure_original_scene(client)
        report["original_source_compiler_ledger"]=ledger_gate(client,mode)
        report["before"]=snapshot(client)
        if not all(report["before"]["witnesses"].values()):
            raise AssertionError("Original witnesses lost before TNT event")
        tick_before=report["before"]["scoreboard"]["tick_id"]
        if tick_before is None:
            raise AssertionError("No publisher #tick_id erb.cfg")
        spawn,observed=verify_started_actor(client)
        report["native_tnt_spawn"]=spawn
        report["pre_event_actor_observations"]=observed
        print("IR026_EVENT_START "+json.dumps({
            "mode":mode,"tick_before":tick_before,
            "ledger":report["original_source_compiler_ledger"],
            "actor_seen":1},sort_keys=True),flush=True)
        time.sleep(WINDOW_SECONDS)
        report["after"]=snapshot(client)
        tick_after=report["after"]["scoreboard"]["tick_id"]
        if tick_after is None:
            raise AssertionError("Publisher #tick_id disappeared")
        ticks=tick_after-tick_before
        report["tick_delta"]=ticks
        if ticks<MIN_TICKS:
            raise AssertionError(f"No bounded original Blastback tick workload: {ticks}")
        # Original TNT must actually have exploded; otherwise this isn't
        # an event/restore behavior check at all.
        client.command("scoreboard players set #ir026_tnt fc_probe 0")
        client.command(
            "execute as @e[type=minecraft:tnt,tag=fc_blastback_probe] "
            "run scoreboard players add #ir026_tnt fc_probe 1")
        remaining=score(client,"#ir026_tnt","fc_probe")
        report["event_tnt_remaining"]=remaining
        if remaining!=0:raise AssertionError("Original one-TNT never detonated")
        if mode!="native":
            diag=client.command("functioncompiler ir025")
            report["fork_diagnostics"]=diag
            if not diag.startswith("IR025 enabled="):
                raise AssertionError("No real IR025 native-JVM diagnostics: "+diag)
            if mode=="compiled":
                if "IR025 enabled=true" not in diag:
                    raise AssertionError("Compiled fork disabled at runtime: "+diag)
                for key in ("compiled_forks","executed_forks",
                            "selector_scans","selected_sources"):
                    if stat(diag,key)<=0:
                        raise AssertionError("Original Blastback not executed through compiled "
                                             +key+": "+diag)
                if stat(diag,"executed_forks")!=stat(diag,"selector_scans"):
                    raise AssertionError("Compiled scans vs fork runs diverged")
            elif ("IR025 enabled=false" not in diag
                  or stat(diag,"executed_forks")!=0):
                raise AssertionError("Plan-only original command wrongly executed compiled fork")
            report["original_restore_compiler_ledger_after"]=ledger_gate(client,mode)
        report["status"]="accepted_bounded_original_event_arm"
        print("IR026_ORIGINAL_ARM "+json.dumps({
            "mode":mode,"tick_delta":ticks,
            "witnesses_after":report["after"]["witnesses"],
            "template_after":report["after"]["template_equal"],
            "marker_counts":report["after"]["marker_counts"],
            "fork":report.get("fork_diagnostics"),
            "original_tnt_detonated":True
        },sort_keys=True),flush=True)
        return report
    except BaseException as error:
        report["status"]="invalid_original_event"
        report["error"]=repr(error)
        raise
    finally:
        stop(proc,client,log)
        (OUT/(mode+".json")).write_text(json.dumps(report,indent=2)+"\n")

def compare(original:dict,mode:dict)->dict:
    a=original["after"]
    b=mode["after"]
    comparison={
        "witnesses_equal":a["witnesses"]==b["witnesses"],
        "template_equal_flag_matches":a["template_equal"]==b["template_equal"],
        "native_marker_counts":a["marker_counts"],
        "comparison_marker_counts":b["marker_counts"],
        "native_dynamic_scores":a["scoreboard"],
        "comparison_dynamic_scores":b["scoreboard"],
        "tick_ratio":max(original["tick_delta"],mode["tick_delta"])/
            min(original["tick_delta"],mode["tick_delta"]),
        "exact_dynamic_score_equivalence_claim":False,
        "identical_event_timing_claim":False,
        "full_restore_oracle_claim":False,
    }
    comparison["bounded_witness_parity"]= (
        comparison["witnesses_equal"] and comparison["template_equal_flag_matches"])
    return comparison

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    publisher=original_publisher()
    report={
        "milestone":"COMPILER-IR-026","status":"started",
        "stage":"original_publisher_compiled_fork_semantic_gate",
        "publisher":publisher,"arms":{},"comparisons":{},
        "native_semantic_scope":"bounded original block witnesses and template flag",
        "dynamic_scores_recorded_not_asserted_equal":True,
        "performance_claim":False,
        "full_restoration_claim":False,
        "production_promotion":False,
    }
    try:
        for mode in MODES:
            report["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        baseline=report["arms"]["native"]
        for mode in MODES[1:]:
            result=compare(baseline,report["arms"][mode])
            report["comparisons"][mode]=result
            if not result["bounded_witness_parity"]:
                raise AssertionError(
                    "Original publisher observable witness state diverged: "
                    +mode+" "+json.dumps(result))
            if result["tick_ratio"]>MAX_TICK_EXPOSURE_RATIO:
                raise AssertionError("Original publisher event tick exposure not comparable: "
                                     +mode+" "+repr(result["tick_ratio"]))
        # An A/B *behavior* gate, not an A/B speedup gate.
        report["status"]="accepted_bounded_original_publisher_semantic_gate"
        report["compiled_fork_real_original_execution"]=True
        report["bounded_witness_parity"]=True
        print("IR026_ORIGINAL_SUMMARY "+json.dumps({
            "status":report["status"],
            "original_publisher_sha256":PIN,
            "modes":MODES,
            "tick_deltas":{m:report["arms"][m]["tick_delta"] for m in MODES},
            "witness_parity":{m:report["comparisons"][m]["bounded_witness_parity"]
                              for m in MODES[1:]},
            "real_compiled_fork_execution":True,
            "complete_restoration_claim":False,"speedup_claim":False,
        },sort_keys=True),flush=True)
    except BaseException as error:
        report["status"]="invalid_original_publisher_semantic_gate"
        report["error"]=repr(error)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__": main()
