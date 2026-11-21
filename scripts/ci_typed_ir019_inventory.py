#!/usr/bin/env python3
"""IR-019: distinguish exact single-score conditional calls from complex calls.

Pure source-shape screening of unchanged SHA-pinned Vein Miner / Blastback.
Does not imply Brigadier admission, native scheduling correctness, dynamic
frequency, condition pass rate, child completion or speedup.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from ci_typed_ir015_coverage import PINS, ROOT
from run_specialization_inventory import Pack

OUT = ROOT / "build/reports/COMPILER-IR-019-INVENTORY"
SCORE_HOLDER = r"(?:#[A-Za-z0-9_.+\-]+|@s)"
OBJECTIVE = r"[A-Za-z0-9_.+\-]+"
SCORE_RANGE = r"(?:-?\d+(?:\.\.(?:-?\d+)?)?|\.\.-?\d+)"
CALLEE = r"[a-z0-9_.-]+:[a-z0-9_./-]+"
EXACT = re.compile(
    rf"^execute (?:if|unless) score {SCORE_HOLDER} {OBJECTIVE} "
    rf"matches {SCORE_RANGE} run function (?P<callee>{CALLEE})$")
BROAD = re.compile(r"^execute (?:if|unless) score .+ run (?:return run )?function .+$")
STATIC_DIRECT = re.compile(r"\bfunction ([a-z0-9_.-]+:[a-z0-9_./-]+)\b")


def classify(line: str) -> str:
    if EXACT.fullmatch(line) is not None:
        return "single_score_static_child"
    if BROAD.fullmatch(line) is not None:
        return "complex_or_return_child"
    return "other"


def audit(name: str) -> dict:
    pin=PINS[name]
    archive=Path(pin["path"])
    if not archive.is_file():
        raise FileNotFoundError(archive)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest!=pin["sha256"]:
        raise ValueError(f"Original-publisher ZIP changed: {name}")
    pack=Pack(name,archive,digest)
    ticking=pack.reachable(("minecraft:tick",)) | pack.scheduled_from(("minecraft:load",))
    totals=Counter()
    callee_counts=Counter()
    non_simple_examples=[]
    simple_sites=[]
    by_function=[]
    for func,lines in sorted(pack.functions.items()):
        local=Counter()
        for index,line in enumerate(lines):
            shape=classify(line)
            if shape=="other":
                continue
            local[shape]+=1
            totals[shape+"_source_lines"]+=1
            if func in ticking:
                totals["tick_"+shape+"_source_lines"]+=1
            if shape=="single_score_static_child":
                callee=EXACT.fullmatch(line).group("callee")
                callee_counts[callee]+=1
                if len(simple_sites)<200:
                    simple_sites.append({"function":func,"index0":index,
                                        "callee":callee,"tick_scope":func in ticking,
                                        "input":line})
            elif len(non_simple_examples)<60 and (
                    func.startswith("erb:capture/")
                    or func.startswith("erb:restore/")
                    or func.startswith("vm:")):
                non_simple_examples.append({"function":func,"index0":index,
                                            "tick_scope":func in ticking,
                                            "input":line[:270]})
        if sum(local.values())>0:
            by_function.append({
                "function":func,"tick_scope":func in ticking,
                "single":local["single_score_static_child"],
                "complex":local["complex_or_return_child"],
                "lines":len(lines)})
    totals["functions_with_any_dispatch"]=len(by_function)
    totals["functions"]=len(pack.functions)
    totals["source_lines"]=sum(map(len,pack.functions.values()))
    totals["unique_simple_callees"]=len(callee_counts)
    by_function.sort(key=lambda x:(not x["tick_scope"],-x["single"],-x["complex"],x["function"]))
    return {
        "name":name,"publisher_sha256":digest,"source_only":True,
        "no_runtime_frequency_or_cpu_claim":True,
        "totals":dict(totals),
        "top_source_functions":by_function[:40],
        "simple_source_samples":simple_sites[:100],
        "non_simple_samples":non_simple_examples[:35],
        "most_referenced_simple_callees":callee_counts.most_common(40),
    }


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"milestone":"COMPILER-IR-019","stage":"original_source_candidate_stratification",
            "source_only":True,"packs":{}}
    for name in PINS:
        data=audit(name)
        report["packs"][name]=data
        (OUT/f"{name}.json").write_text(json.dumps(data,indent=2)+"\n")
        print("IR019_INVENTORY "+json.dumps(data,sort_keys=True),flush=True)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":
    main()
