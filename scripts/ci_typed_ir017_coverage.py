#!/usr/bin/env python3
"""IR-017 exact-source expansion inventory against SHA-pinned publisher packs.

Conservative source-shape lower-bound candidates only; not parsed Minecraft
acceptance, actual hotness, or CPU time. Compares IR-016 old source language to
IR-017 ranged mutation/guarded four-operation source language, unchanged packs.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
import re

from ci_typed_ir015_coverage import PINS, ROOT, shape as old_shape
from run_specialization_inventory import Pack

OUT = ROOT / "build/reports/COMPILER-IR-017-COVERAGE"
HOLDER = r"#[A-Za-z0-9_.+\-]+"
OBJECTIVE = r"[A-Za-z0-9_.+\-]+"
RANGE = r"(?:-?\d+(?:\.\.(?:-?\d+)?)?|\.\.-?\d+)"
MUTATION = (
    rf"scoreboard players (?:add|set|remove) "
    rf"{HOLDER} {OBJECTIVE} -?\d+"
)
BINARY = (
    rf"scoreboard players operation {HOLDER} {OBJECTIVE} "
    rf"(?:=|\+=|-=|\*=) {HOLDER} {OBJECTIVE}"
)
GUARD = re.compile(
    rf"^execute (?:if|unless) score {HOLDER} {OBJECTIVE} "
    rf"matches (?P<range>{RANGE}) "
    rf"run (?P<terminal>{MUTATION}|{BINARY})$"
)


def ir017_shape(line: str) -> str | None:
    old = old_shape(line)
    if old is not None:
        return old
    if "$(" in line:
        return None
    matched = GUARD.fullmatch(line)
    if not matched:
        return None
    if matched.group("terminal").startswith("scoreboard players operation "):
        return "guarded_binary"
    return "ranged_mutation" if ".." in matched.group("range") else None


def segment_counts(lines: list[str], classifier) -> dict:
    kinds = [classifier(x) for x in lines]
    region_lines = 0
    regions = 0
    singletons = 0
    pos = 0
    while pos < len(kinds):
        if kinds[pos] is None:
            pos += 1
            continue
        end = pos
        while end < len(kinds) and kinds[end] is not None:
            end += 1
        for start in range(pos, end, 64):
            length = min(64, end - start)
            if length >= 2:
                regions += 1
                region_lines += length
            else:
                singletons += 1
        pos = end
    return {
        "typed_lines": sum(x is not None for x in kinds),
        "region_lines": region_lines,
        "region_count": regions,
        "singleton_lines": singletons,
        "complete_source_candidate": (2 <= len(lines) <= 4096
                                      and all(x is not None for x in kinds)
                                      and region_lines == len(lines)),
        "kinds": dict(Counter(k for k in kinds if k is not None)),
    }


def audit(name: str) -> dict:
    spec = PINS[name]
    path = Path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Original publisher ZIP missing: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != spec["sha256"]:
        raise ValueError(f"Original {name} publisher SHA-256 mismatch: {digest}")
    pack = Pack(name, path, digest)
    ticking = pack.reachable(("minecraft:tick",)) | pack.scheduled_from(
        ("minecraft:load",))
    totals = Counter()
    kinds = Counter()
    improvement_candidates = []
    for function, lines in sorted(pack.functions.items()):
        old = segment_counts(lines, old_shape)
        new = segment_counts(lines, ir017_shape)
        in_tick = function in ticking
        totals["functions"] += 1
        totals["source_lines"] += len(lines)
        for prefix, stat in (("old", old), ("ir017", new)):
            for field in ("typed_lines", "region_lines", "region_count", "singleton_lines"):
                totals[f"{prefix}_{field}"] += stat[field]
                if in_tick:
                    totals[f"tick_scope_{prefix}_{field}"] += stat[field]
            if stat["complete_source_candidate"]:
                totals[f"{prefix}_complete_candidates"] += 1
                if in_tick:
                    totals[f"tick_scope_{prefix}_complete_candidates"] += 1
        kinds.update(new["kinds"])
        if new["typed_lines"] > old["typed_lines"]:
            totals["functions_with_new_source_shapes"] += 1
            if in_tick:
                totals["tick_scope_functions_with_new_source_shapes"] += 1
            improvement_candidates.append({
                "function": function, "tick_scope": in_tick,
                "source_lines": len(lines),
                "old_typed": old["typed_lines"], "new_typed": new["typed_lines"],
                "old_region_lines": old["region_lines"],
                "new_region_lines": new["region_lines"],
                "new_direct_candidate": new["complete_source_candidate"],
                "added_shapes": dict(Counter(ir017_shape(x) for x in lines
                                              if old_shape(x) is None
                                              and ir017_shape(x) is not None)),
            })
    improvement_candidates.sort(key=lambda x:(
        not x["tick_scope"], -(x["new_region_lines"] - x["old_region_lines"]),
        -(x["new_typed"] - x["old_typed"]), x["function"]))
    totals["new_source_shapes"] = totals["ir017_typed_lines"] - totals["old_typed_lines"]
    totals["additional_region_lines"] = (
        totals["ir017_region_lines"] - totals["old_region_lines"])
    totals["tick_scope_additional_region_lines"] = (
        totals["tick_scope_ir017_region_lines"] -
        totals["tick_scope_old_region_lines"])
    return {
        "pack": name, "sha256": digest, "source_shape_only": True,
        "totals": dict(totals), "ir017_kinds": dict(kinds),
        "top_changed_functions": improvement_candidates[:30],
        "all_changed_functions": improvement_candidates,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "milestone": "COMPILER-IR-017",
        "evidence": "exact_original_source_shapes_not_runtime_or_cpu",
        "no_performance_claim": True,
        "packs": {},
    }
    for name in PINS:
        data = audit(name)
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
        report["packs"][name] = {
            key: data[key] for key in (
                "pack", "sha256", "source_shape_only",
                "totals", "ir017_kinds", "top_changed_functions")
        }
        print("IR017_COVERAGE " + json.dumps(report["packs"][name],
                                              sort_keys=True), flush=True)
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
