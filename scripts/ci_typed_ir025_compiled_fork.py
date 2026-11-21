#!/usr/bin/env python3
"""IR-025: compiled native-selector fork execution versus exact Minecraft 26.3.

Three fresh JVMs: original native; IR024 plan recognized but native action;
IR025 actual ASM-generated fork action. Every mode runs SAME original
mcfunction source and native EntitySelector; no index, persistent membership
cache, cross-command score cache or custom continuation/terminal task.

This extends IR024's accepted headless server fixture with 0/1/2/>2-source,
mixed-score, nearest-limit, absent-objective and quota-truncated scenarios.
Full fake-holder scoreboard snapshots must agree for every mode/fixture/quota.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import ci_typed_ir024_fork_plan as base
import ci_typed_ir014 as callbacks
from ci_typed_ir013 import stop, stat
from ci_typed_ir017 import nullable_score
from ci_smoke_server import ROOT

OUT=ROOT/"build/reports/COMPILER-IR-025-NATIVE"
MODES=("native","plan_only","compiled")
QUOTAS=(1,2,3,4,5,6,8,12,16,20,30,64,130,1023,1024)
# A source-only native comparison; fixture functions are never rewritten.
SELECT=base.SELECT
ALL=base.ALL
HOT=base.HOT
SORTED=(
    "@e[type=minecraft:marker,tag=fc024.fixture,tag=erb.block,"
    "tag=!erb.verified,sort=nearest,limit=1]"
)
ADDED={
    "no_candidate": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #empty fc024 0",
        HOT("empty"),
        "scoreboard players add #steps fc024 1",
    ],
    "multi_four": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #multi fc024 0",
        "scoreboard players set #steps fc024 0",
        *[
            f'summon minecraft:marker {x} 64 0 {{Tags:["fc024.fixture","erb.block"]}}'
            for x in (0,1,2,3)
        ],
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        HOT("multi"),
        "scoreboard players add #steps fc024 5",
    ],
    "partial": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #partial fc024 0",
        "scoreboard players set #steps fc024 0",
        *[
            f'summon minecraft:marker {x} 64 0 {{Tags:["fc024.fixture","erb.block"]}}'
            for x in (0,1,2,3)
        ],
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        *[
            "execute positioned %s 64 0 run scoreboard players set "
            "@e[type=minecraft:marker,tag=fc024.fixture,sort=nearest,limit=1] fc024 8"%x
            for x in (2,3)
        ],
        HOT("partial"),
        "scoreboard players add #steps fc024 3",
    ],
    # sorted limit 1 MUST apply before the per-entity score guard: the
    # nearest entity fails even though another matching candidate passes.
    "sorted_first_fails": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #sorted fc024 0",
        'summon minecraft:marker 0 64 0 {Tags:["fc024.fixture","erb.block"]}',
        'summon minecraft:marker 4 64 0 {Tags:["fc024.fixture","erb.block"]}',
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        "execute positioned 0 64 0 run scoreboard players set "
        "@e[type=minecraft:marker,tag=fc024.fixture,sort=nearest,limit=1] fc024 8",
        f"execute as {SORTED} if score @s fc024 = #active fc024 "
        "run scoreboard players set #sorted fc024 1",
        "scoreboard players add #steps fc024 2",
    ],
    "missing_guard_objective": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #missing fc024 0",
        'summon minecraft:marker 0 64 0 {Tags:["fc024.fixture","erb.block"]}',
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        f"execute as {SELECT} if score @s fc_absent = #active fc024 "
        "run scoreboard players set #missing fc024 1",
        "scoreboard players add #steps fc024 1",
    ],
    # The original ScoreboardQueueInjectionMixin observes the native
    # terminal scoreboard write and queues two original Minecraft child
    # function calls, one nested inside the other. Comparing the following
    # scoreboard read proves native depth-first callback/continuation order.
    "reentrant_callback": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #steps fc024 0",
        'summon minecraft:marker 0 64 0 {Tags:["fc024.fixture","erb.block"]}',
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        f"execute as {SELECT} if score @s fc024 = #active fc024 "
        "run scoreboard players set #ir014_chain fc_ir 1",
        "scoreboard players operation #observed fc_ir = #ir014_marker fc_ir",
        "scoreboard players add #steps fc024 1",
    ],
    "missing_terminal_objective": [
        "scoreboard players set #active fc024 7",
        "scoreboard players set #missing fc024 0",
        'summon minecraft:marker 0 64 0 {Tags:["fc024.fixture","erb.block"]}',
        f"execute as {ALL} run scoreboard players set @s fc024 7",
        f"execute as {SELECT} if score @s fc024 = #active fc024 "
        "run scoreboard players set #missing fc_absent 1",
        "scoreboard players add #steps fc024 1",
    ],
}
ALL_SCORES=base.SCORES+(
    "#empty","#multi","#partial","#sorted","#missing"
)
EXPECTED={
    **base.EXPECTED,
    "no_candidate":{"#empty":0,"#steps":1},
    "multi_four":{"#multi":1,"#steps":5},
    "partial":{"#partial":1,"#steps":3},
    "sorted_first_fails":{"#sorted":0,"#steps":2},
    "missing_guard_objective":{"#missing":0,"#steps":1},
    "missing_terminal_objective":{"#missing":0,"#steps":1},
    "reentrant_callback":{"#steps":1,"#observed_fc_ir":11,
                          "#marker_fc_ir":11,"#inner_fc_ir":9},
}
CASES=tuple(EXPECTED)
BASE_OPTIONS=base.options
BASE_FIXTURE=base.fixture
BASE_START=base.start

def fixture(work):
    BASE_FIXTURE(work)
    injected=work/"world/datapacks"/base.PACK/"data/fc_ir/function"
    injected.mkdir(parents=True,exist_ok=True)
    for name in ("ir014_inject_first","ir014_inject_second"):
        (injected/(name+".mcfunction")).write_text(
            "\\n".join(callbacks.FUNCTIONS[name])+"\\n",encoding="utf-8")

def start(mode):
    process,client,log=BASE_START(mode)
    answer=client.command("scoreboard objectives add fc_ir dummy")
    return process,client,log

def options(mode):
    if mode not in MODES:raise ValueError("Invalid IR025 execution mode")
    original=BASE_OPTIONS("native" if mode=="native" else "fork_plan")
    return {
        **original,
        "FC_TYPED_IR_COMPILED_FORK":str(mode=="compiled").lower(),
        "FC_TYPED_IR_NATIVE_FORK_PLAN":str(mode!="native").lower(),
        "FC_TYPED_IR_DIAGNOSTICS":str(mode!="native").lower(),
        "FC_TYPED_IR_REENTRANT_SAFE":"true",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"true",
        "FC_TYPED_IR_SCORE_CACHE":"false",
        "FC_TYPED_IR_DIRECT_FUNCTION":"false",
        "FC_IR023_VISIBILITY_HARNESS":"false",
    }

def configure_base():
    base.OUT=OUT
    base.options=options
    base.fixture=fixture
    base.start=start
    base.FUNCTIONS={**base.FUNCTIONS,**ADDED}
    base.SCORES=ALL_SCORES
    base.EXPECTED=EXPECTED

def snapshot(client):
    return {holder:nullable_score(client,holder,"fc024") for holder in ALL_SCORES} | {
        "#observed_fc_ir":nullable_score(client,"#observed","fc_ir"),
        "#marker_fc_ir":nullable_score(client,"#ir014_marker","fc_ir"),
        "#inner_fc_ir":nullable_score(client,"#ir014_inner_seen","fc_ir"),
    }

def reset(client):
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    client.command(f"kill {ALL}")
    client.command("scoreboard objectives remove fc_absent")
    for holder in ALL_SCORES:
        client.command(f"scoreboard players set {holder} fc024 0")
    for watched in ("#ir014_chain","#ir014_second"):
        # Reset rather than assigning zero: a score change here would enqueue
        # a callback before the function under test had even started.
        client.command(f"scoreboard players reset {watched} fc_ir")
    for holder in ("#ir014_marker","#ir014_inner_seen","#observed"):
        client.command(f"scoreboard players set {holder} fc_ir 0")

def run_arm(mode):
    process,client,log=base.start(mode)
    report={
        "mode":mode,"status":"started","snapshots":{},
        "native_live_selector":True,"score_cache":False,
        "persistent_index":False,"original_terminal":True,
        "native_continuation":True,"speedup_claim":False
    }
    try:
        for case in CASES:
            for quota in (65536,*QUOTAS):
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                result=client.command(f"function fc_ir024:{case}")
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                if "Running function" not in result:
                    raise AssertionError(
                        f"Original fixture function unavailable {mode}/{case}: {result!r}")
                data=snapshot(client)
                report["snapshots"][f"{case}@{quota}"]=data
                if quota==65536:
                    for holder,value in EXPECTED[case].items():
                        if data[holder]!=value:
                            raise AssertionError(
                                f"Native expected state {mode}/{case}/{holder}: "
                                f"{data[holder]} != {value}")
        if mode!="native":
            for name in ("plan_case","near_miss","multi_four",
                         "partial","sorted_first_fails","missing_guard_objective"):
                ledger=client.command(f"functioncompiler ir016 fc_ir024:{name}")
                if not ledger.startswith("IR016 function="):
                    raise AssertionError("Missing IR016 compiler ledger "+ledger)
                expected=3 if name=="plan_case" else 0 if name=="near_miss" else 1
                found=re.search(r"native_fork_plans=(\d+)",ledger)
                if not found or int(found.group(1))!=expected:
                    raise AssertionError(
                        f"IR025 incorrect native fork admission {mode}/{name}: {ledger}")
                compiled=re.search(r"compiled_forks=(\d+)",ledger)
                should_compile=expected if mode=="compiled" else 0
                if not compiled or int(compiled.group(1))!=should_compile:
                    raise AssertionError(
                        f"IR025 compiled fork source span mismatch {mode}/{name}: {ledger}")
                if mode=="compiled" and expected:
                    if name=="plan_case" and not all(x in ledger for x in (
                            "C8:1","C11:1","C13:1")):
                        raise AssertionError("Compiled fork changed source indices "+ledger)
                if mode=="plan_only" and name=="plan_case" and "N8:1" not in ledger:
                    raise AssertionError("Plan-only original native fork not retained "+ledger)
                if "direct_candidate=true" in ledger:
                    raise AssertionError("Wrongly admitted fork to direct scheduler")
                report.setdefault("ledgers",{})[name]=ledger
            diag=client.command("functioncompiler ir025")
            report["compiler_fork_diagnostic"]=diag
            if not diag.startswith("IR025 enabled="):
                raise AssertionError(f"Missing IR025 diagnostic: {diag!r}")
            if mode=="compiled":
                for metric in ("compiled_forks","executed_forks","selector_scans",
                               "selected_sources","passing_sources",
                               "continuation_schedules","native_fallbacks"):
                    if stat(diag,metric)<=0:
                        raise AssertionError(f"Compiled native fork path not reached at {metric}: {diag}")
            if mode=="plan_only" and stat(diag,"executed_forks")!=0:
                raise AssertionError("Original plan-only arm accidentally ran compiled fork")
            report["jvm_diagnostic"]=client.command("functioncompiler ir008")
        report["status"]="accepted_arm"
        print("IR025_ARM "+json.dumps({
            "mode":mode,"snapshots":len(report["snapshots"]),
            "compiled_selector_execution":mode=="compiled",
            "compiler_fork_diagnostic":report.get("compiler_fork_diagnostic","off"),
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
    configure_base()
    report={
        "milestone":"COMPILER-IR-025","status":"started",
        "arms":{},"native_selector_preserved":True,
        "native_terminal_and_continuation_preserved":True,
        "global_entity_index":False,"production_promotion":False,
        "causal_cpu_gain":False
    }
    try:
        for mode in MODES:
            report["arms"][mode]=run_arm(mode)
            (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
        reference=report["arms"]["native"]["snapshots"]
        for mode in MODES[1:]:
            observed=report["arms"][mode]["snapshots"]
            if reference!=observed:
                mismatch={case:{"native":reference[case],"observed":observed.get(case)}
                          for case in reference if reference[case]!=observed.get(case)}
                raise AssertionError(
                    f"Native original vs {mode} divergence: "
                    +json.dumps(dict(list(mismatch.items())[:4])))
        report["status"]="accepted_compiled_native_selector_fork_parity"
        report["native_semantic_parity"]=True
        report["snapshots_per_arm"]=len(reference)
        print("IR025_SUMMARY "+json.dumps({
            "status":report["status"],"modes":MODES,
            "snapshots_per_arm":len(reference),
            "compiled_fork_execution_proven":True,
            "global_entity_index":False,"causal_cpu_gain":False,
            "native_semantic_parity":True
        },sort_keys=True),flush=True)
    except BaseException as exc:
        report["status"]="invalid";report["error"]=repr(exc)
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":
    main()
