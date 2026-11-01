#!/usr/bin/env python3
"""Capture a local Spark profile of the pinned Spawn Animations 26.3 scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "runtime"))
sys.path.insert(0, str(ROOT / "scripts"))

from player_bot import PacketIds, PlayerBot, Writer  # noqa: E402
from run_runtime_probe import RconClient, locate_official_server_jar  # noqa: E402
from analyze_spark_profile import summarize as summarize_spark_profile  # noqa: E402


SPAWN_PACK_SHA256 = "7f467a0870d2445511f652b1d246b2adac54a4051ff49a1746a2992fab86dbe6"
SPARK_AGENT_SHA256 = "a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9"
SPARK_AGENT = ROOT / "references" / "real-world" / "spark-1.10.194" / "spark-1.10.194-standalone-agent.jar"
SPAWN_PACK = ROOT / "references" / "real-world" / "spawn-animations" / "spawnanimations-v1.11.6-mc1.17-26.3.9-datapack.zip"
OUTPUT_ROOT = ROOT / "build" / "benchmarks" / "PERF-010"
SERVER_JAR_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
SERVER_HOST = "127.0.0.1"
PROFILE_SECONDS = 6
TARGET_ACTORS = 24


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((SERVER_HOST, 0))
        return int(probe.getsockname()[1])


def wait_for_rcon(process: subprocess.Popen[bytes], port: int, password: str, timeout: float = 120) -> RconClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft server exited early with code {process.returncode}")
        try:
            return RconClient(SERVER_HOST, port, password)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(0.5)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def wait_for_spark_password(log_path: Path, process: subprocess.Popen[bytes], timeout: float = 35) -> str:
    ansi = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = ansi.sub("", log_path.read_text(encoding="utf-8", errors="replace"))
        match = re.search(r"(?im)\bpassword\s*[:=]\s*(\S+)", text)
        if match:
            return match.group(1).strip()
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft server exited before Spark initialized: {process.returncode}")
        time.sleep(0.25)
    raise TimeoutError("Spark did not print its local SSH password")


def count_score(client: RconClient, player: str, objective: str) -> int:
    response = client.command(f"scoreboard players get {player} {objective}")
    match = re.search(r"has (-?\d+)", response)
    if not match:
        raise RuntimeError(f"Could not parse scoreboard result: {response!r}")
    return int(match.group(1))


def count_entities(client: RconClient, holder: str, objective: str, selector: str) -> int:
    client.command(f"scoreboard players set {holder} {objective} 0")
    client.command(f"execute as {selector} run scoreboard players add {holder} {objective} 1")
    return count_score(client, holder, objective)


def write_spawn_fixture_pack(path: Path, bot_names: list[str], actor_count: int) -> None:
    function_dir = path / "data/function_compiler_benchmark/function"
    function_dir.mkdir(parents=True)
    (path / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "Function Compiler disposable Spawn Animations fixture",
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
    bot_count = len(bot_names)
    for index in range(actor_count):
        bot = bot_names[index % bot_count]
        local = index // bot_count
        dx, dz = 3 + local * 2, (index % bot_count) * 2
        commands.append(
            f'execute at {bot} run summon minecraft:zombie ~{dx} ~ ~{dz} {{Tags:["fc_sa"]}}'
        )
    (function_dir / "spawn_actors.mcfunction").write_text("\n".join(commands) + "\n", encoding="utf-8")


def start_spark_shell(work: Path, password: str, port: int) -> subprocess.Popen[bytes]:
    askpass = work / "spark-askpass"
    askpass.write_text('#!/bin/sh\nprintf \'%s\\n\' "$SPARK_ASKPASS_PASSWORD"\n', encoding="utf-8")
    askpass.chmod(0o700)
    environment = os.environ.copy()
    environment.update(
        {
            "DISPLAY": ":0",
            "SSH_ASKPASS": str(askpass),
            "SSH_ASKPASS_REQUIRE": "force",
            "SPARK_ASKPASS_PASSWORD": password,
        }
    )
    process = subprocess.Popen(
        [
            "/usr/bin/ssh",
            "-tt",
            "-p",
            str(port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "PreferredAuthentications=password",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            "NumberOfPasswordPrompts=1",
            "spark@localhost",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
        cwd=work,
    )
    time.sleep(1.5)
    if process.poll() is not None:
        output = process.stdout.read().decode("utf-8", errors="replace") if process.stdout else ""
        raise RuntimeError(f"Spark SSH closed before the command shell started: {output[-1200:]}")
    return process


def stop_spark_shell(process: subprocess.Popen[bytes], timeout: float = 20) -> str:
    assert process.stdin is not None
    process.stdin.write(b"spark profiler stop --save-to-file\n")
    process.stdin.flush()
    time.sleep(2.5)
    process.stdin.write(b"spark tps\n")
    process.stdin.flush()
    time.sleep(1.5)
    process.stdin.write(b"exit\n")
    process.stdin.flush()
    output = process.communicate(timeout=timeout)[0].decode("utf-8", errors="replace")
    if process.returncode != 0:
        raise RuntimeError(f"Spark SSH exited with code {process.returncode}: {output[-1200:]}")
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=PROFILE_SECONDS)
    parser.add_argument("--actors", type=int, default=TARGET_ACTORS)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error("--seconds must be positive")
    if args.actors < 1 or args.actors > 256:
        parser.error("--actors must be between 1 and 256")
    if not SPAWN_PACK.is_file() or sha256(SPAWN_PACK) != SPAWN_PACK_SHA256:
        raise FileNotFoundError(
            "Place the pinned Spawn Animations 1.11.6 artifact at "
            f"{SPAWN_PACK.relative_to(ROOT)} (SHA-256 {SPAWN_PACK_SHA256})"
        )
    if not SPARK_AGENT.is_file() or sha256(SPARK_AGENT) != SPARK_AGENT_SHA256:
        raise FileNotFoundError(
            "Place the pinned Spark 1.10.194 standalone agent at "
            f"{SPARK_AGENT.relative_to(ROOT)} (SHA-256 {SPARK_AGENT_SHA256})"
        )
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_JAR_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server jar hash mismatch: {server_jar}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    output_dir = OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    server_port, rcon_port, spark_port = free_port(), free_port(), free_port()
    password = secrets.token_urlsafe(24)
    bot_names = [f"FCPlayer{i:02d}" for i in range(1, 5)]
    bots: list[PlayerBot] = []
    rcon: RconClient | None = None
    ssh: subprocess.Popen[bytes] | None = None
    server: subprocess.Popen[bytes] | None = None
    log_handle = None

    try:
        with tempfile.TemporaryDirectory(prefix="function-compiler-perf-010-") as temporary:
            work = Path(temporary)
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
            shutil.copy2(SPAWN_PACK, datapacks / "spawnanimations.zip")
            write_spawn_fixture_pack(datapacks / "function_compiler_benchmark", bot_names, args.actors)
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
            server = subprocess.Popen(
                [
                    "java",
                    "-Xms1G",
                    "-Xmx3G",
                    f"-javaagent:{SPARK_AGENT}=port={spark_port}",
                    "-jar",
                    str(server_jar),
                    "nogui",
                ],
                cwd=work,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
            rcon = wait_for_rcon(server, rcon_port, password)
            enabled = rcon.command("datapack list enabled")
            if "spawnanimations" not in enabled:
                raise RuntimeError(f"Spawn Animations did not enable: {enabled!r}")
            objectives = rcon.command("scoreboard objectives list")
            if "ts.sa.settings" not in objectives:
                raise RuntimeError(f"Spawn Animations load function did not create its objectives: {objectives!r}")

            for name in bot_names:
                bots.append(PlayerBot(name, SERVER_HOST, server_port, packet_ids).connect())
                rcon.command(f"gamemode creative {name}")
            rcon.command("gamerule doDaylightCycle false")
            rcon.command("gamerule doMobSpawning false")
            rcon.command("time set midnight")

            version = ""
            version_deadline = time.monotonic() + 30
            while time.monotonic() < version_deadline:
                version = rcon.command("scoreboard players get $version ts.sa.settings")
                match = re.search(r"has (-?\d+)", version)
                if match and int(match.group(1)) == 5023:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(f"Spawn Animations did not initialize for 26.3 after player join: {version!r}")

            # Use a fresh actor set and spawn it in one function call. Per-entity
            # RCON setup used to let early animations finish before profiling began.
            rcon.command("gamerule sendCommandFeedback false")
            rcon.command("kill @e[type=!minecraft:player]")
            rcon.command("function function_compiler_benchmark:spawn_actors")
            actor_count_before = count_entities(
                rcon, "#fc_actors", "ts.sa.count", "@e[type=minecraft:zombie,tag=fc_sa]"
            )
            if actor_count_before != args.actors:
                raise RuntimeError(f"Expected {args.actors} tagged zombies before profiling; found {actor_count_before}")

            active_at_start = 0
            activation_deadline = time.monotonic() + 10
            while time.monotonic() < activation_deadline:
                active_at_start = count_entities(
                    rcon,
                    "#fc_animating",
                    "ts.sa.count",
                    "@e[type=minecraft:zombie,tag=fc_sa,tag=ts.sa.verify]",
                )
                if active_at_start > 0:
                    break
                time.sleep(0.25)
            if active_at_start < 1:
                raise RuntimeError("No zombie entered the active animation state before profiling")

            spark_password = wait_for_spark_password(log_path, server)
            ssh = start_spark_shell(work, spark_password, spark_port)
            assert ssh.stdin is not None
            profile_deadline = time.monotonic() + args.seconds
            ssh.stdin.write(b"spark profiler start --interval 4 --thread *\n")
            ssh.stdin.flush()
            time.sleep(min(1, args.seconds))
            remaining = profile_deadline - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            spark_output = stop_spark_shell(ssh)
            ssh = None
            actor_count = count_entities(
                rcon, "#fc_actors", "ts.sa.count", "@e[type=minecraft:zombie,tag=fc_sa]"
            )
            if actor_count != args.actors:
                raise RuntimeError(f"Expected {args.actors} tagged zombies after capture; found {actor_count}")
            active_at_end = count_entities(
                rcon,
                "#fc_animating",
                "ts.sa.count",
                "@e[type=minecraft:zombie,tag=fc_sa,tag=ts.sa.verify]",
            )
            for bot in bots:
                bot.assert_connected()
            player_list = rcon.command("list")
            tick_query = rcon.command("tick query")
            profile_files = list(work.rglob("*.sparkprofile"))
            if not profile_files:
                raise RuntimeError("Spark did not write a local .sparkprofile")
            profile = max(profile_files, key=lambda item: item.stat().st_mtime)
            profile_path = output_dir / "vanilla-spawn-animations.sparkprofile"
            shutil.copy2(profile, profile_path)
            profile_summary = summarize_spark_profile(profile_path, "Server thread", 40)
            thread_summary = profile_summary["matched_threads"][0]
            if thread_summary["stack_node_count"] == 0:
                raise RuntimeError("Spark saved a Server thread with no sample nodes")

            metadata = {
                "benchmark": "PERF-010",
                "purpose": "single vanilla 26.3 real-world datapack profile; not an optimization comparison",
                "minecraft": "26.3 official server",
                "server_jar_sha256": sha256(server_jar),
                "spark": "1.10.194 standalone-agent",
                "spark_sha256": sha256(SPARK_AGENT),
                "datapack": "Tschipcraft Spawn Animations 1.11.6 (mc1.17-26.3.9 artifact)",
                "datapack_sha256": sha256(SPAWN_PACK),
                "scenario": f"four connected creative players; {args.actors} nearby zombies created before profiling; fixed seed 264010; daylight cycle and natural mob spawning disabled",
                "players": bot_names,
                "active_animation_count_at_sample_start": active_at_start,
                "active_animation_count_after_capture": active_at_end,
                "tagged_zombie_count_before_capture": actor_count_before,
                "tagged_zombie_count_after_capture": actor_count,
                "profiler": "Spark CPU sampler, all threads at 4 ms, local --save-to-file",
                "profile_seconds": args.seconds,
                "profile_path": str(profile_path.relative_to(ROOT)),
                "profile_sha256": sha256(profile_path),
                "profile_bytes": profile_path.stat().st_size,
                "spark_thread_nodes": profile_summary["thread_count_in_profile"],
                "server_thread_profile_summary": thread_summary,
                "server_tick_query": tick_query,
                "connected_players": player_list,
                "spark_shell_output": spark_output,
                "limitations": [
                    "One run only; no stable distribution.",
                    "No profiler-off control or allocation profile.",
                    "Vanilla arm only; no mod-stack comparison.",
                    "No compiler optimization or exact per-function timer is active.",
                ],
            }
            (output_dir / "results.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({key: value for key, value in metadata.items() if key != "spark_shell_output"}, indent=2))
            print(f"Spark profile: {profile_path}")
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
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PERF-010 Spawn Animations profile failed: {error}", file=sys.stderr)
        raise
