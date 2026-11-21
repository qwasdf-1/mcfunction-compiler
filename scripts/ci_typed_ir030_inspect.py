#!/usr/bin/env python3
"""IR-030 Gate A: source-free, SHA-checked mapped 26.3 entity NBT method inventory.

Only disassembles the exact mapped Minecraft jar. Does not install hooks, alter
commands, compile an optimizer, or claim semantic/cost equivalence. Raw javap
outputs live in a CI artifact, never in the Git repository.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-030-MAPPED"
JAR_DIR = Path.home() / ".gradle/caches/fabric-loom/minecraftMaven"
LOCK = ROOT / "docs/research/source-versions.lock"
PREFIX = "net/minecraft/server/commands/data/"
CLASSES = (
    "net.minecraft.server.commands.data.DataCommands",
    "net.minecraft.server.commands.data.EntityDataAccessor",
    "net.minecraft.server.commands.data.DataAccessor",
    "net.minecraft.server.commands.ExecuteCommand",
    "net.minecraft.commands.arguments.NbtPathArgument",
    "net.minecraft.world.entity.Entity",
    "net.minecraft.advancements.critereon.NbtPredicate",
    "net.minecraft.commands.CommandSourceStack",
    "net.minecraft.commands.execution.tasks.ExecuteCommand",
    "net.minecraft.commands.execution.tasks.BuildContexts",
)
# These are search indicators, NOT a proof that any particular operation is
# called, or safe to bypass. Preserve the full bytecode for manual inspection.
FOCUS = re.compile(
    r"DataAccessor|DataCommands|getData|getSingleTag|setData|saveWithoutId|"
    r"getEntityTagToCompare|TagValueOutput|NbtPath|Pos\b|getPosition|"
    r"getBlockPos|Mth\.(?:floor|ceil)|Math\.(?:floor|ceil|round)|"
    r"resultConsumer|ResultConsumer|Store|store|callback|Callback|"
    r"CommandSyntaxException|sendSuccess|sendFailure|execute|runCommand",
    re.I,
)
HEADER = re.compile(r"^  [^ ].*\([^;]*\);$")


def lock_properties(contents: str) -> dict[str, str]:
    result = {}
    for line in contents.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def method_sections(javap: str) -> list[dict]:
    """Keep each line associated with its closest method declaration."""
    methods = []
    current = None
    for line in javap.splitlines():
        if HEADER.match(line):
            current = {"signature": line.strip(), "lines": []}
            methods.append(current)
        if current is not None:
            current["lines"].append(line)
    return methods


def focused_sites(methods: list[dict], limit: int = 180) -> list[dict]:
    sites = []
    for section in methods:
        for number, line in enumerate(section["lines"]):
            if FOCUS.search(line):
                sites.append({
                    "method": section["signature"],
                    "line_within_method": number + 1,
                    "instruction": line.strip(),
                    "previous": section["lines"][number-1].strip() if number else "",
                    "next": section["lines"][number+1].strip()
                    if number+1 < len(section["lines"]) else "",
                })
    return sites[:limit]


def find_mapped_jar() -> tuple[Path, str, set[str]]:
    jars = list(JAR_DIR.rglob("minecraft-merged-deobf-26.3.jar"))
    if len(jars) != 1:
        raise AssertionError(f"Expected one Loom-mapped 26.3 jar, found {len(jars)}")
    jar = jars[0]
    sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    props = lock_properties(LOCK.read_text(encoding="utf-8"))
    accepted = {
        props.get("inspection.classfile_artifact_sha256"),
        props.get("verification.current_26.3_classfile_artifact_sha256"),
    }
    accepted.discard(None)
    if props.get("minecraft.version") != "26.3" or sha not in accepted:
        raise AssertionError(f"Wrong unverified mapped Minecraft version/hash: {sha}")
    with zipfile.ZipFile(jar) as archive:
        present = set(archive.namelist())
    return jar, sha, present


def inspect() -> dict:
    jar, sha, present = find_mapped_jar()
    OUT.mkdir(parents=True, exist_ok=True)
    # Discover nested command/accessor classfiles from the actual jar rather
    # than assuming 26.3 synthetic lambda or nested-class identifiers.
    nested = sorted(name for name in present
                    if (name.startswith(PREFIX + "DataCommands$")
                        or name.startswith(PREFIX + "EntityDataAccessor$"))
                    and name.endswith(".class"))
    classes = list(CLASSES) + [
        name[:-6].replace("/", ".") for name in nested[:24]
    ]
    report = {
        "milestone": "COMPILER-IR-030-GATE-A",
        "status": "mapped_bytecode_inventory_only",
        "minecraft": "26.3",
        "mapped_jar_sha256": sha,
        "class_results": {},
        "nested_candidates": nested,
        "runtime_code_changed": False,
        "optimization_implemented": False,
        "native_semantic_parity_proven": False,
        "native_cpu_measured": False,
        "open_questions": [
            "Does /data get entity Pos[axis] use the same entity accessor pathway as macro arguments?",
            "What is the exact numeric conversion, feedback, error and quota contract?",
            "Can a direct coordinate read preserve observable modded NBT serialization?",
            "How does the outer /execute store result entity mutate and restore live entity state?",
        ],
    }
    for index, classname in enumerate(classes):
        entry = classname.replace(".", "/") + ".class"
        required = index < len(CLASSES)
        if entry not in present:
            if required:
                raise AssertionError(f"Missing required mapped class {classname}")
            continue
        result = subprocess.run(
            ["javap", "-p", "-c", "-s", "-classpath", str(jar), classname],
            capture_output=True, text=True, timeout=120, check=False,
        )
        if result.returncode:
            raise AssertionError(f"javap failed for {classname}: {result.stderr[:500]}")
        methods = method_sections(result.stdout)
        if not methods:
            raise AssertionError(f"No method declarations found: {classname}")
        short = classname.rsplit(".", 1)[-1].replace("$", "_")
        # Prevent publishing/committing game classfiles; bytecode text only.
        (OUT / f"{short}.javap.txt").write_text(result.stdout, encoding="utf-8")
        report["class_results"][classname] = {
            "methods": [m["signature"] for m in methods],
            "focus": focused_sites(methods),
            "raw_disassembly": f"{short}.javap.txt",
        }
        print("IR030_CLASS " + json.dumps({
            "name": classname, "methods": len(methods),
            "focus_rows": len(report["class_results"][classname]["focus"]),
        }), flush=True)
    # Fail closed if the expected named core data entrypoints don't exist.
    for cls, method in (
        ("net.minecraft.server.commands.data.DataCommands", "getSingleTag("),
        ("net.minecraft.server.commands.data.EntityDataAccessor", "getData("),
        ("net.minecraft.server.commands.data.EntityDataAccessor", "setData("),
    ):
        signatures = report["class_results"][cls]["methods"]
        if not any(method in signature for signature in signatures):
            raise AssertionError(f"Expected mapped command contract missing: {cls}.{method}")
    # Presence of those methods alone IS NOT a verified execute-store contract.
    output = OUT / "inventory.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IR030_MAPPED_DONE " + json.dumps({
        "status": report["status"], "hash": sha,
        "classes": len(report["class_results"]),
        "native_semantic_parity_proven": False,
    }), flush=True)
    return report


if __name__ == "__main__":
    inspect()
