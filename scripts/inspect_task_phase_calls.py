#!/usr/bin/env python3
"""SCHED-ATTR-026: inspect exact Java 25 / Minecraft 26.3 Loom class bytecode.

No profiler or gameplay changes. Captures method descriptions and actual
INVOKE callsite descriptors so later phase probes target what the compiler
really emitted, not guessed 26.3 APIs.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build"/"benchmarks"/"SCHED-ATTR-026"
OUT.mkdir(parents=True,exist_ok=True)
CLASSES=[
    "net.minecraft.commands.execution.tasks.BuildContexts",
    "net.minecraft.commands.execution.tasks.ExecuteCommand",
    "com.mojang.brigadier.context.ContextChain",
    "com.mojang.brigadier.context.CommandContext",
    "net.minecraft.commands.execution.tasks.ContinuationTask",
    "net.minecraft.commands.execution.ExecutionContext",
]
# Retain exact checksummed 26.3 bytecode; recent Loom runs have also produced
# a second verified artifact SHA because of mapping/toolchain changes.
KNOWN={
    "10d6fed9e924f22f1a034fe55a619d92447b64b4f44043a4ba9a072822dc966e",
    "728e09ff352d7a4f715e85bc7947bbdd13ef4d436f92aa8bc766f2044b59dad7",
    # Fresh Fabric Loom cache rebuilt on the 2026-11-18 GitHub CI image.
    # New artifact fingerprint is retained in source-versions.lock.
    "bf8e2d4fbaeac8e71179cac31f826262292fe9d6bc170143f893c38354d83597",
}

def find_classfile()->tuple[Path,str]:
    roots=[ROOT/".gradle",Path.home()/".gradle"/"caches"]
    candidates=[]
    for root in roots:
        if root.exists():
            candidates.extend(root.rglob("minecraft-merged-deobf-26.3.jar"))
    if not candidates:
        raise RuntimeError("No Minecraft 26.3 merged-deobf classfile after Loom build")
    for jar in sorted(candidates):
        h=hashlib.sha256(jar.read_bytes()).hexdigest()
        print(f"CANDIDATE {jar} sha256={h}",flush=True)
        if h in KNOWN:
            return jar,h
    raise RuntimeError("No classfile matched pinned 26.3 artifact SHA-256")

def main()->int:
    jar,sha=find_classfile()
    (OUT/"classfile-sha256.txt").write_text(
        f"{sha}  {jar}\n",encoding="utf-8")
    # Brigadier's ContextChain and CommandContext live in a separate mapped
    # dependency jar, not necessarily in the merged Minecraft classfile.
    brigadier_root=Path.home()/".gradle"/"caches"/"modules-2"/"files-2.1"/"com.mojang"/"brigadier"
    brigadier=sorted(brigadier_root.rglob("brigadier-*.jar")) if brigadier_root.exists() else []
    if not brigadier:
        raise RuntimeError("Pinned Loom build did not resolve a Brigadier dependency jar")
    classpath=os.pathsep.join([str(jar),str(brigadier[-1])])
    (OUT/"brigadier-path.txt").write_text(str(brigadier[-1])+"\\n")
    for cls in CLASSES:
        command=["javap","-p","-s","-c","-classpath",classpath,cls]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30,check=True)
        text=result.stdout
        # Verify key typed descriptors against historical independently
        # inspected 26.3 mapping, rather than only matching the filename.
        if cls.endswith(".BuildContexts") and not all(t in text for t in (
            "net.minecraft.commands.ExecutionCommandSource",
            "net.minecraft.commands.execution.ChainModifiers",
            "net.minecraft.commands.execution.Frame",
        )):
            raise RuntimeError("BuildContexts typed execute signature no longer matches 26.3")
        if cls.endswith(".ExecuteCommand") and "net.minecraft.commands.execution.Frame" not in text:
            raise RuntimeError("ExecuteCommand execute signature no longer matches 26.3")
        target=OUT/(cls.replace(".","_")+".javap.txt")
        target.write_text(text,encoding="utf-8")
        invokes=[
            line.strip()
            for line in text.splitlines()
            if re.search(r"\b(invokevirtual|invokespecial|invokeinterface|invokestatic|invokedynamic)\b",line)
        ]
        print(f"CLASS {cls}: {len(invokes)} callsites; full bytecode in {target}",flush=True)
        if cls.endswith(("BuildContexts","ExecuteCommand","ContextChain","CommandContext")):
            for line in invokes[:180]:
                print("  "+line,flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
