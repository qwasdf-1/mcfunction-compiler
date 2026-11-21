#!/usr/bin/env python3
"""IR-023 source-free inventory of actual official mapped Minecraft 26.3 mutation APIs.

No classfiles, bytecode rewrites, runtime mixins, or compiler changes are made.
Writes mapped javap output only to build/reports as CI artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-023-MAPPED"
JAR_DIR = Path.home() / ".gradle/caches/fabric-loom/minecraftMaven"
CLASSES = {
    "net.minecraft.world.entity.Entity": True,
    "net.minecraft.server.commands.TagCommand": True,
    "net.minecraft.server.level.ServerLevel": True,
    "net.minecraft.commands.arguments.selector.EntitySelector": True,
    "net.minecraft.world.level.entity.PersistentEntitySectionManager": False,
    "net.minecraft.world.level.entity.EntityInLevelCallback": False,
    "net.minecraft.world.level.entity.EntitySectionStorage": False,
    "net.minecraft.world.level.entity.EntityLookup": False,
}
NEEDLES = re.compile(
    r"addTag|removeTag|entityTags|getTags|setRemoved|load\(|readAdditionalSaveData|"
    r"addFreshEntity|addDuringTeleport|addEntity|entityCallback|"
    r"onTrackingStart|onTrackingEnd|startTracking|stopTracking|"
    r"getEntities|findEntities|updateChunkStatus|removeSection|"
    r"unload|dimension|Tags|EntityInLevelCallback",
    re.I,
)


def summarize_javap(output: str) -> dict:
    lines = output.splitlines()
    details = []
    for number, line in enumerate(lines):
        if NEEDLES.search(line):
            details.append({"line_number_1based": number + 1, "text": line.strip(),
                            "previous": lines[number - 1].strip() if number else "",
                            "next": lines[number + 1].strip()
                            if number + 1 < len(lines) else ""})
    return {"lines": len(lines), "matching_details": details,
            "total_matching_lines": len(details)}


def main() -> None:
    jarlist = list(JAR_DIR.rglob("minecraft-merged-deobf-26.3.jar"))
    if len(jarlist) != 1:
        raise AssertionError(f"Expected exactly one Loom-mapped 26.3 JAR; found {jarlist}")
    jar = jarlist[0]
    OUT.mkdir(parents=True, exist_ok=True)
    classes = {}
    for full_name, required in CLASSES.items():
        process = subprocess.run(
            ["javap", "-p", "-c", "-s", "-classpath", str(jar), full_name],
            capture_output=True, text=True, check=False, timeout=120
        )
        if process.returncode:
            if required:
                raise AssertionError(f"Missing required mapped class {full_name}: "
                                     f"{process.stderr[:400]}")
            classes[full_name] = {"status": "optional_not_found"}
            continue
        simple_name = full_name.rsplit(".", 1)[-1]
        (OUT / (simple_name + ".txt")).write_text(process.stdout, encoding="utf-8")
        classes[full_name] = {"status": "found", **summarize_javap(process.stdout)}
        print("IR023_MAPPED_CLASS", full_name, "matched",
              classes[full_name]["total_matching_lines"], flush=True)
    entity = classes["net.minecraft.world.entity.Entity"]
    tag_command = classes["net.minecraft.server.commands.TagCommand"]
    for name in ("addTag", "removeTag", "entityTags", "setRemoved"):
        if not any(name + "(" in row["text"] for row in entity["matching_details"]):
            raise AssertionError(f"Actual mapped Entity method not verified: {name}")
    if not any("addTag" in row["text"] or "removeTag" in row["text"]
               for row in tag_command["matching_details"]):
        raise AssertionError("TagCommand's actual add/remove implementation not observed")
    report = {
        "milestone": "COMPILER-IR-023", "status": "mapped_method_inventory_only",
        "mapped_minecraft_version": "26.3",
        "mapped_jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "classes": classes,
        "runtime_probe_installed": False,
        "index_implemented": False,
        "native_visibility_or_mutation_frequency_measured": False,
    }
    (OUT / "inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR023_MAPPED_INVENTORY", json.dumps({
        "status": report["status"], "sha256": report["mapped_jar_sha256"],
        "methods_verified": ["addTag", "removeTag", "entityTags", "setRemoved"],
        "classes_found": [n for n, d in classes.items() if d["status"] == "found"],
        "native_visibility_or_mutation_frequency_measured": False
    }), flush=True)


if __name__ == "__main__":
    main()
