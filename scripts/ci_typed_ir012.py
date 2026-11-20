#!/usr/bin/env python3
"""COMPILER-IR-012 native function-level resumable ASM scheduling research.

Four actual Minecraft 26.3 JVM semantic arms (native, interpreted,
same-bytecode scheduler OFF, same-bytecode scheduler ON). A bounded
CPU crossover uses two further native JVM boots, ABBA/BAAB direct ON/OFF
and same-path OFF/OFF controls; no production performance conclusion.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import statistics
import subprocess

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir008 import find_server_thread, server_cpu_ns

OUT = ROOT / "build/reports/COMPILER-IR-012"
PACK = "fc_typed_ir012"
OBJ = "fc_ir"
QUOTAS = (1, 2, 3, 4, 5, 6, 8, 10, 16, 32, 65, 130, 300)
SEMANTIC_MODES = ("native", "interpreted", "bytecode_off", "bytecode_on")
BOOTS = 2
PAIRS_PER_BOOT = 4
AA_PER_BOOT = 2
CALLS_PER_WINDOW = 120
WARMUP_PER_ARM = 60
SEED = 8012

MIXED = [
    "scoreboard players set #a fc_ir 3",
    "scoreboard players set #b fc_ir 2",
    "scoreboard players operation #a fc_ir += #b fc_ir",
    "execute if score #a fc_ir matches 5 run scoreboard players add #a fc_ir 4",
    "execute unless score #a fc_ir matches 5 run scoreboard players remove #a fc_ir 2",
    "scoreboard players operation #a fc_ir *= #b fc_ir",
    "scoreboard players operation #b fc_ir = #a fc_ir",
    "scoreboard players add #a fc_ir 3",
]
ADD = "scoreboard players add #x fc_ir 1"
FUNCTIONS = {
    "ir012_mixed": MIXED,
    "ir012_chunk_64": [ADD] * 64,
    "ir012_chunk_128": [ADD] * 128,
    "ir012_chunk_256": [ADD] * 256,
    "ir012_chunk_2000": [ADD] * 2000,
    "ir012_bad_tail_65": [ADD] * 65,
    "ir012_barrier": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "function fc_ir:ir012_helper",
        "scoreboard players add #x fc_ir 3",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir012_helper": ["scoreboard players add #x fc_ir 11"],
    "ir012_nested": [
        "scoreboard players set #x fc_ir 1",
        "function fc_ir:ir012_mixed",
        "scoreboard players add #x fc_ir 5",
    ],
    "ir012_missing_obj": [
        "scoreboard players add #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_ir012_missing 9",
        "scoreboard players add #x fc_ir 3",
    ],
}
EXPECTED = {
    "ir012_mixed": {"x": 0, "a": 17, "b": 14},
    "ir012_chunk_64": {"x": 64, "a": 0, "b": 0},
    "ir012_chunk_128": {"x": 128, "a": 0, "b": 0},
    "ir012_chunk_256": {"x": 256, "a": 0, "b": 0},
    "ir012_chunk_2000": {"x": 2000, "a": 0, "b": 0},
    "ir012_bad_tail_65": {"x": 65, "a": 0, "b": 0},
    "ir012_barrier": {"x": 21, "a": 0, "b": 0},
    "ir012_nested": {"x": 6, "a": 17, "b": 14},
    "ir012_missing_obj": {"x": 6, "a": 0, "b": 0},
}


def make_pack(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    funcs = root / "data/fc_ir/function"
    funcs.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR012 identical native/ASM function scheduling fixture",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, commands in FUNCTIONS.items():
        (funcs / f"{name}.mcfunction").write_text(
            "\n".join(commands) + "\n", encoding="utf-8")


def options(mode: str, crossover: bool = False) -> dict[str, str]:
    typed = mode in ("interpreted", "bytecode_off", "bytecode_on", "crossover")
    return {
        "FC_WRAPPER_PROBE": str(typed).lower(),
        "FC_TYPED_IR_MODE": ("interpreted" if mode == "interpreted" else "bytecode")
                            if typed else "",
        "FC_TYPED_IR_NAMESPACE": "fc_ir" if typed else "",
        "FC_TYPED_IR_DIRECT_FUNCTION": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_TOGGLE": str(crossover).lower(),
        "FC_TYPED_IR_DIRECT_FUNCTION_HARNESS": "true",
        "FC_TYPED_IR_DIAGNOSTICS": str(not crossover).lower(),
        "FC_TYPED_IR_SCORE_CACHE": "false",
        "FC_TYPED_IR_SINGLETON_FEEDBACK": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_HARNESS": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
    }


def start(work: Path, mode: str, crossover: bool = False):
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    make_pack(work)
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    port, rcon_port = unused_port(), unused_port()
    passwd = secrets.token_hex(18)
    (work / "server.properties").write_text("\n".join((
        "online-mode=false", "enable-rcon=true",
        "broadcast-rcon-to-ops=false", "level-name=world",
        "level-type=minecraft:flat", "pause-when-empty-seconds=-1",
        "view-distance=2", "simulation-distance=2",
        "max-tick-time=-1", "max-players=1",
        f"server-port={port}", f"rcon.port={rcon_port}",
        f"rcon.password={passwd}",
    )) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(options(mode, crossover))
    cmd = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}", "runServer",
    ]
    logfile = (OUT / f"{work.name}.server.log").open("w", encoding="utf-8")
    process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.PIPE,
                               stdout=logfile, stderr=subprocess.STDOUT)
    try:
        client = wait_for_rcon(process, rcon_port, passwd, timeout_seconds=240)
        if PACK not in client.command("datapack list enabled"):
            raise AssertionError("IR-012 original datapack not loaded")
        client.command("scoreboard objectives add fc_ir dummy")
        client.command("gamerule sendCommandFeedback false")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        return process, client, logfile
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        logfile.close()
        raise


def stop(process, client, logfile) -> None:
    try:
        client.command("stop")
    except (OSError, RuntimeError):
        pass
    client.close()
    try:
        process.wait(timeout=40)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=15)
    logfile.close()


def stat(response: str, key: str) -> int:
    match = re.search(rf"\b{re.escape(key)}=(\d+)", response)
    if not match:
        raise AssertionError(f"Missing {key} counter: {response!r}")
    return int(match.group(1))


def invoke(client, name: str, empty_callback: bool = True) -> str:
    cmd = ("fc_ir012_call " if empty_callback else "function ") + "fc_ir:" + name
    result = client.command(cmd)
    expected = "FC_ARCH_CALL queued " if empty_callback else "Running function "
    if not result.startswith(expected):
        raise AssertionError(f"Function {name} wasn't called: {result!r}")
    return result


def reset(client) -> None:
    for holder in ("#x", "#a", "#b", "#result"):
        client.command(f"scoreboard players set {holder} fc_ir 0")


def snapshot(client) -> dict:
    observed = {}
    for holder in ("x", "a", "b", "result"):
        response = client.command(f"scoreboard players get #{holder} fc_ir")
        match = re.search(r"has (-?\d+)", response)
        if match is None:
            raise AssertionError(f"Score #{holder} absent/unreadable: {response!r}")
        observed[holder] = int(match.group(1))
    return observed


def semantic_arm(mode: str) -> dict:
    work = RUNS / ("ci-ir012-" + mode)
    report = {"mode": mode, "status": "started", "cases": {},
              "activation": {}, "compiler_status": None}
    process, client, logfile = start(work, mode)
    try:
        if mode == "bytecode_off":
            result = client.command("fc_ir012_direct off")
            if "enabled=false" not in result:
                raise AssertionError(f"Research switch unavailable: {result!r}")
        for name, expected in EXPECTED.items():
            reset(client)
            invoke(client, name)
            state = snapshot(client)
            report["cases"][name] = state
            for field, value in expected.items():
                if state[field] != value:
                    raise AssertionError(
                        f"{mode}/{name}/{field}: {state[field]} != {value}")

        # Public /function uses callback-carrying CallFunction and remains
        # vanilla for return/result propagation, even with this mode enabled.
        reset(client)
        before = client.command("functioncompiler ir008")
        invoke(client, "ir012_chunk_128", empty_callback=False)
        after = client.command("functioncompiler ir008")
        report["cases"]["ordinary_function"] = snapshot(client)
        if mode == "bytecode_on" and stat(after, "direct_function_executed") != stat(
                before, "direct_function_executed"):
            raise AssertionError("Ordinary /function bypassed original callback frame")

        reset(client)
        client.command("execute store result score #result fc_ir "
                       "run function fc_ir:ir012_mixed")
        report["cases"]["stored_function_result"] = snapshot(client)

        # Unsupported function may still contain locally compiled IR regions,
        # but its whole-function direct path must not activate.
        if mode == "bytecode_on":
            before = stat(client.command("functioncompiler ir008"),
                          "direct_function_executed")
            reset(client)
            invoke(client, "ir012_barrier")
            invoke(client, "ir012_bad_tail_65")
            after = stat(client.command("functioncompiler ir008"),
                         "direct_function_executed")
            if after != before:
                raise AssertionError("Unsupported/partially compiled function was scheduled directly")

        # A trace must use original CallFunction (debug function itself may
        # report an error on unsupported server configurations; do not accept
        # that as evidence if trace command didn't actually run).
        if mode == "bytecode_on":
            before = stat(client.command("functioncompiler ir008"),
                          "direct_function_executed")
            reply = client.command("debug function fc_ir:ir012_mixed")
            if "trace" not in reply.lower() and "traced" not in reply.lower():
                raise AssertionError(f"Debug tracer not actually activated: {reply!r}")
            after = stat(client.command("functioncompiler ir008"),
                         "direct_function_executed")
            if after != before:
                raise AssertionError("Active command tracer entered direct scheduler")
            report["debug_trace_reply"] = reply

        # Quota readback and truncated state are compared across ALL arms.
        for quota in QUOTAS:
            for name in ("ir012_mixed", "ir012_chunk_128",
                         "ir012_chunk_256", "ir012_barrier"):
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                readback = client.command("gamerule minecraft:max_command_sequence_length")
                numbers = re.findall(r"\d+", readback)
                if not numbers or int(numbers[-1]) != quota:
                    raise AssertionError(f"Incorrect quota readback: {quota} {readback!r}")
                invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = snapshot(client)

        status = client.command("functioncompiler ir008")
        report["compiler_status"] = status
        if mode != "native":
            if stat(status, "compiled_regions") <= 0:
                raise AssertionError(f"IR didn't compile: {status}")
        if mode.startswith("bytecode"):
            if stat(status, "bytecode_regions") <= 0:
                raise AssertionError(f"No ASM bytecode: {status}")
            if stat(status, "direct_function_eligible") <= 0:
                raise AssertionError(f"Direct function compile gate not active: {status}")
            executions = stat(status, "direct_function_executed")
            report["activation"]["direct_calls"] = executions
            if mode == "bytecode_on":
                if executions <= 0 or stat(status, "direct_function_resumes") <= 0:
                    raise AssertionError(f"Resumable direct function never ran: {status}")
                if stat(status, "direct_function_chunks") <= executions:
                    raise AssertionError(f"Only one chunk ran: {status}")
            elif executions != 0:
                raise AssertionError(f"Disabled direct scheduler ran: {status}")
        report["status"] = "accepted"
        print("IR012_SEMANTIC_ARM " + json.dumps({
            "mode": mode, "cases": len(report["cases"]),
            "status": status
        }, sort_keys=True), flush=True)
        return report
    except BaseException as err:
        report["status"] = "invalid"
        report["error"] = repr(err)
        raise
    finally:
        stop(process, client, logfile)
        (OUT / f"{mode}.json").write_text(json.dumps(report, indent=2) + "\n")


def semantic() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_arms = []
    report = {"milestone": "COMPILER-IR-012", "status": "started", "arms": all_arms}
    try:
        for mode in SEMANTIC_MODES:
            all_arms.append(semantic_arm(mode))
            (OUT / "semantic.json").write_text(json.dumps(report, indent=2) + "\n")
        reference = all_arms[0]["cases"]
        for arm in all_arms[1:]:
            if arm["status"] != "accepted" or arm["cases"] != reference:
                raise AssertionError(f"Native parity mismatch {arm['mode']}")
        report["status"] = "accepted"
        report["native_parity"] = True
        report["production_promotion"] = False
    except BaseException as e:
        report["status"] = "invalid"
        report["error"] = repr(e)
        raise
    finally:
        (OUT / "semantic.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR012_SEMANTIC_SUMMARY " + json.dumps({
        "status": "accepted", "arms": 4, "cases": len(reference),
        "production_promotion": False
    }, sort_keys=True), flush=True)


def plan(boot: int) -> list[dict]:
    rng = random.Random(SEED + boot)
    blocks = [
        {"kind": "direct_vs_vanilla_scheduler",
         "order": "ABBA" if index % 2 == 0 else "BAAB"}
        for index in range(PAIRS_PER_BOOT)
    ]
    blocks += [
        {"kind": "vanilla_aa",
         "order": "ABBA" if index % 2 == 0 else "BAAB"}
        for index in range(AA_PER_BOOT)
    ]
    rng.shuffle(blocks)
    return blocks


def crossover_boot(boot: int) -> dict:
    work = RUNS / f"ci-ir012-crossover-{boot:02d}"
    report = {"boot": boot, "status": "started", "blocks": [], "plan": plan(boot)}
    process, client, logfile = start(work, "crossover", crossover=True)
    try:
        if "bytecode_regions=" not in client.command("functioncompiler ir008"):
            raise AssertionError("Bytecode compiler not loaded")
        thread = find_server_thread(process.pid)
        for mode in ("on", "off"):
            toggle = client.command(f"fc_ir012_direct {mode}")
            if f"enabled={str(mode == 'on').lower()}" not in toggle:
                raise AssertionError(f"Direct scheduler toggle failed: {toggle!r}")
            for _ in range(WARMUP_PER_ARM):
                invoke(client, "ir012_chunk_256")

        def window(mode: str) -> dict:
            toggle = client.command(f"fc_ir012_direct {mode}")
            if f"enabled={str(mode == 'on').lower()}" not in toggle:
                raise AssertionError(f"Direct scheduler toggle failed: {toggle!r}")
            reset(client)
            cpu0 = server_cpu_ns(thread)
            for _ in range(CALLS_PER_WINDOW):
                invoke(client, "ir012_chunk_256")
            cpu_ns = server_cpu_ns(thread) - cpu0
            state = snapshot(client)
            expected = CALLS_PER_WINDOW * 256
            if cpu_ns <= 0 or state["x"] != expected:
                raise AssertionError(f"{mode} wrong CPU/work {cpu_ns}/{state['x']} != {expected}")
            return {
                "mode": mode,
                "cpu_ns": cpu_ns,
                "original_commands": expected,
                "expected_score": expected,
                "observed": state,
                "state_parity": True
            }

        for index, block in enumerate(report["plan"]):
            labels = ("off", "on") if block["kind"] == "direct_vs_vanilla_scheduler" else ("off", "off")
            actual = [labels[0] if x == "A" else labels[1] for x in block["order"]]
            samples = [window(mode) for mode in actual]
            a = statistics.mean(s["cpu_ns"] for s, token in zip(samples, block["order"])
                                if token == "A")
            b = statistics.mean(s["cpu_ns"] for s, token in zip(samples, block["order"])
                                if token == "B")
            report["blocks"].append({
                "index": index, **block, "modes": actual,
                "windows": samples, "signed_b_over_a_minus_one": b / a - 1
            })
            (OUT / f"crossover-{boot:02d}.json").write_text(
                json.dumps(report, indent=2) + "\n")
        report["status"] = "accepted"
        print("IR012_CROSSOVER_BOOT " + json.dumps({
            "boot": boot,
            "direct": [r["signed_b_over_a_minus_one"] for r in report["blocks"]
                       if r["kind"] == "direct_vs_vanilla_scheduler"],
            "aa": [r["signed_b_over_a_minus_one"] for r in report["blocks"]
                   if r["kind"] == "vanilla_aa"],
        }, sort_keys=True), flush=True)
        return report
    except BaseException as e:
        report["status"] = "invalid"
        report["error"] = repr(e)
        raise
    finally:
        stop(process, client, logfile)
        (OUT / f"crossover-{boot:02d}.json").write_text(
            json.dumps(report, indent=2) + "\n")


def crossover() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"milestone": "COMPILER-IR-012", "status": "started", "boots": []}
    try:
        for boot in range(BOOTS):
            report["boots"].append(crossover_boot(boot))
            (OUT / "crossover.json").write_text(json.dumps(report, indent=2) + "\n")
        values = [row["signed_b_over_a_minus_one"] for boot in report["boots"]
                  for row in boot["blocks"] if row["kind"] == "direct_vs_vanilla_scheduler"]
        controls = [row["signed_b_over_a_minus_one"] for boot in report["boots"]
                    for row in boot["blocks"] if row["kind"] == "vanilla_aa"]
        if len(values) != BOOTS * PAIRS_PER_BOOT or len(controls) != BOOTS * AA_PER_BOOT:
            raise AssertionError("Incomplete A/B or A/A blocks")
        report["summary"] = {
            "milestone": "COMPILER-IR-012",
            "status": "accepted_observational",
            "on_vs_off_blocks": len(values),
            "same_path_controls": len(controls),
            "median_on_vs_off_fraction": statistics.median(values),
            "median_aa_fraction": statistics.median(controls),
            "per_boot_medians": [
                statistics.median(row["signed_b_over_a_minus_one"]
                                  for row in boot["blocks"]
                                  if row["kind"] == "direct_vs_vanilla_scheduler")
                for boot in report["boots"]
            ],
            "on_vs_off_min_max": [min(values), max(values)],
            "aa_min_max": [min(controls), max(controls)],
            "exact_state_work": True,
            "causal_general_speedup": False,
            "production_promotion": False,
            "scope": "same ASM and commands; 256-line wholly typed function; "
                     "four 64-instruction chunks, no source callback",
            "limitations": "Two boots and correlated windows; no multi-mod feedback or "
                           "queue-reentrant observer proof; RCON/command-dispatch CPU "
                           "in denominator; no representative datapack validation"
        }
        report["status"] = "accepted_observational"
    except BaseException as e:
        report["status"] = "invalid"
        report["error"] = repr(e)
        raise
    finally:
        (OUT / "crossover.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR012_CROSSOVER_SUMMARY " + json.dumps(report["summary"], sort_keys=True),
          flush=True)


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--phase", required=True, choices=("semantic", "crossover"))
    parsed = args.parse_args()
    (semantic if parsed.phase == "semantic" else crossover)()
