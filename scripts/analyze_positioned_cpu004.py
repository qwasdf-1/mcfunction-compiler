#!/usr/bin/env python3
"""Parse bounded CPU004 CPU-clock diagnostics; preserve inclusive attribution."""
from __future__ import annotations

from pathlib import Path
import re

BEGIN = re.compile(r"FC_CPU004_BEGIN mode=(plain|empty|timed) stride=(\d+)")
ROW = re.compile(r"FC_CPU004_ROW kind=(\S+) calls=(\d+) samples=(\d+) cpu_ns=(\d+) invalid=(\d+)")
END = re.compile(r"FC_CPU004_END mode=(plain|empty|timed) stride=(\d+)")
KINDS = ("positioned_entry", "enqueue_call_setup", "enqueue_body_leaf")


def parse_cpu004(path: Path, expected_mode: str) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    begins = [m for line in lines if (m := BEGIN.search(line))]
    ends = [m for line in lines if (m := END.search(line))]
    if len(begins) != 1 or len(ends) != 1:
        raise ValueError("Expected exactly one start/end CPU004 dump")
    if begins[0].groups() != ends[0].groups():
        raise ValueError("CPU004 boundaries disagree")
    mode, step = begins[0].groups()
    stride = int(step)
    if mode != expected_mode or stride != 16:
        raise ValueError("Unrecognized CPU004 mode or sampling stride")
    rows = {}
    for line in lines:
        match = ROW.search(line)
        if not match:
            continue
        kind, calls, samples, elapsed, invalid = match.groups()
        if kind in rows or kind not in KINDS:
            raise ValueError("Duplicate or unknown CPU004 kind")
        calls, samples, elapsed, invalid = map(int, (calls, samples, elapsed, invalid))
        if invalid:
            raise ValueError("Negative/invalid CPU-clock interval")
        if mode == "plain":
            if samples or elapsed:
                raise ValueError("Plain arm must not read CPU clocks")
        elif samples != calls // stride:
            raise ValueError(
                f"Missing or extra sparse CPU clock samples for {kind}: "
                f"{samples} != {calls}//{stride}"
            )
        rows[kind] = {"calls": calls, "samples": samples, "clock_ns": elapsed}
    if set(rows) != set(KINDS):
        raise ValueError("Incomplete CPU004 timer classifications")
    if rows["positioned_entry"]["calls"] != 5616:
        raise ValueError("Pinned positioned-site invocation count changed")
    if rows["enqueue_call_setup"]["calls"] <= 0:
        raise ValueError("No child function setup callbacks observed")
    return {"mode": mode, "stride": stride, "rows": rows}


def diagnostic_projection(plain: dict, empty: dict, timed: dict,
                          timed_server_cpu_ns: int) -> dict:
    if timed_server_cpu_ns <= 0:
        raise ValueError("Missing positive Server-thread /proc CPU denominator")
    kinds = plain["rows"].keys()
    if set(kinds) != set(empty["rows"]) or set(kinds) != set(timed["rows"]):
        raise ValueError("Timer kinds differ")
    result = {}
    for kind in kinds:
        control, e, t = (data["rows"][kind] for data in (plain, empty, timed))
        if control["calls"] != e["calls"] or control["calls"] != t["calls"]:
            raise ValueError(f"Different dynamic call exposure for {kind}")
        if kind == "enqueue_body_leaf" and t["calls"] == 0:
            result[kind] = {
                "calls": 0,
                "measured": False,
                "reason": "No ordinary Brigadier callbacks observed; custom/deferred body work remains unmeasured",
                "can_be_claimed_avoidable": False,
            }
            continue
        if e["samples"] < 32 or t["samples"] < 32:
            raise ValueError(f"Too few valid clock pairs for {kind}")
        control_ns = e["clock_ns"] / e["samples"]
        timed_ns = t["clock_ns"] / t["samples"]
        corrected_ns = timed_ns - control_ns
        total_extrapolated = corrected_ns * t["calls"]
        result[kind] = {
            "calls": t["calls"],
            "matched_clock_pairs_per_arm": t["samples"],
            "empty_clock_pair_mean_ns": control_ns,
            "timed_span_mean_ns": timed_ns,
            "signed_control_corrected_cpu_ns_per_call": corrected_ns,
            "signed_descriptive_projection_cpu_ns": total_extrapolated,
            "signed_projected_fraction_of_timed_server_cpu": (
                total_extrapolated / timed_server_cpu_ns
            ),
            "clock_floor_warning": corrected_ns <= control_ns,
            "can_be_claimed_avoidable": False,
        }
    return {
        "kind_projections": result,
        "timed_server_thread_cpu_ns": timed_server_cpu_ns,
        "interpretation": (
            "Sparse within-method CPU-clock intervals control-subtracted across "
            "independent JVM boots; projections are inclusive descriptive "
            "sensitivities, NOT exact exclusive CPU, a timing confidence interval, "
            "a causal optimization effect, or proven avoidable code. The child "
            "body leaf stream observes only ordinary Brigadier callbacks, not "
            "custom executors, queued deferred tasks or complete body CPU. "
            "Do not sum categories as disjoint cost."
        ),
    }
