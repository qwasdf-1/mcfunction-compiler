#!/usr/bin/env python3
"""SCHED-COMP-015: scoreboard callback and objective lookup attribution.

Stage A (diagnostic): timed ObjectiveArgument resolution, score creation /
mutation, and response tracking+feedback *within typed callbacks* only. Those
nanoTime probes are not exclusive CPU times and are disabled during timing.
Stage B: 12 independent JVMs, with five byte-identical function namespaces
and four balanced ABBA/BAAB contrasts: native A/A placebo, pass-through
wrapper vs native, typed body vs pass-through wrapper, research guarded
objective lookup vs typed. No fusion or alternative scheduler in any arm.
"""
from __future__ import annotations

import argparse
import itertools
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

from ci_compiler_off_paired import exact_median_interval, cpu_run_delay, snapshot_host
import ci_compiler_off_stability as stable
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    stage_artifacts, make_fixture, setup_server_properties,
    server_tid, server_cpu_time_ns, read_score,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon

EXPERIMENT = "SCHED-COMP-015"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
SEED = 15015
N_BOOTS = 12
DIAGNOSTIC_CALLS = 32
TIMING_CALLS_PER_WINDOW = 220
PREWARM_PER_ARM = 120
LENGTHS = (4, 16, 256, 2000)
PRIMARY_LENGTH = 2000
KINDS = ("negative","delegating_vs_native","typed_vs_delegating","fastobj_vs_typed")
NAMESPACES = {
    "native":"fc_attr_native",
    "null":"fc_attr_native_null",
    "delegate":"fc_attr_delegate",
    "typed":"fc_attr_typed",
    "fastobj":"fc_attr_fastobj",
}
FAMILIES = {
    "negative":("native","null"),
    "delegating_vs_native":("native","delegate"),
    "typed_vs_delegating":("delegate","typed"),
    "fastobj_vs_typed":("typed","fastobj"),
}


def function_id(arm: str, length: int) -> str:
    if arm not in NAMESPACES or length not in LENGTHS:
        raise ValueError((arm, length))
    return f"{NAMESPACES[arm]}:score_{length}"


def prepare_fixture(workdir: Path) -> None:
    make_fixture(workdir)  # also supplies existing validated warmup/qualification.
    base = workdir / "world" / "datapacks" / PACK
    line = f"scoreboard players add {HOLDER} {OBJECTIVE} 1"
    for length in LENGTHS:
        body = (line + "\n") * length
        for arm, namespace in NAMESPACES.items():
            folder = base / "data" / namespace / "function"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"score_{length}.mcfunction").write_text(body, encoding="utf-8")
    config = workdir / "config"
    config.mkdir(exist_ok=True)
    (config / "function-compiler.json").write_text(json.dumps({
        "enabled": True,
        "score_add": True,
        "fused_regions": False,
        "selective_macros": False,
        "tiered_bytecode": False,
        "tiered_threshold": 5,
        "excluded_namespaces": [NAMESPACES["native"], NAMESPACES["null"]],
    }, indent=2) + "\n", encoding="utf-8")


def plan() -> tuple[dict, ...]:
    rng=random.Random(SEED)
    # 4 Latin-square rotations repeated three times: each contrast is in
    # each temporal block position exactly three times across 12 boots.
    # Six ABBA and six BAAB orientations per contrast, fixed ahead of time.
    rotations=[KINDS[i:]+KINDS[:i] for i in range(4)] * 3
    rng.shuffle(rotations)
    orientations={
        kind:rng.sample(["ABBA","BAAB"]*(N_BOOTS//2),N_BOOTS)
        for kind in KINDS
    }
    return tuple({
        "boot":i,"blocks":[{
            "kind":kind,"orientation":orientations[kind][i],
            "arms":[FAMILIES[kind][0 if x=="A" else 1]
                    for x in orientations[kind][i]],
        } for kind in rotations[i]]
    } for i in range(N_BOOTS))


def parse_stat(response: str, name: str) -> int:
    match = re.search(rf"(?:^|\s){re.escape(name)}=(\d+)(?:\s|$)", response)
    if match is None:
        raise AssertionError(f"Status missing {name}: {response!r}")
    return int(match.group(1))


def compilation_gate(rcon: Rcon) -> dict:
    observed = {}
    for length in LENGTHS:
        for arm in NAMESPACES:
            fid = function_id(arm, length)
            reply = rcon.command(f"functioncompiler stats {fid}")
            counts = {
                key: parse_stat(reply, key)
                for key in ("score_add_compiled", "fused_regions_compiled")
            }
            expected_score = length if arm in ("delegate","typed","fastobj") else 0
            if counts["score_add_compiled"] != expected_score:
                raise AssertionError(f"Wrong typed activation: {fid} {counts} vs {expected_score}")
            expected_fused = 0
            if counts["fused_regions_compiled"] != expected_fused:
                raise AssertionError(f"Wrong fused activation: {fid} {counts} vs {expected_fused}")
            observed[fid] = counts
    return observed


def invoke(rcon: Rcon, arm: str, length: int) -> None:
    result = rcon.command(f"function {function_id(arm,length)}")
    if not result.startswith("Running function "):
        raise AssertionError(f"Invocation failed: {arm}/{length}: {result!r}")


def exact_work(rcon: Rcon, calls: int, length: int, arm: str) -> dict:
    expected = calls * length
    actual = read_score(rcon)
    if actual != expected:
        raise AssertionError(
            f"Non-equivalent command work {arm}/{length}: actual={actual} expected={expected}")
    return {"actual": actual, "expected": expected, "exact_work": True}


PHASE_KEYS=("score_phase_samples","score_phase_objective_ns",
            "score_phase_mutation_ns","score_phase_feedback_ns")


def diagnostic_arm(rcon: Rcon, length: int) -> dict:
    arm="typed"
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    before=rcon.command("functioncompiler status")
    before_counts={k:parse_stat(before,k) for k in PHASE_KEYS}
    for _ in range(DIAGNOSTIC_CALLS):
        invoke(rcon,arm,length)
    integrity=exact_work(rcon,DIAGNOSTIC_CALLS,length,arm)
    after=rcon.command("functioncompiler status")
    after_counts={k:parse_stat(after,k) for k in PHASE_KEYS}
    delta={k:after_counts[k]-before_counts[k] for k in PHASE_KEYS}
    expected=DIAGNOSTIC_CALLS*length
    if delta["score_phase_samples"]!=expected:
        raise AssertionError(f"Wrong number of phase samples: {delta} vs {expected}")
    if any(delta[k]<=0 for k in PHASE_KEYS[1:]):
        raise AssertionError(f"Missing measured phase: {delta}")
    return {"arm":arm,"length":length,"calls":DIAGNOSTIC_CALLS,
            "work":integrity,"breakdown":delta,
            "mean_wall_ns_per_callback":{
                k:delta[k]/expected for k in PHASE_KEYS[1:]},
            "caveat":"Times include nanoTime instrumentation; not exclusive CPU attribution"}


def semantic_guard(rcon: Rcon) -> dict:
    # Research fast lookup always fetches the current Objective. It must
    # observe missing and recreated objectives, rather than retain a stale
    # scoreboard object compiled at datapack load.
    results={}
    rcon.command(f"scoreboard objectives remove {OBJECTIVE}")
    for arm in ("typed","fastobj"):
        results[arm+"_missing_reply"]=invoke(rcon,arm,4)
    rcon.command(f"scoreboard objectives add {OBJECTIVE} dummy")
    for arm in ("typed","fastobj","delegate","native"):
        rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        invoke(rcon,arm,4)
        results[arm+"_recreated_score"]=read_score(rcon)
        if results[arm+"_recreated_score"]!=4:
            raise AssertionError(f"Reloaded objective failed {arm}: {results}")
    # A read-only objective must reject both fast and native paths.
    rcon.command(f"scoreboard objectives remove {OBJECTIVE}")
    created=rcon.command(f"scoreboard objectives add {OBJECTIVE} health")
    results["readonly_create_response"]=created
    if "error" in created.lower() or "unknown" in created.lower():
        raise AssertionError(f"Could not create read-only criterion: {created}")
    for arm in ("typed","fastobj","delegate","native"):
        results[arm+"_readonly_reply"]=invoke(rcon,arm,4)
    rcon.command(f"scoreboard objectives remove {OBJECTIVE}")
    rcon.command(f"scoreboard objectives add {OBJECTIVE} dummy")
    return results


def run_boot(index: int, artifacts: dict, *,
             diagnostic: bool, assignments: dict | None = None) -> dict:
    workdir = RUN_ROOT / f"ci-attr015-{'diag' if diagnostic else 'timing'}-{index:02d}"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(FABRIC_BASE, workdir)
    mods = workdir / "mods"
    mods.mkdir(exist_ok=True)
    for k in ("api", "compiler"):
        path = Path(artifacts[k])
        shutil.copy2(path, mods / path.name)
    prepare_fixture(workdir)
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    setup_server_properties(workdir, port, rcon_port, password)
    env = dict(os.environ)
    # No fusion, scheduler instrumentation, bytecode, macro or JFR.
    # Phase counters are enabled ONLY in this separate diagnostic JVM.
    env.update({
        "FC_WRAPPER_PROBE": "true",
        "FC_SCORE_ADD_PROTOTYPE": "true",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_SCORE_ADD_ATTRIBUTION": "true",
        "FC_SCORE_ADD_PHASE_TIMERS": str(diagnostic).lower(),
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES": "false",
        "FC_FUNCTION_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHEDULER_RESEARCH": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
    })
    record = {
        "index": index, "phase": "diagnostic" if diagnostic else "timing",
        "status": "started", "host_before": snapshot_host(), "blocks": [],
    }
    if assignments is not None:
        record["assignment"] = assignments
    logfile = OUT / f"boot-{'diag' if diagnostic else 'timing'}-{index:02d}.log"
    print(f"SCHED-COMP-015 BOOT {index} diagnostic={diagnostic}",flush=True)
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            ["java", *stable.JVM_ARGS, "-jar",
             str(workdir / "fabric-server-launch.jar"), "nogui"],
            cwd=workdir, env=env, stdin=subprocess.PIPE,
            stdout=log, stderr=subprocess.STDOUT,
        )
        rcon = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=180)
            if PACK not in rcon.command("datapack list enabled"):
                raise AssertionError("Missing generated attribution datapack")
            status = rcon.command("functioncompiler status")
            if ("wrapped=true" not in status
                    or "score_add_prototype_enabled=true" not in status
                    or "fused_region_prototype_enabled=false" not in status
                    or "score_add_attr_enabled=true" not in status):
                raise AssertionError(f"Unexpected compiler configuration: {status}")
            if "arch_counters_enabled=false" not in status:
                raise AssertionError(f"Scheduler counters must be disabled: {status}")
            record["activation"] = compilation_gate(rcon)
            for cmd in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1",
            ):
                rcon.command(cmd)
            pid, tid = process.pid, server_tid(process.pid)
            if diagnostic:
                record["diagnostic"]=diagnostic_arm(rcon,PRIMARY_LENGTH)
                record["semantics"]=semantic_guard(rcon)
                record["diagnostic_valid"]=True
            else:
                # Existing A/A validated qualification workload and plateau.
                # Even the research stage timers are OFF in every timed arm.
                record["qualification"] = stable.warmup_server(rcon, pid, tid)
                for arm in NAMESPACES:
                    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
                    for _ in range(PREWARM_PER_ARM):
                        invoke(rcon, arm, PRIMARY_LENGTH)
                    exact_work(rcon, PREWARM_PER_ARM, PRIMARY_LENGTH, arm)
                for block in assignments["blocks"]:
                    samples = []
                    for j, arm in enumerate(block["arms"]):
                        sample = measure_window(rcon, pid, tid, arm, PRIMARY_LENGTH,
                                                TIMING_CALLS_PER_WINDOW)
                        sample["slot"] = j
                        samples.append(sample)
                    record["blocks"].append({
                        "kind": block["kind"],
                        "orientation": block["orientation"], "windows": samples,
                    })
            record["status"] = "complete"
            record["host_after"] = snapshot_host()
        finally:
            if rcon is not None:
                try:
                    rcon.command("stop")
                except (OSError, RuntimeError):
                    pass
                rcon.close()
            try:
                process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return record


def measure_window(rcon: Rcon, pid: int, tid: int, arm: str,
                   length: int, calls: int) -> dict:
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    cpu0, clock = server_cpu_time_ns(pid, tid)
    delay0 = cpu_run_delay(pid, tid)
    host0 = snapshot_host()
    started = time.perf_counter_ns()
    for _ in range(calls):
        invoke(rcon, arm, length)
    elapsed = time.perf_counter_ns() - started
    host1 = snapshot_host()
    delay1 = cpu_run_delay(pid, tid)
    cpu1, clock1 = server_cpu_time_ns(pid, tid)
    if clock != clock1 or cpu1 <= cpu0:
        raise AssertionError("Invalid server thread CPU counter")
    integrity = exact_work(rcon, calls, length, arm)
    cpu = cpu1 - cpu0
    waited = (max(0, delay1 - delay0)
              if delay0 is not None and delay1 is not None else None)
    c0, c1 = host0.get("cgroup_cpu_stat", {}), host1.get("cgroup_cpu_stat", {})
    throttles = (c1["nr_throttled"] - c0["nr_throttled"]
                 if "nr_throttled" in c0 and "nr_throttled" in c1 else None)
    return {
        "arm": arm, "length": length, "calls": calls,
        "cpu_clock": clock,
        "server_thread_cpu_ns": cpu,
        "cpu_ns_per_command": cpu / (length * calls),
        "rcon_window_wall_seconds": elapsed / 1e9,
        "cgroup_nr_throttled_delta": throttles,
        "runqueue_delay_fraction": (
            waited / (waited + cpu) if waited is not None else None),
        **integrity,
    }


def block_contrast(block: dict, assignment: dict) -> float:
    if (block["kind"] != assignment["kind"]
            or block["orientation"] != assignment["orientation"]):
        raise AssertionError("Wrong crossover block observed")
    if len(block["windows"]) != 4:
        raise AssertionError("Missing crossover windows")
    arms = FAMILIES[block["kind"]]
    observed = [w["arm"] for w in block["windows"]]
    if observed != assignment["arms"]:
        raise AssertionError("Arm order violates preregistration")
    log_a = [math.log(w["cpu_ns_per_command"])
             for w in block["windows"] if w["arm"] == arms[0]]
    log_b = [math.log(w["cpu_ns_per_command"])
             for w in block["windows"] if w["arm"] == arms[1]]
    if len(log_a) != 2 or len(log_b) != 2:
        raise AssertionError("Unbalanced crossover measurements")
    return 100 * (statistics.mean(log_b) - statistics.mean(log_a))


def analyze(boots: list[dict], assignments: tuple[dict, ...]) -> dict:
    if len(boots) != N_BOOTS or len(assignments) != N_BOOTS:
        raise AssertionError("Incomplete independent JVM campaign")
    per_boot = []
    for i, boot in enumerate(boots):
        if boot["index"] != i or boot["status"] != "complete":
            raise AssertionError("Missing or reordered JVM")
        if len(boot["blocks"]) != len(KINDS):
            raise AssertionError("Wrong number of paired contrasts")
        expected = {b["kind"]: b for b in assignments[i]["blocks"]}
        observed = {}
        for block in boot["blocks"]:
            if not all(w["exact_work"] for w in block["windows"]):
                raise AssertionError("Score integrity failure")
            observed[block["kind"]] = block_contrast(block, expected[block["kind"]])
        if set(observed) != set(KINDS):
            raise AssertionError("Missing comparison")
        windows = [w for block in boot["blocks"] for w in block["windows"]]
        quality = (
            boot["qualification"]["qualification_stable"]
            and all(w["cgroup_nr_throttled_delta"] == 0 for w in windows)
            and all(w["runqueue_delay_fraction"] is not None
                    and w["runqueue_delay_fraction"] <= stable.MAX_RUNQUEUE_DELAY_FRACTION
                    for w in windows)
        )
        per_boot.append({"boot": i, "quality": quality, "contrasts": observed})
    kinds = {}
    for kind in KINDS:
        values = [x["contrasts"][kind] for x in per_boot]
        kinds[kind] = {
            "n_boots": N_BOOTS,
            "median_signed_log_percent": statistics.median(values),
            "exact_median_interval": exact_median_interval(values),
            "boot_contrasts": values,
        }
    failed = [v["boot"] for v in per_boot if not v["quality"]]
    null = kinds["negative"]["exact_median_interval"]
    null_pass = null["lower"] <= 0 <= null["upper"]
    if failed:
        verdict = "inconclusive_quality"
    elif not null_pass:
        verdict = "invalid_a_a_control"
    else:
        verdict = "valid_attribution_comparison"
    return {
        "verdict": verdict,
        "quality_failed_boots": failed,
        "negative_interval_includes_zero": null_pass,
        "per_boot": per_boot,
        "by_kind": kinds,
        "derived_exploratory_native_to_typed": {
            "per_boot_signed_log_percent": [
                b["contrasts"]["delegating_vs_native"]+
                b["contrasts"]["typed_vs_delegating"] for b in per_boot
            ],
            "caveat":"Sum of log ratios from separate crossover blocks, exploratory only"
        },
        "prohibited_inference": (
            "Phase wall time with nanoTime probes cannot be subtracted from"
            " uninstrumented server-thread CPU. This only tests the stated"
            " literal ScoreAdd paths and does not isolate Brigadier as a whole."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("diagnostic", "timing"), required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{args.phase}.json"
    assignments = plan()
    record = {
        "experiment": EXPERIMENT, "phase": args.phase,
        "status": "started", "boots": [],
        "preregistration": {
            "seed": SEED, "n_independent_timing_boots": N_BOOTS,
            "diagnostic_separate_from_timing": True,
            "lengths_diagnostic": LENGTHS, "length_primary": PRIMARY_LENGTH,
            "calls_per_window": TIMING_CALLS_PER_WINDOW,
            "prewarm_per_arm": PREWARM_PER_ARM,
            "comparisons": KINDS,
            "assignments": assignments,
            "independent_unit": "JVM boot",
            "diagnostic": "objective resolution, score mutation, feedback wall-time with probes enabled",
            "native_state": "same literal scoreboard increment repeated n times",
            "negative_control": "native vs byte-identical native namespace",
            "no_alternative_scheduler_arm": True,
            "no_fusion":True,
            "phase_timers_off_during_timing":True,
            "no_runtime_metrics_during_cpu_timing": True,
            "retain_all_windows": True,
        },
    }
    target.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    try:
        artifacts = stage_artifacts()
        record["artifact_hashes"] = {
            k: v for k,v in artifacts.items() if k.endswith("_sha256")
        }
        if args.phase == "diagnostic":
            record["boots"].append(run_boot(0, artifacts, diagnostic=True))
            if not record["boots"][0]["diagnostic_valid"]:
                raise AssertionError("Queue/quota diagnostic not valid")
        else:
            prior = json.loads((OUT / "diagnostic.json").read_text())
            if prior["status"] != "complete":
                raise AssertionError("Diagnostic preflight not complete")
            for i, assignment in enumerate(assignments):
                boot = run_boot(i, artifacts, diagnostic=False, assignments=assignment)
                record["boots"].append(boot)
                target.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
            record["analysis"] = analyze(record["boots"], assignments)
        record["status"] = "complete"
        print("SCHED-COMP-015 COMPLETE " + json.dumps({
            "phase":args.phase,"status":record["status"],
            "diagnostic":record["boots"][0].get("diagnostic") if args.phase=="diagnostic" else None,
            "analysis":record.get("analysis"),
        }), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = repr(exc)
        raise
    finally:
        target.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
