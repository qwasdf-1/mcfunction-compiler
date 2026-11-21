#!/usr/bin/env python3
"""Inspect exact SHA-locked Mojang 26.3 mapped type/selector query bytecode.

Do not publish or commit proprietary classfiles; bytecode report is CI artifact.
"""
from pathlib import Path
import subprocess
import zipfile
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/reports/COMPILER-IR-022-INSPECTION"
OUT.mkdir(parents=True,exist_ok=True)
jarlist=list((Path.home()/".gradle/caches/fabric-loom/minecraftMaven").rglob("minecraft-merged-deobf-26.3.jar"))
if len(jarlist)!=1:raise AssertionError(f"Expected one mapped Minecraft 26.3 JAR: {jarlist}")
jar=jarlist[0]
classes=[
"net.minecraft.world.level.entity.EntityTypeTest",
"net.minecraft.server.level.ServerLevel",
"net.minecraft.commands.arguments.selector.EntitySelector",
"net.minecraft.commands.arguments.selector.EntitySelectorParser",
]
results={}
for cls in classes:
 process=subprocess.run(["javap","-p","-c","-s","-classpath",str(jar),cls],text=True,capture_output=True)
 if process.returncode!=0:raise RuntimeError(f"Missing official mapped {cls}: {process.stderr}")
 name=cls.rsplit(".",1)[-1]
 if name=="EntitySelectorParser":name="EntitySelectorParser"
 (OUT/(name+".txt")).write_text(process.stdout,encoding="utf-8")
 lines=process.stdout.splitlines()
 related=[line for line in lines if re.search("getEntities|EntityTypeTest|tryCast|findEntities|addEntities|getPredicate|sortAndLimit|isWorldLimited",line)]
 results[cls]={"total_lines":len(lines),"related":related[:100]}
 print("IR022_MAPPED_SIGNATURES",cls,json.dumps(related[:70]))
(OUT/"inspection.json").write_text(json.dumps({"mapped_minecraft_26_3_sha256":hashlib.sha256(jar.read_bytes()).hexdigest(),"methods":results},indent=2))
