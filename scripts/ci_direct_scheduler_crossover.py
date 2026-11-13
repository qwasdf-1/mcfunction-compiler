#!/usr/bin/env python3
"""SCHED-ARCH-014: strict whole-function direct scheduling versus fused C.

Arm D bypasses CallFunction child-frame/continuation scheduling ONLY for a
whole literal ScoreAdd function with no control-flow, return, fork, source
callback or tracer. Each command still uses the exact fused C semantic bridge.
The remaining global ExecutionContext and all unsupported functions stay
vanilla. This is a bounded architecture proof, not a global replacement.

Phase diagnostic: direct activation and parity across quota, nested calls,
store callbacks and debug tracing. Phase timing: 12 independent Minecraft
server JVMs with C/C' placebo and C/D within-JVM balanced ABBA/BAAB, all runtime
execution/queue counters disabled, exact scoreboard validation every window.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import statistics
import subprocess
import time

import ci_scheduler_arch_attribution as parent
import ci_compiler_off_stability as stable
from ci_compiler_off_paired import exact_median_interval, cpu_run_delay, snapshot_host
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    stage_artifacts, setup_server_properties, server_tid, server_cpu_time_ns,
    read_score,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon

EXPERIMENT = "SCHED-ARCH-014"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
SEED = 14014
N_BOOTS = 12
PRIMARY_LENGTH = 2000
LENGTHS = (4, 16, 256, 2000)
PREWARM_PER_FUNCTION = 180
WINDOW_CALLS = 360
DIAGNOSTIC_CALLS = 40
DIRECT_NS = "fc_arch_direct"
C_NS = parent.NAMESPACES["fused"]
ALIAS_NS = "fc_arch_callers"
KIND_ARMS = {
    "negative": ("fused", "fused_null"),
    "direct_vs_fused": ("fused", "direct"),
}


def function_id(arm: str, length: int) -> str:
    if length not in LENGTHS:
        raise ValueError(length)
    if arm == "fused":
        return f"{C_NS}:score_{length}"
    if arm == "fused_null":
        return f"{C_NS}:score_null_{length}"
    if arm == "direct":
        return f"{DIRECT_NS}:score_{length}"
    raise ValueError(arm)


def make_pack(workdir: Path) -> None:
    parent.prepare_fixture(workdir)
    dp = workdir / "world" / "datapacks" / PACK / "data"
    for length in LENGTHS:
        source = (dp / C_NS / "function" / f"score_{length}.mcfunction").read_text()
        if len(source.splitlines()) != length:
            raise AssertionError("Source function length mismatch")
        for arm in ("fused_null", "direct"):
            target = dp / (DIRECT_NS if arm == "direct" else C_NS) / "function"
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{'score' if arm == 'direct' else 'score_null'}_{length}.mcfunction").write_text(source)
    # Parent functions: same literal work before/after call, only child ID
    # differs. A nested direct call must preserve normal call semantics.
    parent_dir = dp / ALIAS_NS / "function"
    parent_dir.mkdir(parents=True, exist_ok=True)
    for arm in ("fused", "direct"):
        (parent_dir / f"nested_{arm}.mcfunction").write_text(
            f"scoreboard players add {HOLDER} {OBJECTIVE} 1\n"
            f"function {function_id(arm,16)}\n"
            f"scoreboard players add {HOLDER} {OBJECTIVE} 1\n"
        )
    # Unsupported command => D must never be selected for this function.
    (dp / DIRECT_NS / "function" / "unsupported.mcfunction").write_text(
        f"scoreboard players add {HOLDER} {OBJECTIVE} 1\n"
        f"function {function_id('fused',4)}\n"
        f"scoreboard players add {HOLDER} {OBJECTIVE} 1\n"
    )


def plan() -> tuple[dict, ...]:
    rng = random.Random(SEED)
    kinds = tuple(KIND_ARMS)
    orders = rng.sample([kinds, kinds[::-1]] * (N_BOOTS//2), N_BOOTS)
    orientations = {
        kind: rng.sample(["ABBA","BAAB"] * (N_BOOTS//2), N_BOOTS)
        for kind in kinds
    }
    return tuple({
        "index": i,
        "blocks": [{
            "kind":kind,
            "orientation":orientations[kind][i],
            "arms":[KIND_ARMS[kind][0 if label=="A" else 1]
                    for label in orientations[kind][i]],
        } for kind in orders[i]]
    } for i in range(N_BOOTS))


def stat(response: str, key: str) -> int:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)(?:\s|$)", response)
    if not match:
        raise AssertionError(f"Missing {key}: {response!r}")
    return int(match.group(1))


def activation_gate(rcon: Rcon, diagnostics: bool) -> dict:
    all_stats = {}
    for length in LENGTHS:
        for arm in ("fused", "fused_null", "direct"):
            fid = function_id(arm,length)
            reply = rcon.command(f"functioncompiler stats {fid}")
            values = {
                key:stat(reply,key)
                for key in ("score_add_compiled","fused_regions_compiled",
                            "direct_scheduler_compiled","direct_scheduler_executed",
                            "direct_scheduler_fallbacks")
            }
            expected = {
                "score_add_compiled":length,
                "fused_regions_compiled":1,
                "direct_scheduler_compiled":int(arm=="direct"),
            }
            for key,want in expected.items():
                if values[key]!=want:
                    raise AssertionError(f"Wrong compiler activation for {fid}: {key} {values[key]} != {want}")
            if not diagnostics and values["direct_scheduler_executed"]!=0:
                raise AssertionError("Instrumentation leaked into timed arm")
            all_stats[fid]=values
    unsupported = rcon.command(f"functioncompiler stats {DIRECT_NS}:unsupported")
    if stat(unsupported,"direct_scheduler_compiled") != 0:
        raise AssertionError("Unsafe whole-function control-flow was optimized")
    return all_stats


def invoke(rcon: Rcon, arm: str, length: int) -> str:
    return rcon.command(f"fc_arch_call {function_id(arm,length)}")


def read_value(rcon: Rcon, holder: str = HOLDER) -> int:
    response = rcon.command(f"scoreboard players get {holder} {OBJECTIVE}")
    found = re.search(r"\bhas (-?\d+)\b", response)
    if found is None:
        raise AssertionError(f"Missing scoreboard value {holder}: {response}")
    return int(found.group(1))


def execute_and_verify(rcon: Rcon, arm: str, length: int, calls: int) -> dict:
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    for _ in range(calls):
        reply = invoke(rcon,arm,length)
        if not reply.startswith("FC_ARCH_CALL queued "):
            raise AssertionError(f"Function invocation rejected: {arm}/{length}: {reply!r}")
    value = read_score(rcon)
    expected = calls * length
    if value!=expected:
        raise AssertionError(f"Work parity failed {arm} len={length} {value} != {expected}")
    return {"arm":arm, "length":length, "calls":calls,
            "expected":expected,"observed":value,"exact_work":True}


# Minecraft Java 26.3 uses namespaced snake_case gamerules. The older
# maxCommandChainLength name is invalid and silently invalidated an earlier
# purported quota check. Never accept a quota sweep without command readback
# AND a demonstrated reduction in the completed source commands.
SEQUENCE_GAMERULE = "minecraft:max_command_sequence_length"


def read_sequence_quota(rcon: Rcon) -> tuple[int,str]:
    response=rcon.command(f"gamerule {SEQUENCE_GAMERULE}")
    if SEQUENCE_GAMERULE not in response and "max_command_sequence_length" not in response:
        raise AssertionError(f"Gamerule query did not identify the real rule: {response!r}")
    numbers=re.findall(r"-?\\d+",response)
    if not numbers:
        raise AssertionError(f"Expected numeric quota readback: {response!r}")
    return int(numbers[-1]),response


def set_verified_sequence_quota(rcon: Rcon, quota: int) -> dict:
    reply=rcon.command(f"gamerule {SEQUENCE_GAMERULE} {quota}")
    actual,readback=read_sequence_quota(rcon)
    if actual!=quota:
        raise AssertionError(
            f"Quota set/readback mismatch: wanted={quota}, got={actual}; "
            f"set_reply={reply!r}, query_reply={readback!r}")
    return {"requested":quota,"confirmed":actual,
            "set_response":reply,"readback_response":readback}


def quota_parity(rcon: Rcon) -> list[dict]:
    rows=[]
    low_quota_truncated=False
    # Quota 0 cannot support the diagnostic scoreboard read and reset RCON
    # commands. It remains part of the existing full vanilla parity suite.
    original,_=read_sequence_quota(rcon)
    try:
        for quota in (2,3,4,5,8,16,32,64,1024):
            verified=set_verified_sequence_quota(rcon,quota)
            observed={}
            for arm in ("fused","direct"):
                reset=rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
                reply=invoke(rcon,arm,16)
                observed[arm]=read_value(rcon)
                if not 0<=observed[arm]<=16:
                    raise AssertionError(f"Invalid quota-limited score for {arm}: {observed}")
            row={"quota":quota,"readback":verified,"scores":observed}
            if observed["fused"]!=observed["direct"]:
                raise AssertionError(f"Call quota changed semantics: {row}")
            if quota<=8 and observed["fused"]<16:
                low_quota_truncated=True
            if quota==1024 and observed["fused"]!=16:
                raise AssertionError(f"High quota unexpectedly truncated commands: {row}")
            rows.append(row)
        if not low_quota_truncated:
            raise AssertionError("Quota test is not exercising truncation; old gamerule or invalid fixture?")
        return rows
    finally:
        # Restore even when parity fails, preserving the diagnostic evidence.
        set_verified_sequence_quota(rcon,original)


def diagnostic_phase(rcon: Rcon) -> dict:
    evidence={"activation_before":activation_gate(rcon,True)}
    # The public /function command retains its nonempty result callback.
    # Confirm that our conservative fast path refuses that call site.
    name=function_id("direct",16)
    before_std=stat(rcon.command(f"functioncompiler stats {name}"),
                    "direct_scheduler_executed")
    evidence["ordinary_function_response"]=rcon.command(f"function {name}")
    after_std=stat(rcon.command(f"functioncompiler stats {name}"),
                   "direct_scheduler_executed")
    evidence["ordinary_function_direct_executed_delta"]=after_std-before_std
    if after_std!=before_std:
        raise AssertionError("Direct fast path unexpectedly bypassed public /function callbacks")
    for length in LENGTHS:
        for arm in ("fused","fused_null","direct"):
            execute_and_verify(rcon,arm,length,DIAGNOSTIC_CALLS)
    evidence["activation_after"]=activation_gate(rcon,True)
    total_direct=sum(
        evidence["activation_after"][function_id("direct",length)]["direct_scheduler_executed"]
        for length in LENGTHS
    )
    if total_direct<=0:
        raise AssertionError(
            "No direct function executed: callbacks or call-site flags require fallback. "
            "The D/C timing campaign is not eligible.")
    evidence["direct_executions"]=total_direct
    evidence["quota_parity"]=quota_parity(rcon)
    nested={}
    for arm in ("fused","direct"):
        rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        nested[arm]=rcon.command(f"function {ALIAS_NS}:nested_{arm}")
        nested[arm]={"response":nested[arm],"score":read_score(rcon)}
    if nested["fused"]["score"]!=18 or nested["direct"]["score"]!=18:
        raise AssertionError(f"Nested frame semantics broken: {nested}")
    evidence["nested_parity"]=nested
    # A function containing vanilla scheduler control flow must not compile
    # into D, even if two surrounding commands are typed.
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    evidence["unsupported_response"]=rcon.command(f"function {DIRECT_NS}:unsupported")
    if read_score(rcon)!=6:
        raise AssertionError("Unsupported function fallback changed behavior")
    evidence["unsupported_work"] = 6
    # Named command trace must pass through the original CallFunction path.
    # The fallback count increments only with the separate diagnostic flag.
    before=stat(
        rcon.command(f"functioncompiler stats {function_id('direct',16)}"),
        "direct_scheduler_fallbacks")
    evidence["debug_reply"]=rcon.command(f"debug function {function_id('direct',16)}")
    after=stat(
        rcon.command(f"functioncompiler stats {function_id('direct',16)}"),
        "direct_scheduler_fallbacks")
    evidence["trace_fallback_delta"]=after-before
    if evidence["trace_fallback_delta"]<=0:
        raise AssertionError("Trace did not force safe vanilla-frame fallback")
    evidence["status"]="passed"
    return evidence


def measure_window(rcon: Rcon,pid: int,tid: int, arm: str) -> dict:
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    cpu0,clock=server_cpu_time_ns(pid,tid)
    delay0=cpu_run_delay(pid,tid)
    host0=snapshot_host()
    wall0=time.perf_counter_ns()
    for _ in range(WINDOW_CALLS):
        reply=invoke(rcon,arm,PRIMARY_LENGTH)
        if not reply.startswith("FC_ARCH_CALL queued "):
            raise AssertionError(f"Timed invocation failed {arm}: {reply!r}")
    wall_ns=time.perf_counter_ns()-wall0
    host1=snapshot_host()
    delay1=cpu_run_delay(pid,tid)
    cpu1,clock1=server_cpu_time_ns(pid,tid)
    if clock!=clock1 or cpu1<=cpu0:
        raise AssertionError("Server-thread CPU clock did not advance consistently")
    measured=read_score(rcon)
    expected=PRIMARY_LENGTH*WINDOW_CALLS
    if measured!=expected:
        raise AssertionError(f"Wrong scoreboard work: {arm} observed {measured} expected {expected}")
    cpu_ns=cpu1-cpu0
    blocked_ns=max(0,delay1-delay0) if delay0 is not None and delay1 is not None else None
    c0,c1=host0.get("cgroup_cpu_stat",{}),host1.get("cgroup_cpu_stat",{})
    throttled=(c1["nr_throttled"]-c0["nr_throttled"]
               if "nr_throttled" in c0 and "nr_throttled" in c1 else None)
    return {
        "arm":arm,"calls":WINDOW_CALLS,"original_commands":expected,
        "cpu_ns_per_command":cpu_ns/expected,"server_thread_cpu_ns":cpu_ns,
        "cpu_clock":clock,"wall_seconds":wall_ns/1e9,
        "cgroup_nr_throttled_delta":throttled,
        "runqueue_delay_fraction":(
            blocked_ns/(blocked_ns+cpu_ns) if blocked_ns is not None else None),
        "final_score":measured,"expected_score":expected,"exact_work":True,
    }


def run_boot(index: int, artifacts: dict, diagnostic: bool,
             assignment: dict | None = None) -> dict:
    work=RUN_ROOT/f"ci-arch014-{'diag' if diagnostic else 'timing'}-{index:02d}"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(FABRIC_BASE,work)
    mods=work/"mods"
    mods.mkdir(exist_ok=True)
    for key in ("api","compiler"):
        p=Path(artifacts[key])
        shutil.copy2(p,mods/p.name)
    make_pack(work)
    port,rcon_port=unused_port(),unused_port()
    password=secrets.token_hex(20)
    setup_server_properties(work,port,rcon_port,password)
    env=dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE":"true",
        "FC_SCORE_ADD_PROTOTYPE":"true",
        "FC_FUSED_REGION_PROTOTYPE":"true",
        "FC_FUSED_REGION_ONLY_NAMESPACE":C_NS,
        "FC_DIRECT_SCHEDULER_PROTOTYPE":"true",
        "FC_DIRECT_SCHEDULER_HARNESS":"true",
        "FC_DIRECT_SCHEDULER_ONLY_NAMESPACE":DIRECT_NS,
        "FC_DIRECT_SCHEDULER_DIAGNOSTICS":str(diagnostic).lower(),
        "FC_SCORE_ADD_METRICS":"false","FC_SCORE_ADD_TIMING":"false",
        "FC_BYTECODE_REGION_PROTOTYPE":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS":"false",
        "FC_COMMAND_CALLBACK_METRICS":"false",
        "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES":"false",
        "FC_FUNCTION_TIMING":"false","FC_RUNTIME_TRACE":"false",
        "FC_SCHED_ARCH_COUNTERS":"false",
        "FC_SCHEDULER_RESEARCH":"false",
    })
    record={"boot":index,"diagnostic":diagnostic,"status":"started",
            "host_before":snapshot_host(),"blocks":[]}
    if assignment is not None:record["assignment"]=assignment
    logpath=OUT/f"boot-{'diag' if diagnostic else 'timing'}-{index:02d}.log"
    print(f"SCHED-ARCH-014 boot={index} diagnostic={diagnostic}",flush=True)
    with logpath.open("w",encoding="utf-8") as log:
        process=subprocess.Popen(
            ["java",*stable.JVM_ARGS,"-jar",str(work/"fabric-server-launch.jar"),"nogui"],
            cwd=work,env=env,stdin=subprocess.PIPE,
            stdout=log,stderr=subprocess.STDOUT)
        rcon=None
        try:
            rcon=wait_for_rcon(process,rcon_port,password,timeout_seconds=180)
            if PACK not in rcon.command("datapack list enabled"):
                raise AssertionError("Fixture not loaded")
            status=rcon.command("functioncompiler status")
            if not all(token in status for token in (
                "wrapped=true","score_add_prototype_enabled=true",
                "fused_region_prototype_enabled=true",
                "direct_scheduler_prototype_enabled=true",
                f"direct_scheduler_diagnostics_enabled={str(diagnostic).lower()}"
            )):
                raise AssertionError(f"Expected alternative scheduler flags missing: {status}")
            record["configuration"]=status
            record["activation"]=activation_gate(rcon,diagnostic)
            for command in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1",
            ):
                rcon.command(command)
            if diagnostic:
                record["parity"]=diagnostic_phase(rcon)
                record["status"]="complete"
            else:
                pid,tid=process.pid,server_tid(process.pid)
                record["qualification"]=stable.warmup_server(rcon,pid,tid)
                for arm in ("fused","fused_null","direct"):
                    execute_and_verify(rcon,arm,PRIMARY_LENGTH,PREWARM_PER_FUNCTION)
                for block in assignment["blocks"]:
                    windows=[measure_window(rcon,pid,tid,arm) for arm in block["arms"]]
                    record["blocks"].append({
                        "kind":block["kind"],"orientation":block["orientation"],
                        "windows":windows})
                    print(f"SCHED-ARCH-014 boot={index} kind={block['kind']} "
                          f"ns/command={[round(w['cpu_ns_per_command'],2) for w in windows]}",
                          flush=True)
                record["status"]="complete"
            record["host_after"]=snapshot_host()
        finally:
            if rcon is not None:
                try:rcon.command("stop")
                except (RuntimeError,OSError):pass
                rcon.close()
            try:process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return record


def block_contrast(block:dict, frozen:dict) -> float:
    if block["kind"]!=frozen["kind"] or block["orientation"]!=frozen["orientation"]:
        raise AssertionError("Wrong pair assignment")
    if len(block["windows"])!=4:
        raise AssertionError("Incomplete ABBA/BAAB")
    arms=KIND_ARMS[block["kind"]]
    observed=[w["arm"] for w in block["windows"]]
    if observed!=frozen["arms"]:
        raise AssertionError(f"Unexpected arm order: {observed} vs {frozen['arms']}")
    a=[math.log(w["cpu_ns_per_command"]) for w in block["windows"] if w["arm"]==arms[0]]
    b=[math.log(w["cpu_ns_per_command"]) for w in block["windows"] if w["arm"]==arms[1]]
    if len(a)!=2 or len(b)!=2:
        raise AssertionError("Expected two windows per arm")
    return 100*(statistics.mean(b)-statistics.mean(a))


def analyze(boots:list[dict], assignments:tuple[dict,...]) -> dict:
    if len(boots)!=N_BOOTS or len(assignments)!=N_BOOTS:
        raise AssertionError("Incomplete campaign")
    per_boot=[]
    for index,(boot,assignment) in enumerate(zip(boots,assignments)):
        if boot["boot"]!=index or boot["status"]!="complete":
            raise AssertionError(f"Invalid independent boot: {index}")
        if len(boot["blocks"])!=2:
            raise AssertionError("Missing comparison block")
        expected={b["kind"]:b for b in assignment["blocks"]}
        contrasts={b["kind"]:block_contrast(b,expected[b["kind"]])
                   for b in boot["blocks"]}
        if set(contrasts)!=set(KIND_ARMS):
            raise AssertionError("Missing predeclared contrast")
        windows=[w for b in boot["blocks"] for w in b["windows"]]
        if not all(w["exact_work"] for w in windows):
            raise AssertionError("Scoreboard parity invalid")
        qualified=boot["qualification"]["qualification_stable"]
        quality=(qualified
                 and all(w["cgroup_nr_throttled_delta"]==0 for w in windows)
                 and all(w["runqueue_delay_fraction"] is not None
                         and w["runqueue_delay_fraction"]<=stable.MAX_RUNQUEUE_DELAY_FRACTION
                         for w in windows))
        per_boot.append({"boot":index,"quality":quality,
                         "qualification_stable":qualified,"contrasts":contrasts})
    by_kind={}
    for kind in KIND_ARMS:
        values=[x["contrasts"][kind] for x in per_boot]
        by_kind[kind]={
            "n_independent_boots":N_BOOTS,
            "median_signed_log_percent":statistics.median(values),
            "exact_median_interval":exact_median_interval(values),
            "per_boot_log_percent":values,
        }
    bad=[x["boot"] for x in per_boot if not x["quality"]]
    placebo=by_kind["negative"]["exact_median_interval"]
    direct=by_kind["direct_vs_fused"]["exact_median_interval"]
    if bad:
        verdict="inconclusive_quality"
    elif placebo["lower"]>0 or placebo["upper"]<0:
        verdict="invalid_negative_control"
    elif direct["upper"]<=-15:
        verdict="direct_scheduler_material_gain_supported"
    elif direct["lower"]>0:
        verdict="direct_scheduler_regression_supported"
    elif direct["lower"]>=-15:
        verdict="direct_scheduler_no_material_gain"
    else:
        verdict="direct_scheduler_inconclusive"
    return {
        "verdict":verdict,
        "by_kind":by_kind,
        "quality_failed_boots":bad,
        "negative_interval_includes_zero":placebo["lower"]<=0<=placebo["upper"],
        "scope":"Strict exact-literal scoreboard function with no callback/trace/fork/return; not global scheduler replacement",
        "no_production_default_change":True,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=("diagnostic","timing"),required=True)
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    outfile=OUT/f"{args.phase}.json"
    frozen=plan()
    record={
        "experiment":EXPERIMENT,"phase":args.phase,"status":"started",
        "boots":[],
        "preregistration":{
            "seed":SEED,"n_independent_boots":N_BOOTS,
            "control":"identical fused functions in one namespace",
            "treatment":"direct CallFunction fast path vs same fused body",
            "lengths_diagnostic":LENGTHS,"primary_length":PRIMARY_LENGTH,
            "timed_calls_per_window":WINDOW_CALLS,
            "prewarm_calls_per_arm":PREWARM_PER_FUNCTION,
            "all_windows_retained":True,
            "comparison_plan":frozen,
            "minimum_gain_log_percent":-15,
            "exact_interval":">=95% via median order statistics",
            "semantic_gate":"activation, exact work, low quotas, nested, unsupported and debug fallback",
            "timing_metrics_off":True,
        }
    }
    outfile.write_text(json.dumps(record,indent=2)+"\n")
    try:
        artifacts=stage_artifacts()
        record["artifact_sha256"]={k:v for k,v in artifacts.items() if k.endswith("_sha256")}
        if args.phase=="diagnostic":
            record["boots"].append(run_boot(0,artifacts,True))
        else:
            prior=json.loads((OUT/"diagnostic.json").read_text())
            if prior["status"]!="complete" or prior["boots"][0]["parity"]["status"]!="passed":
                raise AssertionError("Direct-call semantic diagnostic required before timing")
            for i,assignment in enumerate(frozen):
                result=run_boot(i,artifacts,False,assignment)
                record["boots"].append(result)
                outfile.write_text(json.dumps(record,indent=2)+"\n")
            record["analysis"]=analyze(record["boots"],frozen)
        record["status"]="complete"
        print("SCHED-ARCH-014 COMPLETE "+json.dumps({
            "phase":args.phase,"status":record["status"],
            "parity":record["boots"][0].get("parity") if args.phase=="diagnostic" else None,
            "analysis":record.get("analysis"),
        }),flush=True)
    except BaseException as error:
        record["status"]="failed"
        record["error"]=repr(error)
        raise
    finally:
        outfile.write_text(json.dumps(record,indent=2)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
