#!/usr/bin/env python3
"""Profile the pinned 26.3 Dynamic Lights datapack on a disposable server."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import secrets
import statistics
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "runtime"))
sys.path.insert(0, str(ROOT / "scripts"))

from player_bot import PacketIds, PlayerBot  # noqa: E402
from mod_artifacts import MODS, MODS_DIR, STACK_MODS  # noqa: E402
from run_runtime_probe import RconClient, locate_official_server_jar  # noqa: E402
from run_spawn_animations_profile import (  # noqa: E402
    count_entities,
    count_score,
    start_spark_shell,
    wait_for_rcon,
    wait_for_spark_password,
    stop_spark_shell,
)


PACK = ROOT / "references" / "real-world" / "dynamic-lights-creepermeyt" / "DynamicLightsByCreepermeYT_v1.4.6.zip"
PACK_SHA256 = "afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20"
SPARK_AGENT = ROOT / "references" / "real-world" / "spark-1.10.194" / "spark-1.10.194-standalone-agent.jar"
SPARK_SHA256 = "a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9"
SERVER_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
OUTPUT_ROOT = ROOT / "build" / "benchmarks" / "PERF-010"
SERVER_HOST = "127.0.0.1"
PROFILE_SECONDS = 18
PLAYER_COUNT = 4
ITEM_COUNT = 24


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def spark_thread_node_count(path: Path) -> int:
    """Count top-level SamplerData thread nodes without external protobuf packages."""
    data = path.read_bytes()
    offset = 0
    count = 0

    def read_varint(position: int) -> tuple[int, int]:
        value = 0
        shift = 0
        while position < len(data) and shift < 70:
            byte = data[position]
            position += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value, position
            shift += 7
        raise ValueError("Malformed Spark profile protobuf varint")

    while offset < len(data):
        key, offset = read_varint(offset)
        field_number, wire_type = key >> 3, key & 0x07
        if field_number == 2 and wire_type == 2:
            count += 1
        if wire_type == 0:
            _, offset = read_varint(offset)
        elif wire_type == 1:
            offset += 8
        elif wire_type == 2:
            length, offset = read_varint(offset)
            offset += length
        elif wire_type == 5:
            offset += 4
        else:
            raise ValueError(f"Unsupported Spark profile protobuf wire type: {wire_type}")
        if offset > len(data):
            raise ValueError("Truncated Spark profile protobuf field")
    return count


def reserve_free_ports(count: int) -> tuple[int, ...]:
    """Choose distinct ports while keeping their sockets reserved together."""
    sockets = []
    ports: list[int] = []
    try:
        while len(ports) < count:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.bind((SERVER_HOST, 0))
            port = int(probe.getsockname()[1])
            if port in ports:
                probe.close()
                continue
            sockets.append(probe)
            ports.append(port)
        return tuple(ports)
    finally:
        for probe in sockets:
            probe.close()


def count_entities_with_tag_predicate(
    rcon: RconClient, holder: str, objective: str, base_selector: str, tag: str
) -> int:
    rcon.command(f"scoreboard players set {holder} {objective} 0")
    rcon.command(
        f"execute as {base_selector} if entity @s[tag={tag}] "
        f"run scoreboard players add {holder} {objective} 1"
    )
    return count_score(rcon, holder, objective)


def entity_position(rcon: RconClient, index: int) -> tuple[float, float, float]:
    selector = f"@e[type=minecraft:item,tag=fc_dl_{index},limit=1]"
    response = rcon.command(f"data get entity {selector} Pos")
    match = re.search(
        r"\[\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)[d]?\s*,"
        r"\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)[d]?\s*,"
        r"\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)[d]?\s*\]",
        response,
    )
    if match is None:
        raise RuntimeError(f"Could not parse position for Dynamic Lights item {index}: {response!r}")
    return tuple(float(value) for value in match.groups())


def item_motion(index: int) -> tuple[float, float]:
    local_index = index // PLAYER_COUNT
    dx_slot = local_index % 3
    z_slot = local_index // 3
    return (0.35 if dx_slot < 2 else -0.35, 0.12 if z_slot == 0 else -0.12)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=("vanilla", *STACK_MODS), default="vanilla")
    parser.add_argument(
        "--mode",
        choices=("cpu", "alloc", "idle"),
        default="cpu",
        help="CPU profile, allocation profile, or Spark attached with sampling idle.",
    )
    parser.add_argument("--wrapper", choices=("off", "on"), default="off")
    parser.add_argument(
        "--datapack",
        choices=("on", "off"),
        default="on",
        help="Run with the pinned Dynamic Lights pack or as a matched datapack-off control.",
    )
    parser.add_argument("--seconds", type=int, default=PROFILE_SECONDS)
    parser.add_argument(
        "--scenario", choices=("stationary", "moving"), default="stationary",
        help="Stationary source control or matched moving dropped-torch workload.",
    )
    parser.add_argument(
        "--exec-census", action="store_true",
        help="Run the explicit Function Compiler execution census with Spark sampling disabled.",
    )
    return parser.parse_args()


@contextmanager
def create_workdir(stack: str, run_id: str):
    work = ROOT / "run" / run_id
    work.mkdir(parents=True, exist_ok=False)
    yield work


def stop_idle_spark_shell(process: subprocess.Popen[bytes], timeout: float = 20) -> str:
    assert process.stdin is not None
    process.stdin.write(b"exit\n")
    process.stdin.flush()
    output = process.communicate(timeout=timeout)[0].decode("utf-8", errors="replace")
    if process.returncode != 0:
        raise RuntimeError(f"Spark SSH exited with code {process.returncode}: {output[-1200:]}")
    return output


def main() -> int:
    args = parse_args()
    if args.seconds < 1:
        raise ValueError("--seconds must be positive")
    if args.stack == "vanilla" and args.wrapper != "off":
        raise ValueError("--wrapper on is available only for Fabric server stacks")
    if args.datapack == "off" and args.wrapper == "on":
        raise ValueError("--wrapper on is not part of the datapack on/off workload control")
    if args.exec_census:
        if args.stack == "vanilla" or args.wrapper != "on" or args.datapack != "on" or args.mode != "idle":
            raise ValueError("--exec-census requires --stack fabric --wrapper on --datapack on --mode idle")
        if os.environ.get("FC_COMPILER_EXEC_CENSUS", "").casefold() not in {"1", "true", "yes"}:
            raise ValueError("--exec-census requires FC_COMPILER_EXEC_CENSUS=true")
        if not os.environ.get("FC_COMPILER_EXEC_CENSUS_FUNCTIONS") or not os.environ.get("FC_COMPILER_EXEC_CENSUS_CALLEES"):
            raise ValueError("--exec-census requires explicit function and callee allowlists")
    artifacts = [(PACK, PACK_SHA256, "Dynamic Lights datapack")]
    if not args.exec_census:
        artifacts.append((SPARK_AGENT, SPARK_SHA256, "Spark standalone agent"))
    artifacts.extend(
        (MODS_DIR / MODS[key][0], MODS[key][1], f"{key} mod")
        for key in STACK_MODS.get(args.stack, ())
    )
    for path, expected, label in artifacts:
        if not path.is_file() or sha256(path) != expected:
            raise FileNotFoundError(f"Missing or mismatched pinned {label}: {path}")

    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server jar hash mismatch: {server_jar}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    census_suffix = "-exec-census" if args.exec_census else ""
    output_dir = OUTPUT_ROOT / f"dynamic-lights-{args.stack}-pack-{args.datapack}-{args.wrapper}-{args.mode}-{args.scenario}{census_suffix}-{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)
    server_port, rcon_port, spark_port = reserve_free_ports(3)
    password = secrets.token_urlsafe(24)
    player_names = [f"DLight{i:02d}" for i in range(1, PLAYER_COUNT + 1)]
    bots: list[PlayerBot] = []
    rcon: RconClient | None = None
    ssh: subprocess.Popen[bytes] | None = None
    server: subprocess.Popen[bytes] | None = None
    log_handle = None
    work_directory: Path | None = None
    exec_census_started = False
    exec_census_start_status = None
    exec_census_stop_status = None

    try:
        with create_workdir(args.stack, run_id) as work:
            work_directory = work
            report_root = work / "packet-report"
            report = subprocess.run(
                [
                    "java",
                    "-DbundlerMainClass=net.minecraft.data.Main",
                    "-jar",
                    str(server_jar),
                    "--reports",
                    "--output",
                    str(report_root),
                ],
                cwd=work,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=120,
                check=False,
            )
            if report.returncode != 0:
                raise RuntimeError(f"Minecraft packet report generation failed: {report.stdout[-1600:]}")
            packet_ids = PacketIds.load(report_root / "reports" / "packets.json")

            datapacks = work / "world" / "datapacks"
            datapacks.mkdir(parents=True)
            if args.datapack == "on":
                shutil.copy2(PACK, datapacks / "dynamic-lights.zip")
            probe_pack = datapacks / "function_compiler_probe"
            shutil.copytree(ROOT / "src" / "main" / "resources" / "data", probe_pack / "data")
            (probe_pack / "pack.mcmeta").write_text(
                json.dumps(
                    {
                        "pack": {
                            "description": "Function Compiler 26.3 benchmark wrapper probe",
                            "min_format": [97, 1],
                            "max_format": [97, 1],
                        }
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if args.stack != "vanilla":
                mods_directory = work / "mods"
                mods_directory.mkdir()
                for mod_key in STACK_MODS[args.stack]:
                    filename, _ = MODS[mod_key]
                    shutil.copy2(MODS_DIR / filename, mods_directory / filename)
            (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            properties = {
                "enable-rcon": "true",
                "rcon.password": password,
                "rcon.port": str(rcon_port),
                "broadcast-rcon-to-ops": "false",
                "server-ip": SERVER_HOST,
                "server-port": str(server_port),
                "level-name": "world",
                "level-seed": "264010",
                "online-mode": "false",
                "white-list": "false",
                "spawn-protection": "0",
                "max-players": "6",
                "view-distance": "4",
                "simulation-distance": "4",
                "sync-chunk-writes": "false",
                "pause-when-empty-seconds": "-1",
            }
            (work / "server.properties").write_text(
                "".join(f"{key}={value}\n" for key, value in properties.items()), encoding="utf-8"
            )
            log_path = work / "server.log"
            log_handle = log_path.open("wb")
            if args.stack == "vanilla":
                server_command = [
                    "java",
                    "-Xms1G",
                    "-Xmx3G",
                    f"-javaagent:{SPARK_AGENT}=port={spark_port}",
                    "-jar",
                    str(server_jar),
                    "nogui",
                ]
                server_cwd = work
                server_environment = None
            else:
                server_environment = os.environ.copy()
                project_cache = ROOT / ".gradle-user-home"
                if "GRADLE_USER_HOME" not in server_environment and project_cache.is_dir():
                    server_environment["GRADLE_USER_HOME"] = str(project_cache)
                shared_cache = Path.home() / ".gradle" / "caches"
                if "GRADLE_RO_DEP_CACHE" not in server_environment and shared_cache.is_dir():
                    server_environment["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
                server_environment.update(
                    {
                        "FC_WRAPPER_PROBE": "true" if args.wrapper == "on" else "false",
                        "FC_RUNTIME_TRACE": "false",
                    }
                )
                gradle_arguments = [
                    "--no-daemon",
                    f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
                ]
                if not args.exec_census:
                    gradle_arguments.extend([
                        f"-PfcSparkAgentPath={SPARK_AGENT}",
                        f"-PfcSparkPort={spark_port}",
                    ])
                gradle_arguments.append("runServer")
                if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
                    gradle_arguments.insert(0, "--offline")
                server_command = [str(ROOT / "gradlew"), *gradle_arguments]
                server_cwd = ROOT
            server = subprocess.Popen(
                server_command,
                cwd=server_cwd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=server_environment,
            )
            rcon = wait_for_rcon(server, rcon_port, password)

            enabled = rcon.command("datapack list enabled")
            if args.datapack == "on":
                if "dynamic-lights" not in enabled.casefold():
                    raise RuntimeError(f"Dynamic Lights did not enable: {enabled!r}")
                objectives = rcon.command("scoreboard objectives list")
                if "dynbclevel" not in objectives:
                    raise RuntimeError(f"Dynamic Lights load function did not create its objective: {objectives!r}")
                version = rcon.command("scoreboard players get v dynbclevel")
                if "-1170" not in version:
                    raise RuntimeError(f"Dynamic Lights did not pass its 26.3 version check: {version!r}")
                tracking_objective = "dynbclevel"
            else:
                if "dynamic-lights" in enabled.casefold():
                    raise RuntimeError(f"Dynamic Lights unexpectedly enabled in control run: {enabled!r}")
                objective_result = rcon.command("scoreboard objectives add fc_bench dummy")
                if "created" not in objective_result.casefold():
                    raise RuntimeError(f"Could not create the control objective: {objective_result!r}")
                tracking_objective = "fc_bench"
            compiler_probe_status = None
            if args.stack != "vanilla":
                compiler_probe_status = rcon.command("function_compiler_probe status")
                if "FC_PROBE present=true" not in compiler_probe_status:
                    raise RuntimeError(f"Function Compiler probe fixture did not load: {compiler_probe_status!r}")
                expected_wrapped = args.wrapper == "on"
                if f"wrapped={str(expected_wrapped).lower()}" not in compiler_probe_status:
                    raise RuntimeError(
                        "Function Compiler wrapper mode did not match the requested profile: "
                        f"{compiler_probe_status!r}"
                    )
                for invariant in ("tag_same_instance=true", "delegates_original=true"):
                    if invariant not in compiler_probe_status:
                        raise RuntimeError(f"Wrapper probe invariant failed ({invariant}): {compiler_probe_status!r}")
            if args.datapack == "on":
                rcon.command("scoreboard players set p dynbclevel 2")
            rcon.command("gamerule doDaylightCycle false")
            rcon.command("gamerule doMobSpawning false")
            rcon.command("time set midnight")
            forced_chunks = rcon.command("forceload add -16 -16 256 32")
            if not any(word in forced_chunks.casefold() for word in ("added", "marked")):
                raise RuntimeError(f"Could not load the fixed profile area: {forced_chunks!r}")
            floor = rcon.command("fill -16 63 -16 256 63 32 minecraft:stone")
            if not any(word in floor.casefold() for word in ("changed", "successfully filled")):
                raise RuntimeError(f"Could not create the fixed test platform: {floor!r}")

            for index, name in enumerate(player_names):
                bots.append(PlayerBot(name, SERVER_HOST, server_port, packet_ids).connect())
                rcon.command(f"gamemode creative {name}")
                teleport = rcon.command(f"tp {name} {index * 64} 65 0 0 0")
                if "teleported" not in teleport.casefold():
                    raise RuntimeError(f"Could not place {name} at its fixed profile position: {teleport!r}")
                response = rcon.command(f"item replace entity {name} weapon.mainhand with minecraft:stone")
                if "replaced" not in response.casefold():
                    raise RuntimeError(f"Could not equip inert item on {name}: {response!r}")

            for index in range(ITEM_COUNT):
                player = player_names[index % len(player_names)]
                local_index = index // len(player_names)
                dx, dz = 2 + (local_index % 3) * 20, 2 + (local_index // 3) * 20
                response = rcon.command(
                    f'execute at {player} run summon minecraft:item ~{dx} ~1 ~{dz} '
                    f'{{NoGravity:1b,Motion:[0.0d,0.0d,0.0d],PickupDelay:32767,'
                    f'Item:{{id:"minecraft:torch",count:1}},Tags:["fc_dl","fc_dl_{index}"]}}'
                )
                if "summoned" not in response.casefold():
                    raise RuntimeError(f"Could not create Dynamic Lights item actor: {response!r}")

            tagged_items = count_entities(rcon, "#fc_items", tracking_objective, "@e[type=item,tag=fc_dl]")
            if tagged_items != ITEM_COUNT:
                raise RuntimeError(f"Expected {ITEM_COUNT} tagged torch items; found {tagged_items}")

            tracked_items = 0
            marker_count = 0
            stable_actor_reads = 0
            previous_tracked_items: int | None = None
            workload_ready_at = time.monotonic() + 90
            workload_started_at = time.monotonic()
            while time.monotonic() < workload_ready_at:
                tracked_selector = (
                    "@e[type=item,tag=fc_dl,tag=dynbc.haslvl]"
                    if args.datapack == "on"
                    else "@e[type=item,tag=fc_dl]"
                )
                tracked_items = count_entities(rcon, "#fc_tracked", tracking_objective, tracked_selector)
                marker_count = count_entities(
                    rcon, "#fc_markers", tracking_objective, "@e[type=marker,tag=dynbc]"
                )
                if tracked_items == ITEM_COUNT and tracked_items == previous_tracked_items:
                    stable_actor_reads += 1
                else:
                    stable_actor_reads = 0
                if tracked_items == ITEM_COUNT and stable_actor_reads >= 10:
                    break
                previous_tracked_items = tracked_items
                time.sleep(1)
            workload_warmup_seconds = round(time.monotonic() - workload_started_at, 2)
            if tracked_items != ITEM_COUNT or stable_actor_reads < 10:
                raise RuntimeError(
                    "Dynamic Lights item tracking did not stabilize: "
                    f"tracked items={tracked_items}, markers={marker_count}, stable actor reads={stable_actor_reads}"
                )
            torch_sources = count_entities(
                rcon, "#fc_torches", tracking_objective, "@e[type=item,tag=fc_dl,tag=dynbc.torch]"
            )
            torch_sources_by_predicate = count_entities_with_tag_predicate(
                rcon,
                "#fc_torches_indirect",
                tracking_objective,
                "@e[type=item,tag=fc_dl]",
                "dynbc.torch",
            )

            if args.scenario == "moving":
                for index in range(ITEM_COUNT):
                    vx, vz = item_motion(index)
                    selector = f"@e[type=minecraft:item,tag=fc_dl_{index},limit=1]"
                    response = rcon.command(
                        f"data modify entity {selector} Motion set value [{vx:.2f}d,0.0d,{vz:.2f}d]"
                    )
                    if "modified" not in response.casefold():
                        raise RuntimeError(
                            f"Could not set moving source velocity for item {index}: {response!r}")
            item_positions_before = {
                index: entity_position(rcon, index) for index in range(ITEM_COUNT)
            }
            if args.exec_census:
                exec_census_start_status = rcon.command("function_compiler_probe exec-census-start")
                if "FC_EXEC started" not in exec_census_start_status:
                    raise RuntimeError(
                        f"Function execution census did not start: {exec_census_start_status!r}")
                exec_census_started = True
                time.sleep(args.seconds)
                exec_census_stop_status = rcon.command("function_compiler_probe exec-census-stop")
                if "FC_EXEC ended" not in exec_census_stop_status:
                    raise RuntimeError(
                        f"Function execution census did not stop: {exec_census_stop_status!r}")
                exec_census_started = False
                spark_output = ""
            else:
                spark_password = wait_for_spark_password(log_path, server)
                ssh = start_spark_shell(work, spark_password, spark_port)
                if args.mode == "cpu":
                    command = "spark profiler start --interval 4 --thread *\n"
                elif args.mode == "alloc":
                    command = "spark profiler start --alloc --interval 524287\n"
                else:
                    command = None
                if command is not None:
                    assert ssh.stdin is not None
                    profile_deadline = time.monotonic() + args.seconds
                    ssh.stdin.write(command.encode("utf-8"))
                    ssh.stdin.flush()
                    time.sleep(min(1, args.seconds))
                    remaining = profile_deadline - time.monotonic()
                    if remaining > 0:
                        time.sleep(remaining)
                else:
                    time.sleep(args.seconds)

                if args.mode == "idle":
                    spark_output = stop_idle_spark_shell(ssh)
                    ssh = None
                else:
                    spark_output = stop_spark_shell(ssh)
                    ssh = None
            profile_path: Path | None = None
            if args.mode != "idle":
                profile_files = list(work.rglob("*.sparkprofile"))
                if not profile_files:
                    log_tail = ""
                    latest_log = work / "logs" / "latest.log"
                    if latest_log.is_file():
                        log_lines = latest_log.read_text(encoding="utf-8", errors="replace").splitlines()
                        interesting = [
                            line for line in log_lines
                            if any(token in line.casefold() for token in ("spark", "profiler", "error", "exception"))
                        ]
                        log_tail = "\n".join((interesting or log_lines)[-30:])
                    raise RuntimeError(
                        "Spark did not write a local .sparkprofile; "
                        f"Spark SSH output={spark_output[-1600:]!r}; relevant server log lines:\n{log_tail}"
                    )
                profile_path = output_dir / f"dynamic-lights-{args.mode}.sparkprofile"
                shutil.copy2(max(profile_files, key=lambda item: item.stat().st_mtime), profile_path)
                spark_thread_nodes = spark_thread_node_count(profile_path)
                if spark_thread_nodes == 0:
                    raise RuntimeError(
                        "Spark saved metadata but no thread sample nodes; "
                        "the profile is not usable for call-tree analysis"
                    )
            else:
                spark_thread_nodes = 0

            item_positions_after = {
                index: entity_position(rcon, index) for index in range(ITEM_COUNT)
            }
            item_displacements = {
                index: math.dist(item_positions_before[index], item_positions_after[index])
                for index in range(ITEM_COUNT)
            }
            item_motion_summary = {
                "scenario": args.scenario,
                "moved_item_count": sum(distance >= 1.0 for distance in item_displacements.values()),
                "minimum_displacement_blocks": min(item_displacements.values()),
                "mean_displacement_blocks": statistics.mean(item_displacements.values()),
                "maximum_displacement_blocks": max(item_displacements.values()),
            }
            if args.scenario == "moving" and item_motion_summary["moved_item_count"] != ITEM_COUNT:
                raise RuntimeError(f"Moving source fixture did not move every item: {item_motion_summary!r}")
            if args.scenario == "stationary" and item_motion_summary["maximum_displacement_blocks"] > 0.05:
                raise RuntimeError(f"Stationary source control unexpectedly moved: {item_motion_summary!r}")

            if args.exec_census:
                log_handle.flush()
                census_lines = []
                for candidate_log in (log_path, work / "logs" / "latest.log"):
                    if candidate_log.is_file():
                        census_lines.extend(
                            line for line in candidate_log.read_text(
                                encoding="utf-8", errors="replace"
                            ).splitlines() if "FC_EXEC_" in line
                        )
                census_lines = list(dict.fromkeys(census_lines))
                if not any("FC_EXEC_BEGIN" in line for line in census_lines) or not any(
                    "FC_EXEC_END" in line for line in census_lines
                ):
                    raise RuntimeError("Function execution census log boundaries are missing")
                (output_dir / "exec-census.log").write_text(
                    "\n".join(census_lines) + "\n", encoding="utf-8")

            tracked_selector = (
                "@e[type=item,tag=fc_dl,tag=dynbc.haslvl]"
                if args.datapack == "on"
                else "@e[type=item,tag=fc_dl]"
            )
            tracked_after = count_entities(rcon, "#fc_tracked", tracking_objective, tracked_selector)
            torch_sources_after = count_entities(
                rcon, "#fc_torches", tracking_objective, "@e[type=item,tag=fc_dl,tag=dynbc.torch]"
            )
            torch_sources_after_by_predicate = count_entities_with_tag_predicate(
                rcon,
                "#fc_torches_indirect",
                tracking_objective,
                "@e[type=item,tag=fc_dl]",
                "dynbc.torch",
            )
            markers_after = count_entities(
                rcon, "#fc_markers", tracking_objective, "@e[type=marker,tag=dynbc]"
            )
            dynamic_lights_tick_state = (
                {
                    holder: rcon.command(f"scoreboard players get {holder} dynbclevel")
                    for holder in ("k", "-", "p")
                }
                if args.datapack == "on"
                else None
            )
            first_source_score = (
                rcon.command("scoreboard players get @e[type=item,tag=fc_dl,limit=1] dynbclevel")
                if args.datapack == "on"
                else None
            )
            tick_query = rcon.command("tick query")
            players_online = rcon.command("list")
            for bot in bots:
                bot.assert_connected()

            metadata = {
                "benchmark": "PERF-010",
                "workload": "Dynamic Lights By CreepermeYT 1.4.6 datapack",
                "purpose": f"{args.stack} 26.3 {args.mode} profile, Dynamic Lights datapack {args.datapack}, scenario={args.scenario}; not an optimization comparison",
                "mode": args.mode,
                "stack": args.stack,
                "dynamic_lights_datapack_enabled": args.datapack == "on",
                "function_compiler_wrapper": args.wrapper if args.stack != "vanilla" else None,
                "function_compiler_mod_loaded": args.stack != "vanilla",
                "function_compiler_probe_status": compiler_probe_status,
                "minecraft": "26.3 official server" if args.stack == "vanilla" else "26.3 Fabric Loom development server",
                "server_jar_sha256": sha256(server_jar),
                "spark": None if args.exec_census else "1.10.194 standalone-agent",
                "spark_sha256": None if args.exec_census else SPARK_SHA256,
                "mods": {
                    mod_key: {"file": MODS[mod_key][0], "sha256": MODS[mod_key][1]}
                    for mod_key in STACK_MODS.get(args.stack, ())
                },
                "datapack": "Dynamic Lights By CreepermeYT v1.4.6-mc1.17.x-26.3 datapack zip",
                "datapack_sha256": sha256(PACK),
                "scenario": (
                    "four connected creative players holding non-light-emitting stone at fixed positions 64 blocks apart; "
                    f"24 tagged {args.scenario} dropped torches in fixed non-overlapping light-source positions; "
                    "fixed seed 264010; daylight cycle and natural mob spawning disabled; Smart preset"
                ),
                "item_motion": item_motion_summary,
                "compiler_exec_census_enabled": args.exec_census,
                "exec_census_start_status": exec_census_start_status,
                "exec_census_stop_status": exec_census_stop_status,
                "exec_census_log": str((output_dir / "exec-census.log").relative_to(ROOT))
                    if args.exec_census else None,
                "players": player_names,
                "preset_score": 2,
                "control_tracking_objective": tracking_objective,
                "tracked_items_before_profile": tracked_items,
                "tracked_items_after_profile": tracked_after,
                "tagged_torch_sources_before_profile": torch_sources,
                "tagged_torch_sources_after_profile": torch_sources_after,
                "tagged_torch_sources_by_predicate_before_profile": torch_sources_by_predicate,
                "tagged_torch_sources_by_predicate_after_profile": torch_sources_after_by_predicate,
                "workload_warmup_seconds": workload_warmup_seconds,
                "dynamic_light_markers_before_profile": marker_count,
                "dynamic_light_markers_after_profile": markers_after,
                "dynamic_light_marker_delta": markers_after - marker_count,
                "dynamic_lights_tick_state_after_profile": dynamic_lights_tick_state,
                "first_source_light_level_score": first_source_score,
                "profile_seconds": args.seconds,
                "spark_sampling": None if args.exec_census else {
                    "cpu_interval_ms": 4,
                    "cpu_thread_scope": "all threads",
                    "allocation_interval_bytes": 524287,
                    "profile_seconds": args.seconds,
                },
                "profile_path": str(profile_path.relative_to(ROOT)) if profile_path else None,
                "profile_sha256": sha256(profile_path) if profile_path else None,
                "profile_bytes": profile_path.stat().st_size if profile_path else 0,
                "spark_thread_nodes": spark_thread_nodes,
                "server_tick_query": tick_query,
                "connected_players": players_online,
                "spark_shell_output": spark_output,
                "limitations": [
                    "One run per scenario; repeat distribution is not established.",
                    (
                        "Function Compiler execution census is diagnostic counts only; "
                        "no optimization or CPU timing is active."
                        if args.exec_census else
                        "No Function Compiler optimization or exact per-function timer is active."
                    ),
                ],
            }
            (output_dir / "results.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({key: value for key, value in metadata.items() if key != "spark_shell_output"}, indent=2))
            if profile_path:
                print(f"Spark profile: {profile_path}")
            rcon.command("stop")
            server.wait(timeout=90)
            rcon.close()
            rcon = None
    except Exception as error:
        if exec_census_started and rcon is not None:
            try:
                rcon.command("function_compiler_probe exec-census-stop")
            except Exception:
                pass
            exec_census_started = False
        diagnostics: list[str] = []
        if log_handle is not None:
            log_handle.flush()
        if work_directory is not None:
            for log_path in (work_directory / "logs" / "latest.log", work_directory / "server.log"):
                if not log_path.is_file():
                    continue
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                diagnostics.extend(
                    line for line in lines
                    if not any(secret in line.casefold() for secret in ("password", "askpass"))
                    and any(token in line.casefold() for token in ("spark", "error", "exception", "failed", "fail", "warn"))
                )
        excerpt = "\n".join(diagnostics[-35:])
        failure = {
            "benchmark": "PERF-010",
            "stack": args.stack,
            "wrapper": args.wrapper,
            "mode": args.mode,
            "run_id": run_id,
            "failure": str(error),
            "server_diagnostics": excerpt,
        }
        (output_dir / "failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(f"{error}\nFiltered server diagnostics:\n{excerpt}") from error
    finally:
        if ssh is not None and ssh.poll() is None:
            try:
                if ssh.stdin is not None:
                    ssh.stdin.write(b"exit\n")
                    ssh.stdin.flush()
                ssh.wait(timeout=5)
            except Exception:  # noqa: BLE001 - best-effort close for the disposable agent shell
                ssh.kill()
                ssh.wait()
        for bot in bots:
            bot.close()
        if rcon is not None:
            try:
                rcon.command("stop")
            except Exception:  # noqa: BLE001 - server may already have stopped
                pass
            rcon.close()
        if server is not None and server.poll() is None:
            try:
                server.wait(timeout=35)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait(timeout=10)
        if log_handle is not None:
            log_handle.close()
        if work_directory is not None:
            shutil.rmtree(work_directory, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PERF-010 Dynamic Lights profile failed: {error}", file=sys.stderr)
        raise
