#!/usr/bin/env python3
"""IR-013: native CPU screen of guarded direct function scheduling.

Reuse the accepted IR-012 same-generated-ASM, same-JVM ABBA/BAAB / A/A
methodology. Both ON and OFF direct scheduling arms have the *same*
IR-013 reentrant queue epoch guard enabled. No synthetic callback is active
during timing, so this measures the common no-reentrancy fast path.

This is a bounded observational screen, not a guard-on/off causal estimate.
The effect size of the guard itself cannot be isolated without a separate
within-JVM control; neither this study nor IR-012 establishes promotion.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import ci_typed_ir012 as baseline
from ci_smoke_server import ROOT

OUT = ROOT / "build/reports/COMPILER-IR-013-GUARDED-CPU"


def main() -> None:
    # These pass through to both actual Minecraft JVM subprocesses because
    # ci_typed_ir012.options() does not override either flag. We never enable
    # the reentrant observer in CPU windows.
    os.environ["FC_TYPED_IR_REENTRANT_SAFE"] = "true"
    os.environ["FC_TYPED_IR_REENTRANT_TEST_OBSERVER"] = "false"
    os.environ["FC_TYPED_IR_DIAGNOSTICS"] = "false"
    baseline.OUT = OUT
    baseline.crossover()
    report_file = OUT / "crossover.json"
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if report.get("status") != "accepted_observational":
        raise AssertionError(f"Guarded CPU crossover isn't accepted: {report['status']}")
    summary = report["summary"]
    if not summary.get("exact_state_work") or summary.get("production_promotion"):
        raise AssertionError("Guarded benchmark exact work / no-promotion invariant failed")
    report["milestone"] = "COMPILER-IR-013"
    report["comparison"] = (
        "same emitted ASM direct scheduler on/off; queue-generation safety "
        "guard ON in both arms; no injected callback"
    )
    report["feature_flags"] = {
        "FC_TYPED_IR_REENTRANT_SAFE": "true",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER": "false",
        "FC_TYPED_IR_DIRECT_FUNCTION": "true",
        "FC_TYPED_IR_SINGLETON_FEEDBACK": "false",
        "FC_TYPED_IR_SCORE_CACHE": "false",
    }
    report["guard_overhead_isolated"] = False
    report["causal_or_general_speedup_established"] = False
    report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IR013_GUARDED_CPU_SUMMARY " + json.dumps({
        "status": report["status"],
        "on_vs_off_blocks": summary["on_vs_off_blocks"],
        "same_path_controls": summary["same_path_controls"],
        "median_on_vs_off_fraction": summary["median_on_vs_off_fraction"],
        "median_aa_fraction": summary["median_aa_fraction"],
        "per_boot_medians": summary["per_boot_medians"],
        "exact_state_work": True,
        "guard_enabled_both_arms": True,
        "guard_overhead_isolated": False,
        "production_promotion": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
