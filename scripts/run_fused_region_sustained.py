#!/usr/bin/env python3
"""Measure a sustained adjacent-eligible fused-region workload on Minecraft 26.3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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


FIXTURE = ROOT / "tests/fixtures/function_compiler_fused_sustained"
OUTPUT_ROOT = ROOT / "build/benchmarks/PERF-FUSED-SUSTAINED"
RUN_ROOT = ROOT / "run"
HOST = "127.0.0.1"
ADD_COMMAND = "scoreboard players add #fused fc_fused 1"
STACK_CHOICES = ("fabric", "lb113", "lbm113", "lbm113120")
IDLE_TICKS = 110
WARMUP_ACTIVE_TICKS = 110
TICKS_PER_WINDOW = 110
MEASUREMENT_WINDOWS = 5
IDLE_WINDOWS = 3
TICK_QUERY_WINDOW = 100
DEFAULT_STACK = "fabric"
DEFAULT_MINIMUM_GAIN_PERCENT = 15.0
FUSED_REGIONS_PER_ACTIVE_TICK = 1
ACTIVE_REPORT_PATH: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def adjacent_adds_per_tick() -> int:
    """Count the pristine contiguous eligible adds in the fixture tick function."""
    tick_function = FIXTURE / "data/function_compiler_fused_sustained/function/tick.mcfunction"
    lines = [line.strip() for line in tick_function.read_text(encoding="utf-8").splitlines()]
    commands = [line for line in lines if line]
    if not commands or any(line != ADD_COMMAND for line in commands):
        raise RuntimeError(
            f"Fixture tick function is no longer a contiguous block of {ADD_COMMAND!r}"
        )
    return len(commands)


ADDS_PER_TICK = adjacent_adds_per_tick()


def generated_files(adds_per_tick: int = ADDS_PER_TICK) -> dict[str, str]:
    """Generate the tick instrumentation that gates and counts the fixture workload.

    The pristine contiguous add block stays untouched inside
    `function_compiler_fused_sustained:tick`; the generated wrapper only counts
    ticks and conditionally invokes it, mirroring the sustained macro fixture's
    enable gate. When ``--adds-per-tick`` requests a larger block, a generated
    workload function supplies it instead.
    """
    if adds_per_tick == ADDS_PER_TICK:
        workload_function = "function_compiler_fused_sustained:tick"
        files: dict[str, str] = {}
    else:
        workload_function = "function_compiler_fused_sustained:tick_scaled"
        files = {
            "data/function_compiler_fused_sustained/function/tick_scaled.mcfunction":
                "".join(f"{ADD_COMMAND}\n" for _ in range(adds_per_tick))
        }
    instrumented = (
        "scoreboard players add #server_ticks fc_fused 1\n"
        "execute if score #enabled fc_fused matches 1 run "
        f"function {workload_function}\n"
        "execute if score #enabled fc_fused matches 1 run "
        "scoreboard players add #active_ticks fc_fused 1\n"
    )
    tag = {
        "replace": True,
        "values": ["function_compiler_fused_sustained:tick_instrumented"],
    }
    files.update(
        {
            "data/function_compiler_fused_sustained/function/tick_instrumented.mcfunction": instrumented,
            "data/minecraft/tags/function/tick.json": json.dumps(tag, indent=2) + "\n",
        }
    )
    return files


def generated_hashes(adds_per_tick: int = ADDS_PER_TICK) -> dict[str, str]:
    return {
        relative: hashlib.sha256(contents.encode("utf-8")).hexdigest()
        for relative, contents in generated_files(adds_per_tick).items()
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
        bot = PlayerBot("FCFused", HOST, server_port, packet_ids)
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
    response = rcon.command(f"scoreboard players get {holder} fc_fused")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not read #{holder} fc_fused: {response!r}")
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


def median_window(windows: list[dict[str, float]]) -> dict[str, float]:
    """Take the per-label median across sampled tick-query windows."""
    if not windows:
        raise RuntimeError("No tick query windows were sampled")
    labels = sorted(windows[0])
    return {
        label: round(statistics.median(window[label] for window in windows), 6)
        for label in labels
    }


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
    candidate = mode == "fused"
    environment.update(
        {
            # The candidate arm mirrors the runtime probe's canonical
            # fused-interpreted mode: specialization active (it supplies the
            # fusable commands) plus region fusion, with metrics/timers off.
            "FC_WRAPPER_PROBE": str(candidate).lower(),
            "FC_SCORE_ADD_PROTOTYPE": str(candidate).lower(),
            "FC_SCORE_ADD_METRICS": str(candidate and diagnostic).lower(),
            "FC_SCORE_ADD_TIMING": "false",
            "FC_FUSED_REGION_PROTOTYPE": str(candidate).lower(),
            "FC_BYTECODE_REGION_PROTOTYPE": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": "false",
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
    adds_per_tick: int = ADDS_PER_TICK,
) -> Path:
    world = work / "world"
    datapack_dir = world / "datapacks" / FIXTURE.name
    shutil.copytree(FIXTURE, datapack_dir)
    for relative, contents in generated_files(adds_per_tick).items():
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


def setup_fixture(rcon: DrainingRconClient, *, mode: str) -> str | None:
    enabled = rcon.command("datapack list enabled")
    if FIXTURE.name not in enabled:
        raise RuntimeError(f"Sustained fused fixture did not load: {enabled!r}")
    rcon.command("gamerule doMobSpawning false")
    rcon.command("gamerule doDaylightCycle false")
    rcon.command("gamerule randomTickSpeed 0")
    rcon.command("forceload add 0 0 15 15")
    rcon.command("scoreboard players set #enabled fc_fused 0")
    rcon.command("scoreboard players set #server_ticks fc_fused 0")
    rcon.command("scoreboard players set #active_ticks fc_fused 0")
    rcon.command("scoreboard players set #fused fc_fused 0")
    rcon.command("scoreboard players get #fused fc_fused")
    compiler_status = None
    if mode != "vanilla":
        compiler_status = rcon.command("function_compiler_probe status")
        expected_wrapper = mode == "fused"
        expected_fused = mode == "fused"
        for label, expected in (
            ("wrapper_enabled", expected_wrapper),
            ("score_add_prototype_enabled", expected_fused),
            ("fused_region_prototype_enabled", expected_fused),
            ("bytecode_region_prototype_enabled", False),
            ("selective_macro_arguments_enabled", False),
        ):
            if f"{label}={str(expected).lower()}" not in compiler_status:
                raise RuntimeError(f"{mode} arm has wrong {label}: {compiler_status!r}")
    return compiler_status


def read_status_counts(status: str, label: str) -> int:
    match = re.search(rf"{label}=(\d+)", status)
    if match is None:
        raise RuntimeError(f"Diagnostic omitted {label}: {status!r}")
    return int(match.group(1))


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
    adds_per_tick: int = ADDS_PER_TICK,
) -> dict[str, object]:
    work = RUN_ROOT / f"fused-{run_id}-{arm_name}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    server_port, rcon_port = reserve_ports(2)
    password = f"fc-fused-{os.getpid()}-{arm_name}"
    prepare_workdir(
        work,
        mode=mode,
        stack=stack,
        server_port=server_port,
        rcon_port=rcon_port,
        password=password,
        adds_per_tick=adds_per_tick,
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
        rcon.command("gamemode spectator FCFused")
        rcon.command("tp FCFused 4 100 4")
        compiler_status = setup_fixture(rcon, mode=mode)

        server_tick_start = score(rcon, "#server_ticks")
        wait_for_score(
            server,
            rcon,
            "#server_ticks",
            server_tick_start + IDLE_TICKS,
        )
        idle_tick_query = rcon.command("tick query")
        idle_timings = tick_metrics(idle_tick_query)
        rcon.command("scoreboard players set #enabled fc_fused 1")
        active_ticks_observed = wait_for_score(
            server,
            rcon,
            "#active_ticks",
            WARMUP_ACTIVE_TICKS,
            timeout_seconds=600,
        )
        # Sample several full tick-query windows so a single GC pause or JIT
        # hiccup cannot define the arm's measurement. Each window covers 110
        # active ticks while the /tick query summary spans its last 100.
        active_windows: list[dict[str, float]] = []
        active_started = time.monotonic()
        for _ in range(MEASUREMENT_WINDOWS):
            window_start = score(rcon, "#active_ticks")
            active_ticks_observed = wait_for_score(
                server,
                rcon,
                "#active_ticks",
                window_start + TICKS_PER_WINDOW,
                timeout_seconds=600,
            )
            active_windows.append(tick_metrics(rcon.command("tick query")))
        query_elapsed = time.monotonic() - active_started
        active_timings = median_window(active_windows)
        rcon.command("scoreboard players set #enabled fc_fused 0")
        idle_windows: list[dict[str, float]] = []
        for _ in range(IDLE_WINDOWS):
            idle_mark = score(rcon, "#server_ticks")
            wait_for_score(
                server,
                rcon,
                "#server_ticks",
                idle_mark + IDLE_TICKS,
            )
            idle_windows.append(tick_metrics(rcon.command("tick query")))
        post_idle_timings = median_window(idle_windows)
        fused_total = score(rcon, "#fused")
        server_ticks = score(rcon, "#server_ticks")
        ticks = score(rcon, "#active_ticks")
        expected_adds = ticks * adds_per_tick
        if fused_total != expected_adds:
            raise RuntimeError(
                f"Workload integrity failed: active_ticks={ticks}, fused={fused_total}, "
                f"expected fused={expected_adds} ({adds_per_tick} adds per active tick)"
            )
        activation = None
        if diagnostic:
            status_after = rcon.command("function_compiler_probe status")
            regions_compiled = read_status_counts(status_after, "fused_regions_compiled")
            regions_executed = read_status_counts(status_after, "fused_regions_executed")
            expected_regions = ticks * FUSED_REGIONS_PER_ACTIVE_TICK
            if mode == "fused" and (
                regions_compiled < 1 or regions_executed != expected_regions
            ):
                raise RuntimeError(
                    f"Fused region activation mismatch: compiled={regions_compiled}, "
                    f"executed={regions_executed}, active_ticks={ticks}, "
                    f"expected executed={expected_regions}"
                )
            score_add_executed = read_status_counts(status_after, "score_add_executed")
            expected_region_adds = ticks * adds_per_tick
            if mode == "fused" and score_add_executed < expected_region_adds:
                raise RuntimeError(
                    f"Specialized commands did not execute inside the region: "
                    f"score_add_executed={score_add_executed}, "
                    f"expected at least {expected_region_adds}"
                )
            activation = {
                "fused_regions_compiled": regions_compiled,
                "fused_regions_executed": regions_executed,
                "expected_fused_region_executions": expected_regions,
                "fused_regions_per_active_tick": FUSED_REGIONS_PER_ACTIVE_TICK,
                "exact": regions_executed == expected_regions if mode == "fused" else None,
                "score_add_compiled": read_status_counts(status_after, "score_add_compiled"),
                "score_add_executed": score_add_executed,
            }

        if server.poll() is not None:
            raise RuntimeError(f"Minecraft exited during arm {arm_name}")
        rcon.command("stop")
        server.wait(timeout=60)
        state = {
            "active_ticks": ticks,
            "server_ticks": server_ticks,
            "adds_applied": fused_total,
            "adds_per_active_tick": fused_total / ticks,
            "expected_adds_per_active_tick": adds_per_tick,
            "exact_workload_integrity": fused_total == expected_adds,
            "workload_tick_average_ms": round(
                active_timings["tick_average_ms"] - post_idle_timings["tick_average_ms"], 6
            ),
        }
        return {
            "arm": arm_name,
            "mode": mode,
            "stack": stack if mode != "vanilla" else "mod-free-vanilla",
            "diagnostic_only": diagnostic,
            "instrumentation": (
                "fused region counters enabled" if diagnostic else "no Spark; no compiler counters or timers"
            ),
            "warmup_active_ticks": WARMUP_ACTIVE_TICKS,
            "active_tick_threshold_observed": active_ticks_observed,
            "active_tick_count_at_stop": ticks,
            "idle_ticks_before_workload": IDLE_TICKS,
            "tick_query_window_ticks": TICK_QUERY_WINDOW,
            "measurement_windows": MEASUREMENT_WINDOWS,
            "pre_workload_settle_tick_timings_ms": idle_timings,
            "active_window_timings_ms": active_windows,
            "post_workload_idle_window_timings_ms": idle_windows,
            "post_workload_idle_tick_timings_ms": post_idle_timings,
            "active_tick_timings_ms": active_timings,
            "workload_attributable_tick_average_ms": round(
                active_timings["tick_average_ms"] - post_idle_timings["tick_average_ms"], 6
            ),
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
    parser.add_argument("--stack", choices=STACK_CHOICES, default=DEFAULT_STACK)
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=26871041)
    parser.add_argument(
        "--adds-per-tick",
        type=int,
        default=None,
        help=(
            "size of the contiguous eligible add block; defaults to the checked-in "
            f"fixture's {ADDS_PER_TICK} adds"
        ),
    )
    parser.add_argument("--phase", choices=("screening", "confirmatory"), default="screening")
    parser.add_argument(
        "--minimum-gain-percent",
        type=float,
        default=DEFAULT_MINIMUM_GAIN_PERCENT,
        help="predeclared worthwhile active-tick-average improvement; default 15%%",
    )
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("--pairs must be at least 1")
    if args.phase == "confirmatory" and args.pairs < 6:
        parser.error("confirmatory campaigns require at least six pairs")
    if args.minimum_gain_percent <= 0:
        parser.error("--minimum-gain-percent must be positive")
    if args.adds_per_tick is not None and args.adds_per_tick < 2:
        parser.error("--adds-per-tick must be at least 2 (fusion requires adjacent pairs)")
    return args


def main() -> int:
    args = parse_args()
    adds_per_tick = args.adds_per_tick if args.adds_per_tick is not None else ADDS_PER_TICK
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
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = OUTPUT_ROOT / f"{args.stack}-{args.phase}-{args.pairs}pairs-{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "results.json"
    global ACTIVE_REPORT_PATH
    ACTIVE_REPORT_PATH = report_path
    report: dict[str, object] = {
        "benchmark": "PERF-016",
        "minecraft": "26.3",
        "server_sha256": sha256(server_jar),
        "stack": args.stack,
        "mods": mods,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "fixture_sha256": fixture_hashes,
        "generated_sha256": generated_hashes(adds_per_tick),
        "runner_sha256": sha256(Path(__file__).resolve()),
        "candidate": "fused-interpreted",
        "metric": "workload_tick_average_ms",
        "metric_definition": (
            "active-phase /tick query average minus the same server's post-workload "
            "idle /tick query average; isolates the workload's marginal tick cost "
            "from fixed server overhead"
        ),
        "minimum_gain_percent": args.minimum_gain_percent,
        "decision_rule": "95% exact paired median interval must support at least the preselected gain",
        "phase": args.phase,
        "pairs_requested": args.pairs,
        "random_seed": args.seed,
        "configuration": {
            "adjacent_eligible_adds_per_active_tick": adds_per_tick,
            "fused_regions_per_active_tick": FUSED_REGIONS_PER_ACTIVE_TICK,
            "warmup_active_ticks": WARMUP_ACTIVE_TICKS,
            "measurement_windows_per_arm": MEASUREMENT_WINDOWS,
            "active_ticks_per_window": TICKS_PER_WINDOW,
            "idle_windows_per_arm": IDLE_WINDOWS,
            "arm_aggregate": "per-label median across sampled tick-query windows",
            "idle_ticks_before_workload": IDLE_TICKS,
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
        adds_per_tick=adds_per_tick,
    )
    report["vanilla_reference"] = vanilla
    report["arms"].append(vanilla)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not vanilla["state"]["exact_workload_integrity"]:
        raise RuntimeError("Vanilla workload integrity failed")

    diagnostic = run_arm(
        run_id=run_id,
        arm_name="activation-diagnostic",
        mode="fused",
        stack=args.stack,
        server_jar=server_jar,
        packet_ids=packet_ids,
        output_dir=output_dir,
        diagnostic=True,
        adds_per_tick=adds_per_tick,
    )
    report["activation_diagnostic"] = diagnostic
    report["arms"].append(diagnostic)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not diagnostic["activation_diagnostic"]["exact"]:
        raise RuntimeError("Fused region activation diagnostic did not count every eligible region")

    rng = random.Random(args.seed)
    pair_orders = [["off", "fused"] for _ in range(args.pairs // 2)]
    pair_orders.extend([["fused", "off"] for _ in range(args.pairs // 2)])
    if args.pairs % 2:
        pair_orders.append(["off", "fused"] if rng.randrange(2) == 0 else ["fused", "off"])
    rng.shuffle(pair_orders)
    for pair_index in range(1, args.pairs + 1):
        order = pair_orders[pair_index - 1]
        pair_arms: dict[str, dict[str, object]] = {}
        print(f"Starting sustained fused pair {pair_index}/{args.pairs}: {order}", flush=True)
        for label in order:
            arm = run_arm(
                run_id=run_id,
                arm_name=f"pair-{pair_index:02d}-{label}",
                mode=label,
                stack=args.stack,
                server_jar=server_jar,
                packet_ids=packet_ids,
                output_dir=output_dir,
                adds_per_tick=adds_per_tick,
            )
            pair_arms[label] = arm
            report["arms"].append(arm)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        vanilla_rate = vanilla["state"]["adds_per_active_tick"]
        parity = all(
            arm["state"]["adds_per_active_tick"] == vanilla_rate
            and arm["state"]["exact_workload_integrity"]
            for arm in pair_arms.values()
        )
        pair = {
            "repetition": pair_index,
            "order": order,
            "off": {
                "tick_average_ms": pair_arms["off"]["active_tick_timings_ms"]["tick_average_ms"],
                "workload_tick_average_ms": pair_arms["off"]["state"]["workload_tick_average_ms"],
                "tick_p95_ms": pair_arms["off"]["active_tick_timings_ms"]["tick_p95_ms"],
            },
            "fused": {
                "tick_average_ms": pair_arms["fused"]["active_tick_timings_ms"]["tick_average_ms"],
                "workload_tick_average_ms": pair_arms["fused"]["state"]["workload_tick_average_ms"],
                "tick_p95_ms": pair_arms["fused"]["active_tick_timings_ms"]["tick_p95_ms"],
            },
            "exact_parity_with_vanilla": parity,
        }
        report["pairs"].append(pair)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not parity:
            raise RuntimeError(f"Pair {pair_index} differs from vanilla workload counts")

    primary_changes = paired_percent_changes(
        report["pairs"],
        metric="workload_tick_average_ms",
        baseline_arm="off",
        candidate_arm="fused",
    )
    report["analysis"] = {
        "workload_tick_average_ms": summarize_paired_changes(
            primary_changes,
            minimum_gain_percent=args.minimum_gain_percent if args.phase == "confirmatory" else None,
        ),
        "active_tick_average_ms": summarize_paired_changes(
            paired_percent_changes(
                report["pairs"],
                metric="tick_average_ms",
                baseline_arm="off",
                candidate_arm="fused",
            )
        ),
        "active_tick_p95_ms": summarize_paired_changes(
            paired_percent_changes(
                report["pairs"],
                metric="tick_p95_ms",
                baseline_arm="off",
                candidate_arm="fused",
            )
        ),
    }
    report["performance_decision"] = report["analysis"]["workload_tick_average_ms"]["decision"]
    report["no_regression_decision"] = report["analysis"]["workload_tick_average_ms"][
        "no_regression_decision"
    ]
    report["all_pairs_exact_parity"] = all(pair["exact_parity_with_vanilla"] for pair in report["pairs"])
    report["status"] = "complete"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "analysis": report["analysis"], "report": str(report_path)}, indent=2))
    print(
        f"performance_decision={report['performance_decision']} "
        f"no_regression_decision={report['no_regression_decision']}",
        flush=True,
    )
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
        print(f"Sustained fused-region benchmark failed: {error}", file=sys.stderr)
        raise
