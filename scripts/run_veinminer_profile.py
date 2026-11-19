#!/usr/bin/env python3
"""Profile a native Vein Miner 5.3.0 ore traversal on Minecraft 26.3."""

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
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "runtime"))

from ci_server_event_cpu import (  # noqa: E402
    find_server_thread, read_thread_schedstat, cgroup_throttle_count, event_cpu_delta,
    parse_tick_query, pre_event_stability, event_tick_diagnostic,
)
from analyze_spark_profile import summarize as summarize_spark_profile  # noqa: E402
from player_bot import PacketIds, PlayerBot  # noqa: E402
from run_dynamic_lights_profile import (  # noqa: E402
    MODS,
    MODS_DIR,
    STACK_MODS,
    sha256,
    spark_thread_node_count,
)
from run_entity_datapack_profile import DrainingRconClient  # noqa: E402
from run_runtime_probe import (  # noqa: E402
    SERVER_JAR_SHA256,
    generate_packet_ids,
    locate_official_server_jar,
)
from run_spawn_animations_profile import (  # noqa: E402
    start_spark_shell,
    stop_spark_shell,
    wait_for_spark_password,
)


PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PACK_SHA256 = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
SPARK_AGENT = ROOT / "references/real-world/spark-1.10.194/spark-1.10.194-standalone-agent.jar"
SPARK_SHA256 = "a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9"
SERVER_HOST = "127.0.0.1"
OUTPUT_ROOT = ROOT / "build/benchmarks/PERF-011-veinminer"
RUN_ROOT = ROOT / "run"
PLAYER_NAME = "FCVein"
PROBE_OBJECTIVE = "fc_vein"
PROBE_PACK = "function_compiler_probe"
PACK_NAME = "veinminer"
PROFILE_INTERVAL_MS = 4
MODE_OPTIONS = (
    "off",
    "wrapper",
    "score-add",
    "score-add-instrumented",
    "fused",
    "fused-timed",
    "selective-macro",
)

# Modes that substitute a compiled instantiation for the original entry list:
# the wrapper then reports delegates_original=false while retaining the
# original parsed action as a fallback.
SUBSTITUTES_COMPILATION = {"fused", "fused-timed", "bytecode-emitted"}


def configure_gradle_cache_environment(environment: dict[str, str]) -> dict[str, str]:
    """Avoid registering the writable Gradle cache as read-only.

    Gradle's shared read-only dependency cache requires a *distinct* cache
    directory. The old auto-configuration used ~/.gradle/caches, which is also
    Gradle's writable cache in a standard GitHub Actions runner. A nested
    runServer invocation then aborted with "already open with different lock
    options" before Minecraft started.
    """
    environment = environment.copy()
    project_cache = ROOT / ".gradle-user-home"
    if "GRADLE_USER_HOME" not in environment and project_cache.is_dir():
        environment["GRADLE_USER_HOME"] = str(project_cache)
    # Do not automatically set GRADLE_RO_DEP_CACHE. This is an explicit
    # opt-in Gradle feature, not an alias for the normal writable cache.
    writable_home = Path(
        environment.get("GRADLE_USER_HOME", str(Path.home() / ".gradle"))
    ).expanduser().resolve()
    readonly = environment.get("GRADLE_RO_DEP_CACHE")
    if readonly and Path(readonly).expanduser().resolve() == writable_home / "caches":
        # Prefer the already-warm writable cache instead of conflicting locks.
        environment.pop("GRADLE_RO_DEP_CACHE")
    return environment


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((SERVER_HOST, 0))
        return int(probe.getsockname()[1])


def wait_for_rcon(
    server: subprocess.Popen[bytes],
    port: int,
    password: str,
    timeout: float = 300,
) -> DrainingRconClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Minecraft exited early with code {server.returncode}")
        try:
            return DrainingRconClient(SERVER_HOST, port, password)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(0.5)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def read_score(client: DrainingRconClient, holder: str, objective: str) -> int:
    response = client.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not read {holder} {objective}: {response!r}")
    return int(match.group(1))


def read_score_or_zero(client: DrainingRconClient, holder: str, objective: str) -> int:
    try:
        return read_score(client, holder, objective)
    except RuntimeError as error:
        if "none is set" in str(error):
            return 0
        raise


def count_entities(
    client: DrainingRconClient,
    holder: str,
    objective: str,
    selector: str,
) -> int:
    client.command(f"scoreboard players set {holder} {objective} 0")
    client.command(f"execute as {selector} run scoreboard players add {holder} {objective} 1")
    return read_score(client, holder, objective)


def stats_int(status: str | None, name: str) -> int:
    if not status:
        return 0
    match = re.search(rf"\b{re.escape(name)}=(\d+)", status)
    return int(match.group(1)) if match else 0


def stats_provider_classes(status: str | None) -> dict[str, int]:
    if not status:
        return {}
    match = re.search(
        r"unsupported_provider_classes=([^ ]*)", status
    )
    if not match or not match.group(1):
        return {}
    result = {}
    for item in match.group(1).split(","):
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        result[key] = int(value)
    return result


def _selective_macro_provider_class_delta(
    before: str | None, after: str | None
) -> dict[str, int]:
    before_counts = stats_provider_classes(before)
    after_counts = stats_provider_classes(after)
    keys = sorted(set(before_counts) | set(after_counts))
    return {
        key: after_counts.get(key, 0) - before_counts.get(key, 0) for key in keys
    }


def function_stats(client: DrainingRconClient, function_id: str, enabled: bool) -> str | None:
    return client.command(f"function_compiler_probe stats {function_id}") if enabled else None


def function_stats_value(stats: str | None, key: str) -> int:
    return stats_int(stats, key)


def world_geometry(side: int) -> dict[str, object]:
    if side in (4, 5, 6):
        return {
            "min": (8, 64, 8),
            "max": (7 + side, 63 + side, 7 + side),
            "source": (8, 64, 9),
            "player": (6.5, 64.0, 9.5, -90.0, 30.0),
        }
    if side == 8:
        return {
            "min": (12, 64, 12),
            "max": (19, 71, 19),
            "source": (15, 65, 12),
            "player": (15.5, 64.0, 9.5, 0.0, 11.0),
        }
    raise ValueError(f"Unsupported test vein side length: {side}")


def write_ore_counter(
    probe_pack: Path,
    minimum: tuple[int, int, int],
    maximum: tuple[int, int, int],
) -> None:
    function_path = (
        probe_pack
        / "data/function_compiler_probe/function/count_ore.mcfunction"
    )
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    lines = [f"scoreboard players set #remaining {PROBE_OBJECTIVE} 0"]
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                lines.append(
                    f"execute if block {x} {y} {z} minecraft:coal_ore run "
                    f"scoreboard players add #remaining {PROBE_OBJECTIVE} 1"
                )
    function_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_success(client: DrainingRconClient, holder: str, objective: str, command: str) -> bool:
    response = client.command(
        f"execute store success score {holder} {objective} run {command}"
    )
    if "Unknown" in response or "Incorrect" in response:
        raise RuntimeError(f"Could not run completion observation {command!r}: {response!r}")
    return read_score(client, holder, objective) == 1


def parse_args() -> object:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=("vanilla", *STACK_MODS), default="vanilla")
    parser.add_argument("--compiler-mode", choices=MODE_OPTIONS, default="off")
    parser.add_argument("--side", type=int, choices=(4, 5, 6, 8), default=4)
    parser.add_argument("--capture-timeout", type=int, default=45)
    parser.add_argument("--mining-hold-seconds", type=float, default=1.25)
    parser.add_argument(
        "--count-command-callbacks",
        action="store_true",
        help=(
            "Enable opt-in ordinary leaf-callback accounting for diagnostics; "
            "the added wrappers perturb timing and Spark samples."
        ),
    )
    parser.add_argument(
        "--scoreadd-path-coverage-diagnostic",
        action="store_true",
        help=(
            "Research-only: count typed ScoreAdd callback entries separately"
            " from wrapped leaf callbacks. Require both ScoreAdd and callback"
            " counters; preserve legacy strict diagnostic acceptance otherwise."
        ),
    )
    parser.add_argument(
        "--count-selective-macro-arguments",
        action="store_true",
        help=(
            "Enable selective macro hit counting for diagnostics; the added metric "
            "perturbs timing and is not comparable to ordinary profiles."
        ),
    )
    parser.add_argument(
        "--no-spark",
        action="store_true",
        help=(
            "Run the native event timing without the Spark agent or sampling; "
            "use a separate Spark run for CPU attribution."
        ),
    )
    parser.add_argument(
        "--capture-jfr-cpu",
        action="store_true",
        help=(
            "Research-only JDK 25 Linux CPUTimeSample JFR capture restricted"
            " to the native mining event. Requires --no-spark and"
            " --capture-server-thread-cpu; never combines with callback counters."
        ),
    )
    parser.add_argument(
        "--capture-server-thread-cpu",
        action="store_true",
        help=(
            "Opt-in Linux /proc Server-thread running-CPU accounting for the "
            "native mining event only; no agents or function counters."
        ),
    )
    parser.add_argument(
        "--startup-readiness-record", type=Path, default=None,
        help="Research-only file recording pre-mining stage for eligibility audit.",
    )
    parser.add_argument(
        "--setup-rcon-timeout-seconds",type=float,default=10.0,
        help="Research-only timeout for the chunk forceload setup request.",
    )
    parser.add_argument(
        "--tick-stability-diagnostics", action="store_true",
        help="Research-only idle baseline gate and non-exclusionary event tick diagnostics.",
    )
    parser.add_argument(
        "--pre-event-idle-seconds",type=float,default=9.0,
        help="Idle settling interval before baseline tick query (018R1, >=8s).",
    )
    args = parser.parse_args()
    if args.scoreadd_path_coverage_diagnostic and not (
        args.compiler_mode == "score-add-instrumented" and args.count_command_callbacks
    ):
        parser.error("ScoreAdd path coverage requires score-add-instrumented and --count-command-callbacks")
    if args.tick_stability_diagnostics and args.pre_event_idle_seconds < 8.0:
        parser.error("Research idle baseline requires at least 8 seconds")
    if not 10.0 <= args.setup_rcon_timeout_seconds <= 60.0:
        parser.error("Setup RCON timeout must be between 10 and 60 seconds")
    if args.setup_rcon_timeout_seconds != 10.0 and args.startup_readiness_record is None:
        parser.error("Long setup RCON timeout requires a startup readiness record")
    if args.stack == "vanilla" and args.compiler_mode != "off":
        parser.error("a compiler mode requires a Fabric stack")
    if args.stack == "vanilla" and args.count_command_callbacks:
        parser.error("--count-command-callbacks requires a Fabric stack")
    if args.count_selective_macro_arguments and args.compiler_mode != "selective-macro":
        parser.error(
            "--count-selective-macro-arguments requires --compiler-mode selective-macro"
        )
    if args.capture_jfr_cpu and not (
        args.no_spark and args.capture_server_thread_cpu
        and not args.count_command_callbacks
        and not args.count_selective_macro_arguments
        and args.compiler_mode in ("off", "score-add")
        and args.stack != "vanilla"
    ):
        parser.error(
            "JFR CPU sampling requires Fabric compiler off/score-add,"
            " --no-spark, --capture-server-thread-cpu, and no counters"
        )
    if args.capture_timeout < 5:
        parser.error("--capture-timeout must be at least 5 seconds")
    if args.mining_hold_seconds < 0.2:
        parser.error("--mining-hold-seconds must be at least 0.2 seconds")
    return args


def main() -> int:
    args = parse_args()
    startup_history: list[dict[str, object]] = []
    mining_started = False

    def mark_startup(stage: str) -> None:
        # The parent runner may retry only one very specific, recorded
        # pre-intervention failure. An absent/corrupted stage must never be
        # treated as proof that the player action has not started.
        if args.startup_readiness_record is None:
            return
        startup_history.append({
            "stage":stage,
            "mining_started":mining_started,
            "monotonic_ns":time.monotonic_ns(),
        })
        target=args.startup_readiness_record
        target.parent.mkdir(parents=True,exist_ok=True)
        payload={
            "protocol":"SCHED-COMP-018R2",
            "stage":stage,"mining_started":mining_started,
            "stage_history":startup_history,
            "setup_rcon_timeout_seconds":args.setup_rcon_timeout_seconds,
        }
        temporary=target.with_suffix(target.suffix+".tmp")
        temporary.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
        temporary.replace(target)

    mark_startup("runner_created")
    geometry = world_geometry(args.side)
    minimum = geometry["min"]
    maximum = geometry["max"]
    source = geometry["source"]
    player = geometry["player"]
    assert isinstance(minimum, tuple) and isinstance(maximum, tuple)
    assert isinstance(source, tuple) and isinstance(player, tuple)
    expected_work = args.side**3 - 1
    maximum_work = expected_work + 1
    compiler_enabled = args.compiler_mode != "off"
    callback_metrics_enabled = args.count_command_callbacks
    selective_macro_metrics_enabled = args.count_selective_macro_arguments
    score_add_metrics_enabled = args.compiler_mode in {
        "score-add-instrumented",
        "fused",
    }
    capture_spark = not args.no_spark
    capture_jfr_cpu = args.capture_jfr_cpu
    cpu004_mode = os.environ.get("FC_CPU004_MODE", "")
    cpu004_enabled = cpu004_mode in ("plain", "empty", "timed")
    if cpu004_mode and (
        not cpu004_enabled
        or os.environ.get("FC_CPU004_NAMESPACE") != "vm"
        or args.stack == "vanilla"
        or args.compiler_mode != "wrapper"
        or args.count_command_callbacks
        or args.capture_jfr_cpu
        or not args.no_spark
        or not args.capture_server_thread_cpu
    ):
        raise ValueError("CPU004 requires vm namespace, Fabric wrapper mode, --no-spark, "
                         "--capture-server-thread-cpu and no other callback/JFR metrics")
    cpu005_mode = os.environ.get("FC_CPU005_MODE", "")
    cpu005_enabled = cpu005_mode in ("plain", "empty", "timed")
    if cpu005_mode and (
        not cpu005_enabled
        or os.environ.get("FC_CPU005_NAMESPACE") != "vm"
        or args.stack == "vanilla"
        or args.compiler_mode != "wrapper"
        or args.count_command_callbacks
        or args.capture_jfr_cpu
        or not args.no_spark
        or not args.capture_server_thread_cpu
        or cpu004_enabled
    ):
        raise ValueError("CPU005 requires vm namespace, Fabric wrapper mode, --no-spark, "
                         "--capture-server-thread-cpu and no other command/JFR metrics")
    exec_census_enabled = os.environ.get(
        "FC_COMPILER_EXEC_CENSUS", "").lower() in {"true", "1"}
    if exec_census_enabled and (
        args.stack == "vanilla"
        or not os.environ.get("FC_COMPILER_EXEC_CENSUS_NAMESPACE")
        or not os.environ.get("FC_COMPILER_EXEC_CENSUS_FUNCTIONS")
        or args.compiler_mode not in ("wrapper", "score-add")
    ):
        raise ValueError(
            "Execution census requires Fabric, wrapper/score-add, namespace and allowlist"
        )
    acceptance_audit_enabled = os.environ.get(
        "FC_COMPILER_ACCEPTANCE_AUDIT", "").lower() in {"true", "1"}
    if acceptance_audit_enabled and (
        args.stack == "vanilla"
        or not os.environ.get("FC_COMPILER_ACCEPTANCE_NAMESPACE")
    ):
        raise ValueError("Acceptance audit requires Fabric and an explicit namespace")
    compiler_probe_active = compiler_enabled or callback_metrics_enabled
    diagnostics = []
    if acceptance_audit_enabled:
        diagnostics.append("namespace-scoped compiler acceptance census")
    if exec_census_enabled:
        diagnostics.append("event-scoped selected command entry/callback counters")
    if cpu004_enabled:
        if exec_census_enabled or acceptance_audit_enabled:
            raise ValueError("CPU004 and other compiler audits must run in separate JVMs")
        diagnostics.append("sparse CPU004 command-site timers (" + cpu004_mode + ")")
    if cpu005_enabled:
        if exec_census_enabled or acceptance_audit_enabled or callback_metrics_enabled:
            raise ValueError("CPU005 must run without other command/callback audits")
        diagnostics.append("sparse CPU005 queue macro predicate/NBT task clocks (" + cpu005_mode + ")")
    if callback_metrics_enabled:
        diagnostics.append("command callback counters")
    if selective_macro_metrics_enabled:
        diagnostics.append("selective-macro hit counter")
    if score_add_metrics_enabled:
        diagnostics.append("ScoreAdd compile/execution counters")
    timing_instrumentation = (
        f"Spark CPU sampling and {', '.join(diagnostics)} active during event"
        if capture_spark and diagnostics
        else "Spark CPU sampling active during event"
        if capture_spark
        else f"no Spark; {', '.join(diagnostics)} enabled"
        if diagnostics
        else "no Spark agent or Function Compiler timing/counter metrics"
    )

    if capture_jfr_cpu:
        timing_instrumentation = (
            "JDK 25 JFR CPUTimeSample (5ms CPU-time period),"
            " no Spark or Function Compiler callback counters;"
            " event-level CPU total is separately read from /proc"
        )

    pinned_artifacts = [(PACK, PACK_SHA256, "Vein Miner 5.3.0 datapack")]
    if capture_spark:
        pinned_artifacts.append((SPARK_AGENT, SPARK_SHA256, "Spark standalone agent"))
    for path, expected, label in pinned_artifacts:
        if not path.is_file() or sha256(path) != expected:
            raise FileNotFoundError(f"Missing or mismatched pinned {label}: {path}")
    for key in STACK_MODS.get(args.stack, ()):
        path, expected = MODS[key]
        mod_path = MODS_DIR / path
        if not mod_path.is_file() or sha256(mod_path) != expected:
            raise FileNotFoundError(f"Missing or mismatched pinned {key} mod: {mod_path}")
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_JAR_SHA256:
        raise RuntimeError(f"Minecraft server hash mismatch: {server_jar}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    diagnostic_suffix = (
        "-callback-diagnostic"
        if callback_metrics_enabled
        else "-selective-macro-diagnostic"
        if selective_macro_metrics_enabled
        else ""
    )
    timing_suffix = "" if capture_spark else "-no-spark"
    output = OUTPUT_ROOT / (
        f"vein-{args.side}-{args.stack}-{args.compiler_mode}"
        f"{diagnostic_suffix}{timing_suffix}-{run_id}"
    )
    output.mkdir(parents=True, exist_ok=False)
    work = RUN_ROOT / f"veinminer-{run_id}"
    work.mkdir(parents=True, exist_ok=False)
    server_port, rcon_port, spark_port = free_port(), free_port(), free_port()
    password = secrets.token_urlsafe(24)
    rcon: DrainingRconClient | None = None
    bot: PlayerBot | None = None
    spark: subprocess.Popen[bytes] | None = None
    server: subprocess.Popen[bytes] | None = None
    log_handle = None
    profile_path: Path | None = None
    jfr_path: Path | None = None
    jfr_pid: int | None = None
    jfr_started = False
    jfr_start_message: str | None = None
    jfr_stop_message: str | None = None
    succeeded = False
    manifest_path = output / "results.json"
    exec_census_started = False
    exec_census_start_status = None
    exec_census_stop_status = None
    cpu004_started = False
    cpu004_start_status = None
    cpu004_stop_status = None
    cpu005_started = False
    cpu005_start_status = None
    cpu005_stop_status = None

    try:
        datapacks = work / "world/datapacks"
        datapacks.mkdir(parents=True)
        shutil.copy2(PACK, datapacks / f"{PACK_NAME}.zip")
        probe_pack = datapacks / PROBE_PACK
        shutil.copytree(ROOT / "src/main/resources/data", probe_pack / "data")
        write_ore_counter(probe_pack, minimum, maximum)
        (probe_pack / "pack.mcmeta").write_text(
            json.dumps(
                {
                    "pack": {
                        "description": "Function Compiler runtime probe",
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
            mods_dir = work / "mods"
            mods_dir.mkdir()
            for key in STACK_MODS[args.stack]:
                filename, _ = MODS[key]
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
            "max-players": "2",
            "view-distance": "4",
            "simulation-distance": "4",
            "sync-chunk-writes": "false",
            "pause-when-empty-seconds": "-1",
        }
        (work / "server.properties").write_text(
            "".join(f"{key}={value}\n" for key, value in properties.items()),
            encoding="utf-8",
        )
        log_path = work / "server.log"
        log_handle = log_path.open("wb")

        if args.stack == "vanilla":
            command = [
                "java",
                "-Xms1G",
                "-Xmx4G",
            ]
            if capture_spark:
                command.append(f"-javaagent:{SPARK_AGENT}=port={spark_port}")
            command.extend(("-jar", str(server_jar), "nogui"))
            cwd = work
            environment = None
        else:
            environment = configure_gradle_cache_environment(os.environ.copy())
            wrapper_enabled = compiler_enabled or callback_metrics_enabled
            score_add_enabled = args.compiler_mode in {
                "score-add",
                "score-add-instrumented",
                "fused",
                "fused-timed",
            }
            environment.update(
                {
                    "FC_WRAPPER_PROBE": str(wrapper_enabled).lower(),
                    "FC_SCORE_ADD_PROTOTYPE": str(score_add_enabled).lower(),
                    "FC_SCORE_ADD_METRICS": str(
                        args.compiler_mode in {"score-add-instrumented", "fused"}
                    ).lower(),
                    "FC_FUSED_REGION_PROTOTYPE": str(
                        args.compiler_mode in {"fused", "fused-timed"}
                    ).lower(),
                    "FC_COMMAND_CALLBACK_METRICS": str(callback_metrics_enabled).lower(),
                    "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES": str(
                        callback_metrics_enabled
                    ).lower(),
                    "FC_SELECTIVE_MACRO_ARGUMENTS": str(
                        args.compiler_mode == "selective-macro"
                    ).lower(),
                    "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": str(
                        selective_macro_metrics_enabled
                    ).lower(),
                    "FC_RUNTIME_TRACE": "false",
                }
            )
            gradle = [
                "--no-daemon",
                "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
                "-PfcJvmArgs=-Xms512M,-Xmx2G",
                f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
            ]
            if capture_spark:
                gradle.extend(
                    (
                        f"-PfcSparkAgentPath={SPARK_AGENT}",
                        f"-PfcSparkPort={spark_port}",
                    )
                )
            gradle.append("runServer")
            if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
                gradle.insert(0, "--offline")
            command = [str(ROOT / "gradlew"), *gradle]
            cwd = ROOT

        launched_at = time.monotonic()
        server = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        rcon = wait_for_rcon(server, rcon_port, password)
        launch_to_rcon_seconds = time.monotonic() - launched_at
        mark_startup("rcon_ready")
        datapacks_enabled = rcon.command("datapack list enabled")
        if PACK_NAME not in datapacks_enabled.casefold():
            raise RuntimeError(f"Vein Miner did not load: {datapacks_enabled!r}")
        objectives = rcon.command("scoreboard objectives list")
        for objective in ("vmr.config", "vmr.runtime", "vmr.work"):
            if objective not in objectives:
                raise RuntimeError(f"Vein Miner did not initialize {objective}: {objectives!r}")

        compiler_status = None
        if args.stack != "vanilla":
            compiler_status = rcon.command("function_compiler_probe status")
            # Fused and bytecode modes substitute a compiled instantiation for the
            # original entry list, so delegates_original is false for them; the
            # original parsed action must still be retained as a fallback.
            substitutes_compilation = args.compiler_mode in SUBSTITUTES_COMPILATION
            for invariant in (
                "FC_PROBE present=true",
                f"wrapped={str(compiler_probe_active).lower()}",
                "tag_same_instance=true",
                f"delegates_original={str(not substitutes_compilation).lower()}",
                "original_fallback_retained=true",
            ):
                if invariant not in compiler_status:
                    raise RuntimeError(f"Compiler probe failed {invariant}: {compiler_status!r}")
            if args.compiler_mode == "selective-macro":
                for invariant in (
                    "selective_macro_arguments_enabled=true",
                    "selective_macro_arguments_metrics_enabled="
                    f"{str(selective_macro_metrics_enabled).lower()}",
                ):
                    if invariant not in compiler_status:
                        raise RuntimeError(
                            f"Selective macro probe failed {invariant}: "
                            f"{compiler_status!r}"
                        )

        rcon.command("gamerule sendCommandFeedback false")
        rcon.command("gamerule doDaylightCycle false")
        rcon.command("gamerule doMobSpawning false")
        rcon.command("gamerule maxEntityCramming 10000")
        rcon.command("gamerule randomTickSpeed 0")
        rcon.command("difficulty peaceful")
        rcon.command(f"scoreboard objectives add {PROBE_OBJECTIVE} dummy")

        x0, y0, z0 = minimum
        x1, y1, z1 = maximum
        sx, sy, sz = source
        px, py, pz, yaw, pitch = player
        # The R1 failure was a 10-second RCON receive timeout while the
        # *first* chunk-forceload command was still blocking the server tick.
        # The longer limit is only for this pre-mining setup command; revert
        # to the previous socket timeout immediately after it, in all cases.
        old_socket_timeout=rcon.socket.gettimeout()
        mark_startup("forceload_pending")
        try:
            rcon.socket.settimeout(args.setup_rcon_timeout_seconds)
            rcon.command(f"forceload add {x0 - 8} {z0 - 8} {x1 + 8} {z1 + 8}")
            mark_startup("forceload_completed")
        finally:
            rcon.socket.settimeout(old_socket_timeout)
        rcon.command(f"fill {x0 - 8} 63 {z0 - 8} {x1 + 8} 63 {z1 + 8} minecraft:stone")
        rcon.command(f"fill {x0} {y0} {z0} {x1} {y1} {z1} minecraft:coal_ore")

        packet_ids = generate_packet_ids(server_jar)
        bot = PlayerBot(PLAYER_NAME, SERVER_HOST, server_port, packet_ids).connect()
        rcon.command(f"gamemode survival {PLAYER_NAME}")
        rcon.command(f"tp {PLAYER_NAME} {px} {py} {pz} {yaw} {pitch}")
        rcon.command(
            f"item replace entity {PLAYER_NAME} weapon.mainhand with minecraft:diamond_pickaxe"
        )
        rcon.command("scoreboard players set #activation vmr.config 0")
        rcon.command(f"scoreboard players set #max vmr.config {maximum_work}")

        registration_deadline = time.monotonic() + 15
        while time.monotonic() < registration_deadline:
            if read_score_or_zero(rcon, PLAYER_NAME, "vmr.player") == 1:
                break
            time.sleep(0.25)
        owner = read_score(rcon, PLAYER_NAME, "vmr.owner")
        if read_score(rcon, PLAYER_NAME, "vmr.player") != 1:
            raise RuntimeError("Vein Miner did not register the headless player")

        target_deadline = time.monotonic() + 15
        target_data = ""
        while time.monotonic() < target_deadline:
            target_exists = is_success(
                rcon,
                "#target",
                PROBE_OBJECTIVE,
                "execute if entity @e[type=minecraft:marker,tag=vmr.target,limit=1]",
            )
            if target_exists:
                target_data = rcon.command(
                    "data get entity @e[type=minecraft:marker,tag=vmr.target,limit=1] data"
                )
                if f"owner: {owner}" in target_data:
                    break
            time.sleep(0.25)
        if f"owner: {owner}" not in target_data:
            raise RuntimeError(f"Vein Miner did not ray-track the intended source: {target_data!r}")

        if capture_spark:
            spark_password = wait_for_spark_password(log_path, server)
            spark = start_spark_shell(work, spark_password, spark_port)
            assert spark.stdin is not None
            spark.stdin.write(
                f"spark profiler start --interval {PROFILE_INTERVAL_MS} --thread *\n".encode()
            )
            spark.stdin.flush()
            time.sleep(0.75)

        work_before = read_score(rcon, PLAYER_NAME, "vmr.work")
        head_before = read_score_or_zero(rcon, "#head", "vmr.runtime")
        queue_stats_before = function_stats(rcon, "vm:queue/drain", compiler_enabled)
        ray_stats_before = function_stats(rcon, "vm:detection/ray_step", compiler_enabled)
        compiler_status_before = (
            rcon.command("function_compiler_probe status") if compiler_probe_active else None
        )
        tick_pre_event_stability = None
        if args.tick_stability_diagnostics:
            # The heavy actual event normally averages 250-310 ms/tick.
            # Only an *idle* baseline can be used as a host-stability gate;
            # post-event slowdown is an outcome and cannot filter runs.
            time.sleep(args.pre_event_idle_seconds)
            baseline_raw = rcon.command("tick query")
            tick_pre_event_stability = pre_event_stability(
                parse_tick_query(baseline_raw))
            (output / "tick-baseline.json").write_text(
                json.dumps({
                    "raw_tick_query":baseline_raw,
                    "pre_event_stability":tick_pre_event_stability,
                    "pre_event_idle_seconds":args.pre_event_idle_seconds,
                },indent=2)+"\n",encoding="utf-8")
            if not tick_pre_event_stability["stable"]:
                raise RuntimeError(
                    "Pre-event idle tick stability gate failed; not measuring or "
                    f"excluding this arm after observing treatment outcome: {tick_pre_event_stability}")
        event_thread = None
        event_cpu_before = None
        event_throttle_before = None
        if args.capture_server_thread_cpu:
            # In Fabric mode the outer process is Gradle. Find Minecraft's
            # actual Server thread in its descendant JVM before the event.
            pid, tid = find_server_thread(server.pid)
            event_thread = (pid, tid)
            event_cpu_before = read_thread_schedstat(pid, tid)
            event_throttle_before = cgroup_throttle_count()
        if capture_jfr_cpu:
            # Attach to the actual Minecraft child JVM rather than Gradle.
            # Start after idle stability and all baseline RCON commands;
            # stop immediately after the event CPU clock is closed.
            if event_thread is None:
                raise RuntimeError("JFR capture needs an identified Server thread")
            jfr_pid = event_thread[0]
            jfr_path = output / "veinminer-cpu.jfr"
            jfr_cmd = [
                "jcmd", str(jfr_pid), "JFR.start",
                "name=fc_comp_021", "settings=profile",
                "jdk.CPUTimeSample#enabled=true",
                "jdk.CPUTimeSample#throttle=5ms",
                "jdk.CPUTimeSample#stackTrace=true",
                "jdk.CPUTimeSamplesLost#enabled=true",
                "jdk.ExecutionSample#enabled=false",
            ]
            jfr_start = subprocess.run(
                jfr_cmd, text=True, capture_output=True, timeout=30, check=True)
            jfr_start_message = jfr_start.stdout
            jfr_started = True
            # Exclude attach/setup time from the /proc CPU denominator.
            pid, tid = event_thread
            event_cpu_before = read_thread_schedstat(pid, tid)
            event_throttle_before = cgroup_throttle_count()
        if cpu005_enabled:
            cpu005_start_status = rcon.command("function_compiler_probe cpu005-start")
            if "FC_CPU005 started mode=" + cpu005_mode not in cpu005_start_status:
                raise RuntimeError(f"CPU005 failed to start: {cpu005_start_status!r}")
            cpu005_started = True
        if cpu004_enabled:
            cpu004_start_status = rcon.command("function_compiler_probe cpu004-start")
            if "FC_CPU004 started mode=" + cpu004_mode not in cpu004_start_status:
                raise RuntimeError(f"CPU004 failed to start: {cpu004_start_status!r}")
            cpu004_started = True
        if exec_census_enabled:
            exec_census_start_status = rcon.command(
                "function_compiler_probe exec-census-start")
            if "FC_EXEC started namespace=" not in exec_census_start_status:
                raise RuntimeError(
                    f"Execution census failed to start: {exec_census_start_status!r}")
            exec_census_started = True
        # Set the irreversible intervention boundary before attempting the
        # first mining packet. Any failure from here is never retryable.
        mining_started = True
        mark_startup("mining_packet_started")
        event_started = time.monotonic()
        bot.send_player_action("start_destroy_block", sx, sy, sz, direction=1, sequence=0)
        time.sleep(args.mining_hold_seconds)
        bot.send_player_action("stop_destroy_block", sx, sy, sz, direction=1, sequence=1)

        source_mining_deadline = time.monotonic() + 5
        source_stat = 0
        while time.monotonic() < source_mining_deadline:
            source_stat = read_score_or_zero(rcon, PLAYER_NAME, "vmr.m41")
            if source_stat >= 1:
                break
            time.sleep(0.1)
        if source_stat < 1:
            raise RuntimeError("Headless player did not mine the coal-ore source block")

        completion_deadline = time.monotonic() + args.capture_timeout
        saw_operation = False
        work_after = work_before
        run_after = 0
        completion_elapsed: float | None = None
        event_progress_checkpoints: list[dict[str, object]] = []
        last_progress_state: tuple[int,int] | None = None
        while time.monotonic() < completion_deadline:
            work_after = read_score(rcon, PLAYER_NAME, "vmr.work")
            run_after = read_score(rcon, PLAYER_NAME, "vmr.run")
            saw_operation = saw_operation or run_after == 1
            current_state = (work_after,run_after)
            if current_state != last_progress_state:
                event_progress_checkpoints.append({
                    "elapsed_seconds":time.monotonic()-event_started,
                    "work":work_after,"run":run_after,
                })
                last_progress_state = current_state
            if work_after == expected_work and run_after == 0:
                completion_elapsed = time.monotonic() - event_started
                break
            time.sleep(0.5)

        # Close the CPU window immediately when the exact ore work completes,
        # before collecting compiler stats, RCON post-run context, or Spark.
        event_cpu = None
        if args.capture_server_thread_cpu:
            assert event_thread is not None and event_cpu_before is not None
            pid, tid = event_thread
            event_cpu = event_cpu_delta(
                event_cpu_before,read_thread_schedstat(pid,tid),
                event_throttle_before,cgroup_throttle_count())
            event_cpu["work_expected"]=expected_work
            event_cpu["cpu_ns_per_affected_block"]=(
                event_cpu["server_thread_cpu_running_ns"]/expected_work)
        if jfr_started:
            assert jfr_pid is not None and jfr_path is not None
            jfr_stop = subprocess.run(
                ["jcmd", str(jfr_pid), "JFR.stop", "name=fc_comp_021",
                 f"filename={jfr_path.resolve()}"],
                text=True, capture_output=True, timeout=40, check=True)
            jfr_stop_message = jfr_stop.stdout
            jfr_started = False
            if not jfr_path.is_file() or jfr_path.stat().st_size == 0:
                raise RuntimeError("JFR CPU sampler did not save a recording")
        if cpu005_started:
            cpu005_stop_status = rcon.command("function_compiler_probe cpu005-stop")
            if "FC_CPU005 ended mode=" + cpu005_mode not in cpu005_stop_status:
                raise RuntimeError(f"CPU005 failed to stop: {cpu005_stop_status!r}")
            cpu005_started = False
        if cpu004_started:
            cpu004_stop_status = rcon.command("function_compiler_probe cpu004-stop")
            if "FC_CPU004 ended mode=" + cpu004_mode not in cpu004_stop_status:
                raise RuntimeError(f"CPU004 failed to stop: {cpu004_stop_status!r}")
            cpu004_started = False
        if exec_census_started:
            exec_census_stop_status = rcon.command(
                "function_compiler_probe exec-census-stop")
            if "FC_EXEC ended entries=" not in exec_census_stop_status:
                raise RuntimeError(
                    f"Execution census failed to stop: {exec_census_stop_status!r}")
            exec_census_started = False
        compiler_status_after = (
            rcon.command("function_compiler_probe status") if compiler_probe_active else None
        )
        acceptance_dump_status = (
            rcon.command("function_compiler_probe acceptance")
            if acceptance_audit_enabled else None
        )
        if acceptance_audit_enabled and (
            acceptance_dump_status is None or "FC_ACCEPTANCE entries=" not in acceptance_dump_status
        ):
            raise RuntimeError(f"Acceptance audit dump failed: {acceptance_dump_status!r}")
        queue_stats_after = function_stats(rcon, "vm:queue/drain", compiler_enabled)
        ray_stats_after = function_stats(rcon, "vm:detection/ray_step", compiler_enabled)
        head_after_capture = read_score_or_zero(rcon, "#head", "vmr.runtime")
        spark_output = None
        capture_seconds = None
        thread_nodes = None
        server_thread = None
        function_samples = None
        if spark is not None:
            spark_output = stop_spark_shell(spark)
            spark = None
            capture_seconds = time.monotonic() - event_started
            profile_files = list(work.rglob("*.sparkprofile"))
            if not profile_files:
                raise RuntimeError(f"Spark saved no profile: {spark_output[-1200:]}")
            profile_path = output / "veinminer.sparkprofile"
            shutil.copy2(max(profile_files, key=lambda path: path.stat().st_mtime), profile_path)
            thread_nodes = spark_thread_node_count(profile_path)
            if thread_nodes == 0:
                raise RuntimeError("Spark saved a profile without thread samples")

        rcon.command(
            f"execute store success score #source fc_vein run execute if block "
            f"{sx} {sy} {sz} minecraft:coal_ore"
        )
        source_remains = read_score(rcon, "#source", PROBE_OBJECTIVE)
        rcon.command(f"function {PROBE_PACK}:count_ore")
        remaining_ore = read_score(rcon, "#remaining", PROBE_OBJECTIVE)
        operation_markers = count_entities(
            rcon,
            "#ops",
            PROBE_OBJECTIVE,
            "@e[type=minecraft:marker,tag=vmr.operation]",
        )
        target_markers = count_entities(
            rcon,
            "#targets",
            PROBE_OBJECTIVE,
            "@e[type=minecraft:marker,tag=vmr.target]",
        )
        runtime_state = {
            "configured_budget": read_score_or_zero(rcon, "#budget", "vmr.config"),
            "remaining_budget": read_score_or_zero(rcon, "#budget", "vmr.runtime"),
            "configured_max_work": read_score_or_zero(rcon, "#max", "vmr.config"),
            "harvest_check": read_score_or_zero(rcon, "#harvest", "vmr.runtime"),
            "claim_ready": read_score_or_zero(rcon, "#ready", "vmr.runtime"),
            "claim_limit": read_score_or_zero(rcon, "#limit", "vmr.runtime"),
            "source_tool_safety_stop": read_score_or_zero(
                rcon, "#safety_stop", "vmr.runtime"
            ),
            "max_command_sequence_length": rcon.command(
                "gamerule minecraft:max_command_sequence_length"
            ),
            "operation_marker_data": (
                rcon.command(
                    "data get entity @e[type=minecraft:marker,tag=vmr.operation,limit=1] data"
                )
                if operation_markers > 0
                else None
            ),
        }
        tick_query = rcon.command("tick query")
        tick_post_event_diagnostic = (
            event_tick_diagnostic(parse_tick_query(tick_query))
            if args.tick_stability_diagnostics else None
        )
        if profile_path is not None:
            profile_summary = summarize_spark_profile(profile_path, "Server thread", 40)
            server_thread = profile_summary["matched_threads"][0]
            function_samples = sum(
                method.get("inclusive_weighted_value", 0)
                for method in server_thread.get("top_methods", [])
                if method.get("class") == "net.minecraft.server.ServerFunctionManager"
                and method.get("method") == "execute"
            )

        command_callback_metrics = None
        specialized_counter_matches = None
        score_add_callback_entries_delta = None
        score_add_callback_entries_in_scope_delta = None
        score_add_direct_successes_delta = None
        if callback_metrics_enabled:
            if compiler_status_before is None or compiler_status_after is None:
                raise RuntimeError("Callback metric run did not capture probe status")
            generic_callbacks = (
                stats_int(compiler_status_after, "generic_leaf_callbacks")
                - stats_int(compiler_status_before, "generic_leaf_callbacks")
            )
            optimized_score_add_callbacks = (
                stats_int(compiler_status_after, "optimized_score_add_leaf_callbacks")
                - stats_int(compiler_status_before, "optimized_score_add_leaf_callbacks")
            )
            score_add_metrics_active = (
                "score_add_metrics_enabled=true" in compiler_status_after
            )
            score_add_executed_delta = (
                stats_int(compiler_status_after, "score_add_executed")
                - stats_int(compiler_status_before, "score_add_executed")
            )
            specialized_counter_matches = (
                optimized_score_add_callbacks == score_add_executed_delta
                if score_add_metrics_active
                else None
            )
            if args.scoreadd_path_coverage_diagnostic:
                score_add_callback_entries_delta = (
                    stats_int(compiler_status_after, "score_add_callback_entries")
                    - stats_int(compiler_status_before, "score_add_callback_entries")
                )
                score_add_callback_entries_in_scope_delta = (
                    stats_int(compiler_status_after, "score_add_callback_entries_in_scope")
                    - stats_int(compiler_status_before, "score_add_callback_entries_in_scope")
                )
                score_add_direct_successes_delta = (
                    stats_int(compiler_status_after, "score_add_direct_successes")
                    - stats_int(compiler_status_before, "score_add_direct_successes")
                )
            command_callback_metrics = {
                "scope": "all execution queues",
                "window": "immediately before the native mine packet through observed completion",
                "generic_leaf_callbacks": generic_callbacks,
                "optimized_score_add_leaf_callbacks": optimized_score_add_callbacks,
                "total_ordinary_leaf_callbacks": (
                    generic_callbacks + optimized_score_add_callbacks
                ),
                "score_add_executed_counter_delta": (
                    score_add_executed_delta if score_add_metrics_active else None
                ),
                "specialized_counter_matches": specialized_counter_matches,
                "typed_score_add_callback_entries": score_add_callback_entries_delta,
                "typed_score_add_callback_entries_in_scope": score_add_callback_entries_in_scope_delta,
                "typed_score_add_direct_successes": score_add_direct_successes_delta,
                "limitations": (
                    "Counts ordinary Brigadier leaf callbacks parsed in function queues. "
                    "Modifier operations and custom command executors are excluded."
                ),
                "timing_comparable": False,
            }
            if generic_callbacks < 0 or optimized_score_add_callbacks < 0:
                raise RuntimeError(
                    f"Callback counters moved backwards: {command_callback_metrics!r}"
                )

        selective_macro_argument_calls_delta = None
        selective_macro_diagnostics_delta = None
        selective_macro_provider_class_delta = None
        if selective_macro_metrics_enabled:
            if compiler_status_before is None or compiler_status_after is None:
                raise RuntimeError("Selective macro diagnostic did not capture probe status")
            selective_macro_argument_calls_delta = (
                stats_int(compiler_status_after, "selective_macro_arguments_used")
                - stats_int(compiler_status_before, "selective_macro_arguments_used")
            )
            selective_macro_diagnostics_delta = {
                name: (
                    stats_int(
                        compiler_status_after, alias
                    ) - stats_int(compiler_status_before, alias)
                )
                for name, alias in (
                    ("attempted", "selective_macro_argument_attempts"),
                    ("unsupported_providers", "selective_macro_unsupported_providers"),
                    ("unsupported_entity_paths", "selective_macro_unsupported_entity_paths"),                    ("invalid_storage_sources", "selective_macro_invalid_storage_sources"),
                    ("missing_entity_custom_data", "selective_macro_missing_entity_custom_data"),
                    ("macro_resolution_fallbacks", "selective_macro_macro_resolution_fallbacks"),
                    ("missing_selected_keys", "selective_macro_missing_selected_keys"),
                )
            }
            selective_macro_provider_class_delta = _selective_macro_provider_class_delta(
                compiler_status_before, compiler_status_after
            )

            if selective_macro_argument_calls_delta <= 0:
                raise RuntimeError(
                    "Selective macro diagnostic did not intercept a real workload call: "
                    f"delta={selective_macro_argument_calls_delta}; "
                    f"before={compiler_status_before!r}; after={compiler_status_after!r}"
                )

        valid_scoreadd_path_coverage_diagnostic = (
            args.scoreadd_path_coverage_diagnostic
            and command_callback_metrics is not None
            and score_add_metrics_active
            and score_add_callback_entries_delta is not None
            and score_add_callback_entries_in_scope_delta is not None
            and score_add_direct_successes_delta is not None
            and 0 < score_add_direct_successes_delta <= score_add_callback_entries_delta
            and score_add_executed_delta >= score_add_direct_successes_delta
            and 0 < optimized_score_add_callbacks <= score_add_callback_entries_in_scope_delta
            <= score_add_callback_entries_delta
            and generic_callbacks >= 0
        )

        valid_command_callback_metric_diagnostic = (
            callback_metrics_enabled
            and command_callback_metrics is not None
            and command_callback_metrics["total_ordinary_leaf_callbacks"] > 0
            and (
                not score_add_enabled
                or command_callback_metrics["optimized_score_add_leaf_callbacks"] > 0
            )
            and specialized_counter_matches is not False
        )

        result = {
            "benchmark": "PERF-011",
            "datapack": "Vein Miner 5.3.0 (26.3)",
            "datapack_sha256": sha256(PACK),
            "minecraft": "26.3 official server" if args.stack == "vanilla" else "26.3 Fabric Loom development server",
            "server_sha256": sha256(server_jar),
            "spark": "1.10.194 standalone-agent" if capture_spark else None,
            "spark_sha256": sha256(SPARK_AGENT) if capture_spark else None,
            "spark_capture_enabled": capture_spark,
            "jfr_cpu_capture_enabled": capture_jfr_cpu,
            "jfr_cpu_profile_path": (
                str(jfr_path.relative_to(ROOT)) if jfr_path else None
            ),
            "jfr_cpu_profile_sha256": (
                sha256(jfr_path) if jfr_path and jfr_path.is_file() else None
            ),
            "jfr_cpu_start_message": jfr_start_message,
            "jfr_cpu_stop_message": jfr_stop_message,
            "timing_instrumentation": timing_instrumentation,
            "stack": args.stack,
            "mods": {
                key: {"file": MODS[key][0], "sha256": MODS[key][1]}
                for key in STACK_MODS.get(args.stack, ())
            },
            "compiler_mode": args.compiler_mode if args.stack != "vanilla" else None,
            "command_callback_metrics_enabled": callback_metrics_enabled,
            "compiler_acceptance_audit_enabled": acceptance_audit_enabled,
            "compiler_exec_census_enabled": exec_census_enabled,
            "cpu004_mode": cpu004_mode if cpu004_enabled else None,
            "cpu005_mode": cpu005_mode if cpu005_enabled else None,
            "cpu005_start_status": cpu005_start_status,
            "cpu005_stop_status": cpu005_stop_status,
            "cpu004_start_status": cpu004_start_status,
            "cpu004_stop_status": cpu004_stop_status,
            "compiler_exec_census_namespace": (
                os.environ.get("FC_COMPILER_EXEC_CENSUS_NAMESPACE")
                if exec_census_enabled else None
            ),
            "compiler_exec_census_targets": (
                os.environ.get("FC_COMPILER_EXEC_CENSUS_FUNCTIONS")
                if exec_census_enabled else None
            ),
            "compiler_exec_census_start_status": exec_census_start_status,
            "compiler_exec_census_stop_status": exec_census_stop_status,
            "compiler_acceptance_audit_namespace": (
                os.environ.get("FC_COMPILER_ACCEPTANCE_NAMESPACE") if acceptance_audit_enabled else None
            ),
            "compiler_acceptance_dump_status": acceptance_dump_status,
            "selective_macro_arguments_metrics_enabled": selective_macro_metrics_enabled,
            "selective_macro_argument_calls_delta": selective_macro_argument_calls_delta,
            "selective_macro_diagnostics_delta": selective_macro_diagnostics_delta,
            "selective_macro_provider_class_delta": selective_macro_provider_class_delta,
            "selective_macro_diagnostics_before": compiler_status_before,
            "selective_macro_diagnostics_after": compiler_status_after,
            "callback_metrics_forced_wrapper": (
                callback_metrics_enabled and not compiler_enabled
            ),
            "diagnostic_only": bool(diagnostics) or capture_jfr_cpu,
            "compiler_status_before": compiler_status_before,
            "compiler_status_after": compiler_status_after,
            "command_callback_metrics": command_callback_metrics,
            "scenario": {
                "native_player_mining_packet": True,
                "survival_player": PLAYER_NAME,
                "diamond_pickaxe": True,
                "cube_side": args.side,
                "blocks_in_vein": args.side**3,
                "source_block": source,
                "work_expected": expected_work,
                "fixed_seed": 264010,
                "random_ticks": False,
                "natural_mob_spawning": False,
            },
            "target_marker_data_before_mining": target_data,
            "player_owner_id": owner,
            "player_mined_source_stat": source_stat,
            "saw_operation_run_state": saw_operation,
            "work_before": work_before,
            "work_after": work_after,
            "work_expected": expected_work,
            "run_state_after": run_after,
            "queue_head_before": head_before,
            "queue_head_after_capture": head_after_capture,
            "queue_head_delta": head_after_capture - head_before,
            "queue_stats_before": queue_stats_before,
            "queue_stats_after": queue_stats_after,
            "ray_stats_before": ray_stats_before,
            "ray_stats_after": ray_stats_after,
            "launch_to_rcon_seconds": launch_to_rcon_seconds,
            "score_add_compile_wall_ns": (
                stats_int(compiler_status, "score_add_compile_wall_ns")
                if compiler_status is not None else None
            ),
            "fused_compile_wall_ns": (
                stats_int(compiler_status, "fused_compile_wall_ns")
                if compiler_status is not None else None
            ),
            "vm_detection_acquire_target_fused_compiled": function_stats_value(
                function_stats(rcon, "vm:detection/acquire_target", compiler_enabled),
                "fused_regions_compiled",
            ),
            "queue_score_add_compiled": function_stats_value(queue_stats_after, "score_add_compiled"),
            "queue_score_add_executed_delta": (
                function_stats_value(queue_stats_after, "score_add_executed")
                - function_stats_value(queue_stats_before, "score_add_executed")
            ),
            "ray_score_add_executed_delta": (
                function_stats_value(ray_stats_after, "score_add_executed")
                - function_stats_value(ray_stats_before, "score_add_executed")
            ),
            "remaining_ore": remaining_ore,
            "source_block_remains": source_remains,
            "operation_markers_after": operation_markers,
            "target_markers_after": target_markers,
            "runtime_state_after_capture": runtime_state,
            "operation_completion_seconds": completion_elapsed,
            "completion_observation_timeout_seconds":args.capture_timeout,
            "event_timeout_reached":completion_elapsed is None,
            "event_progress_checkpoints":(
                event_progress_checkpoints if args.tick_stability_diagnostics else None
            ),
            "tick_pre_event_stability":tick_pre_event_stability,
            "tick_post_event_diagnostic":tick_post_event_diagnostic,
            "server_thread_event_cpu": event_cpu,
            "server_thread_event_cpu_enabled":args.capture_server_thread_cpu,
            "spark_capture_seconds": round(capture_seconds, 3) if capture_seconds is not None else None,
            "spark_interval_ms": PROFILE_INTERVAL_MS if capture_spark else None,
            "spark_thread_nodes": thread_nodes,
            "server_thread_stack_node_count": (
                server_thread["stack_node_count"] if server_thread is not None else None
            ),
            "server_function_manager_execute_weighted_ms": function_samples,
            "tick_query_after_capture": tick_query,
            "profile_path": str(profile_path.relative_to(ROOT)) if profile_path else None,
            "profile_sha256": sha256(profile_path) if profile_path else None,
            "profile_summary": server_thread,
            "fallback_observation": (
                "The native event completed the datapack's remaining queue, loot, block-removal, and player-work paths. "
                "Opt-in callback diagnostics count ordinary generic leaf callbacks and eligible ScoreAdd callbacks; "
                "modifiers and custom executors are outside that count."
            ),
            "valid_native_workload": (
                source_stat == 1
                and work_after == expected_work
                and run_after == 0
                and remaining_ore == 0
                and source_remains == 0
                and operation_markers == 0
                and head_after_capture > head_before
                and (not capture_spark or bool(thread_nodes))
            ),
            "valid_score_add_profile": (
                args.compiler_mode == "score-add"
                and function_stats_value(queue_stats_after, "score_add_compiled") > 0
                and head_after_capture > head_before
                and (not capture_spark or bool(thread_nodes))
            ),
            "valid_instrumented_invocation_diagnostic": (
                args.compiler_mode == "score-add-instrumented"
                and function_stats_value(queue_stats_after, "score_add_compiled") > 0
                and function_stats_value(queue_stats_after, "score_add_executed")
                - function_stats_value(queue_stats_before, "score_add_executed")
                == head_after_capture - head_before
            ),
            "valid_scoreadd_path_coverage_diagnostic": valid_scoreadd_path_coverage_diagnostic,
            "valid_command_callback_metric_diagnostic": (
                valid_command_callback_metric_diagnostic
                if callback_metrics_enabled
                else None
            ),
            "valid_selective_macro_profile": (
                args.compiler_mode == "selective-macro"
                and compiler_status_after is not None
                and "selective_macro_arguments_enabled=true" in compiler_status_after
                and head_after_capture > head_before
                and (not capture_spark or bool(thread_nodes))
                and (
                    not selective_macro_metrics_enabled
                    or bool(selective_macro_argument_calls_delta)
                )
            ),
            "fused_regions_compiled": (
                stats_int(compiler_status_after, "fused_regions_compiled")
                if compiler_status_after is not None
                else None
            ),
            "fused_regions_executed_delta": (
                stats_int(compiler_status_after, "fused_regions_executed")
                - stats_int(compiler_status_before, "fused_regions_executed")
                if compiler_status_after is not None
                and compiler_status_before is not None
                else None
            ),
            "score_add_executed_delta": (
                stats_int(compiler_status_after, "score_add_executed")
                - stats_int(compiler_status_before, "score_add_executed")
                if compiler_status_after is not None
                and compiler_status_before is not None
                else None
            ),
            "valid_fused_timed_profile": (
                args.compiler_mode == "fused-timed"
                and compiler_status_after is not None
                and stats_int(compiler_status_after, "fused_regions_compiled") > 0
                and stats_int(compiler_status_after, "score_add_compiled") > 0
                and "fused_region_prototype_enabled=true" in compiler_status_after
                and "score_add_metrics_enabled=false" in compiler_status_after
                and head_after_capture > head_before
            ),
            "valid_fused_profile": (
                args.compiler_mode == "fused"
                and compiler_status_after is not None
                and compiler_status_before is not None
                and stats_int(compiler_status_after, "fused_regions_compiled") > 0
                and stats_int(compiler_status_after, "fused_regions_executed")
                - stats_int(compiler_status_before, "fused_regions_executed")
                > 0
                and stats_int(compiler_status_after, "score_add_executed")
                - stats_int(compiler_status_before, "score_add_executed")
                > 0
                and head_after_capture > head_before
                and (not capture_spark or bool(thread_nodes))
            ),
        }
        manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if not result["valid_native_workload"]:
            raise RuntimeError(f"Native workload integrity failed: {json.dumps(result, indent=2)}")
        if args.compiler_mode == "score-add" and not result["valid_score_add_profile"]:
            raise RuntimeError(f"ScoreAdd profile gate failed: {json.dumps(result, indent=2)}")
        if args.compiler_mode == "score-add-instrumented" and not (
            result["valid_instrumented_invocation_diagnostic"]
            or (args.scoreadd_path_coverage_diagnostic
                and result["valid_scoreadd_path_coverage_diagnostic"])
        ):
            raise RuntimeError(f"Instrumented invocation gate failed: {json.dumps(result, indent=2)}")
        if callback_metrics_enabled and not (
            result["valid_command_callback_metric_diagnostic"]
            or (args.scoreadd_path_coverage_diagnostic
                and result["valid_scoreadd_path_coverage_diagnostic"])
        ):
            raise RuntimeError(
                f"Command callback diagnostic gate failed: {json.dumps(result, indent=2)}"
            )
        if args.compiler_mode == "selective-macro" and not result["valid_selective_macro_profile"]:
            raise RuntimeError(
                f"Selective macro profile gate failed: {json.dumps(result, indent=2)}"
            )
        if args.compiler_mode == "fused" and not result["valid_fused_profile"]:
            raise RuntimeError(
                f"Fused profile activation gate failed: {json.dumps(result, indent=2)}"
            )
        if args.compiler_mode == "fused-timed" and not result["valid_fused_timed_profile"]:
            raise RuntimeError(
                f"Fused timed profile gate failed: {json.dumps(result, indent=2)}"
            )

        bot.assert_connected()
        succeeded = True
        print(json.dumps({"output": str(output), "results": result}, indent=2))
        return 0
    finally:
        if jfr_started and jfr_pid is not None and jfr_path is not None:
            # An interrupted/failed gameplay event must not be retried; save
            # best-effort raw samples for forensic review without reclassification.
            try:
                subprocess.run(
                    ["jcmd", str(jfr_pid), "JFR.stop", "name=fc_comp_021",
                     f"filename={jfr_path.resolve()}"],
                    text=True, capture_output=True, timeout=15, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
        if spark is not None:
            try:
                stop_spark_shell(spark)
            except Exception:
                spark.terminate()
        if cpu005_started and rcon is not None:
            try:
                rcon.command("function_compiler_probe cpu005-stop")
            except Exception:
                pass
        if cpu004_started and rcon is not None:
            try:
                rcon.command("function_compiler_probe cpu004-stop")
            except Exception:
                pass
        if exec_census_started and rcon is not None:
            # An incomplete event must not be interpreted as an accepted census.
            # Preserve a partial dump for forensic review only.
            try:
                rcon.command("function_compiler_probe exec-census-stop")
            except Exception:
                pass
        if rcon is not None:
            try:
                rcon.command("stop")
            except Exception:
                rcon.close()
        if bot is not None:
            bot.close()
        if server is not None and server.poll() is None:
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        if log_handle is not None:
            log_handle.close()
        if cpu005_enabled and (work / "server.log").is_file():
            cpu_rows = [
                line for line in (work / "server.log").read_text(
                    errors="replace").splitlines()
                if "FC_CPU005_" in line
            ]
            (output / "cpu005.log").write_text(
                "\n".join(cpu_rows) + "\n", encoding="utf-8"
            )
        if cpu004_enabled and (work / "server.log").is_file():
            audit_rows = [
                line for line in (work / "server.log").read_text(
                    errors="replace").splitlines()
                if "FC_CPU004_" in line
            ]
            (output / "cpu004.log").write_text(
                "\n".join(audit_rows) + "\n", encoding="utf-8"
            )
        if exec_census_enabled and (work / "server.log").is_file():
            audit_rows = [
                line for line in (work / "server.log").read_text(
                    errors="replace").splitlines()
                if "FC_EXEC_" in line
            ]
            (output / "exec-census.log").write_text(
                "\n".join(audit_rows) + "\n", encoding="utf-8"
            )
        if acceptance_audit_enabled and (work / "server.log").is_file():
            # Preserve the complete bounded audit independently of the temporary server.
            # This is a post-event diagnostic, never a wall/CPU timing sample.
            audit_rows = [
                line for line in (work / "server.log").read_text(
                    errors="replace").splitlines()
                if "FC_ACCEPTANCE_" in line
            ]
            (output / "acceptance.log").write_text(
                "\n".join(audit_rows) + "\n", encoding="utf-8"
            )
        if not succeeded and (work / "server.log").is_file():
            (output / "failure.log").write_text(
                (work / "server.log").read_text(errors="replace")[-16000:],
                encoding="utf-8",
            )
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
