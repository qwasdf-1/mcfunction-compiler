#!/usr/bin/env python3
"""COMPILER-BLASTBACK-007: SHA-pinned read-only Blastback source/callsite triage.

This is a compiler-eligibility *source* screen only. It does not establish
runtime activation, parser acceptance, actual CPU, or correctness of the
previous 1-TNT event (which FAILED the complete restoration gate).

Use alongside scripts/screen_adjacent_regions.py, never to bypass it.
"""
from __future__ import annotations

from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from screen_adjacent_regions import screen_pack

PACK = ROOT / "references/real-world/candidates/Blastback-Hotfix-3-26.3.zip"
PIN = "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90"
OUT = ROOT / "build/benchmarks/COMPILER-BLASTBACK-007"
FUNCTION_PATH = re.compile(r"^data/([^/]+)/functions?/(.+)\.mcfunction$")
CALL = re.compile(r"(?:^|\brun\s+)function\s+([A-Za-z0-9_.:/-]+)")
STATE_READ = re.compile(r"^execute if block .+ run scoreboard players set @s erb\.state -?\d+$")
MAX_EXAMPLE_TABLES = 5
MAX_CALLERS = 25


def verify() -> None:
    if not PACK.exists():
        raise ValueError("Original publisher Blastback archive is absent")
    checksum = hashlib.sha256(PACK.read_bytes()).hexdigest()
    if checksum != PIN:
        raise ValueError(f"Publisher ZIP SHA-256 mismatch: {checksum} != {PIN}")


def audit() -> dict:
    verify()
    function_commands: dict[str, list[str]] = {}
    callers: dict[str, set[str]] = {}
    with zipfile.ZipFile(PACK) as z:
        for path in z.namelist():
            match = FUNCTION_PATH.match(path)
            if match is None:
                continue
            namespace, rel = match.groups()
            function_id = namespace + ":" + rel
            lines = []
            for raw in z.read(path).decode("utf-8", errors="replace").splitlines():
                line = raw.strip()
                if line and not line.startswith("#"):
                    lines.append(line)
                    for target in CALL.findall(line):
                        callers.setdefault(target, set()).add(function_id)
            function_commands[function_id] = lines
    # Prior 19-pack source screen identifies the generated block-state readers.
    # Restrict to EXACT command shape so non-score and forked function bodies
    # cannot masquerade as 32-instruction table classifiers.
    candidates = []
    for name, lines in function_commands.items():
        if not (name.startswith("erb_generated:read_state/")
                and name.endswith("/root")):
            continue
        matched = [(i, line) for i, line in enumerate(lines) if STATE_READ.fullmatch(line)]
        if not matched:
            continue
        longest = 0
        start = 0
        run = 0
        for i, line in enumerate(lines):
            if STATE_READ.fullmatch(line):
                run += 1
                if run > longest:
                    longest = run
                    start = i - run + 1
            else:
                run = 0
        candidates.append({
            "function": name,
            "command_lines": len(lines),
            "matched_conditional_score_assignments": len(matched),
            "longest_contiguous_classifier_run": longest,
            "longest_run_start_0based": start,
            "longest_run_examples": lines[start:start + min(longest, 4)],
            "direct_callers": sorted(callers.get(name, set()))[:MAX_CALLERS],
            "number_direct_callers": len(callers.get(name, set())),
        })
    candidates.sort(key=lambda r: (-r["longest_contiguous_classifier_run"], r["function"]))
    if not candidates:
        raise ValueError("No exact generated block-state classifier pattern in pinned archive")
    root = "erb:capture/store"
    reachable = set()
    remaining = deque([(root, 0)])
    # Functional closure from the capture/store root, using source-only
    # direct function references. Tags and macros may be missed.
    while remaining and len(reachable) < 50000:
        name, depth = remaining.popleft()
        if name in reachable or name not in function_commands:
            continue
        reachable.add(name)
        for line in function_commands[name]:
            for target in CALL.findall(line):
                if target not in reachable:
                    remaining.append((target, depth+1))
    in_closure = [c for c in candidates if c["function"] in reachable]
    # Grounded *injected* fixture palette; not a claim that natural world
    # terrain or explosion-created blocks contain only these values.
    runner_source = (ROOT / "scripts/run_blastback_profile.py").read_text(
        encoding="utf-8")
    for invariant in (
        "fill -4 63 -4 12 63 12 minecraft:stone",
        '"gold": "gold_block"',
        '"diamond_block": "diamond_block"',
        '"redstone_block": "redstone_block"',
        '"emerald_block": "emerald_block"',
    ):
        if invariant not in runner_source:
            raise ValueError("Blastback source palette fixtures changed: " + invariant)
    injected_palette = (
        "stone", "gold_block", "diamond_block",
        "redstone_block", "emerald_block", "tnt", "air"
    )
    palette_tables = []
    for block in injected_palette:
        name = "erb_generated:read_state/minecraft/" + block + "/root"
        lines = function_commands.get(name)
        palette_tables.append({
            "block": block,
            "function": name,
            "source_present": lines is not None,
            "command_lines": len(lines) if lines is not None else None,
            "classifier_commands": sum(
                bool(STATE_READ.fullmatch(line)) for line in (lines or [])),
            "reached_during_capture": None,
        })
    selected_sources = {
        function: function_commands.get(function, [])[:30]
        for function in (
            "erb:capture/store",
            "erb_generated:read/root",
            "erb:runtime_tick",
            "erb:status/collect",
        )
    }
    existing = screen_pack(PACK, min_run=2, max_examples=10)
    result = {
        "study": "COMPILER-BLASTBACK-007", "status": "pinned-static-source-only",
        "source_sha256": PIN, "functions_parsed": len(function_commands),
        "capture_source_root": root, "capture_direct_call_closure": len(reachable),
        "classifier_tables_found": len(candidates),
        "classifier_tables_directly_reachable_from_capture_store": len(in_closure),
        "highest_exact_classifier_runs": candidates[:MAX_EXAMPLE_TABLES],
        "best_capture_reachable_classifiers": in_closure[:MAX_EXAMPLE_TABLES],
        "known_injected_fixture_palette": palette_tables,
        "selected_original_source_commands": selected_sources,
        "screen_totals": {
            tier: {
                k: val for k, val in existing[tier].items()
                if k in ("tick_runs", "max_tick_run", "total_runs", "functions_with_runs")
            }
            for tier in ("literal_score", "parsed_candidates", "leaf_functions")
        },
        "limits": [
            "Any tick-reachable count is lexical source reachability; 1-TNT restoration remains invalid.",
            "A direct-source call graph can miss tags, macro-generated calls, and dynamic dispatch.",
            "Not proven FusableCommand at runtime; condition stage may be declined.",
            "No CPU, measured parser acceptance, causal speedup or state parity from source alone."
        ],
        "next_gate": (
            "Require a real 1-TNT capture-phase state invariant and exact"
            " runtime observation of named generated tables before any optimization."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source-audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = {
        "sha256": PIN, "functions": len(function_commands),
        "candidate_tables": len(candidates),
        "capture_root_direct_reachable": len(reachable),
        "classifier_tables_in_capture_closure": len(in_closure),
        "best": candidates[:2], "capture_best": in_closure[:2],
        "known_injected_fixture_palette": palette_tables,
        "selected_original_source_commands": selected_sources,
        "screen": result["screen_totals"],
    }
    print("BLASTBACK007_STATIC " + json.dumps(summary, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    audit()
