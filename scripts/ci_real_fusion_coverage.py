#!/usr/bin/env python3
"""SCHED-COMP-012: bounded native runtime fusion coverage and tick impact.

Phase 1: activation diagnostic, with per-function execution counters enabled.
Phase 2 (Simple Timer only, after a valid phase 1): 6 randomized fresh-boot
pairs with counters OFF, observing server-thread CPU per real active tick.
Blastback's native restoration gate is evaluated separately; no meaningful
performance comparison is attempted if that gate fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import statistics
import subprocess
import sys
import time
import zipfile

from ci_compiler_off_paired import exact_median_interval
from ci_native_cross_mode_attribution import (
    ROOT, FABRIC_BASE, RUN_ROOT, stage_artifacts, setup_server_properties,
    server_tid, server_cpu_time_ns,
)
from ci_compiler_off_stability import JVM_ARGS
from ci_smoke_server import unused_port, wait_for_rcon
from screen_adjacent_regions import screen_pack, FUNCTION_PATH
from run_runtime_probe import generate_packet_ids

sys.path.insert(0, str(ROOT / "tests" / "runtime"))

OUT = ROOT / "build/benchmarks/SCHED-COMP-012"
SOURCES = {
    "blastback": ROOT / "references/real-world/candidates/Blastback-Hotfix-3-26.3.zip",
    "simple_timer": ROOT / "references/real-world/candidates/Simple-Timer-source.zip",
}
BLASTBACK_SHA256 = "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90"
PAIR_COUNT = 6
SEED = 12012
SECONDS = 32
REGION_RE = re.compile(r"^execute if block .* run scoreboard players set ")


def stat_int(response: str, key: str) -> int:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)(?:\s|$)", response)
    if not match:
        raise AssertionError(f"Missing {key} in: {response}")
    return int(match.group(1))


def function_id(path: str) -> str:
    match = FUNCTION_PATH.match(path)
    if match is None:
        raise ValueError(path)
    return f"{match.group(1)}:{match.group(2)}"


def candidate_functions(pack: Path, name: str) -> dict:
    observed_sha = hashlib.sha256(pack.read_bytes()).hexdigest()
    if name == "blastback" and observed_sha != BLASTBACK_SHA256:
        raise ValueError(f"Blastback artifact SHA mismatch: {observed_sha}")
    static = screen_pack(pack, 2, 15)
    candidates = []
    with zipfile.ZipFile(pack) as archive:
        for path in archive.namelist():
            if not FUNCTION_PATH.match(path):
                continue
            lines = [line.strip() for line in archive.read(path).decode("utf-8").splitlines()]
            if name == "blastback":
                eligible = sum(1 for line in lines if REGION_RE.match(line))
                # The generated reader is capture-only; a static parser hit is
                # not evidence that it compiles or executes.
                if eligible >= 16:
                    candidates.append({"id":function_id(path), "lines":eligible,
                                       "source":path, "path":"capture_candidate"})
            else:
                # Tick reachability is an upper bound; candidates here may
                # subsequently decline actual runtime specialization.
                tick_ids = {
                    function_id(run["function"])
                    for tier in ("literal_score", "parsed_candidates", "leaf_functions")
                    for run in static[tier]["top_tick_runs"]
                }
                if function_id(path) in tick_ids:
                    candidates.append({"id":function_id(path), "lines":len(lines),
                                       "source":path, "path":"tick_reachable"})
    if not candidates:
        raise AssertionError(f"No static target functions for {name}; do not run timing")
    return {
        "pack":name, "sha256":observed_sha,
        "static_summary": {
            "functions":static["functions"],
            "tick_reachable_functions":static["tick_reachable_functions"],
            "parsed_candidate_tick_runs":static["parsed_candidates"]["tick_runs"],
        },
        "targets":sorted(candidates,key=lambda item:(-item["lines"],item["id"]))[:30],
    }


def write_tick_witness(workdir: Path) -> None:
    dp = workdir / "world/datapacks/fc_coverage_witness"
    target = dp / "data/fc_coverage/function"
    target.mkdir(parents=True,exist_ok=True)
    (dp / "pack.mcmeta").write_text(
        json.dumps({"pack":{"description":"SCHED-COMP-012 tick witness",
                            "min_format":[97,1],"max_format":[97,1]}})+"\n")
    (target / "tick.mcfunction").write_text(
        "scoreboard players add #ticks fc_coverage 1\n")
    tag = dp / "data/minecraft/tags/function/tick.json"
    tag.parent.mkdir(parents=True,exist_ok=True)
    tag.write_text(json.dumps({"replace":False,"values":["fc_coverage:tick"]})+"\n")


def read_tick_count(rcon) -> int:
    reply=rcon.command("scoreboard players get #ticks fc_coverage")
    match=re.search(r"has (-?\d+)",reply)
    if not match:
        return 0
    return int(match.group(1))


def boot(name: str, mode: str, index: int, artifacts: dict, inventory: dict) -> dict:
    assert mode in ("diagnostic","score-add","fused")
    workdir = RUN_ROOT / f"ci-fusion012-{name}-{mode}-{index:02d}"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(FABRIC_BASE,workdir)
    mod_dir=workdir/"mods"
    mod_dir.mkdir(exist_ok=True)
    for artifact in ("api","compiler"):
        source=Path(artifacts[artifact])
        shutil.copy2(source,mod_dir/source.name)
    packs=workdir/"world/datapacks"
    packs.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SOURCES[name],packs/(name+".zip"))
    write_tick_witness(workdir)
    config=workdir/"config"
    config.mkdir(exist_ok=True)
    (config/"function-compiler.json").write_text(json.dumps({
        "enabled":True,"score_add":True,
        "fused_regions":mode!="score-add",
        "selective_macros":False,"tiered_bytecode":False,
        "tiered_threshold":5,"excluded_namespaces":[]
    })+"\n")
    port,rcon_port=unused_port(),unused_port()
    password=secrets.token_hex(16)
    setup_server_properties(workdir,port,rcon_port,password)
    env=dict(os.environ)
    for flag in ("FC_WRAPPER_PROBE","FC_SCORE_ADD_PROTOTYPE",
                 "FC_FUSED_REGION_PROTOTYPE","FC_SCORE_ADD_METRICS",
                 "FC_SCORE_ADD_TIMING","FC_BYTECODE_REGION_PROTOTYPE",
                 "FC_SELECTIVE_MACRO_ARGUMENTS","FC_SELECTIVE_MACRO_ARGUMENTS_METRICS",
                 "FC_COMMAND_CALLBACK_METRICS","FC_FUNCTION_TIMING",
                 "FC_RUNTIME_TRACE","FC_SCHEDULER_RESEARCH"):
        env[flag]="false"
    env.update({
        "FC_WRAPPER_PROBE":"true","FC_SCORE_ADD_PROTOTYPE":"true",
        "FC_FUSED_REGION_PROTOTYPE":str(mode!="score-add").lower(),
        "FC_SCORE_ADD_METRICS":str(mode=="diagnostic").lower(),
    })
    OUT.mkdir(parents=True,exist_ok=True)
    logpath=OUT/f"{name}-{mode}-{index:02d}.log"
    report={"name":name,"mode":mode,"index":index,"status":"started",
            "pack_sha256":inventory["sha256"],"targets":inventory["targets"]}
    with logpath.open("w",encoding="utf-8") as log:
        process=subprocess.Popen(
            ["java",*JVM_ARGS,"-jar",str(workdir/"fabric-server-launch.jar"),"nogui"],
            cwd=workdir,env=env,stdout=log,stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE)
        rcon=None
        bot=None
        try:
            rcon=wait_for_rcon(process,rcon_port,password,timeout_seconds=180)
            status=rcon.command("functioncompiler status")
            if "wrapped=true" not in status or "score_add_prototype_enabled=true" not in status:
                raise AssertionError(f"Compiler not activated: {status}")
            fused="fused_region_prototype_enabled=true" in status
            if fused!=(mode!="score-add"):
                raise AssertionError(f"Fusion flag wrong: {status}")
            rcon.command("gamerule doMobSpawning false")
            rcon.command("gamerule randomTickSpeed 0")
            rcon.command("scoreboard objectives add fc_coverage dummy")
            if name=="simple_timer":
                from player_bot import PlayerBot
                bot=PlayerBot("FCTimer", "127.0.0.1", port,
                              generate_packet_ids(FABRIC_BASE/"server.jar")).connect()
                # This is a native player-trigger attempt, not manually calling
                # the candidate tick function. If the pack uses a different
                # activation mechanism, missing coverage is reported as such.
                report["start_trigger"]=rcon.command("execute as FCTimer run trigger timer.start")
                report["objectives"]=rcon.command("scoreboard objectives list")
            else:
                rcon.command("forceload add -16 -16 16 16")
                rcon.command("forceload add 64 32")
                rcon.command("fill -4 63 -4 12 63 12 minecraft:stone")
                for block,x,z in (
                    ("gold_block",2,4),("diamond_block",4,4),
                    ("redstone_block",6,4),("emerald_block",4,6)):
                    rcon.command(f"setblock {x} 63 {z} minecraft:{block}")
                report["template_clone"]=rcon.command(
                    "clone -4 56 -4 12 72 12 64 56 32 replace force")
            tid=server_tid(process.pid)
            def snapshots():
                return {item["id"]:{
                    key:stat_int(rcon.command(f"functioncompiler stats {item['id']}"),key)
                    for key in ("fused_regions_compiled","fused_regions_executed")}
                    for item in inventory["targets"]}
            report["stats_before"]=snapshots()
            report["ticks_before"]=read_tick_count(rcon)
            cpu_start,cpu_clock=server_cpu_time_ns(process.pid,tid)
            started=time.monotonic()
            if name=="blastback":
                report["tnt_spawn"]=rcon.command(
                    'summon minecraft:tnt 4 64 4 {Fuse:80s,Tags:["fc_blastback_probe"]}')
            time.sleep(SECONDS if name=="simple_timer" else 75)
            report["elapsed_seconds"]=time.monotonic()-started
            cpu_stop,cpu_clock_end=server_cpu_time_ns(process.pid,tid)
            if cpu_clock!=cpu_clock_end:raise AssertionError("CPU clock switched")
            report["cpu_running_ns"]=cpu_stop-cpu_start
            report["ticks_after"]=read_tick_count(rcon)
            report["tick_delta"]=report["ticks_after"]-report["ticks_before"]
            report["stats_after"]=snapshots()
            report["tick_query"]=rcon.command("tick query")
            report["executed_delta_by_function"]={
                key:report["stats_after"][key]["fused_regions_executed"]
                    -report["stats_before"][key]["fused_regions_executed"]
                for key in report["stats_before"]}
            report["compiled_targets"]=[
                key for key,value in report["stats_after"].items()
                if value["fused_regions_compiled"]>0]
            report["executed_targets"]={
                key:count for key,count in report["executed_delta_by_function"].items()
                if count>0}
            report["target_fusion_executed"]=bool(report["executed_targets"])
            report["cpu_ns_per_witness_tick"] = (
                report["cpu_running_ns"]/report["tick_delta"]
                if report["tick_delta"]>0 else None)
            if name=="blastback":
                rcon.command("scoreboard objectives add fc_blastback_check dummy")
                rcon.command("execute store success score #witness fc_blastback_check run "
                             "execute if blocks -4 56 -4 12 72 12 64 56 32 all")
                response=rcon.command("scoreboard players get #witness fc_blastback_check")
                report["source_matches_template"]="has 1" in response
                report["restoration_state"]=rcon.command("function erb:status/collect")
                # The 1-TNT restoration scenario has previously failed exact
                # parity. No performance claim is allowed without full native
                # state validation; this run is a mechanism diagnostic only.
                report["valid_for_native_timing"]=False
                report["native_gate"]="full_restoration_not_certified"
            else:
                report["valid_for_native_timing"]=(
                    report["tick_delta"]>=300 and bot is not None
                    and report["target_fusion_executed"] if mode=="diagnostic"
                    else report["tick_delta"]>=300
                )
                report["native_gate"]=("passed" if report["valid_for_native_timing"]
                                       else "insufficient_real_tick_activation")
            report["status"]="complete"
        finally:
            if rcon is not None:
                try:rcon.command("stop")
                except (OSError,RuntimeError):pass
                rcon.close()
            if bot is not None:
                bot.close()
            try:process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return report


def paired_orders() -> list[tuple[str,str]]:
    orders=[("score-add","fused")]*(PAIR_COUNT//2)+[
        ("fused","score-add")]*(PAIR_COUNT//2)
    random.Random(SEED).shuffle(orders)
    return orders


def analyze_timer_pairs(pairs: list[dict]) -> dict:
    if len(pairs)!=PAIR_COUNT:
        raise AssertionError("Incomplete campaign")
    deltas=[]
    for p in pairs:
        a,b=p["arms"]["score-add"],p["arms"]["fused"]
        if not a["valid_for_native_timing"] or not b["valid_for_native_timing"]:
            raise AssertionError("Unqualified paired native ticks")
        if abs(a["tick_delta"]-b["tick_delta"])>15:
            raise AssertionError("Large mismatch in sampled native tick counts")
        if a["cpu_ns_per_witness_tick"]<=0 or b["cpu_ns_per_witness_tick"]<=0:
            raise AssertionError("Invalid CPU counters")
        deltas.append(100*(b["cpu_ns_per_witness_tick"]/
                           a["cpu_ns_per_witness_tick"]-1))
    interval=exact_median_interval(deltas)
    return {"n_pairs":len(deltas),"median_percent":statistics.median(deltas),
            "exact_median_interval_percent":interval,
            "per_pair_percent":deltas,
            "verdict":("at_least_15pct_gain_supported" if interval["upper"]<=-15
                       else "regression_supported" if interval["lower"]>0
                       else "inconclusive_or_not_material"),
            "caution":"CPU per native tick is whole-server CPU, not eligible function CPU; trigger/control parity remains bounded."}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack",choices=tuple(SOURCES),required=True)
    parser.add_argument("--stage",choices=("diagnostic","timing"),default="diagnostic")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    reportpath=OUT/f"{args.pack}-{args.stage}.json"
    record={"experiment":"SCHED-COMP-012","pack":args.pack,"stage":args.stage,
            "status":"started","boots":[],"seed":SEED,
            "method":"fusion counters on only for diagnostic, never timed"}
    reportpath.write_text(json.dumps(record,indent=2)+"\n")
    try:
        inventory=candidate_functions(SOURCES[args.pack],args.pack)
        record["inventory"]=inventory
        if args.stage=="timing":
            earlier=json.loads((OUT/f"{args.pack}-diagnostic.json").read_text())
            diag=earlier["boots"][0]
            if earlier["status"]!="complete" or not diag["target_fusion_executed"] or not diag["valid_for_native_timing"]:
                record["status"]="not_eligible_for_timing"
                record["reason"]="No runtime-confirmed fused native target with valid native gate"
                return 0
            if args.pack!="simple_timer":
                record["status"]="not_eligible_for_timing"
                record["reason"]="Blastback full native restoration gate remains unverified"
                return 0
        artifacts=stage_artifacts()
        if args.stage=="diagnostic":
            record["boots"].append(boot(args.pack,"diagnostic",0,artifacts,inventory))
        else:
            pairs=[]
            for i,order in enumerate(paired_orders()):
                entry={"pair":i,"order":order,"arms":{}}
                pairs.append(entry)
                record["pairs"]=pairs
                reportpath.write_text(json.dumps(record,indent=2)+"\n")
                for mode in order:
                    result=boot(args.pack,mode,i,artifacts,inventory)
                    entry["arms"][mode]=result
                    record["boots"].append(result)
                    reportpath.write_text(json.dumps(record,indent=2)+"\n")
            record["analysis"]=analyze_timer_pairs(pairs)
        record["status"]="complete"
        print("SCHED-COMP-012 "+json.dumps({
            "pack":args.pack,"stage":args.stage,"status":record["status"],
            "activation":record["boots"][0].get("executed_targets"),
            "analysis":record.get("analysis")}),flush=True)
    except BaseException as e:
        record["status"]="failed"
        record["error"]=repr(e)
        raise
    finally:
        reportpath.write_text(json.dumps(record,indent=2)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
