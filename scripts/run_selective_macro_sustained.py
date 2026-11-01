#!/usr/bin/env python3
"""Measure a sustained selective-macro workload on Minecraft 26.3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "runtime"))

from mod_artifacts import MODS, MODS_DIR, STACK_MODS  # noqa: E402
from paired_benchmark_analysis import paired_percent_changes, summarize_paired_changes  # noqa: E402
from player_bot import PacketIds, PlayerBot  # noqa: E402
from run_entity_datapack_profile import DrainingRconClient  # noqa: E402
from run_runtime_probe import (  # noqa: E402
    SERVER_JAR_SHA256,
    generate_packet_ids,
    locate_official_server_jar,
)


FIXTURE = ROOT / "tests/fixtures/function_compiler_selective_macro_perf"
OUTPUT_ROOT = ROOT / "build/benchmarks/PERF-MACRO-SUSTAINED"
RUN_ROOT = ROOT / "run"
HOST = "127.0.0.1"
ENTITY_TYPE = "minecraft:marker"
ENTITY_COUNT = 256
CALLS_PER_ENTITY_TICK = 1
CALLS_PER_TICK = ENTITY_COUNT * CALLS_PER_ENTITY_TICK
FRONTIER_ENTRIES = 216
WARMUP_ACTIVE_TICKS = 100
MEASURED_ACTIVE_TICKS = 110
TICK_QUERY_WINDOW = 100
DEFAULT_STACK = "lb113"
DEFAULT_MINIMUM_GAIN_PERCENT = 15.0
ACTIVE_REPORT_PATH: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generated_setup_functions() -> dict[str, str]:
    setup_lines = ["scoreboard players set #entities fc_macro 0"]
    for index in range(ENTITY_COUNT):
        x = index % 16
        z = index // 16
        tag = f"fc_macro_actor_{index}"
        setup_lines.extend(
            (
                f'summon {ENTITY_TYPE} {x + 0.5} 100 {z + 0.5} '
                f'{{Tags:["fc_macro_source","{tag}"]}}',
                f"data merge entity @e[type={ENTITY_TYPE},tag={tag},limit=1] "
                f"{{data:{{head:{index + 1}}}}}",
            )
        )
    frontier = ",".join(
        f"{{x:{index % 16},y:{64 + (index // 16) % 16},z:{(index * 7) % 16}}}"
        for index in range(FRONTIER_ENTRIES)
    )
    return {
        "data/function_compiler_selective_macro_perf/function/setup_entities.mcfunction": (
            "\n".join(setup_lines) + "\n"
        ),
        "data/function_compiler_selective_macro_perf/function/populate_frontier.mcfunction": (
            f"data merge entity @s {{data:{{frontier:[{frontier}]}}}}\n"
        ),
    }


def reserve_ports(count: int) -> tuple[int, ...]:
    reservations: list[socket.socket] = []
    try:
        while len(reservations) < count:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.bind((HOST, 0))
            if any(probe.getsockname()[1] == item.getsockname()[1] for item in reservations):
                probe.close()
                continue
            reservations.append(probe)
        return tuple(int(item.getsockname()[1]) for item in reservations)
    finally:
        for probe in reservations:
            probe.close()


def wait_for_rcon(
    process: subprocess.Popen[bytes], port: int, password: str, timeout_seconds: int = 240
) -> DrainingRconClient:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft exited early with code {process.returncode}")
        try:
            return DrainingRconClient(HOST, port, password)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(0.5)
    raise TimeoutError(f"RCON did not become ready: {last_error}")


def connect_player_when_ready(
    process: subprocess.Popen[bytes], server_port: int, packet_ids: PacketIds
) -> tuple[PlayerBot, int]:
    """Let dedicated-server startup settle and retry transient login closes."""
    time.sleep(1.0)
    attempts = 0
    last_error: Exception | None = None
    while attempts < 3:
        if process.poll() is not None:
            raise RuntimeError(
                f"Minecraft exited before player login with code {process.returncode}"
            )
        attempts += 1
        bot = PlayerBot("FCMacro", HOST, server_port, packet_ids)
        try:
            return bot.connect(), attempts
        except (ConnectionError, RuntimeError) as error:
            bot.close()
            last_error = error
            if "server closed the player connection" not in str(error):
                raise
            if attempts < 3:
                time.sleep(1.0)
    raise RuntimeError(
        f"Minecraft closed all three player login attempts; last error: {last_error}"
    )


def score(rcon: DrainingRconClient, holder: str) -> int:
    response = rcon.command(f"scoreboard players get {holder} fc_macro")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not read #{holder} fc_macro: {response!r}")
    return int(match.group(1))


def tick_metrics(response: str) -> dict[str, float]:
    patterns = {
        "tick_average_ms": r"Average time per tick: ([0-9.]+)ms",
        "tick_p50_ms": r"P50: ([0-9.]+)ms",
        "tick_p95_ms": r"P95: ([0-9.]+)ms",
        "tick_p99_ms": r"P99: ([0-9.]+)ms",
    }
    parsed: dict[str, float] = {}
    for label, pattern in patterns.items():
        match = re.search(pattern, response)
        if match is None:
            raise RuntimeError(f"Could not parse {label} from /tick query: {response!r}")
        parsed[label] = float(match.group(1))
    return parsed


def wait_for_score(
    process: subprocess.Popen[bytes],
    rcon: DrainingRconClient,
    holder: str,
    target: int,
    timeout_seconds: int = 240,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    current = score(rcon, holder)
    while current < target and time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft exited while waiting for #{holder}")
        time.sleep(0.2)
        current = score(rcon, holder)
    if current < target:
        raise TimeoutError(f"#{holder} reached {current}; expected at least {target}")
    return current


def server_environment(mode: str, diagnostic: bool) -> dict[str, str]:
    environment = os.environ.copy()
    project_cache = ROOT / ".gradle-user-home"
    if "GRADLE_USER_HOME" not in environment and project_cache.is_dir():
        environment["GRADLE_USER_HOME"] = str(project_cache)
    shared_cache = Path.home() / ".gradle/caches"
    if "GRADLE_RO_DEP_CACHE" not in environment and shared_cache.is_dir():
        environment["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
    candidate = mode == "selective-macro"
    environment.update(
        {
            "FC_WRAPPER_PROBE": str(candidate).lower(),
            "FC_SCORE_ADD_PROTOTYPE": "false",
            "FC_SCORE_ADD_METRICS": "false",
            "FC_SCORE_ADD_TIMING": "false",
            "FC_FUSED_REGION_PROTOTYPE": "false",
            "FC_BYTECODE_REGION_PROTOTYPE": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS": str(candidate).lower(),
            "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": str(candidate and diagnostic).lower(),
            "FC_COMMAND_CALLBACK_METRICS": "false",
            "FC_FUNCTION_TIMING": "false",
            "FC_RUNTIME_TRACE": "false",
        }
    )
    return environment


def prepare_workdir(
    work: Path,
    *,
    mode: str,
    stack: str,
    server_port: int,
    rcon_port: int,
    password: str,
) -> Path:
    world = work / "world"
    datapack_dir = world / "datapacks" / FIXTURE.name
    shutil.copytree(FIXTURE, datapack_dir)
    for relative, contents in generated_setup_functions().items():
        setup_path = datapack_dir / relative
        setup_path.parent.mkdir(parents=True, exist_ok=True)
        setup_path.write_text(contents, encoding="utf-8")
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    properties = {
        "enable-rcon": "true",
        "rcon.password": password,
        "rcon.port": str(rcon_port),
        "broadcast-rcon-to-ops": "false",
        "server-ip": HOST,
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
    if mode != "vanilla":
        mod_dir = work / "mods"
        mod_dir.mkdir()
        for key in STACK_MODS[stack]:
            filename, expected = MODS[key]
            source = MODS_DIR / filename
            if not source.is_file() or sha256(source) != expected:
                raise FileNotFoundError(f"Missing/mismatched pinned {key} jar: {source}")
            shutil.copy2(source, mod_dir / filename)
    return datapack_dir


def start_server(
    mode: str,
    *,
    stack: str,
    work: Path,
    server_jar: Path,
    server_port: int,
    log_handle: object,
    diagnostic: bool,
) -> subprocess.Popen[bytes]:
    if mode == "vanilla":
        command = ["java", "-Xms512M", "-Xmx2G", "-jar", str(server_jar), "nogui"]
        cwd = work
        environment = None
    else:
        gradle_args = [
            "--offline",
            "--no-daemon",
            f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
            "-PfcJvmArgs=-Xms512M,-Xmx2G",
            "runServer",
        ]
        command = [str(ROOT / "gradlew"), *gradle_args]
        cwd = ROOT
        environment = server_environment(mode, diagnostic)
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )


def setup_fixture(rcon: DrainingRconClient) -> None:
    enabled = rcon.command("datapack list enabled")
    if FIXTURE.name not in enabled:
        raise RuntimeError(f"Sustained macro fixture did not load: {enabled!r}")
    rcon.command("gamerule doMobSpawning false")
    rcon.command("gamerule doDaylightCycle false")
    rcon.command("gamerule randomTickSpeed 0")
    rcon.command("forceload add 0 0 15 15")
    rcon.command("function function_compiler_selective_macro_perf:setup_entities")
    rcon.command(
        "execute as @e[type=minecraft:marker,tag=fc_macro_source] run "
        "function function_compiler_selective_macro_perf:populate_frontier"
    )
    rcon.command(
        f"execute as @e[type={ENTITY_TYPE},tag=fc_macro_source] "
        "run scoreboard players add #entities fc_macro 1"
    )
    actual_entities = score(rcon, "#entities")
    if actual_entities != ENTITY_COUNT:
        presence = rcon.command(
            f"execute if entity @e[type={ENTITY_TYPE},tag=fc_macro_source]"
        )
        raise RuntimeError(
            f"Expected {ENTITY_COUNT} actors, got {actual_entities}; "
            f"selector result={presence!r}, "
            f"forceload={rcon.command('forceload query')!r}"
        )
    amount = rcon.command(
        f"data get entity @e[type={ENTITY_TYPE},tag=fc_macro_actor_0,limit=1] data.head"
    )
    if not amount.rstrip().endswith("1"):
        raise RuntimeError(f"Macro source data.head was not 1: {amount!r}")
    frontier_size = rcon.command(
        f"data get entity @e[type={ENTITY_TYPE},tag=fc_macro_actor_0,limit=1] "
        f"data.frontier[{FRONTIER_ENTRIES - 1}].x"
    )
    expected_last_x = (FRONTIER_ENTRIES - 1) % 16
    if not frontier_size.rstrip().endswith(str(expected_last_x)):
        raise RuntimeError(f"Macro source frontier was not initialized: {frontier_size!r}")
    rcon.command("scoreboard players set #enabled fc_macro 0")
    rcon.command("scoreboard players set #server_ticks fc_macro 0")
    rcon.command("scoreboard players set #active_ticks fc_macro 0")
    rcon.command("scoreboard players set #calls fc_macro 0")
    rcon.command("scoreboard players set #work fc_macro 0")


def run_arm(
    *,
    run_id: str,
    arm_name: str,
    mode: str,
    stack: str,
    server_jar: Path,
    packet_ids: PacketIds,
    output_dir: Path,
    diagnostic: bool = False,
) -> dict[str, object]:
    work = RUN_ROOT / f"selective-macro-{run_id}-{arm_name}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    server_port, rcon_port = reserve_ports(2)
    password = f"fc-macro-{os.getpid()}-{arm_name}"
    prepare_workdir(
        work,
        mode=mode,
        stack=stack,
        server_port=server_port,
        rcon_port=rcon_port,
        password=password,
    )
    log_path = output_dir / f"{arm_name}.server.log"
    log_handle = log_path.open("wb")
    server: subprocess.Popen[bytes] | None = None
    rcon: DrainingRconClient | None = None
    bot: PlayerBot | None = None
    player_login_attempts = 0
    try:
        server = start_server(
            mode,
            stack=stack,
            work=work,
            server_jar=server_jar,
            server_port=server_port,
            log_handle=log_handle,
            diagnostic=diagnostic,
        )
        rcon = wait_for_rcon(server, rcon_port, password)
        bot, player_login_attempts = connect_player_when_ready(server, server_port, packet_ids)
        rcon.command("gamemode spectator FCMacro")
        rcon.command("tp FCMacro 4 100 4")
        setup_fixture(rcon)
        compiler_status = None
        if mode != "vanilla":
            compiler_status = rcon.command("function_compiler_probe status")
            expected_selective = mode == "selective-macro"
            expected_metrics = expected_selective and diagnostic
            for label, expected in (
                ("selective_macro_arguments_enabled", expected_selective),
                ("selective_macro_arguments_metrics_enabled", expected_metrics),
            ):
                if f"{label}={str(expected).lower()}" not in compiler_status:
                    raise RuntimeError(f"{arm_name} has wrong {label}: {compiler_status!r}")

        server_tick_start = score(rcon, "#server_ticks")
        wait_for_score(
            server,
            rcon,
            "#server_ticks",
            server_tick_start + 110,
        )
        idle_tick_query = rcon.command("tick query")
        idle_timings = tick_metrics(idle_tick_query)
        rcon.command("scoreboard players set #enabled fc_macro 1")
        active_ticks = wait_for_score(
            server,
            rcon,
            "#active_ticks",
            WARMUP_ACTIVE_TICKS + MEASURED_ACTIVE_TICKS,
            timeout_seconds=600,
        )
        active_started = time.monotonic()
        active_tick_query = rcon.command("tick query")
        query_elapsed = time.monotonic() - active_started
        active_timings = tick_metrics(active_tick_query)
        rcon.command("scoreboard players set #enabled fc_macro 0")
        calls = score(rcon, "#calls")
        work_value = score(rcon, "#work")
        ticks = score(rcon, "#active_ticks")
        expected_calls = ticks * CALLS_PER_TICK
        expected_work = ticks * (ENTITY_COUNT * (ENTITY_COUNT + 1) // 2)
        if calls != expected_calls or work_value != expected_work:
            raise RuntimeError(
                f"Workload integrity failed: ticks={ticks}, calls={calls}, work={work_value}, "
                f"expected calls={expected_calls}, expected work={expected_work}"
            )
        activation = None
        if diagnostic:
            status_after = rcon.command("function_compiler_probe status")
            match = re.search(r"selective_macro_arguments_used=(\d+)", status_after)
            if match is None:
                raise RuntimeError(f"Diagnostic omitted selective argument count: {status_after!r}")
            selected_calls = int(match.group(1))
            if mode == "selective-macro" and selected_calls != expected_calls:
                raise RuntimeError(
                    f"Selective path ran {selected_calls} calls; expected {expected_calls}"
                )
            activation = {
                "selected_argument_calls": selected_calls,
                "expected_argument_calls": expected_calls,
                "exact": selected_calls == expected_calls if mode == "selective-macro" else None,
            }

        if server.poll() is not None:
            raise RuntimeError(f"Minecraft exited during arm {arm_name}")
        rcon.command("stop")
        server.wait(timeout=60)
        state = {
            "active_ticks": ticks,
            "calls": calls,
            "work": work_value,
            "calls_per_active_tick": calls / ticks,
            "work_per_active_tick": work_value / ticks,
            "expected_calls_per_active_tick": CALLS_PER_TICK,
            "expected_work_per_active_tick": ENTITY_COUNT * (ENTITY_COUNT + 1) // 2,
            "exact_workload_integrity": calls == expected_calls and work_value == expected_work,
        }
        return {
            "arm": arm_name,
            "mode": mode,
            "stack": stack if mode != "vanilla" else "mod-free-vanilla",
            "diagnostic_only": diagnostic,
            "instrumentation": "selective argument counter enabled" if diagnostic else "no Spark; no compiler counters or timers",
            "warmup_active_ticks": WARMUP_ACTIVE_TICKS,
            "active_tick_threshold_observed": active_ticks,
            "active_tick_count_at_stop": ticks,
            "tick_query_window_ticks": TICK_QUERY_WINDOW,
            "idle_tick_timings_ms": idle_timings,
            "active_tick_timings_ms": active_timings,
            "query_command_elapsed_seconds": query_elapsed,
            "state": state,
            "activation_diagnostic": activation,
            "compiler_status_before_work": compiler_status,
            "player_login_attempts": player_login_attempts,
            "server_log": str(log_path.relative_to(ROOT)),
        }
    except Exception:
        if log_path.is_file():
            print(f"Preserved server log: {log_path}", file=sys.stderr, flush=True)
        raise
    finally:
        if rcon is not None:
            rcon.close()
        if bot is not None:
            bot.close()
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        log_handle.close()
        shutil.rmtree(work, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=("lb113", "lbm113", "lbm113120"), default=DEFAULT_STACK)
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=26871031)
    parser.add_argument("--phase", choices=("screening", "confirmatory"), default="screening")
    parser.add_argument(
        "--minimum-gain-percent",
        type=float,
        default=DEFAULT_MINIMUM_GAIN_PERCENT,
        help="predeclared worthwhile active-tick-average improvement; default 15%%",
    )
    args = parser.parse_args()
    if args.pairs < 2:
        parser.error("--pairs must be at least 2")
    if args.phase == "confirmatory" and args.pairs < 6:
        parser.error("confirmatory campaigns require at least six pairs")
    if args.minimum_gain_percent <= 0:
        parser.error("--minimum-gain-percent must be positive")
    return args


def main() -> int:
    args = parse_args()
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_JAR_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server hash mismatch: {server_jar}")
    packet_ids = generate_packet_ids(server_jar)
    mods = [
        {"file": MODS[key][0], "sha256": sha256(MODS_DIR / MODS[key][0])}
        for key in STACK_MODS[args.stack]
    ]
    for item, key in zip(mods, STACK_MODS[args.stack], strict=True):
        if item["sha256"] != MODS[key][1]:
            raise RuntimeError(f"Pinned mod hash mismatch: {item['file']}")
    fixture_hashes = {
        str(path.relative_to(FIXTURE)): sha256(path)
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file()
    }
    generated_hashes = {
        relative: hashlib.sha256(contents.encode("utf-8")).hexdigest()
        for relative, contents in generated_setup_functions().items()
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = OUTPUT_ROOT / f"{args.stack}-{args.phase}-{args.pairs}pairs-{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "results.json"
    global ACTIVE_REPORT_PATH
    ACTIVE_REPORT_PATH = report_path
    report: dict[str, object] = {
        "benchmark": "PERF-MACRO-SUSTAINED",
        "minecraft": "26.3",
        "server_sha256": sha256(server_jar),
        "stack": args.stack,
        "mods": mods,
        "fixture_sha256": fixture_hashes,
        "generated_setup_sha256": generated_hashes,
        "runner_sha256": sha256(Path(__file__).resolve()),
        "candidate": "selective-macro",
        "metric": "active_tick_timings_ms.tick_average_ms",
        "minimum_gain_percent": args.minimum_gain_percent,
        "decision_rule": "95% exact paired median interval must support at least the preselected gain",
        "phase": args.phase,
        "pairs_requested": args.pairs,
        "random_seed": args.seed,
        "configuration": {
            "entity_count": ENTITY_COUNT,
            "irrelevant_frontier_entries_per_entity": FRONTIER_ENTRIES,
            "macro_parameter_values_per_tick": ENTITY_COUNT,
            "macro_calls_per_entity_per_tick": CALLS_PER_ENTITY_TICK,
            "macro_calls_per_active_tick": CALLS_PER_TICK,
            "macro_work_sum_per_active_tick": ENTITY_COUNT * (ENTITY_COUNT + 1) // 2,
            "warmup_active_ticks": WARMUP_ACTIVE_TICKS,
            "measurement_active_ticks_minimum": MEASURED_ACTIVE_TICKS,
            "tick_query_window_ticks": TICK_QUERY_WINDOW,
            "spark": False,
            "compiler_counters_during_timing": False,
            "jvm_args": "-Xms512M -Xmx2G",
        },
        "arms": [],
        "pairs": [],
        "status": "running",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("Running standalone vanilla correctness reference", flush=True)
    vanilla = run_arm(
        run_id=run_id,
        arm_name="vanilla-reference",
        mode="vanilla",
        stack=args.stack,
        server_jar=server_jar,
        packet_ids=packet_ids,
        output_dir=output_dir,
    )
    report["vanilla_reference"] = vanilla
    report["arms"].append(vanilla)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not vanilla["state"]["exact_workload_integrity"]:
        raise RuntimeError("Vanilla workload integrity failed")

    diagnostic = run_arm(
        run_id=run_id,
        arm_name="activation-diagnostic",
        mode="selective-macro",
        stack=args.stack,
        server_jar=server_jar,
        packet_ids=packet_ids,
        output_dir=output_dir,
        diagnostic=True,
    )
    report["activation_diagnostic"] = diagnostic
    report["arms"].append(diagnostic)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not diagnostic["activation_diagnostic"]["exact"]:
        raise RuntimeError("Selective macro activation diagnostic did not count every eligible call")

    rng = random.Random(args.seed)
    pair_orders = [["off", "selective-macro"] for _ in range(args.pairs // 2)]
    pair_orders.extend([["selective-macro", "off"] for _ in range(args.pairs // 2)])
    if args.pairs % 2:
        pair_orders.append(
            ["off", "selective-macro"]
            if rng.randrange(2) == 0
            else ["selective-macro", "off"]
        )
    rng.shuffle(pair_orders)
    for pair_index in range(1, args.pairs + 1):
        order = pair_orders[pair_index - 1]
        pair_arms: dict[str, dict[str, object]] = {}
        print(f"Starting sustained macro pair {pair_index}/{args.pairs}: {order}", flush=True)
        for label in order:
            arm = run_arm(
                run_id=run_id,
                arm_name=f"pair-{pair_index:02d}-{label}",
                mode=label,
                stack=args.stack,
                server_jar=server_jar,
                packet_ids=packet_ids,
                output_dir=output_dir,
            )
            pair_arms[label] = arm
            report["arms"].append(arm)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        vanilla_rate = vanilla["state"]["calls_per_active_tick"]
        parity = all(
            arm["state"]["calls_per_active_tick"] == vanilla_rate
            and arm["state"]["work_per_active_tick"] == vanilla["state"]["work_per_active_tick"]
            for arm in pair_arms.values()
        )
        pair = {
            "repetition": pair_index,
            "order": order,
            "off": {
                "tick_average_ms": pair_arms["off"]["active_tick_timings_ms"]["tick_average_ms"],
                "tick_p95_ms": pair_arms["off"]["active_tick_timings_ms"]["tick_p95_ms"],
            },
            "selective-macro": {
                "tick_average_ms": pair_arms["selective-macro"]["active_tick_timings_ms"]["tick_average_ms"],
                "tick_p95_ms": pair_arms["selective-macro"]["active_tick_timings_ms"]["tick_p95_ms"],
            },
            "exact_parity_with_vanilla": parity,
        }
        report["pairs"].append(pair)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not parity:
            raise RuntimeError(f"Pair {pair_index} differs from vanilla workload counts")

    primary_changes = paired_percent_changes(
        report["pairs"],
        metric="tick_average_ms",
        baseline_arm="off",
        candidate_arm="selective-macro",
    )
    report["analysis"] = {
        "active_tick_average_ms": summarize_paired_changes(
            primary_changes,
            minimum_gain_percent=args.minimum_gain_percent if args.phase == "confirmatory" else None,
        ),
        "active_tick_p95_ms": summarize_paired_changes(
            paired_percent_changes(
                report["pairs"],
                metric="tick_p95_ms",
                baseline_arm="off",
                candidate_arm="selective-macro",
            )
        ),
    }
    report["performance_decision"] = report["analysis"]["active_tick_average_ms"]["decision"]
    report["all_pairs_exact_parity"] = all(pair["exact_parity_with_vanilla"] for pair in report["pairs"])
    report["status"] = "complete"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "analysis": report["analysis"], "report": str(report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if ACTIVE_REPORT_PATH is not None and ACTIVE_REPORT_PATH.is_file():
            try:
                failed_report = json.loads(ACTIVE_REPORT_PATH.read_text(encoding="utf-8"))
                failed_report["status"] = "failed"
                failed_report["failure"] = str(error)
                ACTIVE_REPORT_PATH.write_text(
                    json.dumps(failed_report, indent=2) + "\n", encoding="utf-8"
                )
            except (OSError, json.JSONDecodeError):
                pass
        print(f"Sustained selective-macro benchmark failed: {error}", file=sys.stderr)
        raise
