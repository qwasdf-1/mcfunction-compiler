#!/usr/bin/env python3
"""IR-016 first-class mixed typed/vanilla function IR native parity.

Proves that a materialized mixed program retains the original command queue
boundaries for child calls, custom command callbacks, return/discard, store
results, block/score guard barriers, missing objectives and singleton tails.
Run four independent Minecraft 26.3/Java25 JVM modes and compare all observed
full and command-quota-truncated state. No CPU/performance claim.
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
from ci_typed_ir013 import stop, scalar, stat

OUT = ROOT / "build/reports/COMPILER-IR-016"
PACK = "fc_typed_ir016"
MODES = ("native", "interpreted", "bytecode", "bytecode_direct")
QUOTAS = (1, 2, 3, 4, 5, 6, 8, 12, 16, 32, 64, 65, 130)
ADD = "scoreboard players add #x fc_ir 1"
FUNCTIONS = {
    "ir016_child": ["scoreboard players add #x fc_ir 3"],
    "ir016_call_chain": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "function fc_ir:ir016_child",
        "scoreboard players add #x fc_ir 4",
        "scoreboard players add #x fc_ir 5",
        "execute if score #x fc_ir matches 15..30 run scoreboard players add #x fc_ir 6",
        "scoreboard players add #x fc_ir 7",
        "scoreboard players add #x fc_ir 8",
    ],
    "ir016_return": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "return 0",
        "scoreboard players add #x fc_ir 100",
        "scoreboard players add #x fc_ir 200",
    ],
    "ir016_store": [
        "scoreboard players set #x fc_ir 2",
        "scoreboard players add #x fc_ir 5",
        "execute store result score #stored fc_ir run scoreboard players get #x fc_ir",
        "scoreboard players add #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
    ],
    "ir016_lifecycle": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "scoreboard objectives remove fc_missing",
        "scoreboard objectives add fc_missing dummy",
        "scoreboard players set #other fc_missing 17",
        "scoreboard players add #x fc_ir 3",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir016_modded": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "execute store result score #stored fc_ir run fc_probe_leaf",
        "scoreboard players add #x fc_ir 3",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir016_singleton": [
        "scoreboard players set #x fc_ir 1",
        "function fc_ir:ir016_child",
        "scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_ir 3",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir016_chunk65": [ADD] * 65,
    "ir016_chunk66": [ADD] * 66,
    "ir016_missing": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_absent 10",
        "scoreboard players add #x fc_ir 3",
        "scoreboard players add #x fc_ir 4",
    ],
}
EXPECTED = {
    "ir016_call_chain": {"x": 36},
    "ir016_return": {"x": 3},
    "ir016_store": {"x": 10, "stored": 7},
    "ir016_lifecycle": {"x": 10, "other": 17, "missing_objective_exists": True},
    "ir016_modded": {"x": 10, "stored": 7},
    "ir016_singleton": {"x": 13},
    "ir016_chunk65": {"x": 65},
    "ir016_chunk66": {"x": 66},
    "ir016_missing": {"x": 10, "missing_objective_exists": False},
}
CASES = tuple(EXPECTED)


def fixture(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    folder = root / "data/fc_ir/function"
    folder.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR016 native mixed function acceptance fixture",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, commands in FUNCTIONS.items():
        (folder / (name + ".mcfunction")).write_text(
            "\n".join(commands) + "\n", encoding="utf-8")


def options(mode: str) -> dict[str, str]:
    assert mode in MODES
    compiled = mode != "native"
    return {
        "FC_WRAPPER_PROBE": str(compiled).lower(),
        "FC_TYPED_IR_MODE": ("interpreted" if mode == "interpreted" else "bytecode")
                            if compiled else "",
        "FC_TYPED_IR_NAMESPACE": "fc_ir" if compiled else "",
        "FC_TYPED_IR_DIAGNOSTICS": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_TOGGLE": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_HARNESS": "true",
        "FC_TYPED_IR_MIXED_TEST_HARNESS": "true",
        "FC_TYPED_IR_REENTRANT_SAFE": "true",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER": "false",
        "FC_TYPED_IR_FORCE_FAILURE": "false",
        "FC_TYPED_IR_SCORE_CACHE": "false",
        "FC_TYPED_IR_SINGLETON_FEEDBACK": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_DIRECT_SCHEDULER_PROTOTYPE": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
    }


def start(mode: str):
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    work = RUNS / ("ci-ir016-" + mode)
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
            raise AssertionError(f"{mode}: source datapack not loaded")
        client.command("scoreboard objectives add fc_ir dummy")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("gamerule sendCommandFeedback false")
        if mode in ("interpreted", "bytecode"):
            answer = client.command("fc_ir012_direct off")
            if "enabled=false" not in answer:
                raise AssertionError(f"{mode}: direct scheduler not disabled")
        return process, client, log
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        log.close()
        raise


def reset(client) -> None:
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    for holder in ("#x", "#stored"):
        client.command(f"scoreboard players set {holder} fc_ir 0")
    # The objective lifecycle case itself creates or removes these.
    client.command("scoreboard objectives remove fc_missing")
    client.command("scoreboard objectives remove fc_absent")


def snapshot(client) -> dict:
    listed = client.command("scoreboard objectives list")
    exists = re.search(r"\bfc_missing\b", listed) is not None
    output = {"x": scalar(client, "#x"), "stored": scalar(client, "#stored"),
              "missing_objective_exists": exists, "other": None}
    if exists:
        answer = client.command("scoreboard players get #other fc_missing")
        matched = re.search(r"has (-?\d+)", answer)
        if matched:
            output["other"] = int(matched.group(1))
    return output


def invoke(client, name: str) -> None:
    answer = client.command("fc_ir016_call fc_ir:" + name)
    if not answer.startswith("FC_ARCH_CALL queued "):
        raise AssertionError(f"IR016 no-result call failed: {answer!r}")


def inspect_program(client, name: str) -> dict:
    raw = client.command("functioncompiler ir016 fc_ir:" + name)
    result = {"raw": raw}
    if raw.startswith("IR016 function="):
        for key in ("source_lines", "typed_lines", "typed_regions",
                    "opaque_barriers", "singleton_barriers"):
            match = re.search(rf"\b{key}=(\d+)", raw)
            if not match:
                raise AssertionError(f"IR016 missing ledger {key}: {raw}")
            result[key] = int(match.group(1))
        match = re.search(r"\bdirect_candidate=(true|false)", raw)
        if not match:
            raise AssertionError(f"IR016 missing direct admission: {raw}")
        result["direct_candidate"] = match.group(1) == "true"
    return result


def run_arm(mode: str) -> dict:
    process, client, log = start(mode)
    report = {"mode": mode, "status": "started", "cases": {}, "ledger": {}}
    try:
        for name in CASES:
            reset(client)
            invoke(client, name)
            observed = snapshot(client)
            report["cases"][name] = observed
            for key, expected in EXPECTED[name].items():
                if observed[key] != expected:
                    raise AssertionError(
                        f"{mode}/{name}/{key}: observed {observed[key]} expected {expected}")
        if mode != "native":
            for name in CASES:
                report["ledger"][name] = inspect_program(client, name)
            layout = report["ledger"]["ir016_call_chain"]
            if (layout["source_lines"], layout["typed_lines"],
                    layout["typed_regions"], layout["opaque_barriers"]) != (8, 6, 3, 2):
                raise AssertionError(f"Mixed call-chain lowering wrong: {layout}")
            if report["ledger"]["ir016_chunk65"]["singleton_barriers"] != 1:
                raise AssertionError("IR016 65-command tail was not opaque")
            if report["ledger"]["ir016_chunk65"]["direct_candidate"]:
                raise AssertionError("IR016 65-command tail admitted to direct scheduler")
            if mode == "bytecode_direct" and not report["ledger"]["ir016_chunk66"]["direct_candidate"]:
                raise AssertionError("Fully bytecode chunked function incorrectly refused")
            if report["ledger"]["ir016_return"]["direct_candidate"]:
                raise AssertionError("IR016 function return admitted to direct scheduler")

        for quota in QUOTAS:
            for name in CASES:
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                answer = client.command("gamerule minecraft:max_command_sequence_length")
                numbers = re.findall(r"\d+", answer)
                if not numbers or int(numbers[-1]) != quota:
                    raise AssertionError(f"{mode}: invalid quota {answer!r}")
                invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = snapshot(client)
        report["compiler_status"] = client.command("functioncompiler ir008")
        if mode != "native":
            ir = report["compiler_status"]
            for field in ("ir016_mixed_functions", "ir016_typed_regions",
                          "ir016_typed_lines", "ir016_opaque_barriers",
                          "ir016_singletons", "executed_steps"):
                if stat(ir, field) <= 0:
                    raise AssertionError(f"{mode}: missing positive {field}: {ir}")
            if mode != "interpreted" and stat(ir, "bytecode_regions") <= 0:
                raise AssertionError(f"{mode}: no actual ASM compilation")
            if mode == "bytecode_direct" and stat(ir, "direct_function_executed") <= 0:
                raise AssertionError("Direct scheduler did not admit all-bytecode program")
        report["status"] = "complete"
        print("IR016_NATIVE_ARM " + json.dumps({
            "mode": mode, "cases": len(report["cases"]),
            "compiler_status": report["compiler_status"],
            "ledger_examples": {k: report["ledger"].get(k)
                                for k in ("ir016_call_chain", "ir016_chunk65",
                                          "ir016_chunk66", "ir016_return")}
        }, sort_keys=True), flush=True)
        return report
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        stop(process, client, log)
        (OUT / (mode + ".json")).write_text(json.dumps(report, indent=2) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"milestone": "COMPILER-IR-016", "status": "started",
              "arms": [], "production_promotion": False,
              "performance_claim": False}
    try:
        for mode in MODES:
            report["arms"].append(run_arm(mode))
            (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        reference = report["arms"][0]["cases"]
        for arm in report["arms"][1:]:
            bad = {key: {"native": reference[key], "compiled": value}
                   for key, value in arm["cases"].items()
                   if reference[key] != value}
            if bad:
                raise AssertionError(
                    f"Mixed IR native state divergence {arm['mode']}: "
                    f"{json.dumps(dict(list(bad.items())[:3]))}")
        report["status"] = "accepted"
        report["native_semantic_parity"] = True
        report["cases_per_arm"] = len(reference)
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR016_SUMMARY " + json.dumps({
        "status": report["status"],
        "cases_per_arm": report.get("cases_per_arm"),
        "native_semantic_parity": report.get("native_semantic_parity"),
        "performance_claim": False,
        "production_promotion": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
