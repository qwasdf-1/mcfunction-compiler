#!/usr/bin/env python3
"""Exotic Adversarial Red-Team Probe on Minecraft 26.3.

Explores failure domains, edge cases, external optimization mod interactions
(FerriteCore, C2ME, LBMFC, LBFC-C2ME), deep mutual recursion, unloaded chunk
boundary traversal, and command output suppression against official vanilla.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mod_artifacts import MODS, MODS_DIR  # noqa: E402
from run_redteam_probe import (  # noqa: E402
    free_port,
    locate_official_server_jar,
    read_score,
    run_in_server_session,
    wait_for_rcon,
    write_server_files,
    _get_selective_macro_count,
)
from run_runtime_probe import RconClient  # noqa: E402

REPORT_DIR = ROOT / "build" / "reports" / "exotic-redteam-probe"
RCON_HOST = "127.0.0.1"
RCON_PASSWORD = "function-compiler-exotic-redteam-probe"
PROBE_PACK = "function_compiler_probe"
OBJECTIVE = "fc_probe"

MODES = (
    "vanilla",
    "fabric-on",
    "ferritecore",
    "c2me",
    "lbmfc",
    "lbfc-c2me",
)

MODE_MODS: dict[str, tuple[str, ...]] = {
    "vanilla": (),
    "fabric-on": (),
    "ferritecore": ("ferritecore",),
    "c2me": ("c2me",),
    "lbmfc": ("lithium", "bellows113", "moonrise120", "ferritecore"),
    "lbfc-c2me": ("lithium", "bellows113", "ferritecore", "c2me"),
}


def setup_exotic_server(work: Path, rcon_port: int, server_port: int, mode: str) -> None:
    write_server_files(
        work,
        rcon_port,
        server_port,
        rcon_password=RCON_PASSWORD,
        datapack_description="Exotic Red-Team Probe",
    )
    if mode != "vanilla":
        mod_keys = MODE_MODS.get(mode, ())
        if mod_keys:
            mods_dir = work / "mods"
            mods_dir.mkdir(parents=True, exist_ok=True)
            for mod_key in mod_keys:
                filename, _ = MODS[mod_key]
                shutil.copy2(MODS_DIR / filename, mods_dir / filename)


# =========================================================================
# Vector 1: External Optimization Mod Interactions (FerriteCore & C2ME)
# =========================================================================

def _test_vector1_opt_mods(client: RconClient, mode: str) -> dict[str, object]:
    # 1. FerriteCore storage operations & SelectiveMacro slicing
    client.command("data modify storage redteam:ferrite root set value {}")
    client.command(f"scoreboard players set #ferrite_k1 {OBJECTIVE} 0")
    client.command(f"scoreboard players set #ferrite_len {OBJECTIVE} 0")
    storage_resp = client.command(f"function {PROBE_PACK}:exotic_ferrite_storage_ops")
    k1 = read_score(client, "#ferrite_k1")
    length = read_score(client, "#ferrite_len")

    client.command(f"scoreboard players set #ferrite_m1 {OBJECTIVE} 0")
    client.command(f"scoreboard players set #ferrite_m2 {OBJECTIVE} 0")
    client.command(f"scoreboard players set #ferrite_sum {OBJECTIVE} 0")
    client.command('data merge storage redteam:ferrite_macro_in {sub: {val1: 15, val2: 25, unused_tag: "fastmap_dedup_test", nested: {dup: 1}}}')
    
    sel_before = _get_selective_macro_count(client, mode)
    macro_resp = client.command(f"function {PROBE_PACK}:exotic_ferrite_macro with storage redteam:ferrite_macro_in sub")
    sel_after = _get_selective_macro_count(client, mode)

    m1 = read_score(client, "#ferrite_m1")
    m2 = read_score(client, "#ferrite_m2")
    m_sum = read_score(client, "#ferrite_sum")

    # 2. C2ME async chunk mutations & selector queries
    client.command(f"scoreboard players set #chunk_ops {OBJECTIVE} 0")
    chunk_resp = client.command(f"function {PROBE_PACK}:exotic_c2me_chunks")
    chunk_ops = read_score(client, "#chunk_ops")

    selector_resp = client.command("execute as @e[distance=..100] run scoreboard players add #chunk_ops fc_probe 1")

    return {
        "storage_ops": {
            "response": storage_resp,
            "k1": k1,
            "length": length,
        },
        "selective_macro_under_ferrite": {
            "response": macro_resp,
            "m1": m1,
            "m2": m2,
            "sum": m_sum,
            "selective_used_delta": sel_after - sel_before,
        },
        "c2me_chunk_and_selector": {
            "response": chunk_resp,
            "chunk_ops": chunk_ops,
            "selector_query_response": selector_resp,
        },
    }


def _run_and_collect_scores(
    client: RconClient,
    names: tuple[str, str, str, str, str],
    cmd: str,
) -> tuple[str, int, int, int, int, int]:
    for name in names:
        client.command(f"scoreboard players set {name} {OBJECTIVE} 0")
    resp = client.command(cmd)
    scores = tuple(read_score(client, n) for n in names)
    return (resp, scores[0], scores[1], scores[2], scores[3], scores[4])


# =========================================================================
# Vector 2: Deep Mutual Recursion & Stack-Queue Trampoline Integrity
# =========================================================================

def _test_vector2_mutual_recursion(client: RconClient) -> dict[str, object]:
    # 1. Suspended trampoline frames (nested function calls without return run)
    client.command(f"scoreboard players set #tramp_depth {OBJECTIVE} 0")
    client.command(f"scoreboard players set #tramp_pre {OBJECTIVE} 0")
    client.command(f"scoreboard players set #tramp_post {OBJECTIVE} 0")
    tramp_resp = client.command(f"function {PROBE_PACK}:exotic_trampoline_a")
    tramp_depth = read_score(client, "#tramp_depth")
    tramp_pre = read_score(client, "#tramp_pre")
    tramp_post = read_score(client, "#tramp_post")

    # 2. Deep mutual tail-recursion with return run (100 frames)
    mut_resp, mut_depth, mut_a, mut_b, mut_accum, stored_mut = _run_and_collect_scores(
        client,
        ("#mut_depth", "#mut_count_a", "#mut_count_b", "#mut_accum", "#stored_mut"),
        f"execute store result score #stored_mut {OBJECTIVE} run function {PROBE_PACK}:exotic_mutual_run_a",
    )

    # 3. Deep mutual recursion with parameter-passing MACROS (50 frames)
    client.command("data merge storage redteam:rec_n {n: 1}")
    macro_rec_resp, m_depth, m_a, m_b, m_accum, stored_m_rec = _run_and_collect_scores(
        client,
        ("#macro_rec_depth", "#macro_rec_a", "#macro_rec_b", "#macro_accum", "#stored_macro_rec"),
        f"execute store result score #stored_macro_rec {OBJECTIVE} run function {PROBE_PACK}:exotic_macro_rec_a with storage redteam:rec_n",
    )

    return {
        "trampoline_unwind": {
            "response": tramp_resp,
            "depth": tramp_depth,
            "pre_increments": tramp_pre,
            "post_increments": tramp_post,
        },
        "mutual_tail_recursion_100": {
            "response": mut_resp,
            "depth": mut_depth,
            "count_a": mut_a,
            "count_b": mut_b,
            "accum": mut_accum,
            "stored_result": stored_mut,
        },
        "mutual_macro_recursion_50": {
            "response": macro_rec_resp,
            "depth": m_depth,
            "count_a": m_a,
            "count_b": m_b,
            "accum": m_accum,
            "stored_result": stored_m_rec,
        },
    }


# =========================================================================
# Vector 3: Asynchronous Chunk / Unloaded Boundary Traversal
# =========================================================================

def _test_vector3_chunk_boundary(client: RconClient, summon_actor: object) -> dict[str, object]:
    # 1. Unloaded boundary mutation & temporary forceload
    client.command(f"scoreboard players set #boundary_res {OBJECTIVE} 0")
    boundary_resp = client.command(f"function {PROBE_PACK}:exotic_unloaded_boundary")
    boundary_score = read_score(client, "#boundary_res")

    # 2. Multi-dimension entity travel mid-chain
    summon_actor("0.5 64 0.5", "redteam_dim_runner")
    client.command(f"scoreboard players set #dim_runner_steps {OBJECTIVE} 0")
    dim_resp = client.command(f"function {PROBE_PACK}:exotic_dim_traverse_outer")
    dim_steps = read_score(client, "#dim_runner_steps")

    return {
        "unloaded_boundary": {
            "response": boundary_resp,
            "score": boundary_score,
        },
        "multi_dimension_traversal": {
            "response": dim_resp,
            "steps": dim_steps,
        },
    }


# =========================================================================
# Vector 4: Command Output Suppression & Feedback Hygiene
# =========================================================================

def _test_vector4_output_suppression(client: RconClient) -> dict[str, object]:
    # Test with sendCommandFeedback = true
    client.command("gamerule sendCommandFeedback true")
    client.command(f"scoreboard players set #feedback_target {OBJECTIVE} 0")
    fb_true_resp = client.command(f"function {PROBE_PACK}:exotic_suppressed_feedback")
    fb_true_score = read_score(client, "#feedback_target")

    # Test with sendCommandFeedback = false
    client.command("gamerule sendCommandFeedback false")
    client.command(f"scoreboard players set #feedback_target {OBJECTIVE} 0")
    fb_false_resp = client.command(f"function {PROBE_PACK}:exotic_suppressed_feedback")
    fb_false_score = read_score(client, "#feedback_target")

    # Test execute store result capturing return value while output is suppressed
    client.command(f"scoreboard players set #stored_fb {OBJECTIVE} 0")
    store_fb_resp = client.command(f"execute store result score #stored_fb {OBJECTIVE} run function {PROBE_PACK}:exotic_suppressed_feedback")
    stored_fb = read_score(client, "#stored_fb")

    # Restore default
    client.command("gamerule sendCommandFeedback true")

    return {
        "feedback_true": {
            "response": fb_true_resp,
            "score": fb_true_score,
        },
        "feedback_false": {
            "response": fb_false_resp,
            "score": fb_false_score,
        },
        "store_result_suppressed": {
            "response": store_fb_resp,
            "stored_score": stored_fb,
        },
    }


def run_exotic_suite(client: RconClient, mode: str) -> dict[str, object]:
    client.command(f"scoreboard objectives add {OBJECTIVE} dummy")
    client.command("forceload add 0 0 256 32")
    client.command("execute in minecraft:the_nether run forceload add 0 0 32 32")
    client.command("execute in minecraft:the_end run forceload add 0 0 32 32")

    def summon_actor(pos: str, tag: str) -> None:
        client.command(f"kill @e[tag={tag}]")
        for _ in range(20):
            res = client.command(f'summon minecraft:armor_stand {pos} {{Tags:["{tag}"]}}')
            if "Summoned" in res:
                return
            time.sleep(0.05)
        raise RuntimeError(f"Could not summon actor with tag {tag}: {res}")

    return {
        "vector1_opt_mods": _test_vector1_opt_mods(client, mode),
        "vector2_mutual_recursion": _test_vector2_mutual_recursion(client),
        "vector3_chunk_boundary": _test_vector3_chunk_boundary(client, summon_actor),
        "vector4_output_suppression": _test_vector4_output_suppression(client),
    }


def _verify_vectors_1_2(arm: str, arm_data: dict, v: dict) -> list[str]:
    divergences: list[str] = []
    a1, v1 = arm_data["vector1_opt_mods"], v["vector1_opt_mods"]
    if a1["storage_ops"]["k1"] != v1["storage_ops"]["k1"] or a1["storage_ops"]["length"] != v1["storage_ops"]["length"]:
        divergences.append(f"[{arm}] Vector 1 storage ops mismatch: k1={a1['storage_ops']['k1']} (expected {v1['storage_ops']['k1']})")
    if a1["selective_macro_under_ferrite"]["sum"] != v1["selective_macro_under_ferrite"]["sum"]:
        divergences.append(f"[{arm}] Vector 1 macro sum mismatch: {a1['selective_macro_under_ferrite']['sum']} != {v1['selective_macro_under_ferrite']['sum']}")
    if a1["selective_macro_under_ferrite"]["selective_used_delta"] < 1:
        divergences.append(f"[{arm}] Vector 1 selective_macro_under_ferrite did not engage: delta={a1['selective_macro_under_ferrite']['selective_used_delta']}")
    if a1["c2me_chunk_and_selector"]["chunk_ops"] != v1["c2me_chunk_and_selector"]["chunk_ops"]:
        divergences.append(f"[{arm}] Vector 1 c2me chunk ops mismatch")

    a2, v2 = arm_data["vector2_mutual_recursion"], v["vector2_mutual_recursion"]
    if a2["trampoline_unwind"]["depth"] != v2["trampoline_unwind"]["depth"] or \
       a2["trampoline_unwind"]["post_increments"] != v2["trampoline_unwind"]["post_increments"]:
        divergences.append(f"[{arm}] Vector 2 trampoline mismatch: post={a2['trampoline_unwind']['post_increments']} (expected {v2['trampoline_unwind']['post_increments']})")
    if a2["mutual_tail_recursion_100"]["depth"] != v2["mutual_tail_recursion_100"]["depth"] or \
       a2["mutual_tail_recursion_100"]["accum"] != v2["mutual_tail_recursion_100"]["accum"] or \
       a2["mutual_tail_recursion_100"]["stored_result"] != v2["mutual_tail_recursion_100"]["stored_result"]:
        divergences.append(f"[{arm}] Vector 2 tail recursion mismatch: accum={a2['mutual_tail_recursion_100']['accum']} (expected {v2['mutual_tail_recursion_100']['accum']})")
    if a2["mutual_macro_recursion_50"]["depth"] != v2["mutual_macro_recursion_50"]["depth"] or \
       a2["mutual_macro_recursion_50"]["accum"] != v2["mutual_macro_recursion_50"]["accum"] or \
       a2["mutual_macro_recursion_50"]["stored_result"] != v2["mutual_macro_recursion_50"]["stored_result"]:
        divergences.append(f"[{arm}] Vector 2 macro recursion mismatch: accum={a2['mutual_macro_recursion_50']['accum']} (expected {v2['mutual_macro_recursion_50']['accum']})")
    return divergences


def _verify_vectors_3_4(arm: str, arm_data: dict, v: dict) -> list[str]:
    divergences: list[str] = []
    a3, v3 = arm_data["vector3_chunk_boundary"], v["vector3_chunk_boundary"]
    if a3["unloaded_boundary"]["score"] != v3["unloaded_boundary"]["score"]:
        divergences.append(f"[{arm}] Vector 3 boundary score mismatch")
    if a3["multi_dimension_traversal"]["steps"] != v3["multi_dimension_traversal"]["steps"]:
        divergences.append(f"[{arm}] Vector 3 multi-dimension steps mismatch")

    a4, v4 = arm_data["vector4_output_suppression"], v["vector4_output_suppression"]
    if a4["feedback_true"]["score"] != v4["feedback_true"]["score"] or \
       a4["feedback_false"]["score"] != v4["feedback_false"]["score"] or \
       a4["store_result_suppressed"]["stored_score"] != v4["store_result_suppressed"]["stored_score"]:
        divergences.append(f"[{arm}] Vector 4 feedback score mismatch")
    if a4["feedback_true"]["response"] != v4["feedback_true"]["response"]:
        divergences.append(f"[{arm}] Vector 4 feedback_true response text divergence: {a4['feedback_true']['response']!r} != {v4['feedback_true']['response']!r}")
    if a4["feedback_false"]["response"] != v4["feedback_false"]["response"]:
        divergences.append(f"[{arm}] Vector 4 feedback_false response text divergence: {a4['feedback_false']['response']!r} != {v4['feedback_false']['response']!r}")
    return divergences


def _verify_exotic_invariants(all_results: dict[str, object]) -> list[str]:
    if "vanilla" not in all_results:
        return ["Vanilla baseline missing from results"]
    v = all_results["vanilla"]
    divergences: list[str] = []

    for arm, arm_data in all_results.items():
        if arm == "vanilla":
            continue
        divergences.extend(_verify_vectors_1_2(arm, arm_data, v))
        divergences.extend(_verify_vectors_3_4(arm, arm_data, v))

    return divergences


def _execute_all_arms(modes: list[str], server_jar: Path) -> dict[str, object]:
    results: dict[str, object] = {}
    for m in modes:
        print(f"\n[>>>] Exotic Red-Team probe arm starting: {m}")
        results[m] = run_in_server_session(
            mode=m,
            server_jar=server_jar,
            runner_fn=lambda c, arm=m: run_exotic_suite(c, arm),
            server_setup_fn=lambda w, rp, sp, arm=m: setup_exotic_server(w, rp, sp, arm),
            log_dir=REPORT_DIR,
        )
        print(f"[<<<] Exotic Red-Team probe arm finished: {m}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exotic Adversarial Red-Team Probe for Minecraft Function Compiler."
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=MODES,
        default=list(MODES),
        help="Server modes to evaluate differentially.",
    )
    args = parser.parse_args()

    server_jar = locate_official_server_jar()
    print(f"[*] Verified official server jar: {server_jar}")

    all_results = _execute_all_arms(args.modes, server_jar)

    report_target = REPORT_DIR / "exotic-redteam-results.json"
    with open(report_target, "w", encoding="utf-8") as stream:
        json.dump(all_results, stream, indent=2)
        stream.write("\n")

    issues = _verify_exotic_invariants(all_results)
    if issues:
        divergence_text = "\n".join(f"  * {issue}" for issue in issues)
        print(f"\n[FAIL] Exotic red-team divergences detected:\n{divergence_text}")
        return 1

    print(f"\n[SUCCESS] Verified differential invariants across {len(all_results)} server arms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
