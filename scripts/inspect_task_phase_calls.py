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
# Loom's generated whole-JAR SHA is *not* reproducible across CI boots:
# two 2026-11-18 rebuilds yielded different SHA-256. Archive it as evidence,
# but validate provenance against the immutable official server bundle instead.
OFFICIAL_SOURCE_LOCK=ROOT/"docs"/"research"/"source-versions.lock"

def verify_official_server()->str:
    """Stream the official Mojang 26.3 bundle and verify its locked digest."""
    import urllib.request
    entries={}
    for line in OFFICIAL_SOURCE_LOCK.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key,value=line.split("=",1)
            entries[key.strip()]=value.strip()
    if entries.get("minecraft.version")!="26.3":
        raise RuntimeError("Source-version lock is not Minecraft 26.3")
    url=entries["minecraft.official_server_jar"]
    expected=entries["minecraft.official_server_sha256"]
    if not url.startswith("https://piston-data.mojang.com/"):
        raise RuntimeError("Source lock has unexpected official Mojang domain")
    request=urllib.request.Request(url,headers={"User-Agent":"MCFC-SCHED-ATTR-026-inspection/1.0"})
    hasher=hashlib.sha256()
    size=0
    with urllib.request.urlopen(request,timeout=90) as response:
        while chunk:=response.read(1024*1024):
            hasher.update(chunk)
            size+=len(chunk)
    actual=hasher.hexdigest()
    if actual!=expected:
        raise RuntimeError(f"Official Mojang Minecraft 26.3 SHA mismatch {actual}")
    (OUT/"official-server-sha256.txt").write_text(
        f"{actual}  official-mojang-server.jar  {size} bytes\\n",encoding="utf-8")
    print(f"VERIFIED Minecraft 26.3 official server SHA-256 {actual}, {size} bytes",flush=True)
    return actual

def find_classfile()->tuple[Path,str]:
    root=Path.home()/".gradle"/"caches"/"fabric-loom"/"minecraftMaven"/"net"/"minecraft"/"minecraft-merged-deobf"/"26.3"
    candidates=list(root.glob("minecraft-merged-deobf-26.3.jar")) if root.exists() else []
    if len(candidates)!=1:
        raise RuntimeError("Exactly one Loom 26.3 merged-deobf jar required")
    jar=candidates[0]
    sha=hashlib.sha256(jar.read_bytes()).hexdigest()
    print(f"LOOM_CLASSFILE {jar} sha256={sha}",flush=True)
    return jar,sha

def main()->int:
    source_sha=verify_official_server()
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
