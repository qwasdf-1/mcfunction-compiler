#!/usr/bin/env python3
"""IR-030 Gate C2: native-versus-candidate 26.3 entity Pos semantics.

Runs two fresh Fabric 26.3 servers with identical datapack fixtures:
  control: wrapper/candidate off
  candidate: wrapper on, exact function allowlist, native differential verifier on

The candidate fast path is exercised only by an unmounted vanilla Marker.
Mounted markers and other entity classes must delegate to the native callback.
The native execute-store entity modifier remains untouched in both arms.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-030-SEMANTICS"
sys.path.insert(0, str(ROOT / "scripts"))
import run_compatibility_probe as compat  # noqa: E402
from ci_typed_ir030_source import inspect as inspect_original_source  # noqa: E402
from ci_typed_ir015_fetch import fetch  # noqa: E402

PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
CANDIDATE_FUNCTIONS = (
    "vm:queue/append_here,"
    "function_compiler_probe:ir030_pos_store,"
    "function_compiler_probe:ir030_missing_path"
)
XYZ = re.compile(r"x\s*:\s*(-?\d+)\s*,\s*y\s*:\s*(-?\d+)\s*,\s*z\s*:\s*(-?\d+)")


def xyz(response: str) -> tuple[int, int, int]:
    match = XYZ.search(response)
    if match is None:
        raise AssertionError(f"Could not parse frontier coordinates from {response!r}")
    return tuple(map(int, match.groups()))


def stat_value(status: str, key: str) -> int:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)(?:\s|$)", status)
    if match is None:
        raise AssertionError(f"Missing {key} in compiler status: {status!r}")
    return int(match.group(1))


def must_not_fail(label: str, response: str) -> str:
    lowered = response.casefold()
    if any(word in lowered for word in (
            "unknown or invalid command", "unknown entity type",
            "syntax error", "failed to execute", "no entity was found")):
        raise RuntimeError(f"{label} failed: {response!r}")
    return response


def configure_candidate(enabled: bool) -> dict[str, str | None]:
    keys = (
        "FC_IR030_POS_GET", "FC_IR030_POS_GET_VERIFY", "FC_IR030_POS_GET_FUNCTIONS",
        "GRADLE_USER_HOME", "GRADLE_RO_DEP_CACHE",
    )
    previous = {key: os.environ.get(key) for key in keys}
    os.environ["FC_IR030_POS_GET"] = "true" if enabled else "false"
    os.environ["FC_IR030_POS_GET_VERIFY"] = "true" if enabled else "false"
    os.environ["FC_IR030_POS_GET_FUNCTIONS"] = CANDIDATE_FUNCTIONS if enabled else ""
    # The setup-gradle action exports a shared read-only cache. The nested
    # runServer invocation must use one isolated writable Gradle home instead.
    os.environ["GRADLE_USER_HOME"] = str(ROOT / "build/gradle-cache-ir030-semantic")
    os.environ.pop("GRADLE_RO_DEP_CACHE", None)
    return previous


def restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def run_arm(label: str, mode: str, candidate_enabled: bool, server_jar: Path) -> dict:
    work = ROOT / "run" / f"ir030-semantic-{label}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    port = compat.free_port()
    compat.write_server_files(work, port, include_modded_command=False)
    log_path = OUT / f"{label}.server.log"
    previous = configure_candidate(candidate_enabled)
    process = None
    log_handle = None
    client = None
    try:
        process, log_handle = compat.start_server(mode, work, server_jar, log_path)
        client = compat.wait_for_rcon(process, port, timeout=240)
        responses: dict[str, dict[str, str]] = {}
        response_path = OUT / f"{label}.commands.json"
        original_command = client.command
        def logged_command(command_text: str) -> str:
            response_text = original_command(command_text)
            responses[str(len(responses))] = {
                "command": command_text, "response": response_text,
            }
            response_path.write_text(
                json.dumps(responses, indent=2) + "\\n", encoding="utf-8")
            return response_text
        client.command = logged_command
        enabled = client.command("datapack list enabled")
        if "function_compiler_probe" not in enabled:
            raise RuntimeError(f"Probe datapack did not load: {enabled!r}")
        initial_status = client.command("function_compiler_probe status")
        expected_wrapped = candidate_enabled
        if f"wrapped={str(expected_wrapped).lower()}" not in initial_status:
            raise RuntimeError(f"Unexpected wrapper state for {label}: {initial_status!r}")

        # Unmounted Marker at negative fractional coordinates: floor, not cast.
        must_not_fail("summon free marker", client.command(
            "summon minecraft:marker -1.25 64.5 -0.75"))
        must_not_fail("tag free marker", client.command(
            "tag @e[type=minecraft:marker,sort=nearest,limit=1] add ir030_free"))
        must_not_fail("initialize free marker", client.command(
            "data modify entity @e[type=minecraft:marker,tag=ir030_free,limit=1] "
            "data.frontier set value [{x:0,y:0,z:0}]"))
        free_call = client.command(
            "execute as @e[type=minecraft:marker,tag=ir030_free,limit=1] "
            "run function function_compiler_probe:ir030_pos_store")
        free_frontier_text = client.command(
            "data get entity @e[type=minecraft:marker,tag=ir030_free,limit=1] data.frontier")
        free_frontier = xyz(free_frontier_text)

        # A mounted Marker must use the native snapshot rule (vehicle X/Z,
        # passenger Y) and may become unmounted after EntityDataAccessor.setData.
        must_not_fail("summon vehicle", client.command(
            "summon minecraft:horse 10.25 100.5 20.75 "
            "{NoAI:1b,NoGravity:1b,Invulnerable:1b}"))
        must_not_fail("tag vehicle", client.command(
            "tag @e[type=minecraft:horse,limit=1] add ir030_vehicle"))
        must_not_fail("summon passenger marker", client.command(
            "summon minecraft:marker 20.25 65.5 20.75"))
        must_not_fail("tag passenger marker", client.command(
            "tag @e[type=minecraft:marker,sort=furthest,limit=1] add ir030_passenger"))
        must_not_fail("initialize passenger marker", client.command(
            "data modify entity @e[type=minecraft:marker,tag=ir030_passenger,limit=1] "
            "data.frontier set value [{x:0,y:0,z:0}]"))
        ride_result = client.command(
            "ride @e[type=minecraft:marker,tag=ir030_passenger,limit=1] mount "
            "@e[type=minecraft:horse,tag=ir030_vehicle,limit=1]")
        if any(word in ride_result.casefold() for word in ("couldn't", "cannot", "failed", "no entity")):
            raise RuntimeError(f"Could not mount the Marker passenger: {ride_result!r}")
        passenger_call = client.command(
            "execute as @e[type=minecraft:marker,tag=ir030_passenger,limit=1] "
            "run function function_compiler_probe:ir030_pos_store")
        passenger_frontier_text = client.command(
            "data get entity @e[type=minecraft:marker,tag=ir030_passenger,limit=1] data.frontier")
        passenger_frontier = xyz(passenger_frontier_text)

        # Non-Marker entity type must remain on the original serializer path.
        must_not_fail("summon armor stand", client.command(
            "summon minecraft:armor_stand -1.25 64.5 -0.75 {NoGravity:1b}"))
        must_not_fail("tag armor stand", client.command(
            "tag @e[type=minecraft:armor_stand,limit=1] add ir030_nonmarker"))
        must_not_fail("initialize armor stand", client.command(
            "data modify entity @e[type=minecraft:armor_stand,tag=ir030_nonmarker,limit=1] "
            "data.frontier set value [{x:0,y:0,z:0}]"))
        nonmarker_call = client.command(
            "execute as @e[type=minecraft:armor_stand,tag=ir030_nonmarker,limit=1] "
            "run function function_compiler_probe:ir030_pos_store")
        nonmarker_frontier_text = client.command(
            "data get entity @e[type=minecraft:armor_stand,tag=ir030_nonmarker,limit=1] "
            "data.frontier")
        nonmarker_frontier = xyz(nonmarker_frontier_text)

        # A missing NBT path is outside the specialization and must not mutate
        # the destination. The function is allowlisted only to exercise parser
        # decline; its Pos-path check must reject Missing[0].
        must_not_fail("summon missing-path marker", client.command(
            "summon minecraft:marker 50.25 65.5 50.75"))
        must_not_fail("tag missing-path marker", client.command(
            "tag @e[type=minecraft:marker,sort=furthest,limit=1] add ir030_missing"))
        must_not_fail("initialize missing-path marker", client.command(
            "data modify entity @e[type=minecraft:marker,tag=ir030_missing,limit=1] "
            "data.frontier set value [{x:7,y:8,z:9}]"))
        missing_call = client.command(
            "execute as @e[type=minecraft:marker,tag=ir030_missing,limit=1] "
            "run function function_compiler_probe:ir030_missing_path")
        missing_frontier_text = client.command(
            "data get entity @e[type=minecraft:marker,tag=ir030_missing,limit=1] "
            "data.frontier")
        missing_frontier = xyz(missing_frontier_text)

        # The outer entity store target is @s. From the console there is no
        # executor, so the native modifier must fail before entering the getter.
        invalid_target_response = client.command(
            "function function_compiler_probe:ir030_pos_store")

        final_status = client.command("function_compiler_probe status")
        result = {
            "label": label,
            "candidate_enabled": candidate_enabled,
            "wrapper_status": initial_status,
            "free_marker": {
                "function_response": free_call,
                "frontier_response": free_frontier_text,
                "frontier": free_frontier,
            },
            "passenger_marker": {
                "ride_response": ride_result,
                "function_response": passenger_call,
                "frontier_response": passenger_frontier_text,
                "frontier": passenger_frontier,
            },
            "nonmarker": {
                "function_response": nonmarker_call,
                "frontier_response": nonmarker_frontier_text,
                "frontier": nonmarker_frontier,
            },
            "missing_path": {
                "function_response": missing_call,
                "frontier_response": missing_frontier_text,
                "frontier": missing_frontier,
            },
            "invalid_target_response": invalid_target_response,
            "final_status": final_status,
            "ir030_counters": {
                key: stat_value(final_status, key)
                for key in (
                    "ir030_pos_compiled_x", "ir030_pos_compiled_y", "ir030_pos_compiled_z",
                    "ir030_pos_fast_x", "ir030_pos_fast_y", "ir030_pos_fast_z",
                    "ir030_pos_verified", "ir030_pos_verify_mismatches",
                    "ir030_pos_invalid_targets", "ir030_pos_fallback_vehicle",
                    "ir030_pos_fallback_entity_type", "ir030_pos_fallback_nonfinite",
                )
            },
        }
        client.command("stop")
        process.wait(timeout=60)
        return result
    finally:
        if client is not None:
            client.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if log_handle is not None:
            log_handle.close()
        restore_env(previous)
        shutil.rmtree(work, ignore_errors=True)


def compare(control: dict, candidate: dict) -> dict:
    for key in ("free_marker", "passenger_marker", "nonmarker", "missing_path"):
        if control[key]["frontier"] != candidate[key]["frontier"]:
            raise AssertionError(
                f"Native/candidate {key} frontier mismatch: "
                f"{control[key]['frontier']} != {candidate[key]['frontier']}")
        if control[key]["function_response"] != candidate[key]["function_response"]:
            raise AssertionError(
                f"Native/candidate {key} function result changed: "
                f"{control[key]['function_response']!r} != "
                f"{candidate[key]['function_response']!r}")
    if control["invalid_target_response"] != candidate["invalid_target_response"]:
        raise AssertionError("Native/candidate invalid-target response changed")
    if candidate["free_marker"]["frontier"] != (-2, 64, -1):
        raise AssertionError(
            f"Negative fractional Marker position did not floor correctly: "
            f"{candidate['free_marker']['frontier']}")
    if candidate["nonmarker"]["frontier"] != (-2, 64, -1):
        raise AssertionError("Non-Marker native fallback did not preserve coordinates")
    counters = candidate["ir030_counters"]
    if (counters["ir030_pos_compiled_x"], counters["ir030_pos_compiled_y"],
            counters["ir030_pos_compiled_z"]) != (1, 1, 1):
        raise AssertionError(f"Expected exactly three candidate terminals: {counters!r}")
    if min(counters["ir030_pos_fast_x"], counters["ir030_pos_fast_y"],
           counters["ir030_pos_fast_z"]) < 1:
        raise AssertionError(f"Unmounted Marker did not take all three candidate axes: {counters!r}")
    if counters["ir030_pos_verified"] != sum(
            counters[f"ir030_pos_fast_{axis}"] for axis in "xyz"):
        raise AssertionError(f"Not every fast-path read was natively verified: {counters!r}")
    if counters["ir030_pos_verify_mismatches"] != 0:
        raise AssertionError(f"Native/candidate NBT or feedback mismatch: {counters!r}")
    if counters["ir030_pos_fallback_vehicle"] < 1:
        raise AssertionError(f"Mounted Marker did not use native fallback: {counters!r}")
    if counters["ir030_pos_fallback_entity_type"] < 3:
        raise AssertionError(f"Non-Marker entity did not use native fallback: {counters!r}")
    if counters["ir030_pos_invalid_targets"] != 0:
        raise AssertionError(f"Unexpected inner invalid target invocation: {counters!r}")
    return {
        "status": "accepted_candidate_fixture_parity",
        "control": control,
        "candidate": candidate,
        "all_frontier_results_equal": True,
        "negative_coordinate_floor_verified": True,
        "passenger_native_fallback_verified": True,
        "non_marker_native_fallback_verified": True,
        "missing_path_native_fallback_verified": True,
        "invalid_target_outer_modifier_unchanged": True,
        "feedback_component_verified_inside_candidate": True,
        "native_execute_store_callback_unchanged": True,
        "runtime_feature_default_enabled": False,
        "cpu_speedup_measured": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pack = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
    if not pack.is_file():
        fetch("veinminer")
    if hashlib.sha256(pack.read_bytes()).hexdigest() != PIN:
        raise AssertionError("Pinned original publisher archive SHA mismatch")
    source = inspect_original_source()
    if not source.get("append_here_call_sites"):
        raise AssertionError("Original append_here caller missing")
    server_jar = compat.locate_official_server_jar()
    if compat.sha256(server_jar) != compat.SERVER_SHA256:
        raise AssertionError("Minecraft 26.3 official server JAR SHA mismatch")
    report = {
        "milestone": "COMPILER-IR-030-GATE-C2",
        "status": "started",
        "publisher_sha256": PIN,
        "source_callers": {
            "append_here": source["append_here_call_sites"],
            "enqueue_match": source["enqueue_match_call_sites"],
        },
        "minecraft": "26.3",
        "java": "25",
        "arms": {},
        "runtime_semantic_parity_proven": False,
        "cpu_speedup_measured": False,
    }
    try:
        report["arms"]["native_control"] = run_arm(
            "native-control", "fabric-off", False, server_jar)
        report["arms"]["candidate_verify"] = run_arm(
            "candidate-verify", "fabric-on", True, server_jar)
        report.update(compare(
            report["arms"]["native_control"],
            report["arms"]["candidate_verify"]))
        report["runtime_semantic_parity_proven"] = True
    except Exception as exc:
        report["status"] = "invalid"
        report["error"] = repr(exc)
        raise
    finally:
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IR030_SEMANTIC_PARITY " + json.dumps({
        "status": report["status"],
        "free": report["arms"].get("candidate_verify", {}).get("free_marker", {}).get("frontier"),
        "passenger": report["arms"].get("candidate_verify", {}).get("passenger_marker", {}).get("frontier"),
        "nonmarker": report["arms"].get("candidate_verify", {}).get("nonmarker", {}).get("frontier"),
        "counters": report["arms"].get("candidate_verify", {}).get("ir030_counters"),
    }), flush=True)


if __name__ == "__main__":
    main()
