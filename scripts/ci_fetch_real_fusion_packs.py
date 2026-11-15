#!/usr/bin/env python3
"""Acquire candidate archives by publisher version metadata and SHA-256.

Blastback is locked to the existing pinned version and hash. Simple Timer is a
*new* diagnostic source selection, since the 2026-11-03 static screen's local
ZIP fingerprint was not committed. The selected version and digest are saved;
do not claim this reproduces that historical screen without matching hashes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import datetime, timezone

from ci_real_fusion_coverage import ROOT, SOURCES, BLASTBACK_SHA256


def get_json(url: str) -> object:
    request=urllib.request.Request(
        url,headers={"User-Agent":"MCFC-SCHED-COMP-012-research/1.0"})
    with urllib.request.urlopen(request,timeout=40) as response:
        return json.load(response)


def download(file: dict, destination: Path, expected: str | None) -> dict:
    expected_sha=expected or file.get("hashes",{}).get("sha256")
    if not expected_sha:
        raise ValueError("Publisher did not supply SHA-256")
    request=urllib.request.Request(
        file["url"],headers={"User-Agent":"MCFC-SCHED-COMP-012-research/1.0"})
    with urllib.request.urlopen(request,timeout=65) as response:
        payload=response.read()
    observed=hashlib.sha256(payload).hexdigest()
    if observed!=expected_sha:
        raise ValueError(f"SHA-256 mismatch for {destination.name}: {observed} != {expected_sha}")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(payload)
    return {"filename":file["filename"],"expected_sha256":expected_sha,
            "actual_sha256":observed,"bytes":len(payload)}


def choose_timer_version(versions: list[dict]) -> dict:
    # The original 2026-11-03 scan cannot have used a newly published version.
    # Select a deterministic public version no later than that scan.
    cutoff=datetime(2026,11,3,tzinfo=timezone.utc)
    compatible=[]
    historical=[]
    for version in versions:
        try:
            published=datetime.fromisoformat(version["date_published"].replace("Z","+00:00"))
        except (ValueError,KeyError):
            continue
        if published>cutoff:
            continue
        archives=[f for f in version.get("files",[]) if f["filename"].lower().endswith(".zip")
                  and f.get("hashes",{}).get("sha256")]
        if archives:
            historical.append((published,version,archives))
            if {"26.2","26.3"} & set(version.get("game_versions",[])):
                compatible.append((published,version,archives))
    if not historical:
        raise RuntimeError("No historically published Simple Timer ZIP before 2026-11-03")
    # The platform's project-level game-version compatibility can differ from
    # individual version.game_versions; do not conflate these. A historical ZIP
    # with another reported game-version string is diagnostic-only and must
    # separately pass actual 26.3 loader validation and 36-command screen.
    pool=compatible or historical
    pool.sort(key=lambda x:(x[0],x[1]["id"]))
    _,selected,archives=pool[-1]
    chosen=next((f for f in archives if f.get("primary")),archives[0])
    return {"version":selected,"file":chosen}


def main() -> None:
    output=ROOT/"build/benchmarks/SCHED-COMP-012"
    output.mkdir(parents=True,exist_ok=True)
    record={"experiment":"SCHED-COMP-012","source":"publisher metadata",
            "note":"Timer selected before November 3, version metadata may not declare 26.2; loader and candidate counts must independently verify.",
            "packs":{}}
    try:
        blast=get_json("https://api.modrinth.com/v2/version/dMtA8r0n")
        if not isinstance(blast,dict):
            raise TypeError("Blastback version metadata not an object")
        bf=[f for f in blast.get("files",[]) if f["filename"].lower().endswith(".zip")]
        if len(bf)!=1:
            raise ValueError(f"Blastback exact version expected 1 ZIP, found {len(bf)}")
        rec=download(bf[0],SOURCES["blastback"],BLASTBACK_SHA256)
        record["packs"]["blastback"]={**rec,"project":"blastback","version_id":"dMtA8r0n"}

        try:
            versions=get_json("https://api.modrinth.com/v2/project/simple_timer/version")
            if not isinstance(versions,list):raise TypeError("Timer versions response not an array")
            chosen=choose_timer_version(versions)
            version=chosen["version"]
            rec=download(chosen["file"],SOURCES["simple_timer"],None)
            record["packs"]["simple_timer"]={**rec,"project":"simple_timer",
                                              "version_id":version["id"],
                                              "published":version["date_published"],
                                              "game_versions":version["game_versions"]}
            record["status"]="complete"
        except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
            # Pack discovery must not prevent the independently pinned
            # Blastback activation diagnostic from running.
            record["status"]="partial"
            record["packs"]["simple_timer"]={"status":"unavailable",
                                              "reason":repr(error)}
        print("CANDIDATE_PACKS "+json.dumps(record["packs"]),flush=True)
    except BaseException as e:
        record["status"]="failed"
        record["error"]=repr(e)
        raise
    finally:
        (output/"source-manifest.json").write_text(json.dumps(record,indent=2)+"\n")


if __name__=="__main__":
    main()
