#!/usr/bin/env python3
"""Profile Blastback tick dispatch or its TNT restoration workload on a disposable server."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_spark_profile import summarize as summarize_spark_profile  # noqa: E402
from run_dynamic_lights_profile import MODS, MODS_DIR, OUTPUT_ROOT, STACK_MODS, sha256  # noqa: E402
from run_entity_datapack_profile import DrainingRconClient  # noqa: E402
from run_runtime_probe import locate_official_server_jar  # noqa: E402
from run_spawn_animations_profile import (  # noqa: E402
    start_spark_shell,
    stop_spark_shell,
    wait_for_spark_password,
)
from run_dynamic_lights_profile import spark_thread_node_count  # noqa: E402


PACK = ROOT / "references/real-world/candidates/Blastback-Hotfix-3-26.3.zip"
PACK_SHA256 = "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90"
SPARK_AGENT = ROOT / "references/real-world/spark-1.10.194/spark-1.10.194-standalone-agent.jar"
SPARK_SHA256 = "a048b2fe173008c1fd5cc4fc53bcd330b030350d7acdf0d147600c0fa556a3c9"
SERVER_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
SERVER_HOST = "127.0.0.1"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((SERVER_HOST, 0))
        return int(probe.getsockname()[1])


def wait_for_rcon(process: subprocess.Popen[bytes], port: int, password: str, timeout: float = 300) -> DrainingRconClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Minecraft server exited early with code {process.returncode}")
        try:
            return DrainingRconClient(SERVER_HOST, port, password)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(0.5)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def score(client: DrainingRconClient, holder: str, objective: str) -> int:
    response = client.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", response)
    if not match:
        raise RuntimeError(f"Could not read {holder} {objective}: {response!r}")
    return int(match.group(1))


def _status_int(status: str | None, key: str) -> int:
    if status is None:
        return 0
    match = re.search(rf"\b{re.escape(key)}=(\d+)", status)
    return int(match.group(1)) if match else 0


def count_entities(client: DrainingRconClient, holder: str, objective: str, selector: str) -> int:
    client.command(f"scoreboard players set {holder} {objective} 0")
    client.command(f"execute as {selector} run scoreboard players add {holder} {objective} 1")
    return score(client, holder, objective)


def write_setup_pack(path: Path, tnt_count: int) -> None:
    function_dir = path / "data/function_compiler_benchmark/function"
    function_dir.mkdir(parents=True)
    (path / "pack.mcmeta").write_text(
        json.dumps({"pack": {"description": "Function Compiler Blastback test fixture", "min_format": [121, 0], "max_format": [121, 0]}}, indent=2) + "\n",
        encoding="utf-8",
    )
    positions = [] if tnt_count == 0 else [(4, 64, 4)]
    if tnt_count == 4:
        positions = [(3, 64, 3), (3, 64, 5), (5, 64, 3), (5, 64, 5)]
    elif tnt_count == 32:
        positions = [(x, 64, z) for x in range(1, 8) for z in range(1, 8) if (x, z) != (4, 4)][:32]
    lines = [
        f'summon minecraft:tnt {x} {y} {z} {{Fuse:80s,Tags:["fc_blastback_probe"]}}'
        for x, y, z in positions
    ]
    (function_dir / "spawn_tnt.mcfunction").write_text("\n".join(lines) + "\n", encoding="utf-8")


def block_matches(client: DrainingRconClient, block: str, x: int, y: int, z: int) -> bool:
    client.command(f"execute store success score #block_check fc_probe run execute if block {x} {y} {z} minecraft:{block}")
    return score(client, "#block_check", "fc_probe") == 1


def region_matches_template(client: DrainingRconClient) -> bool:
    client.command(
        "execute store success score #region_check fc_probe run "
        "execute if blocks -4 56 -4 12 72 12 64 56 32 all"
    )
    return score(client, "#region_check", "fc_probe") == 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=("vanilla", *STACK_MODS), default="vanilla")
    parser.add_argument(
        "--compiler-mode",
        "--wrapper",
        dest="compiler_mode",
        choices=("off", "on", "wrapper", "score-add", "score-add-instrumented", "fused"),
        default="off",
        help="off, wrapper-only (on/wrapper), ScoreAdd, instrumented ScoreAdd, or fused prototype",
    )
    parser.add_argument("--tnt-count", type=int, choices=(0, 1, 4, 32), default=1,
                        help="use 0 for the no-TNT tick-dispatch profile")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--settle-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.compiler_mode == "on":
        args.compiler_mode = "wrapper"
    if args.stack == "vanilla" and args.compiler_mode != "off":
        parser.error("a non-off compiler mode requires a Fabric stack")
    if args.seconds < 5:
        parser.error("--seconds must be at least 5")
    if args.settle_seconds < 30:
        parser.error("--settle-seconds must be at least 30")
    return args


def main() -> int:
    args = parse_args()
    for path, expected, label in (
        (PACK, PACK_SHA256, "Blastback Hotfix 3"),
        (SPARK_AGENT, SPARK_SHA256, "Spark standalone agent"),
    ):
        if not path.is_file() or sha256(path) != expected:
            raise FileNotFoundError(f"Missing or mismatched pinned {label}: {path}")
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != SERVER_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server jar hash mismatch: {server_jar}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    output = OUTPUT_ROOT / f"blastback-{args.stack}-{args.compiler_mode}-tnt{args.tnt_count}-{run_id}"
    output.mkdir(parents=True, exist_ok=False)
    work = ROOT / "run" / f"blastback-{run_id}"
    work.mkdir(parents=True, exist_ok=False)
    server_port, rcon_port, spark_port = free_port(), free_port(), free_port()
    password = secrets.token_urlsafe(24)
    rcon: DrainingRconClient | None = None
    spark: subprocess.Popen[bytes] | None = None
    server: subprocess.Popen[bytes] | None = None
    log_handle = None
    profile_path: Path | None = None
    metadata_path = output / "manifest.json"
    success = False

    try:
        datapacks = work / "world/datapacks"
        datapacks.mkdir(parents=True)
        shutil.copy2(PACK, datapacks / "blastback.zip")
        fixture = datapacks / "function_compiler_benchmark"
        write_setup_pack(fixture, args.tnt_count)
        probe_pack = datapacks / "function_compiler_probe"
        shutil.copytree(ROOT / "src/main/resources/data", probe_pack / "data")
        (probe_pack / "pack.mcmeta").write_text(
            json.dumps({"pack": {"description": "Function Compiler wrapper probe", "min_format": [97, 1], "max_format": [97, 1]}}, indent=2) + "\n",
            encoding="utf-8",
        )
        if args.stack != "vanilla":
            mods_dir = work / "mods"
            mods_dir.mkdir()
            for mod_key in STACK_MODS[args.stack]:
                filename, _ = MODS[mod_key]
                shutil.copy2(MODS_DIR / filename, mods_dir / filename)

        (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        properties = {
            "enable-rcon": "true", "rcon.password": password, "rcon.port": str(rcon_port),
            "broadcast-rcon-to-ops": "false", "server-ip": SERVER_HOST, "server-port": str(server_port),
            "level-name": "world", "level-seed": "264010", "online-mode": "false", "white-list": "false",
            "spawn-protection": "0", "max-players": "1", "view-distance": "4", "simulation-distance": "4",
            "sync-chunk-writes": "false", "pause-when-empty-seconds": "-1",
        }
        (work / "server.properties").write_text("".join(f"{key}={value}\n" for key, value in properties.items()), encoding="utf-8")
        log_path = work / "server.log"
        log_handle = log_path.open("wb")
        if args.stack == "vanilla":
            command = ["java", "-Xms1G", "-Xmx4G", f"-javaagent:{SPARK_AGENT}=port={spark_port}", "-jar", str(server_jar), "nogui"]
            cwd = work
            env = None
        else:
            env = os.environ.copy()
            project_cache = ROOT / ".gradle-user-home"
            if "GRADLE_USER_HOME" not in env and project_cache.is_dir():
                env["GRADLE_USER_HOME"] = str(project_cache)
            shared_cache = Path.home() / ".gradle/caches"
            if "GRADLE_RO_DEP_CACHE" not in env and shared_cache.is_dir():
                env["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
            wrapper_enabled = args.compiler_mode != "off"
            score_add_enabled = args.compiler_mode in {"score-add", "score-add-instrumented", "fused"}
            score_add_metrics_enabled = args.compiler_mode in {"score-add-instrumented", "fused"}
            fused_enabled = args.compiler_mode == "fused"
            env.update(
                {
                    "FC_WRAPPER_PROBE": str(wrapper_enabled).lower(),
                    "FC_SCORE_ADD_PROTOTYPE": str(score_add_enabled).lower(),
                    "FC_SCORE_ADD_METRICS": str(score_add_metrics_enabled).lower(),
                    "FC_FUSED_REGION_PROTOTYPE": str(fused_enabled).lower(),
                    "FC_RUNTIME_TRACE": "false",
                }
            )
            gradle = [
                "--no-daemon",
                "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
                "-PfcJvmArgs=-Xms512M,-Xmx2G",
                f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
                f"-PfcSparkAgentPath={SPARK_AGENT}",
                f"-PfcSparkPort={spark_port}",
                "runServer",
            ]
            if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
                gradle.insert(0, "--offline")
            command = [str(ROOT / "gradlew"), *gradle]
            cwd = ROOT
        server = subprocess.Popen(command, cwd=cwd, stdout=log_handle, stderr=subprocess.STDOUT, env=env)
        rcon = wait_for_rcon(server, rcon_port, password, timeout=300)
        enabled = rcon.command("datapack list enabled")
        if "blastback" not in enabled.casefold():
            raise RuntimeError(f"Blastback did not enable: {enabled!r}")
        compiler_status = None
        if args.stack != "vanilla":
            compiler_status = rcon.command("function_compiler_probe status")
            wrapper_enabled = args.compiler_mode != "off"
            for invariant in (
                "FC_PROBE present=true",
                f"wrapped={str(wrapper_enabled).lower()}",
                "tag_same_instance=true",
                "delegates_original=true",
            ):
                if invariant not in compiler_status:
                    raise RuntimeError(f"Function Compiler wrapper probe failed ({invariant}): {compiler_status!r}")

        rcon.command("gamerule sendCommandFeedback false")
        rcon.command("gamerule doMobSpawning false")
        rcon.command("gamerule doDaylightCycle false")
        rcon.command("gamerule randomTickSpeed 0")
        rcon.command("gamerule maxEntityCramming 10000")
        rcon.command("difficulty peaceful")
        rcon.command("scoreboard objectives add fc_probe dummy")
        no_event_dispatch = args.tnt_count == 0
        witnesses = {
            "gold": (2, 63, 4), "diamond_block": (4, 63, 4), "redstone_block": (6, 63, 4),
            "emerald_block": (4, 63, 6), "control_stone": (12, 63, 12),
        }
        block_ids = {
            "gold": "gold_block", "diamond_block": "diamond_block", "redstone_block": "redstone_block",
            "emerald_block": "emerald_block", "control_stone": "stone",
        }
        clone_response = None
        before: dict[str, bool] = {}
        template_matches: bool | None = None
        if not no_event_dispatch:
            rcon.command("forceload add -16 -16 16 16")
            rcon.command("forceload add 64 32")
            rcon.command("fill -4 63 -4 12 63 12 minecraft:stone")
            for name, (x, y, z) in witnesses.items():
                if name != "control_stone":
                    rcon.command(f"setblock {x} {y} {z} minecraft:{block_ids[name]}")
            clone_response = rcon.command("clone -4 56 -4 12 72 12 64 56 32 replace force")
            before = {name: block_matches(rcon, block, *witnesses[name]) for name, block in block_ids.items()}
            template_matches = region_matches_template(rcon)
            if not all(before.values()) or not template_matches:
                raise RuntimeError(
                    f"World witness/template setup failed: witnesses={before}, "
                    f"template_matches={template_matches}, clone={clone_response!r}"
                )

        spark_password = wait_for_spark_password(log_path, server)
        spark = start_spark_shell(work, spark_password, spark_port)
        assert spark.stdin is not None
        tick_id_before = score(rcon, "#tick_id", "erb.cfg")
        compiler_status_before_profile = (
            rcon.command("function_compiler_probe status") if args.stack != "vanilla" else None
        )
        compiler_function_stats_before_profile = (
            rcon.command("function_compiler_probe stats erb:runtime_tick")
            if args.stack != "vanilla"
            else None
        )
        profile_started = time.monotonic()
        spark.stdin.write(b"spark profiler start --interval 4 --thread *\n")
        spark.stdin.flush()
        time.sleep(1)
        setup_response = (
            None if no_event_dispatch else rcon.command("function function_compiler_benchmark:spawn_tnt")
        )
        spawned = count_entities(rcon, "#fixture_tnt", "fc_probe", "@e[type=minecraft:tnt,tag=fc_blastback_probe]")
        if spawned != args.tnt_count:
            raise RuntimeError(f"Expected {args.tnt_count} tagged TNT; found {spawned}; setup={setup_response!r}")
        event_offset = time.monotonic() - profile_started
        time.sleep(args.seconds)
        spark_output = stop_spark_shell(spark)
        spark = None
        tick_id_after_capture = score(rcon, "#tick_id", "erb.cfg")
        compiler_status_after_capture = (
            rcon.command("function_compiler_probe status") if args.stack != "vanilla" else None
        )
        compiler_function_stats_after_capture = (
            rcon.command("function_compiler_probe stats erb:runtime_tick")
            if args.stack != "vanilla"
            else None
        )
        profiles = list(work.rglob("*.sparkprofile"))
        if not profiles:
            raise RuntimeError(f"Spark did not save a profile: {spark_output[-1000:]}")
        profile_path = output / "blastback.sparkprofile"
        shutil.copy2(max(profiles, key=lambda path: path.stat().st_mtime), profile_path)
        thread_nodes = spark_thread_node_count(profile_path)
        if thread_nodes == 0:
            raise RuntimeError("Spark saved no thread sample nodes")

        # Do not inject status calls into the capture window. Poll only after the profile stops.
        settle_deadline = time.monotonic() + args.settle_seconds
        outstanding: dict[str, int] = {}
        region_restored: bool | None = None if no_event_dispatch else False
        while time.monotonic() < settle_deadline:
            rcon.command("function erb:status/collect")
            outstanding = {
                "tnt": count_entities(rcon, "#fixture_tnt", "fc_probe", "@e[type=minecraft:tnt,tag=fc_blastback_probe]"),
                "captures": score(rcon, "#captures_active", "erb.cfg"),
                "groups": score(rcon, "#groups_active", "erb.cfg"),
                "verification": score(rcon, "#verification_active", "erb.cfg"),
                "protected": score(rcon, "#protected_active", "erb.cfg"),
                "watchers": score(rcon, "#watchers_active", "erb.cfg"),
                "unresolved": score(rcon, "#unresolved_active", "erb.cfg"),
            }
            no_event_dispatch_drained = no_event_dispatch and all(
                outstanding[key] == 0
                for key in ("tnt", "captures", "verification", "protected", "watchers", "unresolved")
            )
            if no_event_dispatch_drained or all(value == 0 for value in outstanding.values()):
                diagnostic_counts = {
                    "job_markers": count_entities(rcon, "#diag_jobs", "fc_probe", "@e[type=minecraft:marker,tag=erb.job_marker]"),
                    "restore_jobs": count_entities(rcon, "#diag_restores", "fc_probe", "@e[type=minecraft:marker,tag=erb.restore_job]"),
                    "block_markers": count_entities(rcon, "#diag_blocks", "fc_probe", "@e[type=minecraft:marker,tag=erb.block]"),
                    "group_members": count_entities(rcon, "#diag_members", "fc_probe", "@e[type=minecraft:marker,tag=erb.group_member]"),
                    "danger_zones": count_entities(rcon, "#diag_danger", "fc_probe", "@e[type=minecraft:marker,tag=erb.danger_zone]"),
                    "protected_items": count_entities(rcon, "#diag_items", "fc_probe", "@e[type=minecraft:item,tag=erb.protected]"),
                }
                region_restored = None if no_event_dispatch else region_matches_template(rcon)
                no_event_diagnostics = all(
                    diagnostic_counts[key] == 0
                    for key in (
                        "job_markers", "restore_jobs", "block_markers", "group_members",
                        "danger_zones", "protected_items",
                    )
                )
                if no_event_dispatch_drained or (region_restored and no_event_diagnostics):
                    break
            time.sleep(5)
        after = (
            {}
            if no_event_dispatch
            else {name: block_matches(rcon, block, *witnesses[name]) for name, block in block_ids.items()}
        )
        tick_id_after = score(rcon, "#tick_id", "erb.cfg")
        compiler_status_after_profile = (
            rcon.command("function_compiler_probe status") if args.stack != "vanilla" else None
        )
        region_restored = None if no_event_dispatch else region_matches_template(rcon)
        diagnostics = {
            "job_markers": count_entities(rcon, "#diag_jobs", "fc_probe", "@e[type=minecraft:marker,tag=erb.job_marker]"),
            "restore_jobs": count_entities(rcon, "#diag_restores", "fc_probe", "@e[type=minecraft:marker,tag=erb.restore_job]"),
            "block_markers": count_entities(rcon, "#diag_blocks", "fc_probe", "@e[type=minecraft:marker,tag=erb.block]"),
            "group_members": count_entities(rcon, "#diag_members", "fc_probe", "@e[type=minecraft:marker,tag=erb.group_member]"),
            "danger_zones": count_entities(rcon, "#diag_danger", "fc_probe", "@e[type=minecraft:marker,tag=erb.danger_zone]"),
            "protected_items": count_entities(rcon, "#diag_items", "fc_probe", "@e[type=minecraft:item,tag=erb.protected]"),
            "max_job_quiet": score(rcon, "#max_quiet", "erb.tmp"),
            "max_group_member_count": score(rcon, "#max_group", "erb.tmp"),
        }
        tick_query = rcon.command("tick query")
        summary = summarize_spark_profile(profile_path, "Server thread", 40)
        thread_summary = summary["matched_threads"][0]
        callback_sampled = any(
            method.get("class") == "net.minecraft.world.level.timers.FunctionCallback"
            and method.get("method") == "handle"
            for method in thread_summary.get("top_methods", [])
        )
        function_manager_execute_samples = sum(
            method.get("inclusive_weighted_value", 0)
            for method in thread_summary.get("top_methods", [])
            if method.get("class") == "net.minecraft.server.ServerFunctionManager"
            and method.get("method") == "execute"
        )
        no_event_integrity = (
            no_event_dispatch
            and spawned == 0
            and all(
                outstanding[key] == 0
                for key in ("tnt", "captures", "verification", "protected", "watchers", "unresolved")
            )
            and all(
                diagnostics[key] == 0
                for key in (
                    "job_markers", "restore_jobs", "block_markers", "group_members",
                    "danger_zones", "protected_items",
                )
            )
        )
        restored = None if no_event_dispatch else all(after.values())
        quiescent = None if no_event_dispatch else (
            all(value == 0 for value in outstanding.values())
            and all(
                diagnostics[key] == 0
                for key in (
                    "job_markers", "restore_jobs", "block_markers", "group_members",
                    "danger_zones", "protected_items",
                )
            )
        )
        restoration_gate_passed = None if no_event_dispatch else (
            thread_nodes > 0
            and restored
            and region_restored
            and quiescent
        )
        metadata = {
            "benchmark": "PERF-010",
            "purpose": (
                "Blastback scheduled no-event dispatch ScoreAdd eligibility/profile pilot; no TNT event is started"
                if no_event_dispatch
                else "Blastback TNT capture/restoration workload; profile pilot, not an optimization result"
            ),
            "minecraft": "26.3 official server" if args.stack == "vanilla" else "26.3 Fabric Loom development server",
            "server_sha256": sha256(server_jar), "spark": "1.10.194 standalone-agent", "spark_sha256": sha256(SPARK_AGENT),
            "datapack": "Blastback Hotfix 3 (26.3)", "datapack_sha256": sha256(PACK), "datapack_enabled": True,
            "stack": args.stack, "mods": {key: {"file": MODS[key][0], "sha256": MODS[key][1]} for key in STACK_MODS.get(args.stack, ())},
            "compiler_mode": args.compiler_mode if args.stack != "vanilla" else None,
            "wrapper_mode": args.compiler_mode if args.stack != "vanilla" else None,
            "wrapper_probe_status": compiler_status,
            "scenario": (
                "Blastback installed with its normal #minecraft:tick dispatcher; zero TNT actors; seed 264010; "
                "random ticks and mob spawns disabled; forced chunks; no player actors"
                if no_event_dispatch
                else f"17x17x17 source volume cloned to a protected template; {args.tnt_count} tagged TNT with 80 tick fuse; seed 264010; random ticks and mob spawns disabled; forced chunks; no player actors"
            ),
            "template_clone_response": clone_response,
            "profile_seconds": args.seconds, "event_spawned_seconds_after_profile_start": round(event_offset, 3),
            "tick_id_before_profile": tick_id_before,
            "tick_id_after_capture": tick_id_after_capture,
            "tick_id_delta_during_capture": tick_id_after_capture - tick_id_before,
            "tick_id_after_profile": tick_id_after,
            "tick_id_delta": tick_id_after - tick_id_before,
            "compiler_status_before_profile": compiler_status_before_profile,
            "compiler_status_after_capture": compiler_status_after_capture,
            "compiler_status_after_profile": compiler_status_after_profile,
            "compiler_function_stats_before_profile": compiler_function_stats_before_profile,
            "compiler_function_stats_after_capture": compiler_function_stats_after_capture,
            "runtime_tick_score_add_compiled": _status_int(
                compiler_function_stats_after_capture, "score_add_compiled"
            ),
            "runtime_tick_score_add_executed_during_capture": (
                _status_int(compiler_function_stats_after_capture, "score_add_executed")
                - _status_int(compiler_function_stats_before_profile, "score_add_executed")
            ),
            "score_add_compiled": _status_int(compiler_status_after_capture, "score_add_compiled"),
            "score_add_executed_during_capture": (
                _status_int(compiler_status_after_capture, "score_add_executed")
                - _status_int(compiler_status_before_profile, "score_add_executed")
            ),
            "fused_regions_compiled": _status_int(compiler_status_after_capture, "fused_regions_compiled"),
            "fused_regions_executed_during_capture": (
                _status_int(compiler_status_after_capture, "fused_regions_executed")
                - _status_int(compiler_status_before_profile, "fused_regions_executed")
            ),
            "settle_timeout_seconds": args.settle_seconds,
            "spark_thread_nodes": thread_nodes, "server_thread_stack_node_count": thread_summary["stack_node_count"],
            "tnt_spawned": spawned, "post_settle_scheduler_state": outstanding,
            "witnesses_before": before, "witnesses_after": after, "world_witnesses_restored": restored,
            "template_region_matches": region_restored, "post_settle_entity_diagnostics": diagnostics,
            "scheduled_function_callback_sampled": callback_sampled, "workload_quiescent": quiescent,
            "no_event_integrity": no_event_integrity if no_event_dispatch else None,
            "server_function_manager_execute_sampled": function_manager_execute_samples > 0,
            "server_function_manager_execute_weighted_ms": function_manager_execute_samples,
            "tick_query_after_settle": tick_query,
            "profile_sha256": sha256(profile_path), "profile_summary": thread_summary,
            "restoration_gate_passed": restoration_gate_passed,
            "valid_for_restoration_comparison": restoration_gate_passed,
            "valid_for_no_event_dispatch_profile": (
                no_event_dispatch
                and no_event_integrity
                and tick_id_after_capture > tick_id_before
                and thread_nodes > 0
                and (
                    args.stack == "vanilla"
                    or args.compiler_mode in {"off", "wrapper"}
                    or (
                        args.compiler_mode in {"score-add", "score-add-instrumented"}
                        and _status_int(compiler_function_stats_after_capture, "score_add_compiled") > 0
                        and (
                            args.compiler_mode == "score-add"
                            or _status_int(compiler_function_stats_after_capture, "score_add_executed")
                            > _status_int(compiler_function_stats_before_profile, "score_add_executed")
                        )
                    )
                    or (
                        args.compiler_mode == "fused"
                        and _status_int(compiler_status_after_capture, "fused_regions_compiled") > 0
                        and _status_int(compiler_status_after_capture, "fused_regions_executed")
                        > _status_int(compiler_status_before_profile, "fused_regions_executed")
                    )
                )
            ),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if no_event_dispatch and not metadata["valid_for_no_event_dispatch_profile"]:
            raise RuntimeError(
                "Blastback no-event dispatch gate failed: "
                f"tick_id={tick_id_before}->{tick_id_after_capture}, "
                f"compiler={compiler_status_before_profile!r}->{compiler_status_after_capture!r}"
            )
        if not no_event_dispatch and not restoration_gate_passed:
            raise RuntimeError(
                f"Blastback restoration gate failed: scheduler={outstanding}, "
                f"witnesses={after}, template_region_matches={region_restored}"
            )
        success = True
        print(json.dumps({"run_id": run_id, "output": str(output), "metadata": metadata}, indent=2))
        return 0
    finally:
        if spark is not None:
            try:
                stop_spark_shell(spark)
            except Exception:
                spark.terminate()
        if rcon is not None:
            try:
                rcon.command("stop")
            except Exception:
                rcon.close()
        if server is not None and server.poll() is None:
            try:
                server.wait(timeout=25)
            except subprocess.TimeoutExpired:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        if log_handle is not None:
            log_handle.close()
        if not success:
            failure_log = work / "server.log"
            if failure_log.exists():
                (output / "failure.log").write_text(failure_log.read_text(errors="replace")[-12000:], encoding="utf-8")
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
