#!/usr/bin/env python3
"""IR-039 compound-predicate native differential. No CPU timing."""
from __future__ import annotations
import json
import ci_typed_ir017 as base
import ci_typed_ir038 as extended

OUT = base.ROOT / "build/reports/COMPILER-IR-039"
ARMS = ("native", "old_bytecode", "interpreted", "bytecode", "direct")
QUOTAS = (*range(1, 41), 48)
NEW = {
    "ir017_ir039_repeat": [
        "scoreboard players set #g fc_ir 3",
        "scoreboard players set #y fc_ir 5",
        "execute if score #g fc_ir matches 1.. if score #g fc_ir < #y fc_ir if score #g fc_ir matches 1.. if score #g fc_ir < #y fc_ir run scoreboard players add #x fc_ir 10",
        "execute if score #g fc_ir matches 3 unless score #g fc_ir matches 3 run scoreboard players add #x fc_ir 100",
        "execute unless score #g fc_ir = #y fc_ir unless score #g fc_ir = #y fc_ir run scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir039_order": [
        "scoreboard players set #g fc_ir 4",
        "execute if score #g fc_ir matches 0 if score #g fc_ir matches 4 run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 4 unless score #g fc_ir matches 4 if score #g fc_ir matches 4 run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 4 if score #g fc_ir matches 4 run scoreboard players add #x fc_ir 3",
        "scoreboard players set #g fc_ir 1",
        "execute if score #g fc_ir matches 4 if score #g fc_ir matches 4 run scoreboard players add #x fc_ir 100",
        "scoreboard players add #x fc_ir 2",
    ],
    # Eight stages, failure at first, middle, last, and an all-pass chain.
    # Exact marker progression distinguishes each terminal from the suffix.
    "ir017_ir039_empty_suffix": [
        "scoreboard players set #g fc_ir 1",
        "execute " + " ".join(["if score #g fc_ir matches 0"] +
            ["if score #g fc_ir matches 1"] * 7) + " run scoreboard players add #x fc_ir 100",
        "scoreboard players add #x fc_ir 1",
        "execute " + " ".join(["if score #g fc_ir matches 1"] * 3 +
            ["unless score #g fc_ir matches 1"] + ["if score #g fc_ir matches 1"] * 4) +
            " run scoreboard players add #x fc_ir 100",
        "scoreboard players add #x fc_ir 2",
        "execute " + " ".join(["if score #g fc_ir matches 1"] * 7 +
            ["unless score #g fc_ir matches 1"]) + " run scoreboard players add #x fc_ir 100",
        "scoreboard players add #x fc_ir 4",
        "execute " + " ".join(["if score #g fc_ir matches 1"] * 8) +
            " run scoreboard players add #x fc_ir 8",
        "scoreboard players add #x fc_ir 16",
    ],
    "ir017_ir039_missing_rows": [
        "scoreboard players set #x fc_ir 0",
        "execute unless score #never fc_guard = #never fc_guard unless score #never fc_guard = #never fc_guard run scoreboard players add #x fc_ir 2",
        "execute if score #never fc_guard = #never fc_guard if score #g fc_ir matches 0 run scoreboard players add #x fc_ir 100",
        "execute unless score #never fc_guard matches 0 unless score #never fc_guard matches 0 run scoreboard players add #x fc_ir 4",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir039_missing_objective": [
        "scoreboard players set #x fc_ir 1",
        "execute if score #g fc_ir matches 5 if score #g fc_absent matches 0 run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 0 if score #g fc_absent matches 0 run scoreboard players add #x fc_ir 100",
        "execute if score #g fc_ir matches 0 if score #g fc_ir matches 0 run scoreboard players add #m fc_absent 1",
        "execute if score #g fc_ir matches 0 if score #g fc_ir matches 0 run scoreboard players add #x fc_ir 2",
        "scoreboard players add #x fc_ir 4",
    ],
    "ir017_ir039_binary": [
        "scoreboard players set #g fc_guard 3",
        "scoreboard players set #y fc_source 5",
        "scoreboard players set #x fc_ir 10",
        "execute if score #g fc_guard < #y fc_source if score #g fc_guard < #y fc_source run scoreboard players operation #x fc_ir < #y fc_source",
        "execute if score #g fc_guard matches 3 if score #x fc_ir >= #g fc_guard run scoreboard players operation #x fc_ir += #g fc_guard",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir039_self": [
        "scoreboard players set @s fc_ir 3",
        "scoreboard players set #g fc_ir 5",
        "execute if score @s fc_ir = @s fc_ir if score @s fc_ir = @s fc_ir if score @s fc_ir < #g fc_ir run scoreboard players operation @s fc_ir += #g fc_ir",
        "execute if score @s fc_ir > #g fc_ir unless score #g fc_ir = @s fc_ir if score @s fc_ir > #g fc_ir run scoreboard players add #x fc_ir 2",
        "execute if score @s fc_ir matches 8 if score @s fc_ir matches 8 run scoreboard players operation #x fc_ir += @s fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir039_self_absent": [
        "scoreboard players set #g fc_ir 1",
        "execute unless score @s fc_source = @s fc_source unless score @s fc_source = @s fc_source run scoreboard players add #x fc_ir 2",
        "scoreboard players set @s fc_source 7",
        "execute if score @s fc_source = @s fc_source if score @s fc_source = @s fc_source run scoreboard players operation #x fc_ir += @s fc_source",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir039_reentrant": [
        "scoreboard players set #ir014_chain fc_ir 1",
        "execute if score #ir014_marker fc_ir matches 11 if score #ir014_marker fc_ir matches 11 run scoreboard players add #x fc_ir 2",
        "execute if score #ir014_marker fc_ir >= #g fc_ir if score #ir014_marker fc_ir >= #g fc_ir run scoreboard players operation #x fc_ir += #ir014_marker fc_ir",
        "scoreboard players add #x fc_ir 1",
    ],
    "ir017_ir039_barrier": [
        "scoreboard players set #g fc_ir 1",
        "scoreboard players add #x fc_ir 1",
        "execute if score #g fc_ir matches 1 positioned 0 64 0 if score #g fc_ir matches 1 run scoreboard players add #x fc_ir 2",
        "execute if score #g fc_ir matches 1 if score #g fc_ir matches 1 run scoreboard players add #x fc_ir 4",
        "scoreboard players add #x fc_ir 1",
    ],
}
EXPECTED = {
    "ir017_ir039_repeat": 13, "ir017_ir039_order": 5,
    "ir017_ir039_empty_suffix": 31,
    "ir017_ir039_missing_rows": 7, "ir017_ir039_missing_objective": 7,
    "ir017_ir039_binary": 9, "ir017_ir039_self": 11,
    "ir017_ir039_self_absent": 10, "ir017_ir039_reentrant": 14,
    "ir017_ir039_barrier": 8,
}
SELF = {"ir017_ir039_self", "ir017_ir039_self_absent"}
LEGACY = ("ir017_guarded_binary", "ir017_reentrant",
          "ir017_ir038_comparisons", "ir017_ir038_guard_binary")
CASES = tuple(NEW) + LEGACY
original_options = base.options


def options(mode):
    flags = original_options(mode)
    compiled = mode != "native"
    flags.update({
        "FC_TYPED_IR_COMPOUND_SCORE": str(mode in ARMS[2:]).lower(),
        "FC_TYPED_IR_EXTENDED_SCORE": str(compiled).lower(),
        "FC_TYPED_IR_RANGE_GUARDS": str(compiled).lower(),
        "FC_TYPED_IR_SELF_HOLDER": str(compiled).lower(),
    })
    return flags


def invoke(client, name, as_entity):
    prefix = "execute positioned 0 64 0 summon minecraft:armor_stand run " if as_entity else ""
    response = client.command(prefix + "fc_ir017_call fc_ir:" + name)
    if (not as_entity and "FC_ARCH_CALL queued" not in response) or (
            as_entity and ("invalid or disallowed" in response or "no execution context" in response)):
        raise AssertionError(f"{name}/{as_entity}: {response!r}")


def run_arm(mode):
    process, client, log = base.start(mode)
    report = {"mode": mode, "status": "started", "cases": {}, "layouts": {}}
    try:
        client.command("forceload add 0 0")
        client.command("setblock 0 63 0 minecraft:stone")
        for name in CASES:
            for as_entity in ((True, False) if name in SELF else (False,)):
                for quota in (65536, *QUOTAS):
                    base.reset(client)
                    client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                    invoke(client, name, as_entity)
                    client.command("gamerule minecraft:max_command_sequence_length 65536")
                    state = base.snapshot(client)
                    report["cases"][f"{name}/{as_entity}/{quota}"] = state
                    if quota == 65536 and (as_entity or name not in SELF):
                        expected = EXPECTED.get(name, extended.EXPECTED.get(name, base.EXPECTED.get(name, {})).get("x"))
                        if expected is not None and state["x"] != expected:
                            raise AssertionError(f"{mode}/{name}: expected x={expected}; got {state}")
                    # Archived failure: before the fix the interpreter spent
                    # too little quota and reached the final +2 at quota 12.
                    if name == "ir017_ir039_order" and quota == 12 and state["x"] != 3:
                        raise AssertionError(f"{mode}: original IR039 quota regression: {state}")
                    if name == "ir017_ir039_missing_rows" and state["never_score"] is not None:
                        raise AssertionError("predicate reads created missing row")
        if mode != "native":
            for name in NEW:
                report["layouts"][name] = base.inspect(client, name)
            for name in ("ir017_ir039_repeat", "ir017_ir039_order", "ir017_ir039_empty_suffix", "ir017_ir039_binary",
                         "ir017_ir039_self", "ir017_ir039_self_absent"):
                actual = report["layouts"][name]["typed_lines"]
                if mode in ARMS[2:] and actual != len(NEW[name]):
                    raise AssertionError(f"{mode}: incomplete typed coverage {name}: {actual}")
                if mode == "old_bytecode" and actual == len(NEW[name]):
                    raise AssertionError("disabled compound control admitted compound")
            if report["layouts"]["ir017_ir039_barrier"]["opaque_barriers"] < 1:
                raise AssertionError("unsupported context modifier not opaque")
            status = client.command("functioncompiler ir008")
            report["diagnostic"] = status
            for key in ("ir039_stages", "ir039_reused", "ir039_short_circuits",
                        "ir039_native_fallbacks", "ir039_empty_stage_debits"):
                if (extended.stat(status, key) > 0) != (mode in ARMS[2:]):
                    raise AssertionError(f"{mode}: unexpected {key}: {status}")
            if mode in ("bytecode", "direct") and extended.stat(status, "bytecode_regions") <= 0:
                raise AssertionError("no bytecode regions")
        report["status"] = "accepted"
        print("IR039_ARM " + json.dumps({
            "mode": mode, "cases": len(report["cases"]),
            "diagnostic": report.get("diagnostic"), "layouts": report["layouts"],
        }), flush=True)
        return report
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        base.stop(process, client, log)
        (OUT / f"{mode}.json").write_text(json.dumps(report, indent=2) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base.OUT = OUT
    base.FUNCTIONS = {**base.FUNCTIONS, **extended.NEW, **NEW}
    base.options = options
    report = {"status": "started", "arms": [], "performance_claim": False,
              "production_promotion": False}
    try:
        for mode in ARMS:
            arm = run_arm(mode)
            report["arms"].append(arm)
            baseline = report["arms"][0]["cases"]
            bad = [k for k in baseline if arm["cases"].get(k) != baseline[k]]
            arm["differences"] = {k: {"native": baseline[k], "actual": arm["cases"].get(k)}
                                  for k in bad}
        failures = {arm["mode"]: len(arm["differences"]) for arm in report["arms"]
                    if arm["differences"]}
        if failures:
            raise AssertionError(f"native parity differences: {failures}")
        report.update(status="accepted", native_semantic_parity=True,
                      cases_per_arm=len(report["arms"][0]["cases"]))
    except BaseException as error:
        report.update(status="invalid", error=repr(error))
        raise
    finally:
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("IR039_SUMMARY " + json.dumps({
        "status": report["status"], "native_semantic_parity": True,
        "cases_per_arm": report["cases_per_arm"], "performance_claim": False
    }), flush=True)


if __name__ == "__main__":
    main()
