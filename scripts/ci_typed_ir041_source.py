#!/usr/bin/env python3
"""Static IR040 candidate screen of SHA-pinned publisher packs, not runtime coverage."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from collections import Counter
from ci_typed_ir015_coverage import PINS, ROOT, barrier
from ci_typed_ir017_coverage import segment_counts
from run_specialization_inventory import Pack

OUT=ROOT/"build/reports/COMPILER-IR-041-SOURCE"
H=r"(?:#[A-Za-z0-9_.+\-]+|@s)"
O=r"[A-Za-z0-9_.+\-]+"
I=r"-?\d+"
R=rf"(?:{I}(?:\.\.(?:{I})?)?|\.\.{I})"
M=rf"scoreboard players (?:add|set|remove) {H} {O} {I}"
B=rf"scoreboard players operation {H} {O} (?:=|\+=|-=|\*=|<|>|/=|%=|><) {H} {O}"
P=rf"(?:if|unless) score {H} {O} (?:matches {R}|(?:=|<=|>=|<|>) {H} {O})"
TERMINAL=re.compile(rf"(?:{M}|{B})")
PREDICATE=re.compile(rf"(?:{P})(?: |$)")
SPECIAL=re.compile(r" (?:/=|%=|><) ")

def shape(line):
    if "$(" in line: return None
    if TERMINAL.fullmatch(line):
        return "arithmetic" if SPECIAL.search(line) else "plain"
    if not line.startswith("execute ") or " run " not in line: return None
    prefix,tail=line[8:].split(" run ",1)
    if not TERMINAL.fullmatch(tail): return None
    pos=0
    count=0
    while pos<len(prefix):
        m=PREDICATE.match(prefix,pos)
        if not m: return None
        count+=1
        pos=m.end()
    if count==1 and not SPECIAL.search(tail): return "single_guard"
    if 2<=count<=8: return "compound"
    return None

def audit(name):
    pin=PINS[name]
    path=Path(pin["path"])
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=pin["sha256"]: raise AssertionError("publisher archive changed")
    pack=Pack(name,path,digest)
    tick=pack.reachable(("minecraft:tick",))|pack.scheduled_from(("minecraft:load",))
    totals=Counter()
    shapes=Counter()
    opaque=Counter()
    candidates=[]
    for fid,lines in sorted(pack.functions.items()):
        kinds=[shape(line) for line in lines]
        counts=segment_counts(lines,shape)
        totals.update(functions=1,source_lines=len(lines),candidate_lines=counts["typed_lines"],
                      candidate_region_lines=counts["region_lines"],candidate_regions=counts["region_count"])
        shapes.update(x for x in kinds if x is not None)
        opaque.update(barrier(line) for line,kind in zip(lines,kinds) if kind is None)
        if fid in tick:
            totals.update(tick_scope_functions=1,tick_scope_lines=len(lines),
                          tick_scope_candidate_region_lines=counts["region_lines"])
        if counts["region_lines"]:
            candidates.append({"function":fid,"tick_scope":fid in tick,**counts})
    return {"name":name,"sha256":digest,"totals":dict(totals),
            "shapes":dict(shapes),"opaque_kinds":dict(opaque),
            "candidates":sorted(candidates,key=lambda x:(not x["tick_scope"],-x["region_lines"],x["function"])),
            "not_native_admission_or_hotness":True}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={name:audit(name) for name in PINS}
    (OUT/"publisher-candidates.json").write_text(json.dumps(report,indent=2)+"\n")
    print("IR041_SOURCE "+json.dumps({k:{"totals":v["totals"],"shapes":v["shapes"],
        "top_candidates":v["candidates"][:5]} for k,v in report.items()}),flush=True)
if __name__=="__main__":main()
