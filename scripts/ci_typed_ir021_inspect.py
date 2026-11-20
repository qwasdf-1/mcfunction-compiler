#!/usr/bin/env python3
"""IR-021 temporary method inventory of SHA-verified 26.3 Loom-mapped game JAR.

No original Minecraft classfiles or source are committed to the repo.
Inspect exact method calls and labels to design read-only injection bounds.
"""
from pathlib import Path
import subprocess
import zipfile
import os
import re
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/reports/COMPILER-IR-021-INSPECTION"
OUT.mkdir(parents=True,exist_ok=True)
classes=[
"net.minecraft.commands.execution.tasks.BuildContexts",
"net.minecraft.commands.execution.tasks.ExecuteCommand",
"net.minecraft.server.commands.ExecuteCommand",
"net.minecraft.commands.arguments.selector.EntitySelector",
"net.minecraft.commands.execution.ContextChain",
"net.minecraft.commands.execution.ExecutionContext",
]
needle="net/minecraft/commands/execution/tasks/BuildContexts.class"
candidates=[]
for root in [ROOT/".gradle",Path.home()/".gradle/caches"]:
 if root.exists():
  for p in root.rglob("*.jar"):
   if any(w in p.name.lower() for w in ("minecraft","merged","deobf","26.3")):
    candidates.append(p)
print("IR021_JAR_CANDIDATES",len(candidates))
valid=[]
for file in candidates:
 try:
  with zipfile.ZipFile(file) as z:
   if needle in z.namelist():
    valid.append(file)
 except (zipfile.BadZipFile,OSError):
  continue
if not valid:
 raise RuntimeError("No Loom mapped official 26.3 JAR containing exact BuildContexts class")
valid.sort(key=lambda p:("deobf" not in p.name.lower(),"26.3" not in p.name,str(p)))
jar=valid[0]
print("IR021_MAPPED_JAR",jar)
for classname in classes:
 name=classname.rsplit(".",1)[-1]
 proc=subprocess.run(["javap","-p","-c","-s","-l","-classpath",str(jar),classname],
       text=True,capture_output=True,check=False)
 if proc.returncode:
  raise RuntimeError(f"javap failed {classname}: {proc.stderr}")
 (OUT/f"{name}.txt").write_text(proc.stdout)
 lines=proc.stdout.splitlines()
 print("IR021_CLASS",classname,"lines",len(lines))
 if name=="BuildContexts":
  print("IR021_BUILDCONTEXTS_JAVAP_BEGIN")
  print("\n".join(lines[:410]))
  print("IR021_BUILDCONTEXTS_JAVAP_END")
 else:
  focus=[(i,line.strip()) for i,line in enumerate(lines)
         if re.search(r"findEntities|findPlayers|withEntity|queueNext|queueNext|executeFork|execute|predicate|incrementCost|calculate|selector|build|ContextChain|EntitySelector|create|fork|stream",line,re.I)]
  print("IR021_RELATED",classname,focus[:55])
