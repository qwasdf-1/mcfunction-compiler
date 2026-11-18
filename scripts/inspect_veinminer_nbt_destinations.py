#!/usr/bin/env python3
"""Read-only source check: exact pinned Vein Miner archive NBT destinations.

SCHED-ATTR-028 source follow-up, NOT a new performance experiment.
Do not conflate statically possible callback targets with the callback
populations actually reached in the real mining event.
"""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/"references"/"real-world"/"candidates"/"VeinMiner-5.3.0+26.3.zip"
PIN="fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
OUT=ROOT/"build"/"benchmarks"/"SCHED-ATTR-028"/"veinminer-nbt-static-targets.json"
STORE=re.compile(r"\bexecute\b.*?\bstore\s+(result|success)\s+(storage|entity|block)\s+",re.I)
STORE_MACRO=re.compile(r"\bstore\s+(result|success)\s+(storage|entity|block)\s+",re.I)
DATA_CMD=re.compile(r"\bdata\s+(get|modify|merge|remove)\s+(storage|entity|block)\s+",re.I)
MACRO=re.compile(r"\$(?:\([^)]*\)|[a-zA-Z_][a-zA-Z0-9_]*)")
MAX_EXAMPLES=12


def analyze(path:Path)->dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing pinned publisher pack: {path}")
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=PIN:
        raise RuntimeError(f"Publisher ZIP SHA-256 mismatch {digest}, required {PIN}")
    direct=Counter()
    data_commands=Counter()
    examples={kind:[] for kind in ("storage","entity","block")}
    unknown=[]
    matches=0
    num_functions=0
    with zipfile.ZipFile(path) as z:
        for member in sorted(z.namelist()):
            if not member.lower().endswith(".mcfunction") or member.endswith("/"):
                continue
            num_functions+=1
            decoded=z.read(member).decode("utf-8-sig")
            for linenum,line in enumerate(decoded.splitlines(),1):
                stripped=line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                hit=STORE_MACRO.search(stripped)
                if hit:
                    kind=hit.group(2).lower()
                    direct[kind]+=1
                    matches+=1
                    if len(examples[kind])<MAX_EXAMPLES:
                        examples[kind].append({
                            "source":member,
                            "line":linenum,
                            "command":stripped[:500],
                            "macro_template":stripped.startswith("$") or bool(MACRO.search(stripped)),
                        })
                elif "store" in stripped and "execute" in stripped:
                    unknown.append({"source":member,"line":linenum,
                                    "command":stripped[:350]})
                m=DATA_CMD.search(stripped)
                if m:
                    data_commands[f"{m.group(1).lower()}:{m.group(2).lower()}"]+=1
    return {
        "source_archive_sha256":digest,
        "source_file_name":path.name,
        "inspection":"static published .mcfunction text, no runtime CPU and no assurance every command was executed",
        "functions_scanned":num_functions,
        "store_result_or_success_data_destinations":dict(sorted(direct.items())),
        "store_result_or_success_total_matches":matches,
        "other_data_command_targets":dict(sorted(data_commands.items())),
        "source_examples":examples,
        "unparsed_execute_store_candidates":unknown[:30],
        "unparsed_execute_store_candidate_count":len(unknown),
        "important_limitations":[
            "Static presence cannot establish which execute-store command produced the 256 sampled NBT callbacks.",
            "Macro lines can produce dynamic commands with different destination/source fields at runtime.",
            "If multiple destination kinds exist, the measured callsite must be classified by DataAccessor type to establish the observed distribution.",
            "Bellows' verified 26.3 path-specific accelerated get/set code only acts on EntityDataAccessorExtender; non-entity accessors use vanilla fallback.",
        ],
    }


def main()->int:
    data=analyze(PACK)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print("STATIC VEIN MINER NBT DESTINATIONS "+json.dumps({
        "sha256":data["source_archive_sha256"],
        "functions":data["functions_scanned"],
        "store":data["store_result_or_success_data_destinations"],
        "data":data["other_data_command_targets"],
        "unparsed":data["unparsed_execute_store_candidate_count"],
        "examples":data["source_examples"],
    }),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
