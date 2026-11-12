"""Reconstruct top-level G1 GC cycles from Java 25 unified logs.

A GC id may have nested phase, heap and CPU messages. Count only gc-tag
top-level completion messages as cycles, never sum nested phase durations as
additional collections. A start-tag record is preferred for interval starts;
otherwise the end timestamp minus duration is an explicitly flagged fallback.
"""
from __future__ import annotations

from datetime import datetime
import re

RECORD = re.compile(r"^\[([^]]+)\]\[(\d+)ms\]\[([^]]+)\]\[([^]]+)\] (.*)$")
IDENTIFIER = re.compile(r"^GC\((\d+)\) (.*)$")
DURATION = re.compile(r" (\d+(?:\.\d+)?)ms$")
HEAP = re.compile(
    r"(\d+(?:\.\d+)?)([BKMG])->(\d+(?:\.\d+)?)([BKMG])"
    r"\((\d+(?:\.\d+)?)([BKMG])\)"
)
SCALE = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3}


def parse_cycles(lines) -> dict:
    grouped: dict[int, dict] = {}
    malformed = []
    for number, line in enumerate(lines, 1):
        record = RECORD.match(line.rstrip("\n"))
        if not record:
            if "GC(" in line:
                malformed.append(number)
            continue
        timestamp, uptime, _level, tags, message = record.groups()
        identifier = IDENTIFIER.match(message)
        if identifier is None:
            continue
        try:
            epoch = datetime.fromisoformat(timestamp).timestamp() * 1000
        except ValueError:
            malformed.append(number)
            continue
        gc_id = int(identifier.group(1))
        body = identifier.group(2)
        if not body.startswith(("Pause ", "Concurrent ")):
            continue
        grouped.setdefault(gc_id, {"starts": [], "completions": [], "details": []})
        group = grouped[gc_id]
        tagset = {tag.strip() for tag in tags.split(",")}
        if "start" in tagset:
            group["starts"].append((body, epoch))
            continue
        duration = DURATION.search(body)
        if duration is None:
            continue
        title = body[:duration.start()].strip()
        heap = HEAP.search(title)
        if heap:
            title = title[:heap.start()].rstrip()
        event = {
            "name": title,
            "end_ms": epoch,
            "inferred_start_ms": epoch - float(duration.group(1)),
            "duration_ms": float(duration.group(1)),
            "line": number,
        }
        if heap:
            event["heap_before_bytes"] = round(float(heap[1]) * SCALE[heap[2]])
            event["heap_after_bytes"] = round(float(heap[3]) * SCALE[heap[4]])
            event["heap_capacity_bytes"] = round(float(heap[5]) * SCALE[heap[6]])
        if tagset == {"gc"}:
            group["completions"].append(event)
        else:
            group["details"].append(event)

    cycles = []
    incomplete = []
    for gc_id, group in sorted(grouped.items()):
        for completion in group["completions"]:
            if not (completion["name"].startswith("Pause ") or
                    completion["name"].endswith("Cycle")):
                continue
            matching_starts = [t for name, t in group["starts"]
                               if name == completion["name"] and t <= completion["end_ms"]]
            if matching_starts:
                start = matching_starts[-1]
                source = "explicit"
            else:
                start = completion["inferred_start_ms"]
                source = "inferred"
            cycle = {
                **completion, "gc_id": gc_id, "start_ms": start,
                "start_source": source,
                "is_pause": completion["name"].startswith("Pause "),
                "is_concurrent_cycle": completion["name"].startswith("Concurrent ")
                and completion["name"].endswith("Cycle"),
            }
            cycle["nested_phases"] = [
                p for p in group["details"]
                if p["inferred_start_ms"] >= start - 3
                and p["end_ms"] <= completion["end_ms"] + 3
            ]
            cycles.append(cycle)
        for name, timestamp in group["starts"]:
            if not any(c["gc_id"] == gc_id and c["name"] == name
                       and c["start_ms"] >= timestamp - 3 for c in cycles):
                incomplete.append({"gc_id": gc_id, "name": name, "start_ms": timestamp})
    return {"cycles": cycles, "unmatched_starts": incomplete, "malformed_lines": malformed}


def overlap_ms(start: float, end: float, event_start: float, event_end: float) -> float:
    if end < start:
        raise ValueError("Negative window duration")
    return max(0.0, min(end, event_end) - max(start, event_start))


def describe_window(parsed: dict, start_ms: float, end_ms: float) -> dict:
    events = [
        c for c in parsed["cycles"]
        if overlap_ms(start_ms, end_ms, c["start_ms"], c["end_ms"]) > 0
    ]
    pauses = [c for c in events if c["is_pause"]]
    concurrent = [c for c in events if c["is_concurrent_cycle"]]
    return {
        "pause_count": len(pauses),
        "concurrent_cycle_count": len(concurrent),
        "pause_overlap_ms": sum(overlap_ms(start_ms, end_ms, c["start_ms"], c["end_ms"])
                                for c in pauses),
        "concurrent_cycle_overlap_ms": sum(
            overlap_ms(start_ms, end_ms, c["start_ms"], c["end_ms"])
            for c in concurrent
        ),
        "gc_ids": [c["gc_id"] for c in events],
        "inferred_start_count": sum(c["start_source"] == "inferred" for c in events),
        "not_a_quiet_certification": True,
    }
