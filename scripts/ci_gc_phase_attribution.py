#!/usr/bin/env python3
"""SCHED-GC-006 stage A: unchanged-stack A/A GC phase attribution.

Ten A/A pairs (same sequence as 005), all boots and failures preserved.
This diagnostic *does not* apply post-hoc GC exclusions or assert GC-quietness.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import time

import ci_compiler_off_stability as stable
import ci_noise_aa_calibration as aa
from benchmark_noise_telemetry import snapshot_jvm_environment, delta_environment
from gc_phase_telemetry import load_log, window_summary

OUT = stable.ROOT / "build" / "benchmarks" / "SCHED-GC-006"
REPORT = OUT / "results.json"
_original_window = stable.take_cpu_window


def window(rcon, pid, tid, family, calls, *, stage):
    before = snapshot_jvm_environment(pid)
    epoch_start = time.time_ns() / 1_000_000
    result = _original_window(rcon, pid, tid, family, calls, stage=stage)
    epoch_end = time.time_ns() / 1_000_000
    after = snapshot_jvm_environment(pid)
    result["epoch_bracket_start_ms"] = epoch_start
    result["epoch_bracket_end_ms"] = epoch_end
    result["noise_telemetry"] = delta_environment(before, after)
    return result


def annotate_windows(boot):
    workdir = stable.RUN_ROOT / f"ci-stable-hooks-{boot['boot']:02d}-{boot['mode']}"
    log = workdir / "gc-phase.log"
    parsed = load_log(log)
    destination = OUT / f"boot-{boot['boot']:02d}-{boot['mode']}-gc.log"
    if log.exists():
        shutil.copy2(log, destination)
    boot["gc_log"] = {
        "available": parsed["available"],
        "event_count": len(parsed["events"]),
        "unclassified_count": len(parsed["unclassified_gc_events"]),
        "malformed_count": len(parsed["malformed_gc_lines"]),
        "artifact": destination.name if parsed["available"] else None,
    }
    for w in [*boot["warmup"]["qualification"], *boot["timed_windows"]]:
        w["gc_diagnostic"] = window_summary(
            parsed, w["epoch_bracket_start_ms"], w["epoch_bracket_end_ms"]
        )
    return boot


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stable.OUT = OUT
    stable.take_cpu_window = window
    # Only this process and its subprocess children inherit the logging toggle.
    os.environ["FC_BENCH_GC_LOG"] = "true"
    artifacts = stable.stage_artifacts()
    record = {
        "experiment": "SCHED-GC-006",
        "status": "started",
        "stage": "A_phase_attribution",
        "protocol": {
            **aa.protocol(),
            "gc_log": "-Xlog:gc*,safepoint=info:file=gc-phase.log:time,uptimemillis,level,tags",
            "window_clock": "Python time.time_ns UTC epoch bracketing entire RCON measurement",
            "study_limitation": "GC activity is diagnostic only; no GC-quiet filtering or production speedup claim",
            "no_posthoc_exclusions": True,
            "mode_count": 10,
        },
        "artifact_hashes": {k:v for k,v in artifacts.items() if k.endswith("_sha256")},
        "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    try:
        for index, mode in enumerate(aa.BOOT_SEQUENCE):
            boot = stable.run_boot(index, mode, artifacts)
            boot = annotate_windows(boot)
            record["boots"].append(boot)
            REPORT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        record["analysis"] = aa.evaluate(record["boots"])
        record["status"] = "complete"
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("SCHED-GC-006 stage A " + record["analysis"]["verdict"], flush=True)


if __name__ == "__main__":
    main()
