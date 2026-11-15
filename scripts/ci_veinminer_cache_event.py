"""SCHED-COMP-017: real 6x6x6 native Vein Miner mining event, cached vs legacy.

Same compiled ScoreAdd, vanilla scheduler, player-bot inputs and commands in
both arms. Only the explicitly allowlisted legacy config-getenv namespace
changes. Whole-event completion is NOT server-thread CPU and this test does
not compare against compiler-disabled vanilla. No Spark or per-command metrics.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys

from ci_compiler_off_paired import exact_median_interval
from ci_compiler_off_paired import snapshot_host

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "SCHED-COMP-017"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
REPORT = OUT / "results.json"
PAIR_COUNT = 10
SEED = 26874017
SIDELENGTH = 6
MINIMUM_GAIN_PERCENT = 15.0
NATIVE_PACK_PATH = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
NATIVE_PACK_SHA256 = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
ARMS = ("legacy", "cached")
STATE_FIELDS = (
    "player_mined_source_stat", "work_after", "work_expected",
    "run_state_after", "queue_head_delta", "remaining_ore",
    "source_block_remains", "operation_markers_after", "target_markers_after",
)
CONTEXT_METRICS = ("tick_average_ms", "tick_p95_ms")


def allocation() -> tuple[tuple[str, str], ...]:
    rng = random.Random(SEED)
    # Counterbalance exactly five in each order, deterministic before launch.
    values = [("legacy", "cached")] * (PAIR_COUNT//2) + [
        ("cached", "legacy")] * (PAIR_COUNT//2)
    rng.shuffle(values)
    return tuple(values)


def stats_int(status: str | None, name: str) -> int | None:
    import re
    if status is None:
        return None
    m = re.search(rf"\b{re.escape(name)}=(\d+)\b", status)
    return int(m.group(1)) if m else None


def run_profile(mode: str, pair: int, position: int) -> dict:
    if mode not in ARMS:
        raise ValueError(mode)
    command=[
        sys.executable,str(ROOT/"scripts/run_veinminer_profile.py"),
        "--stack","fabric","--compiler-mode","score-add",
        "--side",str(SIDELENGTH),"--capture-timeout","60","--no-spark",
    ]
    env=dict(os.environ)
    # Gradle's runner-wide shared read-only dependency cache has previously
    # conflicted with the nested runServer task's writable lock requirements.
    # Keep a dedicated (serially reusable) cache for these native events.
    # This does not affect Minecraft runtime flags or event timing.
    env.pop("GRADLE_RO_DEP_CACHE",None)
    env["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
    # The existing production runner passes the inherited environment to
    # Gradle's Minecraft server. This flag is intentionally absent for cached,
    # and names the real publisher 'vm' namespace for legacy.
    if mode=="legacy":
        env["FC_SCORE_ADD_LEGACY_NAMESPACE"]="vm"
    else:
        env.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
    completed=subprocess.run(command,cwd=ROOT,env=env,text=True,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             timeout=600,check=False)
    if completed.returncode!=0:
        raise RuntimeError(
            f"Real event pair {pair} arm {mode}: exit={completed.returncode};"
            f" stdout={completed.stdout[-2000:]!r};stderr={completed.stderr[-2000:]!r}")
    profile=json.loads(completed.stdout)
    result=profile["results"]
    if result.get("compiler_mode")!="score-add":
        raise AssertionError("Compiled event unexpectedly using another mode")
    if not result.get("valid_native_workload") or not result.get("valid_score_add_profile"):
        raise AssertionError(f"Native Vein Miner or ScoreAdd validity gate failed: {mode}")
    if result.get("fused_regions_compiled")!=0:
        raise AssertionError("Unexpected fusion in real ScoreAdd attribution")
    if (result.get("queue_score_add_compiled") or 0)<=0:
        raise AssertionError("Publisher vm namespace had no typed ScoreAdd candidates")
    state={key:result[key] for key in STATE_FIELDS}
    completion=result["operation_completion_seconds"]
    if not isinstance(completion,(int,float)) or completion<=0:
        raise AssertionError(f"Missing positive native event duration: {completion}")
    return {
        "pair":pair,"position":position,"mode":mode,
        "profile_mode":"score-add",
        "run_id":result.get("run_id"),"output":profile.get("output"),
        "env_legacy_namespace":"vm" if mode=="legacy" else None,
        "event_completion_seconds":completion,
        "parity_state":state,
        "vm_queue_score_add_compiled":result["queue_score_add_compiled"],
        "fused_regions_compiled":result["fused_regions_compiled"],
        "tick_query_after_capture":result.get("tick_query_after_capture"),
        "exact_native_workload":True,"profile_valid":True,
    }


def paired_percentage(fused: float, baseline: float) -> float:
    if fused <= 0 or baseline <= 0:
        raise AssertionError("Nonpositive timing")
    return 100 * (fused / baseline - 1)


def analyze(pairs:list[dict])->dict:
    if len(pairs)!=PAIR_COUNT:raise AssertionError("Incomplete independent paired events")
    contrasts=[]
    outcomes=[]
    for index,pair in enumerate(pairs,1):
        if pair["index"]!=index or len(pair["arms"])!=2:
            raise AssertionError(f"Pair {index} missing or out of order")
        a=pair["arms"]["legacy"]
        b=pair["arms"]["cached"]
        if a["parity_state"]!=b["parity_state"]:
            raise AssertionError(f"Native mining work diverged in pair {index}")
        if not all(r["profile_valid"] and r["exact_native_workload"] for r in (a,b)):
            raise AssertionError(f"Native mining validity missing in pair {index}")
        if not (a["vm_queue_score_add_compiled"]>0 and b["vm_queue_score_add_compiled"]>0):
            raise AssertionError("Missing actual vm namespace ScoreAdd compilation")
        pct=paired_percentage(b["event_completion_seconds"],a["event_completion_seconds"])
        contrasts.append(pct)
        outcomes.append({
            "index":index,"order":pair["order"],
            "legacy_event_seconds":a["event_completion_seconds"],
            "cached_event_seconds":b["event_completion_seconds"],
            "percent_cached_over_legacy":pct,"exact_native_state_parity":True,
        })
    interval=exact_median_interval(contrasts)
    if interval["upper"]<=-MINIMUM_GAIN_PERCENT:
        verdict="material_15pct_real_event_gain_supported"
    elif interval["upper"]<0:
        verdict="small_real_event_gain_supported"
    elif interval["lower"]>0:
        verdict="real_event_regression_supported"
    elif interval["lower"]>=-MINIMUM_GAIN_PERCENT:
        verdict="no_material_real_event_gain"
    else:
        verdict="real_event_inconclusive"
    return {
        "verdict":verdict,"n_pairs":PAIR_COUNT,"all_pairs_retained":True,
        "paired":outcomes,
        "primary":{
            "metric":"native player-bot ore event completion seconds",
            "median_relative_percent":statistics.median(contrasts),
            "exact_median_interval_percent":interval,
            "minimum_material_gain_percent":MINIMUM_GAIN_PERCENT,
        },
        "scope":"cached ScoreAdd immutable env overrides vs legacy getenv, both ScoreAdd enabled",
        "not_measured":"compiler-off/native vanilla performance; exclusive server CPU; non-vm functions",
        "caution":"Fresh server boot noise is observable but not equivalent to CPU measurement.",
    }


def main() -> int:
    import hashlib
    OUT.mkdir(parents=True, exist_ok=True)
    orders = allocation()
    record = {
        "experiment": EXPERIMENT, "status": "started",
        "preregistration": {
            "seed": SEED, "pairs": PAIR_COUNT, "orders": orders,
            "datapack": str(NATIVE_PACK_PATH.relative_to(ROOT)),
            "datapack_sha256_expected": NATIVE_PACK_SHA256,
            "workload": "native survival-player Vein Miner 6x6x6 ore event",
            "primary": "cached vs legacy ScoreAdd native event completion seconds",
            "minimum_gain_percent": MINIMUM_GAIN_PERCENT,
            "confidence_interval": "exact order-stat median interval >=95%",
            "secondary": "host snapshots and native event state integrity",
            "symmetric_no_spark_no_execution_counters": True,
            "no_exclusions": True,
            "no_production_default_change": True,
        },
        "pairs": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n")
    try:
        if not NATIVE_PACK_PATH.is_file():
            raise FileNotFoundError(f"Native datapack not present at {NATIVE_PACK_PATH}")
        actual = hashlib.sha256(NATIVE_PACK_PATH.read_bytes()).hexdigest()
        if actual != NATIVE_PACK_SHA256:
            raise AssertionError(f"Pinned Vein Miner datapack fingerprint mismatch: {actual}")
        for index, order in enumerate(orders, 1):
            pair = {"index": index, "order": list(order), "arms": {},
                    "host_before": snapshot_host()}
            record["pairs"].append(pair)
            REPORT.write_text(json.dumps(record,indent=2)+"\n")
            for position, mode in enumerate(order):
                print(f"REAL_EVENT pair={index}/{PAIR_COUNT} pos={position} arm={mode}",
                      flush=True)
                pair["arms"][mode] = run_profile(mode, index, position)
                REPORT.write_text(json.dumps(record,indent=2)+"\n")
            pair["host_after"] = snapshot_host()
            if pair["arms"]["legacy"]["parity_state"] != pair["arms"]["cached"]["parity_state"]:
                raise AssertionError(f"Parities diverged in pair {index}")
        record["analysis"] = analyze(record["pairs"])
        record["status"] = "complete"
        print("SCHED-COMP-017 COMPLETE " + json.dumps(record["analysis"]), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["failure"] = repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(record,indent=2)+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
