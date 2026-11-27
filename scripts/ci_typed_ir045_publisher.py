#!/usr/bin/env python3
"""IR045: pinned original source + frozen native visits + parsed D/G admission.
No timing; historical native weights are not counts from the compiled event."""
from __future__ import annotations
from collections import Counter
import json,re,os,hashlib
from pathlib import Path
import ci_typed_ir042_publisher as pub
from ci_typed_ir041_source import P
from ci_typed_ir013 import stop,stat

OUT=pub.base.ROOT/"build/reports/COMPILER-IR-045-PUBLISHER"
TARGET=r"function [a-z0-9_.-]+:[a-z0-9_./-]+"
CALL=re.compile(rf"(?:{TARGET}|execute {P}(?: {P}){{0,7}} run {TARGET})")
POS=r"(?:-?\d+|~(?:-?\d+)?)"
BLOCK=rf"(?:if|unless) block {POS} {POS} {POS} #?[a-z0-9_.-]+:[a-z0-9_./-]+"
TAG=r"tag @s (?:add|remove) [a-zA-Z0-9_.+-]+"
GUARD=re.compile(rf"execute (?:{BLOCK}|{P}) run {TAG}")
BLOCK_ADD=re.compile(rf"execute {BLOCK} run scoreboard players add #[a-zA-Z0-9_.+\-]+ [a-zA-Z0-9_.+\-]+ \d+")

STORE=re.compile(r"execute store (?:result|success) score (?:#[A-Za-z0-9_.+\-]+|@s) [A-Za-z0-9_.+\-]+ run (?:data get (?:entity @s Pos\[[012]\]|storage [a-z0-9_.-]+:[a-z0-9_./-]+ [A-Za-z0-9_.+\-]+) 1|data modify entity @s [A-Za-z0-9_.+\-]+ set from block ~ ~ ~ \{\}|scoreboard players add #[A-Za-z0-9_.+\-]+ [A-Za-z0-9_.+\-]+ [0-9]+)")

def kind(line):
    if STORE.fullmatch(line):return "T"
    if CALL.fullmatch(line):return "D"
    if GUARD.fullmatch(line) or BLOCK_ADD.fullmatch(line):return "G"
    if pub.opportunity(line)=="function_dispatch":return "other_dispatch"
    return pub.opportunity(line)

def join(census,pack):
    seen=set()
    rows=[]
    for row in census["rows"]:
        fid,index=row["function"],int(row["index"])
        key=(fid,index)
        if key in seen or fid not in census["target_functions"]:
            raise AssertionError("duplicate or unexpected native site "+str(key))
        seen.add(key)
        text=pack.functions[fid][index]
        if row["input"]!=text[:240]:raise AssertionError("pinned source mismatch "+str(key))
        rows.append({**row,"input":text,"index":index,"entries":int(row["entries"]),
                     "callbacks":int(row["callbacks"]),"shape":kind(text)})
    for fid in census["target_functions"]:
        if sum(f==fid for f,_ in seen)!=len(pack.functions[fid]):raise AssertionError("missing source indices "+fid)
    if len(rows)!=347 or sum(r["entries"] for r in rows)!=257697:
        raise AssertionError("archive is not the frozen IR042 native observation")
    return rows

def ledger_join(client,rows,targets):
    spans={}
    raw={}
    for fid in targets:
        reply=client.command("functioncompiler ir016 "+fid)
        if not reply.startswith("IR016 function="+fid+" ") or "..." in reply:
            raise AssertionError("missing/truncated parsed ledger "+reply)
        raw[fid]=reply
        nodes=re.findall(r"([JIDGTCFNSV])(\d+):(\d+)",reply.split("layout=",1)[1])
        consumed=0
        for k,start,length in nodes:
            start,length=int(start)-1,int(length)
            if start!=consumed or length<1:raise AssertionError("invalid span "+reply)
            for index in range(start,start+length):spans[(fid,index)]=k
            consumed+=length
        if consumed!=stat(reply,"source_lines") or consumed!=sum(r["function"]==fid for r in rows):
            raise AssertionError("source position coverage mismatch "+reply)
        for k,metric in (("D","typed_calls"),("G","typed_guards"),("T","typed_stores")):
            if sum(n==k for n,_,_ in nodes)!=stat(reply,metric):
                raise AssertionError("ledger count mismatch "+reply)
    result=[]
    for row in rows:
        k=spans.get((row["function"],row["index"]))
        if k in ("D","G","T") and k!=row["shape"]:
            raise AssertionError("unexpected typed admission "+str(row))
        result.append(row|{"parsed_node":k})
    return result,raw

def summarize(rows):
    shapes={}
    for k in ("D","G","T","other_dispatch"):
        sites=[r for r in rows if r["shape"]==k]
        admitted=[r for r in sites if r["parsed_node"]==k]
        shapes[k]={"source_sites":len(sites),"native_visits":sum(r["entries"] for r in sites),
                   "native_ordinary_callbacks":sum(r["callbacks"] for r in sites),
                   "parsed_admitted_sites":len(admitted),"historical_native_visits_at_admitted_sites":sum(r["entries"] for r in admitted),
                   "declined":[[r["function"],r["index"],r["entries"]] for r in sites if r["parsed_node"]!=k]}
    return shapes

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    archive=Path(os.environ["FC_IR045_CENSUS_JSON"])
    census=json.loads(archive.read_text())
    publisher=pub.base.original_publisher()
    pack=pub.Pack("blastback",pub.base.PACK,pub.base.PIN)
    rows=join(census,pack)
    targets=tuple(fid for fid in census["target_functions"] if fid.startswith("erb:"))
    if any(r["shape"] in ("D","G","T") and r["function"] not in targets for r in rows):
        raise AssertionError("candidate outside explicit namespace")
    pub.MODE="compiled";pub.SELECTED=targets[0];pub.DIAGNOSTIC=True;pub.CENSUS=False
    def options(mode):
        return pub.options(mode)|{"FC_TYPED_IR_FUNCTION_FILTER":",".join(targets),
             "FC_TYPED_IR_DISPATCH":"true","FC_TYPED_IR_GUARD_TERMINAL":"true","FC_TYPED_IR_NATIVE_STORE":"true",
             "FC_IR041_COMPILE_TIMING":"false"}
    pub.base.OUT=OUT
    pub.base.options=options
    r={"status":"started","original_publisher":publisher,"native_archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
       "compiled_function_allowlist":targets,"production_promotion":False}
    proc,client,log=pub.base.launch("admission")
    try:
        joined,raw=ledger_join(client,rows,targets)
        r.update(rows=joined,ledgers=raw,summary=summarize(joined))
        # Exact historical native weights only; the new event is a diagnostic
        # parity check and need not reproduce capture cardinality or hotness.
        if any(r["summary"][k]["parsed_admitted_sites"]!=r["summary"][k]["source_sites"] or r["summary"][k]["source_sites"]<=0 for k in ("D","G","T")):
            raise AssertionError("no actual parsed D/G admission "+repr(r["summary"]))
        before=client.command("functioncompiler ir008")
        r["event"]=pub.event(client,label="ir045-compiled")
        after=client.command("functioncompiler ir008")
        r["runtime_deltas"]={k:stat(after,k)-stat(before,k) for k in
            ("ir043_entered","ir043_calls","ir043_skipped","ir043_fallbacks",
             "ir044_entered","ir044_pass","ir044_skip","ir044_fallbacks","ir044_errors",
             "ir045_entered","ir045_queued","ir045_empty","ir045_fallbacks","ir045_errors")}
        if r["event"]["state"]!=census["event"]["state"]:
            raise AssertionError("compiled original restoration state differs")
        if min(r["runtime_deltas"][k] for k in ("ir043_entered","ir044_entered","ir045_entered"))<=0:
            raise AssertionError("new actual paths not exercised")
        r.update(status="accepted",complete_restoration_parity=True,
                 general_datapack_speedup=False)
        print("IR045_PUBLISHER_SUMMARY "+json.dumps({"summary":r["summary"],
            "runtime_deltas":r["runtime_deltas"],"status":r["status"]}),flush=True)
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        stop(proc,client,log)
        (OUT/"results.json").write_text(json.dumps(r,indent=2)+"\n")
if __name__=="__main__":main()
