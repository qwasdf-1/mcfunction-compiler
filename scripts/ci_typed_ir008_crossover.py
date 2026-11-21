#!/usr/bin/env python3
"""IR-008 follow-up: native same-JVM fused-vs-direct ASM CPU crossover.

This is a workload-specific directional comparison, not production promotion.
Within each Minecraft JVM, two *identical* 64-scoreboard-command functions
in separate namespaces run through:
    fc_fused:bench64 -> current existing fused region
    fc_ir:bench64    -> new directly emitted ASM IR region
The 64 original commands and all observed scoreboard results are identical.
A/A uses the same fused function on both sides as a noise sentinel.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import statistics
import subprocess

from ci_smoke_server import ROOT, RUNS, unused_port, wait_for_rcon
from ci_typed_ir008 import find_server_thread, server_cpu_ns, run_function, score

OUT = ROOT / "build/reports/COMPILER-IR-008-CROSSOVER"
MODES = {"fused": "fc_fused:bench64", "asm": "fc_ir:bench64"}
SEED = 8008
BOOTS = 2
REPETITIONS_PER_BOOT = 8
SAME_PATH_CONTROLS = 4
CALLS_PER_WINDOW = 160
WARMUP_PER_PATH = 80
OPERATIONS_PER_CALL = 64


def write_pack(workdir: Path) -> None:
    root = workdir / "world/datapacks/fc_ir008_crossover"
    (root / "pack.mcmeta").parent.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps({
        "pack": {"description": "IR-008 same-VM comparison source",
                 "min_format": [97, 1], "max_format": [97, 1]}
    }) + "\n", encoding="utf-8")
    body = ("scoreboard players add #bench fc_ir 1\n") * OPERATIONS_PER_CALL
    for namespace in ("fc_fused", "fc_ir"):
        folder = root / "data" / namespace / "function"
        folder.mkdir(parents=True)
        (folder / "bench64.mcfunction").write_text(body, encoding="utf-8")


def plan(boot: int) -> tuple[dict, ...]:
    rng = random.Random(SEED + boot)
    blocks = [
        {"contrast": "fused_vs_asm", "order": "ABBA" if i % 2 == 0 else "BAAB"}
        for i in range(REPETITIONS_PER_BOOT)
    ]
    blocks.extend({"contrast": "fused_aa", "order": "ABBA" if i % 2 == 0 else "BAAB"}
                  for i in range(SAME_PATH_CONTROLS))
    rng.shuffle(blocks)
    return tuple(blocks)


def run_boot(boot: int) -> dict:
    RUNS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    work = RUNS / f"ci-ir008-crossover-{boot:02d}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    write_pack(work)
    (work / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(18)
    (work / "server.properties").write_text("\n".join((
        "online-mode=false", "enable-rcon=true", "broadcast-rcon-to-ops=false",
        "level-name=world", "level-type=minecraft:flat",
        "pause-when-empty-seconds=-1", "view-distance=2",
        "simulation-distance=2", "max-tick-time=-1", "max-players=1",
        f"server-port={port}", f"rcon.port={rcon_port}", f"rcon.password={password}",
    )) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE": "true",
        "FC_SCORE_ADD_PROTOTYPE": "true",
        "FC_FUSED_REGION_PROTOTYPE": "true",
        "FC_FUSED_REGION_ONLY_NAMESPACE": "fc_fused",
        "FC_TYPED_IR_MODE": "bytecode",
        "FC_TYPED_IR_NAMESPACE": "fc_ir",
        "FC_TYPED_IR_DIAGNOSTICS": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SCORE_ADD_METRICS": "false",
        "FC_SCORE_ADD_TIMING": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_SCHED_ARCH_COUNTERS": "false",
        "FC_RUNTIME_TRACE": "false",
    })
    command = [
        str(ROOT / "gradlew"), "--no-daemon",
        "-Dorg.gradle.jvmargs=-Xmx1G -Dfile.encoding=UTF-8",
        "-PfcJvmArgs=-Xms512M,-Xmx2G",
        f"-PfcRunDirectory={work.relative_to(ROOT)}", "runServer",
    ]
    report = {"study": "COMPILER-IR-008-CROSSOVER", "boot": boot, "status": "started",
              "seed": SEED + boot, "plan": plan(boot), "blocks": []}
    with (OUT / f"boot-{boot:02d}.server.log").open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=ROOT, env=env,
                                   stdin=subprocess.PIPE,
                                   stdout=output, stderr=subprocess.STDOUT)
        rcon = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=240)
            if "fc_ir008_crossover" not in rcon.command("datapack list enabled"):
                raise AssertionError("Cross-mode same-source pack did not load")
            rcon.command("scoreboard objectives add fc_ir dummy")
            rcon.command("gamerule minecraft:max_command_sequence_length 65536")
            rcon.command("gamerule sendCommandFeedback false")
            # Both function IDs must exist; the fuser and IR namespace gates
            # are disjoint even though every command is byte-for-byte identical.
            status = rcon.command("functioncompiler status")
            if ("fused_region_prototype_enabled=true" not in status
                    or "wrapped=true" not in status):
                raise AssertionError(f"Expected original fuser enabled: {status}")
            fused_status = rcon.command("functioncompiler stats fc_fused:bench64")
            match = re.search(r"fused_regions_compiled=(\d+)", fused_status)
            if not match or int(match.group(1)) < 1:
                raise AssertionError("Original fused backend did not actually compile the control")
            report["original_fused_status"] = fused_status
            report["compiler_status"] = status
            thread = find_server_thread(process.pid)

            for fid in MODES.values():
                for _ in range(WARMUP_PER_PATH):
                    reply = rcon.command("function " + fid)
                    if not reply.startswith("Running function "):
                        raise AssertionError(f"Warmup failed for {fid}: {reply}")

            def window(label: str) -> dict:
                fid = MODES[label]
                rcon.command("scoreboard players set #bench fc_ir 0")
                before = server_cpu_ns(thread)
                for _ in range(CALLS_PER_WINDOW):
                    reply = rcon.command("function " + fid)
                    if not reply.startswith("Running function "):
                        raise AssertionError(f"Window function failed: {reply!r}")
                measured_ns = server_cpu_ns(thread) - before
                measured_score = score(rcon, "#bench")
                if measured_ns <= 0 or measured_score != CALLS_PER_WINDOW * OPERATIONS_PER_CALL:
                    raise AssertionError(
                        f"{label} window had incorrect work or CPU {measured_score} / {measured_ns}")
                return {
                    "arm": label, "function": fid, "cpu_ns": measured_ns,
                    "commands": CALLS_PER_WINDOW * OPERATIONS_PER_CALL,
                    "state_parity": True,
                }

            for i, block in enumerate(report["plan"]):
                arms = {"fused_vs_asm": ("fused", "asm"),
                        "fused_aa": ("fused", "fused")}[block["contrast"]]
                actual = [arms[0] if token == "A" else arms[1] for token in block["order"]]
                samples = [window(arm) for arm in actual]
                a = statistics.mean(s["cpu_ns"] for s, token in zip(samples, block["order"]) if token == "A")
                b = statistics.mean(s["cpu_ns"] for s, token in zip(samples, block["order"]) if token == "B")
                record = {
                    "index": i, **block, "actual_arms": actual, "samples": samples,
                    "a_mean_cpu_ns": a, "b_mean_cpu_ns": b,
                    "b_vs_a_signed_fraction": b / a - 1,
                    "all_work_valid": all(s["state_parity"] for s in samples),
                }
                report["blocks"].append(record)
                (OUT / f"boot-{boot:02d}.json").write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8")
            report["status"] = "accepted"
            print("IR008_CROSSOVER_BOOT " + json.dumps({
                "boot": boot, "fused_vs_asm": [
                    x["b_vs_a_signed_fraction"] for x in report["blocks"]
                    if x["contrast"] == "fused_vs_asm"],
                "fused_aa": [
                    x["b_vs_a_signed_fraction"] for x in report["blocks"]
                    if x["contrast"] == "fused_aa"],
            }, sort_keys=True), flush=True)
        except BaseException as error:
            report["status"] = "invalid"
            report["error"] = repr(error)
            raise
        finally:
            (OUT / f"boot-{boot:02d}.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
            if rcon is not None:
                try:
                    rcon.command("stop")
                except (OSError, RuntimeError):
                    pass
                rcon.close()
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return report


def summarize(boots: list[dict]) -> dict:
    if len(boots) != BOOTS or any(r["status"] != "accepted" for r in boots):
        raise ValueError("Two accepted same-JVM crossover boots required")
    all_ratios = [
        row["b_vs_a_signed_fraction"]
        for boot in boots for row in boot["blocks"]
        if row["contrast"] == "fused_vs_asm"
    ]
    aa = [
        row["b_vs_a_signed_fraction"]
        for boot in boots for row in boot["blocks"]
        if row["contrast"] == "fused_aa"
    ]
    if len(all_ratios) != BOOTS * REPETITIONS_PER_BOOT or len(aa) != BOOTS * SAME_PATH_CONTROLS:
        raise ValueError("Dropped ABBA/BAAB comparison windows")
    return {
        "study": "COMPILER-IR-008-CROSSOVER",
        "status": "accepted_observational",
        "fused_vs_asm_blocks": len(all_ratios),
        "same_path_aa_blocks": len(aa),
        "fused_vs_asm_signed_median_fraction": statistics.median(all_ratios),
        "fused_aa_signed_median_fraction": statistics.median(aa),
        "fused_vs_asm_min_max_fraction": [min(all_ratios), max(all_ratios)],
        "fused_aa_min_max_fraction": [min(aa), max(aa)],
        "both_boot_medians": [
            statistics.median(row["b_vs_a_signed_fraction"]
                              for row in boot["blocks"]
                              if row["contrast"] == "fused_vs_asm")
            for boot in boots
        ],
        "all_windows_exact_state_parity": True,
        "effect_is_causal_or_general": False,
        "production_promotion": False,
        "limitations": [
            "Two fresh JVM boots; window-level pairs in a boot are correlated and are NOT independent servers.",
            "RCON dispatch, game-state updates and JVM warmup remain in Server-thread CPU denominator.",
            "The same-path A/A controls show the resolution/drift, not guaranteed statistical power.",
            "This is a bounded 64-command uniform-score workload and does not establish benefit on real datapacks."
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"study": "COMPILER-IR-008-CROSSOVER", "status": "started", "boots": []}
    try:
        for i in range(BOOTS):
            report["boots"].append(run_boot(i))
            (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        report["summary"] = summarize(report["boots"])
        report["status"] = "accepted"
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR008_CROSSOVER_SUMMARY " + json.dumps(report["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
