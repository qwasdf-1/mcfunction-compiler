#!/usr/bin/env python3
"""IR043 actual Minecraft native differential for typed call boundaries."""
from __future__ import annotations
import json,re
import ci_typed_ir019_native as base
import ci_typed_ir040 as prior
from ci_typed_ir013 import stop,stat

OUT=base.ROOT/"build/reports/COMPILER-IR-043"
MODES=("native","old_bytecode","interpreted","bytecode","direct")
QUOTAS=(65536,*range(1,41),48,64,128)
INHERITED=dict(base.FUNCTIONS)
EXTRA={
 "ir019_ir043_order_child":[
    "scoreboard players operation #order fc_ir *= #ten fc_ir",
    "scoreboard players add #order fc_ir 2"],
 "ir019_ir043_order":[
    "scoreboard players set #order fc_ir 1",
    "scoreboard players set #ten fc_ir 10",
    "execute if score #g fc_ir matches 0 run function fc_ir:ir019_ir043_order_child",
    "scoreboard players operation #order fc_ir *= #ten fc_ir",
    "scoreboard players add #order fc_ir 3",
    "function fc_ir:ir019_ir043_order_child",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_compound":[
    "scoreboard players set #g fc_ir 7",
    "scoreboard players set #a fc_ir 9",
    "execute if score #g fc_ir matches 5.. if score #g fc_ir matches 1.. if score #g fc_ir < #a fc_ir if score #a fc_ir > #g fc_ir run function fc_ir:ir019_child_hit",
    "execute if score #g fc_ir matches 5.. if score #g fc_ir matches ..4 if score #a fc_ir matches 9 run function fc_ir:ir019_child_skip",
    "execute unless score #absent fc_ir matches -2147483648..2147483647 unless score #absent fc_ir = #absent fc_ir run function fc_ir:ir019_child_hit",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_suffix":[
    "execute "+" ".join(["if score #g fc_ir matches 1"]+["if score #g fc_ir matches 0"]*7)+" run function fc_ir:ir019_child_skip",
    "scoreboard players add #after fc_ir 1",
    "execute "+" ".join(["if score #g fc_ir matches 0"]*7+["unless score #g fc_ir matches 0"])+" run function fc_ir:ir019_child_skip",
    "scoreboard players add #after fc_ir 2",
    "execute "+" ".join(["if score #g fc_ir matches 0"]*8)+" run function fc_ir:ir019_child_hit",
    "scoreboard players add #after fc_ir 4"],
 "ir019_ir043_self":[
    "scoreboard players set @s fc_ir 7",
    "scoreboard players set #a fc_ir 9",
    "execute if score @s fc_ir matches 5.. if score @s fc_ir < #a fc_ir if score #a fc_ir > @s fc_ir run function fc_ir:ir019_child_hit",
    "execute unless score @s fc_ir matches 5.. run function fc_ir:ir019_child_skip",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_objective":[
    "scoreboard objectives add fc_temp dummy",
    "scoreboard players set #g fc_temp 1",
    "execute if score #g fc_temp matches 1 run function fc_ir:ir019_child_hit",
    "scoreboard objectives remove fc_temp",
    "execute if score #g fc_temp matches 1 run function fc_ir:ir019_child_skip",
    "execute unless score #g fc_temp matches 1 run function fc_ir:ir019_child_skip",
    "execute if score #g fc_ir matches 1 if score #g fc_temp matches 1 run function fc_ir:ir019_child_skip",
    "scoreboard objectives add fc_temp dummy",
    "execute unless score #g fc_temp matches 1 run function fc_ir:ir019_child_hit",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_recursive":[
    "scoreboard players add #depth fc_ir 1",
    "execute if score #depth fc_ir matches ..3 run function fc_ir:ir019_ir043_recursive",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_result_child":[
    "scoreboard players add #hit fc_ir 1",
    "return 7",
    "scoreboard players add #skip fc_ir 100"],
 "ir019_ir043_result":[
    "execute if score #g fc_ir matches 0 run function fc_ir:ir019_ir043_result_child",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_callback":[
    "execute store result score #result fc_ir run function fc_ir:ir019_ir043_result",
    "execute store success score #success fc_ir run function fc_ir:ir019_ir043_result",
    "scoreboard players add #after fc_ir 2"],
 "ir019_ir043_return":[
    "execute if score #g fc_ir matches 0 run return run function fc_ir:ir019_ir043_result_child",
    "scoreboard players add #skip fc_ir 100"],
 "ir019_ir043_opaque":[
    "execute positioned 0 64 0 if score #g fc_ir matches 0 run function fc_ir:ir019_child_hit",
    "function #fc_ir:ir043_tag",
    "function fc_ir:ir019_ir043_macro {value:3}",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_missing_function":[
    "execute if score #g fc_ir matches 0 run function fc_ir:ir043_missing_target",
    "execute if score #g fc_ir matches 1 run function fc_ir:ir043_missing_target",
    "scoreboard players add #after fc_ir 1"],
 "ir019_ir043_macro":["$scoreboard players add #hit fc_ir $(value)"],
}
ROOTS=(*base.ROOT_CASES,"ir019_ir043_order","ir019_ir043_compound","ir019_ir043_suffix",
       "ir019_ir043_self","ir019_ir043_objective","ir019_ir043_recursive",
       "ir019_ir043_result","ir019_ir043_callback","ir019_ir043_return","ir019_ir043_opaque",
       "ir019_ir043_missing_function")
SELF={"ir019_self","ir019_ir043_self"}
EXPECTED={
 "ir019_ir043_order":{"#order":1232,"#after":1},
 "ir019_ir043_compound":{"#hit":10,"#skip":0,"#after":1},
 "ir019_ir043_suffix":{"#hit":5,"#skip":0,"#after":7},
 "ir019_ir043_self":{"#hit":5,"#skip":0,"#after":1},
 "ir019_ir043_recursive":{"#depth":4,"#after":4},
 "ir019_ir043_result":{"#hit":1,"#skip":0,"#after":1},
 "ir019_ir043_return":{"#hit":1,"#skip":0},
 "ir019_ir043_opaque":{"#hit":13,"#after":1},
 "ir019_ir043_missing_function":{"#after":1},
}
# Required explicit D node count for supported functions; unsupported forms
# remain native; no direct cursor across a call boundary.
LAYOUTS={"ir019_single":3,"ir019_chained":2,"ir019_nested":1,"ir019_missing":2,
 "ir019_self":2,"ir019_mix":1,"ir019_return":0,"ir019_ir043_order":2,
 "ir019_ir043_compound":3,"ir019_ir043_suffix":3,"ir019_ir043_self":2,
 "ir019_ir043_objective":5,"ir019_ir043_recursive":1,"ir019_ir043_result":1,
 "ir019_ir043_callback":0,"ir019_ir043_return":0,"ir019_ir043_opaque":0,
 "ir019_ir043_missing_function":2}
ORIGINAL_FIXTURE=base.fixture
ORIGINAL_RESET=base.reset
ORIGINAL_SNAPSHOT=base.snapshot
MORE=("#order","#ten","#depth","#result","#success")

def fixture(work):
    ORIGINAL_FIXTURE(work)
    folder=work/"world/datapacks"/base.PACK/"data/fc_ir/tags/function"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"ir043_tag.json").write_text(json.dumps({"values":["fc_ir:ir019_child_hit"]})+"\n")

def options(mode):
    flags=prior.options(mode)
    flags.update({"FC_TYPED_IR_DISPATCH":str(mode in MODES[2:]).lower(),
        "FC_TYPED_IR_COMPOUND_SCORE":str(mode!="native").lower(),
        "FC_TYPED_IR_DATAFLOW":str(mode!="native").lower(),
        "FC_TYPED_IR_ARITHMETIC":str(mode!="native").lower(),
        "FC_TYPED_IR_EXTENDED_SCORE":str(mode!="native").lower(),
        "FC_TYPED_IR_RANGE_GUARDS":str(mode!="native").lower(),
        "FC_TYPED_IR_SELF_HOLDER":str(mode!="native").lower(),
        "FC_TYPED_IR_DIRECT_FUNCTION":str(mode=="direct").lower(),
        "FC_TYPED_IR_DISPATCH_TEST_HARNESS":"true","FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"false",
        "FC_TYPED_IR040_BENCHMARK":"false","FC_COMPILER_EXEC_CENSUS":"false"})
    return flags

def reset(client):
    ORIGINAL_RESET(client)
    client.command("scoreboard objectives remove fc_temp")
    for h in MORE:client.command("scoreboard players set "+h+" fc_ir 0")

def snapshot(client):
    return ORIGINAL_SNAPSHOT(client)|{h:base.nullable_score(client,h,"fc_ir") for h in MORE}

def invoke(client,name,entity):
    prefix="execute positioned 0 64 0 summon minecraft:armor_stand run " if entity else ""
    response=client.command(prefix+"fc_ir019_call fc_ir:"+name)
    if (not entity and "FC_ARCH_CALL queued" not in response) or "invalid or disallowed" in response:
        raise AssertionError("invoke failed "+response)

def run(mode):
    proc,client,log=base.start(mode)
    r={"mode":mode,"cases":{},"layouts":{},"status":"started"}
    try:
        client.command("forceload add 0 0")
        client.command("setblock 0 63 0 minecraft:stone")
        for name in ROOTS:
            for entity in ((True,False) if name in SELF else (False,)):
                for quota in QUOTAS:
                    reset(client)
                    client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                    invoke(client,name,entity)
                    client.command("gamerule minecraft:max_command_sequence_length 65536")
                    state=snapshot(client)
                    r["cases"][f"{name}/{entity}/{quota}"]=state
                    if quota==65536 and (name not in SELF or entity):
                        for k,v in (base.EXPECTED|EXPECTED).get(name,{}).items():
                            if state[k]!=v:raise AssertionError(f"{mode}/{name}/{k}: {state[k]} != {v}")
        if mode!="native":
            for name,count in LAYOUTS.items():
                ledger=client.command("functioncompiler ir016 fc_ir:"+name)
                actual=stat(ledger,"typed_calls")
                expected=count if mode in MODES[2:] else 0
                if actual!=expected:raise AssertionError(f"{mode}/{name}: {actual} != {expected}: {ledger}")
                if actual and "direct_candidate=true" in ledger:raise AssertionError("call entered direct cursor")
                r["layouts"][name]=ledger
            diag=client.command("functioncompiler ir008")
            r["diagnostics"]=diag
            for key in ("ir043_lowered","ir043_entered","ir043_calls","ir043_skipped",
                        "ir043_fallbacks","ir043_reused","ir043_empty_debits","ir043_proofs"):
                if (stat(diag,key)>0)!=(mode in MODES[2:]):
                    raise AssertionError(f"{mode}: missing or unexpected {key}: {diag}")
        r["status"]="accepted"
        print("IR043_ARM "+json.dumps({"mode":mode,"cases":len(r["cases"]),
           "diagnostics":r.get("diagnostics"),"layouts":r["layouts"]}),flush=True)
        return r
    finally:
        stop(proc,client,log)
        (OUT/f"{mode}.json").write_text(json.dumps(r,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS=INHERITED|EXTRA
    base.fixture=fixture
    base.options=options
    r={"status":"started","arms":[],"production_promotion":False}
    try:
        for mode in MODES:
            arm=run(mode)
            r["arms"].append(arm)
            native=r["arms"][0]["cases"]
            arm["differences"]={k:{"native":v,"actual":arm["cases"].get(k)} for k,v in native.items()
                                if arm["cases"].get(k)!=v}
        diffs={a["mode"]:len(a["differences"]) for a in r["arms"] if a["differences"]}
        if diffs:raise AssertionError("native parity mismatch "+repr(diffs))
        r.update(status="accepted",native_semantic_parity=True,cases_per_arm=len(r["arms"][0]["cases"]))
        print("IR043_SUMMARY "+json.dumps({k:r[k] for k in ("status","native_semantic_parity","cases_per_arm")}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
if __name__=="__main__":main()
