#!/usr/bin/env python3
"""Differentially exercise vanilla selector and entity-NBT paths on Minecraft 26.3."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_runtime_probe import (  # noqa: E402
    RconClient,
    locate_official_server_jar,
    run_debug_trace_fixture,
)
from mod_artifacts import MODS, MODS_DIR  # noqa: E402

REPORT_DIR = ROOT / "build" / "reports" / "compatibility-probe"
SERVER_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
EXPECTED_HOME_POSITION_RESULTS = {
    "compat_nbt_home_init": "Zombie has the following entity data: [I; 72, 64, 72]",
    "compat_nbt_home_merge": "Zombie has the following entity data: [I; 76, 64, 76]",
    "compat_nbt_home_pos": "Zombie has the following entity data: [I; 80, 64, 80]",
    "compat_nbt_home_remove": "Zombie has the following entity data: [I; 0, 0, 0]",
}
EXPECTED_HOME_RADIUS_RESULTS = {
    "initial": {
        "home_radius": "Zombie has the following entity data: 8",
        "home_pos": "Zombie has the following entity data: [I; 56, 64, 0]",
    },
    "compat_nbt_home_radius_modify": {
        "home_radius": "Zombie has the following entity data: 12",
        "home_pos": "Zombie has the following entity data: [I; 56, 64, 0]",
    },
    "compat_nbt_home_radius_remove": {
        "home_radius": "Found no elements matching home_radius",
        "home_pos": "Found no elements matching home_pos",
    },
}
RCON_HOST = "127.0.0.1"
RCON_PASSWORD = "function-compiler-compatibility-probe"
MODES = (
    "vanilla",
    "fabric-off",
    "fabric-on",
    "score-add-on",
    "fused-interpreted",
    "bytecode-emitted",
    "bellows-off",
    "bellows-on",
    "bellows-score-add-on",
    "bellows-fused-interpreted",
    "bellows-bytecode-emitted",
    "bellows-moonrise120-off",
    "bellows-moonrise120-on",
    "bellows-moonrise120-score-add-on",
    "bellows-moonrise120-fused-interpreted",
    "bellows-moonrise120-bytecode-emitted",
    "lbm113120-off",
    "lbm113120-on",
    "lbm113120-score-add-on",
    "lbm113120-fused-interpreted",
    "lbm113120-bytecode-emitted",
)


def mode_mod_keys(mode: str) -> tuple[str, ...]:
    if mode.startswith("lbm113120-"):
        return ("lithium", "bellows113", "moonrise120")
    if mode.startswith("bellows-moonrise120-"):
        return ("bellows", "moonrise120")
    if mode.startswith("bellows-"):
        return ("bellows",)
    return ()


def mode_wrapper_enabled(mode: str) -> bool:
    return mode != "vanilla" and not mode.endswith("-off")


def mode_score_add_enabled(mode: str) -> bool:
    return (
        mode == "score-add-on"
        or mode.endswith("-score-add-on")
        or mode == "fused-interpreted"
        or mode.endswith("-fused-interpreted")
        or mode == "bytecode-emitted"
        or mode.endswith("-bytecode-emitted")
    )


def mode_fused_enabled(mode: str) -> bool:
    return mode == "fused-interpreted" or mode.endswith("-fused-interpreted")


def mode_bytecode_enabled(mode: str) -> bool:
    return mode == "bytecode-emitted" or mode.endswith("-bytecode-emitted")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind((RCON_HOST, 0))
        return int(sock.getsockname()[1])


def wait_for_rcon(
    process: subprocess.Popen[bytes], port: int, timeout: int = 240
) -> RconClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited early with code {process.returncode}")
        try:
            return RconClient(RCON_HOST, port, RCON_PASSWORD)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(1)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def write_server_files(work: Path, port: int, include_modded_command: bool) -> None:
    world = work / "world"
    datapack = world / "datapacks" / "function_compiler_probe"
    shutil.copytree(ROOT / "src" / "main" / "resources" / "data", datapack / "data")
    if include_modded_command:
        fixture_data = (
            ROOT / "tests" / "fixtures" / "function_compiler_modded_command" / "data"
        )
        shutil.copytree(fixture_data, datapack / "data", dirs_exist_ok=True)
    (datapack / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "Function Compiler compatibility probe",
                    "min_format": [97, 1],
                    "max_format": [97, 1],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    properties = {
        "enable-rcon": "true",
        "rcon.password": RCON_PASSWORD,
        "rcon.port": str(port),
        "broadcast-rcon-to-ops": "false",
        "server-ip": RCON_HOST,
        "server-port": str(free_port()),
        "level-name": "world",
        "level-seed": "264026",
        "online-mode": "false",
        "white-list": "false",
        "spawn-protection": "0",
        "max-players": "1",
        "view-distance": "4",
        "simulation-distance": "4",
        "sync-chunk-writes": "false",
        "pause-when-empty-seconds": "-1",
    }
    (work / "server.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()),
        encoding="utf-8",
    )


def start_server(mode: str, work: Path, server_jar: Path, log_path: Path):
    log_handle = log_path.open("wb")
    if mode == "vanilla":
        command = ["java", "-Xms512M", "-Xmx2G", "-jar", str(server_jar), "nogui"]
        cwd = work
        env = None
    else:
        env = os.environ.copy()
        gradle_home = ROOT / ".gradle-user-home"
        if "GRADLE_USER_HOME" not in env and gradle_home.is_dir():
            env["GRADLE_USER_HOME"] = str(gradle_home)
        shared_cache = Path.home() / ".gradle" / "caches"
        if ("GRADLE_RO_DEP_CACHE" not in env
                and "GRADLE_USER_HOME" not in env
                and shared_cache.is_dir()):
            env["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
        env.update(
            {
                "FC_WRAPPER_PROBE": (
                    "true" if mode_wrapper_enabled(mode) else "false"
                ),
                "FC_SCORE_ADD_PROTOTYPE": (
                    "true" if mode_score_add_enabled(mode) else "false"
                ),
                "FC_SCORE_ADD_METRICS": (
                    "true" if mode_score_add_enabled(mode) else "false"
                ),
                "FC_FUSED_REGION_PROTOTYPE": (
                    "true" if mode_fused_enabled(mode) else "false"
                ),
                "FC_BYTECODE_REGION_PROTOTYPE": (
                    "true" if mode_bytecode_enabled(mode) else "false"
                ),
                "FC_RUNTIME_TRACE": "false",
            }
        )
        command = [str(ROOT / "gradlew"), "--no-daemon"]
        if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
            command.append("--offline")
        command.extend(
            [f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}", "runServer"]
        )
        cwd = ROOT
        mod_keys = mode_mod_keys(mode)
        if mod_keys:
            mods = work / "mods"
            mods.mkdir()
            for mod_key in mod_keys:
                mod_name, _ = MODS[mod_key]
                shutil.copy2(MODS_DIR / mod_name, mods / mod_name)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def command(client: RconClient, text: str) -> str:
    return client.command(text)


def entity_tags(client: RconClient, selector: str, path: str = "Tags") -> list[str]:
    response = command(client, f"data get entity {selector} {path}")
    return sorted(re.findall(r'"([^"\\]+)"', response))


def run_selector_cases(client: RconClient) -> dict[str, object]:
    command(client, "scoreboard objectives add fc_compat dummy")
    command(client, "scoreboard objectives add fc_compat_order dummy")
    command(client, "forceload add 0 0 256 32")
    common = "NoGravity:1b,Invisible:1b,Invulnerable:1b"
    actors = (
        ("0.5 100 0.5", "fc_compat_selector,fc_compat_inside_tagged,fc_compat_limit", ""),
        ("-0.35 100 0.5", "fc_compat_selector,fc_compat_near_outside,fc_compat_limit", ""),
        ("3.5 100 0.5", "fc_compat_selector,fc_compat_far_outside", ""),
        ("0.75 100 0.75", "fc_compat_inside_untagged", ""),
        ("16.5 100 0.5", "fc_compat_selector,fc_compat_second_inside", ""),
        ("32.5 100 0.5", "fc_compat_order,fc_compat_order_a", ""),
        ("33.5 100 0.5", "fc_compat_order,fc_compat_order_b", ""),
        ("34.5 100 0.5", "fc_compat_order,fc_compat_order_c", ""),
        ("64.5 100 0.5", "fc_compat_selector,fc_compat_nbt_silent", ",Silent:1b"),
        ("65.5 100 0.5", "fc_compat_selector,fc_compat_nbt_glow", ",Glowing:1b"),
    )
    for position, tags, extra_nbt in actors:
        for _ in range(10):
            res = command(
                client,
                f'summon minecraft:armor_stand {position} '
                f'{{{common}{extra_nbt},Tags:["{tags.replace(",", chr(34)+","+chr(34))}"]}}',
            )
            if "Summoned" in res:
                break
            time.sleep(0.05)
    command(client, "scoreboard players set @e[tag=fc_compat_far_outside] fc_compat 7")
    command(client, "scoreboard players set @e[tag=fc_compat_second_inside] fc_compat 7")
    command(client, "scoreboard players set @e[tag=fc_compat_order_a] fc_compat_order 2")
    command(client, "scoreboard players set @e[tag=fc_compat_order_b] fc_compat_order 3")
    command(client, "scoreboard players set @e[tag=fc_compat_order_c] fc_compat_order 5")
    command(client, "scoreboard players set #fc_compat_order_last fc_compat_order 7")

    feedback: dict[str, str] = {}
    for fixture in (
        "compat_selector_tag_box",
        "compat_selector_untagged_box",
        "compat_selector_tag_box_limit",
        "compat_selector_second_box",
        "compat_selector_nearest_order",
        "compat_selector_distance",
        "compat_selector_furthest_limit",
        "compat_selector_score_box",
        "compat_selector_negated_tag_box",
        "compat_selector_nbt_match",
        "compat_selector_nbt_no_match",
    ):
        feedback[fixture] = command(client, f"function function_compiler_probe:{fixture}")

    tag_to_selector = {
        tag: f"@e[tag={tag},limit=1]"
        for tag in (
            "fc_compat_inside_tagged",
            "fc_compat_near_outside",
            "fc_compat_far_outside",
            "fc_compat_inside_untagged",
            "fc_compat_second_inside",
            "fc_compat_order_a",
            "fc_compat_order_b",
            "fc_compat_order_c",
            "fc_compat_nbt_silent",
            "fc_compat_nbt_glow",
        )
    }
    tags_after = {
        identity: entity_tags(client, selector)
        for identity, selector in tag_to_selector.items()
    }
    selection_markers = (
        "fc_compat_tag_box_selected",
        "fc_compat_untagged_box_selected",
        "fc_compat_limit_selected",
        "fc_compat_second_box_selected",
        "fc_compat_distance_selected",
        "fc_compat_score_box_selected",
        "fc_compat_negated_tag_box_selected",
        "fc_compat_furthest_selected",
        "fc_compat_nbt_match_selected",
        "fc_compat_nbt_no_match_selected",
    )
    observed_selection = {
        identity: [marker for marker in selection_markers if marker in tags]
        for identity, tags in tags_after.items()
    }
    expected_selection = {
        "fc_compat_inside_tagged": [
            "fc_compat_tag_box_selected",
            "fc_compat_untagged_box_selected",
            "fc_compat_limit_selected",
            "fc_compat_distance_selected",
        ],
        "fc_compat_near_outside": ["fc_compat_distance_selected"],
        "fc_compat_far_outside": [
            "fc_compat_score_box_selected",
        ],
        "fc_compat_inside_untagged": ["fc_compat_untagged_box_selected"],
        "fc_compat_second_inside": [
            "fc_compat_second_box_selected",
            "fc_compat_negated_tag_box_selected",
        ],
        "fc_compat_order_a": [],
        "fc_compat_order_b": [],
        "fc_compat_order_c": ["fc_compat_furthest_selected"],
        "fc_compat_nbt_silent": ["fc_compat_nbt_match_selected"],
        "fc_compat_nbt_glow": ["fc_compat_nbt_no_match_selected"],
    }
    if observed_selection != expected_selection:
        raise RuntimeError(
            f"Selector fixture selected unexpected entities: {observed_selection!r}"
        )
    order_holders = (
        "#fc_compat_order_last",
        "@e[tag=fc_compat_order_a,limit=1]",
        "@e[tag=fc_compat_order_b,limit=1]",
        "@e[tag=fc_compat_order_c,limit=1]",
    )
    order_scores = {h: command(client, f"scoreboard players get {h} fc_compat_order") for h in order_holders}
    order_values = {h: int(re.search(r"has (-?\d+)", r).group(1)) for h, r in order_scores.items()}
    expected_order_values = {
        "#fc_compat_order_last": 5,
        "@e[tag=fc_compat_order_a,limit=1]": 7,
        "@e[tag=fc_compat_order_b,limit=1]": 2,
        "@e[tag=fc_compat_order_c,limit=1]": 3,
    }
    if order_values != expected_order_values:
        raise RuntimeError(f"Nearest-order swap result changed: {order_values!r}")

    def read_order_score(holder: str) -> int:
        response = command(
            client, f"scoreboard players get {holder} fc_compat_order"
        )
        match = re.search(r"has (-?\d+)", response)
        if match is None:
            raise RuntimeError(
                f"Could not read compatibility fork score for {holder}: "
                f"{response!r}"
            )
        return int(match.group(1))

    actor_holders = (
        "@e[tag=fc_compat_order_a,limit=1]",
        "@e[tag=fc_compat_order_b,limit=1]",
        "@e[tag=fc_compat_order_c,limit=1]",
    )
    initial_order_scores = (2, 3, 5)
    low_fork_cases: dict[str, list[dict[str, object]]] = {}
    for sort in ("nearest", "furthest", "random", "arbitrary"):
        cases: list[dict[str, object]] = []
        for fork_limit in (1, 2, 3, 4):
            fork_response = command(
                client, f"gamerule minecraft:max_command_forks {fork_limit}"
            )
            if str(fork_limit) not in fork_response:
                raise RuntimeError(
                    f"Could not set {sort} compatibility fork cap to "
                    f"{fork_limit}: {fork_response!r}"
                )
            command(client, "gamerule minecraft:max_command_sequence_length 65536")
            actor_start = (
                initial_order_scores
                if sort in {"nearest", "furthest"}
                else (0, 0, 0)
            )
            for holder, value in zip(actor_holders, actor_start):
                command(
                    client,
                    f"scoreboard players set {holder} fc_compat_order {value}",
                )
            command(
                client,
                "scoreboard players set #fc_compat_fork_acc "
                f"fc_compat_order {7 if sort in {'nearest', 'furthest'} else 0}",
            )
            command(
                client,
                f"scoreboard players set #fc_compat_fork_followup "
                "fc_compat_order 0",
            )

            direct_command = (
                "execute positioned 32 100 0 as "
                f"@e[type=minecraft:armor_stand,tag=fc_compat_order,"
                f"sort={sort},limit=2] run "
                + (
                    "scoreboard players operation #fc_compat_fork_acc "
                    "fc_compat_order >< @s fc_compat_order"
                    if sort in {"nearest", "furthest"}
                    else "scoreboard players add @s fc_compat_order 1"
                )
            )
            direct_response = command(
                client,
                direct_command,
            )
            direct_scores = tuple(
                read_order_score(holder) for holder in actor_holders
            )
            direct_accumulator = read_order_score("#fc_compat_fork_acc")
            expected_branch_count = 0 if fork_limit < 3 else 2
            overflow_reported = (
                "maximum number of contexts (1) reached"
                in direct_response.casefold()
            )
            no_feedback = direct_response == ""
            if fork_limit == 1 and not overflow_reported:
                raise RuntimeError(
                    f"{sort} Bellows compatibility fork cap 1 returned "
                    f"{direct_response!r}; expected maximum-context error"
                )
            if fork_limit == 2 and not no_feedback:
                raise RuntimeError(
                    f"{sort} Bellows compatibility fork cap 2 returned "
                    f"unexpected feedback: {direct_response!r}"
                )

            for holder, value in zip(actor_holders, actor_start):
                command(
                    client,
                    f"scoreboard players set {holder} fc_compat_order {value}",
                )
            command(
                client,
                "scoreboard players set #fc_compat_fork_acc "
                f"fc_compat_order {7 if sort in {'nearest', 'furthest'} else 0}",
            )
            command(
                client,
                "scoreboard players set #fc_compat_fork_followup "
                "fc_compat_order 0",
            )
            command(
                client,
                f"function function_compiler_probe:compat_fork_{sort}_resume",
            )
            function_scores = tuple(
                read_order_score(holder) for holder in actor_holders
            )
            function_accumulator = read_order_score("#fc_compat_fork_acc")
            function_followup = read_order_score("#fc_compat_fork_followup")
            if function_followup != 10:
                raise RuntimeError(
                    f"{sort} Bellows compatibility function at cap {fork_limit} "
                    f"left follow-up {function_followup}; expected 10"
                )

            if sort == "nearest":
                expected_scores = (
                    (2, 3, 5) if fork_limit < 3 else (7, 2, 5)
                )
                expected_accumulator = 7 if fork_limit < 3 else 3
                if direct_scores != expected_scores or function_scores != expected_scores:
                    raise RuntimeError(
                        f"Bellows nearest fork at cap {fork_limit} changed actors "
                        f"direct/function={direct_scores!r}/{function_scores!r}; "
                        f"expected {expected_scores!r}"
                    )
                if direct_accumulator != expected_accumulator or function_accumulator != expected_accumulator:
                    raise RuntimeError(
                        f"Bellows nearest fork at cap {fork_limit} changed "
                        f"accumulator direct/function={direct_accumulator}/"
                        f"{function_accumulator}; expected {expected_accumulator}"
                    )
            elif sort == "furthest":
                expected_scores = (
                    (2, 3, 5) if fork_limit < 3 else (2, 5, 7)
                )
                expected_accumulator = 7 if fork_limit < 3 else 3
                if direct_scores != expected_scores or function_scores != expected_scores:
                    raise RuntimeError(
                        f"Bellows furthest fork at cap {fork_limit} changed actors "
                        f"direct/function={direct_scores!r}/{function_scores!r}; "
                        f"expected {expected_scores!r}"
                    )
                if direct_accumulator != expected_accumulator or function_accumulator != expected_accumulator:
                    raise RuntimeError(
                        f"Bellows furthest fork at cap {fork_limit} changed "
                        f"accumulator direct/function={direct_accumulator}/"
                        f"{function_accumulator}; expected {expected_accumulator}"
                    )
            else:
                direct_count = sum(direct_scores)
                function_count = sum(function_scores)
                direct_selected = sum(value == 1 for value in direct_scores)
                function_selected = sum(value == 1 for value in function_scores)
                if (direct_count, direct_selected) != (
                    expected_branch_count,
                    expected_branch_count,
                ):
                    raise RuntimeError(
                        f"Bellows {sort} direct fork at cap {fork_limit} changed "
                        f"{direct_count} total/{direct_selected} actors; expected "
                        f"{expected_branch_count}"
                    )
                if (function_count, function_selected) != (
                    expected_branch_count,
                    expected_branch_count,
                ):
                    raise RuntimeError(
                        f"Bellows {sort} function fork at cap {fork_limit} changed "
                        f"{function_count} total/{function_selected} actors; "
                        f"expected {expected_branch_count}"
                    )
            case: dict[str, object] = {
                "max_command_forks": fork_limit,
                "direct_overflow_reported": overflow_reported,
                "direct_no_feedback": no_feedback,
                "function_followup": function_followup,
            }
            if sort in {"nearest", "furthest"}:
                case["direct_actor_scores"] = direct_scores
                case["direct_accumulator"] = direct_accumulator
                case["function_actor_scores"] = function_scores
                case["function_accumulator"] = function_accumulator
            else:
                case["direct_branch_count"] = sum(direct_scores)
                case["function_branch_count"] = sum(function_scores)
            cases.append(case)
        low_fork_cases[sort] = cases
    command(client, "gamerule minecraft:max_command_forks 65536")
    command(client, "gamerule minecraft:max_command_sequence_length 65536")
    return {
        "function_feedback": feedback,
        "entity_tags": tags_after,
        "selected_entities": observed_selection,
        "order_scores": order_scores,
        "order_values": order_values,
        "low_fork_cases": low_fork_cases,
    }


def run_nbt_cases(client: RconClient) -> dict[str, object]:
    command(client, "forceload add 48 0")
    command(
        client,
        'summon minecraft:zombie 48.5 100 0.5 '
        '{NoAI:0b,Invulnerable:1b,Tags:["fc_compat_nbt"]}',
    )
    command(
        client,
        'summon minecraft:zombie 56.5 100 0.5 '
        '{home_radius:8,home_pos:[I;56,64,0],Tags:["fc_compat_home_radius"]}',
    )
    command(
        client,
        'summon minecraft:villager 60.5 100 0.5 '
        '{VillagerDataFinalized:1b,Tags:["fc_compat_villager_finalized"]}',
    )
    command(
        client,
        'summon minecraft:armor_stand 64 100 0 '
        '{NoGravity:1b,Invisible:1b,Invulnerable:1b,Tags:["fc_compat_passenger_vehicle"]}',
    )
    command(
        client,
        'summon minecraft:armor_stand 64 101 0 '
        '{NoGravity:1b,Invisible:1b,Invulnerable:1b,Tags:["fc_compat_passenger"]}',
    )
    command(
        client,
        "ride @e[tag=fc_compat_passenger,limit=1] mount "
        "@e[tag=fc_compat_passenger_vehicle,limit=1]",
    )
    observations: dict[str, object] = {"function_feedback": {}, "data": {}}
    feedback = observations["function_feedback"]
    assert isinstance(feedback, dict)
    for fixture in ("compat_nbt_modify", "compat_nbt_merge", "compat_nbt_remove"):
        feedback[fixture] = command(client, f"function function_compiler_probe:{fixture}")
        observations["data"][fixture] = {
            key: command(
                client,
                f"data get entity @e[type=minecraft:zombie,tag=fc_compat_nbt,limit=1] {path}",
            )
            for key, path in (("NoAI", "NoAI"), ("PersistenceRequired", "PersistenceRequired"), ("Invulnerable", "Invulnerable"))
        }
    home_path_cases: dict[str, object] = {}
    for fixture in (
        "compat_nbt_home_init",
        "compat_nbt_home_merge",
        "compat_nbt_home_pos",
        "compat_nbt_home_remove",
    ):
        feedback[fixture] = command(
            client,
            f"function function_compiler_probe:{fixture}",
        )
        home_path_cases[fixture] = command(
            client,
            "data get entity @e[type=minecraft:zombie,tag=fc_compat_nbt,limit=1] home_pos",
        )
    observations["home_position_filtered_update"] = home_path_cases
    home_radius_selector = (
        "@e[type=minecraft:zombie,tag=fc_compat_home_radius,limit=1]"
    )
    home_radius_cases: dict[str, object] = {
        "initial": {
            "home_radius": command(
                client,
                f"data get entity {home_radius_selector} home_radius",
            ),
            "home_pos": command(
                client,
                f"data get entity {home_radius_selector} home_pos",
            ),
        }
    }
    for fixture in (
        "compat_nbt_home_radius_modify",
        "compat_nbt_home_radius_remove",
    ):
        feedback[fixture] = command(
            client,
            f"function function_compiler_probe:{fixture}",
        )
        home_radius_cases[fixture] = {
            "feedback": feedback[fixture],
            "home_radius": command(
                client,
                f"data get entity {home_radius_selector} home_radius",
            ),
            "home_pos": command(
                client,
                f"data get entity {home_radius_selector} home_pos",
            ),
        }
    observations["home_radius_filtered_update"] = home_radius_cases
    villager_finalized_selector = (
        "@e[type=minecraft:villager,tag=fc_compat_villager_finalized,limit=1]"
    )
    villager_finalized_feedback = command(
        client,
        "function function_compiler_probe:compat_villager_finalized_modify",
    )
    observations["villager_finalized_filtered_update"] = {
        "feedback": villager_finalized_feedback,
        "value": command(
            client,
            f"data get entity {villager_finalized_selector} VillagerDataFinalized",
        ),
    }
    tag_update_feedback = command(
        client,
        "function function_compiler_probe:compat_nbt_tags_update",
    )
    tag_update_counts = {
        tag: count_entities(client, f"@e[type=minecraft:zombie,tag={tag}]")
        for tag in ("fc_compat_nbt", "fc_compat_nbt_index_probe")
    }
    tag_remove_feedback = command(
        client,
        "function function_compiler_probe:compat_nbt_tags_remove",
    )
    tag_remove_counts = {
        tag: count_entities(client, f"@e[type=minecraft:zombie,tag={tag}]")
        for tag in ("fc_compat_nbt", "fc_compat_nbt_index_probe")
    }
    observations["entity_tag_index"] = {
        "modify_feedback": tag_update_feedback,
        "counts_after_modify": tag_update_counts,
        "remove_feedback": tag_remove_feedback,
        "counts_after_remove": tag_remove_counts,
    }
    if tag_update_counts != {"fc_compat_nbt": 1, "fc_compat_nbt_index_probe": 1}:
        raise RuntimeError(f"Filtered tag write did not update selector index: {tag_update_counts!r}")
    if tag_remove_counts != {"fc_compat_nbt": 0, "fc_compat_nbt_index_probe": 0}:
        raise RuntimeError(f"Filtered tag removal did not clear selector index: {tag_remove_counts!r}")
    passenger_before = command(
        client,
        "data get entity @e[tag=fc_compat_passenger_vehicle,limit=1] Passengers",
    )
    modify_response = command(
        client,
        "function function_compiler_probe:compat_passenger_filtered_write",
    )
    passenger_after = command(
        client,
        "data get entity @e[tag=fc_compat_passenger_vehicle,limit=1] Passengers",
    )
    observations["passenger_filtered_write"] = {
        "before": passenger_before,
        "before_tags": entity_tags(
            client,
            "@e[tag=fc_compat_passenger_vehicle,limit=1]",
            "Passengers[0].Tags",
        ),
        "modify_feedback": modify_response,
        "after": passenger_after,
        "after_tags": entity_tags(
            client,
            "@e[tag=fc_compat_passenger_vehicle,limit=1]",
            "Passengers[0].Tags",
        ),
        "nested_tags_after": command(
            client,
            "data get entity @e[tag=fc_compat_passenger_vehicle,limit=1] Passengers[0].Tags",
        ),
    }
    return observations


def run_score_add_case(client: RconClient, mode: str) -> dict[str, object]:
    def check_fn_score(prep_cmd: str | None, fn: str, expected: int, msg: str, target: str = "#fcprobe"):
        if prep_cmd:
            command(client, prep_cmd)
        fb = command(client, fn if " " in fn else f"function function_compiler_probe:{fn}")
        resp = command(client, f"scoreboard players get {target} fc_probe")
        m = re.search(r"has (-?\d+)", resp)
        if m is None or int(m.group(1)) != expected:
            raise RuntimeError(f"{msg} in {mode}: {resp!r}")
        return fb, resp

    command(client, "scoreboard objectives add fc_probe dummy")
    feedback, score_response = check_fn_score("scoreboard players set #fcprobe fc_probe 5", "score_add_literal", 12, "ScoreAdd literal")
    fused_feedback, fused_score_response = check_fn_score("scoreboard players set #fcprobe fc_probe 0", "fused_score_add", 6, "Fused score add")
    mutated_set_feedback, mutated_set_response = check_fn_score("scoreboard players set #fcprobe fc_probe 100", "score_add_literal", 107, "Mutated set")
    mutated_add_feedback, mutated_add_response = check_fn_score("scoreboard players add #fcprobe fc_probe 50", "score_add_literal", 164, "Mutated add")
    reset_feedback, reset_response = check_fn_score("scoreboard players reset #fcprobe fc_probe", "score_add_literal", 7, "Reset")
    command(client, "scoreboard players set #fcprobe fc_probe 42")
    full_reset_feedback, full_reset_response = check_fn_score("scoreboard players reset #fcprobe", "score_add_literal", 7, "Full reset")
    fused_mutated_feedback, fused_mutated_response = check_fn_score("scoreboard players set #fcprobe fc_probe 200", "fused_score_add", 206, "Fused mutated")
    fused_reset_feedback, fused_reset_response = check_fn_score("scoreboard players reset #fcprobe fc_probe", "fused_score_add", 6, "Fused reset")

    # Self-selector @s support
    command(client, "scoreboard players reset @e[tag=fc_self_actor] fc_probe")
    command(client, "kill @e[tag=fc_self_actor]")
    command(client, 'summon minecraft:armor_stand 0.5 100 0.5 {NoGravity:1b,Invisible:1b,Tags:["fc_self_actor"]}')
    self_feedback, self_score_response = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:score_add_self", 3, "Self add", target="@e[tag=fc_self_actor,limit=1]")
    fused_self_feedback, fused_self_score_response = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:fused_score_add_self", 9, "Fused self", target="@e[tag=fc_self_actor,limit=1]")

    # Expanded operations & reset
    mutate_seq_fb, mutate_seq_resp = check_fn_score("scoreboard players reset #fc_mutate fc_probe", "score_mutation_sequence", 13, "Mutate seq", target="#fc_mutate")
    mutate_self_fb, mutate_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:score_mutation_self", 115, "Mutate self", target="@e[tag=fc_self_actor,limit=1]")
    reset_seq_fb, reset_seq_resp = check_fn_score("scoreboard players reset #reset_seq fc_probe", "score_reset_sequence", 7, "Reset seq", target="#reset_seq")
    reset_self_fb, reset_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:score_reset_self", 15, "Reset self", target="@e[tag=fc_self_actor,limit=1]")

    # Macro region compilation fixtures
    macro_seq_fb, macro_seq_resp = check_fn_score("scoreboard players reset #macro_mutate fc_probe", "function function_compiler_probe:macro_mutation_sequence {start:100,step:25,sub:15}", 120, "Macro seq", target="#macro_mutate")
    macro_self_fb, macro_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:macro_mutation_self {base:50,increment:20}", 67, "Macro self", target="@e[tag=fc_self_actor,limit=1]")
    macro_cf_fb, macro_cf_resp = check_fn_score("scoreboard players reset #macro_cf fc_probe", "function function_compiler_probe:macro_mixed_control_flow {init:60,bonus:15}", 80, "Macro cf", target="#macro_cf")
    macro_reset_fb, macro_reset_resp = check_fn_score("scoreboard players reset #macro_reset fc_probe", 'function function_compiler_probe:macro_reset_sequence {holder:"#macro_reset",init:80,val:22}', 22, "Macro reset", target="#macro_reset")
    macro_reset_self_fb, macro_reset_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:macro_reset_self {init:55,val:33}", 33, "Macro reset self", target="@e[tag=fc_self_actor,limit=1]")

    # Scoreboard operation fixtures
    op_seq_fb, op_seq_resp = check_fn_score("scoreboard players reset #op_a fc_probe", "score_operation_sequence", 24, "Op seq", target="#op_a")
    op_self_fb, op_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:score_operation_self", 12, "Op self", target="@e[tag=fc_self_actor,limit=1]")
    op_macro_fb, op_macro_resp = check_fn_score("scoreboard players reset #op_macro_a fc_probe", "function function_compiler_probe:macro_operation_sequence {a:7,b:3}", 30, "Op macro", target="#op_macro_a")

    # Predicates & store interception (Milestone 1 Stage 1A)
    cond_fb, cond_resp = check_fn_score("scoreboard players reset #c_res fc_probe", "score_condition_fused", 41, "Condition fused", target="#c_res")
    store_fb, store_resp = check_fn_score("scoreboard players reset #s_final fc_probe", "score_store_fused", 180, "Store fused", target="#s_final")
    check_fn_score(None, "scoreboard players get #s_stored_res fc_probe", 8, "Store res", target="#s_stored_res")
    check_fn_score(None, "scoreboard players get #s_stored_succ fc_probe", 1, "Store succ", target="#s_stored_succ")
    check_fn_score(None, "scoreboard players get #s_stored_calc fc_probe", 80, "Store calc", target="#s_stored_calc")
    cond_self_fb, cond_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:score_condition_self", 40, "Cond self", target="@e[tag=fc_self_actor,limit=1]")
    store_self_fb, store_self_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:score_store_self", 40, "Store self", target="@e[tag=fc_self_actor,limit=1]")

    # Context modifier folding (Milestone 1 Stage 1B)
    fold_fb, fold_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:context_folding_fused", 50, "Fold fused", target="@e[tag=fc_self_actor,limit=1]")
    chain_fb, chain_resp = check_fn_score(None, "execute as @e[tag=fc_self_actor,limit=1] run function function_compiler_probe:context_folding_chained", 175, "Fold chained", target="@e[tag=fc_self_actor,limit=1]")
    check_fn_score(None, "scoreboard players get #stored_chain fc_probe", 165, "Stored chain", target="#stored_chain")

    # Storage operations & selective macro (Milestone 1 Stage 1C)
    store_mod_fb, store_mod_resp = check_fn_score("scoreboard players reset #store_test fc_probe", "function function_compiler_probe:storage_modify_fused", 175, "Storage modify fused", target="#store_test")
    macro_store_fb, macro_store_resp = check_fn_score("scoreboard players reset #macro_target fc_probe", "function function_compiler_probe:storage_macro_selective", 65, "Storage macro selective", target="#macro_target")

    # Entity & block predicates (Milestone 1 Stage 1D)
    pred_e_fb, pred_e_resp = check_fn_score("scoreboard players reset #pred_e fc_probe", "function function_compiler_probe:predicate_entity_fused", 125, "Predicate entity fused", target="#pred_e")
    pred_b_fb, pred_b_resp = check_fn_score(None, "function function_compiler_probe:predicate_block_fused", 70, "Predicate block fused", target="#pred_b")

    # Parameterized macro bytecode & Tiered JIT (Milestone 2)
    mbw1_fb, mbw1_resp = check_fn_score("scoreboard players reset #macro_bw_a fc_probe", "function function_compiler_probe:macro_bytecode_workload {base:10,step:15,mult:4}", 150, "Macro bw 1", target="#macro_bw_a")
    mbw2_fb, mbw2_resp = check_fn_score("scoreboard players reset #macro_bw_a fc_probe", "function function_compiler_probe:macro_bytecode_workload {base:5,step:5,mult:2}", 20, "Macro bw 2", target="#macro_bw_a")
    tjit_fb, tjit_resp = check_fn_score("scoreboard players reset #tiered_jit fc_probe", "function function_compiler_probe:tiered_jit_transition", 60, "Tiered jit", target="#tiered_jit")
    for _ in range(4): command(client, "function function_compiler_probe:tiered_jit_transition")
    tjit5_fb, tjit5_resp = check_fn_score(None, "scoreboard players get #tiered_jit fc_probe", 300, "Tiered 5x", target="#tiered_jit")

    prototype_enabled = mode_score_add_enabled(mode)
    fused_enabled = mode_fused_enabled(mode)
    bytecode_enabled = mode_bytecode_enabled(mode)
    diagnostics = {"enabled": prototype_enabled, "compiled": 0, "executed": 0}
    fused_diagnostics = {"enabled": fused_enabled, "compiled": 0, "executed": 0}
    bytecode_diagnostics = {
        "enabled": bytecode_enabled, "compiled": 0, "compile_failed": 0, "executed": 0,
    }
    if mode != "vanilla":
        status = command(client, "function_compiler_probe status")
        for key, expected in (
            ("score_add_prototype_enabled", prototype_enabled),
            ("score_add_metrics_enabled", prototype_enabled),
            ("fused_region_prototype_enabled", fused_enabled),
            ("bytecode_region_prototype_enabled", bytecode_enabled),
        ):
            if f"{key}={str(expected).lower()}" not in status:
                raise RuntimeError(f"Unexpected {key} in {mode}: {status!r}")
        compiled_match = re.search(r"score_add_compiled=(\d+)", status)
        executed_match = re.search(r"score_add_executed=(\d+)", status)
        if compiled_match is None or executed_match is None:
            raise RuntimeError(f"Missing ScoreAdd diagnostics in {mode}: {status!r}")
        compiled = int(compiled_match.group(1))
        executed = int(executed_match.group(1))
        diagnostics.update({"compiled": compiled, "executed": executed})
        if prototype_enabled and (compiled < 1 or executed < 1):
            raise RuntimeError(
                f"ScoreAdd did not compile and execute in {mode}: "
                f"compiled={compiled}, executed={executed}"
            )
        if not prototype_enabled and executed != 0:
            raise RuntimeError(f"ScoreAdd unexpectedly executed in {mode}: {status!r}")
        fused_compiled_match = re.search(r"fused_regions_compiled=(\d+)", status)
        fused_executed_match = re.search(r"fused_regions_executed=(\d+)", status)
        if fused_compiled_match is None or fused_executed_match is None:
            raise RuntimeError(f"Missing fused-region diagnostics in {mode}: {status!r}")
        fused_compiled = int(fused_compiled_match.group(1))
        fused_executed = int(fused_executed_match.group(1))
        fused_diagnostics.update({"compiled": fused_compiled, "executed": fused_executed})
        if fused_enabled and (fused_compiled < 1 or fused_executed < 1):
            raise RuntimeError(
                f"Fused region did not compile and execute in {mode}: "
                f"compiled={fused_compiled}, executed={fused_executed}"
            )
        if not fused_enabled and (fused_compiled or fused_executed):
            raise RuntimeError(f"Fused region unexpectedly ran in {mode}: {status!r}")
        bytecode_values = {
            k: int(m.group(1)) if (m := re.search(rf"bytecode_regions_{k}=(\d+)", status)) else None
            for k in ("compiled", "compile_failed", "executed")
        }
        if any(v is None for v in bytecode_values.values()):
            raise RuntimeError(f"Missing bytecode diagnostics in {mode}: {status!r}")
        bytecode_diagnostics.update(bytecode_values)
        if bytecode_enabled and (
            bytecode_values["compiled"] < 1
            or bytecode_values["compile_failed"] != 0
            or bytecode_values["executed"] < 1
        ):
            raise RuntimeError(
                f"Bytecode region did not compile and execute in {mode}: {status!r}"
            )
        if not bytecode_enabled and any(bytecode_values.values()):
            raise RuntimeError(f"Bytecode region unexpectedly ran in {mode}: {status!r}")
    return {
        "feedback": feedback, "score_response": score_response, "score": 12,
        "mutated_set_feedback": mutated_set_feedback, "mutated_set_response": mutated_set_response, "mutated_set_score": 107,
        "mutated_add_feedback": mutated_add_feedback, "mutated_add_response": mutated_add_response, "mutated_add_score": 164,
        "reset_feedback": reset_feedback, "reset_response": reset_response, "reset_score": 7,
        "full_reset_feedback": full_reset_feedback, "full_reset_response": full_reset_response, "full_reset_score": 7,
        "fused_feedback": fused_feedback, "fused_score_response": fused_score_response, "fused_score": 6,
        "fused_mutated_feedback": fused_mutated_feedback, "fused_mutated_response": fused_mutated_response, "fused_mutated_score": 206,
        "fused_reset_feedback": fused_reset_feedback, "fused_reset_response": fused_reset_response, "fused_reset_score": 6,
        "self_feedback": self_feedback, "self_score_response": self_score_response, "self_score": 3,
        "fused_self_feedback": fused_self_feedback, "fused_self_score_response": fused_self_score_response, "fused_self_score": 9,
        "mutate_seq_feedback": mutate_seq_fb, "mutate_seq_response": mutate_seq_resp, "mutate_seq_score": 13,
        "mutate_self_feedback": mutate_self_fb, "mutate_self_response": mutate_self_resp, "mutate_self_score": 115,
        "reset_seq_feedback": reset_seq_fb, "reset_seq_response": reset_seq_resp, "reset_seq_score": 7,
        "reset_self_feedback": reset_self_fb, "reset_self_response": reset_self_resp, "reset_self_score": 15,
        "macro_seq_feedback": macro_seq_fb, "macro_seq_response": macro_seq_resp, "macro_seq_score": 120,
        "macro_self_feedback": macro_self_fb, "macro_self_response": macro_self_resp, "macro_self_score": 67,
        "macro_cf_feedback": macro_cf_fb, "macro_cf_response": macro_cf_resp, "macro_cf_score": 80,
        "macro_reset_feedback": macro_reset_fb, "macro_reset_response": macro_reset_resp, "macro_reset_score": 22,
        "macro_reset_self_feedback": macro_reset_self_fb, "macro_reset_self_response": macro_reset_self_resp, "macro_reset_self_score": 33,
        "op_seq_feedback": op_seq_fb, "op_seq_response": op_seq_resp, "op_seq_score": 24,
        "op_self_feedback": op_self_fb, "op_self_response": op_self_resp, "op_self_score": 12,
        "op_macro_feedback": op_macro_fb, "op_macro_response": op_macro_resp, "op_macro_score": 30,
        "cond_feedback": cond_fb, "cond_response": cond_resp, "cond_score": 41,
        "store_feedback": store_fb, "store_response": store_resp, "store_score": 180,
        "cond_self_feedback": cond_self_fb, "cond_self_response": cond_self_resp, "cond_self_score": 40,
        "store_self_feedback": store_self_fb, "store_self_response": store_self_resp, "store_self_score": 40,
        "fold_feedback": fold_fb, "fold_response": fold_resp, "fold_score": 50,
        "chain_feedback": chain_fb, "chain_response": chain_resp, "chain_score": 175,
        "store_mod_feedback": store_mod_fb, "store_mod_response": store_mod_resp, "store_mod_score": 175,
        "macro_store_feedback": macro_store_fb, "macro_store_response": macro_store_resp, "macro_store_score": 65,
        "pred_e_feedback": pred_e_fb, "pred_e_response": pred_e_resp, "pred_e_score": 125,
        "pred_b_feedback": pred_b_fb, "pred_b_response": pred_b_resp, "pred_b_score": 70,
        "mbw1_feedback": mbw1_fb, "mbw1_response": mbw1_resp, "mbw1_score": 150,
        "mbw2_feedback": mbw2_fb, "mbw2_response": mbw2_resp, "mbw2_score": 20,
        "tjit_feedback": tjit_fb, "tjit_response": tjit_resp, "tjit_score": 60,
        "tjit5_feedback": tjit5_fb, "tjit5_response": tjit5_resp, "tjit5_score": 300,
        "diagnostics": diagnostics, "fused_diagnostics": fused_diagnostics, "bytecode_diagnostics": bytecode_diagnostics,
    }


def run_control_flow_failure_case(
    client: RconClient, mode: str, server_root: Path
) -> dict[str, object]:
    function_id = "function_compiler_probe:quota_execute_unless_exception"
    expected_scores = {0: 0, 1: 0, 2: 1, 3: 1, 4: 1, 5: 3, 6: 13, **{q: 14 for q in range(7, 17)}}
    scores_by_quota: dict[str, int] = {}
    responses_by_quota: dict[str, str] = {}
    for quota, expected_score in expected_scores.items():
        gamerule_response = command(
            client, f"gamerule minecraft:max_command_sequence_length {quota}"
        )
        if str(quota) not in gamerule_response:
            raise RuntimeError(
                f"Could not set {mode} callback sequence limit to {quota}: "
                f"{gamerule_response!r}"
            )
        command(client, "scoreboard players set #fcprobe fc_probe 0")
        command(client, "scoreboard players reset #syntax_missing fc_probe")
        response = command(client, f"function {function_id}")
        score_response = command(client, "scoreboard players get #fcprobe fc_probe")
        match = re.search(r"has (-?\d+)", score_response)
        if match is None:
            raise RuntimeError(
                f"Could not read {mode} callback score at sequence limit {quota}: "
                f"{score_response!r}"
            )
        score = int(match.group(1))
        if score != expected_score:
            raise RuntimeError(
                f"{mode} nested execute-unless syntax-error case at sequence "
                f"limit {quota} ended at {score}; expected {expected_score}"
            )
        scores_by_quota[str(quota)] = score
        responses_by_quota[str(quota)] = response

    command(client, "gamerule minecraft:max_command_sequence_length 65536")
    command(client, "gamerule minecraft:max_command_forks 65536")
    command(client, "scoreboard players reset #syntax_missing fc_probe")
    debug = run_debug_trace_fixture(
        client,
        mode,
        server_root,
        function_id,
        expected_score=14,
        expected_command_events=5,
    )
    debug.pop("response", None)
    store_expected_scores = {
        str(q): {"score": 0 if q < 5 else (2 if q < 9 else 4), "stored_result": -1, "stored_success": -1}
        for q in range(17)
    }
    store_scores: dict[str, dict[str, int]] = {}
    store_responses: dict[str, str] = {}
    for quota in range(17):
        gamerule_response = command(
            client, f"gamerule minecraft:max_command_sequence_length {quota}"
        )
        if str(quota) not in gamerule_response:
            raise RuntimeError(
                f"Could not set {mode} store-callback sequence limit to {quota}: "
                f"{gamerule_response!r}"
            )
        command(client, "scoreboard players set #fcprobe fc_probe 0")
        command(client, "scoreboard players set #nested_store_result fc_probe -1")
        command(client, "scoreboard players set #nested_store_success fc_probe -1")
        command(client, "scoreboard players reset #syntax_missing fc_probe")
        response = command(
            client,
            "function function_compiler_probe:quota_execute_store_exception",
        )
        score_response = command(client, "scoreboard players get #fcprobe fc_probe")
        result_response = command(
            client, "scoreboard players get #nested_store_result fc_probe"
        )
        success_response = command(
            client, "scoreboard players get #nested_store_success fc_probe"
        )
        values = []
        for label, observation in (
            ("score", score_response),
            ("stored result", result_response),
            ("stored success", success_response),
        ):
            match = re.search(r"has (-?\d+)", observation)
            if match is None:
                raise RuntimeError(
                    f"Could not read {mode} {label} at sequence limit {quota}: "
                    f"{observation!r}"
                )
            values.append(int(match.group(1)))
        store_scores[str(quota)] = {
            "score": values[0], "stored_result": values[1], "stored_success": values[2],
        }
        store_responses[str(quota)] = response
    if store_scores != store_expected_scores:
        raise RuntimeError(
            f"{mode} nested execute-store callback outcomes were {store_scores!r}; "
            f"expected {store_expected_scores!r}"
        )

    command(client, "gamerule minecraft:max_command_sequence_length 65536")
    command(client, "scoreboard players set #fcprobe fc_probe 0")
    command(client, "scoreboard players set #nested_store_result fc_probe -1")
    command(client, "scoreboard players set #nested_store_success fc_probe -1")
    command(client, "scoreboard players reset #syntax_missing fc_probe")
    store_debug = run_debug_trace_fixture(
        client,
        mode,
        server_root,
        "function_compiler_probe:quota_execute_store_exception",
        expected_score=4,
        expected_command_events=6,
    )
    store_debug["stored_result"] = int(
        re.search(
            r"has (-?\d+)",
            command(client, "scoreboard players get #nested_store_result fc_probe"),
        ).group(1)
    )
    store_debug["stored_success"] = int(
        re.search(
            r"has (-?\d+)",
            command(client, "scoreboard players get #nested_store_success fc_probe"),
        ).group(1)
    )
    store_debug.pop("response", None)
    if store_debug["stored_result"] != -1 or store_debug["stored_success"] != -1:
        raise RuntimeError(
            f"{mode} nested execute-store error callback wrote a value: "
            f"{store_debug!r}"
        )
    return {
        "function": function_id,
        "scores_by_sequence_limit": scores_by_quota,
        "function_responses_by_sequence_limit": responses_by_quota,
        "debug_score": debug["score"],
        "debug_command_events": debug["command_events"],
        "debug_trace": debug["trace"],
        "execute_store_exception": {
            "function": "function_compiler_probe:quota_execute_store_exception",
            "scores_by_sequence_limit": store_scores,
            "function_responses_by_sequence_limit": store_responses,
            "debug_score": store_debug["score"],
            "debug_command_events": store_debug["command_events"],
            "stored_result": store_debug["stored_result"],
            "stored_success": store_debug["stored_success"],
            "debug_trace": store_debug["trace"],
        },
    }


def parse_status_values(status: str) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in re.findall(r"([a-z_]+)=(\d+)", status)
    }


def run_modded_command_case(
    client: RconClient, mode: str
) -> dict[str, object] | None:
    if mode == "vanilla":
        return None
    command(client, "scoreboard objectives add fc_modded dummy")
    command(client, "scoreboard players set #fcmodded_total fc_modded 0")
    command(client, "scoreboard players set #fcmodded_result fc_modded 99")
    before_status = command(client, "function_compiler_probe status")
    before = parse_status_values(before_status)
    feedback = command(
        client, "function function_compiler_modded_command:fallback"
    )
    total_response = command(
        client, "scoreboard players get #fcmodded_total fc_modded"
    )
    result_response = command(
        client, "scoreboard players get #fcmodded_result fc_modded"
    )
    after_status = command(client, "function_compiler_probe status")
    after = parse_status_values(after_status)
    calls = after.get("modded_leaf_calls", -1)
    total = re.search(r"has (-?\d+)", total_response)
    stored = re.search(r"has (-?\d+)", result_response)
    if total is None or int(total.group(1)) != 15:
        raise RuntimeError(
            f"Modded-command fixture lost surrounding ScoreAdds in {mode}: "
            f"{total_response!r}"
        )
    if stored is None or int(stored.group(1)) != 7:
        raise RuntimeError(
            f"Modded-command return value was not stored in {mode}: "
            f"{result_response!r}"
        )
    if calls != 1:
        raise RuntimeError(
            f"Modded command did not execute exactly once in {mode}: "
            f"{after_status!r}"
        )

    # ControlFlowAware modded command cases (CTRL-008)
    def run_cf_subcase(cmd: str, exp_tot: int, exp_res: int | None, res_holder: str = "#fcmodded_result"):
        command(client, "scoreboard players set #fcmodded_total fc_modded 0")
        if exp_res is not None:
            command(client, f"scoreboard players set {res_holder} fc_modded 99")
        command(client, cmd)
        t_resp = command(client, "scoreboard players get #fcmodded_total fc_modded")
        tm = re.search(r"has (-?\d+)", t_resp)
        tot = int(tm.group(1)) if tm else None
        if tot != exp_tot:
            raise RuntimeError(f"ControlFlowAware subcase failed in {mode}: {t_resp!r}")
        if exp_res is not None:
            r_resp = command(client, f"scoreboard players get {res_holder} fc_modded")
            rm = re.search(r"has (-?\d+)", r_resp)
            res = int(rm.group(1)) if rm else None
            if res != exp_res:
                raise RuntimeError(f"ControlFlowAware result failed in {mode}: {r_resp!r}")
            return tot, res
        return tot, None

    cf_step_total, cf_step_stored = run_cf_subcase("function function_compiler_modded_command:control_flow_step", 15, 7)
    cf_discard_total, _ = run_cf_subcase("function function_compiler_modded_command:control_flow_discard", 3, None)
    cf_return_total, cf_return_stored = run_cf_subcase(
        "execute store result score #fcmodded_result fc_modded run function function_compiler_modded_command:control_flow_return",
        3, 42,
    )
    cf_fail_total, cf_fail_stored = run_cf_subcase(
        "execute store success score #fcmodded_result fc_modded run function function_compiler_modded_command:control_flow_fail",
        3, 0,
    )

    final_status = command(client, "function_compiler_probe status")
    final_values = parse_status_values(final_status)
    cf_calls = final_values.get("modded_control_flow_calls", -1)
    if cf_calls != 4:
        raise RuntimeError(
            f"ControlFlowAware commands did not execute exactly four times in {mode}: "
            f"{final_status!r}"
        )

    score_add_enabled = mode_score_add_enabled(mode)
    fused_enabled = mode_fused_enabled(mode)
    bytecode_enabled = mode_bytecode_enabled(mode)
    score_add_delta = final_values.get("score_add_executed", 0) - before.get(
        "score_add_executed", 0
    )
    fused_delta = final_values.get("fused_regions_executed", 0) - before.get(
        "fused_regions_executed", 0
    )
    bytecode_delta = final_values.get("bytecode_regions_executed", 0) - before.get(
        "bytecode_regions_executed", 0
    )
    if score_add_enabled and not fused_enabled and not bytecode_enabled and score_add_delta < 14:
        raise RuntimeError(
            f"ScoreAdd backend missed surrounding eligible commands in {mode}: "
            f"delta={score_add_delta}"
        )
    if fused_enabled and fused_delta < 7:
        raise RuntimeError(
            f"Fused backend missed regions around the modded commands in {mode}: "
            f"delta={fused_delta}"
        )
    if bytecode_enabled and bytecode_delta < 7:
        raise RuntimeError(
            f"Bytecode backend missed regions around the modded commands in {mode}: "
            f"delta={bytecode_delta}"
        )
    return {
        "feedback": feedback,
        "total_score": 15,
        "stored_result": 7,
        "modded_leaf_calls": calls,
        "control_flow_step_total": cf_step_total,
        "control_flow_step_result": cf_step_stored,
        "control_flow_discard_total": cf_discard_total,
        "control_flow_return_total": cf_return_total,
        "control_flow_return_result": cf_return_stored,
        "control_flow_fail_total": cf_fail_total,
        "control_flow_fail_success": cf_fail_stored,
        "modded_control_flow_calls": cf_calls,
        "diagnostics": {
            "score_add_executed_delta": score_add_delta,
            "fused_regions_executed_delta": fused_delta,
            "bytecode_regions_executed_delta": bytecode_delta,
        },
    }


def count_entities(client: RconClient, selector: str) -> int:
    command(client, "scoreboard players set #fc_compat_count fc_compat 0")
    command(
        client,
        f"execute as {selector} run scoreboard players add #fc_compat_count fc_compat 1",
    )
    response = command(client, "scoreboard players get #fc_compat_count fc_compat")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not parse entity count for {selector}: {response!r}")
    return int(match.group(1))


def run_mode(mode: str, server_jar: Path, run_id: str) -> dict[str, object]:
    work = ROOT / "run" / f"compatibility-probe-{run_id}-{mode}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    port = free_port()
    write_server_files(work, port, include_modded_command=mode != "vanilla")
    log_path = REPORT_DIR / f"{run_id}-{mode}.server.log"
    process, log_handle = start_server(mode, work, server_jar, log_path)
    client: RconClient | None = None
    try:
        client = wait_for_rcon(process, port)
        enabled = command(client, "datapack list enabled")
        if "function_compiler_probe" not in enabled:
            raise RuntimeError(f"Compatibility datapack did not load in {mode}: {enabled!r}")
        wrapper_status = None
        if mode != "vanilla":
            wrapper_status = command(client, "function_compiler_probe status")
            expected_wrapped = mode_wrapper_enabled(mode)
            if f"wrapped={str(expected_wrapped).lower()}" not in wrapper_status:
                raise RuntimeError(f"Unexpected Function Compiler wrapper state in {mode}: {wrapper_status!r}")
        selector = run_selector_cases(client)
        nbt = run_nbt_cases(client)
        modded_command = run_modded_command_case(client, mode)
        score_add = run_score_add_case(client, mode)
        callback_failure = run_control_flow_failure_case(client, mode, work)
        result = {
            "mode": mode,
            "wrapper_status": wrapper_status,
            "selector": selector,
            "entity_nbt": nbt,
            "score_add": score_add,
            "callback_failure": callback_failure,
            "log": str(log_path.relative_to(ROOT)),
        }
        if modded_command is not None:
            result["modded_command"] = modded_command
        command(client, "stop")
        process.wait(timeout=60)
        return result
    finally:
        if client is not None:
            client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_handle.close()
        shutil.rmtree(work, ignore_errors=True)


def normalized_outcome(result: dict[str, object]) -> dict[str, object]:
    value = copy.deepcopy({
        key: item
        for key, item in result.items()
        if key not in {"mode", "wrapper_status", "log"}
    })
    passenger = value.get("entity_nbt", {}).get("passenger_filtered_write", {})
    if isinstance(passenger, dict):
        passenger.pop("before", None)
        passenger.pop("after", None)
    score_add = value.get("score_add", {})
    if isinstance(score_add, dict):
        score_add.pop("diagnostics", None)
        score_add.pop("fused_diagnostics", None)
        score_add.pop("bytecode_diagnostics", None)
    value.pop("modded_command", None)
    text = json.dumps(value, sort_keys=True)
    text = re.sub(r"UUID: \[I; [^\]]+\]", "UUID: <entity-uuid>", text)
    return json.loads(text)


def without_home_position(outcome: dict[str, object]) -> dict[str, object]:
    copied = json.loads(json.dumps(outcome))
    entity_nbt = copied.get("entity_nbt", {})
    if isinstance(entity_nbt, dict):
        entity_nbt.pop("home_position_filtered_update", None)
    return copied


def compare_outcomes(results: list[dict[str, object]]) -> dict[str, object]:
    by_mode = {str(result["mode"]): normalized_outcome(result) for result in results}
    modded_by_mode = {
        str(result["mode"]): result["modded_command"]
        for result in results
        if isinstance(result.get("modded_command"), dict)
    }
    pair_results: dict[str, bool | None] = {}
    for label, first, second in (
        ("vanilla_vs_fabric_off", "vanilla", "fabric-off"),
        ("fabric_wrapper_off_vs_on", "fabric-off", "fabric-on"),
        ("fabric_off_vs_score_add_on", "fabric-off", "score-add-on"),
        ("fabric_off_vs_fused_interpreted", "fabric-off", "fused-interpreted"),
        ("fabric_off_vs_bytecode_emitted", "fabric-off", "bytecode-emitted"),
        ("bellows_wrapper_off_vs_on", "bellows-off", "bellows-on"),
        ("bellows_off_vs_score_add_on", "bellows-off", "bellows-score-add-on"),
        ("bellows_off_vs_fused_interpreted", "bellows-off", "bellows-fused-interpreted"),
        ("bellows_off_vs_bytecode_emitted", "bellows-off", "bellows-bytecode-emitted"),
        ("bellows_moonrise120_off_vs_on", "bellows-moonrise120-off", "bellows-moonrise120-on"),
        ("bellows_moonrise120_off_vs_score_add", "bellows-moonrise120-off", "bellows-moonrise120-score-add-on"),
        ("bellows_moonrise120_off_vs_fused", "bellows-moonrise120-off", "bellows-moonrise120-fused-interpreted"),
        ("bellows_moonrise120_off_vs_bytecode", "bellows-moonrise120-off", "bellows-moonrise120-bytecode-emitted"),
        ("lbm113120_off_vs_on", "lbm113120-off", "lbm113120-on"),
        ("lbm113120_off_vs_score_add", "lbm113120-off", "lbm113120-score-add-on"),
        ("lbm113120_off_vs_fused", "lbm113120-off", "lbm113120-fused-interpreted"),
        ("lbm113120_off_vs_bytecode", "lbm113120-off", "lbm113120-bytecode-emitted"),
    ):
        pair_results[label] = (
            by_mode[first] == by_mode[second]
            if first in by_mode and second in by_mode
            else None
        )
    modded_baseline = modded_by_mode.get("fabric-off")
    modded_semantic_parity: dict[str, bool | None] = {}
    if isinstance(modded_baseline, dict):
        semantic_keys = (
            "feedback",
            "total_score",
            "stored_result",
            "modded_leaf_calls",
            "control_flow_step_total",
            "control_flow_step_result",
            "control_flow_discard_total",
            "control_flow_return_total",
            "control_flow_return_result",
            "control_flow_fail_total",
            "control_flow_fail_success",
            "modded_control_flow_calls",
        )
        for mode, result in modded_by_mode.items():
            if mode == "fabric-off":
                continue
            same = all(
                result.get(key) == modded_baseline.get(key)
                for key in semantic_keys
            )
            modded_semantic_parity[mode] = same
            pair_results[f"modded_leaf_fabric_off_vs_{mode}"] = same
            pair_results[f"modded_control_flow_fabric_off_vs_{mode}"] = same

    vanilla_bellows_equivalent: dict[str, bool | None] = {}
    bellows_modes = (
        "bellows-off", "bellows-on", "bellows-score-add-on", "bellows-fused-interpreted",
        "bellows-bytecode-emitted", "bellows-moonrise120-off", "bellows-moonrise120-on",
        "bellows-moonrise120-score-add-on", "bellows-moonrise120-fused-interpreted",
        "bellows-moonrise120-bytecode-emitted",
        "lbm113120-off", "lbm113120-on", "lbm113120-score-add-on",
        "lbm113120-fused-interpreted", "lbm113120-bytecode-emitted",
    )
    for mode in bellows_modes:
        vanilla_bellows_equivalent[mode] = (
            without_home_position(by_mode["vanilla"])
            == without_home_position(by_mode[mode])
            if "vanilla" in by_mode and mode in by_mode
            else None
        )
    home_path: dict[str, object] = {}
    if "vanilla" in by_mode:
        home_path["vanilla"] = by_mode["vanilla"].get("entity_nbt", {}).get(
            "home_position_filtered_update"
        )
    for mode in bellows_modes:
        if mode in by_mode:
            home_path[mode] = by_mode[mode].get("entity_nbt", {}).get(
                "home_position_filtered_update"
            )
    required_pairs = [value for value in pair_results.values() if value is not None]
    required_stack_comparisons = [
        value for value in vanilla_bellows_equivalent.values() if value is not None
    ]
    home_position_parity = {
        mode: home_path.get(mode) == home_path.get("vanilla")
        for mode in bellows_modes
        if mode in home_path and "vanilla" in home_path
    }
    vanilla_home_results = home_path.get("vanilla", {})
    vanilla_home_expectations = {
        case: isinstance(vanilla_home_results, dict)
        and vanilla_home_results.get(case) == expected
        for case, expected in EXPECTED_HOME_POSITION_RESULTS.items()
    } if "vanilla" in by_mode else {}
    vanilla_home_radius = by_mode.get("vanilla", {}).get("entity_nbt", {}).get(
        "home_radius_filtered_update", {}
    )
    vanilla_home_radius_expectations = {
        case: isinstance(vanilla_home_radius, dict)
        and isinstance(vanilla_home_radius.get(case), dict)
        and all(
            vanilla_home_radius[case].get(field) == value
            for field, value in expected.items()
        )
        for case, expected in EXPECTED_HOME_RADIUS_RESULTS.items()
    } if "vanilla" in by_mode else {}
    home_radius_modes = (
        "fabric-off",
        "fabric-on",
        "score-add-on",
        "fused-interpreted",
        "bytecode-emitted",
        "bellows-off",
        "bellows-on",
        "bellows-score-add-on",
        "bellows-fused-interpreted",
        "bellows-bytecode-emitted",
        "bellows-moonrise120-off",
        "bellows-moonrise120-on",
        "bellows-moonrise120-score-add-on",
        "bellows-moonrise120-fused-interpreted",
        "bellows-moonrise120-bytecode-emitted",
        "lbm113120-off",
        "lbm113120-on",
        "lbm113120-score-add-on",
        "lbm113120-fused-interpreted",
        "lbm113120-bytecode-emitted",
    )
    home_radius_parity = {
        mode: (
            by_mode.get(mode, {})
            .get("entity_nbt", {})
            .get("home_radius_filtered_update")
            == vanilla_home_radius
        )
        for mode in home_radius_modes
        if mode in by_mode and "vanilla" in by_mode
    }
    gates_pass = (
        all(required_pairs)
        and all(required_stack_comparisons)
        and all(vanilla_home_expectations.values())
        and all(vanilla_home_radius_expectations.values())
        and all(home_position_parity.values())
        and all(home_radius_parity.values())
    )
    return {
        "compatibility_parity_pass": gates_pass,
        "pairwise_parity": pair_results,
        "modded_command_parity_vs_fabric_off": modded_semantic_parity,
        "vanilla_vs_bellows_equal_outside_known_home_pos_case": vanilla_bellows_equivalent,
        "vanilla_vs_bellows_home_pos_parity": home_position_parity,
        "vanilla_home_pos_expected_results": vanilla_home_expectations,
        "home_position_filtered_update": home_path,
        "vanilla_home_radius_expected_results": vanilla_home_radius_expectations,
        "home_radius_filtered_update": {
            "vanilla": vanilla_home_radius,
            **{
                mode: by_mode[mode].get("entity_nbt", {}).get(
                    "home_radius_filtered_update"
                )
                for mode in home_radius_parity
            },
        },
        "vanilla_vs_bellows_home_radius_parity": {
            mode: home_radius_parity.get(mode) for mode in bellows_modes
        },
        "home_position_diverges_between_vanilla_and_bellows": (
            home_path.get("vanilla") != home_path.get("bellows-off")
            if "vanilla" in home_path and "bellows-off" in home_path
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    args = parser.parse_args()
    selected_mod_keys = sorted(
        {key for mode in args.modes for key in mode_mod_keys(mode)}
    )
    mod_artifacts: dict[str, dict[str, str]] = {}
    for mod_key in selected_mod_keys:
        mod_name, expected_hash = MODS[mod_key]
        mod_path = MODS_DIR / mod_name
        if not mod_path.is_file() or sha256(mod_path) != expected_hash:
            raise FileNotFoundError(
                f"Missing or mismatched pinned {mod_key} jar: {mod_path}"
            )
        mod_artifacts[mod_key] = {"file": mod_name, "sha256": expected_hash}
    moonrise_modes = [
        mode for mode in args.modes if "moonrise120" in mode_mod_keys(mode)
    ]
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_SHA256:
        raise RuntimeError(f"Minecraft server artifact hash mismatch: {server_jar}")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    results = [run_mode(mode, server_jar, run_id) for mode in args.modes]
    comparison = compare_outcomes(results)
    report = {
        "benchmark": "COMPATIBILITY-PROBE",
        "minecraft": "26.3",
        "server_jar_sha256": sha256(server_jar),
        "mod_artifacts": mod_artifacts,
        "wrapper_modes": [
            "fabric-off",
            "fabric-on",
            "score-add-on",
            "fused-interpreted",
            "bytecode-emitted",
        ],
        "bellows_modes": [
            "bellows-off", "bellows-on", "bellows-score-add-on",
            "bellows-fused-interpreted", "bellows-bytecode-emitted",
            "bellows-moonrise120-off", "bellows-moonrise120-on",
            "bellows-moonrise120-score-add-on", "bellows-moonrise120-fused-interpreted",
            "bellows-moonrise120-bytecode-emitted",
            "lbm113120-off", "lbm113120-on", "lbm113120-score-add-on",
            "lbm113120-fused-interpreted", "lbm113120-bytecode-emitted",
        ],
        "modes": results,
        "comparison": comparison,
        "notes": [
            "Wrapper-only modes delegate to vanilla; ScoreAdd modes specialize literal fake-holder additions, and fused/bytecode modes also group only consecutive eligible additions.",
            "ScoreAdd state/feedback and selector/entity-NBT observations match compiler-off on the same Fabric and Bellows stacks.",
            "The Fabric-only modded leaf runs once, stores result 7, and leaves the surrounding ScoreAdd regions executable in compiler-on profiles.",
            "The Bellows home_pos adapter restores the exact vanilla init/merge/modify/remove values in wrapper-off, wrapper-on, and ScoreAdd arms.",
            "The home_radius modify/remove cases match their explicit vanilla values across all selected arms.",
            "The passenger NBT case exercises a nested entity-data path that Bellows does not implement in its filtered entity loader.",
        ],
    }
    if moonrise_modes:
        moonrise120_name, moonrise120_hash = MODS["moonrise120"]
        report["moonrise"] = {
            "file": moonrise120_name,
            "sha256": moonrise120_hash,
            "selected_modes": moonrise_modes,
        }
    path = REPORT_DIR / f"{run_id}.results.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not comparison["compatibility_parity_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Compatibility probe failed: {error}", file=sys.stderr)
        raise
