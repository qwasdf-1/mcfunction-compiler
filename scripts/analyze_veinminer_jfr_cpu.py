#!/usr/bin/env python3
"""SCHED-COMP-021: server-thread JDK 25 JFR CPUTimeSample attribution.

Only jdk.CPUTimeSample is a CPU-time sampling observation. Never replace it
with jdk.ExecutionSample or Spark execution (wall-time) samples. This is a
diagnostic, not a paired performance experiment or exact method timer.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

MIN_VALID_SERVER_SAMPLES = 150
MAX_INVALID_FRACTION = 0.10
MAX_LOST_FRACTION = 0.05
CATEGORIES = (
    "typed-scoreadd", "other-specialized", "vanilla-scoreboard",
    "execute-control", "function-queue-or-nested", "brigadier-dispatch",
    "other-compiler", "world-updates", "other-minecraft", "other-runtime",
)

OTHER_SPECIALIZED_CLASSES = {
    "dev.functioncompiler.ScoreOperationCommand",
    "dev.functioncompiler.ScoreResetCommand",
    "dev.functioncompiler.ScoreStoreCommand",
    "dev.functioncompiler.ContextModifierCommand",
    "dev.functioncompiler.InlinedForkingCommand",
}

def _frames(values: dict[str, Any]) -> list[tuple[str, str]]:
    trace = values.get("stackTrace")
    if not isinstance(trace, dict):
        return []
    result = []
    for frame in trace.get("frames") or []:
        method = frame.get("method") or {}
        type_data = method.get("type") or {}
        clazz = str(type_data.get("name") or "").replace("/", ".")
        name = str(method.get("name") or "")
        if clazz:
            result.append((clazz, name))
    return result


def _category(frames: list[tuple[str, str]]) -> str:
    names = [clazz for clazz, _ in frames]
    if any(c == "dev.functioncompiler.ScoreAddCommand" for c in names):
        return "typed-scoreadd"
    if any(c in OTHER_SPECIALIZED_CLASSES for c in names):
        return "other-specialized"
    if any(c.startswith("net.minecraft.server.commands.ScoreboardCommand")
           for c in names):
        return "vanilla-scoreboard"
    if any(c.startswith("net.minecraft.server.commands.ExecuteCommand")
           for c in names):
        return "execute-control"
    if any(c.startswith(("net.minecraft.server.ServerFunctionManager",
                         "net.minecraft.commands.execution.",
                         "net.minecraft.commands.functions."))
           for c in names):
        return "function-queue-or-nested"
    if any(c.startswith(("com.mojang.brigadier.", "net.minecraft.commands.CommandDispatcher"))
           for c in names):
        return "brigadier-dispatch"
    if any(c.startswith("dev.functioncompiler.") for c in names):
        return "other-compiler"
    if any(c.startswith(("net.minecraft.server.level.ServerLevel",
                         "net.minecraft.world.level."))
           for c in names):
        return "world-updates"
    if any(c.startswith("net.minecraft.") for c in names):
        return "other-minecraft"
    return "other-runtime"


def interpret_events(events: list[dict[str, Any]], expected_tid: int,
                     min_samples: int = MIN_VALID_SERVER_SAMPLES) -> dict[str, Any]:
    """Classify each successfully captured CPU sample once, never stack-frame sums."""
    counts: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    valid = invalid = lost_server = lost_other = biased = 0
    seen_server_cpu_events = 0
    all_cpu_events = 0
    for event in events:
        kind = event.get("type")
        if kind not in ("jdk.CPUTimeSample", "jdk.CPUTimeSamplesLost"):
            continue
        values = event.get("values") or {}
        thread = values.get("eventThread") or {}
        if kind == "jdk.CPUTimeSample":
            all_cpu_events += 1
        if thread.get("javaName") != "Server thread" or int(thread.get("osThreadId") or -1) != expected_tid:
            if kind == "jdk.CPUTimeSamplesLost":
                lost_other += max(0, int(values.get("lostSamples") or 0))
            continue
        if kind == "jdk.CPUTimeSamplesLost":
            lost_server += max(0, int(values.get("lostSamples") or 0))
            continue
        seen_server_cpu_events += 1
        frames = _frames(values)
        if values.get("failed") is True or not frames:
            invalid += 1
            continue
        valid += 1
        biased += int(values.get("biased") is True)
        counts[_category(frames)] += 1
        innermost_class, innermost_method = frames[0]
        methods[f"{innermost_class}.{innermost_method}"] += 1

    denominator = valid + invalid + lost_server
    if not all_cpu_events:
        raise ValueError("Recording contains no jdk.CPUTimeSample events; CPU sampler unsupported or disabled")
    if valid < min_samples:
        raise ValueError(f"Insufficient valid Server-thread CPU-time samples: {valid} < {min_samples}")
    if (invalid / denominator if denominator else 1) > MAX_INVALID_FRACTION:
        raise ValueError(f"Too many failed/unresolved Server-thread CPU samples: {invalid}/{denominator}")
    if (lost_server / denominator if denominator else 1) > MAX_LOST_FRACTION:
        raise ValueError(f"Too many lost Server-thread CPU samples: {lost_server}/{denominator}")
    if sum(counts.values()) != valid:
        raise AssertionError("CPU sample category partition did not sum to valid sample count")
    share = counts["typed-scoreadd"] / valid
    return {
        "diagnostic_valid": True,
        "sampler": "JDK 25 experimental jdk.CPUTimeSample (CPU time, NOT wall-clock)",
        "server_tid": expected_tid,
        "valid_server_cpu_samples": valid,
        "failed_server_cpu_samples": invalid,
        "lost_server_cpu_samples": lost_server,
        "lost_other_thread_samples": lost_other,
        "biased_server_cpu_samples": biased,
        "all_threads_cpu_sample_events": all_cpu_events,
        "categories": {c: {"samples": counts[c], "sampled_cpu_fraction": counts[c] / valid}
                       for c in CATEGORIES},
        "top_innermost_methods": [
            {"method": name, "samples": number}
            for name, number in methods.most_common(20)
        ],
        "scoreadd_sampled_cpu_fraction": share,
        "scoreadd_ideal_elimination_upper_bound_from_samples": share,
        "would_15pct_be_within_sampled_scoreadd_share": share >= 0.15,
        "interpretation": (
            "Each captured Server-thread CPUTimeSample is classified once by its"
            " stack. Typed ScoreAdd includes all CPU samples in that callback's"
            " descendants; overhead before entry and inlined/missing frames can"
            " escape classification. This is a sampling estimate, NOT an exact"
            " exclusive method timer, causal speedup, or confidence interval."
        ),
    }


def analyze_jfr(path: Path, expected_tid: int,
                jfr_command: str = "jfr") -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    command = [jfr_command, "print", "--json", "--stack-depth", "128",
               "--events", "jdk.CPUTimeSample,jdk.CPUTimeSamplesLost", str(path)]
    result = subprocess.run(command, text=True, capture_output=True,
                            timeout=120, check=True)
    payload = json.loads(result.stdout)
    events = payload.get("recording", {}).get("events")
    if not isinstance(events, list):
        raise ValueError("JFR JSON lacks recording.events")
    report = interpret_events(events, expected_tid)
    report["profile_path"] = str(path)
    report["profile_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["jfr_json_event_count"] = len(events)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--server-tid", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze_jfr(args.profile, args.server_tid)
    body = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
