#!/usr/bin/env python3
"""Offline reanalysis of existing SCHED-GC-006 ZIP, no JVM boots or benchmarks.

Usage:
  python3 scripts/analyze_gc006_archive.py archive.zip --output gc006-reanalysis.json

Reports EVERY boot, scored window, and adjacent A/A pair. Correlations are
descriptive; observed GC absence is not sufficient to prove a GC-quiet state.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import zipfile

from gc_cycle_reconstruction import parse_cycles, describe_window


def pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    numer = sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    denom = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return numer/denom if denom else None


def analyze_archive(path: Path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        result_paths = [p for p in names if p.endswith("results.json")]
        if len(result_paths) != 1:
            raise ValueError("Archive must contain exactly one results.json")
        original = json.loads(z.read(result_paths[0]))
        if original.get("experiment") != "SCHED-GC-006":
            raise ValueError("Wrong experiment")
        boots = original["boots"]
        if len(boots) != 20:
            raise ValueError("Incomplete 20-boot campaign")
        output = []
        observations = []
        for boot in boots:
            suffix = f"boot-{boot['boot']:02d}-{boot['mode']}-gc.log"
            matches = [n for n in names if n.endswith(suffix)]
            if len(matches) != 1:
                raise ValueError(f"Missing or ambiguous GC log for {suffix}")
            text = z.read(matches[0]).decode("utf-8", errors="replace")
            parsed = parse_cycles(text.splitlines())
            scored = []
            for window in boot["timed_windows"]:
                if window["stage"] not in ("score_early", "score_late"):
                    continue
                desc = describe_window(parsed, window["epoch_bracket_start_ms"],
                                       window["epoch_bracket_end_ms"])
                role_cpu = window["noise_telemetry"]["surviving_thread_running_ns_by_role"]
                row = {
                    "stage": window["stage"],
                    "server_cpu_ns_per_line": window["cpu_ns_per_source_line"],
                    "gc_worker_cpu_ms": role_cpu.get("gc", 0)/1e6,
                    "runqueue_fraction": window["runqueue_delay_fraction"],
                    **desc,
                }
                scored.append(row)
                observations.append(row)
            output.append({
                "boot": boot["boot"], "mode": boot["mode"],
                "qualified": boot["warmup"]["qualification_stable"],
                "quality_passed": boot["boot_quality"]["passed"],
                "cycles_total": len(parsed["cycles"]),
                "pause_cycles": sum(c["is_pause"] for c in parsed["cycles"]),
                "concurrent_cycles": sum(c["is_concurrent_cycle"] for c in parsed["cycles"]),
                "unmatched_starts": parsed["unmatched_starts"],
                "malformed_lines": parsed["malformed_lines"],
                "scored_windows": scored,
            })
        pairs = []
        for i in range(0, len(output), 2):
            first, second = output[i:i+2]
            if first["mode"] != second["mode"]:
                raise ValueError(f"Mixed-mode A/A pair {i//2+1}")
            b1,b2 = boots[i:i+2]
            ratio = 100*(b2["score_cpu_ns_per_line"]/b1["score_cpu_ns_per_line"]-1)
            pairs.append({"pair": i//2+1, "mode": first["mode"],
                          "first_to_second_percent": ratio,
                          "mean_pause_overlap_difference_ms":
                              statistics.mean(x["pause_overlap_ms"] for x in second["scored_windows"])
                              - statistics.mean(x["pause_overlap_ms"] for x in first["scored_windows"]),
                          "mean_gc_worker_cpu_difference_ms":
                              statistics.mean(x["gc_worker_cpu_ms"] for x in second["scored_windows"])
                              - statistics.mean(x["gc_worker_cpu_ms"] for x in first["scored_windows"])})
        cpu = [r["server_cpu_ns_per_line"] for r in observations]
        return {
            "experiment": "SCHED-GC-006", "analysis": "archived-cycle-reconstruction",
            "original_verdict": original["analysis"]["verdict"],
            "all_20_boots_retained": True,
            "all_40_score_windows_retained": len(observations) == 40,
            "summary": {
                "total_concurrent_cycles": sum(x["concurrent_cycles"] for x in output),
                "timed_concurrent_overlap_windows": sum(x["concurrent_cycle_count"]>0 for x in observations),
                "median_pause_overlap_ms": statistics.median(x["pause_overlap_ms"] for x in observations),
                "median_gc_worker_cpu_ms": statistics.median(x["gc_worker_cpu_ms"] for x in observations),
                "max_gc_worker_cpu_ms": max(x["gc_worker_cpu_ms"] for x in observations),
                "correlations": {
                    name: pearson([r[name] for r in observations], cpu)
                    for name in ("pause_overlap_ms","gc_worker_cpu_ms","runqueue_fraction")
                },
            },
            "boots": output, "pairs": pairs,
            "cautions": [
                "GC cycles may include overlapping stop-the-world pauses; do not sum cycle and pause time.",
                "Completion timestamps and outer Python time brackets have imperfect alignment.",
                "Zero logged concurrent-cycle overlap does not certify no GC or other JVM activity.",
                "Twenty boots are not randomized evidence that GC logging improved performance.",
                "All correlations are descriptive, not causal.",
            ],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = analyze_archive(args.archive)
    encoded = json.dumps(summary, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps(summary["summary"], indent=2))


if __name__ == "__main__":
    main()
