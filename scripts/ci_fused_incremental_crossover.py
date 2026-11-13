#!/usr/bin/env python3
"""SCHED-COMP-010: fused-region execution versus typed ScoreAdd, same JVM.

All three identical 2000-command functions are ScoreAdd-specialized; only the
treatment namespace is allowlisted for fused regions via an opt-in test flag.
The same crossover plan/boot-level estimator as SCHED-BENCH-008 is reused.
This isolates the narrow typed ScoreAdd callback, NOT a scheduler replacement.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess

import ci_benchmark_crossover as crossover
import ci_compiler_off_stability as stable
from ci_native_cross_mode_attribution import (
    ROOT, RUN_ROOT, FABRIC_BASE, PACK, OBJECTIVE, HOLDER, GATE,
    COMMANDS_PER_CALL, stage_artifacts, make_fixture, setup_server_properties,
    server_tid,
)
from ci_smoke_server import Rcon, unused_port, wait_for_rcon

EXPERIMENT = "SCHED-COMP-010"
OUT = ROOT / "build" / "benchmarks" / EXPERIMENT
REPORT = OUT / "results.json"
BASE = "fc_bench_scoreonly_a"
NULL = "fc_bench_scoreonly_null"
OPT = "fc_bench_fused"
NAMESPACES = (BASE, NULL, OPT)
FUNCTIONS = {
    "score_a": f"{BASE}:score",
    "score_null": f"{NULL}:score",
    "score_treatment": f"{OPT}:score",
}


def compiler_config() -> dict:
    return {
        "enabled": True, "score_add": True, "fused_regions": True,
        "selective_macros": False, "tiered_bytecode": False,
        "tiered_threshold": 5, "excluded_namespaces": [],
    }


def make_fixture_with_three_paths(workdir: Path) -> None:
    make_fixture(workdir)
    function_dir = workdir / "world" / "datapacks" / PACK / "data" / PACK / "function"
    native = (function_dir / "score.mcfunction").read_text(encoding="utf-8")
    if len(native.splitlines()) != COMMANDS_PER_CALL:
        raise AssertionError("Unexpected number of source command lines")
    for namespace in NAMESPACES:
        target = workdir / "world" / "datapacks" / PACK / "data" / namespace / "function"
        target.mkdir(parents=True, exist_ok=True)
        (target / "score.mcfunction").write_text(native, encoding="utf-8")
    # Equal single-function call overhead for all three arms. Normalization
    # uses 2000 exactly verified scoreboard increments, NOT 2000 total lines
    # (each invocation also executes one alias 'function' line).
    for alias, full_id in FUNCTIONS.items():
        (function_dir / f"{alias}.mcfunction").write_text(
            f"function {full_id}\n", encoding="utf-8"
        )
    config_dir = workdir / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "function-compiler.json").write_text(
        json.dumps(compiler_config(), indent=2) + "\n", encoding="utf-8"
    )


def specialization_stats(rcon: Rcon) -> dict:
    result = {}
    for namespace in NAMESPACES:
        key = f"{namespace}:score"
        response = rcon.command(f"functioncompiler stats {key}")
        score = re.search(r"score_add_compiled=(\d+)", response)
        fused = re.search(r"fused_regions_compiled=(\d+)", response)
        if score is None or fused is None:
            raise AssertionError(f"Missing per-function counter: {response!r}")
        result[key] = {"score_add_compiled": int(score.group(1)),
                       "fused_regions_compiled": int(fused.group(1))}
    if any(value["score_add_compiled"] <= 0 for value in result.values()):
        raise AssertionError("All three arms must compile typed ScoreAdd")
    if any(result[f"{name}:score"]["fused_regions_compiled"] != 0
           for name in (BASE, NULL)):
        raise AssertionError("ScoreAdd-only control unexpectedly fused")
    if result[f"{OPT}:score"]["fused_regions_compiled"] <= 0:
        raise AssertionError("Fused treatment did not compile")
    return result


def run_boot(index: int, plan: dict, artifacts: dict) -> dict:
    workdir = RUN_ROOT / f"ci-comp010-{index:02d}"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(FABRIC_BASE, workdir)
    mods = workdir / "mods"
    mods.mkdir(exist_ok=True)
    for name in ("api", "compiler"):
        path = Path(artifacts[name])
        shutil.copy2(path, mods / path.name)
    make_fixture_with_three_paths(workdir)
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    setup_server_properties(workdir, port, rcon_port, password)
    env = dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE": "true",
        "FC_SCORE_ADD_PROTOTYPE": "true",
        "FC_FUSED_REGION_PROTOTYPE": "true",
        "FC_FUSED_REGION_ONLY_NAMESPACE": OPT,
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_FUNCTION_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHEDULER_RESEARCH": "false",
    })
    cmd = ["java", *stable.JVM_ARGS, "-jar",
           str(workdir / "fabric-server-launch.jar"), "nogui"]
    result = {"index": index, "plan": plan, "status": "started",
              "host_at_boot": stable.snapshot_host(), "blocks": []}
    logpath = OUT / f"boot-{index:02d}-compiler.log"
    print(f"BOOT {index+1}/{crossover.N_BOOTS} real fusion versus ScoreAdd crossover", flush=True)
    with logpath.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=workdir, env=env, stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT)
        rcon = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=180)
            if PACK not in rcon.command("datapack list enabled"):
                raise AssertionError("Generated benchmark datapack not loaded")
            status = rcon.command("functioncompiler status")
            if "wrapped=true" not in status or "score_add_prototype_enabled=true" not in status:
                raise AssertionError(f"Compiler optimization not enabled: {status}")
            if "fused_region_prototype_enabled=true" not in status or "bytecode_region_prototype_enabled=true" in status:
                raise AssertionError(f"Unexpected second optimization: {status}")
            result["compiler_status"] = status
            for command in (
                f"scoreboard objectives add {OBJECTIVE} dummy",
                f"scoreboard players set {HOLDER} {OBJECTIVE} 0",
                f"scoreboard players set {GATE} {OBJECTIVE} 1",
            ):
                rcon.command(command)
            result["compiled_before_warmup"] = specialization_stats(rcon)
            pid, tid = process.pid, server_tid(process.pid)
            result["family_prewarm"] = crossover.score_warmup(rcon)
            result["qualification"] = stable.warmup_server(rcon, pid, tid)
            ordinal = 0
            for block in plan["blocks"]:
                measured = {"kind": block["kind"],
                            "orientation": block["orientation"], "windows": []}
                for family in block["functions"]:
                    w = crossover.measured_window(rcon, pid, tid, family, ordinal)
                    measured["windows"].append(w)
                    print(f"WINDOW boot={index} kind={block['kind']} "
                          f"family={family} ns/increment={w['cpu_ns_per_source_line']:.2f}",
                          flush=True)
                    ordinal += 1
                result["blocks"].append(measured)
            result["compiled_after_timings"] = specialization_stats(rcon)
            result["host_after_boot"] = stable.snapshot_host()
            result["status"] = "complete"
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
    return result


def analyze(boots: list[dict]) -> dict:
    # Boot-level contrast B=fused ScoreAdd versus A=typed ScoreAdd alone.
    result = crossover.analyze(boots)
    null = result["by_kind"]["negative"]["exact_median_interval"]
    effect = result["by_kind"]["positive"]["exact_median_interval"]
    negative_valid = null["lower"] <= 0 <= null["upper"]
    if result["quality_failed_boot_ids"]:
        verdict = "inconclusive_quality"
    elif not negative_valid:
        verdict = "invalid_negative_control"
    elif effect["upper"] < 0:
        verdict = "fusion_faster_than_scoreadd_supported"
    elif effect["lower"] > 0:
        verdict = "fusion_slower_than_scoreadd_supported"
    else:
        verdict = "fusion_incremental_effect_inconclusive"
    result["verdict"] = verdict
    result["fusion_incremental_interval_log_percent"] = effect
    result["analysis_note"] = (
        "B is fused ScoreAdd; A is typed ScoreAdd-only with identical bodies. "
        "No scheduler replacement or whole-JVM speedup claim."
    )
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plans = crossover.schedule()
    record = {
        "experiment": EXPERIMENT, "status": "started",
        "preregistration": {
            "parent_design": "SCHED-BENCH-008",
            "plan": plans, "n_independent_boots": crossover.N_BOOTS,
            "control": "two byte-identical ScoreAdd-only functions in separate namespaces",
            "treatment": "byte-identical ScoreAdd with fused region allowlisted by namespace",
            "alias_overhead": "one equal function invocation per arm",
            "primary_metric": "server-thread CPU ns per 2000 exact score increments",
            "contrast": "100*mean(log(B CPU))-100*mean(log(A CPU)) per boot",
            "decision": "95%+ median interval below 0 = faster; above 0 = slower; otherwise inconclusive",
            "quality": "all 12 boot warmups qualified; all timed windows zero throttle and <=25% runqueue delay",
            "negative_control": "interval includes zero",
            "activation_gate": "score_add_compiled>0 in all functions; fused_regions_compiled>0 only in fused namespace",
            "score_add_metrics_during_timings": False,
            "no_jfr_during_timings": True,
            "all_windows_retained": True,
            "no_production_changes": True,
        },
        "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    try:
        artifacts = stage_artifacts()
        record["artifact_hashes"] = {k:v for k,v in artifacts.items() if k.endswith("_sha256")}
        for i, plan in enumerate(plans):
            result = run_boot(i, plan, artifacts)
            record["boots"].append(result)
            REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        record["analysis"] = analyze(record["boots"])
        record["status"] = "complete"
        print("SCHED-COMP-010 COMPLETE " + json.dumps({
            "verdict": record["analysis"]["verdict"],
            "by_kind": record["analysis"]["by_kind"],
            "quality_failed_boot_ids": record["analysis"]["quality_failed_boot_ids"],
        }), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["failure"] = repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
