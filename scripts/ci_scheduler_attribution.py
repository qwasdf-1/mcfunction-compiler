#!/usr/bin/env python3
"""SCHED-ATTR-001: first-pass Minecraft 26.3 scheduler cost attribution.

A screening experiment, NOT a compiler promotion benchmark. One Fabric JVM,
wrapper OFF and all specializers OFF, runs three equal-length functions.
JFR samples Java execution stacks and RCON measures round-trip function
latencies (which include transport); neither is a standalone CPU timer.
All reporting is descriptive, no performance promotion claim is made.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import statistics
import subprocess
import sys
import time

from ci_smoke_server import Rcon, unused_port, wait_for_rcon

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-ATTR-001"
N = 2000
WARMUP_CALLS = 80
WINDOW_SECONDS = 6.0
ARMS = ("noop", "score", "conditional", "conditional", "score", "noop")
PACK = "fc_scheduler_experiment"
OBJECTIVE = "fc_sched"
HOLDER = "#x"
GATE = "#gate"
JFR_SETTINGS = "profile"
JVM_ARGS = "-Xms512M,-Xmx2G"


def make_fixture(run_dir: Path) -> None:
    datapack = run_dir / "world" / "datapacks" / PACK
    data = datapack / "data" / PACK / "function"
    data.mkdir(parents=True, exist_ok=True)
    (datapack / "pack.mcmeta").write_text(
        json.dumps({"pack": {"description": "SCHED-ATTR-001 controlled command families",
                             "min_format": [97, 1], "max_format": [97, 1]}}) + "\n",
        encoding="utf-8",
    )
    commands = {
        "noop": "fc_research_noop",
        "score": f"scoreboard players add {HOLDER} {OBJECTIVE} 1",
        "conditional": (
            f"execute if score {GATE} {OBJECTIVE} matches 1 "
            "run fc_research_noop"
        ),
    }
    for name, command in commands.items():
        (data / f"{name}.mcfunction").write_text(
            (command + "\n") * N, encoding="utf-8"
        )


def java_server_pid(parent_pid: int, server_dir: Path) -> int:
    """Resolve the server JVM by its run-directory cwd, not Gradle parentage.

    Gradle may launch the Minecraft JVM from an already-running daemon rather
    than below the invocation wrapper's process tree. CI hosts have a single
    running server, and its working directory is our dedicated run directory.
    """
    candidates = []
    all_java = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        pid = int(path.name)
        try:
            cwd = (path / "cwd").resolve(strict=True)
            cmd = (path / "cmdline").read_bytes().replace(b"\\0", b" ").decode(errors="replace")
            if "java" in Path(cmd.split(" ", 1)[0]).name:
                all_java.append((pid, str(cwd), cmd[:180]))
            if cwd == server_dir.resolve() and "java" in Path(cmd.split(" ", 1)[0]).name:
                candidates.append(pid)
        except (OSError, ValueError, PermissionError):
            continue
    if len(candidates) != 1:
        jcmd_list = subprocess.run(
            ["jcmd", "-l"], text=True, capture_output=True, check=False,
            timeout=15,
        )
        raise RuntimeError(
            f"Expected one server JVM in {server_dir}, got {candidates}. "
            f"Visible java processes={all_java[:20]!r}. "
            f"jcmd -l: {jcmd_list.stdout[:1400]!r}. "
            f"Gradle wrapper PID={parent_pid}"
        )
    return candidates[0]


def jcmd(pid: int, *args: str) -> str:
    run = subprocess.run(
        ["jcmd", str(pid), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=35, check=False,
    )
    if run.returncode:
        raise RuntimeError(f"jcmd {' '.join(args)} failed: {run.stdout[:1500]}")
    return run.stdout


def describe_frame(frame: dict) -> str:
    method = frame.get("method") or {}
    type_data = method.get("type") or {}
    return f"{type_data.get('name', '')}.{method.get('name', '')}"


def classify_stack(frame_names: list[str]) -> str:
    """Approximate CPU self-sample attribution to the nearest semantic layer.

    Scan from innermost to outermost frame. Java collection methods inherit
    the nearest underlying named Minecraft frame, if one is present.
    Unclassified samples remain unclassified (never force to scheduler).
    """
    for name in frame_names:
        if "dev.functioncompiler.ProbeCommands" in name:
            return "minimal_leaf"
        if ("net.minecraft.world.scores" in name
                or "net.minecraft.server.commands.Scoreboard" in name
                or ".ScoreboardPlayersCommand." in name):
            return "scoreboard_operation"
        if "com.mojang.brigadier" in name:
            return "brigadier_dispatch"
        if ("net.minecraft.commands.execution.tasks.BuildContexts" in name
                or "net.minecraft.commands.execution.tasks.ExecuteCommand" in name
                or "net.minecraft.commands.execution.ContextChain" in name):
            return "context_or_leaf_dispatch"
        if ("net.minecraft.commands.execution.ExecutionContext" in name
                or "net.minecraft.commands.execution.tasks.CallFunction" in name
                or "net.minecraft.commands.execution.tasks.ContinuationTask" in name
                or "net.minecraft.commands.execution.Frame" in name
                or "net.minecraft.commands.execution.CommandQueueEntry" in name):
            return "scheduler_or_function_queue"
    return "other_unclassified"


def summarize_jfr(path: Path) -> dict:
    output = subprocess.run(
        ["jfr", "print", "--json", "--events", "jdk.ExecutionSample", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=90, check=False,
    )
    if output.returncode:
        raise RuntimeError(f"jfr print failed: {output.stderr[:1000]}")
    recording = json.loads(output.stdout)
    events = recording.get("recording", {}).get("events", [])
    server_events = []
    in_queue = []
    all_threads = {}
    for event in events:
        values = event.get("values", {})
        thread = values.get("sampledThread") or {}
        name = thread.get("javaName") or thread.get("osName") or "(unknown)"
        all_threads[name] = all_threads.get(name, 0) + 1
        if name != "Server thread":
            continue
        frames = (values.get("stackTrace") or {}).get("frames") or []
        methods = [describe_frame(f) for f in frames]
        server_events.append(methods)
        if any("net.minecraft.commands.execution.ExecutionContext.runCommandQueue"
               in s for s in methods):
            in_queue.append(methods)
    class_counts = {}
    top_methods = {}
    for names in in_queue:
        owner = classify_stack(names)
        class_counts[owner] = class_counts.get(owner, 0) + 1
        top = names[0] if names else "(no stack)"
        top_methods[top] = top_methods.get(top, 0) + 1
    count = len(in_queue)
    return {
        "all_execution_samples": len(events),
        "server_thread_samples": len(server_events),
        "server_thread_queue_samples": count,
        "server_thread_nonqueue_samples": len(server_events) - count,
        "attributed_queue_sample_counts": class_counts,
        "attributed_queue_sample_percentages": {
            k: round(v / count * 100, 2) if count else None
            for k, v in class_counts.items()
        },
        "top_20_innermost_methods": sorted(
            top_methods.items(), key=lambda kv: -kv[1]
        )[:20],
        "sampled_threads_top_10": sorted(
            all_threads.items(), key=lambda kv: -kv[1]
        )[:10],
        "caveat": "JFR sampled Java stacks only; inlining, native frames, and sample frequency "
                  "limit granularity. Categories are source-code heuristics, not exact timers.",
    }


def get_score(rcon: Rcon) -> int:
    response = rcon.command(f"scoreboard players get {HOLDER} {OBJECTIVE}")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise AssertionError(f"No scoreboard score in {response!r}")
    return int(match.group(1))


def get_noop_count(rcon: Rcon) -> int:
    response = rcon.command("fc_research_count")
    match = re.search(r"FC_RESEARCH_COUNT (\d+)", response)
    if match is None:
        raise AssertionError(f"No research counter in {response!r}")
    return int(match.group(1))


def require_function_call(response: str, name: str) -> None:
    if not response.startswith("Running function "):
        raise AssertionError(f"Failed to execute {name}: {response!r}")


def run_profile_window(rcon: Rcon, pid: int, arm: str, index: int) -> dict:
    name = f"FC_SCHED_{index}"
    filename = (OUTPUT / f"{index:02}_{arm}.jfr").resolve()
    target = f"{PACK}:{arm}"
    before_noop = get_noop_count(rcon)
    before_score = get_score(rcon)
    for _ in range(WARMUP_CALLS):
        require_function_call(rcon.command(f"function {target}"), target)
    after_warmup_noop = get_noop_count(rcon)
    after_warmup_score = get_score(rcon)

    jcmd(pid, "JFR.start", f"name={name}",
         f"settings={JFR_SETTINGS}", "disk=true", "dumponexit=false")
    measurements = []
    clock_start = time.perf_counter()
    try:
        while time.perf_counter() - clock_start < WINDOW_SECONDS:
            started = time.perf_counter_ns()
            response = rcon.command(f"function {target}")
            measurements.append((time.perf_counter_ns() - started) / 1_000_000.0)
            require_function_call(response, target)
    finally:
        jcmd(pid, "JFR.stop", f"name={name}", f"filename={filename}")
    after_noop = get_noop_count(rcon)
    after_score = get_score(rcon)
    calls = len(measurements)
    expected_noop_delta = N * (WARMUP_CALLS + calls) if arm != "score" else 0
    expected_score_delta = N * (WARMUP_CALLS + calls) if arm == "score" else 0
    if (after_noop - before_noop != expected_noop_delta
            or after_score - before_score != expected_score_delta):
        raise AssertionError(
            f"Workload-integrity failure arm={arm} noop_delta={after_noop-before_noop} "
            f"expected={expected_noop_delta}, score_delta={after_score-before_score} "
            f"expected={expected_score_delta}"
        )
    jfr_data = summarize_jfr(filename)
    summary = {
        "window_index": index,
        "arm": arm,
        "lines_per_function": N,
        "warmup_calls": WARMUP_CALLS,
        "measured_calls": calls,
        "measured_command_lines": calls * N,
        "duration_seconds": round(time.perf_counter() - clock_start, 3),
        "rcon_round_trip_median_ms": round(statistics.median(measurements), 4),
        "rcon_round_trip_p95_ms": round(sorted(measurements)[int(.95*(calls-1))], 4),
        "rcon_round_trip_min_ms": round(min(measurements), 4),
        "workload_exact": True,
        "noop_count_after_warmup": after_warmup_noop,
        "score_after_warmup": after_warmup_score,
        "jfr_file": filename.name,
        "jfr": jfr_data,
    }
    print(
        f"WINDOW {index} arm={arm} calls={calls} median_RCON_ms="
        f"{summary['rcon_round_trip_median_ms']} queue_samples="
        f"{jfr_data['server_thread_queue_samples']} "
        f"categories={jfr_data['attributed_queue_sample_percentages']}",
        flush=True,
    )
    return summary


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    run_dir = ROOT / "run" / "ci-scheduler-attribution"
    run_dir.mkdir(parents=True, exist_ok=True)
    make_fixture(run_dir)
    (run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    (run_dir / "server.properties").write_text(
        "\n".join((
            "online-mode=false",
            "enable-rcon=true",
            "broadcast-rcon-to-ops=false",
            "level-type=minecraft:flat",
            "pause-when-empty-seconds=-1",
            "view-distance=2",
            "simulation-distance=2",
            "max-tick-time=-1",
            f"server-port={port}",
            f"rcon.port={rcon_port}",
            f"rcon.password={password}",
        )) + "\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_SCHEDULER_RESEARCH": "true",
    })
    command = [
        str(ROOT / "gradlew"), "--no-daemon",
        f"-PfcRunDirectory={run_dir.relative_to(ROOT)}",
        f"-PfcJvmArgs={JVM_ARGS}", "runServer",
    ]
    logfile = OUTPUT / "minecraft-server.log"
    result = {
        "experiment": "SCHED-ATTR-001",
        "status": "started",
        "classification": "single-host screening; not a promotion gate",
        "environment": "Minecraft 26.3 Fabric, Java 25, all compiler optimizations OFF",
        "arm_sequence": ARMS,
        "lines_per_call": N,
        "warmup_calls_per_window": WARMUP_CALLS,
        "profiling": "JFR settings=profile; jdk.ExecutionSample; Server thread",
        "primary_claim": "Which execution layers dominate the sampled time in each function workload?",
        "secondary_metric": "RCON function round-trip latency (transport included)",
        "windows": [],
    }
    report = OUTPUT / "results.json"
    client = None
    with logfile.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            command, cwd=ROOT, env=env, stdin=subprocess.PIPE,
            stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            client = wait_for_rcon(proc, rcon_port, password, timeout_seconds=180)
            enabled = client.command("datapack list enabled")
            if PACK not in enabled:
                raise RuntimeError(f"Generated profiling datapack missing: {enabled!r}")
            status = client.command("functioncompiler status")
            if "wrapped=false" not in status:
                raise RuntimeError(f"Expected an unwrapped baseline: {status!r}")
            client.command(f"scoreboard objectives add {OBJECTIVE} dummy")
            client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            client.command(f"scoreboard players set {GATE} {OBJECTIVE} 1")
            java_pid = java_server_pid(proc.pid, run_dir)
            print(f"SCHED-ATTR-001 server JVM pid={java_pid}", flush=True)
            for idx, arm in enumerate(ARMS, 1):
                result["windows"].append(run_profile_window(client, java_pid, arm, idx))
                report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            result["status"] = "completed"
            report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print("SCHED-ATTR-001 complete; report=" + str(report), flush=True)
        except BaseException as exc:
            result["status"] = "failed"
            result["error"] = repr(exc)
            report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(f"SCHED-ATTR-001 FAILED: {exc!r}; server log={logfile}", file=sys.stderr)
            raise
        finally:
            if client is not None:
                try:
                    client.command("stop")
                except (OSError, RuntimeError):
                    pass
                client.close()
            try:
                proc.wait(timeout=35)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
