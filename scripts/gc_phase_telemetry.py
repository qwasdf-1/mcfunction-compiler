"""Parse JVM unified GC logs and align events with externally timestamped windows.

The parser deliberately retains unrecognized lines and incomplete events. Parsing is
diagnostic; it must NEVER silently classify missing GC data as GC-quiet.
Uses epoch-millisecond decorators emitted by -Xlog:...:time,uptimemillis,...
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

STAMP = re.compile(r"^\[(\d{4}-\d\d-\d\dT[^\]]+)\]\[(\d+)ms\]")
GC_ID = re.compile(r"GC\((\d+)\)")
HEAP = re.compile(r"(\d+(?:\.\d+)?)([BKMGT])->(\d+(?:\.\d+)?)([BKMGT])\((\d+(?:\.\d+)?)([BKMGT])\)")
PAUSE = re.compile(r"(?:Pause |Concurrent )(.*?)\s+(\d+(?:\.\d+)?)ms(?:\s|$)")
UNITS = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}


def epoch_ms(timestamp: str) -> float:
    # Unified logging uses ISO offset timestamps, including fractional seconds.
    return dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000


def bytes_value(value: str, unit: str) -> int:
    return round(float(value) * UNITS[unit])


def parse_lines(lines) -> dict:
    events, unknown_gc, malformed = [], [], []
    for number, line in enumerate(lines, 1):
        line = line.rstrip("\n")
        stamp = STAMP.match(line)
        if not stamp:
            if "GC(" in line or "[gc" in line:
                malformed.append({"line": number, "text": line})
            continue
        try:
            ms = epoch_ms(stamp.group(1))
        except ValueError:
            malformed.append({"line": number, "text": line})
            continue
        if "[gc" not in line and "safepoint" not in line:
            continue
        identifier = GC_ID.search(line)
        duration = PAUSE.search(line)
        heap = HEAP.search(line)
        item = {
            "line": number,
            "epoch_ms": ms,
            "uptime_ms": int(stamp.group(2)),
            "gc_id": int(identifier.group(1)) if identifier else None,
            "duration_ms": float(duration.group(2)) if duration else None,
            "phase": duration.group(1) if duration else None,
            "is_pause": bool(duration and "Pause " in line),
            "is_concurrent": bool(duration and "Concurrent " in line),
            "text": line,
        }
        if heap:
            item["heap_before_bytes"] = bytes_value(heap.group(1), heap.group(2))
            item["heap_after_bytes"] = bytes_value(heap.group(3), heap.group(4))
            item["heap_capacity_bytes"] = bytes_value(heap.group(5), heap.group(6))
        events.append(item)
        if identifier and not duration and not heap:
            unknown_gc.append(item)
    return {"events": events, "unclassified_gc_events": unknown_gc,
            "malformed_gc_lines": malformed}


def load_log(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"available": False, "events": [], "unclassified_gc_events": [],
                "malformed_gc_lines": [], "path": str(path)}
    data = parse_lines(path.read_text(encoding="utf-8", errors="replace").splitlines())
    data.update({"available": True, "path": str(path)})
    return data


def window_summary(parsed: dict, start_epoch_ms: float, end_epoch_ms: float) -> dict:
    """Diagnostic overlapping-event summary, *not* a qualification gate.

    Unified log timestamps normally mark an event's completion; approximate
    its interval by subtracting the logged duration. Concurrent events can
    span a longer cycle and some phases have no duration: neither absence of
    overlap nor absence of a line proves that GC was idle.
    """
    if end_epoch_ms < start_epoch_ms:
        raise ValueError("window ends before it starts")
    if not parsed["available"]:
        return {"known": False, "reason": "missing_gc_log"}
    matches = []
    for event in parsed["events"]:
        start = event["epoch_ms"] - (event["duration_ms"] or 0)
        if start <= end_epoch_ms and event["epoch_ms"] >= start_epoch_ms:
            matches.append(event)
    return {
        "known": True,
        "observed_events": len(matches),
        "observed_pauses": sum(x["is_pause"] for x in matches),
        "observed_concurrent_phases": sum(x["is_concurrent"] for x in matches),
        "observed_logged_pause_ms": sum(
            x["duration_ms"] or 0 for x in matches if x["is_pause"]
        ),
        "events": matches,
        "limitations": "Completion timestamps; undecoded cycle boundaries and logging gaps mean zero events != GC-quiet.",
    }
