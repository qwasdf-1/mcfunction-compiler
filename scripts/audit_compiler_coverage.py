#!/usr/bin/env python3
"""Compiler coverage audit of a SHA-pinned datapack, without timing claims.

Deliberately reuses the repository's previously tested H2-first source parser
and fork/adjacency rule. A lexical candidate is NOT proof that Brigadier
accepted a parser, the resulting command was compiled, or that it ever ran.

Usage:
  python3 scripts/audit_compiler_coverage.py --pack veinminer
  python3 scripts/audit_compiler_coverage.py --pack veinminer --output DIR
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from run_specialization_inventory import (
    PACKS, Pack, MACRO_WITH_CALL, FUNCTION_CALL, FAKE_HOLDER_ADD,
    is_pure_leaf, leaf_family, parse_execute, sha256_file,
    split_tokens, summarize_pack,
)

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"build"/"benchmarks"/"COMPILER-COVERAGE-AUDIT-001"

# Only lexically well-formed command roots from the parser inventory.
# This is NOT a claim that every shape reaches ScoreAddPrototype's compiler
# implementation. Runtime counters/parity must establish actual activation.
PARSER_ROOTS={
    "scoreboard":"scoreboard",
    "data":"data",
    "setblock":"setblock",
    "fill":"fill",
    "execute":"execute",
    "function":"function",
    "return":"return",
    "bossbar":"bossbar",
    "effect":"effect",
    "title":"title",
    "playsound":"playsound",
    "particle":"particle",
    "summon":"summon",
    "damage":"damage",
    "give":"give",
    "clear":"clear",
    "rotate":"rotate",
    "item":"item",
    "tag":"tag",
    "kill":"kill",
    "tp":"teleport",
    "teleport":"teleport",
}

def canonical_root(command:str)->str:
    tokens=split_tokens(command)
    return tokens[0] if tokens else "(blank)"

def locate_macro_provider(command:str)->str:
    match=re.search(
        r"\bfunction\s+[#a-z0-9_.-]+:[a-z0-9_./-]+\s+with\s+"
        r"(entity|storage|block|(?:from|source|unknown))\b",command
    )
    return match.group(1) if match else "unknown"

def line_classification(pack:Pack,line:str)->dict:
    is_exec,forked,inner=parse_execute(line)
    command=inner if is_exec and inner is not None else line
    tokens=split_tokens(command)
    family=leaf_family(command)
    root=canonical_root(command)
    macro_with=bool(MACRO_WITH_CALL.search(line))
    inline=False
    if root=="function" and len(tokens)>1 and not macro_with:
        target=pack.functions.get(tokens[1])
        inline=target is not None and is_pure_leaf(target)
    fakeholder=bool(FAKE_HOLDER_ADD.match(command))
    if is_exec and inner is None:
        category="execute_without_run"
    elif is_exec and forked:
        category="lexically_forked_execute"
    elif family is not None or inline:
        category="lexical_fusable_or_inline_candidate"
    elif macro_with:
        category="selective_macro_candidate"
    elif root in PARSER_ROOTS:
        category="known_parser_root_not_proven"
    else:
        category="vanilla_or_other_root"

    return {
        "root":root,"category":category,
        "execute_wrapped":is_exec,"forked_lexically":forked,
        "fusable_family":family,"pure_leaf_inline_candidate":inline,
        "fakeholder_score_add":fakeholder,
        "macro_with_provider":locate_macro_provider(line) if macro_with else None,
        "candidate_only":True,
    }

def audit(pack:Pack)->dict:
    direct=pack.reachable(("minecraft:tick","minecraft:load"))
    tick=pack.reachable(("minecraft:tick",)) | pack.scheduled_from(("minecraft:load",))
    scanned=sorted(direct|tick)
    unreach=set(pack.functions)-set(scanned)
    counts=Counter()
    roots=Counter()
    providers=Counter()
    root_categories={}
    by_fn=[]
    for fn in scanned:
        lines=pack.functions[fn]
        local=Counter()
        examples=[]
        for command in lines:
            row=line_classification(pack,command)
            counts[row["category"]]+=1
            local[row["category"]]+=1
            roots[row["root"]]+=1
            if row["macro_with_provider"]:
                providers[row["macro_with_provider"]]+=1
            pair=(row["root"],row["category"])
            root_categories[pair]=root_categories.get(pair,0)+1
            if (row["category"] in (
                    "lexically_forked_execute","known_parser_root_not_proven",
                    "execute_without_run","vanilla_or_other_root")
                    and len(examples)<5):
                examples.append({
                    "category":row["category"],"root":row["root"],
                    "command":command[:230],
                })
        score=(
            4*local["selective_macro_candidate"]
            + 2*local["lexically_forked_execute"]
            + local["known_parser_root_not_proven"]
        )
        by_fn.append({
            "id":fn,"in_tick_or_scheduled_scope":fn in tick,
            "lines":len(lines),"candidate_review_score_not_cpu_cost":score,
            "categories":dict(sorted(local.items())),
            "examples":examples,
        })
    existing=summarize_pack(pack)
    return {
        "audit_id":"COMPILER-COVERAGE-AUDIT-001",
        "name":pack.name,"sha256":pack.sha256,
        "functions_total":len(pack.functions),
        "functions_reachable_or_scheduled":len(scanned),
        "functions_unreachable_from_known_tags":len(unreach),
        "tick_or_scheduled_functions":len(tick),
        "command_lines_scanned":sum(counts.values()),
        "classification_counts":dict(sorted(counts.items())),
        "command_root_counts":dict(sorted(roots.items())),
        "macro_with_provider_counts":dict(sorted(providers.items())),
        "root_by_category":[
            {"root":a,"category":b,"count":n}
            for (a,b),n in sorted(root_categories.items(),
                                   key=lambda item:(-item[1],item[0]))
        ],
        "h2_existing_census_totals":existing["totals"],
        "functions_review_ranked":sorted(
            by_fn,key=lambda r:(
                not r["in_tick_or_scheduled_scope"],
                -r["candidate_review_score_not_cpu_cost"],
                -r["lines"],r["id"]
            )),
        "interpretation":{
            "default_on":"selective_macros=true; generic wrapper enabled=false; score_add=false; fused_regions=false; tiered_bytecode=false",
            "named_compiler_census":"existing H2-first, reused rather than claiming a new discovery",
            "no_runtime_claim":"Static command counts do not identify executed command mix, optimizer activation, or avoidable CPU.",
            "lexical_fork_limit":"Parsing execute subcommands is approximate; called functions may inherit forked context.",
            "no_false_specialization_claim":"known_parser_root and fusable_family are candidates, not proof of shape-specific compilation or runtime fast-path.",
            "macro_with_limit":"Macro with-entity/storage source may fall back on nested paths/missing keys or other conditions.",
            "recommended_follow_up":"Contrast runtime activation counters against the existing H2 static candidates before implementing any new parser.",
        },
    }

def markdown(result:dict)->str:
    counts=result["classification_counts"]
    lines=[
        "# Compiler coverage audit: "+result["name"],"",
        f"**Pinned publisher SHA-256:** \`{result['sha256']}\`.",
        f"**Scope:** {result['functions_reachable_or_scheduled']} reachable/scheduled"
        f" functions ({result['tick_or_scheduled_functions']} tick/scheduled)"
        f" of {result['functions_total']} total; "
        f"{result['command_lines_scanned']} syntactic command lines scanned.","",
        "**Warning:** This is a source-only candidate inventory, not an estimate"
        " of dynamic command counts, actual compiled coverage, callback CPU,"
        " or potential speedup.","",
        "| Source classification | Lexical command lines |",
        "| --- | ---: |",
    ]
    for k,n in sorted(counts.items(),key=lambda x:(-x[1],x[0])):
        lines.append(f"| \`{k}\` | {n} |")
    lines.extend(["", "### H2 baseline already available", "",
        "The existing H2-first inventory is reused; it already counts non-forked"
        " adjacent fusable candidates, forked barriers, pure-leaf calls and"
        " macro providers. An eligible command may still fail at Brigadier"
        " shape parsing or not execute during the actual mining event.","",
        "### Review candidates (not ranked by CPU)", "",
        "| Function | Tick/scheduled | Lines | Review score¹ | Macro | Forked | Known parser root |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for fn in result["functions_review_ranked"][:18]:
        c=fn["categories"]
        lines.append(
            f"| \`{fn['id']}\` | {'yes' if fn['in_tick_or_scheduled_scope'] else 'load/reachable'}"
            f" | {fn['lines']} | {fn['candidate_review_score_not_cpu_cost']}"
            f" | {c.get('selective_macro_candidate',0)}"
            f" | {c.get('lexically_forked_execute',0)}"
            f" | {c.get('known_parser_root_not_proven',0)} |"
        )
    lines.extend(["", "¹ Review score is an arbitrary *triage* weight; it is"
        " explicitly **not** frequency, sample CPU, or performance potential.","",
        "### Practical decision", "",
        "Before changing compiler lowering, select a repeatable **compiler-owned**"
        " candidate: an actual executed command/macro with a measured meaningful"
        " parser/queue overhead fraction and a complete semantic fast/fallback"
        " rule. The prior successful selectively specialized macro argument path"
        " is already on by default. The unpromoted fused-region path and generic"
        " scoreboard ScoreAdd are not promoted by static eligibility alone.",
        "Avoid implementing general NBT get/set optimizations that Bellows"
        " already owns or might handle with its own runtime patches.",""])
    return "\n".join(lines)

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack",choices=tuple(PACKS),default="veinminer")
    parser.add_argument("--output",type=Path,default=OUTPUT)
    args=parser.parse_args()
    spec=PACKS[args.pack]
    path=spec["path"]
    if not path.is_file():
        parser.error(f"Missing SHA-pinned archive: {path}")
    digest=sha256_file(path)
    if digest!=spec["sha256"]:
        parser.error(f"Publisher archive SHA mismatch {digest} != {spec['sha256']}")
    result=audit(Pack(args.pack,path,digest))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"audit.json").write_text(json.dumps(result,indent=2)+"\n")
    (args.output/"audit.md").write_text(markdown(result),encoding="utf-8")
    print(json.dumps({
        "audit":result["audit_id"],"pack":result["name"],
        "sha256":result["sha256"],
        "functions":result["functions_reachable_or_scheduled"],
        "lines":result["command_lines_scanned"],
        "classes":result["classification_counts"],
        "macro_providers":result["macro_with_provider_counts"],
        "top_fns":[{
            "id":row["id"],
            "rank":row["candidate_review_score_not_cpu_cost"],
            "categories":row["categories"],
        } for row in result["functions_review_ranked"][:12]],
    }))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
