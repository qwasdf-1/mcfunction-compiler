#!/usr/bin/env python3
"""SCHED-NOISE-005: negative-control A/A calibration with per-JVM noise telemetry.

Each adjacent pair boots TWO IDENTICAL production Fabric stacks; no code change
or performance effect exists by construction. Five pairs are Fabric API only,
five are Fabric API with the disabled compiler. The question is whether this
host/JVM/measurement protocol invents differences in either population.

This is an A/A experiment. Do not treat a small paired difference as evidence
that the compiler has zero overhead: A/A never compares different stacks.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics
import sys

import ci_compiler_off_stability as stable
from ci_compiler_off_paired import exact_median_interval
from benchmark_noise_telemetry import (
    snapshot_jvm_environment,
    delta_environment,
)

ROOT = stable.ROOT
OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-NOISE-005"
REPORT = OUTPUT / "results.json"

# Five same-binary A/A pairs of each stack, interleaved and balanced across
# the run. First/second is a meaningful time-trend diagnostic. A separately
# blinded signed contrast is used to check false directional effects.
PAIR_MODES = (
    "fabric", "compiler", "compiler", "fabric", "fabric",
    "compiler", "fabric", "compiler", "compiler", "fabric",
)
# Exactly five positive/negative signs; independently counterbalanced by mode.
# These are labels for TWO IDENTICAL JAR stacks, not different code variants.
LABEL_ORDER = (
    ("A", "B"), ("B", "A"), ("A", "B"), ("B", "A"), ("B", "A"),
    ("A", "B"), ("B", "A"), ("A", "B"), ("B", "A"), ("A", "B"),
)
assert len(PAIR_MODES) == len(LABEL_ORDER) == 10
assert PAIR_MODES.count("fabric") == PAIR_MODES.count("compiler") == 5
BOOT_SEQUENCE = tuple(mode for mode in PAIR_MODES for _ in range(2))
# These are SCREENING targets, not confidence guarantees for a real A/B test.
DECLARED_MEDIAN_ABS_NULL_TARGET_PERCENT = 3.0
DECLARED_P90_ABS_NULL_TARGET_PERCENT = 8.0
DECLARED_MAX_ABS_NULL_TARGET_PERCENT = 12.0
MAX_QUALITY_FAILED_PAIR_COUNT = 0

_original_take_window = stable.take_cpu_window


def take_monitored_window(rcon, pid: int, tid: int, family: str, calls: int,
                          *, stage: str) -> dict:
    """Take telemetry OUTSIDE the existing timed function's CPU boundaries."""
    before = snapshot_jvm_environment(pid)
    result = _original_take_window(
        rcon, pid, tid, family, calls, stage=stage
    )
    after = snapshot_jvm_environment(pid)
    noise = delta_environment(before, after)
    whole = noise["whole_jvm_cpu_ns"]
    server_cpu = result["server_thread_cpu_ns"]
    # Separate observation only. Proc-stat tick granularity can yield a
    # negative residual for very short windows; do NOT clip it silently.
    noise["nonserver_jvm_cpu_ns_approx"] = (
        whole - server_cpu if whole is not None else None
    )
    if whole and whole > 0:
        noise["nonserver_jvm_cpu_share_approx"] = (
            noise["nonserver_jvm_cpu_ns_approx"] / whole
        )
    else:
        noise["nonserver_jvm_cpu_share_approx"] = None
    result["noise_telemetry"] = noise
    return result


def pct_change(second: float, first: float) -> float:
    if first <= 0:
        raise ValueError("CPU nanoseconds per line must be positive")
    return 100 * (second / first - 1.0)


def percentile_nearest_rank(items: list[float], p: float) -> float:
    if not items or not 0 < p <= 1:
        raise ValueError("Invalid percentile")
    return sorted(items)[math.ceil(len(items)*p)-1]


def evaluate(boots: list[dict]) -> dict:
    if len(boots) != len(BOOT_SEQUENCE):
        raise AssertionError("Never score incomplete A/A campaign")
    pairs = []
    for index, (expected, labels) in enumerate(zip(PAIR_MODES, LABEL_ORDER)):
        first, second = boots[index*2:index*2+2]
        if first["mode"] != second["mode"] or first["mode"] != expected:
            raise AssertionError("Not same-binary A/A pair")
        a, b = first["score_cpu_ns_per_line"], second["score_cpu_ns_per_line"]
        ordered = {"A": a if labels[0] == "A" else b,
                   "B": a if labels[0] == "B" else b}
        signed_null = pct_change(ordered["B"], ordered["A"])
        time_order = pct_change(b, a)
        direct_quality = (
            first["boot_quality"]["passed"] and second["boot_quality"]["passed"]
            and abs(first["host_at_boot"]["loadavg_1m"] -
                    second["host_at_boot"]["loadavg_1m"]) <= stable.MAX_PAIR_LOAD_DIFFERENCE
        )
        delay_a = first["mean_score_runqueue_delay_fraction"]
        delay_b = second["mean_score_runqueue_delay_fraction"]
        direct_quality = direct_quality and (
            delay_a is not None and delay_b is not None
            and abs(delay_b-delay_a) <= stable.MAX_PAIR_DELAY_FRACTION_DIFFERENCE
        )
        pairs.append({
            "index": index+1,
            "identical_stack": expected,
            "blinded_A_B_order": list(labels),
            "first_cpu_ns_per_line": a,
            "second_cpu_ns_per_line": b,
            "time_order_cpu_delta_percent": time_order,
            "signed_blinded_null_delta_percent": signed_null,
            "abs_log_ratio_percent": 100*abs(math.log(b/a)),
            "quality_passed": bool(direct_quality),
            "first_qualification_stable": first["warmup"]["qualification_stable"],
            "second_qualification_stable": second["warmup"]["qualification_stable"],
            "first_runqueue_fraction": delay_a,
            "second_runqueue_fraction": delay_b,
            "loadavg_before_first": first["host_at_boot"]["loadavg_1m"],
            "loadavg_before_second": second["host_at_boot"]["loadavg_1m"],
        })
    samples = [p["signed_blinded_null_delta_percent"] for p in pairs]
    absolute = [abs(p["signed_blinded_null_delta_percent"]) for p in pairs]
    invalid_pairs = [p["index"] for p in pairs if not p["quality_passed"]]
    summary = {}
    for mode in ("fabric", "compiler"):
        sample = [p for p in pairs if p["identical_stack"] == mode]
        signed = [p["signed_blinded_null_delta_percent"] for p in sample]
        abs_values = [abs(v) for v in signed]
        summary[mode] = {
            "pair_count": len(sample),
            "signed_blinded_null_deltas": signed,
            "median_signed_null_delta_percent": statistics.median(signed),
            "median_absolute_null_delta_percent": statistics.median(abs_values),
            "p90_absolute_null_delta_percent": percentile_nearest_rank(abs_values, .9),
            "max_absolute_null_delta_percent": max(abs_values),
            "median_time_order_delta_percent": statistics.median(
                p["time_order_cpu_delta_percent"] for p in sample
            ),
            # Five observations do not allow a two-sided 95% sign-test
            # median interval narrower than the full range.
            "confidence_warning": "Five A/A pairs per stack: descriptive only.",
        }
    med_abs = statistics.median(absolute)
    p90_abs = percentile_nearest_rank(absolute, .9)
    max_abs = max(absolute)
    threshold_ok = (
        med_abs <= DECLARED_MEDIAN_ABS_NULL_TARGET_PERCENT
        and p90_abs <= DECLARED_P90_ABS_NULL_TARGET_PERCENT
        and max_abs <= DECLARED_MAX_ABS_NULL_TARGET_PERCENT
    )
    if len(invalid_pairs) > MAX_QUALITY_FAILED_PAIR_COUNT:
        verdict = "inconclusive_quality_gate"
    elif not threshold_ok:
        verdict = "null_calibration_failed_variance_targets"
    else:
        verdict = "null_calibration_screening_targets_met"
    return {
        "pairs": pairs,
        "by_stack": summary,
        "pooled_blinded_null": {
            "signed_median_percent": statistics.median(samples),
            "exact_median_interval": exact_median_interval(samples),
            "median_absolute_percent": med_abs,
            "p90_absolute_percent": p90_abs,
            "max_absolute_percent": max_abs,
            "target_median_abs": DECLARED_MEDIAN_ABS_NULL_TARGET_PERCENT,
            "target_p90_abs": DECLARED_P90_ABS_NULL_TARGET_PERCENT,
            "target_max_abs": DECLARED_MAX_ABS_NULL_TARGET_PERCENT,
        },
        "quality": {
            "failed_pair_ids": invalid_pairs,
            "passing_pairs": len(pairs)-len(invalid_pairs),
            "stable_boots": sum(
                x["warmup"]["qualification_stable"] for x in boots
            ),
            "all_source_state_verified": all(
                all(w["exact_work"] for w in x["timed_windows"])
                for x in boots
            ),
            "legacy_loadavg_noisy_boots": [
                x["boot"] for x in boots
                if x["boot_quality"]["historical_loadavg_noisy"]
            ],
        },
        "verdict": verdict,
    }


def protocol() -> dict:
    return {
        "experiment": "SCHED-NOISE-005",
        "question": "How much false effect does a fresh-JVM same-binary A/A pair produce?",
        "a_a_stack_pairs": list(PAIR_MODES),
        "blinded_label_order": [list(x) for x in LABEL_ORDER],
        "jvm_warmup_protocol": stable.quality_constants(),
        "primary_metric": "false A/A percent delta in server thread CPU ns per 2000-command source line",
        "jit_diagnostics": (
            "process total CPU and per-surviving-thread JIT/GC CPU from /proc, "
            "outside inner CPU measurement boundaries; not a tier-4 JIT equivalence proof"
        ),
        "host_diagnostics": "runqueue delay, system CPU PSI, cgroup throttling and affinity",
        "screening_null_targets_percent": {
            "median_abs": DECLARED_MEDIAN_ABS_NULL_TARGET_PERCENT,
            "p90_abs": DECLARED_P90_ABS_NULL_TARGET_PERCENT,
            "max_abs": DECLARED_MAX_ABS_NULL_TARGET_PERCENT,
        },
        "no_pair_exclusion": True,
        "no_posthoc_threshold_change": True,
        "no_jfr_during_timings": True,
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # The earlier SCHED-HOOK-004 protocol is reused byte-for-byte for its
    # warmup, native execution, scoreboard checks and timed CPU windows.
    stable.OUT = OUTPUT
    stable.take_cpu_window = take_monitored_window
    artifact = stable.stage_artifacts()
    record = {
        "experiment": "SCHED-NOISE-005",
        "status": "started",
        "predeclared_protocol": protocol(),
        "artifact_hashes": {
            key: value for key, value in artifact.items()
            if key.endswith("_sha256")
        },
        "boots": [],
    }
    REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    try:
        for index, mode in enumerate(BOOT_SEQUENCE):
            boot = stable.run_boot(index, mode, artifact)
            record["boots"].append(boot)
            REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
            if index % 2 == 1:
                first, second = record["boots"][-2:]
                d = pct_change(
                    second["score_cpu_ns_per_line"],
                    first["score_cpu_ns_per_line"],
                )
                print(
                    f"NEGATIVE_CONTROL {index//2+1}/10 stack={mode} "
                    f"same_jar=true first_to_second={d:+.2f}% "
                    f"qualified={first['boot_quality']['passed'] and second['boot_quality']['passed']}",
                    flush=True,
                )
        record["analysis"] = evaluate(record["boots"])
        record["status"] = "complete"
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        summary = {
            "verdict": record["analysis"]["verdict"],
            "pooled": record["analysis"]["pooled_blinded_null"],
            "by_stack": record["analysis"]["by_stack"],
            "quality": record["analysis"]["quality"],
        }
        print("SCHED-NOISE-005 COMPLETE "+json.dumps(summary), flush=True)
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = repr(exc)
        REPORT.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
