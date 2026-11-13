#!/usr/bin/env python3
"""SCHED-ARCH-013: vanilla-queue architecture attribution, NOT replacement.

Stage A (diagnostic): count observed nonempty queue-loop visits and real
incrementCost debits for identical command bodies. These counters are opt-in;
they are deliberately disabled during CPU timing.
Stage B: twelve independent Minecraft JVMs, each containing all four execution
paths: A native, N byte-identical native placebo, B ScoreAdd-only, C fused
ScoreAdd, with ABBA/BAAB blocks and boot-level inference. D, an alternative
scheduler, does not exist and is explicitly NOT estimated by this campaign.
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

from ci_compiler_off_paired import exact_median_interval
import ci_compiler_off_stability as stable
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    stage_artifacts, make_fixture, setup_server_properties,
    server_tid, server_cpu_time_ns, cpu_run_delay, snapshot_host, read_score,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon

EXPERIMENT = "SCHED-ARCH-013"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
SEED = 13013
N_BOOTS = 12
DIAGNOSTIC_CALLS = 24
TIMING_CALLS_PER_WINDOW = 220
PREWARM_PER_ARM = 120
LENGTHS = (4, 16, 256, 2000)
PRIMARY_LENGTH = 2000
KINDS = ("negative", "typed_vs_native", "fusion_vs_typed")
NAMESPACES = {
    "native": "fc_arch_native",
    "null": "fc_arch_native_null",
    "typed": "fc_arch_typed",
    "fused": "fc_arch_fused",
}
FAMILIES = {
    "negative": ("native", "null"),
    "typed_vs_native": ("native", "typed"),
    "fusion_vs_typed": ("typed", "fused"),
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
        "fused_regions": True,
        "selective_macros": False,
        "tiered_bytecode": False,
        "tiered_threshold": 5,
        "excluded_namespaces": [NAMESPACES["native"], NAMESPACES["null"]],
    }, indent=2) + "\n", encoding="utf-8")


def plan() -> tuple[dict, ...]:
    rng = random.Random(SEED)
    # 3! = 6 block orders, repeated twice across 12 boots. Independently
    # balance ABBA/BAAB for every contrast. Reproducible before measurements.
    orderings = rng.sample(list(itertools.permutations(KINDS))*2, N_BOOTS)
    orientations = {
        kind: rng.sample(["ABBA", "BAAB"]*(N_BOOTS//2), N_BOOTS)
        for kind in KINDS
    }
    return tuple({
        "boot": i,
        "blocks": [{
            "kind": kind,
            "orientation": orientations[kind][i],
            "arms": [FAMILIES[kind][0 if token == "A" else 1]
                     for token in orientations[kind][i]],
        } for kind in orderings[i]]
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
            expected_score = length if arm in ("typed", "fused") else 0
            if counts["score_add_compiled"] != expected_score:
                raise AssertionError(f"Wrong typed activation: {fid} {counts} vs {expected_score}")
            expected_fused = 1 if arm == "fused" and length >= 2 else 0
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


def diagnostic_arm(rcon: Rcon, arm: str, length: int) -> dict:
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    before = rcon.command("functioncompiler status")
    for _ in range(DIAGNOSTIC_CALLS):
        invoke(rcon, arm, length)
    integrity = exact_work(rcon, DIAGNOSTIC_CALLS, length, arm)
    after = rcon.command("functioncompiler status")
    measured = {
        "arm": arm, "length": length,
        "work": integrity,
        "calls": DIAGNOSTIC_CALLS,
        "instrumentation": "diagnostic-only, includes RCON overhead",
        "queue_nonempty_visit_delta": (
            parse_stat(after, "arch_nonempty_queue_visits") -
            parse_stat(before, "arch_nonempty_queue_visits")
        ),
        "quota_debit_delta": (
            parse_stat(after, "arch_quota_debits") -
            parse_stat(before, "arch_quota_debits")
        ),
    }
    if measured["quota_debit_delta"] < DIAGNOSTIC_CALLS * length:
        raise AssertionError(f"Missing vanilla quota debits for {arm}/{length}")
    return measured


def run_boot(index: int, artifacts: dict, *,
             diagnostic: bool, assignments: dict | None = None) -> dict:
    workdir = RUN_ROOT / f"ci-arch013-{'diag' if diagnostic else 'timing'}-{index:02d}"
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
    # No timed-path metrics, bytecode, alternate scheduler, selective macros,
    # GC logging or JFR. Only these three paths differ by namespace.
    env.update({
        "FC_WRAPPER_PROBE": "true",
        "FC_SCORE_ADD_PROTOTYPE": "true",
        "FC_FUSED_REGION_PROTOTYPE": "true",
        "FC_FUSED_REGION_ONLY_NAMESPACE": NAMESPACES["fused"],
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES": "false",
        "FC_FUNCTION_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHEDULER_RESEARCH": "false",
        "FC_SCHED_ARCH_COUNTERS": str(diagnostic).lower(),
    })
    record = {
        "index": index, "phase": "diagnostic" if diagnostic else "timing",
        "status": "started", "host_before": snapshot_host(), "blocks": [],
    }
    if assignments is not None:
        record["assignment"] = assignments
    logfile = OUT / f"boot-{'diag' if diagnostic else 'timing'}-{index:02d}.log"
    print(f"ARCH BOOT {index} diagnostic={diagnostic}", flush=True)
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
                    or "fused_region_prototype_enabled=true" not in status):
                raise AssertionError(f"Unexpected compiler configuration: {status}")
            flag = ("true" if diagnostic else "false")
            if f"arch_counters_enabled={flag}" not in status:
                raise AssertionError(f"Incorrect diagnostic counter flag: {status}")
            record["activation"] = compilation_gate(rcon)
            for cmd in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1",
            ):
                rcon.command(cmd)
            pid, tid = process.pid, server_tid(process.pid)
            if diagnostic:
                summaries = []
                for length in LENGTHS:
                    for arm in NAMESPACES:
                        summaries.append(diagnostic_arm(rcon, arm, length))
                record["diagnostic"] = summaries
                for length in (16, 256, 2000):
                    by_arm = {item["arm"]: item for item in summaries
                              if item["length"] == length}
                    if not (by_arm["fused"]["queue_nonempty_visit_delta"] <
                            by_arm["typed"]["queue_nonempty_visit_delta"]):
                        raise AssertionError(f"Fusion did not reduce queue visit count at {length}")
                    # All variants must account for every original command;
                    # allow constant RCON/manager costs, never fewer debits.
                    if (by_arm["fused"]["quota_debit_delta"] <
                            DIAGNOSTIC_CALLS * length):
                        raise AssertionError("Fusion failed to preserve command quota")
                record["diagnostic_valid"] = True
            else:
                # Existing A/A validated qualification workload and plateau.
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
        verdict = "valid_a_b_c_comparison"
    return {
        "verdict": verdict,
        "quality_failed_boots": failed,
        "negative_interval_includes_zero": null_pass,
        "per_boot": per_boot,
        "by_kind": kinds,
        "prohibited_inference": (
            "D-C alternative scheduler benefit is UNMEASURED: no D backend exists. "
            "Queue visits are event counts, not CPU time attributable to scheduling."
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
            "observed_queue_metric": "nonempty queue-loop visits (not exclusive scheduler CPU)",
            "native_state": "same literal scoreboard increment repeated n times",
            "negative_control": "native namespace versus byte-identical native namespace",
            "no_alternative_scheduler_arm": True,
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
        print("SCHED-ARCH-013 COMPLETE " + json.dumps({
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
