#!/usr/bin/env python3
"""COMPILER-QUEUE-005: SHA-pinned static function-call graph; NOT runtime CPU."""
from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
OUT = ROOT / "build/benchmarks/COMPILER-QUEUE-005"
ROOTS = ("vm:queue/enqueue_here", "vm:queue/enqueue_match")
MAX_NODES = 40
MAX_DEPTH = 6
CALL = re.compile(r"\bfunction\s+(vm:[a-z0-9_./-]+)(?:\s+with\b|\s|$)")


def inspect() -> dict:
    if hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
        raise ValueError("Publisher ZIP SHA-256 mismatch")
    with zipfile.ZipFile(PACK) as archive:
        functions = {}
        for name in archive.namelist():
            match = re.fullmatch(r"data/([a-z0-9_.-]+)/function/([a-z0-9_./-]+)\.mcfunction", name)
            if match:
                functions[match[1] + ":" + match[2]] = archive.read(name).decode("utf-8")
    for root in ROOTS:
        if root not in functions:
            raise ValueError(f"Required pinned source function missing: {root}")
    to_visit = deque((root, 0) for root in ROOTS)
    visited = set()
    rows = []
    while to_visit and len(rows) < MAX_NODES:
        name, depth = to_visit.popleft()
        if name in visited:
            continue
        visited.add(name)
        source = functions.get(name)
        if source is None:
            rows.append({"function": name, "missing_source": True, "depth": depth})
            continue
        commands = [line.strip() for line in source.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
        deps = sorted(set(t for cmd in commands for t in CALL.findall(cmd)))
        rows.append({
            "function": name, "depth": depth, "command_lines": len(commands),
            "commands": commands, "direct_function_targets": deps,
            "contains_macro_lines": any(x.startswith("$") for x in commands),
            "macro_with_calls": sum(" with " in x and "function " in x for x in commands),
        })
        if depth < MAX_DEPTH:
            for dep in deps:
                if dep not in visited:
                    to_visit.append((dep, depth + 1))
    result = {
        "study": "COMPILER-QUEUE-005", "pinned_zip_sha256": PIN,
        "all_functions": len(functions), "roots": list(ROOTS),
        "sources": rows, "scan_bounded": bool(to_visit),
        "limitations": [
            "Source-only graph; calls via tags or computed macro arguments can be missed.",
            "No command-execution, callback success, CPU or compiler-eligibility inference.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pinned_queue_source.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print("QUEUE005_FUNCTION " + json.dumps(row, sort_keys=True), flush=True)
    print("QUEUE005_GRAPH_SUMMARY " + json.dumps({
        "functions": len(rows), "bounded": result["scan_bounded"],
        "total_command_lines_in_graph": sum(x.get("command_lines", 0) for x in rows),
        "pinned_zip_sha256": PIN,
    }, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    inspect()
