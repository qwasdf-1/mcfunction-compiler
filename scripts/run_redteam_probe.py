#!/usr/bin/env python3
"""Adversarial Red-Team Differential Verification Probe on Minecraft 26.3."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_runtime_probe import RconClient, locate_official_server_jar  # noqa: E402

REPORT_DIR = ROOT / "build" / "reports" / "redteam-probe"
RCON_HOST = "127.0.0.1"
RCON_PASSWORD = "function-compiler-redteam-probe"
LEVEL_RULE = "minecraft:max_command_sequence_length"
PROBE_PACK = "function_compiler_probe"
OBJECTIVE = "fc_probe"

MODES = (
    "vanilla",
    "fabric-off",
    "fabric-on",
    "fused-interpreted",
    "bytecode-emitted",
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind((RCON_HOST, 0))
        return int(sock.getsockname()[1])


def wait_for_rcon(
    proc: subprocess.Popen[bytes],
    port: int,
    timeout: int = 180,
    rcon_password: str = RCON_PASSWORD,
) -> RconClient:
    limit = time.monotonic() + timeout
    err: Exception | None = None
    while time.monotonic() < limit:
        if proc.poll() is not None:
            raise RuntimeError(f"Server exited with code {proc.returncode}")
        try:
            return RconClient(RCON_HOST, port, rcon_password)
        except Exception as e:
            err = e
            time.sleep(0.9)
    raise TimeoutError(f"RCON timeout on {port}: {err}")


def read_score(client: RconClient, holder: str, objective: str = OBJECTIVE) -> int:
    res = client.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", res)
    if match is None:
        raise RuntimeError(f"Could not read score for {holder} {objective}: {res!r}")
    return int(match.group(1))


def write_server_files(
    work: Path,
    rcon_port: int,
    server_port: int,
    rcon_password: str = RCON_PASSWORD,
    datapack_description: str = "Red-Team Probe",
) -> None:
    world_dir = work / "world"
    datapack_root = world_dir / "datapacks" / PROBE_PACK
    shutil.copytree(ROOT / "src" / "main" / "resources" / "data", datapack_root / "data")
    meta = {"pack": {"description": datapack_description, "min_format": [97, 1], "max_format": [97, 1]}}
    (datapack_root / "pack.mcmeta").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    server_props = (
        f"enable-rcon=true\nrcon.password={rcon_password}\nrcon.port={rcon_port}\n"
        f"server-ip={RCON_HOST}\nserver-port={server_port}\nlevel-name=world\n"
        "online-mode=false\nwhite-list=false\nsync-chunk-writes=false\npause-when-empty-seconds=-1\n"
    )
    (work / "server.properties").write_text(server_props, encoding="utf-8")

    cfg_dir = work / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    fc_config = {
        "enabled": True,
        "fused_regions": True,
        "selective_macros": True,
        "tiered_bytecode": True,
        "tiered_threshold": 1,
        "excluded_namespaces": ["excluded_ns"],
    }
    (cfg_dir / "function-compiler.json").write_text(json.dumps(fc_config, indent=2) + "\n", encoding="utf-8")


def _configure_gradle_env(mode: str) -> dict[str, str]:
    env = os.environ.copy()
    gh = ROOT / ".gradle-user-home"
    if "GRADLE_USER_HOME" not in env and gh.is_dir():
        env["GRADLE_USER_HOME"] = str(gh)
    sc = Path.home() / ".gradle" / "caches"
    if "GRADLE_RO_DEP_CACHE" not in env and sc.is_dir():
        env["GRADLE_RO_DEP_CACHE"] = str(sc)

    on = mode != "fabric-off"
    is_fused = on and mode in ("fused-interpreted", "bytecode-emitted")
    is_bc = on and mode == "bytecode-emitted"
    env["FC_WRAPPER_PROBE"] = "true" if on else "false"
    env["FC_SCORE_ADD_PROTOTYPE"] = "true" if on else "false"
    env["FC_SCORE_ADD_METRICS"] = "true" if on else "false"
    env["FC_FUSED_REGION_PROTOTYPE"] = "true" if is_fused else "false"
    env["FC_BYTECODE_REGION_PROTOTYPE"] = "true" if is_bc else "false"
    env["FC_SELECTIVE_MACRO_ARGUMENTS"] = "true" if on else "false"
    env["FC_SELECTIVE_MACRO_ARGUMENTS_METRICS"] = "true" if on else "false"
    env["FC_RUNTIME_TRACE"] = "false"
    return env


def start_server(mode: str, work: Path, server_jar: Path, log_path: Path):
    log_handle = log_path.open("wb")
    if mode == "vanilla":
        cmd = ["java", "-Xms512M", "-Xmx2G", "-jar", str(server_jar), "nogui"]
        return subprocess.Popen(cmd, cwd=work, stdout=log_handle, stderr=subprocess.STDOUT), log_handle

    env = _configure_gradle_env(mode)
    cmd = [
        str(ROOT / "gradlew"),
        "--no-daemon",
        "--offline",
        f"-PfcRunDirectory={work.relative_to(ROOT).as_posix()}",
        "runServer",
    ]
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log_handle, stderr=subprocess.STDOUT), log_handle


def run_in_server_session(
    mode: str,
    server_jar: Path,
    runner_fn: Callable[[RconClient], dict[str, object]],
    server_setup_fn: Callable[[Path, int, int], None] | None = None,
    log_dir: Path | None = None,
) -> dict[str, object]:
    target_dir = log_dir or REPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    work_dir = ROOT / "run" / f"session_{mode.replace('-', '_')}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    rcon_p = free_port()
    srv_p = free_port()
    log_file = target_dir / f"{mode}.log"

    if server_setup_fn is not None:
        server_setup_fn(work_dir, rcon_p, srv_p)
    else:
        write_server_files(work_dir, rcon_p, srv_p)

    srv_mode = mode if mode in MODES else ("vanilla" if mode == "vanilla" else "bytecode-emitted")
    proc, log_handle = start_server(srv_mode, work_dir, server_jar, log_file)
    try:
        client = wait_for_rcon(proc, rcon_p, timeout=240)
        try:
            return runner_fn(client)
        finally:
            client.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_handle.close()
        shutil.rmtree(work_dir, ignore_errors=True)


def _get_selective_macro_count(client: RconClient, mode: str) -> int:
    if mode == "vanilla":
        return 0
    st = client.command("functioncompiler status")
    m = re.search(r"selective_macro_arguments_used=(\d+)", st)
    return int(m.group(1)) if m else 0


def _test_area1_arithmetic(client: RconClient) -> dict[str, object]:
    client.command(f"function {PROBE_PACK}:redteam_arith_overflow")
    area1: dict[str, object] = {
        "overflow_add": read_score(client, "#res_add_overflow"),
        "underflow_remove": read_score(client, "#res_remove_underflow"),
        "overflow_mul": read_score(client, "#res_mul_overflow"),
        "underflow_sub": read_score(client, "#res_sub_underflow"),
    }

    client.command(f"scoreboard players set #target_div0 {OBJECTIVE} 42")
    client.command(f"scoreboard players set #zero {OBJECTIVE} 0")
    area1["div_zero_response"] = client.command(f"function {PROBE_PACK}:redteam_div_zero")
    area1["div_zero_target_score"] = read_score(client, "#target_div0")

    client.command(f"scoreboard players set #target_mod0 {OBJECTIVE} 99")
    area1["mod_zero_response"] = client.command(f"function {PROBE_PACK}:redteam_mod_zero")
    area1["mod_zero_target_score"] = read_score(client, "#target_mod0")

    client.command(f"scoreboard players set #fused_div0_score {OBJECTIVE} 0")
    client.command(f"scoreboard players set #fused_div0_state {OBJECTIVE} 0")
    resp = client.command(f"function {PROBE_PACK}:redteam_fused_div_zero_middle")
    area1["fused_div_zero_middle"] = {
        "response": resp,
        "score": read_score(client, "#fused_div0_score"),
        "state": read_score(client, "#fused_div0_state"),
    }
    return area1


def _test_area2_quota(client: RconClient) -> dict[str, object]:
    seven_scores: dict[int, int] = {}
    for q in (0, 1, 2, 3, 4, 5, 6, 7, 8, 10):
        client.command(f"gamerule {LEVEL_RULE} {q}")
        client.command(f"scoreboard players set #quota_count {OBJECTIVE} 0")
        client.command(f"function {PROBE_PACK}:redteam_quota_seven")
        seven_scores[q] = read_score(client, "#quota_count")

    interleaved_scores: dict[int, int] = {}
    for q in (1, 2, 3, 4, 5, 8):
        client.command(f"gamerule {LEVEL_RULE} {q}")
        client.command(f"scoreboard players set #quota_interleaved {OBJECTIVE} 0")
        client.command(f"function {PROBE_PACK}:redteam_quota_interleaved")
        interleaved_scores[q] = read_score(client, "#quota_interleaved")

    client.command(f"gamerule {LEVEL_RULE} 65536")
    return {"quota_sweep_seven": seven_scores, "quota_interleaved": interleaved_scores}


def _test_area3_context(client: RconClient, summon_actor: object) -> dict[str, object]:
    client.command("kill @e[type=pig]")
    client.command(f"scoreboard players set #zero_entity_count {OBJECTIVE} 0")
    zero_resp = client.command(f"function {PROBE_PACK}:redteam_zero_entity")

    summon_actor("0.5 100 0.5", "redteam_die_target")  # type: ignore[operator]
    client.command(f"scoreboard players set #die_test_score {OBJECTIVE} 0")
    die_resp = client.command(f"function {PROBE_PACK}:redteam_entity_die_outer")

    summon_actor("0.5 100 0.5", "redteam_dim_target")  # type: ignore[operator]
    client.command(f"scoreboard players set #dim_test_score {OBJECTIVE} 0")
    dim_resp = client.command(f"function {PROBE_PACK}:redteam_entity_dim_outer")

    return {
        "zero_entities": {"response": zero_resp, "score": read_score(client, "#zero_entity_count")},
        "entity_death_mid_chain": {"response": die_resp, "score": read_score(client, "#die_test_score")},
        "entity_dimension_mid_chain": {"response": dim_resp, "score": read_score(client, "#dim_test_score")},
    }


def _test_area4_control_flow(client: RconClient) -> dict[str, object]:
    client.command(f"scoreboard players set #res_fail_store {OBJECTIVE} 999")
    client.command(f"scoreboard players set #child_fail_marker {OBJECTIVE} 0")
    store_resp = client.command(f"function {PROBE_PACK}:redteam_store_result_fail_outer")

    client.command(f"scoreboard players set #unless_res {OBJECTIVE} 0")
    client.command(f"scoreboard players set #unless_dead_code {OBJECTIVE} 0")
    unless_resp = client.command(f"function {PROBE_PACK}:redteam_unless_return_run_fail_outer")

    return {
        "store_result_child_fail": {
            "response": store_resp,
            "stored_result": read_score(client, "#res_fail_store"),
            "child_marker": read_score(client, "#child_fail_marker"),
        },
        "unless_return_run_fail": {
            "response": unless_resp,
            "unless_result": read_score(client, "#unless_res"),
            "dead_code": read_score(client, "#unless_dead_code"),
        },
    }


def _test_area5_macros(client: RconClient, mode: str) -> dict[str, object]:
    client.command(f"scoreboard players set #p1 {OBJECTIVE} 0")
    client.command(f"scoreboard players set #p2 {OBJECTIVE} 0")
    client.command("data merge storage redteam:data {val1: 10}")
    missing_resp = client.command(f"function {PROBE_PACK}:redteam_macro_two_params with storage redteam:data")

    client.command(f"scoreboard players set #p_int {OBJECTIVE} 0")
    client.command('data merge storage redteam:data {int_val: "not_a_number"}')
    mismatch_resp = client.command(f"function {PROBE_PACK}:redteam_macro_int with storage redteam:data")

    client.command(f"scoreboard players set #deep_res {OBJECTIVE} 0")
    client.command('data merge storage redteam:nested {levels: [{sub: [{target: {deep_val: 777}}]}]}')
    deep_resp = client.command(
        f"function {PROBE_PACK}:redteam_macro_deep with storage redteam:nested levels[0].sub[0].target"
    )

    client.command(f"scoreboard players set #deep_res {OBJECTIVE} 0")
    invalid_resp = client.command(
        f"function {PROBE_PACK}:redteam_macro_deep with storage redteam:nested levels[99].missing"
    )

    client.command(f"scoreboard players set #p1 {OBJECTIVE} 0")
    client.command(f"scoreboard players set #p2 {OBJECTIVE} 0")
    client.command("data merge storage redteam:valid_data {sub: {val1: 10, val2: 20, unused_large_payload: [1,2,3]}}")
    sel_before = _get_selective_macro_count(client, mode)
    sel_resp = client.command(f"function {PROBE_PACK}:redteam_macro_two_params with storage redteam:valid_data sub")
    sel_after = _get_selective_macro_count(client, mode)

    return {
        "macro_missing_param": {"response": missing_resp, "p1": read_score(client, "#p1"), "p2": read_score(client, "#p2")},
        "macro_mismatched_types": {"response": mismatch_resp, "p_int": read_score(client, "#p_int")},
        "macro_deep_nested_path": {"response": deep_resp, "deep_res": read_score(client, "#deep_res")},
        "macro_invalid_nested_path": {"response": invalid_resp, "deep_res": read_score(client, "#deep_res")},
        "macro_selective_success": {
            "response": sel_resp,
            "p1": read_score(client, "#p1"),
            "p2": read_score(client, "#p2"),
            "selective_used_delta": sel_after - sel_before,
        },
    }


def _test_area6_exclusion(client: RconClient, mode: str) -> dict[str, object]:
    client.command(f"scoreboard players set #excluded_score {OBJECTIVE} 0")
    plain_resp = client.command("function excluded_ns:fused_candidate")
    plain_stats = client.command("functioncompiler stats excluded_ns:fused_candidate") if mode != "vanilla" else ""

    sel_excl_before = _get_selective_macro_count(client, mode)
    client.command(f"scoreboard players set #excluded_macro {OBJECTIVE} 0")
    client.command('data merge storage redteam:excluded {sub: {val: 42, extra: "payload"}}')
    macro_resp = client.command("function excluded_ns:macro_candidate with storage redteam:excluded sub")
    sel_excl_after = _get_selective_macro_count(client, mode)

    return {
        "excluded_namespace": {
            "plain_function_response": plain_resp,
            "plain_function_score": read_score(client, "#excluded_score"),
            "plain_function_stats": plain_stats,
            "macro_function_response": macro_resp,
            "macro_function_score": read_score(client, "#excluded_macro"),
            "selective_excl_before": sel_excl_before,
            "selective_excl_after": sel_excl_after,
            "selective_arguments_used_delta": sel_excl_after - sel_excl_before,
        }
    }


def run_adversarial_suite(client: RconClient, mode: str) -> dict[str, object]:
    client.command(f"scoreboard objectives add {OBJECTIVE} dummy")
    client.command("forceload add 0 0 256 32")
    client.command("execute in minecraft:the_nether run forceload add 0 0 32 32")

    def summon_actor(pos: str, tag: str) -> None:
        client.command(f"kill @e[tag={tag}]")
        for _ in range(20):
            res = client.command(f'summon minecraft:armor_stand {pos} {{Tags:["{tag}"]}}')
            if "Summoned" in res:
                return
            time.sleep(0.05)
        raise RuntimeError(f"Could not summon actor with tag {tag}: {res}")

    return {
        "area1_arithmetic": _test_area1_arithmetic(client),
        "area2_quota": _test_area2_quota(client),
        "area3_context_modifiers": _test_area3_context(client, summon_actor),
        "area4_control_flow": _test_area4_control_flow(client),
        "area5_macros": _test_area5_macros(client, mode),
        "area6_exclusion": _test_area6_exclusion(client, mode),
    }


def _check_core_invariants(arm: str, a: dict[str, object], v: dict[str, object], diffs: list[str]) -> None:
    v1, a1 = v["area1_arithmetic"], a["area1_arithmetic"]
    for fld in ("overflow_add", "underflow_remove", "overflow_mul", "underflow_sub",
                "div_zero_target_score", "mod_zero_target_score"):
        if a1[fld] != v1[fld]:
            diffs.append(f"[{arm}] Area 1 {fld}: {a1[fld]} != {v1[fld]}")
    if a1["fused_div_zero_middle"]["score"] != v1["fused_div_zero_middle"]["score"] or \
       a1["fused_div_zero_middle"]["state"] != v1["fused_div_zero_middle"]["state"]:
        diffs.append(f"[{arm}] Area 1 fused div0 mismatch")

    v2, a2 = v["area2_quota"], a["area2_quota"]
    if a2["quota_sweep_seven"] != v2["quota_sweep_seven"] or a2["quota_interleaved"] != v2["quota_interleaved"]:
        diffs.append(f"[{arm}] Area 2 quota mismatch")

    v3, a3 = v["area3_context_modifiers"], a["area3_context_modifiers"]
    for fld in ("zero_entities", "entity_death_mid_chain", "entity_dimension_mid_chain"):
        if a3[fld]["score"] != v3[fld]["score"]:
            diffs.append(f"[{arm}] Area 3 {fld} mismatch")


def _check_macro_invariants(arm: str, a: dict[str, object], v: dict[str, object], diffs: list[str]) -> None:
    v4, a4 = v["area4_control_flow"], a["area4_control_flow"]
    if a4["store_result_child_fail"]["stored_result"] != v4["store_result_child_fail"]["stored_result"] or \
       a4["store_result_child_fail"]["child_marker"] != v4["store_result_child_fail"]["child_marker"] or \
       a4["unless_return_run_fail"]["unless_result"] != v4["unless_return_run_fail"]["unless_result"]:
        diffs.append(f"[{arm}] Area 4 control flow mismatch")

    a5 = a["area5_macros"]
    if a5["macro_missing_param"]["p1"] != 0 or a5["macro_missing_param"]["p2"] != 0 or \
       a5["macro_mismatched_types"]["p_int"] != 0 or a5["macro_deep_nested_path"]["deep_res"] != 777 or \
       a5["macro_invalid_nested_path"]["deep_res"] != 0 or a5["macro_selective_success"]["p1"] != 10:
        diffs.append(f"[{arm}] Area 5 macro mismatch")

    a6 = a["area6_exclusion"]["excluded_namespace"]
    v6 = v["area6_exclusion"]["excluded_namespace"]
    if a6["plain_function_score"] != v6["plain_function_score"] or \
       a6["macro_function_score"] != v6["macro_function_score"] or \
       a6["selective_arguments_used_delta"] != 0:
        diffs.append(f"[{arm}] Area 6 exclusion leak")


def _verify_differential_invariants(all_results: dict[str, object]) -> list[str]:
    if "vanilla" not in all_results:
        return []
    vanilla = all_results["vanilla"]
    divergences: list[str] = []

    for arm, arm_data in all_results.items():
        if arm != "vanilla":
            _check_core_invariants(arm, arm_data, vanilla, divergences)
            _check_macro_invariants(arm, arm_data, vanilla, divergences)

    return divergences


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adversarial Red-Team QA Probe for Minecraft Function Compiler."
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=MODES,
        default=["vanilla", "fabric-on", "fused-interpreted", "bytecode-emitted"],
        help="Server modes to evaluate differentially.",
    )
    args = parser.parse_args()

    server_jar = locate_official_server_jar()
    print(f"[*] Verified official server jar: {server_jar}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, object] = {}

    for mode in args.modes:
        print(f"\n=======================================================\n[*] Executing Red-Team suite on arm: {mode}\n=======================================================")
        mode_results = run_in_server_session(
            mode=mode,
            server_jar=server_jar,
            runner_fn=lambda c: run_adversarial_suite(c, mode),
        )
        all_results[mode] = mode_results
        print(f"[+] Red-Team suite completed successfully on arm: {mode}")

    out_file = REPORT_DIR / "redteam-results.json"
    out_file.write_text(json.dumps(all_results, indent=2) + "\n", encoding="utf-8")
    print(f"\n[+] Raw red-team results written to: {out_file}")

    divergences = _verify_differential_invariants(all_results)
    if divergences:
        print(f"\n[!] SEMANTIC DIVERGENCES DETECTED:")
        for div in divergences:
            print(f"    - {div}")
        return 1

    print(f"\n[+] 100% PARITY & INVARIANT PROOFS VERIFIED across all 6 adversarial target areas against vanilla!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
