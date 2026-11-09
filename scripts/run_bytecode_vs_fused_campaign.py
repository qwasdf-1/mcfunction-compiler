#!/usr/bin/env python3
"""BC-06: the paired bytecode-vs-fused region performance campaign.

The coverage row BC-06 claims a *measured win over fused interpretation on a
declared workload*, which is a campaign, not a fixture. This script mirrors
the house paired-campaign structure (the Vein Miner and sustained-fused
campaigns): counterbalanced pairs, a predeclared seed, a screening phase
that estimates variance, then a confirmatory phase whose pair count and
minimum worthwhile gain are predeclared before its first arm, analysed with
the shared exact-median paired analysis.

Pre-declared design
-------------------
* Declared workload: `tests/fixtures/function_compiler_fused_sustained` on
  the pinned, hash-verified official 26.3 server (`fabric` stack), the same
  sustained adjacent-eligible workload PERF-016 measured: 110 idle ticks,
  110 warmup active ticks, then 5 measurement windows of 110 active ticks
  with the `/tick query` summary spanning the last 100, and 3 post-workload
  idle windows for attribution. The primary metric is the
  workload-attributable active tick average (active average minus
  post-workload idle average), which charges the arm only for the
  workload's own ticks.
* Baseline arm: `fused` (the canonical fused-interpreted configuration -
  wrapper and ScoreAdd specialization active, fused region prototype active,
  bytecode region prototype inactive). Candidate arm: `bytecode` (wrapper
  and ScoreAdd specialization active, *bytecode* region prototype active,
  fused region prototype inactive). Everything else in the configuration is
  identical, so the pair isolates the region backend.
* Activation gate: before pairs, a diagnostic arm per backend asserts the
  backend's regions actually execute (fused: fused_regions_executed equals
  the active ticks and score_add_executed covers every eligible add;
  bytecode: bytecode_regions_executed equals the active ticks) and that the
  other backend's counters stay at zero. A pair whose either arm fails
  activation, workload integrity, or the arm parity (adds per active tick
  equal to the mod-free vanilla reference) is a failed campaign run, not a
  missing measurement.
* Screening phase: 5 counterbalanced pairs with the predeclared seed
  26871050 and no threshold, whose variance fixes the confirmatory pair
  count and whose medians inform (never override) the predeclared minimum
  gain.
* Confirmatory phase: at least 6 pairs, a predeclared `--minimum-gain-percent`
  supplied before its first arm, and the same seed. The decision comes from
  the shared exact-median interval analysis and uses the house vocabulary
  (`does_not_meet_threshold` / meets the predeclared gain).
* Every arm records the 1-minute host load average at start and reruns once
  if it exceeds the CPU count, retaining both results.
"""

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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mc-tooling" / "mc-harness"))

from mod_artifacts import MODS, MODS_DIR, STACK_MODS  # noqa: E402
from mc_harness import assert_version  # noqa: E402
from mc_harness.paired_stats import (  # noqa: E402
    paired_percent_changes,
    summarize_paired_changes,
)
from mc_harness.server_lifecycle import MINECRAFT_SERVER_SHA256  # noqa: E402

#: The harness version this campaign was verified against (roadmap step 6 pin).
HARNESS_PIN = "1.0.0"

assert_version(HARNESS_PIN)
from run_entity_datapack_profile import DrainingRconClient  # noqa: E402
from run_fused_region_sustained import (  # noqa: E402
    ADDS_PER_TICK,
    FIXTURE,
    HOST,
    IDLE_TICKS,
    IDLE_WINDOWS,
    MEASUREMENT_WINDOWS,
    TICKS_PER_WINDOW,
    WARMUP_ACTIVE_TICKS,
    connect_player_when_ready,
    generated_files,
    median_window,
    reserve_ports,
    score,
    tick_metrics,
    wait_for_rcon,
    wait_for_score,
)
from run_runtime_probe import (  # noqa: E402
    generate_packet_ids,
    locate_official_server_jar,
)
from player_bot import PacketIds, PlayerBot  # noqa: E402

OUTPUT_ROOT = ROOT / "build/benchmarks/BC-06"
RUN_ROOT = ROOT / "run"
BASELINE_ARM = "fused"
CANDIDATE_ARM = "bytecode"
DEFAULT_SEED = 26871050
ARMS = (BASELINE_ARM, CANDIDATE_ARM)
ACTIVE_REPORT_PATH: Path | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def server_environment(mode: str, diagnostic: bool) -> dict[str, str]:
    """The two arms differ only in which region prototype is active."""
    environment = os.environ.copy()
    project_cache = ROOT / ".gradle-user-home"
    if "GRADLE_USER_HOME" not in environment and project_cache.is_dir():
        environment["GRADLE_USER_HOME"] = str(project_cache)
    shared_cache = Path.home() / ".gradle/caches"
    if "GRADLE_RO_DEP_CACHE" not in environment and shared_cache.is_dir():
        environment["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
    environment.update(
        {
            # Both arms wrap functions and specialize the ScoreAdd family,
            # matching the runtime probe's canonical fused-interpreted and
            # bytecode-emitted modes; metrics/timers stay off except in the
            # diagnostic arm.
            "FC_WRAPPER_PROBE": "true",
            "FC_SCORE_ADD_PROTOTYPE": "true",
            "FC_SCORE_ADD_METRICS": "true",
            "FC_SCORE_ADD_TIMING": "false",
            "FC_FUSED_REGION_PROTOTYPE": (
                "true" if mode == BASELINE_ARM else "false"
            ),
            "FC_BYTECODE_REGION_PROTOTYPE": (
                "true" if mode == CANDIDATE_ARM else "false"
            ),
            "FC_BYTECODE_FORCE_COMPILE_FAILURE": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": "false",
            "FC_COMMAND_CALLBACK_METRICS": "false",
            "FC_FUNCTION_TIMING": "false",
            "FC_RUNTIME_TRACE": "false",
        }
    )
    if not diagnostic:
        environment["FC_SCORE_ADD_METRICS"] = "false"
    return environment


def prepare_workdir(
    work: Path,
    *,
    mode: str,
    stack: str,
    server_port: int,
    rcon_port: int,
    password: str,
) -> None:
    world = work / "world"
    datapack_dir = world / "datapacks" / FIXTURE.name
    shutil.copytree(FIXTURE, datapack_dir)
    for relative, contents in generated_files().items():
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


def setup_fixture(rcon: DrainingRconClient, mode: str) -> str | None:
    enabled = rcon.command("datapack list enabled")
    if FIXTURE.name not in enabled:
        raise RuntimeError(f"Sustained fused fixture did not load: {enabled!r}")
    rcon.command("gamerule doMobSpawning false")
    rcon.command("gamerule doDaylightCycle false")
    rcon.command("gamerule randomTickSpeed 0")
    rcon.command("forceload add 0 0 15 15")
    for holder in ("#enabled", "#server_ticks", "#active_ticks", "#fused"):
        rcon.command(f"scoreboard players set {holder} fc_fused 0")
    rcon.command("scoreboard players get #fused fc_fused")
    compiler_status = None
    if mode != "vanilla":
        compiler_status = rcon.command("function_compiler_probe status")
        for label, expected in (
            ("wrapper_enabled", True),
            ("score_add_prototype_enabled", True),
            ("fused_region_prototype_enabled", mode == BASELINE_ARM),
            ("bytecode_region_prototype_enabled", mode == CANDIDATE_ARM),
            ("selective_macro_arguments_enabled", False),
            ("score_add_prototype_enabled", True),
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
) -> dict[str, object]:
    work = RUN_ROOT / f"bc06-{run_id}-{arm_name}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    server_port, rcon_port = reserve_ports(2)
    password = f"fc-bc06-{os.getpid()}-{arm_name}"
    load_average_start = round(os.getloadavg()[0], 2)
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
        bot, player_login_attempts = connect_player_when_ready(
            server, server_port, packet_ids
        )
        rcon.command("gamemode spectator FCFused")
        rcon.command("tp FCFused 4 100 4")
        compiler_status = setup_fixture(rcon, mode=mode)

        server_tick_start = score(rcon, "#server_ticks")
        wait_for_score(server, rcon, "#server_ticks", server_tick_start + IDLE_TICKS)
        idle_timings = tick_metrics(rcon.command("tick query"))
        rcon.command("scoreboard players set #enabled fc_fused 1")
        active_ticks_observed = wait_for_score(
            server, rcon, "#active_ticks", WARMUP_ACTIVE_TICKS, timeout_seconds=600
        )
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
            wait_for_score(server, rcon, "#server_ticks", idle_mark + IDLE_TICKS)
            idle_windows.append(tick_metrics(rcon.command("tick query")))
        post_idle_timings = median_window(idle_windows)
        adds_applied = score(rcon, "#fused")
        server_ticks = score(rcon, "#server_ticks")
        ticks = score(rcon, "#active_ticks")
        expected_adds = ticks * ADDS_PER_TICK
        if adds_applied != expected_adds:
            raise RuntimeError(
                f"Workload integrity failed: active_ticks={ticks}, adds={adds_applied}, "
                f"expected adds={expected_adds} ({ADDS_PER_TICK} adds per active tick)"
            )
        activation = None
        if diagnostic:
            status_after = rcon.command("function_compiler_probe status")
            fused_regions_executed = read_status_counts(
                status_after, "fused_regions_executed"
            )
            bytecode_regions_executed = read_status_counts(
                status_after, "bytecode_regions_executed"
            )
            fused_regions_compiled = read_status_counts(
                status_after, "fused_regions_compiled"
            )
            bytecode_regions_compiled = read_status_counts(
                status_after, "bytecode_regions_compiled"
            )
            score_add_executed = read_status_counts(status_after, "score_add_executed")
            expected_region_adds = ticks * ADDS_PER_TICK
            if mode == BASELINE_ARM:
                if fused_regions_executed != ticks:
                    raise RuntimeError(
                        "Fused activation mismatch: "
                        f"executed={fused_regions_executed}, active_ticks={ticks}"
                    )
                if bytecode_regions_executed != 0:
                    raise RuntimeError(
                        "Fused arm executed bytecode regions: "
                        f"{bytecode_regions_executed}"
                    )
                if score_add_executed < expected_region_adds:
                    raise RuntimeError(
                        "Specialized commands did not execute inside the fused "
                        f"region: score_add_executed={score_add_executed}, "
                        f"expected at least {expected_region_adds}"
                    )
            if mode == CANDIDATE_ARM:
                if bytecode_regions_executed != ticks:
                    raise RuntimeError(
                        "Bytecode activation mismatch: "
                        f"executed={bytecode_regions_executed}, active_ticks={ticks}; "
                        "the workload's one contiguous eligible block must compile "
                        "and execute once per active tick"
                    )
                if fused_regions_executed != 0:
                    raise RuntimeError(
                        "Bytecode arm executed fused regions: "
                        f"{fused_regions_executed}"
                    )
                if score_add_executed < expected_region_adds:
                    raise RuntimeError(
                        "Specialized commands did not execute inside the bytecode "
                        f"region: score_add_executed={score_add_executed}, "
                        f"expected at least {expected_region_adds}"
                    )
            activation = {
                "mode": mode,
                "fused_regions_compiled": fused_regions_compiled,
                "fused_regions_executed": fused_regions_executed,
                "bytecode_regions_compiled": bytecode_regions_compiled,
                "bytecode_regions_executed": bytecode_regions_executed,
                "active_ticks": ticks,
                "score_add_compiled": read_status_counts(
                    status_after, "score_add_compiled"
                ),
                "score_add_executed": score_add_executed,
                "exact": (
                    fused_regions_executed == ticks
                    if mode == BASELINE_ARM
                    else bytecode_regions_executed == ticks
                ),
            }

        if server.poll() is not None:
            raise RuntimeError(f"Minecraft exited during arm {arm_name}")
        rcon.command("stop")
        server.wait(timeout=60)
        state = {
            "active_ticks": ticks,
            "server_ticks": server_ticks,
            "adds_applied": adds_applied,
            "adds_per_active_tick": adds_applied / ticks,
            "expected_adds_per_active_tick": ADDS_PER_TICK,
            "exact_workload_integrity": adds_applied == expected_adds,
        }
        return {
            "arm": arm_name,
            "mode": mode,
            "stack": stack if mode != "vanilla" else "mod-free-vanilla",
            "diagnostic_only": diagnostic,
            "instrumentation": "no Spark; /tick query only",
            "load_average_1m_start": load_average_start,
            "noisy_by_declared_rule": load_average_start > os.cpu_count(),
            "warmup_active_ticks": WARMUP_ACTIVE_TICKS,
            "active_tick_threshold_observed": active_ticks_observed,
            "active_tick_count_at_stop": ticks,
            "idle_ticks_before_workload": IDLE_TICKS,
            "tick_query_window_ticks": 100,
            "measurement_windows": MEASUREMENT_WINDOWS,
            "pre_workload_settle_tick_timings_ms": idle_timings,
            "active_window_timings_ms": active_windows,
            "post_workload_idle_window_timings_ms": idle_windows,
            "post_workload_idle_tick_timings_ms": post_idle_timings,
            "active_tick_timings_ms": active_timings,
            "workload_attributable_tick_average_ms": round(
                active_timings["tick_average_ms"] - post_idle_timings["tick_average_ms"],
                6,
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


def make_report(args: argparse.Namespace) -> None:
    server_jar = locate_official_server_jar()
    if sha256(server_jar) != MINECRAFT_SERVER_SHA256:
        raise RuntimeError(f"Minecraft 26.3 server hash mismatch: {server_jar}")
    packet_ids = generate_packet_ids(server_jar)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = OUTPUT_ROOT / f"{args.stack}-{args.phase}-{args.pairs}pairs-{run_id}"
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "results.json"
    global ACTIVE_REPORT_PATH
    ACTIVE_REPORT_PATH = report_path
    report: dict[str, object] = {
        "benchmark": "BC-06",
        "row": "measured win over fused interpretation on a declared workload",
        "phase": args.phase,
        "minecraft": "26.3",
        "server_sha256": sha256(server_jar),
        "stack": args.stack,
        "mods": [
            {"file": MODS[key][0], "sha256": sha256(MODS_DIR / MODS[key][0])}
            for key in STACK_MODS[args.stack]
        ],
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "fixture_sha256": {
            str(path.relative_to(FIXTURE)): sha256(path)
            for path in sorted(FIXTURE.rglob("*"))
            if path.is_file()
        },
        "baseline_arm": BASELINE_ARM,
        "candidate_arm": CANDIDATE_ARM,
        "primary_metric": "workload_attributable_tick_average_ms",
        "predeclared": {
            "seed": args.seed,
            "pairs": args.pairs,
            "minimum_gain_percent": args.minimum_gain_percent,
            "host_noise_rule": (
                "1-minute load average above the CPU count marks an arm noisy and "
                "it is repeated once; both results are retained"
            ),
        },
        "arms": [],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

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

    for mode in ARMS:
        diagnostic = run_arm(
            run_id=run_id,
            arm_name=f"activation-diagnostic-{mode}",
            mode=mode,
            stack=args.stack,
            server_jar=server_jar,
            packet_ids=packet_ids,
            output_dir=output_dir,
            diagnostic=True,
        )
        report[f"activation_diagnostic_{mode}"] = diagnostic
        report["arms"].append(diagnostic)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        activation = diagnostic["activation_diagnostic"]
        if activation is None or not activation["exact"]:
            raise RuntimeError(f"{mode} activation diagnostic was not exact")

    rng = random.Random(args.seed)
    pair_orders: list[list[str]] = [
        [BASELINE_ARM, CANDIDATE_ARM] for _ in range(args.pairs // 2)
    ]
    pair_orders.extend([CANDIDATE_ARM, BASELINE_ARM] for _ in range(args.pairs // 2))
    if args.pairs % 2:
        pair_orders.append(
            [BASELINE_ARM, CANDIDATE_ARM]
            if rng.randrange(2) == 0
            else [CANDIDATE_ARM, BASELINE_ARM]
        )
    rng.shuffle(pair_orders)

    pairs: list[dict[str, object]] = []
    for pair_index in range(1, args.pairs + 1):
        order = pair_orders[pair_index - 1]
        pair_arms: dict[str, dict[str, object]] = {}
        print(
            f"Starting BC-06 pair {pair_index}/{args.pairs}: {order}", flush=True
        )
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
        vanilla_rate = vanilla["state"]["adds_per_active_tick"]
        if any(
            arm["state"]["adds_per_active_tick"] != vanilla_rate
            or not arm["state"]["exact_workload_integrity"]
            for arm in pair_arms.values()
        ):
            raise RuntimeError(
                f"BC-06 pair {pair_index} lost workload parity with the vanilla "
                f"reference: {vanilla_rate} adds per active tick expected"
            )
        baseline = pair_arms[BASELINE_ARM]
        candidate = pair_arms[CANDIDATE_ARM]
        for label, arm in pair_arms.items():
            if arm["noisy_by_declared_rule"]:
                repeat = run_arm(
                    run_id=run_id,
                    arm_name=f"pair-{pair_index:02d}-{label}-rerun",
                    mode=label,
                    stack=args.stack,
                    server_jar=server_jar,
                    packet_ids=packet_ids,
                    output_dir=output_dir,
                )
                repeat["repeat_of"] = arm["arm"]
                report["arms"].append(repeat)
                pair_arms[label] = repeat
                report_path.write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
        baseline = pair_arms[BASELINE_ARM]
        candidate = pair_arms[CANDIDATE_ARM]
        pair = {
            "repetition": pair_index,
            "order": order,
            "baseline": {
                "arm": baseline["arm"],
                "workload_attributable_tick_average_ms": baseline[
                    "workload_attributable_tick_average_ms"
                ],
                "active_tick_average_ms": baseline["active_tick_timings_ms"][
                    "tick_average_ms"
                ],
                "active_tick_p95_ms": baseline["active_tick_timings_ms"]["tick_p95_ms"],
                "load_average_1m_start": baseline["load_average_1m_start"],
            },
            "candidate": {
                "arm": candidate["arm"],
                "workload_attributable_tick_average_ms": candidate[
                    "workload_attributable_tick_average_ms"
                ],
                "active_tick_average_ms": candidate["active_tick_timings_ms"][
                    "tick_average_ms"
                ],
                "active_tick_p95_ms": candidate["active_tick_timings_ms"]["tick_p95_ms"],
                "load_average_1m_start": candidate["load_average_1m_start"],
            },
        }
        pairs.append(pair)
        report["pairs"] = pairs
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    changes = paired_percent_changes(
        pairs,
        metric="workload_attributable_tick_average_ms",
        baseline_arm="baseline",
        candidate_arm="candidate",
    )
    active_changes = paired_percent_changes(
        pairs,
        metric="active_tick_average_ms",
        baseline_arm="baseline",
        candidate_arm="candidate",
    )
    p95_changes = paired_percent_changes(
        pairs,
        metric="active_tick_p95_ms",
        baseline_arm="baseline",
        candidate_arm="candidate",
    )
    summary = summarize_paired_changes(
        changes,
        confidence=0.95,
        minimum_gain_percent=args.minimum_gain_percent,
    )
    report["analysis"] = {
        "primary_metric": "workload_attributable_tick_average_ms",
        "primary_summary": summary,
        "active_tick_average_summary": summarize_paired_changes(
            active_changes,
            confidence=0.95,
            minimum_gain_percent=args.minimum_gain_percent,
        ),
        "active_tick_p95_summary": summarize_paired_changes(
            p95_changes,
            confidence=0.95,
            minimum_gain_percent=args.minimum_gain_percent,
        ),
        "confidence": 0.95,
        "ci_method": summary.get("ci_method"),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["analysis"], indent=2))
    print(f"BC-06 {args.phase} report: {report_path}")
    print(f"BC-06 {args.phase} decision: {summary['decision']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", choices=("fabric",), default="fabric")
    parser.add_argument("--pairs", type=int)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--phase", choices=("screening", "confirmatory"), default="screening"
    )
    parser.add_argument(
        "--minimum-gain-percent",
        type=float,
        help=(
            "predeclared worthwhile primary-metric improvement for the "
            "confirmatory phase (percent, positive)"
        ),
    )
    args = parser.parse_args()
    if args.pairs is None:
        if args.phase == "confirmatory":
            parser.error(
                "--pairs must be chosen from screening variance before a "
                "confirmatory campaign"
            )
        args.pairs = 5
    if args.pairs < 1:
        parser.error("--pairs must be at least 1")
    if args.phase == "confirmatory" and args.pairs < 6:
        parser.error(
            "confirmatory campaigns require at least six pairs for the 95% "
            "exact median-interval confidence target"
        )
    if args.phase == "confirmatory" and args.minimum_gain_percent is None:
        parser.error("--minimum-gain-percent is required for confirmatory campaigns")
    if args.phase == "screening" and args.minimum_gain_percent is not None:
        parser.error("set the practical threshold with --phase confirmatory")
    if args.minimum_gain_percent is not None and args.minimum_gain_percent <= 0:
        parser.error("--minimum-gain-percent must be positive")
    return args


def main() -> int:
    args = parse_args()
    make_report(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
