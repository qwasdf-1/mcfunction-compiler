#!/usr/bin/env python3
"""COMPILER-CPU-005: bound method CPU clock streams, never claim removability."""
from __future__ import annotations

from pathlib import Path
import re

BEGIN = re.compile(r"FC_CPU005_BEGIN mode=(plain|empty|timed) stride=(\d+)")
END = re.compile(r"FC_CPU005_END mode=(plain|empty|timed) stride=(\d+)")
ROW = re.compile(r"FC_CPU005_ROW kind=(\S+) calls=(\d+) samples=(\d+) cpu_ns=(\d+) invalid=(\d+)")

EXPECTED_CALLS = {
    "enqueue_macro_predicate_build": 5616,
    "append_tp_execute": 1940,
    "append_frontier_execute": 1940,
    "append_coordinate_store_execute": 5820,
    "append_data_get_leaf": 5820,
}
STRIDE = 16


def parse_cpu005(path: Path, mode: str) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    begins = [m for line in lines if (m := BEGIN.search(line))]
    ends = [m for line in lines if (m := END.search(line))]
    if len(begins) != 1 or len(ends) != 1:
        raise ValueError("Exactly one CPU005 start/end required")
    if begins[0].groups() != ends[0].groups():
        raise ValueError("CPU005 start/end mismatch")
    if begins[0].group(1) != mode or int(begins[0].group(2)) != STRIDE:
        raise ValueError("CPU005 mode or stride mismatch")
    rows = {}
    for line in lines:
        m = ROW.search(line)
        if m is None:
            continue
        kind, calls, samples, ns, invalid = m.groups()
        calls, samples, ns, invalid = map(int, (calls, samples, ns, invalid))
        if kind in rows or kind not in EXPECTED_CALLS:
            raise ValueError("Duplicate or unknown CPU005 stream")
        if invalid:
            raise ValueError(f"CPU005 invalid or missing CPU interval: {kind} {invalid}")
        if calls != EXPECTED_CALLS[kind]:
            raise ValueError(f"CPU005 dynamic exposure drift: {kind} {calls}")
        if mode == "plain":
            if samples or ns:
                raise ValueError("Plain mode must never read CPU clock")
        elif samples != calls // STRIDE or ns <= 0:
            raise ValueError(f"Missing/extra CPU005 sample pairs: {kind}")
        rows[kind] = {"calls": calls, "samples": samples, "clock_ns": ns}
    if set(rows) != set(EXPECTED_CALLS):
        raise ValueError("Incomplete CPU005 stream census")
    return {"mode": mode, "stride": STRIDE, "rows": rows}


def projection(plain: dict, empty: dict, timed: dict, cpu_ns: int) -> dict:
    if cpu_ns <= 0:
        raise ValueError("No positive timed Server-thread CPU denominator")
    result = {}
    for kind in EXPECTED_CALLS:
        p, e, t = [arm["rows"][kind] for arm in (plain, empty, timed)]
        if len({p["calls"], e["calls"], t["calls"]}) != 1:
            raise ValueError(f"CPU005 mismatched invocation cardinality: {kind}")
        if e["samples"] < 64 or t["samples"] < 64:
            raise ValueError(f"Too few CPU005 samples for {kind}")
        empty_mean = e["clock_ns"] / e["samples"]
        timed_mean = t["clock_ns"] / t["samples"]
        corrected = timed_mean - empty_mean
        estimate_ns = corrected * t["calls"]
        result[kind] = {
            "calls": t["calls"],
            "timed_samples": t["samples"],
            "empty_pair_mean_ns": empty_mean,
            "timed_span_mean_ns": timed_mean,
            "signed_corrected_ns_per_call": corrected,
            "signed_projected_event_cpu_ns": estimate_ns,
            "signed_projected_event_cpu_fraction": estimate_ns / cpu_ns,
            "at_or_below_clock_floor": corrected <= empty_mean,
            "measured_inclusive_not_avoidable": True,
        }
    return {
        "streams": result, "timed_server_thread_cpu_ns": cpu_ns,
        "interpretation": (
            "CPU-time clocks from distinct PLAIN, EMPTY and TIMED JVMs sample "
            "synchronous original Minecraft methods. Macro BuildContexts spans "
            "predicate evaluation and custom function scheduling. ExecuteCommand "
            "spans real game work, including stateful result consumers. The "
            "nested data-get leaf measurement overlaps the coordinate-store "
            "ExecuteCommand span. Never sum these as disjoint fractions. "
            "These are noncausal descriptive projections, not speedup estimates "
            "or exact upper bounds on removable compiler cost."
        ),
    }
