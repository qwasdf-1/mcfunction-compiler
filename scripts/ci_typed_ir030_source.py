#!/usr/bin/env python3
"""IR-030 Gate A: exact SHA-pinned original Vein Miner source sequence proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
OUT = ROOT / "build/reports/COMPILER-IR-030-SOURCE"
APPEND_PATH = "data/vm/function/queue/append_here.mcfunction"
COMMANDS = (
    "tp @s ~ ~ ~",
    "data modify entity @s data.frontier append value {x:0,y:0,z:0}",
    "execute store result entity @s data.frontier[-1].x int 1 run data get entity @s Pos[0]",
    "execute store result entity @s data.frontier[-1].y int 1 run data get entity @s Pos[1]",
    "execute store result entity @s data.frontier[-1].z int 1 run data get entity @s Pos[2]",
)


def noncomment_commands(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines()
                 if line.strip() and not line.lstrip().startswith("#"))


def validate_sequence(text: str) -> tuple[dict, ...]:
    lines = noncomment_commands(text)
    if lines != COMMANDS:
        raise AssertionError(
            "Original append_here is not exactly the five ordered commands; "
            f"actual={lines!r}")
    return tuple({"source_index_zero_based": i, "command": line}
                 for i, line in enumerate(lines))


def inspect() -> dict:
    if not PACK.is_file():
        raise AssertionError(f"Pinned publisher archive missing: {PACK}")
    sha = hashlib.sha256(PACK.read_bytes()).hexdigest()
    if sha != PIN:
        raise AssertionError(f"Original publisher SHA mismatch: {sha}")
    with zipfile.ZipFile(PACK) as archive:
        if APPEND_PATH not in archive.namelist():
            raise AssertionError(f"Missing original publisher path {APPEND_PATH}")
        rows = validate_sequence(archive.read(APPEND_PATH).decode("utf-8"))
        sightings = {line: [] for line in COMMANDS}
        callers = []
        enqueue_callers = []
        for path in archive.namelist():
            if not path.startswith("data/") or not path.endswith(".mcfunction"):
                continue
            for index, line in enumerate(noncomment_commands(
                    archive.read(path).decode("utf-8"))):
                if line in sightings:
                    sightings[line].append({"path": path, "command_index": index})
                if "function vm:queue/append_here" in line:
                    callers.append({
                        "path": path, "command_index": index, "command": line,
                    })
                if "function vm:queue/enqueue_match" in line:
                    enqueue_callers.append({
                        "path": path, "command_index": index, "command": line,
                    })
    for i, cmd in enumerate(COMMANDS):
        if sightings[cmd] != [{"path": APPEND_PATH, "command_index": i}]:
            raise AssertionError(f"Original command not unique to its ordinal: {cmd}")
    result = {
        "milestone": "COMPILER-IR-030-GATE-A-SOURCE",
        "status": "verified_exact_original_source_only",
        "publisher_sha256": sha,
        "function": "vm:queue/append_here",
        "commands": rows,
        "append_here_call_sites": callers,
        "enqueue_match_call_sites": enqueue_callers,
        "runtime_code_changed": False,
        "parsed_brigadier_chain_verified": False,
        "native_semantic_equivalence_proven": False,
        "cpu_speedup_measured": False,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source.json").write_text(json.dumps(result, indent=2) + "\n",
                                      encoding="utf-8")
    print("IR030_ORIGINAL_SOURCE_VERIFIED " + json.dumps({
        "sha256": sha, "function": result["function"],
        "source_ordinals": list(range(len(COMMANDS))),
        "append_here_call_sites": callers,
        "enqueue_match_call_sites": enqueue_callers,
        "native_semantic_equivalence_proven": False,
    }), flush=True)
    return result


if __name__ == "__main__":
    inspect()
