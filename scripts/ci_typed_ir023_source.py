#!/usr/bin/env python3
"""IR-023 read-only publisher source screen; NOT a mutation-frequency measurement.

No compiler opcode, selector replacement, or game behavior is changed.
Static commands do not reveal command execution counts, third-party mutations,
world/chunk lifecycle events, or whether index invalidation is economically safe.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ci_typed_ir015_coverage import PINS

OUT = ROOT / "build/reports/COMPILER-IR-023-SOURCE"
PIN = PINS["blastback"]["sha256"]
PACK = Path(PINS["blastback"]["path"])
FUNCTION_PATH = re.compile(r"^data/([^/]+)/functions?/(.+)\.mcfunction$")
EXACT_SELECTOR = (
    "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified] "
    "if score @s erb.job = #active erb.job "
    "run scoreboard players set #needs_restore erb.tmp 1"
)
WATCHED_TAGS = ("erb.block", "erb.verified")
TAG_WRITE = re.compile(r"(?:^|\brun\s+)tag\s+\S+\s+(add|remove)\s+([A-Za-z0-9_.+\-]+)$")
SPAWN = re.compile(r"(?:^|\brun\s+)summon\s+")
KILL = re.compile(r"(?:^|\brun\s+)kill(?:\s|$)")
EXAMPLES = 24


def read_functions(raw: bytes) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        for path in archive.namelist():
            matched = FUNCTION_PATH.fullmatch(path)
            if not matched:
                continue
            namespace, function_path = matched.groups()
            fid = f"{namespace}:{function_path}"
            if fid in result:
                raise AssertionError(f"Duplicate original function identifier: {fid}")
            lines = archive.read(path).decode("utf-8", errors="strict").splitlines()
            result[fid] = [line.strip() for line in lines
                           if line.strip() and not line.lstrip().startswith("#")]
    return result


def audit_archive(raw: bytes, expected_sha: str) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise AssertionError(f"Original publisher SHA mismatch: {digest} != {expected_sha}")
    functions = read_functions(raw)
    target = functions.get("erb:restore/job_tick")
    if target is None or len(target) <= 4 or target[4] != EXACT_SELECTOR:
        raise AssertionError("Original restore/job_tick index-4 selector changed")
    totals: Counter[str] = Counter()
    examples: dict[str, list[dict]] = {}
    by_function: Counter[str] = Counter()
    for fid, commands in sorted(functions.items()):
        totals["functions"] += 1
        for zero, command in enumerate(commands):
            totals["source_commands"] += 1
            kinds: list[str] = []
            if command == EXACT_SELECTOR:
                kinds.append("exact_selector")
            elif "tag=erb.block" in command or "tag=!erb.verified" in command:
                kinds.append("related_selector_or_tag_read")
            dynamic = "$(" in command
            if dynamic:
                kinds.append("macro_unresolved")
            operation = TAG_WRITE.search(command)
            if operation and not dynamic:
                action, tag = operation.groups()
                kinds.append("tag_command_" + action)
                if tag in WATCHED_TAGS:
                    kinds.append("watched_tag_" + action)
            # Data/NBT editing is NOT equivalent to a vanilla /tag command:
            # capture it as an unresolved path, even when its target is dynamic.
            if re.search(r"(?:^|\brun\s+)data\s+(?:merge|modify|remove)\s+entity\b", command):
                kinds.append("entity_nbt_edit_unresolved")
            if re.search(r"(?<![A-Za-z0-9_])Tags\s*:", command) or ".Tags" in command:
                kinds.append("nbt_tags_reference_unresolved")
            if SPAWN.search(command):
                kinds.append("summon_source_site")
            if KILL.search(command):
                kinds.append("kill_source_site")
            # Entity removal via other hooks, dimensions, chunk unloads and
            # external mods are NOT accounted for by these source expressions.
            for kind in set(kinds):
                totals[kind] += 1
                if kind in ("watched_tag_add", "watched_tag_remove",
                            "entity_nbt_edit_unresolved", "nbt_tags_reference_unresolved",
                            "macro_unresolved", "summon_source_site", "kill_source_site",
                            "exact_selector"):
                    examples.setdefault(kind, [])
                    if len(examples[kind]) < EXAMPLES:
                        examples[kind].append({
                            "function": fid, "command_index_0based": zero,
                            "command": command[:320]
                        })
            if kinds:
                by_function[fid] += 1
    if totals["exact_selector"] != 1:
        raise AssertionError("Expected exactly one original full-line selector")
    return {
        "milestone": "COMPILER-IR-023",
        "status": "original_publisher_static_source_only",
        "publisher_sha256": digest,
        "original_selector_command_index_0based": 4,
        "totals": dict(sorted(totals.items())),
        "functions_with_any_relevant_sites": len(by_function),
        "examples": examples,
        "caveats": [
            "All counts are literal source occurrences, never runtime call frequencies",
            "Nested execute and macro expansion may change reachability or effects",
            "Tag commands may target other entities; matching a tag name does not prove target identity",
            "Entity NBT, spawn, kill, chunk lifecycle and third-party changes need native inspection",
            "A combined-predicate failure does not establish a watched-tag failure",
            "No index safety, mutation rate, CPU savings or complete restoration is established"
        ],
        "requires_native_mutation_and_visibility_study": True,
        "selector_optimization_implemented": False,
        "causal_speedup_claim": False,
    }


def main() -> None:
    if not PACK.is_file():
        raise FileNotFoundError(f"Pinned original publisher ZIP unavailable: {PACK}")
    report = audit_archive(PACK.read_bytes(), PIN)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR023_SOURCE_AUDIT " + json.dumps({
        "status": report["status"], "sha256": report["publisher_sha256"],
        "totals": report["totals"],
        "requires_native_mutation_and_visibility_study": True
    }), flush=True)


if __name__ == "__main__":
    main()
