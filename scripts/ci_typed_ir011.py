#!/usr/bin/env python3
"""COMPILER-IR-011 — native singleton-result feedback specialization.

Four real Minecraft 26.3/Java25 semantic JVMs compare vanilla, original
tracker-backed bytecode, singleton feedback interpreted, and singleton
feedback bytecode. The runtime A/B uses exactly the SAME generated ASM in
the SAME JVM, toggling only the one-element CommandResponseTracker elimination.

This measures one narrowly supported callback optimization. No general
speedup, real datapack acceptance or production promotion is inferred.
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

OUT = ROOT / "build/reports/COMPILER-IR-011"
PACK = "fc_typed_ir011"
NS = "fc_ir"
OBJ = "fc_ir"
SEMANTIC_MODES = ("native", "bytecode_off", "interpreted_on", "bytecode_on")
QUOTAS = (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 32)
SEED = 8011
BOOTS = 2
PAIRS_PER_BOOT = 6
AA_PER_BOOT = 3
CALLS_PER_WINDOW = 160
WARMUP_CALLS = 60

CASES = {
    "zero": [
        "scoreboard players set #a fc_ir 0",
        "scoreboard players add #a fc_ir 0",
        "scoreboard players remove #a fc_ir 0",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #b fc_ir = #a fc_ir",
        "scoreboard players add #a fc_ir 0",
    ],
    "signed": [
        "scoreboard players set #a fc_ir -2147483648",
        "scoreboard players remove #a fc_ir 1",
        "scoreboard players remove #a fc_ir 5",
        "scoreboard players operation #b fc_ir = #a fc_ir",
        "scoreboard players add #b fc_ir 2",
    ],
    "binary": [
        "scoreboard players set #a fc_ir 5",
        "scoreboard players set #b fc_ir 3",
        "scoreboard players operation #a fc_ir += #b fc_ir",
        "scoreboard players operation #a fc_ir -= #b fc_ir",
        "scoreboard players operation #a fc_ir *= #b fc_ir",
        "scoreboard players operation #a fc_ir = #b fc_ir",
    ],
    "conditional": [
        "scoreboard players set #a fc_ir 5",
        "execute if score #a fc_ir matches 5 run scoreboard players add #b fc_ir 1",
        "execute if score #a fc_ir matches 4 run scoreboard players add #b fc_ir 10",
        "execute unless score #a fc_ir matches 5 run scoreboard players set #b fc_ir 100",
        "scoreboard players remove #a fc_ir 2",
        "execute unless score #a fc_ir matches 5 run scoreboard players add #b fc_ir 2",
    ],
    "barrier": [
        "scoreboard players set #a fc_ir 2",
        "scoreboard players add #a fc_ir 3",
        "function fc_ir:helper",
        "scoreboard players add #a fc_ir 2",
        "scoreboard players remove #a fc_ir 1",
    ],
    "helper": ["scoreboard players add #a fc_ir 10"],
    "bench64": [
        "scoreboard players set #src fc_ir 7",
        "scoreboard players set #a fc_ir 0",
    ] + ["scoreboard players operation #a fc_ir += #src fc_ir"] * 62,
}
EXPECTED = {
    "zero": {"a": 0, "b": 0},
    "signed": {"a": 2147483642, "b": 2147483644},
    "binary": {"a": 3, "b": 3},
    "conditional": {"a": 3, "b": 3},
    "barrier": {"a": 16, "b": 0},
    "bench64": {"a": 434, "b": 0},
}


def make_pack(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    funcs = root / "data" / NS / "function"
    funcs.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "description": "COMPILER-IR-011 native feedback singleton validation",
            "min_format": [97, 1], "max_format": [97, 1],
        }
    }) + "\n", encoding="utf-8")
    for name, commands in CASES.items():
        (funcs / (name + ".mcfunction")).write_text(
            "\n".join(commands) + "\n", encoding="utf-8")


def options(mode: str, crossover: bool = False) -> dict[str, str]:
    if mode not in SEMANTIC_MODES and mode != "crossover":
        raise ValueError(mode)
    enabled = mode in ("interpreted_on", "bytecode_on", "crossover")
    interpreted = mode == "interpreted_on"
    wrapped = mode != "native"
    return {
        "FC_WRAPPER_PROBE": str(wrapped).lower(),
        "FC_TYPED_IR_MODE": ("interpreted" if interpreted else "bytecode") if wrapped else "",
        "FC_TYPED_IR_NAMESPACE": NS if wrapped else "",
        "FC_TYPED_IR_DIAGNOSTICS": str(not crossover).lower(),
        "FC_TYPED_IR_SINGLETON_FEEDBACK": str(enabled).lower(),
        "FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE": str(crossover).lower(),
        "FC_TYPED_IR_SCORE_CACHE": "false",
        "FC_TYPED_IR_SCORE_CACHE_TOGGLE": "false",
        "FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_RUNTIME_TRACE": "false",
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
    password = secrets.token_hex(18)
    (work / "server.properties").write_text("\n".join((
        "online-mode=false", "enable-rcon=true",
        "broadcast-rcon-to-ops=false", "level-name=world",
        "level-type=minecraft:flat", "pause-when-empty-seconds=-1",
        "view-distance=2", "simulation-distance=2",
        "max-tick-time=-1", "max-players=1",
        f"server-port={port}", f"rcon.port={rcon_port}",
        f"rcon.password={password}",
    )) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(options(mode, crossover))
    command = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}", "runServer",
    ]
    logfile = (OUT / (work.name + ".server.log")).open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=ROOT, env=env,
                               stdout=logfile, stderr=subprocess.STDOUT,
                               stdin=subprocess.PIPE)
    try:
        client = wait_for_rcon(process, rcon_port, password, timeout_seconds=240)
        enabled = client.command("datapack list enabled")
        if PACK not in enabled:
            raise AssertionError(f"Original source pack wasn't enabled: {enabled!r}")
        client.command("scoreboard objectives add fc_ir dummy")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("gamerule sendCommandFeedback false")
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


def invoke(client, name: str) -> None:
    response = client.command(f"function {NS}:{name}")
    if not response.startswith("Running function "):
        raise AssertionError(f"Failed to run {name}: {response!r}")


def reset(client) -> None:
    for holder in ("#a", "#b", "#src", "#result"):
        client.command(f"scoreboard players set {holder} {OBJ} 0")


def snapshot(client) -> dict:
    result = {}
    for name in ("a", "b", "src", "result"):
        response = client.command(f"scoreboard players get #{name} {OBJ}")
        match = re.search(r"has (-?\d+)", response)
        if match is None:
            raise AssertionError(f"Cannot read #{name}: {response!r}")
        result[name] = int(match.group(1))
    return result


def semantic_arm(mode: str) -> dict:
    work = RUNS / ("ci-ir011-" + mode)
    report = {"mode": mode, "status": "started", "cases": {},
              "compiler_status": None, "actual_instruction_count": 0}
    process, client, logfile = start(work, mode)
    try:
        for name, expected in EXPECTED.items():
            reset(client)
            invoke(client, name)
            observed = snapshot(client)
            report["cases"][name] = observed
            for field, value in expected.items():
                if observed[field] != value:
                    raise AssertionError(f"{mode}/{name}/{field}: {observed[field]} != {value}")

        # Function-result consumer contract: a scoreboard write made by
        # an ordinary execute-store callback is still observable around
        # compiler regions; the exact stored result is compared to native.
        reset(client)
        client.command("execute store result score #result fc_ir "
                       "run function fc_ir:signed")
        report["cases"]["function_result_consumer"] = snapshot(client)

        # A second pass with feedback enabled probes the ordinary message
        # path (which may be suppressed by the function's source stack);
        # no compiler arm is allowed to alter final score states.
        client.command("gamerule sendCommandFeedback true")
        for name in ("zero", "binary", "conditional"):
            reset(client)
            invoke(client, name)
            report["cases"]["feedback_enabled_" + name] = snapshot(client)
        client.command("gamerule sendCommandFeedback false")

        # Truncated execution matters because feedback still runs after
        # individual score writes and not after skipped conditional bodies.
        for quota in QUOTAS:
            client.command("gamerule minecraft:max_command_sequence_length 65536")
            for name in ("zero", "signed", "binary", "conditional"):
                reset(client)
                client.command(
                    f"gamerule minecraft:max_command_sequence_length {quota}")
                invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = snapshot(client)

        status = client.command("functioncompiler ir008")
        report["compiler_status"] = status
        if mode != "native":
            for counter in ("compiled_regions", "executed_steps"):
                match = re.search(rf"\b{counter}=(\d+)", status)
                if match is None or int(match.group(1)) <= 0:
                    raise AssertionError(f"{mode}: IR wasn't executing {status!r}")
            if mode != "interpreted_on":
                match = re.search(r"\bbytecode_regions=(\d+)", status)
                if match is None or int(match.group(1)) <= 0:
                    raise AssertionError(f"{mode}: no generated ASM path {status!r}")
            singleton = int(re.search(r"\bsingleton_feedback_steps=(\d+)", status).group(1))
            tracker = int(re.search(r"\btracker_feedback_steps=(\d+)", status).group(1))
            report["singleton_feedback_steps"] = singleton
            report["tracker_feedback_steps"] = tracker
            if mode.endswith("_on"):
                if singleton <= 0 or tracker != 0:
                    raise AssertionError(f"{mode}: singleton path not active {status!r}")
            elif tracker <= 0 or singleton != 0:
                raise AssertionError(f"{mode}: baseline not active {status!r}")
        report["status"] = "accepted"
        print("IR011_SEMANTIC_ARM " + json.dumps({
            "mode": mode, "case_count": len(report["cases"]), "status": status
        }, sort_keys=True), flush=True)
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        stop(process, client, logfile)
        (OUT / (mode + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    return report


def semantic() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"milestone": "COMPILER-IR-011", "status": "started", "arms": []}
    try:
        for mode in SEMANTIC_MODES:
            result["arms"].append(semantic_arm(mode))
            (OUT / "semantic.json").write_text(json.dumps(result, indent=2) + "\n")
        baseline = result["arms"][0]["cases"]
        for arm in result["arms"]:
            if arm["status"] != "accepted" or arm["cases"] != baseline:
                raise AssertionError(f"Native parity failed in {arm['mode']}: "
                                     f"{arm['cases']} versus {baseline}")
        result["status"] = "accepted"
        result["native_parity"] = True
        result["production_promotion"] = False
    except BaseException as error:
        result["status"] = "invalid"
        result["error"] = repr(error)
        raise
    finally:
        (OUT / "semantic.json").write_text(json.dumps(result, indent=2) + "\n")
    print("IR011_SEMANTIC_SUMMARY " + json.dumps({
        "status": result["status"], "arms": len(result["arms"]),
        "cases_per_arm": len(baseline), "promotion": False
    }, sort_keys=True), flush=True)


def plan(boot: int) -> list[dict]:
    rng = random.Random(SEED + boot)
    blocks = [
        {"kind": "singleton_vs_tracker",
         "order": "ABBA" if i % 2 == 0 else "BAAB"}
        for i in range(PAIRS_PER_BOOT)
    ]
    blocks += [
        {"kind": "tracker_aa", "order": "ABBA" if i % 2 == 0 else "BAAB"}
        for i in range(AA_PER_BOOT)
    ]
    rng.shuffle(blocks)
    return blocks


def crossover_boot(boot: int) -> dict:
    work = RUNS / f"ci-ir011-crossover-{boot:02d}"
    report = {"boot": boot, "status": "started", "plan": plan(boot),
              "blocks": [], "source": "one identical 64-command function"}
    process, client, logfile = start(work, "crossover", crossover=True)
    try:
        baseline = client.command("functioncompiler ir008")
        if "singleton_feedback=true" not in baseline or "score_cache=false" not in baseline:
            raise AssertionError(f"Incorrect benchmark feature selection {baseline!r}")
        # The CPU fixture touches only #a and #src. Give the observer
        # snapshot's #b and #result real zero rows before starting the
        # measured interval; never conflate a missing row with zero.
        for holder in ("#b", "#result"):
            client.command(f"scoreboard players set {holder} fc_ir 0")
        thread = find_server_thread(process.pid)

        for label in ("on", "off"):
            reply = client.command("fc_ir011_feedback " + label)
            if f"singleton feedback enabled={str(label == 'on').lower()}" not in reply:
                raise AssertionError(f"Missing feature toggle {reply!r}")
            for _ in range(WARMUP_CALLS):
                invoke(client, "bench64")

        def window(label: str) -> dict:
            reply = client.command("fc_ir011_feedback " + label)
            if f"singleton feedback enabled={str(label == 'on').lower()}" not in reply:
                raise AssertionError(f"Missing feature toggle {reply!r}")
            before = server_cpu_ns(thread)
            for _ in range(CALLS_PER_WINDOW):
                invoke(client, "bench64")
            cpu = server_cpu_ns(thread) - before
            state = snapshot(client)
            if state["a"] != EXPECTED["bench64"]["a"] or cpu <= 0:
                raise AssertionError(f"Invalid benchmark {label}: {state} cpu={cpu}")
            return {
                "mode": label, "cpu_ns": cpu, "source": "fc_ir:bench64",
                "original_commands": CALLS_PER_WINDOW * 64, "exact_work": True,
                "state": state
            }

        for i, entry in enumerate(report["plan"]):
            modes = ("off", "on") if entry["kind"] == "singleton_vs_tracker" else ("off", "off")
            actual = [modes[0] if token == "A" else modes[1] for token in entry["order"]]
            samples = [window(label) for label in actual]
            a = statistics.mean(s["cpu_ns"] for s, token in zip(samples, entry["order"])
                                if token == "A")
            b = statistics.mean(s["cpu_ns"] for s, token in zip(samples, entry["order"])
                                if token == "B")
            report["blocks"].append({
                "index": i, **entry, "arms": actual, "samples": samples,
                "signed_b_over_a_minus_one": b / a - 1
            })
            (OUT / f"crossover-{boot:02d}.json").write_text(
                json.dumps(report, indent=2) + "\n")
        report["status"] = "accepted"
        print("IR011_CROSSOVER_BOOT " + json.dumps({
            "boot": boot,
            "singleton_vs_tracker": [x["signed_b_over_a_minus_one"]
                                      for x in report["blocks"]
                                      if x["kind"] == "singleton_vs_tracker"],
            "aa": [x["signed_b_over_a_minus_one"] for x in report["blocks"]
                   if x["kind"] == "tracker_aa"]
        }, sort_keys=True), flush=True)
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        stop(process, client, logfile)
        (OUT / f"crossover-{boot:02d}.json").write_text(
            json.dumps(report, indent=2) + "\n")
    return report


def crossover() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"milestone": "COMPILER-IR-011", "status": "started", "boots": []}
    try:
        for boot in range(BOOTS):
            result["boots"].append(crossover_boot(boot))
            (OUT / "crossover.json").write_text(json.dumps(result, indent=2) + "\n")
        rows = [x for b in result["boots"] for x in b["blocks"]
                if x["kind"] == "singleton_vs_tracker"]
        aa = [x for b in result["boots"] for x in b["blocks"]
              if x["kind"] == "tracker_aa"]
        if len(rows) != BOOTS * PAIRS_PER_BOOT or len(aa) != BOOTS * AA_PER_BOOT:
            raise AssertionError("Missing ABBA/BAAB or A/A windows")
        values = [r["signed_b_over_a_minus_one"] for r in rows]
        aa_values = [r["signed_b_over_a_minus_one"] for r in aa]
        result["summary"] = {
            "milestone": "COMPILER-IR-011",
            "status": "accepted_observational",
            "singleton_vs_tracker_blocks": len(values),
            "tracker_aa_blocks": len(aa_values),
            "singleton_vs_tracker_median_fraction": statistics.median(values),
            "tracker_aa_median_fraction": statistics.median(aa_values),
            "per_boot_medians": [
                statistics.median(x["signed_b_over_a_minus_one"]
                                  for x in boot["blocks"]
                                  if x["kind"] == "singleton_vs_tracker")
                for boot in result["boots"]
            ],
            "singleton_min_max": [min(values), max(values)],
            "aa_min_max": [min(aa_values), max(aa_values)],
            "exact_work": True, "causal_general_speedup": False,
            "production_promotion": False,
            "limitations": "Within-boot blocks are correlated; console RCON and "
                           "scoreboard work remain in CPU denominator. This is a "
                           "single 64-command microfixture, not a real datapack."
        }
        result["status"] = "accepted_observational"
    except BaseException as error:
        result["status"] = "invalid"
        result["error"] = repr(error)
        raise
    finally:
        (OUT / "crossover.json").write_text(json.dumps(result, indent=2) + "\n")
    print("IR011_CROSSOVER_SUMMARY " + json.dumps(result["summary"], sort_keys=True),
          flush=True)


if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument("--phase", required=True, choices=("semantic", "crossover"))
    args = argp.parse_args()
    (semantic if args.phase == "semantic" else crossover)()
