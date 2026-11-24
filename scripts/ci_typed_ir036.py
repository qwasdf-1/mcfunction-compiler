#!/usr/bin/env python3
"""IR-036 native semantic validation of actual 3-way structural backend selection.

Four independent Java25/Minecraft26.3 Fabric JVMs run the EXACT same mixed-IR
fixture and quotas. "vanilla", "interpreter", "bytecode" are expected backend
decisions, NOT treatment arms for CPU speedup. No timing is collected.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil

import ci_typed_ir016 as base

OUT = base.ROOT / "build/reports/COMPILER-IR-036"
# Same executable mode for all cost arms; ONLY assumed calls differ.
ARMS = (
    ("original", "native", None),
    ("cost_1", "bytecode", "1"),
    ("cost_8", "bytecode", "8"),
    ("cost_256", "bytecode", "256"),
)
CASES = (
    "ir016_call_chain", "ir016_return", "ir016_store", "ir016_modded",
    "ir016_singleton", "ir016_chunk65", "ir016_chunk66",
    "ir016_missing", "ir016_lifecycle",
)
QUOTAS = (1, 2, 4, 8, 32, 64, 65, 130)


def counter(status: str, key: str) -> int:
    match = re.search(rf"(?:^|\\s){re.escape(key)}=(\\d+)(?=\\s|$)", status)
    if not match:
        raise AssertionError(f"IR-036 missing counter {key}: {status!r}")
    return int(match.group(1))


def run_arm(label: str, mode: str, expected_calls: str | None) -> dict:
    previous_policy = os.environ.get("FC_TYPED_IR_COST_POLICY")
    previous_calls = os.environ.get("FC_TYPED_IR_EXPECTED_CALLS")
    try:
        if expected_calls is not None:
            os.environ["FC_TYPED_IR_COST_POLICY"] = "select"
            os.environ["FC_TYPED_IR_EXPECTED_CALLS"] = expected_calls
        else:
            os.environ.pop("FC_TYPED_IR_COST_POLICY", None)
            os.environ.pop("FC_TYPED_IR_EXPECTED_CALLS", None)
        process, client, log = base.start(mode)
    finally:
        for key, value in (("FC_TYPED_IR_COST_POLICY", previous_policy),
                           ("FC_TYPED_IR_EXPECTED_CALLS", previous_calls)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    report = {"label": label, "mode": mode, "assumed_calls": expected_calls,
              "status": "started", "cases": {}, "ledgers": {},
              "causal_performance_claim": False}
    try:
        for name in CASES:
            base.reset(client)
            base.invoke(client, name)
            observed = base.snapshot(client)
            report["cases"][name] = observed
            for field, expected in base.EXPECTED[name].items():
                if observed[field] != expected:
                    raise AssertionError(
                        f"{label}/{name}/{field}: got {observed[field]}, expected {expected}")
            for quota in QUOTAS:
                base.reset(client)
                client.command(f"gamerule minecraft:max_command_sequence_length {quota}")
                base.invoke(client, name)
                client.command("gamerule minecraft:max_command_sequence_length 65536")
                report["cases"][f"{name}_quota_{quota}"] = base.snapshot(client)

        report["compiler_status"] = client.command("functioncompiler ir008")
        if expected_calls is not None:
            for name in ("ir016_call_chain", "ir016_chunk66", "ir016_return"):
                report["ledgers"][name] = base.inspect_program(client, name)
            info = report["ledgers"]["ir016_call_chain"]
            status = report["compiler_status"]
            if "ir036_cost_policy=true" not in status:
                raise AssertionError(f"{label}: cost policy not active: {status}")
            if label == "cost_1":
                # Three separate two-command regions in this real fixture must
                # revert to exact original actions at one assumed invocation.
                if info["typed_regions"] != 0 or info["opaque_barriers"] != 8:
                    raise AssertionError(f"cost_1 did not retain native command slots: {info}")
                if counter(status, "ir036_cost_native") <= 0:
                    raise AssertionError("cost_1 never selected original queue actions")
            elif label == "cost_8":
                if info["typed_regions"] != 3:
                    raise AssertionError(f"cost_8 did not retain interpreted regions: {info}")
                if counter(status, "ir036_cost_interpreted") <= 0:
                    raise AssertionError("cost_8 never selected typed interpretation")
            elif label == "cost_256":
                if info["typed_regions"] != 3:
                    raise AssertionError(f"cost_256 did not retain bytecode regions: {info}")
                if counter(status, "ir036_cost_bytecode") <= 0:
                    raise AssertionError("cost_256 never selected bytecode")
                if counter(status, "bytecode_regions") <= 0:
                    raise AssertionError("cost_256 failed to emit actual JVM bytecode")

        report["status"] = "accepted"
        print("IR036_ARM " + json.dumps({
            "label": label, "case_count": len(report["cases"]),
            "assumed_calls": expected_calls,
            "cost_native": counter(report["compiler_status"], "ir036_cost_native")
                if expected_calls else 0,
            "cost_interpreted": counter(report["compiler_status"], "ir036_cost_interpreted")
                if expected_calls else 0,
            "cost_bytecode": counter(report["compiler_status"], "ir036_cost_bytecode")
                if expected_calls else 0,
            "call_chain_ledger": report["ledgers"].get("ir016_call_chain"),
        }), flush=True)
        return report
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = repr(error)
        raise
    finally:
        base.stop(process, client, log)
        raw_log = base.OUT / f"{mode}.server.log"
        if raw_log.exists():
            shutil.copy2(raw_log, OUT / f"{label}.server.log")
        (OUT / f"{label}.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"milestone": "COMPILER-IR-036", "status": "started",
              "arms": [], "production_promotion": False,
              "causal_performance_claim": False}
    try:
        for label, mode, expected_calls in ARMS:
            report["arms"].append(run_arm(label, mode, expected_calls))
            (OUT / "results.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8")
        baseline = report["arms"][0]["cases"]
        for arm in report["arms"][1:]:
            if arm["cases"] != baseline:
                bad = [k for k in baseline if arm["cases"].get(k) != baseline[k]]
                raise AssertionError(
                    f"IR-036 backend choice changed Minecraft state for {arm['label']}: "
                    f"{bad[:8]}")
        report["status"] = "accepted"
        report["cases_per_arm"] = len(baseline)
        report["native_semantic_parity"] = True
    except BaseException as error:
        report["status"] = "invalid"
        report["error"] = repr(error)
        raise
    finally:
        (OUT / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IR036_SUMMARY " + json.dumps({
        "status": report["status"],
        "cases_per_arm": report["cases_per_arm"],
        "native_semantic_parity": True,
        "cost_policy": "select (opt-in research only)",
        "causal_performance_claim": False,
        "production_promotion": False,
    }), flush=True)


if __name__ == "__main__":
    main()
