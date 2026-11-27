#!/usr/bin/env python3
"""IR048 initial native parity: scalar, ordered fanout and fallback paths."""
from __future__ import annotations
import json
import re
import time
import ci_typed_ir019_native as base
from ci_typed_ir013 import stat

OUT = base.ROOT / "build/reports/COMPILER-IR-048"
MODES = ("native", "old_bytecode", "interpreted", "bytecode", "direct")
QUOTAS = (1,2,3,4,5,6,7,8,10,12,16,24,32,64,65536)
P = "ir019_ir048_"
SELECT = "@e[type=minecraft:marker,tag=fc048_active,sort=nearest]"
CALL = "run function fc_ir:" + P
ROOTS = {
    P+"at": [f"execute as {SELECT} at @s {CALL}child", "scoreboard players add #after fc_ir 1"],
    P+"before": [f"execute if score #gate fc_ir matches 1 as {SELECT} at @s {CALL}child", "scoreboard players add #after fc_ir 1"],
    P+"after": [f"execute as {SELECT} if score @s fc_ir matches 2.. {CALL}child", "scoreboard players add #after fc_ir 1"],
    P+"compare": [f"execute as {SELECT} if score @s fc_ir >= #two fc_ir {CALL}child", "scoreboard players add #after fc_ir 1"],
    P+"missing": [f"execute as {SELECT} if score @s fc048_missing matches 1 {CALL}child", "scoreboard players add #after fc_ir 1"],
    P+"nested": [f"execute as {SELECT} at @s {CALL}nested_child", "scoreboard players add #after fc_ir 1"],
    P+"opaque": [f"execute as {SELECT} positioned 0 64 0 {CALL}child",
                 f"execute as {SELECT} at @s run return run function fc_ir:{P}child",
                 "scoreboard players add #after fc_ir 100"],
}
CHILDREN = {
    P+"child": [
        "scoreboard players add #calls fc_ir 1",
        "scoreboard players operation #order fc_ir *= #ten fc_ir",
        "scoreboard players operation #order fc_ir += @s fc_ir",
        "scoreboard players add @s fc_hits 1",
        "execute if block ~ ~ ~ minecraft:gold_block run scoreboard players add #position fc_ir 1",
        "execute if block ^ ^ ^1 minecraft:diamond_block run scoreboard players add #rotation fc_ir 1",
    ],
    P+"nested_child": [f"function fc_ir:{P}child", "return 7",
                       "scoreboard players add #after fc_ir 100"],
}
SCENARIOS = (("at",0,1),("at",1,1),("at",3,1),
             ("before",3,0),("before",3,1),("before",0,1),
             ("after",3,1),("after",1,1),("compare",3,1),
             ("missing",3,1),("nested",3,1),("opaque",1,1))
KEYS = ("ir048_lowered","ir048_entered","ir048_empty","ir048_single","ir048_multi",
        "ir048_fallbacks","ir048_debits","ir048_empty_debits","ir048_modifiers",
        "ir048_multi_stages","ir048_terminals","ir048_errors","ir048_limit_errors")
SCORES = ("#calls","#order","#position","#rotation","#after","#callback_seen")
def options(mode):
    compiled = mode != "native"
    return base_original_options("native") | {
        "FC_WRAPPER_PROBE": str(compiled).lower(),
        "FC_TYPED_COMPILER_PROFILE": "validated" if compiled else "",
        "FC_TYPED_IR_NAMESPACE": "fc_ir" if compiled else "",
        "FC_TYPED_IR_MODE": ("interpreted" if mode=="interpreted" else "bytecode") if compiled else "",
        "FC_TYPED_IR_CONTEXT_DISPATCH": str(mode in MODES[2:]).lower(),
        "FC_TYPED_IR_DIAGNOSTICS": str(compiled).lower(),
        "FC_TYPED_IR_DIRECT_FUNCTION": str(mode=="direct").lower(),
        "FC_TYPED_IR_DIRECT_FUNCTION_HARNESS": str(mode=="direct").lower(),
        "FC_TYPED_IR_SELF_HOLDER": str(compiled).lower(),
        "FC_TYPED_IR_RANGE_GUARDS": str(compiled).lower(),
        "FC_TYPED_IR_REENTRANT_SAFE": str(compiled).lower(),
        "FC_IR048_NATIVE_HARNESS": "true",
        "FC_IR048_CENSUS": "false",
    }
base_original_options = base.options

def score(client, name, objective="fc_ir"):
    return base.nullable_score(client, name, objective)

def establish(client):
    client.command("forceload add 0 0")
    client.command("scoreboard objectives add fc_hits dummy")
    client.command("kill @e[tag=fc048_marker]")
    deadline = time.monotonic()+15
    while True:
        client.command("setblock 0 64 0 minecraft:air")
        client.command("setblock 0 64 1 minecraft:air")
        client.command("setblock 1 64 1 minecraft:gold_block")
        client.command("execute store success score #setup fc_ir run execute if block 1 64 1 minecraft:gold_block")
        if score(client,"#setup")==1: break
        if time.monotonic()>deadline: raise AssertionError("fixture chunk unavailable")
        time.sleep(.1)
    for i,x in enumerate((1,4,7),1):
        client.command(f"setblock {x} 64 1 minecraft:gold_block")
        client.command(f"setblock {x} 64 2 minecraft:diamond_block")
        reply=client.command(f'summon minecraft:marker {x} 64 1 {{Tags:["fc048_marker","fc048_{i}"],Rotation:[0f,0f]}}')
        s=f"@e[tag=fc048_{i},limit=1]"
        # A block-accessible chunk need not yet expose freshly spawned entities.
        # Use the same bounded native selector readiness gate as IR047.
        deadline = time.monotonic()+10
        while True:
            client.command("scoreboard players set #entity_ready fc_ir 0")
            probe = client.command(f"execute as @e[type=minecraft:marker,tag=fc048_{i}] run scoreboard players add #entity_ready fc_ir 1")
            count = score(client,"#entity_ready")
            if count == 1: break
            if count != 0 or time.monotonic()>deadline:
                raise AssertionError(f"marker {i} unavailable or duplicated: count={count}, summon={reply!r}, probe={probe!r}")
            time.sleep(.1)
        assigned = client.command(f"scoreboard players set {s} fc_ir {i}")
        assert score(client,s)==i, (reply,assigned)
    client.command("gamerule minecraft:max_command_forks 65536")

def reset(client,n,gate):
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    client.command("gamerule minecraft:max_command_forks 65536")
    for h in SCORES: client.command(f"scoreboard players set {h} fc_ir 0")
    client.command("scoreboard players set #ten fc_ir 10")
    client.command("scoreboard players set #two fc_ir 2")
    client.command(f"scoreboard players set #gate fc_ir {gate}")
    client.command("scoreboard players set @e[tag=fc048_marker] fc_hits 0")
    client.command("tag @e[tag=fc048_marker] remove fc048_active")
    for i in range(1,n+1): client.command(f"tag @e[tag=fc048_{i}] add fc048_active")

def snapshot(client):
    return {h:score(client,h) for h in SCORES} | {
        "hits":[score(client,f"@e[tag=fc048_{i},limit=1]","fc_hits") for i in range(1,4)]}

def invoke(client,name,quota=65536,positioned=True):
    prefix="execute positioned 0 64 0 run " if positioned else ""
    reply=client.command(prefix+"fc_ir019_call fc_ir:"+P+name)
    if "FC_ARCH_CALL queued" not in reply:
        if positioned and quota<=2 and not reply.strip(): return
        raise AssertionError(f"invocation failed {name}/{quota}: {reply!r}")

def expected(name,n,gate):
    if name=="opaque": return None
    ids=list(range(1,n+1))
    if name=="before" and gate!=1 or name=="missing": ids=[]
    if name in ("after","compare"): ids=[i for i in ids if i>=2]
    at=name in ("at","before","nested")
    return {"#calls":len(ids),"#order":int("".join(map(str,ids)) or "0"),
            "#position":len(ids) if at else 0,"#rotation":len(ids) if at else 0,
            "#after":1,"#callback_seen":0,"hits":[int(i in ids) for i in range(1,4)]}

def run(mode):
    proc,client,log=base.start(mode)
    r={"mode":mode,"status":"started","cases":{},"layouts":{}}
    enabled=mode in MODES[2:]
    def metrics():
        reply=client.command("functioncompiler ir008")
        return {k:stat(reply,k) for k in KEYS}
    try:
        establish(client)
        for name,n,gate in SCENARIOS:
            for quota in QUOTAS:
                reset(client,n,gate)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                invoke(client,name,quota)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                state=snapshot(client)
                r["cases"][f"{name}/{n}/{gate}/{quota}"]=state
                want=expected(name,n,gate)
                if quota==65536 and want is not None and state!=want:
                    raise AssertionError(f"{mode}/{name}/{n}/{gate}: {state} != {want}")
        for limit in (1,2,3,4):
            reset(client,3,1)
            client.command(f"gamerule minecraft:max_command_forks {limit}")
            assert re.search(rf"\b{limit}\b",client.command("gamerule minecraft:max_command_forks"))
            invoke(client,"at",positioned=limit!=1)
            client.command("gamerule minecraft:max_command_forks 65536")
            r["cases"][f"fork/{limit}"]=snapshot(client)
            assert r["cases"][f"fork/{limit}"]["#calls"]==(3 if limit==4 else 0)
        reset(client,1,1)
        before=metrics() if enabled else {}
        reply=client.command("debug function fc_ir:"+P+"at")
        assert "trace" in reply.lower(),reply
        r["trace_reply"]=reply
        r["cases"]["trace"]=snapshot(client)
        if enabled: assert metrics()["ir048_fallbacks"]>before["ir048_fallbacks"],"trace fallback not reached"
        reset(client,1,1)
        before=metrics() if enabled else {}
        reply=client.command("fc_ir048_callback")
        assert "IR048 callback queued" in reply,reply
        r["cases"]["callback"]=snapshot(client)
        if enabled: assert metrics()["ir048_fallbacks"]>before["ir048_fallbacks"],"callback fallback not reached"
        if mode!="native":
            for name in ROOTS:
                ledger=client.command("functioncompiler ir016 fc_ir:"+name)
                want=int(enabled and not name.endswith("_opaque"))
                assert stat(ledger,"typed_context_calls")==want,ledger
                if want: assert "direct_candidate=false" in ledger and "H1:1" in ledger,ledger
                r["layouts"][name]=ledger
            d=metrics()
            r["counts"]=d
            if enabled:
                for k in KEYS:
                    if k!="ir048_errors": assert d[k]>0,(k,d)
                assert d["ir048_entered"]==sum(d[k] for k in ("ir048_empty","ir048_single","ir048_multi","ir048_fallbacks","ir048_limit_errors")),d
            else: assert not any(d.values()),d
        r["status"]="accepted"
        print("IR048_NATIVE_ARM "+json.dumps({"mode":mode,"cases":len(r["cases"]),"counts":r.get("counts"),"layouts":r["layouts"]}),flush=True)
        return r
    finally:
        base.stop(proc,client,log)
        (OUT/f"{mode}.json").write_text(json.dumps(r,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS=ROOTS|CHILDREN
    base.options=options
    r={"status":"started","arms":[],"production_promotion":False}
    try:
        for mode in MODES:
            arm=run(mode)
            r["arms"].append(arm)
            ref=r["arms"][0]["cases"]
            if arm["cases"]!=ref:
                mismatch={k:{"native":v,"actual":arm["cases"].get(k)} for k,v in ref.items() if v!=arm["cases"].get(k)}
                raise AssertionError("native parity mismatch "+repr(list(mismatch.items())[:5]))
        r.update(status="accepted",native_semantic_parity=True,cases_per_arm=len(r["arms"][0]["cases"]))
        print("IR048_NATIVE_SUMMARY "+json.dumps({"status":r["status"],"cases_per_arm":r["cases_per_arm"]}),flush=True)
    except BaseException as error:
        r.update(status="invalid",error=repr(error))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
if __name__=="__main__": main()
