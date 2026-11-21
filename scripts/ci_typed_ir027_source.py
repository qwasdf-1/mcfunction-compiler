#!/usr/bin/env python3
"""IR027 read-only original publisher restore/completion source audit.

Requires SHA-verified original Blastback archive. Produces bounded relevant
function source *excerpts* and inventories, never rewrites datapack/pack.
No CPU, compiler or behavioral conclusion.
"""
from __future__ import annotations
import collections, hashlib, json, re, zipfile
from pathlib import Path
from ci_typed_ir015_coverage import PINS
from ci_typed_ir022_cpu import EXACT_ORIGINAL_LINE
OUT=Path("build/reports/COMPILER-IR-027-SOURCE")
PIN=PINS["blastback"]["sha256"]; PACK=Path(PINS["blastback"]["path"])
EXACT=(
"erb:restore/job_tick","erb:status/collect","erb:runtime_tick",
"erb:restore/tick","erb:restore/group_loop","erb:restore/group_once",
"erb:restore/revisit","erb:restore/consider","erb:restore/one",
"erb:restore/audit_loop_macro","erb:restore/finish_job_macro",
"erb:job/quiet_tick","erb:job/tick_once","erb:status/count_group",
"erb:restore/job_complete","erb:restore/job_finish",
"erb:restore/finish","erb:runtime/finish",
"erb:job/create","erb:restore/step","erb:restore/run",
"erb:restore/start","erb:restore/queue",
)
SEARCH=(r"#needs_restore",r"#active erb\.job",r"#captures_active",
        r"#unresolved_active",r"erb\.verified",r"erb\.restore_job",
        r"erb\.job_marker",r"\bkill\b",r"\bremove\b")
def main():
  OUT.mkdir(parents=True,exist_ok=True)
  checksum=hashlib.sha256(PACK.read_bytes()).hexdigest()
  if checksum!=PIN:raise AssertionError(f"Original publisher SHA mismatch {checksum}")
  with zipfile.ZipFile(PACK) as z:
    files={p[len("data/"):-len(".mcfunction")]:
           z.read(p).decode("utf-8",errors="replace")
           for p in z.namelist()
           if p.startswith("data/") and p.endswith(".mcfunction")}
  functions={i.split("/",1)[0].replace("/",":",1)+":"+i.split("/",1)[1]
            for i in []}
  # Minecraft 26.3 datapack paths: data/<namespace>/function/<relative>.mcfunction
  original={}
  for key,raw in files.items():
    namespace,rest=key.split("/",1)
    for directory in ("function/","functions/"):
      if rest.startswith(directory):
        original[namespace+":"+rest[len(directory):]]=raw
        break
  source=original.get("erb:restore/job_tick","")
  commands=[x.strip() for x in source.splitlines() if x.strip() and not x.lstrip().startswith("#")]
  if len(commands)<5 or commands[4]!=EXACT_ORIGINAL_LINE:
    raise AssertionError("Original restore job target changed")
  keywords={pat:[] for pat in SEARCH}
  for name,body in original.items():
    if not name.startswith("erb:"):continue
    for pat in SEARCH:
      if re.search(pat,body) and (name.startswith("erb:restore/")
          or name.startswith("erb:status/")
          or name.startswith("erb:job/")
          or name.startswith("erb:runtime/")):
        keywords[pat].append(name)
  selected=sorted(set(EXACT)&original.keys())
  selected+=sorted(k for k in original
        if (k.startswith("erb:restore/") or k.startswith("erb:status/"))
        and k not in selected
        and any(re.search(p,original[k]) for p in SEARCH))[:65]
  excerpts={}
  for name in selected:
    lines=[x.rstrip() for x in original[name].splitlines()
           if x.strip() and not x.strip().startswith("#")]
    excerpts[name]={"total_lines":len(lines),"first_lines":lines[:45],
                    "truncated":len(lines)>45}
  result={"milestone":"COMPILER-IR-027","status":"pinned_original_source_inventory",
          "sha256":checksum,"functions":len(original),
          "exact_original_restore_source":commands[4],
          "functions_examined":len(excerpts),
          "selected_original_source":excerpts,
          "symbol_references":{k:{"count":len(v),"first_functions":v[:45]}
                               for k,v in keywords.items()},
          "original_pack_edited":False,
          "gameplay_oracle_claim":False}
  (OUT/"inventory.json").write_text(json.dumps(result,indent=2)+"\n")
  for name in EXACT:
    if name in excerpts: print("IR027_SOURCE "+json.dumps({"function":name,
                       **excerpts[name]},sort_keys=True),flush=True)
  print("IR027_SOURCE_SUMMARY "+json.dumps({"functions":len(original),
     "selected":len(excerpts),
     "symbol_refs":{k:len(v) for k,v in keywords.items()},
     "status":result["status"]},sort_keys=True),flush=True)
if __name__=="__main__":main()
