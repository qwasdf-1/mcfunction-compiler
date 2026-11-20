#!/usr/bin/env python3
"""COMPILER-IR-014: objective lifecycle and cascading queue-callback native parity.

This is a correctness-only follow-up to the accepted IR-013 queue-epoch gate.
A real synchronous scoreboard listener stages functions through Minecraft's
own ExecutionContext. The injections (including a nested listener) are never
run inline, and the guard must yield before the next source instruction.

Compare native, guarded ASM, guarded interpreted IR and guarded direct function
scheduling; compare full and quota-truncated scoreboard states, including a
missing versus newly recreated objective. No CPU/speedup claim is made.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir013 import options, stop, scalar, stat

OUT = ROOT / "build/reports/COMPILER-IR-014"
PACK = "fc_typed_ir014"
OBJ = "fc_ir"
AUX = "fc_aux"
MODES = ("native", "bytecode_guarded", "interpreted_guarded", "direct_guarded")
QUOTAS = (1, 2, 3, 4, 5, 8, 12, 16, 32, 64, 65, 80, 140)
CASES = ("ir014_cascade", "ir014_guarded", "ir014_recreate", "ir014_drop",
         "ir014_return")
WATCHED = ("#ir013_trigger", "#ir014_chain", "#ir014_second",
           "#ir014_recreate", "#ir014_drop", "#ir014_return")
HOLDERS = {
    "marker": "#ir014_marker",
    "inner_seen": "#ir014_inner_seen",
    "seen": "#ir014_seen",
    "after": "#ir014_after",
    "chain": "#ir014_chain",
    "second": "#ir014_second",
    "recreate": "#ir014_recreate",
    "drop": "#ir014_drop",
    "return_trigger": "#ir014_return",
}
FUNCTIONS = {
    # Retain IR-013's callback destination as a safe fixture dependency.
    "ir013_injected": [
        "scoreboard players add #ir013_mark fc_ir 7",
        "scoreboard players add #ir013_count fc_ir 1",
    ],
    # First injected function causes another listener to queue a SECOND
    # function. Its following scoreboard read must see the second's write.
    "ir014_inject_first": [
        "scoreboard players set #ir014_second fc_ir 1",
        "scoreboard players operation #ir014_inner_seen fc_ir = #ir014_marker fc_ir",
        "scoreboard players add #ir014_marker fc_ir 2",
    ],
    "ir014_inject_second": [
        "scoreboard players add #ir014_marker fc_ir 9",
        "scoreboard players add #ir014_marker fc_ir 0",
    ],
    "ir014_cascade": [
        "scoreboard players set #ir014_chain fc_ir 1",
        "scoreboard players operation #ir014_seen fc_ir = #ir014_marker fc_ir",
        "scoreboard players add #ir014_after fc_ir 1",
    ],
    "ir014_guarded": [
        "scoreboard players set #ir014_chain fc_ir 1",
        "execute if score #ir014_marker fc_ir matches 11 run "
        "scoreboard players add #ir014_seen fc_ir 3",
        "scoreboard players add #ir014_after fc_ir 1",
    ],
    # Object identity changes in the listener-queued function. The next
    # typed source read must resolve the newly created fc_aux objective.
    "ir014_inject_recreate": [
        "scoreboard objectives remove fc_aux",
        "scoreboard objectives add fc_aux dummy",
        "scoreboard players set #ir014_input fc_aux 19",
    ],
    "ir014_recreate": [
        "scoreboard players set #ir014_recreate fc_ir 1",
        "scoreboard players operation #ir014_seen fc_ir = #ir014_input fc_aux",
        "scoreboard players add #ir014_seen fc_ir 1",
        "scoreboard players add #ir014_after fc_ir 1",
    ],
    # A missing objective must take the normal original-command fallback;
    # the following independent command is still a separate queue entry.
    "ir014_inject_drop": ["scoreboard objectives remove fc_aux"],
    "ir014_drop": [
        "scoreboard players set #ir014_drop fc_ir 1",
        "scoreboard players add #ir014_input fc_aux 3",
        "scoreboard players add #ir014_after fc_ir 1",
    ],
    # A return in an INJECTED child must not discard its caller's tail.
    "ir014_inject_return": [
        "return 0",
        "scoreboard players add #ir014_marker fc_ir 100",
    ],
    "ir014_return": [
        "scoreboard players set #ir014_return fc_ir 1",
        "scoreboard players add #ir014_after fc_ir 1",
        "scoreboard players operation #ir014_seen fc_ir = #ir014_marker fc_ir",
    ],
}
# Full-run expected values are independent checks, not substitutes for the
# per-quota native-versus-compiled full-state comparisons.
EXPECTED = {
    "ir014_cascade": {"marker": 11, "inner_seen": 9, "seen": 11, "after": 1},
    "ir014_guarded": {"marker": 11, "inner_seen": 9, "seen": 3, "after": 1},
    "ir014_recreate": {"aux_exists": True, "aux_input": 19,
                       "seen": 20, "after": 1},
    "ir014_drop": {"aux_exists": False, "after": 1},
    "ir014_return": {"marker": 0, "seen": 0, "after": 1},
}


def fixture(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    funcs = root / "data/fc_ir/function"
    funcs.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR014 original source lifecycle/queue fixture",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, lines in FUNCTIONS.items():
        (funcs / (name + ".mcfunction")).write_text(
            "\n".join(lines) + "\n", encoding="utf-8")


def start(mode: str):
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    work = RUNS / ("ci-ir014-" + mode)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fixture(work)
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
    env.update(options(mode))
    command = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}", "runServer",
    ]
    log = (OUT / (mode + ".server.log")).open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=ROOT, env=env,
                               stdout=log, stderr=subprocess.STDOUT,
                               stdin=subprocess.PIPE)
    try:
        client = wait_for_rcon(process, rcon_port, password, timeout_seconds=240)
        if PACK not in client.command("datapack list enabled"):
            raise AssertionError(f"{mode}: IR014 fixture missing")
        client.command("scoreboard objectives add fc_ir dummy")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("gamerule sendCommandFeedback false")
        if mode in ("bytecode_guarded", "interpreted_guarded"):
            answer = client.command("fc_ir012_direct off")
            if "enabled=false" not in answer:
                raise AssertionError(f"Couldn't disable direct scheduler: {answer!r}")
        return process, client, log
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        log.close()
        raise


def reset(client) -> None:
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    # Remove watched rows; setting them to zero would invoke the test listener.
    for holder in WATCHED:
        client.command(f"scoreboard players reset {holder} fc_ir")
    for holder in HOLD_DEFS:
        client.command(f"scoreboard players set {holder} fc_ir 0")
    client.command("scoreboard objectives remove fc_aux")
    client.command("scoreboard objectives add fc_aux dummy")
    client.command("scoreboard players set #ir014_input fc_aux 5")


HOLD_DEFS = tuple(holder for holder in HOLDERS.values() if holder not in WATCHED)


def snapshot(client) -> dict:
    listed = client.command("scoreboard objectives list")
    aux_exists = re.search(r"\bfc_aux\b", listed) is not None
    result = {key: scalar(client, holder) for key, holder in HOLDERS.items()}
    result["aux_exists"] = aux_exists
    result["aux_input"] = scalar(client, "#ir014_input") if aux_exists else None
    # scalar() above addresses fc_ir, whereas aux_input belongs to fc_aux.
    if aux_exists:
        answer = client.command("scoreboard players get #ir014_input fc_aux")
        match = re.search(r"has (-?\d+)", answer)
        if not match:
            raise AssertionError(f"Unexpected fc_aux score reply {answer!r}")
        result["aux_input"] = int(match.group(1))
    return result


def invoke(client, name: str) -> None:
    answer = client.command("fc_ir013_call fc_ir:" + name)
    if not answer.startswith("FC_ARCH_CALL queued "):
        raise AssertionError(f"IR014 harness failed: {answer!r}")


def run_arm(mode: str) -> dict:
    process, client, log = start(mode)
    report = {"mode": mode, "status": "started", "cases": {}}
    try:
        for name in CASES:
            reset(client)
            invoke(client, name)
            observed = snapshot(client)
            report["cases"][name] = observed
            for key, expected in EXPECTED[name].items():
                if observed[key] != expected:
                    raise AssertionError(
                        f"{mode}/{name}/{key}: {observed[key]} != {expected}")
        for quota in QUOTAS:
            for name in CASES:
                reset(client)
                client.command(
                    f"gamerule minecraft:max_command_sequence_length {quota}")
                reply = client.command("gamerule minecraft:max_command_sequence_length")
                numbers = re.findall(r"\d+", reply)
                if not numbers or int(numbers[-1]) != quota:
                    raise AssertionError(f"{mode}: quota not applied {reply!r}")
                invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = snapshot(client)
        report["compiler_status"] = client.command("functioncompiler ir008")
        report["observer_status"] = client.command("fc_ir013_status")
        if stat(report["observer_status"], "reentrant_test_injections") <= 0:
            raise AssertionError(f"{mode}: observer never queued functions")
        if mode != "native":
            if stat(report["compiler_status"], "compiled_regions") <= 0:
                raise AssertionError(f"{mode}: typed IR compiler not activated")
            if mode != "interpreted_guarded" and stat(
                    report["compiler_status"], "bytecode_regions") <= 0:
                raise AssertionError(f"{mode}: no actual JVM bytecode regions")
            if stat(report["compiler_status"], "reentrant_yields") <= 0:
                raise AssertionError(f"{mode}: never detected a queue insertion")
            if stat(report["compiler_status"], "reentrant_queued_steps") <= 0:
                raise AssertionError(f"{mode}: no queue-recovered typed instructions")
        if mode == "direct_guarded" and stat(
                report["compiler_status"], "direct_function_executed") <= 0:
            raise AssertionError("IR014 direct scheduler was not exercised")
        report["status"] = "complete"
        print("IR014_NATIVE_ARM " + json.dumps({
            "mode": mode, "cases": len(report["cases"]),
            "compiler_status": report["compiler_status"],
            "observer_status": report["observer_status"]
        }, sort_keys=True), flush=True)
        return report
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        stop(process, client, log)
        (OUT / f"{mode}.json").write_text(json.dumps(report, indent=2) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"milestone": "COMPILER-IR-014", "status": "started",
              "arms": [], "performance_claim": False,
              "production_promotion": False}
    try:
        for mode in MODES:
            report["arms"].append(run_arm(mode))
            (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        reference = report["arms"][0]["cases"]
        for arm in report["arms"][1:]:
            differences = {
                name: {"native": reference[name], "actual": actual}
                for name, actual in arm["cases"].items()
                if reference[name] != actual
            }
            if differences:
                raise AssertionError(
                    f"IR014 native parity failure {arm['mode']}: "
                    f"{json.dumps(dict(list(differences.items())[:3]))}")
        report["status"] = "accepted"
        report["cases_per_arm"] = len(reference)
        report["native_semantic_parity"] = True
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR014_SUMMARY " + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
