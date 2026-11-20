#!/usr/bin/env python3
"""IR-017: native ranged-score guards and guarded binary operation parity.

Five fresh actual Minecraft 26.3 JVMs compare unmodified vanilla, old
IR-016/IR-009 ASM with the new flag OFF, and new guarded interpreted/ASM/direct
backends. Full and quota-truncated scoreboard state is checked, including
absent rows, objective removal, callback-inserted functions and child return.
This is a semantics/coverage study, NOT a CPU speedup claim.
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
from ci_typed_ir014 import FUNCTIONS as CALLBACK_FUNCTIONS

OUT = ROOT / "build/reports/COMPILER-IR-017"
PACK = "fc_typed_ir017"
MODES = ("native", "old_bytecode", "interpreted", "bytecode", "direct")
QUOTAS = (1, 2, 3, 4, 5, 6, 8, 12, 16, 32, 64, 65, 130)
FUNC = {
    "ir017_child": ["scoreboard players add #x fc_ir 3"],
    "ir017_inclusive": [
        "scoreboard players set #g fc_ir 4",
        "scoreboard players set #x fc_ir 0",
        "execute if score #g fc_ir matches 4..9 run scoreboard players add #x fc_ir 1",
        "execute if score #g fc_ir matches 5..9 run scoreboard players add #x fc_ir 100",
        "execute unless score #g fc_ir matches 5..9 run scoreboard players add #x fc_ir 2",
        "execute unless score #g fc_ir matches 4.. run scoreboard players add #x fc_ir 50",
        "scoreboard players add #x fc_ir 3",
    ],
    "ir017_open": [
        "scoreboard players set #g fc_ir -7",
        "scoreboard players set #x fc_ir 1",
        "execute if score #g fc_ir matches ..-7 run scoreboard players add #x fc_ir 2",
        "execute if score #g fc_ir matches -7.. run scoreboard players add #x fc_ir 4",
        "execute if score #g fc_ir matches ..-8 run scoreboard players add #x fc_ir 100",
        "execute unless score #g fc_ir matches -8.. run scoreboard players add #x fc_ir 200",
        "scoreboard players add #x fc_ir 3",
    ],
    "ir017_extreme": [
        "scoreboard players set #g fc_ir -2147483648",
        "scoreboard players set #x fc_ir 0",
        "execute if score #g fc_ir matches -2147483648..-2147483648 "
        "run scoreboard players add #x fc_ir 5",
        "execute unless score #g fc_ir matches -2147483647.. "
        "run scoreboard players add #x fc_ir 3",
        "execute if score #g fc_ir matches ..-2147483648 "
        "run scoreboard players add #x fc_ir 7",
        "execute if score #g fc_ir matches 2147483647.. "
        "run scoreboard players add #x fc_ir 10",
    ],
    "ir017_guarded_binary": [
        "scoreboard players set #g fc_ir 5",
        "scoreboard players set #x fc_ir 3",
        "scoreboard players set #y fc_ir 6",
        "execute if score #g fc_ir matches 1..7 "
        "run scoreboard players operation #x fc_ir += #y fc_ir",
        "execute if score #g fc_ir matches 4.. "
        "run scoreboard players operation #x fc_ir -= #y fc_ir",
        "execute unless score #g fc_ir matches 4.. "
        "run scoreboard players operation #x fc_ir *= #y fc_ir",
        "execute if score #g fc_ir matches ..5 "
        "run scoreboard players operation #x fc_ir *= #y fc_ir",
        "execute if score #g fc_ir matches 5 "
        "run scoreboard players operation #x fc_ir = #y fc_ir",
        "execute if score #g fc_ir matches 5..5 "
        "run scoreboard players operation #x fc_ir += #y fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_distinct": [
        "scoreboard players set #g fc_guard 6",
        "scoreboard players set #x fc_ir 5",
        "scoreboard players set #y fc_source 2",
        "execute if score #g fc_guard matches 5..6 "
        "run scoreboard players operation #x fc_ir += #y fc_source",
        "execute unless score #g fc_guard matches ..5 "
        "run scoreboard players operation #x fc_ir *= #y fc_source",
        "execute if score #g fc_guard matches 6.. "
        "run scoreboard players operation #x fc_ir = #y fc_source",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_missing_guard": [
        "scoreboard players set #x fc_ir 1",
        "execute if score #never fc_guard matches 1..3 "
        "run scoreboard players add #x fc_ir 100",
        "execute unless score #never fc_guard matches 1..3 "
        "run scoreboard players operation #x fc_ir += #y fc_source",
        "scoreboard players add #x fc_ir 2",
    ],
    "ir017_missing_objectives": [
        "scoreboard players set #x fc_ir 1",
        "execute if score #g fc_absent matches 1..3 "
        "run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 1..3 "
        "run scoreboard players operation #x fc_ir += #y fc_absent",
        "scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_ir 3",
    ],
    "ir017_same_holder": [
        "scoreboard players set #x fc_ir 2",
        "execute if score #x fc_ir matches 2..2 "
        "run scoreboard players operation #x fc_ir += #x fc_ir",
        "execute unless score #x fc_ir matches ..3 "
        "run scoreboard players operation #x fc_ir *= #x fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_child_barrier": [
        "scoreboard players set #x fc_ir 1",
        "scoreboard players set #g fc_ir 7",
        "function fc_ir:ir017_child",
        "execute if score #g fc_ir matches 5..10 "
        "run scoreboard players operation #x fc_ir += #g fc_ir",
        "scoreboard players add #x fc_ir 2",
    ],
    "ir017_return": [
        "scoreboard players set #x fc_ir 2",
        "execute if score #x fc_ir matches 1.. "
        "run scoreboard players add #x fc_ir 3",
        "return 0",
        "execute if score #x fc_ir matches 5.. "
        "run scoreboard players operation #x fc_ir *= #x fc_ir",
        "scoreboard players add #x fc_ir 100",
    ],
    "ir017_divide_barrier": [
        "scoreboard players set #g fc_ir 2",
        "scoreboard players set #x fc_ir 12",
        "scoreboard players set #y fc_ir 3",
        "execute if score #g fc_ir matches 1..3 "
        "run scoreboard players operation #x fc_ir /= #y fc_ir",
        "execute if score #g fc_ir matches 2.. "
        "run scoreboard players operation #x fc_ir += #y fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_reentrant": [
        "scoreboard players set #ir014_chain fc_ir 1",
        "execute if score #ir014_marker fc_ir matches 10..11 "
        "run scoreboard players add #x fc_ir 2",
        "execute unless score #ir014_marker fc_ir matches ..9 "
        "run scoreboard players operation #x fc_ir += #ir014_marker fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
}
# Test-only observer functions are sourced unchanged from accepted IR-014
# and invoked by a real synchronous ServerScoreboard listener.
FUNCTIONS = {**{k: v for k, v in CALLBACK_FUNCTIONS.items()
                if k.startswith("ir014_inject_") or k == "ir013_injected"},
             **FUNC}
CASES = tuple(name for name in FUNC if name != "ir017_child")
EXPECTED = {
    "ir017_inclusive": {"x": 6},
    "ir017_open": {"x": 10},
    "ir017_extreme": {"x": 15},
    "ir017_guarded_binary": {"x": 13},
    "ir017_distinct": {"x": 3},
    "ir017_missing_objectives": {"x": 6},
    "ir017_same_holder": {"x": 17},
    "ir017_child_barrier": {"x": 13},
    "ir017_return": {"x": 5},
    "ir017_divide_barrier": {"x": 8},
    "ir017_reentrant": {"x": 14, "ir014_marker": 11, "ir014_inner_seen": 9},
}
# No independent value for the ambiguous missing-holder + unless behavior:
# vanilla defines it, then every compiled mode must match native exactly.
WATCHED = ("#ir014_chain", "#ir014_second", "#ir014_recreate",
           "#ir014_drop", "#ir014_return")


def fixture(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    folder = root / "data/fc_ir/function"
    folder.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR017 native scoreboard range and guarded binary fixture",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, commands in FUNCTIONS.items():
        (folder / (name + ".mcfunction")).write_text(
            "\n".join(commands) + "\n", encoding="utf-8")


def options(mode: str) -> dict[str, str]:
    if mode not in MODES:
        raise ValueError(mode)
    compiled = mode != "native"
    ir017 = mode not in ("native", "old_bytecode")
    return {
        "FC_WRAPPER_PROBE": str(compiled).lower(),
        "FC_TYPED_IR_MODE": ("interpreted" if mode == "interpreted" else "bytecode")
                            if compiled else "",
        "FC_TYPED_IR_NAMESPACE": "fc_ir" if compiled else "",
        "FC_TYPED_IR_RANGE_GUARDS": str(ir017).lower(),
        "FC_TYPED_IR_DIAGNOSTICS": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_TOGGLE": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_HARNESS": "true",
        "FC_TYPED_IR_RANGE_TEST_HARNESS": "true",
        "FC_TYPED_IR_REENTRANT_SAFE": "true",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER": "true",
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
    work = RUNS / ("ci-ir017-" + mode)
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
    cmd = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}", "runServer",
    ]
    log = (OUT / (mode + ".server.log")).open("w", encoding="utf-8")
    process = subprocess.Popen(cmd, cwd=ROOT, env=env,
                               stdout=log, stderr=subprocess.STDOUT,
                               stdin=subprocess.PIPE)
    try:
        client = wait_for_rcon(process, rcon_port, password, timeout_seconds=240)
        if PACK not in client.command("datapack list enabled"):
            raise AssertionError(f"{mode}: original source fixture not loaded")
        for objective in ("fc_ir", "fc_guard", "fc_source"):
            client.command("scoreboard objectives add " + objective + " dummy")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("gamerule sendCommandFeedback false")
        if mode in ("old_bytecode", "interpreted", "bytecode"):
            answer = client.command("fc_ir012_direct off")
            if "enabled=false" not in answer:
                raise AssertionError(f"{mode}: direct scheduler not disabled: {answer}")
        return process, client, log
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        log.close()
        raise


def reset(client) -> None:
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    for holder in WATCHED:
        client.command("scoreboard players reset " + holder + " fc_ir")
    for holder in ("#x", "#g", "#y", "#result", "#ir014_marker", "#ir014_inner_seen"):
        client.command("scoreboard players set " + holder + " fc_ir 0")
    client.command("scoreboard players reset #never fc_guard")
    client.command("scoreboard players set #g fc_guard 0")
    client.command("scoreboard players set #y fc_source 1")
    client.command("scoreboard objectives remove fc_absent")


def snapshot(client) -> dict:
    output = {name: scalar(client, "#" + name) for name in (
        "x", "g", "y", "result", "ir014_marker", "ir014_inner_seen")}
    output["guard_score"] = nullable_score(client, "#g", "fc_guard")
    output["operand_score"] = nullable_score(client, "#y", "fc_source")
    output["never_score"] = nullable_score(client, "#never", "fc_guard")
    output["missing_objective_exists"] = bool(
        re.search(r"\bfc_absent\b", client.command("scoreboard objectives list")))
    return output


def nullable_score(client, holder: str, objective: str) -> int | None:
    answer = client.command(f"scoreboard players get {holder} {objective}")
    m = re.search(r"has (-?\d+)", answer)
    if m:
        return int(m.group(1))
    if "none is set" in answer:
        return None
    raise AssertionError(f"Unexpected score reply for {holder}/{objective}: {answer!r}")


def invoke(client, name: str) -> None:
    reply = client.command("fc_ir017_call fc_ir:" + name)
    if not reply.startswith("FC_ARCH_CALL queued "):
        raise AssertionError(f"IR017 no-result fixture call failed: {reply!r}")


def inspect(client, name: str) -> dict:
    raw = client.command("functioncompiler ir016 fc_ir:" + name)
    if not raw.startswith("IR016 function="):
        raise AssertionError(f"No compiled ledger entry for {name}: {raw!r}")
    d = {"raw": raw}
    for field in ("source_lines", "typed_lines", "typed_regions",
                  "opaque_barriers", "singleton_barriers"):
        m = re.search(rf"\b{field}=(\d+)", raw)
        if not m:
            raise AssertionError(f"Missing {field} in {raw!r}")
        d[field] = int(m.group(1))
    match = re.search(r"direct_candidate=(true|false)", raw)
    d["direct_candidate"] = bool(match and match.group(1) == "true")
    return d


def run_arm(mode: str) -> dict:
    process, client, log = start(mode)
    report = {"mode": mode, "status": "started", "cases": {}, "layouts": {}}
    try:
        for name in CASES:
            reset(client)
            invoke(client, name)
            state = snapshot(client)
            report["cases"][name] = state
            for field, expected in EXPECTED.get(name, {}).items():
                if state[field] != expected:
                    raise AssertionError(
                        f"{mode}/{name}/{field}: observed {state[field]} != {expected}")
        if mode != "native":
            for name in ("ir017_inclusive", "ir017_guarded_binary", "ir017_distinct",
                         "ir017_missing_objectives", "ir017_child_barrier",
                         "ir017_return", "ir017_reentrant"):
                report["layouts"][name] = inspect(client, name)
            if mode in ("interpreted", "bytecode", "direct"):
                if report["layouts"]["ir017_guarded_binary"]["typed_lines"] < 8:
                    raise AssertionError("IR017 guarded binary operations not lowered")
                if report["layouts"]["ir017_inclusive"]["typed_lines"] < 5:
                    raise AssertionError("IR017 range predicates not lowered")
                if report["layouts"]["ir017_child_barrier"]["direct_candidate"]:
                    raise AssertionError("Barrier-containing function admitted to direct cursor")
                if report["layouts"]["ir017_return"]["direct_candidate"]:
                    raise AssertionError("Return-containing function admitted to direct cursor")
            elif report["layouts"]["ir017_guarded_binary"]["typed_lines"] >= 8:
                raise AssertionError("Old IR-009 control unexpectedly accepts new typed guards")
        for quota in QUOTAS:
            for name in CASES:
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                answer = client.command("gamerule minecraft:max_command_sequence_length")
                values = re.findall(r"\d+", answer)
                if not values or int(values[-1]) != quota:
                    raise AssertionError(f"{mode}: quota was not applied: {answer!r}")
                invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = snapshot(client)
        report["diagnostic"] = client.command("functioncompiler ir008")
        report["observer"] = client.command("fc_ir013_status")
        if stat(report["observer"], "reentrant_test_injections") <= 0:
            raise AssertionError(f"{mode}: no actual synchronous callback injection")
        if mode != "native":
            for field in ("executed_steps", "ir016_typed_regions"):
                if stat(report["diagnostic"], field) <= 0:
                    raise AssertionError(f"{mode}: IR never executed ({field})")
            if mode != "interpreted" and stat(
                    report["diagnostic"], "bytecode_regions") <= 0:
                raise AssertionError(f"{mode}: JVM ASM not emitted")
            if mode in ("bytecode", "direct", "interpreted"):
                if stat(report["diagnostic"], "conditional_steps") <= 0:
                    raise AssertionError(f"{mode}: ranged conditional never executed")
                if stat(report["diagnostic"], "guarded_binary_steps") <= 0:
                    raise AssertionError(f"{mode}: binary terminal never directly lowered")
                if stat(report["diagnostic"], "reentrant_yields") <= 0:
                    raise AssertionError(f"{mode}: failed to yield to native callback queue")
        report["status"] = "complete"
        print("IR017_NATIVE_ARM " + json.dumps({
            "mode": mode, "observations": len(report["cases"]),
            "diagnostic": report["diagnostic"],
            "layouts": report["layouts"]
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
    report = {"milestone": "COMPILER-IR-017", "status": "started",
              "arms": [], "performance_claim": False,
              "production_promotion": False}
    try:
        for mode in MODES:
            report["arms"].append(run_arm(mode))
            (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        reference = report["arms"][0]["cases"]
        for arm in report["arms"][1:]:
            differences = {case: {"native": reference[case], "mode": observed}
                           for case, observed in arm["cases"].items()
                           if observed != reference[case]}
            if differences:
                raise AssertionError(f"IR017 parity mismatch in {arm['mode']}: "
                                     + json.dumps(dict(list(differences.items())[:4])))
        report["native_semantic_parity"] = True
        report["cases_per_arm"] = len(reference)
        report["status"] = "accepted"
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR017_SUMMARY " + json.dumps({
        "status": report["status"], "native_semantic_parity":
        report.get("native_semantic_parity"), "cases_per_arm":
        report.get("cases_per_arm"), "performance_claim": False
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
