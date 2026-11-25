#!/usr/bin/env python3
"""IR044 native tag/block/score/queue differential. No synthetic scheduler."""
from __future__ import annotations
import json,time
import ci_typed_ir019_native as base
import ci_typed_ir043 as prior
from ci_typed_ir013 import stop,stat

OUT=base.ROOT/"build/reports/COMPILER-IR-044"
MODES=("native","old_bytecode","interpreted","bytecode","direct")
QUOTAS=(65536,*range(1,25),32,48,64,128)
ROOTS={
 "ir019_ir044_block":[
    "execute if block ~ ~-1 ~ minecraft:stone run tag @s add fc044_hit",
    "execute unless block ~ ~-1 ~ minecraft:stone run tag @s add fc044_skip",
    "execute if block 0 63 0 minecraft:air run tag @s add fc044_skip",
    "setblock 0 63 0 minecraft:dirt",
    "execute if block ~ ~-1 ~ #fc_ir:ir044_test_blocks run tag @s add fc044_changed",
    "execute unless block 0 63 0 minecraft:stone run tag @s add fc044_neg",
    "execute if block 0 63 0 minecraft:dirt run tag @s remove fc044_hit",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir044_score":[
    "scoreboard players set @s fc_ir 7",
    "execute if score @s fc_ir matches 7 run tag @s add fc044_hit",
    "execute unless score @s fc_ir matches 7 run tag @s add fc044_skip",
    "execute if score #absent fc_ir matches 0 run tag @s add fc044_skip",
    "execute unless score #absent fc_ir matches 0 run tag @s add fc044_neg",
    "execute if score #g fc_ir = #a fc_ir run tag @s add fc044_changed",
    "execute if score #g fc_temp matches 0 run tag @s add fc044_skip",
    "execute if score #g fc_ir matches 0 run tag @s add fc044_hit",
    "execute if score #g fc_ir matches 0 run tag @s remove fc044_skip",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir044_order":[
    "scoreboard players add #after fc_ir 1",
    "scoreboard players add #after fc_ir 2",
    "execute if block 0 63 0 minecraft:stone run scoreboard players add #after fc_ir 4",
    "execute if block 0 63 0 minecraft:air run scoreboard players add #after fc_ir 100",
    "scoreboard players add #after fc_ir 8",
    "scoreboard players add #after fc_ir 16"],
 "ir019_ir044_opaque":[
    "execute positioned 0 64 0 if block ~ ~-1 ~ minecraft:stone run tag @s add fc044_hit",
    "execute if block 0 63 0 minecraft:stone if score #g fc_ir matches 0 run tag @s add fc044_neg",
    "execute if entity @s run tag @s add fc044_changed",
    "execute store success score #result fc_ir run execute if block 0 63 0 minecraft:stone run tag @s add fc044_skip",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir044_callback":[
    "execute store result score #result fc_ir run function fc_ir:ir019_ir044_child",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir044_return":[
    "execute if block 0 63 0 minecraft:stone run return run tag @s add fc044_hit",
    "scoreboard players add #after fc_ir 100"],
 "ir019_ir044_no_entity":[
    "execute if block 0 63 0 minecraft:stone run tag @s add fc044_hit",
    "execute if score @s fc_ir matches 7 run tag @s add fc044_skip",
    "scoreboard players add #after fc_ir 1"],
}
EXTRA={"ir019_ir044_child":[
    "execute if block 0 63 0 minecraft:stone run tag @s add fc044_hit",
    "return 7"]}
LAYOUTS={"ir019_ir044_block":6,"ir019_ir044_score":8,"ir019_ir044_order":2,
         "ir019_ir044_opaque":0,"ir019_ir044_callback":0,"ir019_ir044_child":1,
         "ir019_ir044_return":0,"ir019_ir044_no_entity":2}
TAGS=("fc044_hit","fc044_skip","fc044_changed","fc044_neg")
EXPECTED={
 "ir019_ir044_block":{"#after":1,"fc044_hit":0,"fc044_skip":0,"fc044_changed":1,"fc044_neg":1},
 "ir019_ir044_score":{"#after":1,"fc044_hit":1,"fc044_skip":0,"fc044_changed":1,"fc044_neg":1},
 "ir019_ir044_order":{"#after":31},
 "ir019_ir044_opaque":{"#after":1,"fc044_hit":1,"fc044_skip":1,"fc044_changed":1,"fc044_neg":1},
 "ir019_ir044_callback":{"#after":1,"#result":7,"fc044_hit":1},
 "ir019_ir044_return":{"#after":0,"fc044_hit":1},
 "ir019_ir044_no_entity":{"#after":1,"fc044_hit":0,"fc044_skip":0},
}
ORIGINAL_FIXTURE=base.fixture

def fixture(work):
    ORIGINAL_FIXTURE(work)
    path=work/"world/datapacks"/base.PACK/"data/fc_ir/tags/block/ir044_test_blocks.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"values":["minecraft:stone","minecraft:dirt"]})+"\n")

def options(mode):
    flags=prior.options(mode)
    flags.update({"FC_TYPED_IR_DISPATCH":str(mode!="native").lower(),
                  "FC_TYPED_IR_GUARD_TERMINAL":str(mode in MODES[2:]).lower()})
    return flags

def reset(client):
    base.reset(client)
    client.command("scoreboard players set #result fc_ir 0")
    client.command("scoreboard objectives remove fc_temp")
    client.command("kill @e[type=minecraft:armor_stand,tag=fc044_probe]")
    client.command("setblock 0 63 0 minecraft:stone")
    client.command("execute store success score #setupblock fc_ir run execute if block 0 63 0 minecraft:stone")
    if base.nullable_score(client,"#setupblock","fc_ir")!=1:
        raise AssertionError("fixture failed to establish loaded stone block")

def snapshot(client):
    out=base.snapshot(client)|{"#result":base.nullable_score(client,"#result","fc_ir")}
    for tag in TAGS:
        client.command("scoreboard players set #tagprobe fc_ir 0")
        client.command(f"execute as @e[type=minecraft:armor_stand,tag=fc044_probe,tag={tag}] run scoreboard players set #tagprobe fc_ir 1")
        out[tag]=base.nullable_score(client,"#tagprobe","fc_ir")
    client.command("execute store success score #blockprobe fc_ir run execute if block 0 63 0 minecraft:dirt")
    out["dirt"]=base.nullable_score(client,"#blockprobe","fc_ir")
    return out

def run(mode):
    proc,client,log=base.start(mode)
    r={"mode":mode,"cases":{},"layouts":{},"status":"started"}
    try:
        client.command("forceload add 0 0")
        # Force-load tickets are asynchronous; establish a real block witness
        # before beginning the native reference, not merely issue a command.
        deadline=time.monotonic()+15
        while True:
            block_reply=client.command("setblock 0 63 0 minecraft:stone")
            client.command("execute store success score #setupblock fc_ir run execute if block 0 63 0 minecraft:stone")
            if base.nullable_score(client,"#setupblock","fc_ir")==1:break
            if time.monotonic()>deadline:raise AssertionError("initial block unavailable: "+block_reply)
            time.sleep(.1)
        for name in ROOTS:
            for quota in QUOTAS:
                reset(client)
                if name!="ir019_ir044_no_entity":
                    summon=client.command('summon minecraft:armor_stand 0 64 0 {Tags:["fc044_probe"],NoGravity:1b,Marker:1b}')
                    deadline=time.monotonic()+10
                    while True:
                        client.command("scoreboard players set #entityprobe fc_ir 0")
                        client.command("execute as @e[type=minecraft:armor_stand,tag=fc044_probe,limit=1] run scoreboard players set #entityprobe fc_ir 1")
                        if base.nullable_score(client,"#entityprobe","fc_ir")==1:break
                        if time.monotonic()>deadline:raise AssertionError("fixture entity unavailable: "+summon)
                        time.sleep(.1)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                prefix="" if name=="ir019_ir044_no_entity" else "execute as @e[type=minecraft:armor_stand,tag=fc044_probe,limit=1] at @s run "
                reply=client.command(prefix+"fc_ir019_call fc_ir:"+name)
                if "invalid or disallowed" in reply or "instantiation failed" in reply or "missing function" in reply:
                    raise AssertionError("fixture invocation failed: "+reply)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                state=snapshot(client)
                r["cases"][f"{name}/{quota}"]=state
                if quota==65536:
                    if name!="ir019_ir044_no_entity":
                        client.command("scoreboard players set #entityprobe fc_ir 0")
                        client.command("execute as @e[type=minecraft:armor_stand,tag=fc044_probe,limit=1] run scoreboard players set #entityprobe fc_ir 1")
                        if base.nullable_score(client,"#entityprobe","fc_ir")!=1:
                            raise AssertionError("fixture entity no longer visible: "+reply)
                    for k,v in EXPECTED[name].items():
                        if state[k]!=v:raise AssertionError(f"{mode}/{name}/{k}: {state[k]} != {v}; reply={reply!r}; state={state!r}")
        if mode!="native":
            for name,count in LAYOUTS.items():
                ledger=client.command("functioncompiler ir016 fc_ir:"+name)
                actual=stat(ledger,"typed_guards")
                expected=count if mode in MODES[2:] else 0
                if actual!=expected:raise AssertionError(f"{mode}/{name}: {actual} != {expected}: {ledger}")
                if actual and "direct_candidate=true" in ledger:raise AssertionError("G node admitted into direct cursor")
                r["layouts"][name]=ledger
            r["diagnostics"]=client.command("functioncompiler ir008")
            for k in ("ir044_lowered","ir044_block_lowered","ir044_score_lowered",
                      "ir044_entered","ir044_pass","ir044_skip"):
                if (stat(r["diagnostics"],k)>0)!=(mode in MODES[2:]):
                    raise AssertionError("IR044 wrong path: "+k+" "+r["diagnostics"])
        r["status"]="accepted"
        print("IR044_ARM "+json.dumps({"mode":mode,"cases":len(r["cases"]),
             "diagnostics":r.get("diagnostics"),"layouts":r["layouts"]}),flush=True)
        return r
    finally:
        stop(proc,client,log)
        (OUT/f"{mode}.json").write_text(json.dumps(r,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS=ROOTS|EXTRA
    base.fixture=fixture
    base.options=options
    r={"status":"started","arms":[],"production_promotion":False}
    try:
        for mode in MODES:
            arm=run(mode)
            r["arms"].append(arm)
            if arm["cases"]!=r["arms"][0]["cases"]:
                diffs={k:{"native":v,"actual":arm["cases"].get(k)} for k,v in r["arms"][0]["cases"].items()
                       if arm["cases"].get(k)!=v}
                raise AssertionError("native parity mismatch "+repr(list(diffs.items())[:5]))
        r.update(status="accepted",native_semantic_parity=True,cases_per_arm=len(r["arms"][0]["cases"]))
        print("IR044_SUMMARY "+json.dumps({k:r[k] for k in ("status","native_semantic_parity","cases_per_arm")}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
if __name__=="__main__":main()
