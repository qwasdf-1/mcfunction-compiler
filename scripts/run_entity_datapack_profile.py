#!/usr/bin/env python3
"""Probe a pinned per-entity datapack loop on a disposable Minecraft 26.3 server."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "runtime"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "mc-harness"))

from player_bot import PacketIds, PlayerBot  # noqa: E402
from run_dynamic_lights_profile import (  # noqa: E402
    MODS,
    MODS_DIR,
    OUTPUT_ROOT,
    SERVER_HOST,
    SPARK_AGENT,
    SPARK_SHA256,
    STACK_MODS,
    create_workdir,
    count_entities,
    reserve_free_ports,
    sha256,
    spark_thread_node_count,
    stop_idle_spark_shell,
)
from run_spawn_animations_profile import (  # noqa: E402
    start_spark_shell,
    stop_spark_shell,
    wait_for_spark_password,
)
from mc_harness import assert_version  # noqa: E402
from mc_harness.server_lifecycle import (  # noqa: E402
    DrainingRconClient,
    locate_official_server_jar,
    wait_for_rcon as mc_wait_for_rcon,
)

#: The harness version this profile was verified against (roadmap step 6 pin).
HARNESS_PIN = "1.0.0"

assert_version(HARNESS_PIN)
from analyze_spark_profile import summarize as summarize_spark_profile  # noqa: E402


SERVER_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
PACKS = {
    "everything-clings": (
        ROOT / "references/real-world/candidates/everything-clings-1.0.0.zip",
        "dcb9f5398f4840375f5ade0fe47f596071644a7a447dd0d9a6e99737d71e5c75",
        "Everything Clings 1.0.0",
        "everything_clings.calc",
    ),
}
PLAYER_COUNT = 4
PROFILE_SECONDS = 18
DEFAULT_ENTITIES = 128


def wait_for_profile_rcon(
    process: subprocess.Popen[bytes], port: int, password: str, timeout: float = 120
) -> DrainingRconClient:
    """Wait for a profile server's RCON (shared harness implementation)."""
    return mc_wait_for_rcon(
        process,
        host=SERVER_HOST,
        port=port,
        password=password,
        client_cls=DrainingRconClient,
        timeout_seconds=int(timeout),
        poll_seconds=0.5,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", choices=tuple(PACKS), default="everything-clings")
    parser.add_argument("--stack", choices=("vanilla", *STACK_MODS), default="vanilla")
    parser.add_argument("--wrapper", choices=("off", "on"), default="off")
    parser.add_argument("--datapack", choices=("on", "off"), default="on")
    parser.add_argument("--entities", type=int, default=DEFAULT_ENTITIES)
    parser.add_argument("--mode", choices=("cpu", "alloc", "idle"), default="cpu")
    parser.add_argument("--seconds", type=int, default=PROFILE_SECONDS)
    args = parser.parse_args()
    if args.stack == "vanilla" and args.wrapper != "off":
        parser.error("--wrapper on is only available for Fabric stacks")
    if args.datapack == "off" and args.wrapper == "on":
        parser.error("--wrapper on requires the datapack workload arm")
    if args.entities < 1 or args.entities > 512:
        parser.error("--entities must be between 1 and 512")
    if args.seconds < 1:
        parser.error("--seconds must be positive")
    return args


def score_value(rcon: RconClient, holder: str, objective: str) -> int:
    response = rcon.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", response)
    if not match:
        raise RuntimeError(f"Could not parse scoreboard result: {response!r}")
    return int(match.group(1))


def count_candidate_entities(rcon: RconClient, tracking_objective: str) -> int:
    return count_entities(
        rcon, "#fc_entities", tracking_objective, "@e[type=minecraft:pig,tag=fc_candidate]"
    )


def candidate_entity_sample(rcon: RconClient) -> str:
    return rcon.command(
        "data get entity @e[type=minecraft:pig,tag=fc_candidate,sort=nearest,limit=1] Pos"
    )


def count_clings_eligible_entities(rcon: RconClient, tracking_objective: str) -> int:
    rcon.command(f"scoreboard players set #fc_eligible {tracking_objective} 0")
    rcon.command(
        "execute as @e[type=minecraft:pig,tag=fc_candidate] at @s "
        "if entity @a[distance=2..40,gamemode=!spectator] "
        f"run scoreboard players add #fc_eligible {tracking_objective} 1"
    )
    return score_value(rcon, "#fc_eligible", tracking_objective)


def write_setup_pack(path: Path, player_names: list[str], count: int) -> None:
    functions = path / "data/function_compiler_benchmark/function"
    functions.mkdir(parents=True)
    (path / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "Function Compiler disposable profile setup",
                    "min_format": [121, 0],
                    "max_format": [121, 0],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commands = []
    for index in range(count):
        player = player_names[index % len(player_names)]
        local = index // len(player_names)
        dx = 3 + (local % 8) * 3
        dz = 3 + ((local // 8) % 8) * 3
        commands.append(
            f'execute at {player} run summon minecraft:pig ~{dx} ~ ~{dz} '
            '{NoAI:1b,NoGravity:1b,PersistenceRequired:1b,Tags:["fc_candidate"]}'
        )
    (functions / "setup.mcfunction").write_text("\n".join(commands) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    pack_path, pack_hash, pack_title, objective = PACKS[args.pack]
    for path, expected, label in (
        (pack_path, pack_hash, pack_title),
        (SPARK_AGENT, SPARK_SHA256, "Spark standalone agent"),
    ):
        if not path.is_file() or sha256(path) != expected:
            raise FileNotFoundError(f"Missing or mismatched pinned {label}: {path}")
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server jar hash mismatch: {server_jar}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    out = OUTPUT_ROOT / f"{args.pack}-{args.stack}-pack-{args.datapack}-{args.mode}-{run_id}"
    out.mkdir(parents=True, exist_ok=False)
    server_port, rcon_port, spark_port = reserve_free_ports(3)
    password = secrets.token_urlsafe(24)
    player_names = [f"FCEntity{i:02d}" for i in range(1, PLAYER_COUNT + 1)]
    bots: list[PlayerBot] = []
    rcon: DrainingRconClient | None = None
    ssh: subprocess.Popen[bytes] | None = None
    server: subprocess.Popen[bytes] | None = None
    log_handle = None
    work: Path | None = None

    try:
        with create_workdir(args.stack, run_id) as run_dir:
            work = run_dir
            packet_report_dir = work / "packet-report"
            report = subprocess.run(
                [
                    "java",
                    "-DbundlerMainClass=net.minecraft.data.Main",
                    "-jar",
                    str(server_jar),
                    "--reports",
                    "--output",
                    str(packet_report_dir),
                ],
                cwd=work,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=120,
                check=False,
            )
            if report.returncode != 0:
                raise RuntimeError(f"Minecraft packet report failed: {report.stdout[-1600:]}")
            packet_ids = PacketIds.load(packet_report_dir / "reports/packets.json")

            datapacks = work / "world/datapacks"
            datapacks.mkdir(parents=True)
            if args.datapack == "on":
                shutil.copy2(pack_path, datapacks / f"{args.pack}.zip")
            probe_pack = datapacks / "function_compiler_probe"
            shutil.copytree(ROOT / "src/main/resources/data", probe_pack / "data")
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
            write_setup_pack(datapacks / "function_compiler_benchmark", player_names, args.entities)
            if args.stack != "vanilla":
                mods_dir = work / "mods"
                mods_dir.mkdir()
                for mod_key in STACK_MODS[args.stack]:
                    filename, _ = MODS[mod_key]
                    shutil.copy2(MODS_DIR / filename, mods_dir / filename)
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
                cwd = work
                server_env = None
            else:
                server_env = os.environ.copy()
                project_cache = ROOT / ".gradle-user-home"
                if "GRADLE_USER_HOME" not in server_env and project_cache.is_dir():
                    server_env["GRADLE_USER_HOME"] = str(project_cache)
                shared_cache = Path.home() / ".gradle/caches"
                if "GRADLE_RO_DEP_CACHE" not in server_env and shared_cache.is_dir():
                    server_env["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
                server_env.update(
                    {
                        "FC_WRAPPER_PROBE": "true" if args.wrapper == "on" else "false",
                        "FC_RUNTIME_TRACE": "false",
                    }
                )
                gradle_args = [
                    "--no-daemon",
                    f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
                    f"-PfcSparkAgentPath={SPARK_AGENT}",
                    f"-PfcSparkPort={spark_port}",
                    "runServer",
                ]
                if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
                    gradle_args.insert(0, "--offline")
                server_command = [str(ROOT / "gradlew"), *gradle_args]
                cwd = ROOT
            server = subprocess.Popen(
                server_command, cwd=cwd, stdout=log_handle, stderr=subprocess.STDOUT, env=server_env
            )
            rcon = wait_for_profile_rcon(server, rcon_port, password)
            enabled = rcon.command("datapack list enabled")
            if args.datapack == "on":
                if objective not in rcon.command("scoreboard objectives list"):
                    raise RuntimeError(f"{pack_title} did not initialize objective {objective!r}")
            tracking_objective = "fc_profile"
            created = rcon.command(f"scoreboard objectives add {tracking_objective} dummy")
            if "created" not in created.casefold() and tracking_objective not in created:
                raise RuntimeError(f"Could not create tracking objective: {created!r}")
            compiler_status = None
            if args.stack != "vanilla":
                compiler_status = rcon.command("function_compiler_probe status")
                if "FC_PROBE present=true" not in compiler_status:
                    raise RuntimeError(f"Function Compiler probe did not load: {compiler_status!r}")
                if f"wrapped={str(args.wrapper == 'on').lower()}" not in compiler_status:
                    raise RuntimeError(f"Unexpected wrapper mode: {compiler_status!r}")
                for invariant in ("tag_same_instance=true", "delegates_original=true"):
                    if invariant not in compiler_status:
                        raise RuntimeError(f"Wrapper invariant failed ({invariant}): {compiler_status!r}")

            rcon.command("gamerule sendCommandFeedback false")
            rcon.command("gamerule doDaylightCycle false")
            rcon.command("gamerule doMobSpawning false")
            rcon.command("gamerule maxEntityCramming 10000")
            rcon.command("difficulty peaceful")
            rcon.command("time set midnight")
            rcon.command("forceload add -16 -16 224 48")
            rcon.command("fill -16 63 -16 224 63 48 minecraft:stone")
            rcon.command("kill @e[type=!minecraft:player]")
            for index, player in enumerate(player_names):
                bots.append(PlayerBot(player, SERVER_HOST, server_port, packet_ids).connect())
                rcon.command(f"gamemode creative {player}")
                teleport = rcon.command(f"tp {player} {index * 64} 65 0 0 0")
                if "teleported" not in teleport.casefold():
                    raise RuntimeError(f"Could not place {player}: {teleport!r}")
            rcon.command("function function_compiler_benchmark:setup")
            created_entities = count_candidate_entities(rcon, tracking_objective)
            if created_entities != args.entities:
                raise RuntimeError(f"Expected {args.entities} entities; found {created_entities}")

            eligible_before = count_clings_eligible_entities(rcon, tracking_objective)
            count_before = count_candidate_entities(rcon, tracking_objective)
            entity_sample_before = candidate_entity_sample(rcon)

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
            spark_output = stop_idle_spark_shell(ssh) if args.mode == "idle" else stop_spark_shell(ssh)
            ssh = None

            profile_path: Path | None = None
            if args.mode != "idle":
                files = list(work.rglob("*.sparkprofile"))
                if not files:
                    raise RuntimeError(f"Spark wrote no profile; shell output: {spark_output[-1200:]}")
                profile_path = out / f"{args.pack}-{args.mode}.sparkprofile"
                shutil.copy2(max(files, key=lambda p: p.stat().st_mtime), profile_path)
                nodes = spark_thread_node_count(profile_path)
                if nodes == 0:
                    raise RuntimeError("Spark saved metadata but no thread sample nodes")
            else:
                nodes = 0

            count_after = count_candidate_entities(rcon, tracking_objective)
            eligible_after = count_clings_eligible_entities(rcon, tracking_objective)
            entity_sample_after = candidate_entity_sample(rcon)
            tick_query = rcon.command("tick query")
            online = rcon.command("list")
            for bot in bots:
                bot.assert_connected()
            result = {
                "benchmark": "PERF-010",
                "pack_id": args.pack,
                "datapack": pack_title,
                "datapack_enabled": args.datapack == "on",
                "datapack_sha256": sha256(pack_path),
                "workload": "per-entity pull and proximity selectors",
                "stack": args.stack,
                "wrapper_mode": args.wrapper if args.stack != "vanilla" else None,
                "wrapper_probe_status": compiler_status,
                "minecraft": "26.3 official server" if args.stack == "vanilla" else "26.3 Fabric Loom development server",
                "server_sha256": sha256(server_jar),
                "spark": "1.10.194 standalone-agent",
                "spark_sha256": SPARK_SHA256,
                "mods": {
                    key: {"file": MODS[key][0], "sha256": MODS[key][1]}
                    for key in STACK_MODS.get(args.stack, ())
                },
                "scenario": f"four headless creative players, {args.entities} persistent NoAI pigs tagged fc_candidate, fixed seed 264010, forced test chunks, daylight and natural spawns disabled",
                "players": player_names,
                "entity_count_before_profile": count_before,
                "entity_count_after_profile": count_after,
                "entity_count_retained": count_after == count_before,
                "valid_for_comparison": count_after == count_before,
                "entity_sample_before_profile": entity_sample_before,
                "entity_sample_after_profile": entity_sample_after,
                "clings_eligible_count_before_profile": eligible_before,
                "clings_eligible_count_after_profile": eligible_after,
                "profile_mode": args.mode,
                "profile_seconds": args.seconds,
                "spark_thread_nodes": nodes,
                "profile_path": str(profile_path.relative_to(ROOT)) if profile_path else None,
                "profile_sha256": sha256(profile_path) if profile_path else None,
                "profile_bytes": profile_path.stat().st_size if profile_path else 0,
                "server_thread_profile_summary": (
                    summarize_spark_profile(profile_path, "Server thread", 25)["matched_threads"][0]
                    if profile_path
                    else None
                ),
                "tick_query": tick_query,
                "connected_players": online,
                "purpose": "workload/profile pilot only; no Function Compiler optimization is enabled",
                "limitations": [
                    "One capture is a path-validation pilot, not a performance conclusion.",
                    "The Function Compiler wrapper delegates to vanilla and is not an optimization arm.",
                    "Entity commands and datapack effects require same-stack compiler-off/on parity before an optimization comparison.",
                ],
            }
            (out / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2))
            if profile_path:
                print(f"Spark profile: {profile_path}")
            rcon.command("stop")
            server.wait(timeout=90)
            rcon.close()
            rcon = None
    except Exception as error:
        diagnostics: list[str] = []
        if work is not None:
            for log_path in (work / "logs/latest.log", work / "server.log"):
                if not log_path.is_file():
                    continue
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                diagnostics.extend(
                    line
                    for line in lines
                    if any(word in line.casefold() for word in ("error", "exception", "failed", "fail", "warn"))
                )
        failure = {
            "benchmark": "PERF-010",
            "pack_id": args.pack,
            "stack": args.stack,
            "datapack": args.datapack,
            "workload": "per-entity pull and proximity selectors",
            "run_id": run_id,
            "failure": str(error),
            "diagnostics": "\n".join(diagnostics[-40:]),
        }
        (out / "failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        if ssh is not None and ssh.poll() is None:
            try:
                if ssh.stdin is not None:
                    ssh.stdin.write(b"exit\n")
                    ssh.stdin.flush()
                ssh.wait(timeout=5)
            except Exception:  # noqa: BLE001 - disposable Spark shell cleanup
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
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
