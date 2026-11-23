#!/usr/bin/env python3
"""IR-031 Gate A: inspect the exact 26.3 entity result-store writeback contract.

This is source-free javap inspection of the fingerprinted Loom classfile jar.
It does not add a runtime hook, mutate gameplay, or claim a safe optimization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

from ci_typed_ir030_inspect import find_mapped_jar, method_sections

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-031-MAPPED"

CLASSES = (
    "net.minecraft.server.commands.data.EntityDataAccessor",
    "net.minecraft.world.entity.Entity",
    "net.minecraft.world.entity.Marker",
    "net.minecraft.world.item.component.CustomData",
    "net.minecraft.core.component.DataComponents",
    "net.minecraft.world.level.storage.TagValueInput",
    "net.minecraft.world.level.storage.TagValueOutput",
)
FOCUS = re.compile(
    r"setData|load\(|postDataManipulated|readAdditionalSaveData|"
    r"addAdditionalSaveData|repositionEntityAfterLoad|reapplyPosition|"
    r"setComponent|applyImplicitComponent|customData|CUSTOM_DATA|"
    r"CustomData|copyTag|update\(|CODEC|TagValueInput|"
    r"ProblemReporter|EntityDataAccessor|setUUID|saveWithoutId",
    re.I,
)
MARKER_LIFECYCLE_METHODS = (
    "load(", "postDataManipulated(", "readAdditionalSaveData(",
    "addAdditionalSaveData(", "repositionEntityAfterLoad(",
)


def focused_methods(methods: list[dict]) -> dict[str, list[str]]:
    result = {}
    for section in methods:
        signature = section["signature"]
        if any(token in signature for token in (
            "load(", "postDataManipulated(", "readAdditionalSaveData(",
            "addAdditionalSaveData(", "repositionEntityAfterLoad(",
            "setComponent(", "applyImplicitComponent(", "saveWithoutId(",
            "setData(", "copyTag(", " update(", " of(",
        )):
            result[signature] = [
                line.strip() for line in section["lines"] if FOCUS.search(line)
            ]
    return result


def inspect() -> dict:
    jar, jar_sha, present = find_mapped_jar()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "milestone": "COMPILER-IR-031-GATE-A",
        "status": "mapped_writeback_contract_inventory",
        "minecraft": "26.3",
        "mapped_jar_sha256": jar_sha,
        "official_server_sha256": "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64",
        "classes": {},
        "marker_overrides_entity_load_lifecycle": {},
        "runtime_code_changed": False,
        "optimizer_implemented": False,
        "semantic_equivalence_proven": False,
        "bellows_1_1_3_already_has_filtered_setter": True,
        "bellows_1_1_3_source_commit": "7c53a5cde1baa8a3eccf1d208d0828a66b880965",
    }
    for classname in CLASSES:
        entry = classname.replace(".", "/") + ".class"
        if entry not in present:
            raise AssertionError(f"Required mapped 26.3 class missing: {classname}")
        result = subprocess.run(
            ["javap", "-p", "-c", "-s", "-classpath", str(jar), classname],
            capture_output=True, text=True, timeout=120, check=False,
        )
        if result.returncode:
            raise AssertionError(f"javap failed for {classname}: {result.stderr[:1000]}")
        methods = method_sections(result.stdout)
        if not methods:
            raise AssertionError(f"No methods in mapped class {classname}")
        short = classname.removeprefix("net.minecraft.").replace(".", "_").replace("$", "_")
        raw_name = f"{short}.javap.txt"
        (OUT / raw_name).write_text(result.stdout, encoding="utf-8")
        report["classes"][classname] = {
            "method_count": len(methods),
            "methods": [m["signature"] for m in methods],
            "focused_methods": focused_methods(methods),
            "raw_disassembly": raw_name,
            "javap_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        }
        print("IR031_CLASS " + json.dumps({
            "class": classname,
            "methods": len(methods),
            "focused": len(report["classes"][classname]["focused_methods"]),
            "raw": raw_name,
        }), flush=True)

    marker_methods = report["classes"]["net.minecraft.world.entity.Marker"]["methods"]
    for method in MARKER_LIFECYCLE_METHODS:
        report["marker_overrides_entity_load_lifecycle"][method] = [
            signature for signature in marker_methods if method in signature
        ]

    entity_methods = report["classes"]["net.minecraft.world.entity.Entity"]["methods"]
    accessor_methods = report["classes"]["net.minecraft.server.commands.data.EntityDataAccessor"]["methods"]
    custom_data_methods = report["classes"]["net.minecraft.world.item.component.CustomData"]["methods"]
    components_methods = report["classes"]["net.minecraft.core.component.DataComponents"]["methods"]

    required_entity = (
        "load(", "setComponent(", "applyImplicitComponent(", "postDataManipulated(",
        "saveWithoutId(", "get(",
    )
    required_accessor = ("setData(", "getData(")
    required_custom = ("copyTag(", "of(")
    for token in required_entity:
        if not any(token in signature for signature in entity_methods):
            raise AssertionError(f"Entity.{token} missing from mapped 26.3")
    for token in required_accessor:
        if not any(token in signature for signature in accessor_methods):
            raise AssertionError(f"EntityDataAccessor.{token} missing from mapped 26.3")
    for token in required_custom:
        if not any(token in signature for signature in custom_data_methods):
            raise AssertionError(f"CustomData.{token} missing from mapped 26.3")
    if not any("CUSTOM_DATA" in signature for signature in components_methods):
        # javap lists fields outside method declarations, so check raw output below.
        raw = (OUT / "core_component_DataComponents.javap.txt").read_text()
        if "CUSTOM_DATA" not in raw:
            raise AssertionError("DataComponents.CUSTOM_DATA missing from mapped 26.3")

    marker_overrides = report["marker_overrides_entity_load_lifecycle"]
    report["marker_declares_any_entity_load_lifecycle_override"] = any(marker_overrides.values())
    report["entity_component_setter_is_public"] = any(
        signature.startswith("public ") and "setComponent(" in signature
        for signature in entity_methods
    )
    report["custom_data_factory_and_copy_present"] = all(
        any(token in signature for signature in custom_data_methods)
        for token in required_custom
    )
    report["open_questions"] = [
        "Does a direct CustomData component replacement preserve all observable side effects of Entity.load for exact Marker?",
        "Does the original EntityDataAccessor.setData call count equal exactly the 5,820 append_here coordinate stores?",
        "Can exact source-site timing isolate EntityDataAccessor.setData/Entity.load from unrelated entity NBT writes?",
        "Does Bellows 1.1.3 filtered data write already cover this exact path, and should a candidate decline when Bellows is installed?",
        "What vanilla/Fabric/Mixin hooks observe Entity.load or component replacement for Marker?",
    ]
    report["interpretation"] = (
        "Static bytecode inventory only. Entity.load performs more than replacing custom_data; "
        "a path-specific write may omit entity lifecycle effects. Exact Marker overrides and "
        "runtime side effects must be checked before any implementation."
    )
    (OUT / "inventory.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IR031_MAPPED_DONE " + json.dumps({
        "status": report["status"],
        "mapped_sha256": jar_sha,
        "marker_lifecycle_overrides": marker_overrides,
        "optimizer_implemented": False,
        "semantic_equivalence_proven": False,
    }, sort_keys=True), flush=True)
    return report


if __name__ == "__main__":
    inspect()
