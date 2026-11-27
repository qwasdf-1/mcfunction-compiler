#!/usr/bin/env python3
"""IR045 native result-store differential; genuine native terminal and callbacks."""
from __future__ import annotations
import json,time
import ci_typed_ir019_native as base
import ci_typed_ir044 as prior
from ci_typed_ir013 import stop,stat

OUT=base.ROOT/"build/reports/COMPILER-IR-045"
MODES=("native","old_bytecode","interpreted","bytecode","direct")
QUOTAS=(65536,*range(1,25),32,48,64,128)
ROOTS={
 "ir019_ir045_storage":[
    "execute store result score #result fc_ir run data get storage fc_ir:ir045 value 1",
    "execute store success score #success fc_ir run data get storage fc_ir:ir045 value 1",
    "execute store result score #miss fc_ir run data get storage fc_ir:ir045 missing 1",
    "execute store success score #miss2 fc_ir run data get storage fc_ir:ir045 missing 1",
    "execute store result score #result fc_temp run data get storage fc_ir:ir045 value 1",
    "data modify storage fc_ir:ir045 value set value -3",
    "execute store result score #changed fc_ir run data get storage fc_ir:ir045 value 1",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir045_order":[
    "scoreboard players add #after fc_ir 1",
    "scoreboard players add #after fc_ir 2",
    "execute store result score #result fc_ir run scoreboard players add #after fc_ir 4",
    "execute store success score #success fc_ir run scoreboard players add #after fc_ir 8",
    "scoreboard players add #after fc_ir 16",
    "scoreboard players add #after fc_ir 32"],
 "ir019_ir045_pos":[
    "execute store result score @s fc_ir run data get entity @s Pos[1] 1",
    "execute store result score #result fc_ir run data get entity @s Pos[0] 1",
    "execute store success score #success fc_ir run data get entity @s Pos[2] 1",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir045_no_entity":[
    "execute store result score #result fc_ir run data get entity @s Pos[0] 1",
    "execute store success score @s fc_ir run data get storage fc_ir:ir045 value 1",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir045_copy":[
    "execute store success score #first fc_ir run data modify entity @s data.saved_nbt set from block ~ ~ ~ {}",
    "execute store success score #second fc_ir run data modify entity @s data.saved_nbt set from block ~ ~ ~ {}",
    "setblock 1 64 1 minecraft:stone",
    "execute store success score #third fc_ir run data modify entity @s data.saved_nbt set from block ~ ~ ~ {}",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir045_callback":[
    "execute store result score #outer fc_ir run function fc_ir:ir019_ir045_child",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir045_opaque":[
    "execute positioned 0 64 0 store result score #result fc_ir run data get storage fc_ir:ir045 value 1",
    "execute store result score #outer fc_ir store success score #success fc_ir run data get storage fc_ir:ir045 value 1",
    "execute store result storage fc_ir:ir045 other int 1 run data get storage fc_ir:ir045 value 1",
    "execute store result score #miss fc_ir run return 7",
    "scoreboard players add #after fc_ir 100"],
}
EXTRA={"ir019_ir045_child":[
    "execute store result score #result fc_ir run data get storage fc_ir:ir045 value 1",
    "return 7"]}
LAYOUTS={"ir019_ir045_storage":6,"ir019_ir045_order":2,"ir019_ir045_pos":3,
         "ir019_ir045_no_entity":2,"ir019_ir045_copy":3,"ir019_ir045_callback":0,
         "ir019_ir045_child":1,"ir019_ir045_opaque":0}
SCORES=("#result","#success","#miss","#miss2","#changed","#first","#second","#third","#outer")
EXPECTED={
 "ir019_ir045_storage":{"#result":7,"#success":1,"#miss":0,"#miss2":0,"#changed":-3,"#after":1},
 "ir019_ir045_order":{"#after":63,"#result":7,"#success":1},
 "ir019_ir045_pos":{"#result":1,"#success":1,"self_score":64,"#after":1},
 "ir019_ir045_no_entity":{"#result":0,"#after":1},
 "ir019_ir045_copy":{"#first":1,"#second":0,"#third":0,"copy_x":1,"#after":1},
 "ir019_ir045_callback":{"#outer":7,"#result":7,"#after":1},
 "ir019_ir045_opaque":{"#result":7,"#outer":7,"#success":1,"#after":0},
}
ORIGINAL_FIXTURE=base.fixture

def options(mode):
    flags=prior.options(mode)
    flags.update({"FC_TYPED_IR_GUARD_TERMINAL":str(mode!="native").lower(),
                  "FC_TYPED_IR_NATIVE_STORE":str(mode in MODES[2:]).lower()})
    return flags

def establish(client):
    client.command("forceload add 0 0")
    deadline=time.monotonic()+15
    while True:
        client.command("setblock 1 64 1 minecraft:chest")
        client.command("execute store success score #setupblock fc_ir run execute if block 1 64 1 minecraft:chest")
        if base.nullable_score(client,"#setupblock","fc_ir")==1:return
        if time.monotonic()>deadline:raise AssertionError("fixture block unavailable")
        time.sleep(.1)

def reset(client,name):
    base.reset(client)
    for h in SCORES:client.command(f"scoreboard players set {h} fc_ir -999")
    client.command("scoreboard objectives remove fc_temp")
    client.command("data modify storage fc_ir:ir045 value set value 7")
    client.command("data remove storage fc_ir:ir045 missing")
    client.command("data remove storage fc_ir:ir045 other")
    client.command("kill @e[tag=fc045_probe]")
    client.command("setblock 1 64 1 minecraft:air")
    client.command("setblock 1 64 1 minecraft:chest")
    if name not in ("ir019_ir045_pos","ir019_ir045_copy"):return ""
    entity="marker" if name.endswith("_copy") else "armor_stand"
    nbt='{Tags:["fc045_probe"]}' if entity=="marker" else '{Tags:["fc045_probe"],NoGravity:1b,Marker:1b}'
    summon=client.command(f"summon minecraft:{entity} 1 64 1 "+nbt)
    selector=f"@e[type=minecraft:{entity},tag=fc045_probe,limit=1]"
    deadline=time.monotonic()+10
    while True:
        client.command("scoreboard players set #entityprobe fc_ir 0")
        client.command(f"execute as {selector} run scoreboard players set #entityprobe fc_ir 1")
        if base.nullable_score(client,"#entityprobe","fc_ir")==1:break
        if time.monotonic()>deadline:raise AssertionError("fixture entity unavailable: "+summon)
        time.sleep(.1)
    return f"execute as {selector} at @s run "

def snapshot(client):
    r=base.snapshot(client)|{h:base.nullable_score(client,h,"fc_ir") for h in SCORES}
    client.command("scoreboard players set #selfprobe fc_ir -999")
    client.command("execute as @e[tag=fc045_probe,limit=1] run scoreboard players operation #selfprobe fc_ir = @s fc_ir")
    r["self_score"]=base.nullable_score(client,"#selfprobe","fc_ir")
    client.command("scoreboard players set #copyprobe fc_ir -999")
    client.command("execute as @e[type=minecraft:marker,tag=fc045_probe,limit=1] store result score #copyprobe fc_ir run data get entity @s data.saved_nbt.x 1")
    r["copy_x"]=base.nullable_score(client,"#copyprobe","fc_ir")
    r["storage"]=client.command("data get storage fc_ir:ir045")
    return r

def run(mode):
    proc,client,log=base.start(mode)
    r={"mode":mode,"cases":{},"layouts":{},"status":"started"}
    try:
        establish(client)
        for name in ROOTS:
            for quota in QUOTAS:
                prefix=reset(client,name)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                reply=client.command(prefix+"fc_ir019_call fc_ir:"+name)
                if "invalid or disallowed" in reply or "missing function" in reply or "instantiation failed" in reply:
                    raise AssertionError("fixture invocation failed: "+reply)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                state=snapshot(client)
                r["cases"][f"{name}/{quota}"]=state
                if quota==65536:
                    for k,v in EXPECTED[name].items():
                        if state[k]!=v:raise AssertionError(f"{mode}/{name}/{k}: {state[k]} != {v}; reply={reply!r}; state={state!r}")
        if mode!="native":
            for name,count in LAYOUTS.items():
                ledger=client.command("functioncompiler ir016 fc_ir:"+name)
                actual=stat(ledger,"typed_stores")
                expected=count if mode in MODES[2:] else 0
                if actual!=expected:raise AssertionError(f"{mode}/{name}: {actual} != {expected}: {ledger}")
                if actual and "direct_candidate=true" in ledger:raise AssertionError("T node admitted into direct cursor")
                r["layouts"][name]=ledger
            r["diagnostics"]=client.command("functioncompiler ir008")
            for k in ("ir045_lowered","ir045_data_lowered","ir045_score_lowered","ir045_entered","ir045_queued"):
                if (stat(r["diagnostics"],k)>0)!=(mode in MODES[2:]):
                    raise AssertionError("IR045 wrong path: "+k+" "+r["diagnostics"])
        r["status"]="accepted"
        print("IR045_ARM "+json.dumps({"mode":mode,"cases":len(r["cases"]),
             "diagnostics":r.get("diagnostics"),"layouts":r["layouts"]}),flush=True)
        return r
    finally:
        stop(proc,client,log)
        (OUT/f"{mode}.json").write_text(json.dumps(r,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS=ROOTS|EXTRA
    base.fixture=ORIGINAL_FIXTURE
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
        print("IR045_SUMMARY "+json.dumps({k:r[k] for k in ("status","native_semantic_parity","cases_per_arm")}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
if __name__=="__main__":main()
