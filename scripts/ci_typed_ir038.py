#!/usr/bin/env python3
"""IR-038: targeted native parity for extended score coverage and read CSE.

Reuse the actual Minecraft IR-017 fixture launcher, RCON, observer, and
snapshot oracle; each arm is a fresh JVM. No timing or CPU claims.
"""
from __future__ import annotations
import json
import os
import ci_typed_ir017 as base

OUT = base.ROOT / "build/reports/COMPILER-IR-038"
ARMS = ("native", "old_bytecode", "interpreted", "bytecode", "direct")
QUOTAS = (1, 2, 3, 4, 5, 8, 16, 64)
NEW = {
    "ir017_ir038_minmax": [
        "scoreboard players set #x fc_ir -7",
        "scoreboard players set #y fc_ir 3",
        "scoreboard players operation #x fc_ir > #y fc_ir",
        "scoreboard players operation #x fc_ir < #y fc_ir",
        "scoreboard players set #y fc_ir -2147483648",
        "scoreboard players operation #x fc_ir < #y fc_ir",
        "scoreboard players set #y fc_ir 2147483647",
        "scoreboard players operation #x fc_ir > #y fc_ir",
        "scoreboard players operation #x fc_ir < #x fc_ir",
    ],
    "ir017_ir038_comparisons": [
        "scoreboard players set #g fc_ir -3",
        "scoreboard players set #y fc_ir 2",
        "execute if score #g fc_ir < #y fc_ir run scoreboard players add #x fc_ir 1",
        "execute if score #g fc_ir <= #y fc_ir run scoreboard players add #x fc_ir 2",
        "execute if score #y fc_ir > #g fc_ir run scoreboard players add #x fc_ir 4",
        "execute if score #y fc_ir >= #g fc_ir run scoreboard players add #x fc_ir 8",
        "execute if score #y fc_ir = #g fc_ir run scoreboard players add #x fc_ir 100",
        "execute unless score #y fc_ir = #g fc_ir run scoreboard players add #x fc_ir 16",
        "execute unless score #y fc_ir > #g fc_ir run scoreboard players add #x fc_ir 100",
        "execute if score #y fc_ir = #y fc_ir run scoreboard players add #x fc_ir 32",
        "execute if score #y fc_ir < #y fc_ir run scoreboard players add #x fc_ir 100",
        "execute unless score #y fc_ir > #y fc_ir run scoreboard players add #x fc_ir 64",
    ],
    "ir017_ir038_missing_rows": [
        "scoreboard players set #x fc_ir 0",
        "execute if score #never fc_guard = #never fc_guard run scoreboard players add #x fc_ir 100",
        "execute unless score #never fc_guard = #never fc_guard run scoreboard players add #x fc_ir 1",
        "execute if score #g fc_guard <= #never fc_guard run scoreboard players add #x fc_ir 100",
        "execute unless score #g fc_guard <= #never fc_guard run scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir017_ir038_distinct": [
        "scoreboard players set #g fc_guard 3",
        "scoreboard players set #y fc_source 5",
        "scoreboard players set #x fc_ir 10",
        "execute if score #g fc_guard < #y fc_source run scoreboard players operation #x fc_ir < #y fc_source",
        "execute if score #g fc_guard < #y fc_source run scoreboard players operation #x fc_ir > #g fc_guard",
        "execute if score #y fc_source = #y fc_source run scoreboard players operation #x fc_ir += #g fc_guard",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir038_guard_binary": [
        "scoreboard players set #g fc_ir 3",
        "scoreboard players set #x fc_ir 4",
        "scoreboard players set #y fc_ir 8",
        "execute if score #g fc_ir < #y fc_ir run scoreboard players operation #x fc_ir > #y fc_ir",
        "execute if score #x fc_ir >= #x fc_ir run scoreboard players operation #x fc_ir < #g fc_ir",
        "execute if score #g fc_ir matches 3 run scoreboard players operation #x fc_ir > #y fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir038_missing_objective": [
        "scoreboard players set #x fc_ir 2",
        "execute if score #g fc_absent = #g fc_ir run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir = #g fc_absent run scoreboard players add #x fc_ir 100",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir017_ir038_callback": [
        "scoreboard players set #ir014_chain fc_ir 1",
        "execute if score #ir014_marker fc_ir >= #g fc_ir run scoreboard players operation #x fc_ir > #ir014_marker fc_ir",
        "execute if score #ir014_marker fc_ir = #ir014_marker fc_ir run scoreboard players add #x fc_ir 3",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir038_barriers": [
        "scoreboard players set #x fc_ir 12",
        "scoreboard players set #y fc_ir 3",
        "scoreboard players operation #x fc_ir /= #y fc_ir",
        "scoreboard players operation #x fc_ir %= #y fc_ir",
        "scoreboard players operation #x fc_ir >< #y fc_ir",
        "scoreboard players add #x fc_ir 1",
        "scoreboard players operation #x fc_ir > #y fc_ir",
    ],
}
EXPECTED = {
    "ir017_ir038_minmax": {"x": 2147483647},
    "ir017_ir038_comparisons": {"x": 127},
    "ir017_ir038_missing_rows": {"x": 7, "never_score": None},
    "ir017_ir038_distinct": {"x": 9},
    "ir017_ir038_guard_binary": {"x": 9},
    "ir017_ir038_missing_objective": {"x": 6},
    "ir017_ir038_callback": {"x": 15, "ir014_marker": 11},
    "ir017_ir038_barriers": {"x": 4},
}
LEGACY = ("ir017_guarded_binary", "ir017_distinct", "ir017_reentrant",
          "ir017_missing_objectives", "ir017_inclusive")
CASES = tuple(NEW) + LEGACY


def stat(status: str, name: str) -> int:
    for field in status.split():
        if field.startswith(name + "="):
            return int(field.split("=", 1)[1])
    raise AssertionError(f"missing diagnostic {name}: {status}")


def run_arm(mode: str) -> dict:
    previous = os.environ.get("FC_TYPED_IR_EXTENDED_SCORE")
    os.environ["FC_TYPED_IR_EXTENDED_SCORE"] = str(mode in ARMS[2:]).lower()
    try:
        process, client, log = base.start(mode)
    finally:
        if previous is None:
            os.environ.pop("FC_TYPED_IR_EXTENDED_SCORE", None)
        else:
            os.environ["FC_TYPED_IR_EXTENDED_SCORE"] = previous
    report = {"mode": mode, "cases": {}, "layouts": {}, "status": "started"}
    try:
        for name in CASES:
            for quota in (65536, *QUOTAS):
                base.reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                base.invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                state = base.snapshot(client)
                report["cases"][f"{name}/{quota}"] = state
                if quota == 65536:
                    for key, expected in EXPECTED.get(name, base.EXPECTED.get(name, {})).items():
                        if state[key] != expected:
                            raise AssertionError(f"{mode}/{name}/{key}: {state[key]} != {expected}")
        if mode != "native":
            for name in NEW:
                report["layouts"][name] = base.inspect(client, name)
            for name in ("ir017_ir038_minmax", "ir017_ir038_comparisons",
                         "ir017_ir038_guard_binary", "ir017_ir038_distinct"):
                typed = report["layouts"][name]["typed_lines"]
                if mode in ARMS[2:] and typed != len(NEW[name]):
                    raise AssertionError(f"{mode}: not all new supported commands lowered: {name}/{typed}")
                if mode == "old_bytecode" and typed == len(NEW[name]):
                    raise AssertionError(f"disabled extension unexpectedly lowered {name}")
            if report["layouts"]["ir017_ir038_barriers"]["opaque_barriers"] < 3:
                raise AssertionError("division, modulo or swap lost its opaque barrier")
            status = client.command("functioncompiler ir008")
            report["diagnostic"] = status
            for key in ("ir038_minmax_steps", "ir038_comparisons", "ir038_comparison_reads_reused"):
                count = stat(status, key)
                if (count > 0) != (mode in ARMS[2:]):
                    raise AssertionError(f"{mode}: unexpected {key}={count}")
            if mode in ("bytecode", "direct") and stat(status, "bytecode_regions") <= 0:
                raise AssertionError("no actual generated JVM code")
            if mode in ARMS[2:] and stat(status, "reentrant_yields") <= 0:
                raise AssertionError("no real callback yield")
        report["status"] = "accepted"
        print("IR038_ARM " + json.dumps({
            "mode": mode, "case_count": len(report["cases"]),
            "diagnostic": report.get("diagnostic"), "layouts": report["layouts"],
        }), flush=True)
        return report
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = repr(exc)
        raise
    finally:
        base.stop(process, client, log)
        (OUT / f"{mode}.json").write_text(json.dumps(report, indent=2) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Use existing audited no-result invocation harness, observer and launcher
    # without changing the historical IR-017 corpus or its default behavior.
    base.OUT = OUT
    base.FUNCTIONS = {**base.FUNCTIONS, **NEW}
    report = {"status": "started", "arms": [], "performance_claim": False,
              "production_promotion": False}
    try:
        for mode in ARMS:
            arm = run_arm(mode)
            report["arms"].append(arm)
            if arm["cases"] != report["arms"][0]["cases"]:
                baseline = report["arms"][0]["cases"]
                bad = [k for k in baseline if arm["cases"].get(k) != baseline[k]]
                raise AssertionError(f"{mode}: native state/quota mismatch in {bad[:8]}")
        report["status"] = "accepted"
        report["native_semantic_parity"] = True
        report["cases_per_arm"] = len(report["arms"][0]["cases"])
    except BaseException as exc:
        report["status"] = "invalid"
        report["error"] = repr(exc)
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR038_SUMMARY " + json.dumps({
        "status": report["status"], "native_semantic_parity": True,
        "cases_per_arm": report["cases_per_arm"], "performance_claim": False,
    }), flush=True)


if __name__ == "__main__":
    main()
