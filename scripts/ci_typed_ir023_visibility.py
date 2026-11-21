#!/usr/bin/env python3
"""IR-023 stage 4: native same-queue marker tag-selector visibility and bypass.

Two independent Minecraft 26.3/Java25 servers run the EXACT same test-only
commands, always delegating native EntitySelector and native function queue.
The second arm additionally enables a passive addTag/removeTag-only observer
during the RAW backing-Set mutation case. No index, cache or alternate selector.

The gated fixture command deliberately calls native Entity.entityTags().add/
remove directly. This is a discovered uncovered invalidation path, NOT a
proposed optimization or replacement for ordinary vanilla /tag.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir013 import stop
from ci_typed_ir017 import nullable_score
from ci_typed_ir023_native import METRICS, parse_cpu023

OUT=ROOT/"build/reports/COMPILER-IR-023-VISIBILITY"
PACK="fc_ir023_visibility"
MODES=("native","observer")
SELECT="@e[type=minecraft:marker,tag=fc023.fixture,tag=erb.block,tag=!erb.verified]"
ALL="@e[type=minecraft:marker,tag=fc023.fixture]"
COMMANDS={
    "readiness": [
        'summon minecraft:marker 0 64 0 {Tags:["fc023.ready"]}',
        "execute if entity @e[type=minecraft:marker,tag=fc023.ready] "
        "run scoreboard players set #ready fc023 1",
        "kill @e[type=minecraft:marker,tag=fc023.ready]",
    ],
    "cycle": [
        "scoreboard players add #root fc023 1",
        'summon minecraft:marker 0 64 0 {Tags:["fc023.fixture"]}',
        f"execute as {SELECT} run scoreboard players add #c0 fc023 1",
        f"tag {ALL} add erb.block",
        "scoreboard players add #root fc023 1",
        f"execute as {SELECT} run scoreboard players add #c1 fc023 1",
        f"tag {ALL} add erb.block",
        f"execute as {SELECT} run scoreboard players add #c2 fc023 1",
        f"tag {ALL} add erb.verified",
        f"execute as {SELECT} run scoreboard players add #c3 fc023 1",
        f"tag {ALL} remove erb.verified",
        f"execute as {SELECT} run scoreboard players add #c4 fc023 1",
        f"tag {ALL} remove erb.block",
        f"execute as {SELECT} run scoreboard players add #c5 fc023 1",
    ],
    "nested_child": [
        f"execute as {SELECT} run scoreboard players add #child0 fc023 1",
        f"tag {ALL} add erb.verified",
        f"execute as {SELECT} run scoreboard players add #child1 fc023 1",
    ],
    "nested_parent": [
        'summon minecraft:marker 0 64 0 {Tags:["fc023.fixture"]}',
        f"tag {ALL} add erb.block",
        f"execute as {SELECT} run scoreboard players add #parent0 fc023 1",
        "function fc_ir023:nested_child",
        f"execute as {SELECT} run scoreboard players add #parent1 fc023 1",
    ],
    "raw_cycle": [
        'summon minecraft:marker 0 64 0 {Tags:["fc023.fixture"]}',
        f"execute as {SELECT} run scoreboard players add #r0 fc023 1",
        f"execute as {ALL} run fc_ir023_raw_tag add_block",
        f"execute as {SELECT} run scoreboard players add #r1 fc023 1",
        f"execute as {ALL} run fc_ir023_raw_tag add_verified",
        f"execute as {SELECT} run scoreboard players add #r2 fc023 1",
        f"execute as {ALL} run fc_ir023_raw_tag remove_verified",
        f"execute as {SELECT} run scoreboard players add #r3 fc023 1",
        f"execute as {ALL} run fc_ir023_raw_tag remove_block",
        f"execute as {SELECT} run scoreboard players add #r4 fc023 1",
    ],
    "summon_kill": [
        f"execute as {SELECT} run scoreboard players add #s0 fc023 1",
        'summon minecraft:marker 0 64 0 {Tags:["fc023.fixture","erb.block"]}',
        f"execute as {SELECT} run scoreboard players add #s1 fc023 1",
        f"tag {ALL} add erb.verified",
        f"execute as {SELECT} run scoreboard players add #s2 fc023 1",
        f"kill {ALL}",
        f"execute as {SELECT} run scoreboard players add #s3 fc023 1",
    ],
    "near_limit": [
        f"execute positioned 0 64 0 as {SELECT}[INVALID] run scoreboard players set #unused fc023 999",
    ],
}
# SOURCE-FIXTURE freeze: construct the sorted variant once, in source order;
# no modifying the production selector, no additional predicate evaluations.
ORDERED_SELECT="@e[type=minecraft:marker,tag=fc023.fixture,tag=erb.block,tag=!erb.verified,sort=nearest,limit=1]"
COMMANDS["near_limit"]=[
    'summon minecraft:marker 0 64 0 {Tags:["fc023.fixture","erb.block"]}',
    'summon minecraft:marker 4 64 0 {Tags:["fc023.fixture","erb.block"]}',
    'execute positioned 0 64 0 run scoreboard players set '
    '@e[type=minecraft:marker,tag=fc023.fixture,sort=nearest,limit=1] fc023 11',
    'execute positioned 4 64 0 run scoreboard players set '
    '@e[type=minecraft:marker,tag=fc023.fixture,sort=nearest,limit=1] fc023 22',
    f"execute positioned 0 64 0 as {ORDERED_SELECT} run scoreboard players operation #pick0 fc023 = @s fc023",
    f"execute positioned 0 64 0 as {ORDERED_SELECT} run tag @s add erb.verified",
    f"execute positioned 0 64 0 as {ORDERED_SELECT} run scoreboard players operation #pick1 fc023 = @s fc023",
]
SCORES=tuple("#"+tag+str(i)
    for tag,upper in (("c",6),("r",5),("s",4))
    for i in range(upper)
)+("#child0","#child1","#parent0","#parent1","#pick0","#pick1","#root")
EXPECTED={
    "cycle":{**{f"#c{i}":v for i,v in enumerate((0,1,1,0,1,0))},"#root":2},
    "raw_cycle":{f"#r{i}":v for i,v in enumerate((0,1,0,1,0))},
    "summon_kill":{f"#s{i}":v for i,v in enumerate((0,1,0,0))},
    "near_limit":{"#pick0":11,"#pick1":22},
}


def fixture(work:Path)->None:
    root=work/"world/datapacks"/PACK
    folder=root/"data/fc_ir023/function"
    folder.mkdir(parents=True,exist_ok=True)
    (root/"pack.mcmeta").write_text(json.dumps({
        "pack":{"description":"IR023 native tag selector mutation visibility fixture",
                "min_format":[97,1],"max_format":[97,1]}})+"\n",encoding="utf-8")
    for name,commands in COMMANDS.items():
        (folder/f"{name}.mcfunction").write_text("\n".join(commands)+"\n",encoding="utf-8")


def start(mode:str):
    if mode not in MODES:raise ValueError("Unknown mode")
    RUNS.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    work=RUNS/("ci-ir023-visibility-"+mode)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    fixture(work)
    (work/"eula.txt").write_text("eula=true\n")
    port,rcon=unused_port(),unused_port()
    passwd=secrets.token_hex(14)
    (work/"server.properties").write_text("\n".join([
        "online-mode=false","enable-rcon=true","broadcast-rcon-to-ops=false",
        "level-name=world","level-type=minecraft:flat","pause-when-empty-seconds=-1",
        "view-distance=2","simulation-distance=2","max-tick-time=-1",
        "max-players=1",f"server-port={port}",f"rcon.port={rcon}",
        f"rcon.password={passwd}"])+"\n")
    env=dict(os.environ)
    env.update({
        "FC_IR023_VISIBILITY_HARNESS":"true",
        "FC_CPU023_MODE":"plain" if mode=="observer" else "",
        "FC_CPU023_NAMESPACE":"erb" if mode=="observer" else "",
        "FC_TYPED_IR_MODE":"","FC_TYPED_IR_NAMESPACE":"",
        "FC_SCORE_ADD_PROTOTYPE":"false","FC_FUSED_REGION_PROTOTYPE":"false",
        "FC_BYTECODE_REGION_PROTOTYPE":"false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE":"false",
        "FC_TYPED_IR_DIRECT_FUNCTION":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS":"false","FC_WRAPPER_PROBE":"false",
    })
    cmd=[str(ROOT/"gradlew"),"--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}","runServer"]
    log=(OUT/(mode+".server.log")).open("w",encoding="utf-8")
    proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,
                          stderr=subprocess.STDOUT,stdin=subprocess.PIPE)
    try:
        client=wait_for_rcon(proc,rcon,passwd,timeout_seconds=240)
        if PACK not in client.command("datapack list enabled"):
            raise AssertionError("IR023 visibility fixture not loaded: "+mode)
        client.command("gamerule sendCommandFeedback false")
        client.command("gamerule doMobSpawning false")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("scoreboard objectives add fc023 dummy")
        client.command("forceload add 0 0")
        client.command("setblock 0 63 0 minecraft:stone")
        # Forceload marks a ticket; its entity-section lookup may not yet be
        # ready on a newly booted empty server. Require original same-queue
        # summon -> world-entity lookup -> kill before each experimental arm.
        # This readiness work is OUTSIDE all measured native tag windows.
        attempts=[]
        for attempt in range(24):
            client.command("scoreboard players set #ready fc023 0")
            result=client.command("function fc_ir023:readiness")
            seen=nullable_score(client,"#ready","fc023")
            attempts.append(seen)
            if seen==1:
                print("IR023_READY "+json.dumps({
                    "mode":mode,"attempts":attempt+1,"last_result":result[:120],
                    "marked_forceload":True}),flush=True)
                break
            time.sleep(0.15)
        else:
            raise AssertionError(
                f"Native marker lookup not ready after bounded warmup {mode}: {attempts!r}")
        return proc,client,log
    except BaseException:
        proc.terminate();proc.wait(timeout=40);log.close();raise


def reset(client,case:str)->None:
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    client.command(f"kill {ALL}")
    for holder in SCORES:
        client.command(f"scoreboard players set {holder} fc023 0")
    # All marker creation occurs in the SAME native function queue that
    # checks the selector. No fixture depends on persistence across RCON.


def snapshot(client)->dict[str,int|None]:
    return {holder:nullable_score(client,holder,"fc023") for holder in SCORES}


def assert_case(case:str,snapshot:dict)->None:
    for holder,expected in EXPECTED.get(case,{}).items():
        if snapshot[holder]!=expected:
            raise AssertionError(f"Native {case} {holder}={snapshot[holder]}, expected {expected}")
    if case=="nested_parent" and snapshot["#parent0"]!=1:
        raise AssertionError("Nested parent failed its original pre-child selection")
    if case=="nested_parent" and snapshot["#child0"]!=1:
        raise AssertionError("Native child was not invoked through same function queue")


def run_arm(mode:str)->dict:
    proc,client,log=start(mode)
    result={"mode":mode,"status":"started","snapshots":{},
            "native_selector_unchanged":True,
            "compiler_disabled":True,
            "test_only_mutation_command":True,
            "index_implemented":False,
            "world_restoration_claim":False,
            "causal_cpu_claim":False}
    try:
        for case in ("cycle","nested_parent","summon_kill","near_limit","raw_cycle"):
            reset(client,case)
            if case=="raw_cycle" and mode=="observer":
                response=client.command("functioncompiler cpu023-start")
                if "FC_CPU023 started mode=plain" not in response:
                    raise AssertionError("IR023 observer not started: "+repr(response))
            response=client.command(f"function fc_ir023:{case}")
            print("IR023_VISIBILITY_CALL "+json.dumps({
                "mode":mode,"case":case,"response":response[:240]}),flush=True)
            if "unknown function" in response.lower() or "not found" in response.lower():
                raise AssertionError(f"Fixture function unavailable: {case} {response!r}")
            observed=snapshot(client)
            if case=="cycle" and observed.get("#c1")!=1:
                debug={}
                for label,selector in (
                    ("any_marker","@e[type=minecraft:marker]"),
                    ("fixture",ALL),
                    ("eligible",SELECT),
                ):
                    client.command("scoreboard players set #selector_diag fc023 0")
                    answer=client.command(f"execute if entity {selector} run "
                                          "scoreboard players set #selector_diag fc023 1")
                    debug[label]={"response":answer[:220],
                                  "found":nullable_score(client,"#selector_diag","fc023")}
                debug["forceload"]=client.command("forceload query 0 0")[:220]
                debug["cycle_root"]=observed.get("#root")
                print("IR023_VISIBILITY_DIAGNOSTIC "+json.dumps(debug,sort_keys=True),flush=True)
            assert_case(case,observed)
            result["snapshots"][case]=observed
            if case=="raw_cycle" and mode=="observer":
                response=client.command("functioncompiler cpu023-stop")
                if "FC_CPU023 ended mode=plain" not in response:
                    raise AssertionError("IR023 observer not stopped: "+repr(response))
        result["status"]="accepted_arm"
        print("IR023_VISIBILITY_ARM "+json.dumps({
            "mode":mode,
            "cycle":{k:v for k,v in result["snapshots"]["cycle"].items() if k.startswith("#c")},
            "raw_cycle":{k:v for k,v in result["snapshots"]["raw_cycle"].items() if k.startswith("#r")},
            "nested":{k:v for k,v in result["snapshots"]["nested_parent"].items()
                      if k.startswith(("#child","#parent"))},
            "summon_kill":{k:v for k,v in result["snapshots"]["summon_kill"].items()
                           if k.startswith("#s")},
            "near_limit":{k:v for k,v in result["snapshots"]["near_limit"].items()
                          if k.startswith("#pick")},
            "direct_set_invalidation_gap_reproduced":
                result.get("direct_set_invalidation_gap_reproduced")
        },sort_keys=True),flush=True)
        return result
    except BaseException as exc:
        result["status"]="invalid"
        result["error"]=repr(exc)
        raise
    finally:
        stop(proc,client,log)
        (OUT/(mode+".json")).write_text(json.dumps(result,indent=2)+"\n")


def main()->None:
    OUT.mkdir(parents=True,exist_ok=True)
    report={"milestone":"COMPILER-IR-023","stage":"native_same_queue_visibility",
            "status":"started","arms":{},"index_implemented":False,
            "production_promotion":False,"causal_cpu_claim":False,
            "vanilla_selector_behavior_not_replaced":True,
            "native_but_test_only_direct_set_command":True}
    try:
        for mode in MODES:
            report["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        reference=report["arms"]["native"]["snapshots"]
        observed=report["arms"]["observer"]["snapshots"]
        # Read the counter dump only AFTER run_arm's finally block stopped
        # Minecraft/Gradle and closed its stdout file. Reading before native
        # process termination can see incomplete buffered SLF4J output.
        raw=(OUT/"observer.server.log").read_text(errors="replace")
        counter=parse_cpu023(raw,"plain")
        watched=(name for name in METRICS
                 if name.startswith(("add_","remove_","eligible_")))
        if any(counter[name]!=0 for name in watched):
            raise AssertionError(
                "Direct entityTags() Set writes unexpectedly fired addTag/removeTag hooks")
        if (observed["raw_cycle"]["#r1"]!=1 or
                observed["raw_cycle"]["#r2"]!=0 or
                observed["raw_cycle"]["#r3"]!=1 or
                observed["raw_cycle"]["#r4"]!=0):
            raise AssertionError("Original selector failed direct-set immediate visibility")
        report["arms"]["observer"]["direct_set_observer_rows"]=counter
        report["arms"]["observer"]["direct_set_invalidation_gap_reproduced"]=True
        (OUT/"observer.json").write_text(
            json.dumps(report["arms"]["observer"],indent=2)+"\n")
        if reference!=observed:
            mismatch={k:{"native":reference[k],"observer":observed[k]}
                      for k in reference if reference[k]!=observed[k]}
            raise AssertionError("IR023 passive observer changed native selector visibility: "+
                                 json.dumps(mismatch)[:4000])
        report["status"]="accepted_native_same_queue_visibility_and_direct_set_bypass"
        report["native_semantic_parity"]=True
        report["cases_per_arm"]=len(reference)
        report["direct_set_invalidation_gap_reproduced"]=True
        print("IR023_VISIBILITY_SUMMARY "+json.dumps({
            "status":report["status"],"cases_per_arm":len(reference),
            "nested":{k:v for k,v in reference["nested_parent"].items()
                      if k.startswith(("#child","#parent"))},
            "direct_set_invalidation_gap_reproduced":True,
            "tag_index_not_admitted":True,
            "native_semantic_parity":True
        },sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":
    main()
