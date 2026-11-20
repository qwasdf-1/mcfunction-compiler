#!/usr/bin/env python3
"""IR-019 bounded original Blastback capture-stage dispatch activation pilot.

One untouched publisher SHA-pinned Blastback 26.3 datapack, real TNT, real
server tick/capture behavior, transparent read-only function-entry and native
callee counters. No attempt to assert full world restoration (the earlier
Blastback restoration oracle is unresolved); no compiler optimization or CPU
claim. Fails closed if event or target capture stage is not observed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir013 import stop
from ci_typed_ir015_coverage import PINS
from run_blastback_profile import write_setup_pack, score, block_matches, region_matches_template
from ci_typed_ir019_native import parse_log

OUT=ROOT/"build/reports/COMPILER-IR-019-BLASTBACK"
PACK=Path(PINS["blastback"]["path"])
ALLOWLIST=(
    "erb:runtime_tick",
    "erb:runtime/finish",
    "erb:capture/prepare",
    "erb:capture/check_captured_position",
    "erb:capture/queue",
    "erb:capture/loop",
    "erb:capture/store",
    "erb:restore/job_tick",
    "erb:group/join",
    "erb:pump/dormant",
    "erb:source/tick_dimension",
    "erb:job/create",
    "erb:watch/scan/root",
)
CALLEES=(
    "erb:group/add_segment",
    "erb:capture/requeue_moved",
    "erb:capture/schedule",
    "erb:capture/loop",
    "erb:restore/job_tick",
    "erb:job/create",
    "erb:group/join",
    "erb:runtime_tick",
    "erb:capture/store",
    "erb:capture/queue",
    "erb:pump/dormant",
)
# Known independently planted block palette from accepted BLASTBACK-007 audit.
WITNESSES={
    "gold_block":(2,63,4),
    "diamond_block":(4,63,4),
    "redstone_block":(6,63,4),
    "emerald_block":(4,63,6),
    "stone":(12,63,12),
}


def setup(cpu_mode: str | None = None, output: Path = OUT, cpu_family: str = "020"):
    output.mkdir(parents=True,exist_ok=True)
    RUNS.mkdir(parents=True,exist_ok=True)
    if cpu_family not in ("020","021","022"):
        raise ValueError("Unknown native CPU diagnostic: "+cpu_family)
    work=RUNS/("ci-ir019-blastback" if cpu_mode is None
               else "ci-ir"+cpu_family+"-blastback-"+cpu_mode)
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    packs=work/"world/datapacks"
    packs.mkdir(parents=True)
    shutil.copy2(PACK,packs/"blastback.zip")
    write_setup_pack(packs/"function_compiler_benchmark",1)
    (work/"eula.txt").write_text("eula=true\n")
    server_port,rcon_port=unused_port(),unused_port()
    password=secrets.token_hex(16)
    (work/"server.properties").write_text("\n".join([
        "online-mode=false","enable-rcon=true","broadcast-rcon-to-ops=false",
        "level-name=world","level-seed=264010",
        "pause-when-empty-seconds=-1","view-distance=4","simulation-distance=4",
        "max-tick-time=-1","max-players=1",
        f"server-port={server_port}",f"rcon.port={rcon_port}",
        f"rcon.password={password}"])+"\n")
    env=dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE":"true",
        "FC_COMPILER_EXEC_CENSUS":"true",
        "FC_COMPILER_EXEC_CENSUS_NAMESPACE":"erb",
        "FC_COMPILER_EXEC_CENSUS_FUNCTIONS":",".join(ALLOWLIST),
        "FC_COMPILER_EXEC_CENSUS_CALLEES":",".join(CALLEES),
        "FC_TYPED_IR_MODE":"","FC_TYPED_IR_NAMESPACE":"",
        "FC_SCORE_ADD_PROTOTYPE":"false",
        "FC_FUSED_REGION_PROTOTYPE":"false",
        "FC_BYTECODE_REGION_PROTOTYPE":"false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE":"false",
        "FC_TYPED_IR_DIRECT_FUNCTION":"false",
        "FC_SELECTIVE_MACRO_ARGUMENTS":"false",
    })
    if cpu_mode is not None:
        if cpu_mode not in (("control", "plain", "empty", "timed") if cpu_family=="022"
                            else ("plain", "empty", "timed")):
            raise ValueError(f"Invalid IR020 native CPU mode: {cpu_mode}")
        env["FC_COMPILER_EXEC_CENSUS"] = "false"
        env["FC_COMPILER_EXEC_CENSUS_FUNCTIONS"] = ""
        env["FC_COMPILER_EXEC_CENSUS_CALLEES"] = ""
        if cpu_family == "020":
            env["FC_CPU020_MODE"] = cpu_mode
            env["FC_CPU020_NAMESPACE"] = "erb"
        elif cpu_family == "021":
            env["FC_CPU021_MODE"] = cpu_mode
            env["FC_CPU021_NAMESPACE"] = "erb"
        else:
            env["FC_CPU022_MODE"] = cpu_mode
            env["FC_CPU022_NAMESPACE"] = "erb"
    command=[str(ROOT/"gradlew"),"--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx3G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}","runServer"]
    log=(output/"server.log").open("w",encoding="utf-8")
    proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,
                          stderr=subprocess.STDOUT,stdin=subprocess.PIPE)
    try:
        client=wait_for_rcon(proc,rcon_port,password,timeout_seconds=300)
        enabled=client.command("datapack list enabled")
        if "blastback" not in enabled.lower():
            raise AssertionError("Publisher Blastback did not enable: "+enabled)
        status=client.command("functioncompiler status")
        if "present=true" not in status and "wrapper" not in status.lower():
            # The census command below is the actual instrumentation gate.
            print("IR019_BLASTBACK_WRAPPER_STATUS "+status,flush=True)
        return proc,client,log
    except BaseException:
        proc.terminate();proc.wait(timeout=40);log.close();raise


def measure():
    if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest()!=PINS["blastback"]["sha256"]:
        raise AssertionError("Original Blastback publisher ZIP pin mismatch")
    proc,client,log=setup()
    report={"milestone":"COMPILER-IR-019","stage":"real_blastback_capture_read_only_pilot",
            "status":"started","publisher_sha256":PINS["blastback"]["sha256"],
            "dispatch_lowering":False,"cpu_speedup_claim":False,
            "full_restoration_claim":False,"native_gameplay_parity_claim":False}
    try:
        client.command("gamerule sendCommandFeedback false")
        client.command("gamerule doMobSpawning false")
        client.command("gamerule doDaylightCycle false")
        client.command("gamerule randomTickSpeed 0")
        client.command("gamerule maxEntityCramming 10000")
        client.command("difficulty peaceful")
        client.command("scoreboard objectives add fc_probe dummy")
        client.command("forceload add -16 -16 16 16")
        client.command("forceload add 64 32")
        client.command("fill -4 63 -4 12 63 12 minecraft:stone")
        for block,pt in WITNESSES.items():
            if block!="stone":
                x,y,z=pt
                client.command(f"setblock {x} {y} {z} minecraft:{block}")
        clone=client.command("clone -4 56 -4 12 72 12 64 56 32 replace force")
        before={block:block_matches(client,block,*pt) for block,pt in WITNESSES.items()}
        template=region_matches_template(client)
        if not all(before.values()) or not template:
            raise AssertionError(f"Native blastback TNT fixture witness mismatch: {before}, {clone}")
        report["fixture_before"]={"witnesses":before,"template_equal":template}
        tick_before=score(client,"#tick_id","erb.cfg")
        response=client.command("functioncompiler exec-census-start")
        if "FC_EXEC started" not in response:
            raise AssertionError(f"Census not installed on original pack: {response!r}")
        # Direct native summon avoids an unrelated /function queue tick
        # between an RCON response and the actual entity creation. A longer
        # 160-tick fuse ensures there is time to observe the live entity even
        # on a slow CI runner; this is a pilot fixture, not a baseline CPU run.
        spawn=client.command(
            'summon minecraft:tnt 4 64 4 {Fuse:160s,Tags:["fc_blastback_probe"]}')
        if "Summoned new" not in spawn:
            raise AssertionError(f"Original 1-TNT native summon declined: {spawn!r}")
        spawned=0
        for _ in range(12):
            client.command("scoreboard players set #ir019_tnt fc_probe 0")
            client.command("execute as @e[type=minecraft:tnt,tag=fc_blastback_probe] "
                           "run scoreboard players add #ir019_tnt fc_probe 1")
            spawned=score(client,"#ir019_tnt","fc_probe")
            if spawned==1:break
            time.sleep(0.1)
        if spawned!=1:
            raise AssertionError(
                f"Summon succeeded but original tagged TNT not resident: {spawned} {spawn!r}")
        report["spawned_tnt"]=spawned
        print("IR019_BLASTBACK_EVENT_ACTIVATED "+json.dumps({
            "spawned_tnt":spawned,"tick_before":tick_before}),flush=True)
        # Only a 30-second event window is observed. No TNT restoration gate
        # or unsupported end-to-end performance claim is inferred.
        time.sleep(30)
        census_stop=client.command("functioncompiler exec-census-stop")
        if "FC_EXEC ended" not in census_stop or "overflow=0" not in census_stop:
            raise AssertionError(
                f"Blastback bounded census missing/overflowed: {census_stop!r}")
        time.sleep(0.3)
        rows,callees=parse_log(OUT/"server.log")
        tick_after=score(client,"#tick_id","erb.cfg")
        after={block:block_matches(client,block,*pt) for block,pt in WITNESSES.items()}
        report["window"]={"tick_before":tick_before,"tick_after":tick_after,
                          "census_stop":census_stop,"source_rows":rows,
                          "native_callee_tasks":callees}
        report["fixture_after_window"]={"witnesses":after,
                                        "template_equal":region_matches_template(client)}
        reached=[r for r in rows if r["function"] and r["function"].startswith("erb:capture/")
                 and int(r.get("entries") or 0)>0]
        simple=[r for r in rows if r.get("dispatch_shape")=="single_score_static_call"
                and int(r.get("entries") or 0)>0]
        complex_=[r for r in rows if r.get("dispatch_shape")=="complex_or_return_call"
                  and int(r.get("entries") or 0)>0]
        report["reached_capture_rows"]=reached
        report["reached_simple_dispatch_rows"]=simple
        report["reached_complex_dispatch_rows"]=complex_
        report["source_entries_total"]=sum(int(r.get("entries") or 0) for r in rows)
        report["ordinary_callbacks_total"]=sum(int(r.get("callbacks") or 0) for r in rows)
        report["single_dispatch_entry_reaches"]=sum(int(r["entries"]) for r in simple)
        report["complex_dispatch_entry_reaches"]=sum(int(r["entries"]) for r in complex_)
        report["native_call_tasks_total"]=sum(callees.values())
        report["top_callback_expansion"]=max(
            rows,key=lambda r:int(r.get("callbacks") or 0),default=None)
        report["capture_stage_observed"]=bool(reached)
        report["source_dispatch_seen"]=bool(simple or complex_)
        report["valid_capture_window"]=tick_after>tick_before and bool(reached)
        report["full_restoration_validated"]=False
        if not report["valid_capture_window"]:
            raise AssertionError("No real Blastback capture function was seen inside bounded TNT window")
        report["status"]="accepted_capture_window_only"
        print("IR019_BLASTBACK_SUMMARY "+json.dumps({
            "status":report["status"],"ticks":tick_after-tick_before,
            "capture_rows":len(reached),"single_guard_rows_reached":len(simple),
            "complex_guard_rows_reached":len(complex_),
            "single_dispatch_entry_reaches":report["single_dispatch_entry_reaches"],
            "complex_dispatch_entry_reaches":report["complex_dispatch_entry_reaches"],
            "total_source_entries":report["source_entries_total"],
            "total_ordinary_callbacks":report["ordinary_callbacks_total"],
            "top_callback_expansion":report["top_callback_expansion"],
            "native_callee_tasks":callees,
            "speedup_claim":False,"full_restoration_claim":False
        },sort_keys=True),flush=True)
    except BaseException as e:
        report["status"]="invalid_capture_window"
        report["error"]=repr(e)
        raise
    finally:
        stop(proc,client,log)
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":
    measure()
