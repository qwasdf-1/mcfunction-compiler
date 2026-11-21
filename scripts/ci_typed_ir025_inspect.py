#!/usr/bin/env python3
"""IR025 actual Minecraft 26.3 mapped scheduling API inventory, source-free.

No classfile edits, no game execution; inspect exact mapped overloads,
visibility, and calls before changing the fork scheduler. Fail closed if
required mapped classes or methods disappear.
"""
from pathlib import Path
import subprocess
import re
import zipfile
import json
import hashlib

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/reports/COMPILER-IR-025-MAPPED"
JAR_DIR=Path.home()/".gradle/caches/fabric-loom/minecraftMaven"
REQUIRED=[
    "net.minecraft.commands.execution.tasks.BuildContexts",
    "net.minecraft.commands.execution.tasks.BuildContexts$Unbound",
    "net.minecraft.commands.execution.tasks.ExecuteCommand",
    "net.minecraft.commands.execution.tasks.ContinuationTask",
    "net.minecraft.commands.execution.ChainModifiers",
    "net.minecraft.commands.execution.ExecutionContext",
    "net.minecraft.commands.arguments.selector.EntitySelector",
    "net.minecraft.commands.CommandSourceStack",
    "net.minecraft.world.scores.ScoreHolder",
    "net.minecraft.world.scores.Scoreboard",
    "net.minecraft.world.scores.Objective",
    "net.minecraft.world.scores.ReadOnlyScoreInfo",
]
def main():
    matches=list(JAR_DIR.rglob("minecraft-merged-deobf-26.3.jar"))
    if len(matches)!=1:raise AssertionError(f"Expected ONE mapped jar, got {matches}")
    jar=matches[0]
    OUT.mkdir(parents=True,exist_ok=True)
    report={"milestone":"COMPILER-IR-025","mapped_minecraft_version":"26.3",
            "mapped_sha256":hashlib.sha256(jar.read_bytes()).hexdigest(),
            "inspected_classes":[],"runtime_code_changed":False}
    for clazz in REQUIRED:
        result=subprocess.run(["javap","-p","-c","-s","-classpath",str(jar),clazz],
                              text=True,capture_output=True,timeout=60,check=False)
        if result.returncode:raise AssertionError(f"Missing mapped {clazz}: {result.stderr}")
        name=clazz.rsplit(".",1)[-1].replace("$","_")
        (OUT/(name+".txt")).write_text(result.stdout,encoding="utf-8")
        headers=[line.strip() for line in result.stdout.splitlines()
                 if re.search(r"^  (public|protected|private|static) .+\(",line)]
        report["inspected_classes"].append({"class":clazz,"methods":headers})
        print("IR025_MAPPED "+json.dumps({"class":clazz,"methods":headers[:30]}),flush=True)
    build=(OUT/"BuildContexts.txt").read_text()
    branch=(OUT/"BuildContexts_Unbound.txt").read_text()
    required={"BuildContexts":"ContinuationTask.schedule",
              "BuildContexts_Unbound":"execute(",
              "ChainModifiers":"isForked(",
              "ExecuteCommand":"execute(",
              "ScoreHolder":"forNameOnly(",
              "EntitySelector":"findEntities("}
    for filename,needle in required.items():
        if needle not in (OUT/(filename+".txt")).read_text():
            raise AssertionError(f"Required mapped method {filename}.{needle} missing")
    (OUT/"inventory.json").write_text(json.dumps(report,indent=2)+"\n")
    print("IR025_MAPPED_DONE "+json.dumps({"status":"mapped_inspection_only",
          "classes":len(report["inspected_classes"]),"runtime_code_changed":False}))
if __name__=="__main__":main()
