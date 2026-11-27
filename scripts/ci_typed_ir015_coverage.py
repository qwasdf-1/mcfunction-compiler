#!/usr/bin/env python3
"""IR-015: conservative exact-source-shape screen against existing typed IR.

This is a source coverage census, NOT a parser or native execution census.
Only the existing Brigadier-validated typed wrappers can prove runtime
compilation. Macro instantiations and dynamic call frequencies are unknown.

Inputs: SHA-256 pinned original publisher Vein Miner and Blastback ZIPs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from run_specialization_inventory import Pack, PACKS, command_lines

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-015"
PINS = {
    "veinminer": {
        "path": PACKS["veinminer"]["path"],
        "sha256": PACKS["veinminer"]["sha256"],
    },
    "blastback": {
        "path": ROOT / "references/real-world/candidates/Blastback-Hotfix-3-26.3.zip",
        "sha256": "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90",
    },
}
HOLDER = r"#[A-Za-z0-9_.+\-]+"
OBJ = r"[A-Za-z0-9_.+\-]+"
VALUE = r"-?\d+"
MUTATION = re.compile(
    rf"^scoreboard players (?:add|set|remove) {HOLDER} {OBJ} {VALUE}$"
)
BINARY = re.compile(
    rf"^scoreboard players operation {HOLDER} {OBJ} (?:=|\+=|-=|\*=) {HOLDER} {OBJ}$"
)
GUARD = re.compile(
    rf"^execute (?:if|unless) score {HOLDER} {OBJ} matches {VALUE} "
    rf"run scoreboard players (?:add|set|remove) {HOLDER} {OBJ} {VALUE}$"
)
ROOTS = ("scoreboard", "execute", "function", "data", "return", "schedule")


def shape(line: str) -> str | None:
    # Original macro source may contain placeholders. A source match does
    # not prove an instantiated macro will have the same shape or even parse.
    if "$(" in line:
        return None
    if MUTATION.fullmatch(line):
        return "mutation"
    if BINARY.fullmatch(line):
        return "binary"
    if GUARD.fullmatch(line):
        return "guard"
    return None


def barrier(line: str) -> str:
    words = line.split()
    if not words:
        return "(blank)"
    root = words[0]
    if "$(" in line:
        return "macro_placeholder"
    if root == "scoreboard":
        return "scoreboard_other"
    if root == "execute":
        if " run " in line:
            tail = line.rsplit(" run ", 1)[-1]
            if tail.startswith("function "):
                return "execute_run_function"
            if tail.startswith("scoreboard "):
                return "execute_run_scoreboard_other"
        return "execute_other"
    if root == "function":
        return "function_call"
    if root in ROOTS:
        return root + "_other"
    return root


def segment(lines: list[str]) -> dict:
    """Replicate IR-008 flush and IR-012 completely-compiled admission.

    Every maximal typed run is chunked into <=64. Singleton chunks stay
    original vanilla entries. This is only a static source-shape model.
    """
    kinds = [shape(line) for line in lines]
    regions = []
    compiled_commands = 0
    singleton_commands = 0
    start = 0
    while start < len(kinds):
        if kinds[start] is None:
            start += 1
            continue
        end = start
        while end < len(kinds) and kinds[end] is not None:
            end += 1
        for index in range(start, end, 64):
            length = min(64, end - index)
            if length >= 2:
                compiled_commands += length
                regions.append({"start": index + 1, "length": length,
                                "shapes": dict(Counter(kinds[index:index+length]))})
            else:
                singleton_commands += 1
        start = end
    fully_typed = len(lines) >= 2 and all(k is not None for k in kinds)
    direct_candidate = (fully_typed and len(lines) <= 4096
                        and compiled_commands == len(lines))
    return {
        "lines": len(lines),
        "shapes": dict(Counter(k for k in kinds if k is not None)),
        "source_shaped_commands": sum(x is not None for x in kinds),
        "source_shaped_region_commands": compiled_commands,
        "source_shaped_singletons": singleton_commands,
        "candidate_regions": regions,
        "possible_direct_function": direct_candidate,
        "barriers": dict(Counter(barrier(line) for line, k in zip(lines, kinds)
                                 if k is None)),
    }


def audit_pack(name: str, path: Path, expected_sha: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Pinned publisher ZIP missing: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha:
        raise ValueError(f"{name}: SHA-256 mismatch {digest} != {expected_sha}")
    pack = Pack(name, path, digest)
    load_tick = pack.reachable(("minecraft:load", "minecraft:tick"))
    ticking = pack.reachable(("minecraft:tick",)) | pack.scheduled_from(
        ("minecraft:load",))
    totals = Counter()
    barriers = Counter()
    shapes = Counter()
    blockers_sample = {}
    functions = []
    for function_id, lines in sorted(pack.functions.items()):
        stat = segment(lines)
        totals["functions"] += 1
        totals["source_command_lines"] += len(lines)
        totals["source_shaped_instructions"] += stat["source_shaped_commands"]
        totals["region_commands"] += stat["source_shaped_region_commands"]
        totals["compiled_region_candidates"] += len(stat["candidate_regions"])
        totals["singleton_source_shaped_commands"] += stat["source_shaped_singletons"]
        totals["possible_direct_functions"] += int(stat["possible_direct_function"])
        if function_id in ticking:
            totals["tick_scope_functions"] += 1
            totals["tick_scope_lines"] += len(lines)
            totals["tick_scope_region_commands"] += stat["source_shaped_region_commands"]
            totals["tick_scope_direct_functions"] += int(stat["possible_direct_function"])
        if function_id in load_tick:
            totals["load_tick_scope_functions"] += 1
        barriers.update(stat["barriers"])
        shapes.update(stat["shapes"])
        for line in lines:
            if shape(line) is None:
                kind = barrier(line)
                blockers_sample.setdefault(kind, [])
                if len(blockers_sample[kind]) < 6 and line not in blockers_sample[kind]:
                    blockers_sample[kind].append(line[:230])
        functions.append({
            "id": function_id,
            "in_tick_scope": function_id in ticking,
            "in_load_tick_scope": function_id in load_tick,
            **stat,
        })
    ranked = sorted(functions, key=lambda f:(
        -int(f["in_tick_scope"]), -f["source_shaped_region_commands"],
        -f["source_shaped_commands"], f["id"]))
    return {
        "pack": name,
        "sha256": digest,
        "total": dict(totals),
        "source_shaped_family_totals": dict(shapes),
        "barrier_totals": dict(barriers),
        "barrier_examples": blockers_sample,
        "top_candidates": ranked[:40],
        "possible_direct_functions": [
            {"id": f["id"], "lines": f["lines"], "tick": f["in_tick_scope"]}
            for f in functions if f["possible_direct_function"]
        ][:100],
        "all_functions": functions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packs", nargs="+", choices=PINS, default=list(PINS))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "milestone": "COMPILER-IR-015",
        "evidence": "source_shape_only_not_parsed_or_executed",
        "caveat": "Native parser acceptance, macro expansions, dynamic hotness, "
                  "Brigadier wrapping, callbacks and performance are NOT measured",
        "packs": {},
    }
    for name in args.packs:
        spec = PINS[name]
        analyzed = audit_pack(name, Path(spec["path"]), spec["sha256"])
        (OUT / (name + ".full.json")).write_text(
            json.dumps(analyzed, indent=2) + "\n")
        result["packs"][name] = {
            key: analyzed[key] for key in (
                "pack", "sha256", "total", "source_shaped_family_totals",
                "barrier_totals", "barrier_examples",
                "top_candidates", "possible_direct_functions"
            )
        }
        print("IR015_PACK " + json.dumps({
            "pack": name, "sha256": analyzed["sha256"],
            "total": analyzed["total"],
            "shapes": analyzed["source_shaped_family_totals"],
            "largest_barriers": Counter(analyzed["barrier_totals"]).most_common(12),
            "candidate_functions": analyzed["possible_direct_functions"][:15],
            "blocker_examples": {k: v[:3] for k, v in sorted(
                analyzed["barrier_examples"].items(),
                key=lambda pair: -analyzed["barrier_totals"].get(pair[0], 0))[:10]},
            "ranked_regions": [
                {"id": f["id"], "tick": f["in_tick_scope"],
                 "regions": [(r["start"], r["length"])
                             for r in f["candidate_regions"]],
                 "typed_lines": f["source_shaped_commands"],
                 "all_lines": f["lines"]}
                for f in analyzed["top_candidates"][:12]
                if f["source_shaped_region_commands"]],
        }, sort_keys=True), flush=True)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
