#!/usr/bin/env python3
"""IR-024 compiler-boundary admission: typed scoreboard regions around an
exact ORIGINAL native selector fork-plan barrier. No index or selector rewrite.

Two fresh Minecraft 26.3/Java25 JVMs compare vanilla original execution vs
opt-in typed-IR + compile-time native selector plan classification.
Only the neighboring scoreboard code can execute generated JVM bytecode;
the recognized fork action itself ALWAYS executes its original native
BuildContexts.Unbound in its original source position.
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
from ci_typed_ir013 import stop, stat
from ci_typed_ir017 import nullable_score

OUT=ROOT/"build/reports/COMPILER-IR-024"
PACK="fc_typed_ir024"
MODES=("native","fork_plan")
QUOTAS=(1,2,3,4,5,6,8,12,16,20,30,64)
SELECT="@e[type=minecraft:marker,tag=fc024.fixture,tag=erb.block,tag=!erb.verified]"
ALL="@e[type=minecraft:marker,tag=fc024.fixture]"
HOT=lambda name: (
    f"execute as {SELECT} if score @s fc024 = #active fc024 "
    f"run scoreboard players set #{name} fc024 1"
)
FUNCTIONS={
    "ready": [
        'summon minecraft:marker 0 64 0 {Tags:["fc024.ready"]}',
        "execute if entity @e[type=minecraft:marker,tag=fc024.ready] "
        "run scoreboard players set #ready fc024 1",
        "kill @e[type=minecraft:marker,tag=fc024.ready]"
    ],
    "plan_case": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #hit fc024 0",
        "scoreboard players set #hit_after fc024 0",
        "scoreboard players set #hit_reenabled fc024 0",
        "scoreboard players set #steps fc024 0",
        'summon minecraft:marker 0 64 0 {Tags:["fc024.fixture","erb.block"]}',
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        HOT("hit"),
        "scoreboard players add #steps fc024 1",
        f"tag {ALL} add erb.verified",
        HOT("hit_after"),
        f"tag {ALL} remove erb.verified",
        HOT("hit_reenabled"),
        "scoreboard players add #steps fc024 2"
    ],
    # Changed selector shape (no negative watched tag) must not be admitted:
    "near_miss": [
        "scoreboard players set #miss fc024 0",
        "scoreboard players set #steps fc024 0",
        'summon minecraft:marker 0 64 0 {Tags:["fc024.fixture","erb.block"]}',
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        f"execute as {ALL} if score @s fc024 = #active fc024 "
        "run scoreboard players set #miss fc024 1",
        "scoreboard players add #steps fc024 1"
    ],
}
SCORES=("#active","#hit","#hit_after","#hit_reenabled","#steps","#miss")
EXPECTED={
    "plan_case":{"#active":7,"#hit":1,"#hit_after":0,
                 "#hit_reenabled":1,"#steps":3},
    "near_miss":{"#miss":1,"#steps":1}
}

def fixture(work:Path):
    root=work/"world/datapacks"/PACK
    functions=root/"data/fc_ir024/function"
    functions.mkdir(parents=True,exist_ok=True)
    (root/"pack.mcmeta").write_text(json.dumps({
        "pack":{"description":"IR024 native execution and post-Brigadier fork IR gate",
                "min_format":[97,1],"max_format":[97,1]}
    })+"\n",encoding="utf-8")
    for name,commands in FUNCTIONS.items():
        (functions/(name+".mcfunction")).write_text(
            "\n".join(commands)+"\n",encoding="utf-8")

def options(mode:str)->dict[str,str]:
    if mode not in MODES:raise ValueError("Unknown IR024 mode")
    compiled=mode=="fork_plan"
    return {
        "FC_WRAPPER_PROBE":str(compiled).lower(),
        "FC_TYPED_IR_MODE":"bytecode" if compiled else "",
        "FC_TYPED_IR_NAMESPACE":"fc_ir024" if compiled else "",
        "FC_TYPED_IR_DIAGNOSTICS":str(compiled).lower(),
        "FC_TYPED_IR_NATIVE_FORK_PLAN":str(compiled).lower(),
        "FC_TYPED_IR_DIRECT_FUNCTION":"false",
        "FC_TYPED_IR_SCORE_CACHE":"false",
        "FC_TYPED_IR_SINGLETON_FEEDBACK":"false",
        "FC_SCORE_ADD_PROTOTYPE":"false",
        "FC_FUSED_REGION_PROTOTYPE":"false",
        "FC_BYTECODE_REGION_PROTOTYPE":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS":"false",
        "FC_IR023_VISIBILITY_HARNESS":"false",
    }

def start(mode:str):
    RUNS.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    work=RUNS/("ci-ir024-"+mode)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    fixture(work)
    (work/"eula.txt").write_text("eula=true\n")
    port,rcon=unused_port(),unused_port()
    password=secrets.token_hex(15)
    (work/"server.properties").write_text("\n".join([
        "online-mode=false","enable-rcon=true","broadcast-rcon-to-ops=false",
        "level-name=world","level-type=minecraft:flat",
        "pause-when-empty-seconds=-1","view-distance=2",
        "simulation-distance=2","max-tick-time=-1","max-players=1",
        f"server-port={port}",f"rcon.port={rcon}",
        f"rcon.password={password}"])+"\n")
    env=dict(os.environ);env.update(options(mode))
    command=[str(ROOT/"gradlew"),"--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}","runServer"]
    log=(OUT/(mode+".server.log")).open("w",encoding="utf-8")
    process=subprocess.Popen(command,cwd=ROOT,env=env,
                             stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.PIPE)
    try:
        client=wait_for_rcon(process,rcon,password,timeout_seconds=240)
        if PACK not in client.command("datapack list enabled"):
            raise AssertionError("IR024 test pack absent")
        client.command("gamerule sendCommandFeedback false")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("scoreboard objectives add fc024 dummy")
        client.command("forceload add 0 0")
        client.command("setblock 0 63 0 minecraft:stone")
        for tries in range(24):
            client.command("scoreboard players set #ready fc024 0")
            client.command("function fc_ir024:ready")
            if nullable_score(client,"#ready","fc024")==1:
                print("IR024_READY "+json.dumps({"mode":mode,"attempts":tries+1}),flush=True)
                break
            time.sleep(.15)
        else:
            raise AssertionError(f"IR024 native entity query not ready in {mode}")
        return process,client,log
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        log.close()
        raise

def reset(client):
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    client.command(f"kill {ALL}")
    for key in SCORES:
        client.command(f"scoreboard players set {key} fc024 0")

def snapshot(client)->dict:
    return {key:nullable_score(client,key,"fc024") for key in SCORES}

def run_arm(mode:str):
    process,client,log=start(mode)
    report={"mode":mode,"status":"started","snapshots":{},
            "native_selector_execution":True,"index_implemented":False,
            "plan_admission_only":True,"native_fork_preserved":True,
            "causal_cpu_claim":False}
    try:
        for case in ("plan_case","near_miss"):
            for quota in (65536,*QUOTAS):
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                result=client.command(f"function fc_ir024:{case}")
                # Score queries can consume their own quota in separate RCON
                # execution contexts; reset to a nontruncating value first.
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                if "Running function" not in result:
                    raise AssertionError(f"Native function not found {case}: {result!r}")
                data=snapshot(client)
                report["snapshots"][f"{case}@{quota}"]=data
                if quota==65536:
                    for key,value in EXPECTED[case].items():
                        if data[key]!=value:
                            raise AssertionError(
                                f"{mode}/{case}/{key}: expected {value}, observed {data[key]}")
        if mode=="fork_plan":
            for case in ("plan_case","near_miss"):
                text=client.command(f"functioncompiler ir016 fc_ir024:{case}")
                if not text.startswith("IR016 function="):
                    raise AssertionError("No actual compiler IR ledger: "+repr(text))
                match=re.search(r"native_fork_plans=(\d+)",text)
                if match is None:
                    raise AssertionError("New native-fork node not represented in IR: "+text)
                planned=int(match.group(1))
                if planned!=(3 if case=="plan_case" else 0):
                    raise AssertionError(
                        f"Compiler admitted incorrect native selector shape {case}: {text}")
                if case=="plan_case" and ("N8:1" not in text or "N11:1" not in text):
                    raise AssertionError("Compiler plan lost source position: "+text)
                if "direct_candidate=true" in text:
                    raise AssertionError("Opaque native fork improperly admitted for direct scheduling")
                if "typed_regions=0" in text:
                    raise AssertionError("No adjacent actual typed-score JVM compilation")
                report.setdefault("compiled_ledgers",{})[case]=text
            info=client.command("functioncompiler ir008")
            if stat(info,"bytecode_regions")<=0 or stat(info,"executed_steps")<=0:
                raise AssertionError("Generated JVM scoreboard execution was not reached: "+info)
            report["compiler_diagnostic"]=info
        report["status"]="accepted_arm"
        print("IR024_ARM "+json.dumps({
            "mode":mode,"snapshots":len(report["snapshots"]),
            "admitted_native_fork_plans":
                (3 if mode=="fork_plan" else 0),
            "native_selector_unchanged":True,
            "source_barrier_unchanged":True
        },sort_keys=True),flush=True)
        return report
    except BaseException as exc:
        report["status"]="invalid"
        report["error"]=repr(exc)
        raise
    finally:
        stop(process,client,log)
        (OUT/(mode+".json")).write_text(json.dumps(report,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"milestone":"COMPILER-IR-024","stage":"compiler_native_fork_plan_admission",
            "status":"started","arms":{},"index_implemented":False,
            "selector_replacement":False,"production_promotion":False,
            "causal_cpu_claim":False}
    try:
        for mode in MODES:
            report["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        reference=report["arms"]["native"]["snapshots"]
        actual=report["arms"]["fork_plan"]["snapshots"]
        if reference!=actual:
            differences={k:{"native":reference[k],"compiled":actual[k]}
                         for k in reference if reference[k]!=actual.get(k)}
            raise AssertionError("Typed IR fork-plan source-slot semantic parity failure: "+
                                 json.dumps(dict(list(differences.items())[:5])))
        report["status"]="accepted_compiler_plan_admission_only"
        report["native_semantic_parity"]=True
        report["snapshots_per_arm"]=len(reference)
        print("IR024_SUMMARY "+json.dumps({
            "status":report["status"],
            "snapshots_per_arm":len(reference),
            "actual_bytecode_neighbor_regions":True,
            "native_fork_plans":3,
            "compiler_owned_shape_admission":True,
            "runtime_selector_index":False,
            "selector_replacement":False,
            "causal_cpu_claim":False
        },sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid"
        report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":
    main()
