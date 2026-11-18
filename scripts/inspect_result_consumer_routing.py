#!/usr/bin/env python3
"""SCHED-ATTR-028: inspect exact 26.3 consumer routing bytecode before hot hooks.

No game run or performance inference. Reuses official Mojang SHA verifier and
Loom-derived 26.3 classfile location from the accepted SCHED-ATTR-026 survey.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess

from inspect_task_phase_calls import verify_official_server, find_classfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build"/"benchmarks"/"SCHED-ATTR-028"
OUT.mkdir(parents=True,exist_ok=True)

CLASSES=(
    "net.minecraft.commands.ExecutionCommandSource",
    "net.minecraft.commands.CommandSourceStack",
    "net.minecraft.commands.CommandResultCallback",
    "net.minecraft.commands.execution.Frame",
    "net.minecraft.commands.execution.ExecutionContext",
    "net.minecraft.commands.execution.tasks.ExecuteCommand",
    "net.minecraft.commands.execution.tasks.BuildContexts",
    "net.minecraft.commands.execution.tasks.CallFunction",
    "com.mojang.brigadier.ResultConsumer",
    "com.mojang.brigadier.context.ContextChain",
)

def main()->int:
    official=verify_official_server()
    jar,loom_sha=find_classfile()
    roots=Path.home()/".gradle"/"caches"/"modules-2"/"files-2.1"/"com.mojang"/"brigadier"
    brigadier=sorted(roots.rglob("brigadier-*.jar"))
    if not brigadier:
        raise RuntimeError("Brigadier jar missing from Loom 26.3 dependency resolution")
    cp=os.pathsep.join((str(jar),str(brigadier[-1])))
    (OUT/"source-fingerprints.txt").write_text(
        "minecraft=26.3\n"
        f"official_server_sha256={official}\n"
        f"loom_derived_jar_sha256={loom_sha}\n"
        f"brigadier_jar_sha256={hashlib.sha256(brigadier[-1].read_bytes()).hexdigest()}\n",
        encoding="utf-8"
    )
    for cls in CLASSES:
        proc=subprocess.run(["javap","-p","-s","-c","-classpath",cp,cls],
                            text=True,capture_output=True,check=True,timeout=35)
        data=proc.stdout
        (OUT/(cls.replace(".","_")+".javap.txt")).write_text(data,encoding="utf-8")
        invocations=[x.strip() for x in data.splitlines() if
                    re.search(r"\b(invokevirtual|invokeinterface|invokestatic|invokedynamic|invokespecial)\b",x)]
        print(f"CLASS {cls} ({len(invocations)} callsites)",flush=True)
        for line in invocations:
            if any(part in line for part in (
                "callback", "Callback", "consumer", "Consumer", "result", "Result",
                "lambda$", "CommandSourceStack", "CommandResultCallback",
                "ExecutionCommandSource", "onSuccess", "onFailure")):
                print("  "+line,flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
