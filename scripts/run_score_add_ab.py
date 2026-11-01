#!/usr/bin/env python3
"""Compare the literal fake-holder ScoreAdd prototype with vanilla execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "runtime"))

from run_dynamic_lights_profile import spark_thread_node_count  # noqa: E402
from run_runtime_probe import (  # noqa: E402
    RconClient,
    SERVER_JAR_SHA256,
    generate_packet_ids,
    locate_official_server_jar,
)
from player_bot import PacketIds, PlayerBot  # noqa: E402
from run_spawn_animations_profile import (  # noqa: E402
    free_port,
    start_spark_shell,
    stop_spark_shell,
    wait_for_rcon,
    wait_for_spark_password,
)


OUTPUT_DIR = ROOT / "build" / "benchmarks" / "PERF-002"
RUN_ROOT = ROOT / "run"
SPARK_AGENT = (
    ROOT
    / "references"
    / "real-world"
    / "spark-1.10.194"
    / "spark-1.10.194-standalone-agent.jar"
)
SPARK_SHA256 = "a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9"
FUNCTION_LINES = 5_000
PROFILE_CALLS_PER_TICK = 10
BENCH_OBJECTIVE = "fc_perf"
BENCH_HOLDER = "#fcperf"
BENCH_FUNCTION = "function_compiler_perf:scoreboard"
LEVEL_RULE = "minecraft:max_command_sequence_length"
JVM_ARGS = ("-Xms512M", "-Xmx2G")
MODES = (
    "vanilla", "fabric-off", "wrapper-only", "score-add-on", "fused-interpreted",
    "bytecode-emitted",
)
TIMING_MODES = ("instrument-only", "score-add-timed")
FUNCTION_TIMING_MODES = (
    "function-instrument-only",
    "function-score-add-timed",
    "function-fused-timed",
)
BACKEND_TIMING_MODES = (
    *FUNCTION_TIMING_MODES,
    "function-bytecode-timed",
)
ALL_FUNCTION_TIMING_MODES = set(BACKEND_TIMING_MODES)
SERVER_HOST = "127.0.0.1"
RCON_PASSWORD_PREFIX = "fc-perf-002-"


class PortBindError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def java_version() -> str:
    result = subprocess.run(
        ["java", "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    return result.stdout.strip()


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * fraction) - 1]


def interpolated_quantile(values: list[float], fraction: float) -> float:
    """Linear-interpolated quantile, reported alongside raw trial values."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def prepare_fixture(work: Path, rcon_port: int, server_port: int, password: str) -> str:
    datapack_root = (
        work
        / "world"
        / "datapacks"
        / "function_compiler_perf"
    )
    function_path = (
        datapack_root
        / "data"
        / "function_compiler_perf"
        / "function"
        / "scoreboard.mcfunction"
    )
    function_path.parent.mkdir(parents=True, exist_ok=True)
    function_path.write_text(
        "".join(
            f"scoreboard players add {BENCH_HOLDER} {BENCH_OBJECTIVE} 1\n"
            for _ in range(FUNCTION_LINES)
        ),
        encoding="utf-8",
    )
    profile_tick_path = (
        datapack_root
        / "data"
        / "function_compiler_perf"
        / "function"
        / "profile_tick.mcfunction"
    )
    profile_tick_path.write_text(
        "execute if data storage function_compiler_perf:profile running "
        "run scoreboard players add #profile_ticks fc_perf 1\n"
        + "".join(
            "execute if data storage function_compiler_perf:profile running "
            f"run function {BENCH_FUNCTION}\n"
            for _ in range(PROFILE_CALLS_PER_TICK)
        ),
        encoding="utf-8",
    )
    tick_tag_path = datapack_root / "data" / "minecraft" / "tags" / "function" / "tick.json"
    tick_tag_path.parent.mkdir(parents=True, exist_ok=True)
    tick_tag_path.write_text(
        json.dumps({"values": ["function_compiler_perf:profile_tick"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    (datapack_root / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "Function Compiler PERF-002 fixed ScoreAdd workload",
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
        "rcon.password": password,
        "rcon.port": str(rcon_port),
        "broadcast-rcon-to-ops": "false",
        "server-ip": SERVER_HOST,
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
    return sha256(function_path)


def start_server(
    mode: str,
    work: Path,
    server_jar: Path,
    spark_port: int,
    log_path: Path,
) -> tuple[subprocess.Popen[bytes], object]:
    log_handle = log_path.open("wb")
    if mode == "vanilla":
        command = [
            "java",
            *JVM_ARGS,
            f"-javaagent:{SPARK_AGENT}=port={spark_port}",
            "-jar",
            str(server_jar),
            "nogui",
        ]
        cwd = work
        environment = None
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
                "FC_WRAPPER_PROBE": "true" if mode in {
                    "wrapper-only", "score-add-on", "instrument-only", "score-add-timed",
                    "fused-interpreted", "bytecode-emitted", *BACKEND_TIMING_MODES,
                } else "false",
                "FC_SCORE_ADD_PROTOTYPE": "true" if mode in {
                    "score-add-on", "score-add-timed", "fused-interpreted",
                    "bytecode-emitted", "function-score-add-timed", "function-fused-timed",
                    "function-bytecode-timed",
                } else "false",
                "FC_FUSED_REGION_PROTOTYPE": "true" if mode in {
                    "fused-interpreted", "function-fused-timed"
                } else "false",
                "FC_BYTECODE_REGION_PROTOTYPE": "true" if mode in {
                    "bytecode-emitted", "function-bytecode-timed"
                } else "false",
                "FC_SCORE_ADD_TIMING": "true" if mode in TIMING_MODES else "false",
                "FC_FUNCTION_TIMING": "true" if mode in ALL_FUNCTION_TIMING_MODES else "false",
                # Per-command counters are useful in the correctness suite, but
                # would add AtomicLong work to only the optimized arm here.
                "FC_SCORE_ADD_METRICS": "false",
                "FC_RUNTIME_TRACE": "false",
            }
        )
        command = [str(ROOT / "gradlew"), "--no-daemon"]
        if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
            command.append("--offline")
        command.extend(
            [
                f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
                f"-PfcJvmArgs={','.join(JVM_ARGS)}",
                f"-PfcSparkAgentPath={SPARK_AGENT}",
                f"-PfcSparkPort={spark_port}",
                "runServer",
            ]
        )
        cwd = ROOT
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def connect_perf_player(packet_ids: PacketIds, port: int) -> PlayerBot:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        bot = PlayerBot("FCPerf", SERVER_HOST, port, packet_ids)
        try:
            return bot.connect()
        except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
            bot.close()
            last_error = error
            if attempt < 3:
                time.sleep(1)
    raise RuntimeError(f"Headless player failed to connect after 3 attempts: {last_error}")


def score_value(client: RconClient) -> int:
    response = client.command(
        f"scoreboard players get {BENCH_HOLDER} {BENCH_OBJECTIVE}"
    )
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not parse benchmark scoreboard value: {response!r}")
    return int(match.group(1))


def status_integer(response: str, field: str) -> int:
    match = re.search(rf"{re.escape(field)}=(\d+)", response)
    if match is None:
        raise RuntimeError(f"Probe status omitted {field}: {response!r}")
    return int(match.group(1))


def scoreboard_value(client: RconClient, holder: str) -> int:
    response = client.command(f"scoreboard players get {holder} {BENCH_OBJECTIVE}")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not parse benchmark scoreboard value: {response!r}")
    return int(match.group(1))


def wait_for_stable_scoreboard_value(
    client: RconClient,
    holder: str,
    stable_samples: int = 3,
    timeout_seconds: float = 15.0,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    previous: int | None = None
    stable = 0
    current = 0
    while time.monotonic() < deadline:
        current = scoreboard_value(client, holder)
        if current == previous:
            stable += 1
            if stable >= stable_samples:
                return current
        else:
            previous = current
            stable = 0
        time.sleep(0.1)
    raise TimeoutError(
        f"Scoreboard value for {holder} did not stabilize; last value {current}"
    )


def wait_for_score(client: RconClient, expected: int, timeout_seconds: float = 30.0) -> int:
    deadline = time.monotonic() + timeout_seconds
    actual = score_value(client)
    while actual != expected and time.monotonic() < deadline:
        if actual > expected:
            raise RuntimeError(
                f"Benchmark score advanced past expected value {expected}: {actual}"
            )
        time.sleep(0.1)
        actual = score_value(client)
    if actual != expected:
        raise TimeoutError(
            f"Benchmark score did not reach {expected} within {timeout_seconds}s; got {actual}"
        )
    return actual


def run_function(client: RconClient, mode: str) -> str:
    response = client.command(f"function {BENCH_FUNCTION}")
    if not response.startswith("Running function "):
        raise RuntimeError(f"Benchmark function did not run: {response!r}")
    return response


def read_prototype_status(client: RconClient, mode: str) -> dict[str, object] | None:
    if mode == "vanilla":
        return None
    response = client.command("function_compiler_probe status")
    expected_wrapper = mode in {
        "wrapper-only", "score-add-on", "instrument-only", "score-add-timed",
        "fused-interpreted", "bytecode-emitted", *BACKEND_TIMING_MODES,
    }
    expected_prototype = mode in {
        "score-add-on", "score-add-timed", "fused-interpreted",
        "bytecode-emitted", "function-score-add-timed", "function-fused-timed",
        "function-bytecode-timed",
    }
    expected_fused = mode in {"fused-interpreted", "function-fused-timed"}
    expected_bytecode = mode in {"bytecode-emitted", "function-bytecode-timed"}
    expected_timing = mode in TIMING_MODES
    expected_function_timing = mode in ALL_FUNCTION_TIMING_MODES
    if f"function_timing_enabled={str(expected_function_timing).lower()}" not in response:
        raise RuntimeError(
            f"{mode} function timing flag mismatch in probe status: {response!r}"
        )
    for key, expected in (
        ("wrapper_enabled", expected_wrapper),
        ("score_add_prototype_enabled", expected_prototype),
        ("score_add_timing_enabled", expected_timing),
        ("fused_region_prototype_enabled", expected_fused),
        ("bytecode_region_prototype_enabled", expected_bytecode),
    ):
        if f"{key}={str(expected).lower()}" not in response:
            raise RuntimeError(f"{mode} status mismatch for {key}: {response!r}")
    if "score_add_metrics_enabled=false" not in response:
        raise RuntimeError(
            "Runtime status must expose disabled ScoreAdd metrics during benchmarking; "
            f"got {response!r}"
        )
    compiled_match = re.search(r"score_add_compiled=(\d+)", response)
    executed_match = re.search(r"score_add_executed=(\d+)", response)
    if compiled_match is None or executed_match is None:
        raise RuntimeError(f"ScoreAdd counters missing from status: {response!r}")
    compiled = int(compiled_match.group(1))
    executed = int(executed_match.group(1))
    if expected_prototype or expected_timing:
        if compiled < FUNCTION_LINES:
            raise RuntimeError(
                f"{mode} prepared only {compiled} ScoreAdd entries; expected at least {FUNCTION_LINES}"
            )
    elif compiled != 0:
        raise RuntimeError(f"Unexpected ScoreAdd instrumentation in {mode}: {compiled}")
    if executed != 0:
        raise RuntimeError(f"ScoreAdd hot-path metrics were not disabled: {executed}")
    fused_compiled = status_integer(response, "fused_regions_compiled")
    fused_executed = status_integer(response, "fused_regions_executed")
    if expected_fused and fused_compiled < 1:
        raise RuntimeError(f"{mode} did not compile any fused regions: {response!r}")
    if not expected_fused and (fused_compiled or fused_executed):
        raise RuntimeError(f"{mode} unexpectedly compiled/executed fused regions: {response!r}")
    if fused_executed != 0:
        raise RuntimeError(
            "Fused-region execution metrics must be disabled during timed trials; "
            f"got {fused_executed}"
        )
    bytecode_compiled = status_integer(response, "bytecode_regions_compiled")
    bytecode_failed = status_integer(response, "bytecode_regions_compile_failed")
    bytecode_executed = status_integer(response, "bytecode_regions_executed")
    if expected_bytecode and (bytecode_compiled < 1 or bytecode_failed != 0):
        raise RuntimeError(
            f"{mode} failed bytecode region compilation: compiled={bytecode_compiled}, "
            f"failed={bytecode_failed}; status={response!r}"
        )
    if not expected_bytecode and (bytecode_compiled or bytecode_failed or bytecode_executed):
        raise RuntimeError(f"{mode} unexpectedly used the bytecode backend: {response!r}")
    timed_calls_match = re.search(r"score_add_timed_calls=(\d+)", response)
    elapsed_match = re.search(r"score_add_elapsed_nanos=(\d+)", response)
    if timed_calls_match is None or elapsed_match is None:
        raise RuntimeError(f"ScoreAdd timing counters missing from status: {response!r}")
    return {
        "wrapper_enabled": expected_wrapper,
        "score_add_prototype_enabled": expected_prototype,
        "score_add_timing_enabled": expected_timing,
        "function_timing_enabled": expected_function_timing,
        "score_add_metrics_enabled": False,
        "score_add_compiled": compiled,
        "score_add_executed_metric": executed,
        "fused_region_prototype_enabled": expected_fused,
        "fused_regions_compiled": fused_compiled,
        "fused_regions_executed_metric": fused_executed,
        "bytecode_regions_compiled": bytecode_compiled,
        "bytecode_regions_compile_failed": bytecode_failed,
        "bytecode_regions_executed_metric": bytecode_executed,
        "score_add_timed_calls": int(timed_calls_match.group(1)),
        "score_add_elapsed_nanos": int(elapsed_match.group(1)),
        "function_timed_calls": status_integer(response, "function_timed_calls"),
        "function_elapsed_nanos": status_integer(response, "function_elapsed_nanos"),
        "raw": response,
    }


def capture_spark_profile(
    mode: str,
    profile_kind: str,
    profile_seconds: int,
    work: Path,
    output_dir: Path,
    log_path: Path,
    process: subprocess.Popen[bytes],
    client: RconClient,
    spark_port: int,
) -> dict[str, object]:
    password = wait_for_spark_password(log_path, process)
    shell = start_spark_shell(work, password, spark_port)
    try:
        assert shell.stdin is not None
        if profile_kind == "cpu":
            command = "spark profiler start --interval 4 --thread *\n"
        elif profile_kind == "alloc":
            command = "spark profiler start --alloc --interval 524287\n"
        else:
            raise ValueError(profile_kind)
        shell.stdin.write(command.encode("utf-8"))
        shell.stdin.flush()
        time.sleep(1)
        ticks_before = scoreboard_value(client, "#profile_ticks")
        score_before = score_value(client)
        client.command(
            "data modify storage function_compiler_perf:profile running set value 1b"
        )
        time.sleep(profile_seconds)
        client.command("data remove storage function_compiler_perf:profile running")
        ticks_after = wait_for_stable_scoreboard_value(client, "#profile_ticks")
        score_after = score_value(client)
        tick_delta = ticks_after - ticks_before
        calls = tick_delta * PROFILE_CALLS_PER_TICK
        expected_score_delta = calls * FUNCTION_LINES
        if tick_delta < 1:
            raise RuntimeError(f"Spark {profile_kind} capture completed no profile ticks")
        if score_after - score_before != expected_score_delta:
            raise RuntimeError(
                f"Spark {profile_kind} capture completed {tick_delta} profile ticks "
                f"({calls} expected functions), but scoreboard advanced by "
                f"{score_after - score_before}; expected {expected_score_delta}"
            )
        output = stop_spark_shell(shell)
        shell = None
    finally:
        if shell is not None and shell.poll() is None:
            try:
                if shell.stdin is not None:
                    shell.stdin.write(b"exit\n")
                    shell.stdin.flush()
                shell.communicate(timeout=10)
            except Exception:
                shell.kill()
                shell.wait(timeout=5)

    profiles = list(work.rglob("*.sparkprofile"))
    if not profiles:
        raise RuntimeError(
            f"Spark did not save its {profile_kind} profile; SSH output={output[-1600:]!r}"
        )
    source = max(profiles, key=lambda item: item.stat().st_mtime_ns)
    target = output_dir / f"{mode}-{profile_kind}.sparkprofile"
    shutil.copy2(source, target)
    nodes = spark_thread_node_count(target) if profile_kind == "cpu" else None
    if profile_kind == "cpu" and not nodes:
        raise RuntimeError(f"Spark CPU profile has no thread samples: {target}")
    return {
        "profile_kind": profile_kind,
        "profile_seconds": profile_seconds,
        "profile_tick_batches": tick_delta,
        "completed_function_calls": calls,
        "sampled_function_calls": calls,
        "completed_function_commands": expected_score_delta,
        "score_delta_verified": score_after - score_before,
        "spark_thread_nodes": nodes,
        "path": str(target.relative_to(ROOT)),
        "sha256": sha256(target),
        "bytes": target.stat().st_size,
    }


def run_trial(
    mode: str,
    repetition: int,
    warmup_calls: int,
    measured_calls: int,
    profile_seconds: int,
    capture_profiles: bool,
    server_jar: Path,
    packet_ids: PacketIds,
    fixture_sha256: str,
) -> dict[str, object]:
    trial_id = f"{mode}-r{repetition:02d}-{time.time_ns()}"
    work_root = RUN_ROOT
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"perf-002-{trial_id}-", dir=work_root) as temporary:
        work = Path(temporary)
        allocated_ports: list[int] = []
        while len(allocated_ports) < 3:
            candidate = free_port()
            if candidate not in allocated_ports:
                allocated_ports.append(candidate)
        server_port, rcon_port, spark_port = allocated_ports
        password = RCON_PASSWORD_PREFIX + str(time.time_ns())
        actual_fixture_hash = prepare_fixture(work, rcon_port, server_port, password)
        if actual_fixture_hash != fixture_sha256:
            raise RuntimeError("Fixture changed between independent trial preparations")
        log_path = work / "server.log"
        process, log_handle = start_server(mode, work, server_jar, spark_port, log_path)
        client: RconClient | None = None
        bot: PlayerBot | None = None
        started_at = time.monotonic()
        measured_ns: list[int] = []
        profile_records: list[dict[str, object]] = []
        try:
            client = wait_for_rcon(process, rcon_port, password, timeout=240)
            bot = connect_perf_player(packet_ids, server_port)
            bot.assert_connected()
            client.command("gamemode spectator FCPerf")
            datapacks = client.command("datapack list enabled")
            if "function_compiler_perf" not in datapacks:
                available = client.command("datapack list available")
                if "function_compiler_perf" not in available:
                    raise RuntimeError(
                        f"Fixed benchmark datapack is unavailable: {datapacks!r}; {available!r}"
                    )
                enabled = client.command("datapack enable file/function_compiler_perf")
                if "Unknown" in enabled or "Could not" in enabled:
                    raise RuntimeError(f"Could not enable fixed benchmark datapack: {enabled!r}")
                client.command("reload")
                time.sleep(1)
                datapacks = client.command("datapack list enabled")
                if "function_compiler_perf" not in datapacks:
                    raise RuntimeError(f"Benchmark datapack did not enable: {datapacks!r}")

            if mode != "vanilla":
                prototype_before = read_prototype_status(client, mode)
            else:
                prototype_before = None
            objective = client.command(f"scoreboard objectives add {BENCH_OBJECTIVE} dummy")
            if "Unknown" in objective or "Incorrect" in objective:
                raise RuntimeError(f"Could not create benchmark objective: {objective!r}")
            client.command("scoreboard players set #profile_ticks fc_perf 0")
            quota = client.command(f"gamerule {LEVEL_RULE} 65536")
            if "65536" not in quota:
                raise RuntimeError(f"Could not set benchmark command quota: {quota!r}")
            client.command(f"scoreboard players set {BENCH_HOLDER} {BENCH_OBJECTIVE} 0")
            run_function(client, mode)
            smoke_score = score_value(client)
            if smoke_score != FUNCTION_LINES:
                raise RuntimeError(
                    f"Smoke call score was {smoke_score}; expected {FUNCTION_LINES}"
                )
            client.command(f"scoreboard players set {BENCH_HOLDER} {BENCH_OBJECTIVE} 0")

            for _ in range(warmup_calls):
                run_function(client, mode)
            client.command("tick query")
            timing_before = (
                read_prototype_status(client, mode)
                if mode in (*TIMING_MODES, *BACKEND_TIMING_MODES)
                else None
            )
            started_measurement = time.perf_counter_ns()
            for _ in range(measured_calls):
                started = time.perf_counter_ns()
                run_function(client, mode)
                measured_ns.append(time.perf_counter_ns() - started)
            elapsed_ns = time.perf_counter_ns() - started_measurement
            expected_timing_score = FUNCTION_LINES * (warmup_calls + measured_calls)
            if mode != "vanilla":
                prototype_after = read_prototype_status(client, mode)
            else:
                prototype_after = None
            score_after_timing = wait_for_score(client, expected_timing_score)
            server_thread_timing = None
            if mode in TIMING_MODES:
                assert timing_before is not None and prototype_after is not None
                timed_calls = int(prototype_after["score_add_timed_calls"]) - int(
                    timing_before["score_add_timed_calls"]
                )
                elapsed_nanos = int(prototype_after["score_add_elapsed_nanos"]) - int(
                    timing_before["score_add_elapsed_nanos"]
                )
                expected_timed_calls = FUNCTION_LINES * measured_calls
                if timed_calls != expected_timed_calls:
                    raise RuntimeError(
                        f"{mode} timed {timed_calls} command callbacks; expected "
                        f"{expected_timed_calls} measured fixture actions"
                    )
                server_thread_timing = {
                    "timed_command_callbacks": timed_calls,
                    "elapsed_callback_nanos": elapsed_nanos,
                    "mean_callback_nanos": elapsed_nanos / timed_calls,
                    "scope": "server-thread time inside the command callback only",
                }
            elif mode in BACKEND_TIMING_MODES:
                assert timing_before is not None and prototype_after is not None
                timed_calls = int(prototype_after["function_timed_calls"]) - int(
                    timing_before["function_timed_calls"]
                )
                elapsed_nanos = int(prototype_after["function_elapsed_nanos"]) - int(
                    timing_before["function_elapsed_nanos"]
                )
                if timed_calls != measured_calls:
                    raise RuntimeError(
                        f"{mode} timed {timed_calls} function execution queues; "
                        f"expected {measured_calls}"
                    )
                server_thread_timing = {
                    "timed_function_executions": timed_calls,
                    "elapsed_function_nanos": elapsed_nanos,
                    "mean_function_execution_nanos": elapsed_nanos / timed_calls,
                    "scope": (
                        "server-thread time from FunctionCommand.queueFunctions for "
                        "the target fixture through ExecutionContext.runCommandQueue "
                        "return; includes instantiation and queue work, excludes "
                        "RCON and outer Brigadier command parsing"
                    ),
                }
            if capture_profiles:
                for profile_kind in ("cpu", "alloc"):
                    profile_records.append(
                        capture_spark_profile(
                            mode,
                            profile_kind,
                            profile_seconds,
                            work,
                            OUTPUT_DIR,
                            log_path,
                            process,
                            client,
                            spark_port,
                        )
                    )

            profile_calls = sum(
                int(record["sampled_function_calls"]) for record in profile_records
            )
            expected_final = FUNCTION_LINES * (
                warmup_calls + measured_calls + profile_calls
            )
            score_final = wait_for_score(client, expected_final)
            status_final = (
                read_prototype_status(client, mode) if mode != "vanilla" else None
            )
            tick_query = client.command("tick query")
            client.command("stop")
            process.wait(timeout=60)
        except Exception:
            if log_path.is_file():
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
                if "failed to bind to port" in log_text.casefold():
                    raise PortBindError("Minecraft could not bind its temporary server port")
                lines = log_text.splitlines()
                diagnostic_lines = [
                    line
                    for line in lines
                    if any(
                        token in line.casefold()
                        for token in ("error", "exception", "failed", "failure", "warn")
                    )
                ]
                if diagnostic_lines:
                    print("\n".join(diagnostic_lines[-25:]), file=sys.stderr)
            raise
        finally:
            if client is not None:
                client.close()
            if bot is not None:
                bot.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            log_handle.close()

        ordered = sorted(measured_ns)
        elapsed_seconds = elapsed_ns / 1_000_000_000
        return {
            "trial_id": trial_id,
            "mode": mode,
            "repetition": repetition,
            "server_started_to_stop_seconds": time.monotonic() - started_at,
            "fixture_sha256": actual_fixture_hash,
            "fixture_lines": FUNCTION_LINES,
            "warmup_calls": warmup_calls,
            "measured_calls": measured_calls,
            "measured_command_count": FUNCTION_LINES * measured_calls,
            "timing_metric": "RCON /function round trip; includes client/socket/dispatch overhead",
            "measured_elapsed_ns": elapsed_ns,
            "measured_calls_per_second": measured_calls / elapsed_seconds,
            "measured_function_commands_per_second": (
                FUNCTION_LINES * measured_calls / elapsed_seconds
            ),
            "rcon_round_trip_median_ns": ordered[len(ordered) // 2],
            "rcon_round_trip_p95_ns": percentile(measured_ns, 0.95),
            "rcon_round_trip_p99_ns": percentile(measured_ns, 0.99),
            "rcon_round_trip_samples_ns": measured_ns,
            "smoke_score": smoke_score,
            "score_after_timing": score_after_timing,
            "expected_score_after_timing": expected_timing_score,
            "final_score": score_final,
            "expected_final_score": expected_final,
            "profile_calls": profile_calls,
            "prototype_status_before": prototype_before,
            "prototype_status_after_timing": prototype_after,
            "server_thread_timing": server_thread_timing,
            "prototype_status_final": status_final,
            "spark_profiles": profile_records,
            "server_tick_query_after_profile": tick_query,
        }


def summarize(
    results: list[dict[str, object]],
    modes: tuple[str, ...] = MODES,
    baseline_mode: str = "vanilla",
) -> dict[str, object]:
    summary: dict[str, object] = {}
    for mode in modes:
        trials = [record for record in results if record["mode"] == mode]
        rates = [float(record["measured_function_commands_per_second"]) for record in trials]
        medians = [int(record["rcon_round_trip_median_ns"]) for record in trials]
        median_rate = float(statistics.median(rates))
        median_rcon = int(statistics.median(medians))
        summary[mode] = {
            "independent_trials": len(trials),
            "function_commands_per_second_by_trial": rates,
            "median_function_commands_per_second": median_rate,
            "function_commands_per_second_min": min(rates),
            "function_commands_per_second_max": max(rates),
            "function_commands_per_second_iqr": (
                interpolated_quantile(rates, 0.75) - interpolated_quantile(rates, 0.25)
            ),
            "function_commands_per_second_mad": float(
                statistics.median([abs(rate - median_rate) for rate in rates])
            ),
            "rcon_median_ns_by_trial": medians,
            "median_rcon_round_trip_ns": median_rcon,
            "rcon_median_min_ns": min(medians),
            "rcon_median_max_ns": max(medians),
            "rcon_median_iqr_ns": (
                interpolated_quantile([float(value) for value in medians], 0.75)
                - interpolated_quantile([float(value) for value in medians], 0.25)
            ),
            "rcon_median_mad_ns": int(
                statistics.median([abs(value - median_rcon) for value in medians])
            ),
            "score_verified_each_trial": all(
                record["score_after_timing"] == record["expected_score_after_timing"]
                for record in trials
            ),
        }
        timing_key = (
            "mean_function_execution_nanos"
            if mode in ALL_FUNCTION_TIMING_MODES
            else "mean_callback_nanos"
        )
        timing_values = [
            float(record["server_thread_timing"][timing_key])
            for record in trials
            if record.get("server_thread_timing") is not None
        ]
        if timing_values:
            median_timing_nanos = float(statistics.median(timing_values))
            summary[mode][f"{timing_key}_by_trial"] = timing_values
            summary[mode][f"median_{timing_key}"] = median_timing_nanos
            summary[mode][f"{timing_key}_min"] = min(timing_values)
            summary[mode][f"{timing_key}_max"] = max(timing_values)
            summary[mode][f"{timing_key}_mad"] = float(
                statistics.median(
                    [abs(value - median_timing_nanos) for value in timing_values]
                )
            )
    baseline_rate = float(summary[baseline_mode]["median_function_commands_per_second"])
    for mode in modes:
        summary[mode][f"throughput_ratio_to_{baseline_mode}"] = (
            float(summary[mode]["median_function_commands_per_second"]) / baseline_rate
        )
        median_timing_key = (
            "median_mean_function_execution_nanos"
            if mode in ALL_FUNCTION_TIMING_MODES
            else "median_mean_callback_nanos"
        )
        baseline_timing_key = (
            "median_mean_function_execution_nanos"
            if baseline_mode in ALL_FUNCTION_TIMING_MODES
            else "median_mean_callback_nanos"
        )
        if median_timing_key in summary[mode] and baseline_timing_key in summary[baseline_mode]:
            ratio_key = (
                "function_execution_time_ratio_to_instrument_only"
                if mode in ALL_FUNCTION_TIMING_MODES
                else "callback_time_ratio_to_instrument_only"
            )
            summary[mode][ratio_key] = (
                float(summary[mode][median_timing_key])
                / float(summary[baseline_mode][baseline_timing_key])
            )
    summary["interpretation_limit"] = (
        "RCON throughput includes orchestration and command dispatch. The optional "
        "ScoreAdd callback timer measures only Command.run. The optional full-function "
        "timer measures from FunctionCommand.queueFunctions for the target fixture "
        "through ExecutionContext.runCommandQueue return, including instantiation, "
        "queue processing, quota, callbacks, and tracing, while excluding RCON and "
        "the preceding Brigadier command parse. Spark profiles provide sampled "
        "attribution; do not generalize from this static fixture."
    )
    return summary


def main() -> int:
    global OUTPUT_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup-calls", type=int, default=50)
    parser.add_argument("--measured-calls", type=int, default=1_000)
    parser.add_argument("--profile-seconds", type=int, default=10)
    parser.add_argument("--seed", type=int, default=260326)
    parser.add_argument(
        "--exact-timing",
        action="store_true",
        help=(
            "compare instrument-only and ScoreAdd callbacks with a test-only "
            "server-thread timer; writes a separate PERF-002-timing report"
        ),
    )
    parser.add_argument(
        "--function-timing",
        action="store_true",
        help=(
            "compare matched target-function queue time for the vanilla "
            "delegate, ScoreAdd, and fused-region prototypes; writes PERF-003"
        ),
    )
    parser.add_argument(
        "--backend-comparison",
        action="store_true",
        help=(
            "compare the PERF-003 backends plus emitted bytecode with the same "
            "function-queue timer; writes a separate PERF-004 report"
        ),
    )
    parser.add_argument("--fresh", action="store_true", help="start a new report instead of resuming a matching run")
    args = parser.parse_args()
    if args.repetitions < 1 or args.measured_calls < 1 or args.warmup_calls < 0:
        parser.error("repetitions must be >= 1, measured-calls >= 1, and warmup-calls >= 0")
    if args.profile_seconds < 1:
        parser.error("profile-seconds must be >= 1")
    if sum((args.exact_timing, args.function_timing, args.backend_comparison)) > 1:
        parser.error("timing experiment options are mutually exclusive")
    timed_experiment = (
        args.exact_timing or args.function_timing or args.backend_comparison
    )
    modes = (
        TIMING_MODES if args.exact_timing else
        BACKEND_TIMING_MODES if args.backend_comparison else
        FUNCTION_TIMING_MODES if args.function_timing else MODES
    )
    baseline_mode = "instrument-only" if args.exact_timing else (
        "function-instrument-only"
        if args.function_timing or args.backend_comparison
        else "vanilla"
    )
    benchmark_id = (
        "PERF-002-TIMING" if args.exact_timing else
        "PERF-004-BACKEND-TIMING" if args.backend_comparison else
        "PERF-003-FUNCTION-TIMING" if args.function_timing else "PERF-002"
    )
    if args.exact_timing:
        OUTPUT_DIR = ROOT / "build" / "benchmarks" / "PERF-002-timing"
    elif args.function_timing:
        OUTPUT_DIR = ROOT / "build" / "benchmarks" / "PERF-003-function-timing"
    elif args.backend_comparison:
        OUTPUT_DIR = ROOT / "build" / "benchmarks" / "PERF-004-bytecode-timing"
    if not SPARK_AGENT.is_file() or sha256(SPARK_AGENT) != SPARK_SHA256:
        raise FileNotFoundError(
            f"Expected pinned Spark 1.10.194 agent at {SPARK_AGENT.relative_to(ROOT)}"
        )

    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_JAR_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server jar hash mismatch: {server_jar}")
    packet_ids = generate_packet_ids(server_jar)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results_path = OUTPUT_DIR / "results.json"
    fixture_probe = OUTPUT_DIR / "scoreboard-fixture.sha256"
    fixture_text = "".join(
        f"scoreboard players add {BENCH_HOLDER} {BENCH_OBJECTIVE} 1\n"
        for _ in range(FUNCTION_LINES)
    ).encode("utf-8")
    fixture_sha256 = hashlib.sha256(fixture_text).hexdigest()
    fixture_probe.write_text(fixture_sha256 + "\n", encoding="utf-8")

    order = [
        (mode, repetition)
        for repetition in range(1, args.repetitions + 1)
        for mode in modes
    ]
    random.Random(args.seed).shuffle(order)
    manifest = {
        "benchmark": benchmark_id,
        "purpose": (
            "Test-only server-thread callback timing: delegate to vanilla command "
            "versus the disabled-by-default literal fake-holder ScoreAdd prototype"
            if args.exact_timing
            else "Matched server-thread timing for vanilla command dispatch, ScoreAdd, and fused interpreted regions"
            if args.function_timing
            else "Matched server-thread timing for vanilla command dispatch, ScoreAdd, fused interpreted regions, and emitted bytecode"
            if args.backend_comparison
            else "A/B test for the disabled-by-default literal fake-holder ScoreAdd prototype"
        ),
        "minecraft": "26.3 official server bundle",
        "server_jar_sha256": SERVER_JAR_SHA256,
        "spark": "1.10.194 standalone agent",
        "spark_agent_sha256": SPARK_SHA256,
        "java_version": java_version(),
        "host": platform.platform(),
        "cpu_count": os.cpu_count(),
        "jvm_args": list(JVM_ARGS),
        "fixture": BENCH_FUNCTION,
        "fixture_sha256": fixture_sha256,
        "fixture_lines": FUNCTION_LINES,
        "score_holder": BENCH_HOLDER,
        "objective": BENCH_OBJECTIVE,
        "quota": 65536,
        "warmup_calls_per_trial": args.warmup_calls,
        "measured_calls_per_trial": args.measured_calls,
        "repetitions": args.repetitions,
        "profile_seconds": 0 if timed_experiment else args.profile_seconds,
        "spark_profile_workload": None if timed_experiment else {
            "source": "#minecraft:tick function gated by a storage flag",
            "scoreboard_function_calls_per_tick": PROFILE_CALLS_PER_TICK,
            "scoreboard_actions_per_call": FUNCTION_LINES,
            "scoreboard_actions_per_profile_tick": PROFILE_CALLS_PER_TICK * FUNCTION_LINES,
            "completion_oracle": "profile tick counter and fake-holder scoreboard delta",
        },
        "randomized_trial_order_seed": args.seed,
        "trial_order": [f"{mode}-r{repetition:02d}" for mode, repetition in order],
        "modes": (
            {
                "instrument-only": "Fabric wrapper; timed callback delegates to vanilla ScoreboardCommand",
                "score-add-timed": "Fabric wrapper; timed callback runs the ScoreAdd prototype",
            }
            if args.exact_timing
            else {
                "function-instrument-only": "Fabric wrapper; whole-function timer with vanilla command delegate",
                "function-score-add-timed": "Fabric wrapper; whole-function timer with ScoreAdd prototype",
                "function-fused-timed": "Fabric wrapper; whole-function timer with fused interpreted ScoreAdd regions",
                **({
                    "function-bytecode-timed": "Fabric wrapper; whole-function timer with emitted bytecode ScoreAdd regions",
                } if args.backend_comparison else {}),
            }
            if args.function_timing or args.backend_comparison
            else {
                "vanilla": "official Minecraft server jar",
                "fabric-off": "Fabric development server, wrapper disabled",
                "wrapper-only": "Fabric development server, delegating wrapper enabled",
                "score-add-on": "Fabric development server, wrapper and ScoreAdd prototype enabled",
                "fused-interpreted": "Fabric development server, fused interpreted ScoreAdd regions enabled",
                "bytecode-emitted": "Fabric development server, emitted bytecode ScoreAdd regions enabled",
            }
        ),
        "score_add_metrics": "disabled in every timed trial; correctness suite enables its counter separately",
        "score_add_callback_timer": (
            "enabled only for matched instrument-only and ScoreAdd-timed arms"
            if args.exact_timing
            else "disabled in every benchmark arm"
        ),
        "full_function_timer": (
            "enabled from FunctionCommand.queueFunctions for the target fixture "
            "through its ExecutionContext.runCommandQueue return in all selected backend arms"
            if args.function_timing or args.backend_comparison
            else "disabled in every benchmark arm"
        ),
        "timing_limit": (
            "System.nanoTime surrounds the command callback on the server thread; timer covers callback only"
            if args.exact_timing
            else "System.nanoTime spans target function queueing through ExecutionContext.runCommandQueue return; RCON and preceding Brigadier command parsing are excluded"
            if args.function_timing
            else "RCON round trip includes orchestration and command dispatch; not exact server-thread elapsed time"
        ),
    }
    report: dict[str, object] = {"manifest": manifest, "trials": []}
    results: list[dict[str, object]] = []
    if results_path.is_file() and not args.fresh:
        previous_report = json.loads(results_path.read_text(encoding="utf-8"))
        if previous_report.get("manifest") != manifest:
            raise RuntimeError(
                f"An existing {benchmark_id} report has a different manifest; "
                "rerun with --fresh to start a new comparison"
            )
        results = list(previous_report.get("trials", []))
        report["trials"] = results
        profile_captured = {
            str(trial["mode"])
            for trial in results
            if trial.get("spark_profiles")
        }
        print(
            f"Resuming matching {benchmark_id} report with {len(results)} of {len(order)} trials",
            flush=True,
        )
    else:
        profile_captured = set()
    results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for mode, repetition in order:
        if any(
            trial["mode"] == mode and trial["repetition"] == repetition
            for trial in results
        ):
            continue
        print(f"Starting {benchmark_id} {mode} repetition {repetition}/{args.repetitions}", flush=True)
        for attempt in range(1, 4):
            try:
                trial = run_trial(
                    mode=mode,
                    repetition=repetition,
                    warmup_calls=args.warmup_calls,
                    measured_calls=args.measured_calls,
                    profile_seconds=args.profile_seconds,
                    capture_profiles=(not timed_experiment and mode not in profile_captured),
                    server_jar=server_jar,
                    packet_ids=packet_ids,
                    fixture_sha256=fixture_sha256,
                )
                break
            except PortBindError as error:
                if attempt == 3:
                    raise
                print(
                    f"Retrying {mode} repetition {repetition} after transient port bind failure "
                    f"({attempt}/3): {error}",
                    flush=True,
                )
        if trial["spark_profiles"]:
            profile_captured.add(mode)
        results.append(trial)
        report["trials"] = results
        report["summary"] = (
            summarize(results, modes, baseline_mode) if len(results) == len(order) else None
        )
        results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "trial_id": trial["trial_id"],
                    "mode": mode,
                    "measured_function_commands_per_second": trial[
                        "measured_function_commands_per_second"
                    ],
                    "rcon_median_ns": trial["rcon_round_trip_median_ns"],
                    "verified_score": trial["score_after_timing"],
                    "spark_profiles": len(trial["spark_profiles"]),
                }
            ),
            flush=True,
        )

    report["summary"] = summarize(results, modes, baseline_mode)
    results_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"{benchmark_id} result: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
