#!/usr/bin/env python3
"""Reconcile archived IR042/045 source positions and model IR046 candidate.
Usage: python scripts/audit_ir046_candidates.py IR042.zip IR045.zip [IR041-source.zip]
Operation counts and abstract parity only; no Minecraft execution or timing.
"""
import collections
import hashlib
import itertools
import json
import re
import sys
import zipfile

def load(path, suffix):
    with zipfile.ZipFile(path) as archive:
        raw=archive.read(next(n for n in archive.namelist() if n.endswith(suffix)))
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def reconcile(native,publisher,digest):
    original={(r["function"],int(r["index"])):r for r in native["rows"]}
    rows=publisher["rows"]
    assert len(original)==len(rows)==347
    assert len({(r["function"],r["index"]) for r in rows})==347
    assert digest==publisher["native_archive_sha256"]
    for r in rows:
        o=original[r["function"],r["index"]]
        assert (int(o["entries"]),int(o["callbacks"]),o["input"])==(
            r["entries"],r["callbacks"],r["input"][:240])
    assert sum(r["entries"] for r in rows)==257697
    return rows

def wrap_commands(rows):
    pattern=(r"execute if score @s erb.radius matches (\d+) if score @s "
             r"erb.cursor matches (\d+\.\.|\.\.-1) run scoreboard players set @s erb.cursor (\d+)")
    sites=sorted((r for r in rows if r["function"]=="erb_generated:restore/wrap"),
                 key=lambda r:r["index"])
    assert len(sites)==10
    commands=[]
    for site in sites:
        m=re.fullmatch(pattern,site["input"])
        assert m,site
        radius,bound,value=m.groups()
        commands.append((int(radius),None if bound=="..-1" else int(bound[:-2]),int(value)))
    return sites,commands

def simulate(commands,radius,cursor,quota,listener,reuse):
    """Abstract two-guard/set model. None denotes absence. No native proof."""
    reads=collections.Counter()
    cache={}
    writes=[]
    debits=0
    events=[]
    def read(key):
        if reuse and key in cache:return cache[key]
        reads[key]+=1
        value=radius if key=="radius" else cursor
        if reuse:cache[key]=value
        return value
    for index,(r,b,value) in enumerate(commands):
        if quota<=0:break
        quota-=2
        debits+=2
        if read("radius")!=r:continue
        c=read("cursor")
        if c is None or not (c<=-1 if b is None else c>=b):continue
        if quota<=0:break
        quota-=1
        debits+=1
        cache.clear() # before terminal effects, even if write is a no-op
        cursor=value
        writes.append((index,value))
        events.append(("write",index,value))
        if listener=="change_radius":radius=12 if radius!=12 else 3
        elif listener=="remove_radius":radius=None
        elif listener=="change_cursor":cursor=-1
        elif listener=="remove_cursor":cursor=None
        elif listener=="both":radius,cursor=6,-1
    return (radius,cursor,quota,debits,writes,events),reads

def compare(commands):
    radii=[None,-2**31,-1,0,3,6,8,10,12,13,2**31-1]
    cursors=[None,-2**31,-2,-1,0,1,2**31-1]
    cursors += [n+d for _,n,_ in commands if n is not None for d in (-1,0,1)]
    cursors=sorted(set(cursors),key=lambda c:(c is not None,c))
    listeners=["none","change_radius","remove_radius","change_cursor","remove_cursor","both"]
    count=0
    for radius,cursor,quota,listener in itertools.product(radii,cursors,range(26),listeners):
        a,ar=simulate(commands,radius,cursor,quota,listener,False)
        b,br=simulate(commands,radius,cursor,quota,listener,True)
        assert a==b,(radius,cursor,quota,listener,a,b)
        assert sum(br.values())<=sum(ar.values())
        count+=1
    return count

def classify(rows):
    patterns={
        "as_at":r"execute as \S+ at @s run function \S+",
        "guarded_as_at":r"execute if score .* as \S+ at @s run function \S+",
        "as_score":r"execute as \S+ if score .* run function \S+",
        "plain_self_tag":r"tag @s (?:add|remove) \S+",
    }
    groups={k:[r for r in rows if re.fullmatch(p,r["input"])] for k,p in patterns.items()}
    groups["singleton"]=[r for r in rows if r["parsed_node"]=="S"]
    return {k:{"sites":len(v),"visits":sum(r["entries"] for r in v),
               "ordinary_callbacks":sum(r["callbacks"] for r in v),
               "reached_sites":sum(r["entries"]>0 for r in v),
               "positions":[[r["function"],r["index"],r["entries"],r["input"]] for r in v]}
            for k,v in groups.items()}

def main():
    native,digest=load(sys.argv[1],"/census.json")
    pub,_=load(sys.argv[2],"/results.json")
    rows=reconcile(native,pub,digest)
    sites,commands=wrap_commands(rows)
    visits=sum(r["entries"] for r in sites)
    writes=sum(r["callbacks"] for r in sites)
    calls=native["summary"]["all_allowlisted_calls"]["erb_generated:restore/wrap"]
    assert (visits,writes,calls)==(172450,2,17245)
    assert [r["callbacks"] for r in sites]==[0]*8+[2,0]
    cases=compare(commands)
    samples=[]
    for radius,cursor in [(12,1),(3,122),(12,7153),(3,-1),(None,None),(12,None)]:
        a,ar=simulate(commands,radius,cursor,99,"none",False)
        b,br=simulate(commands,radius,cursor,99,"none",True)
        assert a==b
        samples.append({"radius":radius,"cursor":cursor,"ordinary":dict(ar),
                        "reuse":dict(br),"state":a})
    result={"native_census_sha256":digest,"rows":len(rows),"entries":sum(r["entries"] for r in rows),
            "wrap":{"commands":commands,"visits":visits,"writes":writes,"calls":calls,
                    "model_cases":cases,"conditional_radius_lookup_saving":visits-calls-writes,
                    "samples":samples},"families":classify(rows)}
    if len(sys.argv)>3:
        screen,_=load(sys.argv[3],"publisher-candidates.json")
        result["static_only"]={k:v["totals"]|{"isolated_candidates":
            v["totals"]["candidate_lines"]-v["totals"]["candidate_region_lines"]}
            for k,v in screen.items()}
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
