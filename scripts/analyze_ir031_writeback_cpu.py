#!/usr/bin/env python3
"""IR-031 Gate B: parse exact Marker Entity.load CPU attribution streams."""
from __future__ import annotations

from pathlib import Path
import re

BEGIN = re.compile(r"FC_IR031_BEGIN mode=(plain|empty|timed) stride=(\d+)")
END = re.compile(r"FC_IR031_END mode=(plain|empty|timed) stride=(\d+)")
ROW = re.compile(
    r"FC_IR031_ROW axis=(x|y|z) path_calls=(\d+) marker_calls=(\d+) "
    r"eligible=(\d+) store_completed=(\d+) load_calls=(\d+) "
    r"load_completed=(\d+) mounted=(\d+) other=(\d+) samples=(\d+) "
    r"cpu_ns=(\d+) invalid=(\d+)"
)
EXPECTED = {"x": 1940, "y": 1940, "z": 1940}
STRIDE = 16
MIN_EVENT_CPU_FRACTION = 0.05
MIN_CLOCK_FLOOR_RATIO = 3.0


def parse(path: Path, mode: str) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    begins = [m for line in lines if (m := BEGIN.search(line))]
    ends = [m for line in lines if (m := END.search(line))]
    if len(begins) != 1 or len(ends) != 1:
        raise ValueError("Exactly one IR031 start/end boundary required")
    if begins[0].groups() != ends[0].groups():
        raise ValueError("IR031 start/end mode or stride mismatch")
    if begins[0].group(1) != mode or int(begins[0].group(2)) != STRIDE:
        raise ValueError("IR031 mode or stride mismatch")

    rows = {}
    for line in lines:
        match = ROW.search(line)
        if match is None:
            continue
        (axis, path_calls, marker_calls, eligible, store_completed,
         load_calls, load_completed, mounted, other, samples, cpu_ns,
         invalid) = match.groups()
        values = tuple(map(int, (
            path_calls, marker_calls, eligible, store_completed, load_calls,
            load_completed, mounted, other, samples, cpu_ns, invalid,
        )))
        if axis in rows:
            raise ValueError(f"Duplicate IR031 axis row: {axis}")
        (path_calls, marker_calls, eligible, store_completed, load_calls,
         load_completed, mounted, other, samples, cpu_ns, invalid) = values
        expected = EXPECTED[axis]
        if (
            path_calls != expected or marker_calls != expected
            or eligible != expected or store_completed != expected
            or load_calls != expected or load_completed != expected
            or mounted or other
        ):
            raise ValueError(
                f"IR031 exact source/entity/load exposure drift on {axis}: {values!r}")
        if invalid:
            raise ValueError(f"IR031 invalid CPU clock sample on {axis}: {invalid}")
        expected_samples = 0 if mode == "plain" else expected // STRIDE
        if samples != expected_samples:
            raise ValueError(
                f"IR031 wrong sample count on {axis}: {samples}, expected {expected_samples}")
        if mode == "plain" and cpu_ns:
            raise ValueError("IR031 plain mode must never read the CPU clock")
        if mode == "timed" and cpu_ns <= 0:
            raise ValueError(f"IR031 timed Entity.load clock empty on {axis}")
        rows[axis] = {
            "path_calls": path_calls,
            "marker_calls": marker_calls,
            "eligible": eligible,
            "store_completed": store_completed,
            "entity_load_calls": load_calls,
            "entity_load_completed": load_completed,
            "samples": samples,
            "clock_ns": cpu_ns,
        }
    if set(rows) != set(EXPECTED):
        raise ValueError(f"IR031 incomplete axis census: {sorted(rows)}")
    return {"mode": mode, "stride": STRIDE, "rows": rows}


def project(plain: dict, empty: dict, timed: dict, event_cpu_ns: int) -> dict:
    if event_cpu_ns <= 0:
        raise ValueError("Missing positive plain-event Server-thread CPU denominator")
    if any(arm["mode"] != mode for arm, mode in (
        (plain, "plain"), (empty, "empty"), (timed, "timed")
    )):
        raise ValueError("IR031 attribution arms supplied in wrong mode order")
    axes = {}
    total_projected_ns = 0.0
    all_above_floor = True
    for axis, calls in EXPECTED.items():
        p = plain["rows"][axis]
        e = empty["rows"][axis]
        t = timed["rows"][axis]
        if len({p["entity_load_calls"], e["entity_load_calls"],
                t["entity_load_calls"]}) != 1:
            raise ValueError(f"IR031 Entity.load cardinality changed on {axis}")
        empty_mean = e["clock_ns"] / e["samples"]
        timed_mean = t["clock_ns"] / t["samples"]
        corrected = timed_mean - empty_mean
        projected = corrected * calls
        ratio = corrected / empty_mean if empty_mean > 0 else None
        above = corrected > 0 and ratio is not None and ratio >= MIN_CLOCK_FLOOR_RATIO
        all_above_floor = all_above_floor and above
        total_projected_ns += projected
        axes[axis] = {
            "calls": calls,
            "samples": t["samples"],
            "empty_pair_mean_ns": empty_mean,
            "timed_entity_load_mean_ns": timed_mean,
            "signed_corrected_entity_load_ns_per_call": corrected,
            "empty_floor_multiple": ratio,
            "signed_projected_event_cpu_ns": projected,
            "above_three_times_empty_clock_floor": above,
        }
    fraction = total_projected_ns / event_cpu_ns
    return {
        "entity_load_by_axis": axes,
        "signed_projected_entity_load_cpu_ns": total_projected_ns,
        "plain_event_server_thread_cpu_ns": event_cpu_ns,
        "signed_projected_entity_load_event_cpu_fraction": fraction,
        "all_axes_above_three_times_empty_clock_floor": all_above_floor,
        "predeclared_materiality_threshold": MIN_EVENT_CPU_FRACTION,
        "projected_entity_load_exceeds_5pct_event_cpu": fraction >= MIN_EVENT_CPU_FRACTION,
        "candidate_research_warranted": (
            all_above_floor and fraction >= MIN_EVENT_CPU_FRACTION
        ),
        "measurement_scope": (
            "Only Entity.load called synchronously by EntityDataAccessor.setData "
            "inside the exact x/y/z execute-store callback for an unmounted exact "
            "vanilla Marker. The x/y/z calls are disjoint from each other. This is "
            "inclusive Entity.load CPU, not proof that all of it is avoidable; do "
            "not add enclosing ExecuteCommand or nested data-get projections."
        ),
        "semantic_equivalence_proven": False,
        "cpu_speedup_measured": False,
        "production_promotion": False,
    }
