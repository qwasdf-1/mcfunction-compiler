#!/usr/bin/env python3
"""IR-018: @s source-context scoreboard lowering and native function dispatch.

Five independent Minecraft 26.3 JVMs (unmodified native, IR-017 code with
selector feature disabled, IR-018 interpreter, IR-018 ASM, IR-018 ASM+direct)
execute the SAME mcfunctions with an actual armor stand source and with no
entity source. All scoreboard states and partial command quotas must match
native. The direct backend must NEVER admit a function-dispatch barrier.
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
from ci_typed_ir013 import stop, stat
from ci_typed_ir017 import nullable_score

OUT = ROOT / "build/reports/COMPILER-IR-018"
PACK = "fc_typed_ir018"
MODES = ("native", "old_bytecode", "interpreted", "bytecode", "direct")
QUOTAS = (1, 2, 3, 4, 5, 6, 8, 12, 16, 32, 64)
SELECTOR = "@e[type=minecraft:armor_stand,tag=ir018_test,limit=1]"
FUNCTIONS = {
    "ir018_child": [
        "scoreboard players add @s fc_ir 7",
    ],
    "ir018_child_return": [
        "scoreboard players add @s fc_ir 4",
        "return 0",
        "scoreboard players add @s fc_ir 100",
    ],
    "ir018_self_mutation": [
        "scoreboard players set @s fc_ir 2",
        "scoreboard players add @s fc_ir 4",
        "scoreboard players remove @s fc_ir 1",
        "scoreboard players set #g fc_ir 4",
        "scoreboard players operation @s fc_ir += #g fc_ir",
        "scoreboard players operation #g fc_ir += @s fc_ir",
    ],
    "ir018_self_binary": [
        "scoreboard players set @s fc_ir 2",
        "scoreboard players set @s fc_source 3",
        "scoreboard players operation @s fc_ir += @s fc_source",
        "scoreboard players operation #g fc_ir += @s fc_ir",
        "scoreboard players operation @s fc_ir *= #mult fc_ir",
        "scoreboard players operation @s fc_ir = #g fc_ir",
    ],
    "ir018_self_guard": [
        "scoreboard players set @s fc_ir 2",
        "scoreboard players set #g fc_ir 4",
        "execute if score @s fc_ir matches 2..4 run scoreboard players add @s fc_ir 3",
        "execute unless score @s fc_ir matches ..4 run scoreboard players operation @s fc_ir += #g fc_ir",
        "execute if score #g fc_ir matches 4 run scoreboard players operation #g fc_ir += @s fc_ir",
        "execute unless score @s fc_ir matches 0..8 run scoreboard players set @s fc_ir 100",
        "scoreboard players add @s fc_ir 1",
    ],
    "ir018_dispatch": [
        "scoreboard players set @s fc_ir 1",
        "scoreboard players add @s fc_ir 1",
        "execute if score @s fc_ir matches 1..3 run function fc_ir:ir018_child",
        "execute unless score @s fc_ir matches ..8 run function fc_ir:ir018_child",
        "scoreboard players add @s fc_ir 2",
        "scoreboard players add @s fc_ir 3",
    ],
    "ir018_dispatch_return": [
        "scoreboard players set @s fc_ir 3",
        "scoreboard players add @s fc_ir 1",
        "execute if score @s fc_ir matches 4.. run function fc_ir:ir018_child_return",
        "scoreboard players add @s fc_ir 2",
        "scoreboard players add @s fc_ir 3",
    ],
    "ir018_context_barrier": [
        "scoreboard players set #g fc_ir 1",
        f"execute as {SELECTOR} run scoreboard players add @s fc_ir 9",
        "scoreboard players add #g fc_ir 2",
        "scoreboard players add #g fc_ir 3",
    ],
    "ir018_missing_self": [
        "scoreboard players set #g fc_ir 1",
        "execute if score @s fc_ir matches 1.. run scoreboard players add #g fc_ir 100",
        "scoreboard players add @s fc_ir 5",
        "scoreboard players add #g fc_ir 2",
    ],
    "ir018_missing_objective": [
        "scoreboard players set @s fc_ir 1",
        "scoreboard players add @s fc_ir 2",
        "scoreboard players add @s fc_absent 7",
        "execute if score @s fc_absent matches 1.. run scoreboard players add @s fc_ir 100",
        "scoreboard players add @s fc_ir 3",
        "scoreboard players add @s fc_ir 4",
    ],
}
ENTITY_CASES = tuple(x for x in FUNCTIONS if x not in (
    "ir018_child", "ir018_child_return", "ir018_missing_self"))
NO_ENTITY_CASES = ("ir018_self_mutation", "ir018_self_guard", "ir018_missing_self")
EXPECTED_ENTITY = {
    "ir018_self_mutation": {"self": 9, "g": 13},
    "ir018_self_binary": {"self": 5, "g": 5},
    "ir018_self_guard": {"self": 10, "g": 13},
    "ir018_dispatch": {"self": 21},
    "ir018_dispatch_return": {"self": 13},
    "ir018_context_barrier": {"g": 6, "self": 9},
    "ir018_missing_objective": {"self": 10, "missing": False},
}


def fixture(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    folder = root / "data/fc_ir/function"
    folder.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR018 dynamic source and opaque child-frame test",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, lines in FUNCTIONS.items():
        (folder / (name + ".mcfunction")).write_text(
            "\n".join(lines) + "\n", encoding="utf-8")


def options(mode: str) -> dict[str, str]:
    assert mode in MODES
    compiled = mode != "native"
    return {
        "FC_WRAPPER_PROBE": str(compiled).lower(),
        "FC_TYPED_IR_MODE": ("interpreted" if mode == "interpreted" else "bytecode")
                            if compiled else "",
        "FC_TYPED_IR_NAMESPACE": "fc_ir" if compiled else "",
        "FC_TYPED_IR_SELF_HOLDER": str(mode in MODES[2:]).lower(),
        "FC_TYPED_IR_RANGE_GUARDS": "true",
        "FC_TYPED_IR_DIAGNOSTICS": "true",
        "FC_TYPED_IR_REENTRANT_SAFE": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_TOGGLE": "true",
        "FC_TYPED_IR_DIRECT_FUNCTION_HARNESS": "true",
        "FC_TYPED_IR_SELF_TEST_HARNESS": "true",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER": "false",
        "FC_TYPED_IR_SCORE_CACHE": "false",
        "FC_TYPED_IR_SINGLETON_FEEDBACK": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
    }


def start(mode: str):
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    work = RUNS / ("ci-ir018-" + mode)
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
        "view-distance=2", "simulation-distance=2", "max-tick-time=-1",
        "max-players=1", f"server-port={port}", f"rcon.port={rcon_port}",
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
            raise AssertionError(f"{mode}: test datapack was not loaded")
        for obj in ("fc_ir", "fc_source"):
            client.command(f"scoreboard objectives add {obj} dummy")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        client.command("gamerule sendCommandFeedback false")
        # A headless server has no player ticket. Without a forced chunk the
        # new entity can immediately be unloaded before an RCON snapshot.
        client.command("forceload add 0 0")
        # A no-player superflat world has no guaranteed surface at y=64.
        # Place a solid platform before summoning so an armor stand cannot
        # die from a long drop or from spawning inside default flat terrain.
        platform = client.command("setblock 0 63 0 minecraft:stone")
        result = client.command('summon minecraft:armor_stand 0 64 0')
        if "Summoned new" not in result:
            raise AssertionError(f"{mode}: source entity not summoned: {result!r}")
        client.command(
            'tag @e[type=minecraft:armor_stand,limit=1,sort=nearest] add ir018_test')
        check = client.command(f"data get entity {SELECTOR} UUID")
        if "UUID" not in check:
            all_armor = client.command(
                'data get entity @e[type=minecraft:armor_stand,limit=1] UUID')
            forced = client.command("forceload query 0 0")
            raise AssertionError(
                f"{mode}: source entity not resident/tagged: tagged={check!r}, "
                f"any_armor={all_armor!r}, forceload={forced!r}, platform={platform!r}")
        if mode in ("old_bytecode", "interpreted", "bytecode"):
            result = client.command("fc_ir012_direct off")
            if "enabled=false" not in result:
                raise AssertionError(f"{mode}: direct compiler not disabled: {result!r}")
        return process, client, log
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        log.close()
        raise


def entity_score(client, obj: str) -> int | None:
    # Resolve the one tagged entity directly as a scoreboard holder from
    # console, so the RCON response is not suppressed by execute-as.
    response=client.command(
        f"scoreboard players get {SELECTOR} {obj}")
    match=re.search(r"has (-?\d+)", response)
    if match:
        return int(match.group(1))
    if "none is set" in response:
        return None
    raise AssertionError(f"Unexpected selector score result: {response!r}")


def reset(client) -> None:
    client.command("gamerule minecraft:max_command_sequence_length 65536")
    for objective in ("fc_ir", "fc_source"):
        client.command(f"scoreboard players set #g {objective} 0")
        client.command(f"scoreboard players set #mult {objective} 2")
        client.command(
            f"execute as {SELECTOR} run scoreboard players reset @s {objective}")
    client.command("scoreboard objectives remove fc_absent")


def snapshot(client) -> dict:
    return {
        "self": entity_score(client, "fc_ir"),
        "self_source": entity_score(client, "fc_source"),
        "g": nullable_score(client, "#g", "fc_ir"),
        "mult": nullable_score(client, "#mult", "fc_ir"),
        "absent": nullable_score(client, "#never", "fc_ir"),
        "missing": "fc_absent" in client.command("scoreboard objectives list"),
    }


def invoke(client, name: str, *, as_entity: bool) -> None:
    prefix = f"execute as {SELECTOR} run " if as_entity else ""
    response = client.command(prefix + f"fc_ir018_call fc_ir:{name}")
    # In Minecraft, execute-as returns the result command but may suppress
    # child CommandSourceStack feedback to the RCON caller, yielding "".
    # A real entity invocation is validated by independent expected game
    # state and source identity below; no-entity control still has feedback.
    if (not as_entity and "FC_ARCH_CALL queued" not in response) or (
            as_entity and ("invalid or disallowed" in response
                           or "no execution context" in response)):
        raise AssertionError(f"IR018 call rejected: {name}/{as_entity}: {response!r}")


def ledger(client, name: str) -> dict:
    raw = client.command(f"functioncompiler ir016 fc_ir:{name}")
    if not raw.startswith("IR016 function="):
        raise AssertionError(f"Missing compiled program ledger: {raw!r}")
    info = {"raw": raw}
    for field in ("source_lines", "typed_lines", "typed_regions",
                  "opaque_barriers", "singleton_barriers", "dispatch_barriers"):
        found = re.search(rf"\b{field}=(\d+)", raw)
        if not found:
            raise AssertionError(f"No field {field} in {raw!r}")
        info[field] = int(found.group(1))
    info["direct_candidate"] = "direct_candidate=true" in raw
    return info


def run_arm(mode: str) -> dict:
    process, client, log = start(mode)
    report = {"mode": mode, "status": "started", "snapshots": {}, "layouts": {}}
    try:
        for name in ENTITY_CASES:
            reset(client)
            invoke(client, name, as_entity=True)
            data = snapshot(client)
            report["snapshots"][name] = data
            if mode == "native":
                for key, expected in EXPECTED_ENTITY.get(name, {}).items():
                    if data[key] != expected:
                        raise AssertionError(f"Vanilla/{name}/{key}: {data[key]} != {expected}")
        for name in NO_ENTITY_CASES:
            reset(client)
            invoke(client, name, as_entity=False)
            report["snapshots"][name + "_no_entity"] = snapshot(client)
        if mode != "native":
            for name in ("ir018_self_mutation", "ir018_self_binary", "ir018_self_guard",
                         "ir018_dispatch", "ir018_dispatch_return", "ir018_context_barrier"):
                report["layouts"][name] = ledger(client, name)
            disp = report["layouts"]["ir018_dispatch"]
            if disp["dispatch_barriers"] < 2 or disp["direct_candidate"]:
                raise AssertionError(f"Child function dispatch crossed direct scheduler: {disp}")
            if mode in MODES[2:]:
                if report["layouts"]["ir018_self_mutation"]["typed_lines"] < 6:
                    raise AssertionError("No native @s mutation/binary compilation")
                if report["layouts"]["ir018_self_guard"]["typed_lines"] < 5:
                    raise AssertionError("No native dynamic @s range predicate compilation")
            else:
                if report["layouts"]["ir018_self_mutation"]["typed_lines"] >= 6:
                    raise AssertionError("Old compiler inadvertently compiled @s")
        for quota in QUOTAS:
            for name in ENTITY_CASES:
                reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                text = client.command("gamerule minecraft:max_command_sequence_length")
                numbers = re.findall(r"\d+", text)
                if not numbers or int(numbers[-1]) != quota:
                    raise AssertionError(f"Command quota not applied: {text!r}")
                invoke(client, name, as_entity=True)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["snapshots"][f"{name}_quota_{quota}"] = snapshot(client)
        report["compiler_diagnostic"] = client.command("functioncompiler ir008")
        if mode != "native":
            info = report["compiler_diagnostic"]
            if stat(info, "executed_steps") <= 0:
                raise AssertionError(f"No actual typed steps: {info}")
            if (mode in ("old_bytecode", "bytecode", "direct")
                    and stat(info, "bytecode_regions") <= 0):
                raise AssertionError(f"No emitted bytecode regions: {info}")
            if mode == "direct" and stat(info, "direct_function_executed") <= 0:
                raise AssertionError(f"No eligible direct native function calls: {info}")
        report["status"] = "complete"
        print("IR018_ARM " + json.dumps({
            "mode": mode, "snapshots": len(report["snapshots"]),
            "compiler_diagnostic": report["compiler_diagnostic"],
            "layouts": report["layouts"],
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
    study = {"milestone": "COMPILER-IR-018", "status": "started", "arms": [],
             "production_promotion": False, "performance_claim": False}
    try:
        for mode in MODES:
            study["arms"].append(run_arm(mode))
            (OUT / "results.json").write_text(json.dumps(study, indent=2) + "\n")
        reference = study["arms"][0]["snapshots"]
        for arm in study["arms"][1:]:
            divergences = {
                case: {"native": reference[case], "observed": actual}
                for case, actual in arm["snapshots"].items()
                if reference[case] != actual
            }
            if divergences:
                raise AssertionError(
                    f"IR018 {arm['mode']} native divergence: "
                    + json.dumps(dict(list(divergences.items())[:4])))
        study["status"] = "accepted"
        study["native_semantic_parity"] = True
        study["cases_per_arm"] = len(reference)
    except BaseException as error:
        study["status"] = "invalid"
        study["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(study, indent=2) + "\n")
    print("IR018_SUMMARY " + json.dumps({
        "status": study["status"], "cases_per_arm": study.get("cases_per_arm"),
        "native_semantic_parity": study.get("native_semantic_parity"),
        "production_promotion": False, "performance_claim": False
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
