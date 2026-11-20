#!/usr/bin/env python3
"""IR-019: original vanilla dispatch scheduling and passive call-census validation.

Three separate actual Minecraft 26.3/Java25 servers:
  native: original unwrapped commands as semantic oracle
  census: exact original commands, opt-in source-entry and native CallFunction
          observation with ZERO dispatch rewriting
  ir018: previous typed JVM scoreboard compiler, native dispatch barriers
The study makes no CPU or successful-guard attribution claim.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir013 import stop
from ci_typed_ir017 import nullable_score

OUT=ROOT/"build/reports/COMPILER-IR-019-NATIVE"
PACK="fc_ir019"
MODES=("native","census","ir018")
QUOTAS=(1,2,3,4,5,6,8,12,16,32,64)
FUNCTIONS={
    "ir019_child_hit": ["scoreboard players add #hit fc_ir 5"],
    "ir019_child_skip": ["scoreboard players add #skip fc_ir 100"],
    "ir019_child_chain": ["scoreboard players add #chain fc_ir 7"],
    "ir019_child_return": [
        "scoreboard players add #return_child fc_ir 3",
        "return 0",
        "scoreboard players add #return_child fc_ir 100",
    ],
    "ir019_child_nested": [
        "scoreboard players add #nested fc_ir 2",
        "function fc_ir:ir019_child_hit",
        "scoreboard players add #nested fc_ir 4",
    ],
    "ir019_single": [
        "scoreboard players set #g fc_ir 2",
        "execute if score #g fc_ir matches 2..3 run function fc_ir:ir019_child_hit",
        "execute unless score #g fc_ir matches 2..3 run function fc_ir:ir019_child_skip",
        "scoreboard players set #g fc_ir 8",
        "execute if score #g fc_ir matches 2..3 run function fc_ir:ir019_child_skip",
        "scoreboard players add #after fc_ir 1",
    ],
    "ir019_chained": [
        "scoreboard players set #g fc_ir 2",
        "scoreboard players set #a fc_ir 3",
        "execute if score #g fc_ir matches 2 "
        "if score #a fc_ir matches 3 run function fc_ir:ir019_child_chain",
        "execute if score #g fc_ir matches 2 "
        "if score #a fc_ir matches 9 run function fc_ir:ir019_child_skip",
        "scoreboard players add #after fc_ir 2",
    ],
    "ir019_return": [
        "scoreboard players set #g fc_ir 1",
        "execute if score #g fc_ir matches 1.. "
        "run return run function fc_ir:ir019_child_return",
        "scoreboard players add #after fc_ir 100",
    ],
    "ir019_nested": [
        "scoreboard players set #g fc_ir 2",
        "execute if score #g fc_ir matches 2 run function fc_ir:ir019_child_nested",
        "scoreboard players add #after fc_ir 4",
    ],
    "ir019_missing": [
        "scoreboard players reset #absent fc_ir",
        "execute if score #absent fc_ir matches 1.. "
        "run function fc_ir:ir019_child_skip",
        "execute unless score #absent fc_ir matches 1.. "
        "run function fc_ir:ir019_child_hit",
        "scoreboard players add #after fc_ir 6",
    ],
    "ir019_self": [
        "scoreboard players set @s fc_ir 3",
        "execute if score @s fc_ir matches 2..3 run function fc_ir:ir019_child_hit",
        "execute unless score @s fc_ir matches 1..4 run function fc_ir:ir019_child_skip",
        "scoreboard players add #after fc_ir 3",
    ],
    "ir019_mix": [
        "scoreboard players add #after fc_ir 1",
        "scoreboard players add #after fc_ir 2",
        "execute if score #g fc_ir matches 0.. run function fc_ir:ir019_child_hit",
        "scoreboard players add #after fc_ir 3",
        "scoreboard players add #after fc_ir 4",
    ],
}
ROOT_CASES=("ir019_single","ir019_chained","ir019_return",
            "ir019_nested","ir019_missing","ir019_self","ir019_mix")
CALLEE_NAMES=("ir019_child_hit","ir019_child_skip","ir019_child_chain",
              "ir019_child_return","ir019_child_nested")
SOURCE_NAMES=tuple(FUNCTIONS)
SCORE_NAMES=("#hit","#skip","#chain","#return_child","#nested","#after","#g","#a")
EXPECTED={
    "ir019_single":{"#hit":5,"#skip":0,"#after":1},
    "ir019_chained":{"#chain":7,"#skip":0,"#after":2},
    "ir019_return":{"#return_child":3,"#after":0},
    "ir019_nested":{"#nested":6,"#hit":5,"#after":4},
    "ir019_self":{"#hit":5,"#skip":0,"#after":3},
}


def fixture(work: Path):
    directory=work/"world/datapacks"/PACK/"data/fc_ir/function"
    directory.mkdir(parents=True,exist_ok=True)
    root=directory.parents[2]
    (root/"pack.mcmeta").write_text(json.dumps({
        "pack":{"description":"IR-019 native conditional function dispatch",
                "min_format":[97,1],"max_format":[97,1]}})+"\n")
    for name,commands in FUNCTIONS.items():
        (directory/f"{name}.mcfunction").write_text("\n".join(commands)+"\n")


def options(mode):
    compiled=mode!="native"
    census=mode=="census"
    typed=mode=="ir018"
    return {
        "FC_WRAPPER_PROBE":str(compiled).lower(),
        "FC_COMPILER_EXEC_CENSUS":str(census).lower(),
        "FC_COMPILER_EXEC_CENSUS_NAMESPACE":"fc_ir" if census else "",
        "FC_COMPILER_EXEC_CENSUS_FUNCTIONS":
            ",".join("fc_ir:"+name for name in SOURCE_NAMES) if census else "",
        "FC_COMPILER_EXEC_CENSUS_CALLEES":
            ",".join("fc_ir:"+name for name in CALLEE_NAMES) if census else "",
        "FC_TYPED_IR_DISPATCH_TEST_HARNESS":"true",
        "FC_TYPED_IR_MODE":"bytecode" if typed else "",
        "FC_TYPED_IR_NAMESPACE":"fc_ir" if typed else "",
        "FC_TYPED_IR_DIAGNOSTICS":"true" if typed else "false",
        "FC_TYPED_IR_SELF_HOLDER":str(typed).lower(),
        "FC_TYPED_IR_RANGE_GUARDS":str(typed).lower(),
        "FC_TYPED_IR_REENTRANT_SAFE":str(typed).lower(),
        "FC_TYPED_IR_DIRECT_FUNCTION":"false",
        "FC_SCORE_ADD_PROTOTYPE":"false",
        "FC_SCORE_ADD_METRICS":"false",
        "FC_FUSED_REGION_PROTOTYPE":"false",
        "FC_BYTECODE_REGION_PROTOTYPE":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS":"false",
    }


def start(mode):
    OUT.mkdir(parents=True,exist_ok=True)
    RUNS.mkdir(parents=True,exist_ok=True)
    work=RUNS/("ci-ir019-"+mode)
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    fixture(work)
    (work/"eula.txt").write_text("eula=true\n")
    port,rcon=unused_port(),unused_port()
    passwd=secrets.token_hex(14)
    (work/"server.properties").write_text("\n".join([
        "online-mode=false","enable-rcon=true","broadcast-rcon-to-ops=false",
        "level-name=world","level-type=minecraft:flat",
        "pause-when-empty-seconds=-1","view-distance=2","simulation-distance=2",
        "max-tick-time=-1","max-players=1",
        f"server-port={port}",f"rcon.port={rcon}",f"rcon.password={passwd}"])+"\n")
    env=dict(os.environ);env.update(options(mode))
    command=[str(ROOT/"gradlew"),"--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}","runServer"]
    output=(OUT/f"{mode}.server.log").open("w",encoding="utf-8")
    proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,
                          stderr=subprocess.STDOUT,stdin=subprocess.PIPE)
    try:
        client=wait_for_rcon(proc,rcon,passwd,timeout_seconds=240)
        if PACK not in client.command("datapack list enabled"):
            raise AssertionError("Original IR019 commands not loaded")
        client.command("scoreboard objectives add fc_ir dummy")
        client.command("gamerule sendCommandFeedback false")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        return proc,client,output
    except BaseException:
        proc.terminate();proc.wait(timeout=40);output.close();raise


def reset(client):
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    for name in SCORE_NAMES:
        client.command(f"scoreboard players set {name} fc_ir 0")
    client.command("scoreboard players reset #absent fc_ir")


def snapshot(client):
    return {name:nullable_score(client,name,"fc_ir") for name in SCORE_NAMES} | {
        "#absent":nullable_score(client,"#absent","fc_ir")}


def invoke(client,name):
    # Real execute summon binds an entity for @s without persistence assumptions.
    prefix="execute positioned 0 64 0 summon minecraft:armor_stand run " if name=="ir019_self" else ""
    answer=client.command(prefix+f"fc_ir019_call fc_ir:{name}")
    if name!="ir019_self" and "FC_ARCH_CALL queued" not in answer:
        raise AssertionError(f"IR019 original function call rejected: {name} {answer!r}")


def parse_log(path):
    lines=path.read_text(errors="replace").splitlines()
    rows=[];callees={}
    for line in lines:
        if "FC_EXEC_ROW " in line:
            text=line.split("FC_EXEC_ROW ",1)[1]
            metadata, marker, original_input = text.partition(" input=")
            found=dict(re.findall(r"(\w+)=(\S+)",metadata))
            row={k:found.get(k) for k in (
                "function","index","entries","callbacks","kind","dispatch_shape")}
            row["input"] = original_input[:240] if marker else None
            rows.append(row)
        if "FC_EXEC_CALLEE " in line:
            text=line.split("FC_EXEC_CALLEE ",1)[1]
            found=re.search(r"function=(\S+) native_call_tasks=(\d+)",text)
            if found:callees[found.group(1)]=int(found.group(2))
    return rows,callees


def run_arm(mode):
    proc,client,output=start(mode)
    report={"mode":mode,"status":"started","snapshots":{},"original_source":True}
    try:
        if mode=="census":
            result=client.command("functioncompiler exec-census-start")
            if "FC_EXEC started" not in result:
                raise AssertionError(f"Native census did not start: {result!r}")
        for name in ROOT_CASES:
            reset(client);invoke(client,name)
            obs=snapshot(client)
            report["snapshots"][name]=obs
            if mode=="native":
                for slot,expected in EXPECTED.get(name,{}).items():
                    if obs[slot]!=expected:
                        raise AssertionError(f"{name}/{slot}: {obs[slot]} != {expected}")
        for quota in QUOTAS:
            for name in ROOT_CASES:
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                reply=client.command("gamerule minecraft:max_command_sequence_length")
                if not re.search(rf"\b{quota}\b",reply):
                    raise AssertionError(f"Quota not applied: {reply}")
                invoke(client,name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["snapshots"][f"{name}/quota/{quota}"]=snapshot(client)
        if mode=="census":
            response=client.command("functioncompiler exec-census-stop")
            if "FC_EXEC ended" not in response:
                raise AssertionError(f"Census did not stop: {response}")
            report["census_command"]=response
            # Flush RCON command's log before taking the read-only snapshot.
            import time;time.sleep(0.3)
            rows,callees=parse_log(OUT/f"{mode}.server.log")
            report["census_rows"]=rows
            report["callee_calls"]=callees
            if not rows or not any(r["dispatch_shape"]=="single_score_static_call"
                                   and int(r["entries"])>0 for r in rows):
                raise AssertionError("No native single score call-site reaches recorded")
            if not any(r["dispatch_shape"]=="complex_or_return_call"
                       and int(r["entries"])>0 for r in rows):
                raise AssertionError("No native complex dispatch source sites recorded")
            if callees.get("fc_ir:ir019_child_hit",0)<=0:
                raise AssertionError(f"Native child call tasks never observed: {callees}")
            if callees.get("fc_ir:ir019_child_skip",0)!=0:
                raise AssertionError(f"Failed guards incorrectly invoked skipped callee: {callees}")
        if mode=="ir018":
            diagnostic=client.command("functioncompiler ir008")
            report["typed_diagnostic"]=diagnostic
            if "bytecode_regions=" not in diagnostic or "ir018_dispatch_barriers=" not in diagnostic:
                raise AssertionError(f"Prior compiler did not activate: {diagnostic!r}")
        report["status"]="complete"
        print("IR019_NATIVE_ARM "+json.dumps({
            "mode":mode,"observations":len(report["snapshots"]),
            "callee_calls":report.get("callee_calls"),
            "census_command":report.get("census_command"),
        },sort_keys=True),flush=True)
        return report
    except BaseException as error:
        report["status"]="invalid";report["error"]=repr(error);raise
    finally:
        stop(proc,client,output)
        (OUT/f"{mode}.json").write_text(json.dumps(report,indent=2)+"\n")


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"milestone":"COMPILER-IR-019","stage":"read_only_dispatch_native_baseline",
            "status":"started","production_promotion":False,
            "performance_claim":False,"compiled_dispatch_claim":False,"arms":[]}
    try:
        for mode in MODES:
            result["arms"].append(run_arm(mode))
            (OUT/"results.json").write_text(json.dumps(result,indent=2)+"\n")
        ref=result["arms"][0]["snapshots"]
        for arm in result["arms"][1:]:
            mismatches={k:{"native":ref[k],"other":value}
                        for k,value in arm["snapshots"].items() if value!=ref[k]}
            if mismatches:
                raise AssertionError(f"IR019 {arm['mode']} snapshot mismatch "
                                     +json.dumps(dict(list(mismatches.items())[:4])))
        result["status"]="accepted"
        result["native_semantic_parity"]=True
        result["observations_per_arm"]=len(ref)
    except BaseException as e:
        result["status"]="invalid";result["error"]=repr(e);raise
    finally:
        (OUT/"results.json").write_text(json.dumps(result,indent=2)+"\n")
    print("IR019_NATIVE_SUMMARY "+json.dumps({
        "status":result["status"],"native_semantic_parity":True,
        "observations_per_arm":len(ref),
        "compiled_dispatch_claim":False,"performance_claim":False
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()
