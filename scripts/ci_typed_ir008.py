#!/usr/bin/env python3
"""COMPILER-IR-008: native Fabric semantic comparison and bounded CPU screen.

Four fresh actual Minecraft 26.3 / Java25 JVMs on the same disposable pack:
  native (unwrapped), existing fused interpreter, typed IR interpreter,
  and ASM-direct typed IR. Exact effects and low-quota snapshots must match.
The CPU reading is an unpaired descriptive *screen*, not a production gain
claim or promotion gate. No other research diagnostics run during CPU timing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

from ci_smoke_server import ROOT, RUNS, Rcon, unused_port, wait_for_rcon

OUT = ROOT / "build/reports/COMPILER-IR-008"
MODES = ("native", "fused", "interpreted", "bytecode")
PACK = "fc_typed_ir_008"
NS = "fc_ir"
OBJ = "fc_ir"
QUOTAS = (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 32)
BENCH_OPS = 64
WARMUP_CALLS = 18
BENCH_CALLS = 160
FUNCTIONS = {
    "chain": [
        "scoreboard players set #x fc_ir 3",
        "scoreboard players add #x fc_ir 7",
        "scoreboard players remove #x fc_ir 2",
        "scoreboard players add #x fc_ir 5",
        "scoreboard players set #y fc_ir -4",
        "scoreboard players add #y fc_ir 1",
    ],
    "barrier": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "function fc_ir:helper",
        "scoreboard players add #x fc_ir 5",
        "scoreboard players remove #x fc_ir 1",
    ],
    "helper": ["scoreboard players add #x fc_ir 10"],
    "conditional": [
        "scoreboard players set #x fc_ir 2",
        "scoreboard players add #x fc_ir 3",
        "execute if score #x fc_ir matches 5 run scoreboard players add #x fc_ir 7",
        "scoreboard players remove #x fc_ir 2",
        "scoreboard players add #x fc_ir 1",
    ],
    "operation": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "scoreboard players operation #x fc_ir += #y fc_ir",
        "scoreboard players add #x fc_ir 4",
        "scoreboard players remove #x fc_ir 1",
    ],
    "overflow": [
        "scoreboard players set #x fc_ir 2147483646",
        "scoreboard players add #x fc_ir 2",
        "scoreboard players remove #x fc_ir 1",
    ],
    "missing": [
        "scoreboard players add #m fc_missing 1",
        "scoreboard players add #m fc_missing 1",
    ],
    "readonly": [
        "scoreboard players add #m fc_readonly 1",
        "scoreboard players add #m fc_readonly 1",
    ],
    "bench64": ["scoreboard players add #bench fc_ir 1"] * BENCH_OPS,
}


def fixture(directory: Path) -> None:
    root = directory / "world/datapacks" / PACK
    funcs = root / "data" / NS / "function"
    funcs.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR-008 disposable vanilla semantic comparator",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, commands in FUNCTIONS.items():
        (funcs / f"{name}.mcfunction").write_text(
            "\n".join(commands) + "\n", encoding="utf-8")


def score(rcon: Rcon, holder: str, objective: str = OBJ) -> int:
    text = rcon.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", text)
    if not match:
        raise AssertionError(f"Score {holder}/{objective} not readable: {text!r}")
    return int(match.group(1))


def run_function(rcon: Rcon, name: str) -> str:
    text = rcon.command(f"function {NS}:{name}")
    if not text.startswith("Running function "):
        raise AssertionError(f"{name} not invoked: {text!r}")
    return text


def reset(rcon: Rcon) -> None:
    for holder in ("#x", "#y", "#result"):
        rcon.command(f"scoreboard players set {holder} {OBJ} 0")


def snapshot(rcon: Rcon) -> dict:
    return {"x": score(rcon, "#x"), "y": score(rcon, "#y"),
            "result": score(rcon, "#result")}


def server_cpu_ns(pid: int) -> int:
    root = Path(f"/proc/{pid}/task")
    threads = [child for child in root.iterdir()
               if (child / "comm").read_text().strip() == "Server thread"]
    if len(threads) != 1:
        raise AssertionError(f"Expected one Minecraft Server thread, got {len(threads)}")
    schedstat = (threads[0] / "schedstat").read_text().split()
    if len(schedstat) < 1 or int(schedstat[0]) <= 0:
        raise AssertionError("Linux running-CPU clock not available")
    return int(schedstat[0])


def options(mode: str) -> dict[str, str]:
    assert mode in MODES
    return {
        "FC_WRAPPER_PROBE": str(mode != "native").lower(),
        "FC_SCORE_ADD_PROTOTYPE": str(mode == "fused").lower(),
        "FC_FUSED_REGION_PROTOTYPE": str(mode == "fused").lower(),
        "FC_FUSED_REGION_ONLY_NAMESPACE": NS,
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_TYPED_IR_MODE": mode if mode in ("interpreted", "bytecode") else "",
        "FC_TYPED_IR_NAMESPACE": NS if mode in ("interpreted", "bytecode") else "",
        "FC_TYPED_IR_DIAGNOSTICS": "true",  # semantic phase only, not used for promotion
    }


def run(mode: str) -> dict:
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    directory = RUNS / ("ci-ir008-" + mode)
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    fixture(directory)
    (directory / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(18)
    (directory / "server.properties").write_text("\n".join((
        "online-mode=false", "enable-rcon=true",
        "broadcast-rcon-to-ops=false", "level-name=world",
        "level-type=minecraft:flat", "pause-when-empty-seconds=-1",
        "view-distance=2", "simulation-distance=2",
        "max-tick-time=-1", "max-players=1",
        f"server-port={port}", f"rcon.port={rcon_port}",
        f"rcon.password={password}",
    )) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(options(mode))
    command = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={directory.relative_to(ROOT)}",
        "runServer",
    ]
    output_log = OUT / f"{mode}.server.log"
    report = {"mode": mode, "status": "started", "cases": {},
              "semantic_verified": False, "compiler_status": None}
    with output_log.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.PIPE)
        client = None
        try:
            client = wait_for_rcon(process, rcon_port, password, timeout_seconds=240)
            reply = client.command("datapack list enabled")
            if PACK not in reply:
                raise AssertionError(f"IR-008 original fixture was not enabled: {reply!r}")
            client.command(f"scoreboard objectives add {OBJ} dummy")
            client.command("scoreboard objectives add fc_readonly health")
            client.command("gamerule sendCommandFeedback false")
            client.command("gamerule minecraft:max_command_sequence_length 65536")
            for name in ("chain", "barrier", "conditional", "operation", "overflow"):
                reset(client)
                client.command(f"scoreboard players set #y {OBJ} 2")
                run_function(client, name)
                report["cases"][name] = snapshot(client)
            if report["cases"]["chain"]["x"] != 13 or report["cases"]["chain"]["y"] != -3:
                raise AssertionError("IR chain arithmetic source fixture incorrect")
            if report["cases"]["barrier"]["x"] != 17:
                raise AssertionError("Vanilla nested function barrier didn't run")
            if report["cases"]["conditional"]["x"] != 11:
                raise AssertionError("Vanilla conditional fallback didn't run")
            if report["cases"]["operation"]["x"] != 8:
                raise AssertionError("Scoreboard operation barrier didn't run")
            if report["cases"]["overflow"]["x"] != 2147483647:
                raise AssertionError("Signed 32-bit overflow semantics incorrect")
            # Result callback is a separate source of semantic observation.
            reset(client)
            client.command("execute store result score #result fc_ir "
                           "run function fc_ir:chain")
            report["cases"]["store_result"] = snapshot(client)
            # An invalid objective must route through the retained original
            # parsed command; adding it at runtime must then activate direct IR.
            run_function(client, "missing")
            if "fc_missing" in client.command("scoreboard objectives list"):
                raise AssertionError("Invalid objective unexpectedly appeared")
            report["cases"]["missing_before_create"] = "objective_absent"
            client.command("scoreboard objectives add fc_missing dummy")
            run_function(client, "missing")
            report["cases"]["missing_after_create"] = score(client, "#m", "fc_missing")
            if report["cases"]["missing_after_create"] != 2:
                raise AssertionError("Runtime objective creation didn't reenable typed path")
            run_function(client, "readonly")
            report["cases"]["readonly"] = (
                client.command("scoreboard players get #m fc_readonly"))
            for quota in QUOTAS:
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                run_function(client, "chain")
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"quota_{quota}"] = snapshot(client)
            # Status has diagnostic counters. They are not enabled in any
            # production default, and are deliberately NOT CPU evidence.
            report["compiler_status"] = client.command("functioncompiler ir008")
            if mode in ("interpreted", "bytecode"):
                expected = "IR008 mode=" + mode
                if expected not in report["compiler_status"]:
                    raise AssertionError(f"IR mode wasn't activated: {report['compiler_status']!r}")
                if re.search(r"executed_steps=0(?:\s|$)", report["compiler_status"]):
                    raise AssertionError("No direct IR instructions executed")
                if mode == "bytecode" and re.search(
                        r"bytecode_regions=0(?:\s|$)", report["compiler_status"]):
                    raise AssertionError("ASM backend not generated")
                if re.search(r"fallback_steps=0(?:\s|$)", report["compiler_status"]):
                    raise AssertionError("Original-missing-objective fallback not exercised")
            report["semantic_verified"] = True
            report["status"] = "semantic_accepted"

            # Small unpaired CPU screen to detect catastrophic regressions,
            # NOT a paired speed claim. All modes execute the same 64 * 160
            # scoreboard writes and keep result/command metrics off.
            client.command("scoreboard players set #bench fc_ir 0")
            for _ in range(WARMUP_CALLS):
                run_function(client, "bench64")
            client.command("scoreboard players set #bench fc_ir 0")
            cpu_before = server_cpu_ns(process.pid)
            elapsed_before = time.monotonic_ns()
            for _ in range(BENCH_CALLS):
                run_function(client, "bench64")
            elapsed_ns = time.monotonic_ns() - elapsed_before
            cpu_delta = server_cpu_ns(process.pid) - cpu_before
            count = score(client, "#bench")
            expected_count = BENCH_CALLS * BENCH_OPS
            if count != expected_count or cpu_delta <= 0:
                raise AssertionError(f"Invalid benchmark work or CPU: {count}, {cpu_delta}")
            report["screen"] = {
                "calls": BENCH_CALLS, "operations_per_call": BENCH_OPS,
                "expected_writes": expected_count, "actual_final_score": count,
                "linux_server_thread_cpu_ns": cpu_delta,
                "rcon_interval_wall_ns": elapsed_ns,
                "sampling": "single independent JVM, instrumentation present",
                "causal_performance_claim": False,
            }
            report["status"] = "accepted"
            print("IR008_ARM " + json.dumps({
                "mode": mode, "cases": report["cases"],
                "compiler_status": report["compiler_status"],
                "cpu_ns": cpu_delta,
            }, sort_keys=True), flush=True)
        except BaseException as error:
            report["status"] = "invalid"
            report["failure"] = repr(error)
            raise
        finally:
            (OUT / f"{mode}.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
            if client:
                try:
                    client.command("stop")
                except (OSError, RuntimeError):
                    pass
                client.close()
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return report


def validate(results: list[dict]) -> dict:
    if [r["mode"] for r in results] != list(MODES):
        raise ValueError("IR-008 requires all four independent native JVM paths")
    if any(r["status"] != "accepted" or not r["semantic_verified"] for r in results):
        raise ValueError("IR-008 missing a valid native path")
    original = results[0]["cases"]
    for row in results[1:]:
        if row["cases"] != original:
            raise AssertionError(f"IR-008 parity mismatch: {row['mode']}: "
                                 f"{row['cases']} vs vanilla {original}")
        if row["screen"]["expected_writes"] != results[0]["screen"]["expected_writes"]:
            raise AssertionError("IR-008 benchmark work mismatch")
    return {
        "milestone": "COMPILER-IR-008",
        "status": "accepted",
        "native_parity": True,
        "original_path": "native Fabric",
        "comparison_paths": list(MODES),
        "cases": original,
        "cpu_screen_ns": {r["mode"]: r["screen"]["linux_server_thread_cpu_ns"] for r in results},
        "causal_speedup_established": False,
        "compiler_production_promotion": False,
        "note": "One unpaired CPU interval per mode with diagnostic compilation enabled; "
                "not a promotion test. Bytecode path emits ScoreAccess.add/set directly, "
                "while condition and scoreboard-operation barriers remain vanilla.",
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    partial = OUT / "results.json"
    result = {"milestone": "COMPILER-IR-008", "status": "started", "arms": []}
    try:
        for mode in MODES:
            record = run(mode)
            result["arms"].append(record)
            partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["summary"] = validate(result["arms"])
        result["status"] = "accepted"
    except BaseException as error:
        result["status"] = "invalid"
        result["error"] = repr(error)
        raise
    finally:
        partial.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("IR008_SUMMARY " + json.dumps(result["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
