#!/usr/bin/env python3
"""Validate complete function-entry and ordinary-callback event-window census.

Rows represent reached UnboundEntryAction executions and ordinary Brigadier
terminal callbacks. In particular, entries of custom executors count as
reached but do not imply their terminal callback executed.
"""
from __future__ import annotations

from pathlib import Path
import re

_BEGIN = re.compile(
    r"FC_EXEC_BEGIN namespace=(\S+) sites=(\d+) entries=(\d+) callbacks=(\d+) overflow=(\d+) targets=(\d+)"
)
_ROW = re.compile(
    r"FC_EXEC_ROW function=(\S+) index=(\d+) entries=(\d+) callbacks=(\d+) kind=(\S+) input=(.*)$"
)
_END = re.compile(
    r"FC_EXEC_END namespace=(\S+) sites=(\d+) entries=(\d+) callbacks=(\d+) overflow=(\d+)"
)


def parse_exec_census(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    beginnings = [m for line in lines if (m := _BEGIN.search(line))]
    endings = [m for line in lines if (m := _END.search(line))]
    if len(beginnings) != 1 or len(endings) != 1:
        raise ValueError("Exactly one bounded event begin/end required")
    begin, end = beginnings[0], endings[0]
    namespace, sites, entries, callbacks, overflow, targets = begin.groups()
    sites, entries, callbacks, overflow, targets = (
        int(sites), int(entries), int(callbacks), int(overflow), int(targets)
    )
    if (
        end.group(1) != namespace
        or tuple(int(x) for x in end.groups()[1:])
        != (sites, entries, callbacks, overflow)
    ):
        raise ValueError("Event-window begin/end totals disagree")
    if overflow:
        raise ValueError(f"Lost {overflow} sites to bounded census overflow")
    if not targets:
        raise ValueError("No explicit target functions")
    rows = []
    seen = set()
    for line in lines:
        match = _ROW.search(line)
        if not match:
            continue
        function, index, entry_count, callback_count, kind, example = match.groups()
        index, entry_count, callback_count = (
            int(index), int(entry_count), int(callback_count)
        )
        if (not function.startswith(namespace + ":") or
            (function, index) in seen or
            kind not in {
                "ordinary_callback", "custom_executor", "non_brigadier",
                "no_executable", "no_callback", "mixed",
            }):
            raise ValueError("Duplicate site, out-of-scope function, or invalid kind")
        if kind in {"custom_executor", "non_brigadier", "no_executable", "no_callback"} and callback_count:
            raise ValueError("A callback was counted for a non-Brigadier terminal")
        if entry_count < 0 or callback_count < 0:
            raise ValueError("Negative execution/callback count")
        seen.add((function, index))
        rows.append({
            "function": function, "index": index,
            "entries": entry_count, "callbacks": callback_count,
            "kind": kind, "example": example,
        })
    if (
        len(rows) != sites
        or sum(r["entries"] for r in rows) != entries
        or sum(r["callbacks"] for r in rows) != callbacks
    ):
        raise ValueError("Per-site counts do not conserve event totals")
    return {
        "namespace": namespace, "target_count": targets,
        "sites": sites, "entries": entries, "ordinary_callbacks": callbacks,
        "rows": rows,
    }


def top_sites(report: dict, count: int = 20) -> list[dict]:
    return sorted(
        report["rows"],
        key=lambda row: (-row["entries"], -row["callbacks"], row["function"], row["index"])
    )[:count]
