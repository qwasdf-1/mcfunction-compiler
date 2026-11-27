#!/usr/bin/env python3
"""IR046: actual native execution of effect-bounded guard runs."""
from __future__ import annotations
import json,time,re
import ci_typed_ir017 as base
import ci_typed_ir040 as prior
from ci_typed_ir013 import stat
OUT=base.ROOT/"build/reports/COMPILER-IR-046"
MODES=("native","old_bytecode","interpreted","bytecode","direct")
QUOTAS=(65536,*range(1,26),32,48,64)
BOUNDS=((3,123),(6,925),(8,2109),(10,4169),(12,7153))
def guard(r,c,match,bound,value,ro="fc_ir",co="fc_ir"):
    return f"execute if score {r} {ro} matches {match} if score {c} {co} matches {bound} run scoreboard players set {c} {co} {value}"
def wrap(r="@s",c="@s",ro="fc_radius",co="fc_cursor"):
    return [line for radius,b in BOUNDS for line in
            (guard(r,c,radius,f"{b}..",0,ro,co),guard(r,c,radius,"..-1",b-1,ro,co))]
def adversary(cursor):
    r="#fc046_radius"
    return [guard(r,cursor,12,"7153..",0),
            guard(r,cursor,3,"123..",0),
            guard(r,cursor,6,"0",7),
            guard(r,cursor,6,"7",8)]
ROOTS={
    "ir017_ir046_wrap":wrap(),
    "ir017_ir046_change":adversary("#fc046_change"),
    "ir017_ir046_remove":adversary("#fc046_remove"),
    "ir017_ir046_queue":adversary("#fc046_queue"),
    "ir017_ir046_fake":wrap("#fc046_radius","#fc046_cursor","fc_ir","fc_ir"),
    "ir017_ir046_barrier":[*wrap("#fc046_radius","#fc046_cursor","fc_ir","fc_ir")[:2],
        "scoreboard players set #fc046_radius fc_ir 6",
        *wrap("#fc046_radius","#fc046_cursor","fc_ir","fc_ir")[2:4],
        "data modify storage fc_ir:ir046 dummy set value 1",
        "scoreboard players set #fc046_cursor fc_ir -1",
        *wrap("#fc046_radius","#fc046_cursor","fc_ir","fc_ir")[2:4]],
    "ir017_ir046_missing":[guard("#fc046_radius","#fc046_cursor",3,"0",9,"fc_ir","fc_absent"),
        guard("#fc046_radius","#fc046_cursor",6,"0",10,"fc_ir","fc_absent"),
        "scoreboard players add #x fc_ir 1"],
    "ir017_ir046_readonly":[guard("#fc046_radius","#fc046_cursor",3,"0",9,"fc_ir","fc_readonly"),
        guard("#fc046_radius","#fc046_cursor",6,"0",10,"fc_ir","fc_readonly"),
        "scoreboard players add #x fc_ir 1"],
    "ir017_ir046_injected":["scoreboard players set #fc046_radius fc_ir 6"],
}
# Explicit boundary/absence/overflow cases plus real synchronous and queued mutations.
SCENARIOS=[
    ("wrap",12,1,True),("wrap",3,122,True),("wrap",6,925,True),
    ("wrap",8,-1,True),("wrap",10,4169,True),("wrap",12,7153,True),
    ("wrap",3,-2147483648,True),("wrap",12,2147483647,True),
    ("wrap",None,0,True),("wrap",12,None,True),("wrap",13,0,True),
    ("wrap",None,None,False),("fake",3,-1,False),("fake",None,None,False),
    ("change",3,123,False),("remove",3,123,False),("queue",3,123,False),
    ("barrier",12,925,False),("missing",3,0,False),("readonly",3,0,False),
]
SELECTOR="@e[type=minecraft:armor_stand,tag=fc046_probe,limit=1]"
KEYS=("ir046_boundaries","ir046_present_reuse","ir046_absent_reuse",
      "ir046_invalidations","ir046_trace_fallbacks","ir046_fork_fallbacks","ir046_callback_fallbacks")
def options(mode):
    flags=prior.options(mode)
    flags.update({"FC_TYPED_IR_GUARD_RUN_REUSE":str(mode in MODES[2:]).lower(),
        "FC_TYPED_IR_DATAFLOW":str(mode!="native").lower(),
        "FC_TYPED_IR_ARITHMETIC":str(mode!="native").lower(),
        "FC_TYPED_IR046_TEST_OBSERVER":"true",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"true",
        "FC_TYPED_IR046_CALLBACK_HARNESS":"true",
        "FC_TYPED_IR_DIAGNOSTICS":"true"})
    return flags
def establish(client):
    client.command("forceload add 0 0")
    for name,criterion in (("fc_radius","dummy"),("fc_cursor","dummy"),("fc_readonly","health")):
        client.command(f"scoreboard objectives add {name} {criterion}")
    deadline=time.monotonic()+20
    while True:
        client.command("setblock 0 63 0 minecraft:stone")
        client.command("execute store success score #loaded fc_ir run execute if block 0 63 0 minecraft:stone")
        if base.nullable_score(client,"#loaded","fc_ir")==1:break
        if time.monotonic()>deadline:raise AssertionError("block unavailable")
        time.sleep(.1)
    client.command("kill "+SELECTOR)
    reply=client.command('summon minecraft:armor_stand 0 64 0 {Tags:["fc046_probe"],NoGravity:1b,Marker:1b}')
    deadline=time.monotonic()+10
    while True:
        client.command("scoreboard players set #loaded fc_ir 0")
        client.command(f"execute as {SELECTOR} run scoreboard players set #loaded fc_ir 1")
        if base.nullable_score(client,"#loaded","fc_ir")==1:break
        if time.monotonic()>deadline:raise AssertionError("entity unavailable "+reply)
        time.sleep(.1)
def set_score(client,holder,obj,value):
    client.command(f"scoreboard players reset {holder} {obj}" if value is None
                   else f"scoreboard players set {holder} {obj} {value}")
def reset(client,name,r,c,entity):
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    client.command("scoreboard objectives remove fc_absent")
    for h in ("#fc046_change","#fc046_remove","#fc046_queue","#fc046_cursor","#fc046_radius"):
        set_score(client,h,"fc_ir",None)
    if name in ("change","remove","queue"):set_score(client,"#fc046_"+name,"fc_ir",c)
    else:set_score(client,"#fc046_cursor","fc_ir",c)
    # The queue observer may fire during setup. Initialize radius after it.
    set_score(client,"#fc046_radius","fc_ir",r)
    set_score(client,SELECTOR,"fc_radius",r if entity else None)
    set_score(client,SELECTOR,"fc_cursor",c if entity else None)
    set_score(client,"#x","fc_ir",0)
    set_score(client,"#result","fc_ir",-999)
    set_score(client,"#fc046_callback_seen","fc_ir",0)
    client.command("data remove storage fc_ir:ir046 dummy")
def snapshot(client):
    out={h:base.nullable_score(client,h,"fc_ir") for h in
         ("#x","#result","#fc046_radius","#fc046_cursor","#fc046_change","#fc046_remove","#fc046_queue","#fc046_callback_seen")}
    out["radius"]=base.nullable_score(client,SELECTOR,"fc_radius")
    out["cursor"]=base.nullable_score(client,SELECTOR,"fc_cursor")
    out["storage"]=client.command("data get storage fc_ir:ir046 dummy")
    return out
def invoke(client,name,entity,quota=65536):
    prefix=f"execute as {SELECTOR} at @s run " if entity else ""
    reply=client.command(prefix+"fc_ir017_call fc_ir:ir017_ir046_"+name)
    # The two native source modifiers can exhaust quota before the ordinary
    # harness terminal is queued; blank feedback is expected at those cuts.
    # Retain strict invocation validation at every other quota.
    if entity and quota <= 2 and not reply.strip():return
    if "FC_ARCH_CALL queued" not in reply:raise AssertionError(
        f"invocation failed {name}/{entity}/{quota}: {reply!r}")
def run(mode):
    proc,client,log=base.start(mode)
    r={"mode":mode,"cases":{},"layouts":{},"status":"started"}
    try:
        establish(client)
        for i,(name,radius,cursor,entity) in enumerate(SCENARIOS):
            for quota in QUOTAS:
                reset(client,name,radius,cursor,entity)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                invoke(client,name,entity,quota)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                state=snapshot(client)
                r["cases"][f"{i}/{name}/{quota}"]=state
                if quota==65536:
                    if name in ("change","queue") and (state["#fc046_radius"],state["#fc046_"+name])!=(6,8):
                        raise AssertionError(f"{mode}/{name} observer not exercised {state}")
                    if name=="remove" and (state["#fc046_radius"],state["#fc046_remove"])!=(None,0):
                        raise AssertionError(f"{mode}/{name} observer not exercised {state}")
                    if name=="wrap" and entity:
                        bound=dict(BOUNDS).get(radius)
                        expected=cursor if bound is None or cursor is None else (0 if cursor>=bound else bound-1 if cursor<0 else cursor)
                        if state["cursor"]!=expected:raise AssertionError(f"{mode}/{i} wrap {state} != {expected}")
        # Positive native trace and restrictive fork-limit paths.
        reset(client,"fake",3,-1,False)
        debug=client.command("debug function fc_ir:ir017_ir046_fake")
        if "trace" not in debug.lower():raise AssertionError("trace unavailable "+debug)
        r["trace_reply"]=debug
        r["cases"]["trace"]=snapshot(client)
        reset(client,"fake",3,-1,False)
        reply=client.command("gamerule minecraft:max_command_forks 1")
        readback=client.command("gamerule minecraft:max_command_forks")
        if not re.search(r"\b1\b",readback) or "unknown" in readback.lower():
            raise AssertionError("fork limit unavailable "+reply+" / "+readback)
        invoke(client,"fake",False)
        client.command("gamerule minecraft:max_command_forks 65536")
        r["cases"]["fork"]=snapshot(client)
        reset(client,"fake",3,-1,False)
        answer=client.command("fc_ir046_callback")
        if "IR046 callback queued" not in answer:raise AssertionError("callback harness "+answer)
        r["cases"]["callback"]=snapshot(client)
        if mode!="native":
            for name in ROOTS:
                ledger=base.inspect(client,name) if name!="ir017_ir046_injected" else None
                if ledger is not None:r["layouts"][name]=ledger
            for name in ("wrap","change","remove","queue","fake"):
                k="ir017_ir046_"+name
                if r["layouts"][k]["typed_lines"]!=len(ROOTS[k]):
                    raise AssertionError("guard region not fully typed "+str(r["layouts"][k]))
            d=client.command("functioncompiler ir008")
            r["diagnostics"]=d
            r["counts"]={k:stat(d,k) for k in KEYS}
            for k in KEYS:
                if (r["counts"][k]>0)!=(mode in MODES[2:]):
                    raise AssertionError("IR046 path mismatch "+k+" "+d)
            if stat(d,"reentrant_yields")<=0:raise AssertionError("no reentrant queue yields")
        r["status"]="accepted"
        print("IR046_ARM "+json.dumps({"mode":mode,"cases":len(r["cases"]),"counts":r.get("counts"),"diagnostics":r.get("diagnostics")}),flush=True)
        return r
    finally:
        base.stop(proc,client,log)
        (OUT/f"{mode}.json").write_text(json.dumps(r,indent=2)+"\n")
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS=ROOTS
    base.options=options
    r={"status":"started","arms":[],"production_promotion":False}
    try:
        for mode in MODES:
            arm=run(mode)
            r["arms"].append(arm)
            if arm["cases"]!=r["arms"][0]["cases"]:
                diffs={k:{"native":v,"actual":arm["cases"].get(k)} for k,v in r["arms"][0]["cases"].items() if arm["cases"].get(k)!=v}
                raise AssertionError("native parity mismatch "+repr(list(diffs.items())[:5]))
        r.update(status="accepted",native_semantic_parity=True,cases_per_arm=len(r["arms"][0]["cases"]))
        print("IR046_SUMMARY "+json.dumps({k:r[k] for k in ("status","native_semantic_parity","cases_per_arm")}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
if __name__=="__main__":main()
