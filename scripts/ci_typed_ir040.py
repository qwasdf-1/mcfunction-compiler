#!/usr/bin/env python3
"""IR-040: actual native differential for predicate dataflow and arithmetic."""
from __future__ import annotations
import json
import ci_typed_ir017 as base
import ci_typed_ir038 as ir038
import ci_typed_ir039 as ir039

OUT = base.ROOT / "build/reports/COMPILER-IR-040"
ARMS = ("native", "old_bytecode", "interpreted", "bytecode", "direct")
QUOTAS = (*range(1, 41), 48, 64)
NEW = {
    "ir017_ir040_ranges": [
        "scoreboard players set #g fc_ir 7",
        "execute if score #g fc_ir matches 5.. if score #g fc_ir matches 1.. run scoreboard players add #x fc_ir 1",
        "execute if score #g fc_ir matches 5..8 if score #g fc_ir matches 6..10 if score #g fc_ir matches 6..8 run scoreboard players add #x fc_ir 2",
        "execute if score #g fc_ir matches 5..8 unless score #g fc_ir matches 6..10 if score #g fc_ir matches 7 run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 5.. unless score #g fc_ir matches ..4 run scoreboard players add #x fc_ir 4",
        "execute if score #g fc_ir matches 5.. if score #g fc_ir matches ..4 run scoreboard players add #x fc_ir 100",
        "scoreboard players set #g fc_ir -2147483648",
        "execute if score #g fc_ir matches ..-2147483648 if score #g fc_ir matches -2147483648 run scoreboard players add #x fc_ir 8",
        "scoreboard players set #g fc_ir 2147483647",
        "execute if score #g fc_ir matches 2147483647.. unless score #g fc_ir matches ..2147483646 run scoreboard players add #x fc_ir 16",
    ],
    "ir017_ir040_relations": [
        "scoreboard players set #g fc_ir 7",
        "scoreboard players set #y fc_ir 9",
        "execute if score #g fc_ir < #y fc_ir if score #y fc_ir > #g fc_ir if score #g fc_ir <= #y fc_ir run scoreboard players add #x fc_ir 1",
        "execute if score #g fc_ir < #y fc_ir if score #y fc_ir <= #g fc_ir run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir < #y fc_ir if score #g fc_ir matches 5.. unless score #g fc_ir matches ..3 run scoreboard players add #x fc_ir 2",
        "execute if score #g fc_ir matches 1.. if score #y fc_ir matches 1.. if score #g fc_ir < #y fc_ir run scoreboard players add #x fc_ir 4",
        "execute if score #g fc_ir = #g fc_ir if score #g fc_ir <= #g fc_ir run scoreboard players add #x fc_ir 8",
        "scoreboard players set #y fc_ir 7",
        "execute if score #g fc_ir <= #y fc_ir if score #y fc_ir <= #g fc_ir if score #g fc_ir = #y fc_ir run scoreboard players add #x fc_ir 16",
    ],
    "ir017_ir040_absence": [
        "scoreboard players set #g fc_ir 7",
        "execute unless score #never fc_guard matches 0 unless score #never fc_guard matches 0.. run scoreboard players add #x fc_ir 1",
        "execute unless score #never fc_guard matches -2147483648..2147483647 unless score #never fc_guard = #never fc_guard run scoreboard players add #x fc_ir 2",
        "execute unless score #never fc_guard = #g fc_ir unless score #g fc_ir = #never fc_guard run scoreboard players add #x fc_ir 4",
        "execute unless score #never fc_guard matches 0 if score #never fc_guard matches ..-1 run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 5.. if score #g fc_ir > #never fc_guard run scoreboard players add #x fc_ir 100",
    ],
    "ir017_ir040_self": [
        "scoreboard players set @s fc_ir 7",
        "scoreboard players set #g fc_ir 9",
        "execute if score @s fc_ir matches 5.. if score @s fc_ir matches 1.. if score #g fc_ir > @s fc_ir if score @s fc_ir < #g fc_ir run scoreboard players add #x fc_ir 1",
        "execute if score @s fc_ir matches 5.. if score @s fc_ir < #g fc_ir run scoreboard players add #x fc_ir 2",
        "scoreboard players set @s fc_ir 3",
        "execute if score @s fc_ir matches 5.. if score @s fc_ir matches 1.. run scoreboard players add #x fc_ir 100",
        "execute if score @s fc_ir = @s fc_ir if score @s fc_ir matches 3 run scoreboard players operation #x fc_ir += @s fc_ir",
    ],
    "ir017_ir040_arithmetic": [
        "scoreboard players set #x fc_ir -7",
        "scoreboard players set #g fc_ir 3",
        "scoreboard players operation #x fc_ir /= #g fc_ir",
        "scoreboard players operation #result fc_ir = #x fc_ir",
        "scoreboard players set #x fc_ir -7",
        "scoreboard players operation #x fc_ir %= #g fc_ir",
        "scoreboard players operation #x fc_ir >< #g fc_ir",
        "scoreboard players operation #x fc_ir >< #x fc_ir",
        "scoreboard players set #y fc_ir -3",
        "scoreboard players operation #g fc_ir /= #y fc_ir",
        "scoreboard players operation #g fc_ir %= #y fc_ir",
        "scoreboard players set #x fc_ir -2147483648",
        "scoreboard players set #y fc_ir -1",
        "scoreboard players operation #x fc_ir /= #y fc_ir",
    ],
    "ir017_ir040_zero": [
        "scoreboard players set #x fc_ir 12",
        "scoreboard players set #g fc_ir 0",
        "scoreboard players operation #x fc_ir /= #g fc_ir",
        "scoreboard players operation #x fc_ir %= #g fc_ir",
        "scoreboard players operation #x fc_ir /= #never fc_guard",
        "scoreboard players operation #x fc_ir >< #y fc_source",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir040_compound_arithmetic": [
        "scoreboard players set #x fc_ir -7",
        "scoreboard players set #g fc_ir 3",
        "execute if score #g fc_ir matches 3 if score #g fc_ir matches 1.. run scoreboard players operation #x fc_ir /= #g fc_ir",
        "execute if score #g fc_ir matches 3 if score #g fc_ir matches 1.. run scoreboard players operation #x fc_ir %= #g fc_ir",
        "execute if score #g fc_ir matches 3 if score #g fc_ir matches 1.. run scoreboard players operation #x fc_ir >< #g fc_ir",
        "execute if score #x fc_ir matches 3 if score #x fc_ir matches 1.. run scoreboard players operation #x fc_ir /= #g fc_ir",
        "execute if score #x fc_ir matches 0 if score #x fc_ir matches 1.. run scoreboard players operation #x fc_ir %= #g fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir040_self_arithmetic": [
        "scoreboard players set @s fc_ir -7",
        "scoreboard players set #g fc_ir 3",
        "scoreboard players operation @s fc_ir /= #g fc_ir",
        "scoreboard players operation @s fc_ir %= #g fc_ir",
        "scoreboard players operation @s fc_ir >< #g fc_ir",
        "execute if score @s fc_ir matches 3 if score @s fc_ir matches 1.. run scoreboard players operation @s fc_ir >< @s fc_ir",
        "scoreboard players operation #x fc_ir = @s fc_ir",
    ],
    "ir017_ir040_swap_reentrant": [
        "scoreboard players set #g fc_ir 1",
        "scoreboard players operation #ir014_chain fc_ir >< #g fc_ir",
        "execute if score #ir014_marker fc_ir matches 11 if score #ir014_marker fc_ir matches 1.. run scoreboard players add #x fc_ir 1",
        "scoreboard players operation #x fc_ir += #ir014_marker fc_ir",
    ],
}
SELF = {"ir017_ir040_self", "ir017_ir040_self_arithmetic", *ir039.SELF}
EXPECTED = {
    "ir017_ir040_ranges": {"x":31},
    "ir017_ir040_relations": {"x":31},
    "ir017_ir040_absence": {"x":7,"never_score":None},
    "ir017_ir040_self": {"x":6},
    "ir017_ir040_arithmetic": {"x":-2147483648,"result":-3},
    "ir017_ir040_zero": {"x":2,"operand_score":12,"never_score":0},
    "ir017_ir040_compound_arithmetic": {"x":4,"g":0},
    "ir017_ir040_self_arithmetic": {"x":3,"g":0},
}
# Include the full accepted IR039 corpus and inherited IR038 fixtures.
CASES = (*NEW, *ir039.CASES)
def options(mode):
    flags = ir039.options(mode)
    flags.update({
        "FC_TYPED_IR_COMPOUND_SCORE": str(mode != "native").lower(),
        "FC_TYPED_IR_DATAFLOW": str(mode in ARMS[2:]).lower(),
        "FC_TYPED_IR_ARITHMETIC": str(mode in ARMS[2:]).lower(),
        "FC_TYPED_IR040_BENCHMARK": "false",
    })
    return flags

def run_arm(mode):
    process, client, log = base.start(mode)
    report = {"mode":mode,"cases":{},"layouts":{},"status":"started"}
    try:
        client.command("forceload add 0 0")
        client.command("setblock 0 63 0 minecraft:stone")
        for name in CASES:
            for as_entity in ((True, False) if name in SELF else (False,)):
                for quota in (65536,*QUOTAS):
                    base.reset(client)
                    client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                    ir039.invoke(client,name,as_entity)
                    client.command("gamerule minecraft:max_command_sequence_length 65536")
                    state=base.snapshot(client)
                    report["cases"][f"{name}/{as_entity}/{quota}"]=state
                    if quota==65536 and (name not in SELF or as_entity):
                        for key,value in EXPECTED.get(name,{}).items():
                            if state[key]!=value:
                                raise AssertionError(f"{mode}/{name}/{key}: {state[key]} != {value}")
                    if name=="ir017_ir039_order" and quota==12 and state["x"]!=3:
                        raise AssertionError("IR039 quota regression")
        if mode!="native":
            for name in NEW:
                layout=base.inspect(client,name)
                report["layouts"][name]=layout
                if mode in ARMS[2:] and layout["typed_lines"]!=len(NEW[name]):
                    raise AssertionError(f"{mode}: incomplete lowering: {name}/{layout}")
            if mode=="old_bytecode" and report["layouts"]["ir017_ir040_arithmetic"]["typed_lines"]==len(NEW["ir017_ir040_arithmetic"]):
                raise AssertionError("arithmetic disabled but fully lowered")
            status=client.command("functioncompiler ir008")
            report["diagnostic"]=status
            for key in ("ir040_proofs","ir040_operand_reads_reused","ir040_arithmetic_steps","ir040_arithmetic_errors"):
                if (ir038.stat(status,key)>0)!=(mode in ARMS[2:]):
                    raise AssertionError(f"{mode}: unexpected {key}: {status}")
            if mode in ("bytecode","direct") and ir038.stat(status,"bytecode_regions")<=0:
                raise AssertionError("no actual JVM bytecode")
        report["status"]="accepted"
        print("IR040_ARM "+json.dumps({"mode":mode,"cases":len(report["cases"]),
            "diagnostic":report.get("diagnostic"),"layouts":report["layouts"]}),flush=True)
        return report
    except BaseException as e:
        report.update(status="failed",error=repr(e))
        raise
    finally:
        base.stop(process,client,log)
        (OUT/f"{mode}.json").write_text(json.dumps(report,indent=2)+"\n")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS={**base.FUNCTIONS,**ir038.NEW,**ir039.NEW,**NEW}
    base.options=options
    report={"status":"started","arms":[],"performance_claim":False}
    try:
        for mode in ARMS:
            arm=run_arm(mode)
            report["arms"].append(arm)
            oracle=report["arms"][0]["cases"]
            arm["differences"]={k:{"native":v,"actual":arm["cases"].get(k)}
                                for k,v in oracle.items() if arm["cases"].get(k)!=v}
        failures={a["mode"]:len(a["differences"]) for a in report["arms"] if a["differences"]}
        if failures:
            raise AssertionError(f"native parity differences: {failures}")
        report.update(status="accepted",native_semantic_parity=True,cases_per_arm=len(report["arms"][0]["cases"]))
    except BaseException as e:
        report.update(status="invalid",error=repr(e))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    print("IR040_SUMMARY "+json.dumps({k:report[k] for k in ("status","native_semantic_parity","cases_per_arm","performance_claim")}),flush=True)

if __name__=="__main__":
    main()
