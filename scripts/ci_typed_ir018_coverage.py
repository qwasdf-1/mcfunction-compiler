#!/usr/bin/env python3
"""IR-018 conservative @s compiler coverage and original function-dispatch inventory.

The same two original publisher ZIPs from IR-015/IR-017 are independently
SHA-pinned. Source-only screening cannot establish Brigadier/parser acceptance,
macro instantiation, execution frequency, native fidelity or CPU savings.
Conditional function dispatch stays an *opaque* Minecraft queue barrier.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from ci_typed_ir015_coverage import ROOT, PINS
from ci_typed_ir017_coverage import ir017_shape, segment_counts, RANGE
from run_specialization_inventory import Pack

OUT = ROOT / "build/reports/COMPILER-IR-018-COVERAGE"
HOLDER = r"(?:#[A-Za-z0-9_.+\-]+|@s)"
OBJ = r"[A-Za-z0-9_.+\-]+"
MUT = rf"scoreboard players (?:add|set|remove) {HOLDER} {OBJ} -?\d+"
BIN = rf"scoreboard players operation {HOLDER} {OBJ} (?:=|\+=|-=|\*=) {HOLDER} {OBJ}"
MUT_PATTERN = re.compile("^" + MUT + "$")
BIN_PATTERN = re.compile("^" + BIN + "$")
GUARD_PATTERN = re.compile(
    rf"^execute (?:if|unless) score {HOLDER} {OBJ} matches {RANGE} "
    rf"run (?P<terminal>{MUT}|{BIN})$")
DISPATCH = re.compile(
    r"^execute (?:if|unless) score .+ run function .+$")


def classifier(line: str) -> str | None:
    prev = ir017_shape(line)
    if prev is not None:
        return prev
    if "$(" in line or "@s" not in line:
        return None
    if MUT_PATTERN.fullmatch(line):
        return "self_mutation"
    if BIN_PATTERN.fullmatch(line):
        return "self_binary"
    match = GUARD_PATTERN.fullmatch(line)
    if match is not None:
        return ("self_guarded_binary"
                if match.group("terminal").startswith("scoreboard players operation")
                else "self_guarded_mutation")
    return None


def audit(name: str) -> dict:
    spec = PINS[name]
    path = Path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Pinned publisher ZIP missing: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != spec["sha256"]:
        raise ValueError(f"Original publisher SHA mismatch: {name}")
    pack=Pack(name,path,digest)
    ticking=pack.reachable(("minecraft:tick",)) | pack.scheduled_from(
        ("minecraft:load",))
    totals=Counter()
    kinds=Counter()
    dispatch_examples=[]
    candidate_examples=[]
    for fid, lines in sorted(pack.functions.items()):
        old=segment_counts(lines, ir017_shape)
        new=segment_counts(lines, classifier)
        is_tick = fid in ticking
        totals["functions"] += 1
        totals["source_lines"] += len(lines)
        for prefix, stats in (("ir017", old), ("ir018", new)):
            totals[f"{prefix}_source_lines"] += stats["typed_lines"]
            totals[f"{prefix}_region_lines"] += stats["region_lines"]
            totals[f"{prefix}_regions"] += stats["region_count"]
            totals[f"{prefix}_complete_functions"] += int(stats["complete_source_candidate"])
            if is_tick:
                totals[f"tick_{prefix}_region_lines"] += stats["region_lines"]
                totals[f"tick_{prefix}_complete_functions"] += int(
                    stats["complete_source_candidate"])
        kinds.update(new["kinds"])
        commands=[line for line in lines if DISPATCH.fullmatch(line)]
        totals["source_text_guarded_function_dispatches"] += len(commands)
        if is_tick:
            totals["tick_source_text_guarded_function_dispatches"] += len(commands)
        if commands and len(dispatch_examples)<25:
            dispatch_examples.append({
                "function":fid,"tick_scope":is_tick,
                "count":len(commands),"example":commands[0][:250]})
        if new["typed_lines"]>old["typed_lines"]:
            totals["functions_with_new_self_source"] += 1
            if is_tick: totals["tick_functions_with_new_self_source"] += 1
            candidate_examples.append({
                "function":fid,"tick_scope":is_tick,
                "old_typed":old["typed_lines"],"new_typed":new["typed_lines"],
                "old_region":old["region_lines"],"new_region":new["region_lines"],
                "source_size":len(lines),
                "example":next((s[:250] for s in lines if classifier(s) is not None
                                 and ir017_shape(s) is None),""),
            })
    totals["added_self_source_lines"] = (
        totals["ir018_source_lines"]-totals["ir017_source_lines"])
    totals["added_region_lines"] = (
        totals["ir018_region_lines"]-totals["ir017_region_lines"])
    totals["tick_added_region_lines"] = (
        totals["tick_ir018_region_lines"]-totals["tick_ir017_region_lines"])
    candidate_examples.sort(key=lambda x:(not x["tick_scope"],
        -(x["new_region"]-x["old_region"]),-(x["new_typed"]-x["old_typed"]),
        x["function"]))
    dispatch_examples.sort(key=lambda x:(not x["tick_scope"],-x["count"],x["function"]))
    return {
        "pack":name,"sha256":digest,"source_shape_only":True,
        "guarded_function_dispatch_compiled":False,
        "totals":dict(totals),"typed_families":dict(kinds),
        "changed_functions":candidate_examples,
        "guarded_dispatch_functions_sample":dispatch_examples,
    }


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"milestone":"COMPILER-IR-018",
            "evidence":"static_source_shape_only_not_runtime_or_performance",
            "no_cpu_claim":True,"packs":{}}
    for name in PINS:
        data=audit(name)
        (OUT/f"{name}.json").write_text(json.dumps(data,indent=2)+"\n")
        public={k:data[k] for k in ("pack","sha256","source_shape_only",
                                   "guarded_function_dispatch_compiled",
                                   "totals","typed_families")}
        public["top_changed_functions"]=data["changed_functions"][:25]
        public["dispatch_samples"]=data["guarded_dispatch_functions_sample"][:12]
        report["packs"][name]=public
        print("IR018_COVERAGE "+json.dumps(public,sort_keys=True),flush=True)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    main()
