#!/usr/bin/env python3
"""COMPILER-IR-010: native per-slot source-value reuse parity and same-JVM CPU A/B.

Semantic arms: native, bytecode without cache, interpreted with cache, and
bytecode with cache; each uses a fresh Minecraft 26.3 Fabric / Java 25 JVM.

CPU followup: two fresh JVMs, identical source and identical compiled ASM
instructions with runtime cache on/off toggles in counterbalanced ABBA blocks.
A/A control blocks compare cache OFF against itself.

All CPU results remain exploratory; no general datapack speedup or production
promotion can be inferred from this microfixture. This file is research-only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import statistics
import subprocess

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir008 import find_server_thread, server_cpu_ns, score

OUT = ROOT / "build/reports/COMPILER-IR-010"
PACK = "fc_typed_ir_010"
OBJ = "fc_ir"
CASES = {
    "repeat": [
        "scoreboard players set #fc_ir010_source fc_ir 7",
        "scoreboard players set #a fc_ir 0",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #b fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
    ],
    "write_invalidated": [
        "scoreboard players set #fc_ir010_source fc_ir 2",
        "scoreboard players set #a fc_ir 0",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players add #fc_ir010_source fc_ir 3",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
    ],
    "observer_invalidated": [
        "scoreboard players set #fc_ir010_source fc_ir 1",
        "scoreboard players set #a fc_ir 0",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        # A TEST-ONLY Scoreboard.onScoreChanged observer increments SOURCE
        # synchronously during this other score's ordinary mutation.
        "scoreboard players add #fc_ir010_trigger fc_ir 1",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
    ],
    "reset_invalidated": [
        "scoreboard players set #fc_ir010_source fc_ir 9",
        "scoreboard players set #a fc_ir 0",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        # Test observer resets SOURCE and exercises onPlayerRemoved.
        "scoreboard players add #fc_ir010_reset fc_ir 1",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
    ],
    "alias_write": [
        "scoreboard players set #fc_ir010_source fc_ir 4",
        "scoreboard players set #a fc_ir 1",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #fc_ir010_source fc_ir += #a fc_ir",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
    ],
    "barrier": [
        "scoreboard players set #fc_ir010_source fc_ir 4",
        "scoreboard players set #a fc_ir 0",
        "scoreboard players set #b fc_ir 0",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
        "function fc_ir:helper",
        "scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir",
    ],
    "helper": [
        "scoreboard players add #fc_ir010_source fc_ir 4",
    ],
    # Two setup commands, 62 identical binary reads, 64 total original lines.
    "bench64": [
        "scoreboard players set #fc_ir010_source fc_ir 7",
        "scoreboard players set #a fc_ir 0",
    ] + ["scoreboard players operation #a fc_ir += #fc_ir010_source fc_ir"] * 62,
}
EXPECTED = {
    "repeat": {"a": 14, "b": 7, "source": 7},
    "write_invalidated": {"a": 12, "b": 0, "source": 5},
    "observer_invalidated": {"a": 13, "b": 0, "source": 6},
    "reset_invalidated": {"a": 9, "b": 0, "source": 0},
    "alias_write": {"a": 23, "b": 0, "source": 9},
    "barrier": {"a": 12, "b": 0, "source": 8},
    "bench64": {"a": 434, "b": 0, "source": 7},
}
SEMANTIC_MODES = ("native", "bytecode_off", "interpreted_cache", "bytecode_cache")
QUOTAS = (1, 2, 3, 4, 5, 6, 7, 8, 10, 16, 32)
SEED = 8010
BOOTS = 2
BLOCKS_PER_BOOT = 6
AA_PER_BOOT = 3
CALLS_PER_WINDOW = 120
WARMUP_CALLS = 60


def make_pack(work: Path) -> None:
    root = work / "world/datapacks" / PACK
    funcs = root / "data/fc_ir/function"
    funcs.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR-010 original-equivalent source fixture",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    for name, commands in CASES.items():
        (funcs / f"{name}.mcfunction").write_text("\n".join(commands) + "\n", encoding="utf-8")


def options(mode: str, crossover: bool = False) -> dict[str, str]:
    cache = mode.endswith("_cache") or crossover
    interpreted = mode.startswith("interpreted")
    compiled = mode != "native"
    return {
        "FC_WRAPPER_PROBE": str(compiled).lower(),
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_TYPED_IR_MODE": ("interpreted" if interpreted else "bytecode") if compiled else "",
        "FC_TYPED_IR_NAMESPACE": "fc_ir" if compiled else "",
        "FC_TYPED_IR_DIAGNOSTICS": str(not crossover).lower(),
        "FC_TYPED_IR_SCORE_CACHE": str(cache).lower(),
        "FC_TYPED_IR_SCORE_CACHE_TOGGLE": str(crossover).lower(),
        # A synthetic scoreboard listener runs equally in ALL semantic arms.
        "FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER": str(not crossover).lower(),
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_RUNTIME_TRACE": "false",
    }


def start(work: Path, mode: str, crossover: bool = False):
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    make_pack(work)
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    port, rcon_port = unused_port(), unused_port()
    passwd = secrets.token_hex(18)
    (work / "server.properties").write_text("\n".join((
        "online-mode=false", "enable-rcon=true",
        "broadcast-rcon-to-ops=false", "level-name=world",
        "level-type=minecraft:flat", "pause-when-empty-seconds=-1",
        "view-distance=2", "simulation-distance=2",
        "max-tick-time=-1", "max-players=1",
        f"server-port={port}", f"rcon.port={rcon_port}",
        f"rcon.password={passwd}",
    )) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(options(mode, crossover))
    command = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}", "runServer",
    ]
    logfile = OUT / f"{work.name}.server.log"
    log = logfile.open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                               stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
    try:
        client = wait_for_rcon(process, rcon_port, passwd, timeout_seconds=240)
        enabled = client.command("datapack list enabled")
        if PACK not in enabled:
            raise AssertionError(f"Datapack not enabled: {enabled!r}")
        client.command("scoreboard objectives add fc_ir dummy")
        client.command("gamerule sendCommandFeedback false")
        client.command("gamerule minecraft:max_command_sequence_length 65536")
        return process, client, log
    except BaseException:
        process.terminate()
        process.wait(timeout=40)
        log.close()
        raise


def stop(process, client, log) -> None:
    try:
        client.command("stop")
    except (OSError, RuntimeError):
        pass
    client.close()
    try:
        process.wait(timeout=40)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=15)
    log.close()


def invoke(client, name: str) -> None:
    result = client.command("function fc_ir:" + name)
    if not result.startswith("Running function "):
        raise AssertionError(f"Failed to execute {name}: {result!r}")


def clear(client) -> None:
    for holder in ("#a", "#b", "#fc_ir010_source",
                   "#fc_ir010_trigger", "#fc_ir010_reset"):
        client.command(f"scoreboard players reset {holder} fc_ir")
    # At the smallest function-command quotas none of the actual function
    # entries may execute. Initialize observable rows *outside* the measured
    # function, rather than allowing RCON score reads to fail on absence.
    for holder in ("#a", "#b", "#fc_ir010_source"):
        client.command(f"scoreboard players set {holder} fc_ir 0")


def snapshot(client) -> dict:
    return {
        "a": score(client, "#a"),
        "b": score(client, "#b"),
        "source": score(client, "#fc_ir010_source"),
    }


def run_semantic_arm(mode: str) -> dict:
    work = RUNS / ("ci-ir010-" + mode)
    report = {"mode": mode, "status": "started", "cases": {},
              "compiler_status": None}
    process, client, log = start(work, mode)
    try:
        for name in EXPECTED:
            clear(client)
            invoke(client, name)
            observed = snapshot(client)
            report["cases"][name] = observed
            if observed != EXPECTED[name]:
                raise AssertionError(f"{mode}/{name} got {observed} != {EXPECTED[name]}")
        for quota in QUOTAS:
            for name in ("repeat", "observer_invalidated",
                         "reset_invalidated", "alias_write"):
                clear(client)
                client.command(
                    f"gamerule minecraft:max_command_sequence_length {quota}")
                invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = snapshot(client)
        status = client.command("functioncompiler ir008")
        report["compiler_status"] = status
        if mode != "native":
            for key in ("compiled_regions", "executed_regions", "binary_steps"):
                import re
                match = re.search(rf"\b{key}=(\d+)", status)
                if not match or int(match.group(1)) <= 0:
                    raise AssertionError(f"IR source not activated: {key} {status!r}")
            if mode != "interpreted_cache" and "bytecode_regions=0" in status:
                raise AssertionError(f"ASM not activated in {mode}: {status!r}")
        if mode.endswith("_cache"):
            import re
            for counter in ("cache_hits", "cache_misses", "cache_invalidations"):
                match = re.search(rf"\b{counter}=(\d+)", status)
                if not match or int(match.group(1)) <= 0:
                    raise AssertionError(f"No real cache {counter} in {mode}: {status!r}")
        else:
            if "cache_hits=0" not in status and mode != "native":
                raise AssertionError(f"Cache unexpectedly enabled in {mode}: {status!r}")
        report["status"] = "accepted"
        print("IR010_SEMANTIC_ARM " + json.dumps({
            "mode": mode, "cases": len(report["cases"]), "status": status
        }, sort_keys=True), flush=True)
        return report
    finally:
        stop(process, client, log)
        (OUT / f"{mode}.json").write_text(json.dumps(report, indent=2) + "\n")


def semantic() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"milestone": "COMPILER-IR-010", "status": "started", "arms": []}
    try:
        for mode in SEMANTIC_MODES:
            result["arms"].append(run_semantic_arm(mode))
            (OUT / "semantic.json").write_text(json.dumps(result, indent=2) + "\n")
        vanilla = result["arms"][0]["cases"]
        for arm in result["arms"]:
            if arm["status"] != "accepted" or arm["cases"] != vanilla:
                raise AssertionError(f"Native parity invalid: {arm['mode']}")
        result["status"] = "accepted"
        result["native_parity"] = True
        result["no_promotion"] = True
    except BaseException as exc:
        result["status"] = "invalid"
        result["error"] = repr(exc)
        raise
    finally:
        (OUT / "semantic.json").write_text(json.dumps(result, indent=2) + "\n")
    print("IR010_SEMANTIC_SUMMARY " + json.dumps({
        "status": result["status"], "cases": len(vanilla),
        "modes": list(SEMANTIC_MODES), "promotion": False
    }, sort_keys=True), flush=True)


def plan(boot: int) -> list[dict]:
    rng = random.Random(SEED + boot)
    blocks = [
        {"kind": "cache_vs_off", "order": "ABBA" if i % 2 == 0 else "BAAB"}
        for i in range(BLOCKS_PER_BOOT)
    ]
    blocks += [
        {"kind": "off_aa", "order": "ABBA" if i % 2 == 0 else "BAAB"}
        for i in range(AA_PER_BOOT)
    ]
    rng.shuffle(blocks)
    return blocks


def run_crossover_boot(boot: int) -> dict:
    work = RUNS / f"ci-ir010-crossover-{boot:02d}"
    report = {"boot": boot, "status": "started", "plan": plan(boot), "blocks": []}
    process, client, log = start(work, "bytecode_cache", crossover=True)
    try:
        status = client.command("functioncompiler ir008")
        if "score_cache=true" not in status or "bytecode_regions=" not in status:
            raise AssertionError(f"IR cache bytecode not activated: {status!r}")
        thread = find_server_thread(process.pid)
        for enabled in ("on", "off"):
            reply = client.command(f"fc_ir010_cache {enabled}")
            if f"cache enabled={str(enabled == 'on').lower()}" not in reply:
                raise AssertionError(f"Cache toggle missing: {reply!r}")
            for _ in range(WARMUP_CALLS):
                invoke(client, "bench64")

        def window(enabled: str) -> dict:
            reply = client.command("fc_ir010_cache " + enabled)
            if f"cache enabled={str(enabled == 'on').lower()}" not in reply:
                raise AssertionError(f"Cache toggle missing in window: {reply!r}")
            begin = server_cpu_ns(thread)
            for _ in range(CALLS_PER_WINDOW):
                invoke(client, "bench64")
            cpu_ns = server_cpu_ns(thread) - begin
            observed = snapshot(client)
            if cpu_ns <= 0 or observed != EXPECTED["bench64"]:
                raise AssertionError(f"Wrong benchmark state: {enabled}: {observed}/{cpu_ns}")
            return {"cache": enabled, "cpu_ns": cpu_ns,
                    "writes": CALLS_PER_WINDOW * 64,
                    "observed": observed, "exact_work": True}

        for i, b in enumerate(report["plan"]):
            labels = ("off", "on") if b["kind"] == "cache_vs_off" else ("off", "off")
            actual = [labels[0] if letter == "A" else labels[1] for letter in b["order"]]
            observations = [window(x) for x in actual]
            a = statistics.mean(x["cpu_ns"] for x, marker in zip(observations, b["order"])
                                if marker == "A")
            bb = statistics.mean(x["cpu_ns"] for x, marker in zip(observations, b["order"])
                                 if marker == "B")
            report["blocks"].append({
                "index": i, **b, "arms": actual, "observations": observations,
                "signed_b_over_a_minus_one": bb / a - 1
            })
            (OUT / f"crossover-{boot:02d}.json").write_text(
                json.dumps(report, indent=2) + "\n")
        report["status"] = "accepted"
        print("IR010_CROSSOVER_BOOT " + json.dumps({
            "boot": boot, "on_vs_off": [
                b["signed_b_over_a_minus_one"] for b in report["blocks"]
                if b["kind"] == "cache_vs_off"
            ], "aa": [
                b["signed_b_over_a_minus_one"] for b in report["blocks"]
                if b["kind"] == "off_aa"
            ]
        }), flush=True)
        return report
    finally:
        stop(process, client, log)
        (OUT / f"crossover-{boot:02d}.json").write_text(
            json.dumps(report, indent=2) + "\n")


def crossover() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"milestone": "COMPILER-IR-010", "status": "started", "boots": []}
    try:
        for boot in range(BOOTS):
            result["boots"].append(run_crossover_boot(boot))
            (OUT / "crossover.json").write_text(json.dumps(result, indent=2) + "\n")
        if len(result["boots"]) != BOOTS or any(
                b["status"] != "accepted" for b in result["boots"]):
            raise AssertionError("Two native JVMs required")
        on = [r["signed_b_over_a_minus_one"] for b in result["boots"]
              for r in b["blocks"] if r["kind"] == "cache_vs_off"]
        aa = [r["signed_b_over_a_minus_one"] for b in result["boots"]
              for r in b["blocks"] if r["kind"] == "off_aa"]
        if len(on) != BOOTS * BLOCKS_PER_BOOT or len(aa) != BOOTS * AA_PER_BOOT:
            raise AssertionError("Missing counterbalanced CPU blocks")
        result["summary"] = {
            "native_benchmark_parity": True, "on_vs_off_blocks": len(on),
            "off_aa_blocks": len(aa),
            "on_vs_off_median_signed_fraction": statistics.median(on),
            "off_aa_median_signed_fraction": statistics.median(aa),
            "per_boot_median": [
                statistics.median(r["signed_b_over_a_minus_one"]
                                  for r in b["blocks"] if r["kind"] == "cache_vs_off")
                for b in result["boots"]
            ],
            "on_min_max": [min(on), max(on)],
            "aa_min_max": [min(aa), max(aa)],
            "causal_general_speedup": False,
            "production_promotion": False,
            "scope": "64 scoreboard instructions, one hot source, 62 binary reads",
            "caution": "windows are correlated within a server; A/A is a noise sentinel",
        }
        result["status"] = "accepted_observational"
    except BaseException as exc:
        result["status"] = "invalid"
        result["error"] = repr(exc)
        raise
    finally:
        (OUT / "crossover.json").write_text(json.dumps(result, indent=2) + "\n")
    print("IR010_CROSSOVER_SUMMARY " + json.dumps(result["summary"], sort_keys=True),
          flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("semantic", "crossover"), required=True)
    phase = parser.parse_args().phase
    if phase == "semantic":
        semantic()
    else:
        crossover()
