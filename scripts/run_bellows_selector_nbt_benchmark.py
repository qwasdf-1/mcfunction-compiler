#!/usr/bin/env python3
"""Run parity-checked Bellows x fused-compiler selector and NBT profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "runtime"))
sys.path.insert(0, str(ROOT / "scripts"))

from player_bot import PacketIds, PlayerBot  # noqa: E402
from analyze_spark_profile import summarize as summarize_spark_profile  # noqa: E402
from run_dynamic_lights_profile import (  # noqa: E402
    reserve_free_ports,
    spark_thread_node_count,
)
from run_runtime_probe import (  # noqa: E402
    RconClient,
    locate_official_server_jar,
)
from run_spawn_animations_profile import (  # noqa: E402
    start_spark_shell,
    stop_spark_shell,
    wait_for_spark_password,
)


OUTPUT_ROOT = ROOT / "build" / "benchmarks" / "PERF-005-006"
FIXTURE = ROOT / "tests" / "fixtures" / "function_compiler_perf_compat"
MODS_DIR = ROOT / "references" / "real-world" / "mods-26.3"
BELLOWS_JAR = MODS_DIR / "bellows-1.1.2.jar"
BELLOWS_SHA256 = "d0c7218e7e368c7d1473483881540ff78554853ff0a4f0bab098df6b3c753b67"
SPARK_AGENT = ROOT / "references" / "real-world" / "spark-1.10.194" / "spark-1.10.194-standalone-agent.jar"
SPARK_SHA256 = "a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9"
SERVER_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
RCON_HOST = "127.0.0.1"
ACTOR_COUNT = 64
WORKLOAD_REPETITIONS = 8
DEFAULT_REPETITIONS = 5
DEFAULT_PROFILE_SECONDS = 18
WARMUP_SECONDS = 4
SPARK_INTERVAL_MS = 1
MODES = (
    "vanilla",
    "fabric-off",
    "bellows-off",
    "fused-interpreted",
    "bellows-fused-interpreted",
)
MODE_CONFIG = {
    "vanilla": {"bellows": False, "compiler": False},
    "fabric-off": {"bellows": False, "compiler": False},
    "bellows-off": {"bellows": True, "compiler": False},
    "fused-interpreted": {"bellows": False, "compiler": True},
    "bellows-fused-interpreted": {"bellows": True, "compiler": True},
}
SCORE_HOLDERS = (
    "#selector_enabled",
    "#nbt_enabled",
    "#selector_ticks",
    "#nbt_ticks",
    "#selector_box",
    "#selector_furthest",
    "#selector_random",
    "#nbt_targets",
    "#optimizer_total",
    "#bad_noai",
    "#bad_health",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generate_profile_packet_ids(server_jar: Path, output_dir: Path) -> PacketIds:
    work = output_dir / "packet-report-work"
    report_root = work / "report"
    work.mkdir(parents=True, exist_ok=False)
    result = subprocess.run(
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
        timeout=300,
        check=False,
    )
    packets = report_root / "reports" / "packets.json"
    if result.returncode != 0 or not packets.is_file():
        shutil.rmtree(work, ignore_errors=True)
        raise RuntimeError("Minecraft packet report generation failed: " + result.stdout[-1600:])
    packet_ids = PacketIds.load(packets)
    shutil.rmtree(work, ignore_errors=True)
    return packet_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--seconds", type=int, default=DEFAULT_PROFILE_SECONDS)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--fresh", action="store_true", help="replace a prior matching report")
    args = parser.parse_args()
    if args.repetitions < 1 or args.repetitions > 20:
        parser.error("--repetitions must be between 1 and 20")
    if args.seconds < 3:
        parser.error("--seconds must be at least 3")
    return args


def write_server_files(work: Path, server_port: int, rcon_port: int, password: str) -> None:
    world = work / "world"
    source_datapack = world / "datapacks" / "function_compiler_probe"
    shutil.copytree(ROOT / "src" / "main" / "resources" / "data", source_datapack / "data")
    (source_datapack / "pack.mcmeta").write_text(
        json.dumps(
            {"pack": {"description": "Function Compiler benchmark probe", "min_format": [97, 1], "max_format": [97, 1]}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copytree(FIXTURE, world / "datapacks" / "function_compiler_perf_compat")
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    properties = {
        "enable-rcon": "true",
        "rcon.password": password,
        "rcon.port": str(rcon_port),
        "broadcast-rcon-to-ops": "false",
        "server-ip": RCON_HOST,
        "server-port": str(server_port),
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


def start_server(
    mode: str,
    work: Path,
    server_jar: Path,
    spark_port: int,
    log_path: Path,
) -> tuple[subprocess.Popen[bytes], object]:
    config = MODE_CONFIG[mode]
    log_handle = log_path.open("wb")
    if mode == "vanilla":
        environment = None
        command = [
            "java",
            "-Xms1G",
            "-Xmx2G",
            f"-javaagent:{SPARK_AGENT}=port={spark_port}",
            "-jar",
            str(server_jar),
            "nogui",
        ]
        cwd = work
    else:
        environment = os.environ.copy()
        project_cache = ROOT / ".gradle-user-home"
        if "GRADLE_USER_HOME" not in environment and project_cache.is_dir():
            environment["GRADLE_USER_HOME"] = str(project_cache)
        shared_cache = Path.home() / ".gradle" / "caches"
        if "GRADLE_RO_DEP_CACHE" not in environment and shared_cache.is_dir():
            environment["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
        environment.update(
            {
                "FC_WRAPPER_PROBE": str(config["compiler"]).lower(),
                "FC_SCORE_ADD_PROTOTYPE": str(config["compiler"]).lower(),
                "FC_SCORE_ADD_METRICS": "false",
                "FC_SCORE_ADD_TIMING": "false",
                "FC_FUSED_REGION_PROTOTYPE": str(config["compiler"]).lower(),
                "FC_BYTECODE_REGION_PROTOTYPE": "false",
                "FC_RUNTIME_TRACE": "false",
                "FC_FUNCTION_TIMING": "false",
            }
        )
        gradle_args = [
            "--no-daemon",
            f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
            f"-PfcSparkAgentPath={SPARK_AGENT}",
            f"-PfcSparkPort={spark_port}",
            "-PfcJvmArgs=-Xms1G,-Xmx2G",
            "runServer",
        ]
        if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
            gradle_args.insert(0, "--offline")
        command = [str(ROOT / "gradlew"), *gradle_args]
        cwd = ROOT
    if config["bellows"]:
        mods = work / "mods"
        mods.mkdir()
        shutil.copy2(BELLOWS_JAR, mods / BELLOWS_JAR.name)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def wait_for_rcon(process: subprocess.Popen[bytes], port: int, password: str) -> RconClient:
    deadline = time.monotonic() + 180
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited early with code {process.returncode}")
        try:
            return RconClient(RCON_HOST, port, password)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(0.5)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def command(client: RconClient, text: str) -> str:
    return client.command(text)


def get_score(client: RconClient, holder: str) -> int:
    response = command(client, f"scoreboard players get {holder} fc_perf")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not parse {holder} score: {response!r}")
    return int(match.group(1))


def set_scores(client: RconClient, holders: tuple[str, ...]) -> None:
    for holder in holders:
        response = command(client, f"scoreboard players set {holder} fc_perf 0")
        if "Unknown" in response or "Incorrect" in response:
            raise RuntimeError(f"Could not initialize {holder}: {response!r}")


def parse_tick_query(response: str) -> dict[str, float]:
    labels = {
        "average": r"Average time per tick: ([0-9.]+)ms",
        "p50": r"P50: ([0-9.]+)ms",
        "p95": r"P95: ([0-9.]+)ms",
        "p99": r"P99: ([0-9.]+)ms",
    }
    parsed: dict[str, float] = {}
    for label, pattern in labels.items():
        match = re.search(pattern, response)
        if match is None:
            raise RuntimeError(f"Could not parse {label} tick timing from /tick query: {response!r}")
        parsed[label] = float(match.group(1))
    return parsed


def spawn_entities(client: RconClient) -> list[str]:
    responses: list[str] = []
    for index in range(32):
        x = index % 8
        z = index // 8
        tags = ["fc_perf_selector", "fc_perf_nbt", "fc_perf_inside"]
        if index < 8:
            tags.append("fc_perf_excluded")
        responses.append(summon(client, x + 0.5, 0.5, tags))
    for index in range(32):
        x = 9 + index % 4
        z = index // 4
        tags = ["fc_perf_selector", "fc_perf_nbt", "fc_perf_far"]
        responses.append(summon(client, x + 0.5, z + 0.5, tags))
    return responses


def summon(client: RconClient, x: float, z: float, tags: list[str]) -> str:
    tag_snbt = ",".join(f'"{tag}"' for tag in tags)
    response = command(
        client,
        f"summon minecraft:zombie {x} 100 {z} "
        f"{{NoAI:1b,NoGravity:1b,Silent:1b,Invulnerable:1b,"
        f"PersistenceRequired:1b,Health:20.0f,Tags:[{tag_snbt}]}}",
    )
    if "summoned" not in response.casefold():
        raise RuntimeError(f"Could not summon a benchmark actor: {response!r}")
    return response


def verify_setup(client: RconClient) -> None:
    enabled = command(client, "datapack list enabled")
    if "function_compiler_perf_compat" not in enabled:
        raise RuntimeError(f"Benchmark fixture datapack did not load: {enabled!r}")
    command(client, "scoreboard objectives add fc_perf dummy")
    command(client, "gamerule doMobSpawning false")
    command(client, "gamerule doDaylightCycle false")
    command(client, "gamerule minecraft:max_command_sequence_length 65536")
    forceload = command(client, "forceload add 0 0 32 0")
    if not any(value in forceload.casefold() for value in ("added", "marked", "already")):
        raise RuntimeError(f"Could not force-load benchmark actors: {forceload!r}")
    set_scores(client, SCORE_HOLDERS)


def spawn_and_verify_entities(client: RconClient) -> None:
    summon_responses = spawn_entities(client)
    time.sleep(1)
    command(client, "scoreboard players set #actor_count fc_perf 0")
    tag_count_command = command(
        client,
        "execute as @e[type=minecraft:zombie,tag=fc_perf_nbt] "
        "run scoreboard players add #actor_count fc_perf 1",
    )
    actor_count = get_score(client, "#actor_count")
    if actor_count != ACTOR_COUNT:
        command(client, "scoreboard players set #all_zombies fc_perf 0")
        all_zombie_command = command(
            client,
            "execute as @e[type=minecraft:zombie] run scoreboard players add #all_zombies fc_perf 1",
        )
        all_zombies = get_score(client, "#all_zombies")
        sample = command(client, "data get entity @e[type=minecraft:zombie,limit=1]")
        forceload_query = command(client, "forceload query 0 0")
        raise RuntimeError(
            f"Expected {ACTOR_COUNT} benchmark actors, found {actor_count}; "
            f"all_zombies={all_zombies}, tag_count_command={tag_count_command!r}, "
            f"all_zombie_command={all_zombie_command!r}, sample={sample!r}, "
            f"forceload={forceload!r}, forceload_query={forceload_query!r}, "
            f"summon_responses={summon_responses[:2]!r}...{summon_responses[-2:]!r}"
        )


def verify_compiler_arm(client: RconClient, mode: str) -> dict[str, object]:
    if mode == "vanilla":
        return {"wrapper": False, "fused_regions_compiled": 0, "score_add_compiled": 0}
    status = command(client, "function_compiler_probe status")
    if "FC_PROBE present=true" not in status:
        raise RuntimeError(f"Function Compiler did not load in {mode}: {status!r}")
    if not MODE_CONFIG[mode]["compiler"]:
        for expected in (
            "wrapper_enabled=false",
            "score_add_prototype_enabled=false",
            "fused_region_prototype_enabled=false",
        ):
            if expected not in status:
                raise RuntimeError(f"Compiler features were active in {mode}: {status!r}")
        return {"wrapper": False, "fused_regions_compiled": 0, "score_add_compiled": 0}
    for expected in (
        "wrapped=true",
        "score_add_prototype_enabled=true",
        "score_add_metrics_enabled=false",
        "fused_region_prototype_enabled=true",
        "bytecode_region_prototype_enabled=false",
    ):
        if expected not in status:
            raise RuntimeError(f"{mode} did not enable expected compiler state {expected}: {status!r}")
    stats = command(client, "function_compiler_probe stats function_compiler_perf_compat:score_add_work")
    match = re.search(r"score_add_compiled=(\d+)", stats)
    if match is None or int(match.group(1)) != 4:
        raise RuntimeError(f"Benchmark ScoreAdd fixture did not compile all four entries: {stats!r}")
    fused_match = re.search(r"fused_regions_compiled=(\d+)", status)
    if fused_match is None or int(fused_match.group(1)) < 1:
        raise RuntimeError(f"Fused prototype compiled no region in {mode}: {status!r}")
    return {
        "wrapper": True,
        "fused_regions_compiled": int(fused_match.group(1)),
        "score_add_compiled_for_fixture": int(match.group(1)),
        "score_add_metrics_enabled": False,
    }


def reset_workload(client: RconClient, name: str) -> None:
    flag = "nbt" if name == "entity_nbt" else name
    command(client, "scoreboard players set #selector_enabled fc_perf 0")
    command(client, "scoreboard players set #nbt_enabled fc_perf 0")
    set_scores(client, SCORE_HOLDERS)
    command(
        client,
        f"scoreboard players set #{flag}_enabled fc_perf 1",
    )


def validate_workload(client: RconClient, name: str) -> dict[str, object]:
    flag = "nbt" if name == "entity_nbt" else name
    command(client, f"scoreboard players set #{flag}_enabled fc_perf 0")
    time.sleep(0.05)
    active_ticks = get_score(client, f"#{flag}_ticks")
    optimizer_total = get_score(client, "#optimizer_total")
    if active_ticks <= 0:
        raise RuntimeError(f"{name} workload ran no tick functions")
    expected_score_adds = active_ticks * 4 * WORKLOAD_REPETITIONS
    if optimizer_total != expected_score_adds:
        raise RuntimeError(
            f"{name} ScoreAdd sidecar was {optimizer_total} for {active_ticks} active ticks; "
            f"expected {expected_score_adds}"
        )
    state: dict[str, object] = {
        "active_ticks": active_ticks,
        "score_add_total": optimizer_total,
        "score_adds_per_tick": optimizer_total // active_ticks,
    }
    if name == "selector":
        counts = {
            "box_limit16": get_score(client, "#selector_box"),
            "furthest_limit12": get_score(client, "#selector_furthest"),
            "random_limit8": get_score(client, "#selector_random"),
        }
        expected = {
            "box_limit16": 16 * WORKLOAD_REPETITIONS,
            "furthest_limit12": 12 * WORKLOAD_REPETITIONS,
            "random_limit8": 8 * WORKLOAD_REPETITIONS,
        }
        normalized = {key: value // active_ticks for key, value in counts.items()}
        if normalized != expected:
            raise RuntimeError(f"Selector results diverged from expected per-tick counts: {normalized} != {expected}")
        state.update({"selector_counts": counts, "selector_counts_per_tick": normalized})
    else:
        target_count = get_score(client, "#nbt_targets")
        expected_updates = active_ticks * ACTOR_COUNT * WORKLOAD_REPETITIONS
        if target_count != expected_updates:
            raise RuntimeError(
                f"NBT operations reached {target_count} actors for {active_ticks} ticks; expected {expected_updates}"
            )
        command(client, "scoreboard players set #bad_noai fc_perf 0")
        command(
            client,
            "execute as @e[type=minecraft:zombie,tag=fc_perf_nbt] "
            "unless data entity @s {NoAI:1b} run scoreboard players add #bad_noai fc_perf 1",
        )
        command(client, "scoreboard players set #bad_health fc_perf 0")
        command(
            client,
            "execute as @e[type=minecraft:zombie,tag=fc_perf_nbt] "
            "unless score @s fc_perf matches 20000 run scoreboard players add #bad_health fc_perf 1",
        )
        bad_noai = get_score(client, "#bad_noai")
        bad_health = get_score(client, "#bad_health")
        if bad_noai or bad_health:
            raise RuntimeError(f"NBT state parity failed: bad NoAI={bad_noai}, bad Health scores={bad_health}")
        state.update(
            {
                "nbt_actor_updates": target_count,
                "nbt_actors_per_tick": target_count // active_ticks,
                "bad_noai": bad_noai,
                "bad_health_scores": bad_health,
                "sample_health_score": get_score(
                    client,
                    "@e[type=minecraft:zombie,tag=fc_perf_nbt,limit=1]",
                ),
            }
        )
    state["tick_query"] = command(client, "tick query")
    return state


def capture_profile(
    *,
    mode: str,
    workload: str,
    seconds: int,
    rcon: RconClient,
    work: Path,
    output_dir: Path,
    server: subprocess.Popen[bytes],
    log_path: Path,
    spark_password: str,
    spark_port: int,
    trial: int,
) -> dict[str, object]:
    reset_workload(rcon, workload)
    time.sleep(WARMUP_SECONDS)
    before = set(SCORE_HOLDERS)
    ssh = start_spark_shell(work, spark_password, spark_port)
    try:
        assert ssh.stdin is not None
        ssh.stdin.write(f"spark profiler start --interval {SPARK_INTERVAL_MS} --thread *\n".encode("ascii"))
        ssh.stdin.flush()
        time.sleep(seconds)
        spark_output = stop_spark_shell(ssh)
        ssh = None
    finally:
        if ssh is not None and ssh.poll() is None:
            if ssh.stdin is not None:
                ssh.stdin.write(b"exit\n")
                ssh.stdin.flush()
            ssh.wait(timeout=10)
    candidates = list(work.rglob("*.sparkprofile"))
    if not candidates:
        raise RuntimeError(f"Spark did not save a profile for {mode}/{workload}")
    source_profile = max(candidates, key=lambda path: path.stat().st_mtime_ns)
    profile = output_dir / f"trial-{trial:02d}-{mode}-{workload}.sparkprofile"
    shutil.copy2(source_profile, profile)
    thread_nodes = spark_thread_node_count(profile)
    if thread_nodes < 1:
        raise RuntimeError(f"Spark profile has no thread nodes: {profile}")
    analysis = summarize_spark_profile(profile, "Server thread", 100)
    server_thread = analysis["matched_threads"][0]
    weighted_execute = sum(
        float(method["inclusive_weighted_value"])
        for method in server_thread["top_methods"]
        if method["method"] == "execute" and "ServerFunctionManager" in method["class"]
    )
    outcome = validate_workload(rcon, workload)
    tick_query = outcome["tick_query"]
    return {
        "mode": mode,
        "workload": workload,
        "trial": trial,
        "profile_seconds": seconds,
        "spark_interval_ms": SPARK_INTERVAL_MS,
        "spark_thread_scope": "all threads",
        "spark_profile": str(profile.relative_to(ROOT)),
        "spark_profile_sha256": sha256(profile),
        "spark_thread_nodes": thread_nodes,
        "server_thread_weighted_total": server_thread["total_weighted_value"],
        "server_function_manager_execute_weighted": weighted_execute,
        "spark_top_server_thread_methods": server_thread["top_methods"][:20],
        "server_tick_timings_ms": parse_tick_query(str(tick_query)),
        "spark_shell_output": spark_output,
        "outcome": outcome,
    }


def run_arm(
    *,
    mode: str,
    trial: int,
    workload_order: list[str],
    server_jar: Path,
    packet_ids: PacketIds,
    run_id: str,
    output_dir: Path,
    seconds: int,
) -> dict[str, object]:
    work = ROOT / "run" / f"perf-005-006-{run_id}-{trial:02d}-{mode}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    server_port, rcon_port, spark_port = reserve_free_ports(3)
    password = f"fc-prof-{trial:02d}-{mode}-{os.getpid()}"
    write_server_files(work, server_port, rcon_port, password)
    log_path = work / "server.log"
    server, log_handle = start_server(mode, work, server_jar, spark_port, log_path)
    rcon: RconClient | None = None
    bot: PlayerBot | None = None
    completed = False
    try:
        rcon = wait_for_rcon(server, rcon_port, password)
        verify_setup(rcon)
        bot = PlayerBot("FCPerf", RCON_HOST, server_port, packet_ids).connect()
        for player_command in ("gamemode creative FCPerf", "tp FCPerf 0 100 0"):
            response = command(rcon, player_command)
            if "Unknown" in response or "Could not" in response:
                raise RuntimeError(f"Could not prepare benchmark player: {player_command}: {response!r}")
        time.sleep(1)
        spawn_and_verify_entities(rcon)
        compiler_state = verify_compiler_arm(rcon, mode)
        spark_password = wait_for_spark_password(log_path, server)
        profiles = [
            capture_profile(
                mode=mode,
                workload=workload,
                seconds=seconds,
                rcon=rcon,
                work=work,
                output_dir=output_dir,
                server=server,
                log_path=log_path,
                spark_password=spark_password,
                spark_port=spark_port,
                trial=trial,
            )
            for workload in workload_order
        ]
        normalized = {
            profile["workload"]: (
                {
                    "selector_counts_per_tick": profile["outcome"]["selector_counts_per_tick"],
                    "score_adds_per_tick": profile["outcome"]["score_adds_per_tick"],
                }
                if profile["workload"] == "selector"
                else {
                    "nbt_actors_per_tick": profile["outcome"]["nbt_actors_per_tick"],
                    "sample_health_score": profile["outcome"]["sample_health_score"],
                    "bad_noai": profile["outcome"]["bad_noai"],
                    "bad_health_scores": profile["outcome"]["bad_health_scores"],
                    "score_adds_per_tick": profile["outcome"]["score_adds_per_tick"],
                }
            )
            for profile in profiles
        }
        bot.assert_connected()
        command(rcon, "stop")
        server.wait(timeout=90)
        completed = True
        return {
            "trial": trial,
            "mode": mode,
            "workload_order": workload_order,
            "compiler_state": compiler_state,
            "normalized_outcomes": normalized,
            "profiles": profiles,
        }
    finally:
        if rcon is not None:
            rcon.close()
        if bot is not None:
            bot.close()
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        log_handle.close()
        if not completed and log_path.is_file():
            failure_log = output_dir / f"failed-trial-{trial:02d}-{mode}.log"
            shutil.copy2(log_path, failure_log)
            print(f"Preserved failed server log: {failure_log}", file=sys.stderr, flush=True)
        shutil.rmtree(work, ignore_errors=True)


def median_mad(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    middle = ordered[len(ordered) // 2]
    deviations = sorted(abs(value - middle) for value in values)
    return {
        "median": middle,
        "mad": deviations[len(deviations) // 2],
        "min": ordered[0],
        "max": ordered[-1],
    }


def main() -> int:
    args = parse_args()
    if not BELLOWS_JAR.is_file() or sha256(BELLOWS_JAR) != BELLOWS_SHA256:
        raise FileNotFoundError(f"Missing or mismatched pinned Bellows jar: {BELLOWS_JAR}")
    if not SPARK_AGENT.is_file() or sha256(SPARK_AGENT) != SPARK_SHA256:
        raise FileNotFoundError(f"Missing or mismatched Spark standalone agent: {SPARK_AGENT}")
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_SHA256:
        raise RuntimeError(f"Minecraft server artifact hash mismatch: {server_jar}")
    fixture_hashes = {
        str(path.relative_to(FIXTURE)): sha256(path)
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file()
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    packet_ids = generate_profile_packet_ids(server_jar, output_dir)
    results_path = output_dir / "results.json"
    manifest = {
        "benchmark": "PERF-005-006",
        "minecraft": "26.3",
        "server_sha256": sha256(server_jar),
        "bellows": {"file": BELLOWS_JAR.name, "sha256": sha256(BELLOWS_JAR)},
        "spark": {"file": SPARK_AGENT.name, "sha256": sha256(SPARK_AGENT)},
        "modes": list(MODES),
        "workloads": ["selector", "entity_nbt"],
        "repetitions": args.repetitions,
        "profile_seconds": args.seconds,
        "warmup_seconds": WARMUP_SECONDS,
        "spark_interval_ms": SPARK_INTERVAL_MS,
        "actor_count": ACTOR_COUNT,
        "workload_repetitions_per_tick": WORKLOAD_REPETITIONS,
        "seed": args.seed,
        "fixture_sha256": fixture_hashes,
        "metrics_enabled_during_profiles": False,
        "jvm_heap": "-Xms1G -Xmx2G",
        "limitations": [
            "Controlled selector/NBT fixture, not a real datapack workload.",
            "Spark weights are sampled inclusive estimates; /tick query is whole-server context.",
            "The four-line ScoreAdd sidecar exercises the fused compiler in each active profile.",
            "The vanilla arm uses Mojang's standalone server; every other arm uses the project's Fabric runtime.",
            "The fabric-off and bellows-off arms load the dev mod with all compiler features disabled.",
        ],
    }
    report: dict[str, object]
    if results_path.is_file() and not args.fresh:
        report = json.loads(results_path.read_text(encoding="utf-8"))
        if report.get("manifest") != manifest:
            raise RuntimeError("Existing PERF-005/006 report has a different manifest; rerun with --fresh")
        arms = list(report.get("arms", []))
    else:
        arms = []
        report = {"manifest": manifest, "arms": [], "summary": None}
        results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rng = random.Random(args.seed)
    order: list[tuple[int, str, list[str]]] = []
    for trial in range(1, args.repetitions + 1):
        trial_modes = list(MODES)
        rng.shuffle(trial_modes)
        for mode in trial_modes:
            workloads = ["selector", "entity_nbt"]
            rng.shuffle(workloads)
            order.append((trial, mode, workloads))
    report["manifest"]["trial_order"] = [
        {"trial": trial, "mode": mode, "workloads": workloads}
        for trial, mode, workloads in order
    ]
    completed = {(int(arm["trial"]), str(arm["mode"])) for arm in arms}
    results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for trial, mode, workload_order in order:
        if (trial, mode) in completed:
            continue
        print(f"Starting PERF-005/006 trial={trial} mode={mode} workloads={workload_order}", flush=True)
        arm = run_arm(
            mode=mode,
            trial=trial,
            workload_order=workload_order,
            server_jar=server_jar,
            packet_ids=packet_ids,
            run_id=run_id,
            output_dir=output_dir,
            seconds=args.seconds,
        )
        arms.append(arm)
        report["arms"] = arms
        results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Completed PERF-005/006 trial={trial} mode={mode}", flush=True)

    baseline_by_trial = {
        int(arm["trial"]): arm["normalized_outcomes"]
        for arm in arms
        if arm["mode"] == "vanilla"
    }
    parity: dict[str, bool] = {}
    for arm in arms:
        if arm["mode"] == "vanilla":
            continue
        key = f"trial-{arm['trial']}-{arm['mode']}"
        parity[key] = arm["normalized_outcomes"] == baseline_by_trial[int(arm["trial"])]
    if len(arms) != args.repetitions * len(MODES):
        raise RuntimeError(f"Incomplete benchmark: {len(arms)} of {args.repetitions * len(MODES)} arms")
    if not all(parity.values()):
        report["parity_pass"] = False
        report["parity_vs_vanilla"] = parity
        report["arms"] = arms
        results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(f"Behavior parity failed before performance comparison: {parity}")

    grouped: dict[str, dict[str, object]] = {}
    for workload in ("selector", "entity_nbt"):
        grouped[workload] = {}
        for mode in MODES:
            profiles = [
                profile
                for arm in arms
                if arm["mode"] == mode
                for profile in arm["profiles"]
                if profile["workload"] == workload
            ]
            grouped[workload][mode] = {
                "server_function_manager_execute_weighted": median_mad(
                    [float(profile["server_function_manager_execute_weighted"]) for profile in profiles]
                ),
                "server_thread_weighted_total": median_mad(
                    [float(profile["server_thread_weighted_total"]) for profile in profiles]
                ),
                "server_tick_average_ms": median_mad(
                    [float(profile["server_tick_timings_ms"]["average"]) for profile in profiles]
                ),
                "server_tick_p50_ms": median_mad(
                    [float(profile["server_tick_timings_ms"]["p50"]) for profile in profiles]
                ),
                "server_tick_p95_ms": median_mad(
                    [float(profile["server_tick_timings_ms"]["p95"]) for profile in profiles]
                ),
                "server_tick_p99_ms": median_mad(
                    [float(profile["server_tick_timings_ms"]["p99"]) for profile in profiles]
                ),
                "trial_values": [
                    {
                        "trial": profile["trial"],
                        "server_function_manager_execute_weighted": profile[
                            "server_function_manager_execute_weighted"
                        ],
                        "server_thread_weighted_total": profile["server_thread_weighted_total"],
                    }
                    for profile in profiles
                ],
            }
    report["parity_pass"] = True
    report["parity_vs_vanilla"] = parity
    report["summary"] = grouped
    results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"parity_pass": True, "summary": grouped, "report": str(results_path)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PERF-005/006 benchmark failed: {error}", file=sys.stderr)
        raise
