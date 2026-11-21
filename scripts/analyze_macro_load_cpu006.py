#!/usr/bin/env python3
"""COMPILER-MACRO-006: strictly validate bounded load_next CPU-clock streams.

All method spans are inclusive CPU time, not a causal performance result.
"""
from __future__ import annotations

from pathlib import Path
import re

BEGIN = re.compile(r"FC_MACRO006_BEGIN mode=(plain|empty|timed) stride=(\d+) function=(\S+)")
END = re.compile(r"FC_MACRO006_END mode=(plain|empty|timed) stride=(\d+)")
ROW = re.compile(r"FC_MACRO006_ROW kind=(\S+) calls=(\d+) samples=(\d+) cpu_ns=(\d+) invalid=(\d+)")
COUNTS = re.compile(r"FC_MACRO006_COUNTS cache_hits=(\d+) extraction_null=(\d+)")
EXPECTED_FUNCTION = "vm:queue/load_next"
EXPECTED_CALLS = 1952
STRIDE = 8
STREAMS = ("macro_total", "argument_extraction", "vanilla_macro_instantiation")


def parse_macro006(path: Path, expected_mode: str) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = [m for line in lines if (m := BEGIN.search(line))]
    ends = [m for line in lines if (m := END.search(line))]
    counts = [m for line in lines if (m := COUNTS.search(line))]
    if len(starts) != 1 or len(ends) != 1 or len(counts) != 1:
        raise ValueError("Macro006 requires one and only one complete event-scoped dump")
    mode, stride, function = starts[0].groups()
    if mode != expected_mode or int(stride) != STRIDE or function != EXPECTED_FUNCTION:
        raise ValueError("Macro006 incorrect mode, function, or stride")
    if ends[0].group(1) != mode or int(ends[0].group(2)) != STRIDE:
        raise ValueError("Macro006 start/end mismatch")
    cache_hits, missing = map(int, counts[0].groups())
    if cache_hits != 0 or missing != 0:
        raise ValueError(f"Macro006 changed cache/argument exposure: hits={cache_hits}, null={missing}")
    rows = {}
    for line in lines:
        match = ROW.search(line)
        if not match:
            continue
        kind, calls, samples, ns, invalid = match.groups()
        calls, samples, ns, invalid = map(int, (calls, samples, ns, invalid))
        if kind not in STREAMS or kind in rows:
            raise ValueError("Macro006 duplicate or unknown timed stream")
        if invalid:
            raise ValueError(f"Macro006 negative or failed CPU sample in {kind}")
        if calls != EXPECTED_CALLS:
            raise ValueError(f"Macro006 changed native instantiation exposure: {kind}={calls}")
        if mode == "plain":
            if samples or ns:
                raise ValueError("Macro006 plain control must not read the CPU clock")
        elif samples != calls // STRIDE or ns <= 0:
            raise ValueError(f"Macro006 samples lost, duplicated, or empty: {kind}")
        rows[kind] = {"calls": calls, "samples": samples, "clock_ns": ns}
    if set(rows) != set(STREAMS):
        raise ValueError("Macro006 lacks one or more required timed streams")
    return {"mode": mode, "stride": STRIDE, "function": function,
            "cache_hits": cache_hits, "extract_null": missing, "rows": rows}


def interpret(plain: dict, empty: dict, timed: dict, cpu_ns: int) -> dict:
    if cpu_ns <= 0:
        raise ValueError("Macro006 must have a positive measured Server-thread CPU denominator")
    result = {}
    for kind in STREAMS:
        p, e, t = (r["rows"][kind] for r in (plain, empty, timed))
        if len({p["calls"], e["calls"], t["calls"]}) != 1 or e["samples"] != t["samples"]:
            raise ValueError("Macro006 cross-boot call/sample identity changed")
        if e["samples"] < 200:
            raise ValueError("Macro006 sparse sample coverage too low")
        empty_ns = e["clock_ns"] / e["samples"]
        timed_ns = t["clock_ns"] / t["samples"]
        corrected = timed_ns - empty_ns
        projected = corrected * t["calls"]
        result[kind] = {
            "calls": t["calls"],
            "samples_per_timed_and_empty_arm": t["samples"],
            "empty_clock_pair_mean_ns": empty_ns,
            "timed_span_mean_ns": timed_ns,
            "signed_corrected_ns_per_call": corrected,
            "signed_projected_event_cpu_ns": projected,
            "signed_projected_event_cpu_fraction": projected / cpu_ns,
            "at_or_below_clock_floor": corrected <= empty_ns,
            "fully_avoidable": False,
        }
    return {
        "study": "COMPILER-MACRO-006",
        "diagnostic_valid": True,
        "streams": result,
        "timed_event_server_cpu_ns": cpu_ns,
        "interpretation": (
            "Three independent native JVMs provide a PLAIN counter, EMPTY clock-control,"
            " and TIMED method spans. The total span CONTAINS extraction and vanilla"
            " instantiate spans, so do not add fractions. Vanilla instantiate"
            " includes meaningful parsing/validation and cannot simply be deleted."
            " These measurements are descriptive CPU sensitivities, NOT proven"
            " savings, causal estimates, exact exclusive CPU, or a confidence interval."
        ),
    }
