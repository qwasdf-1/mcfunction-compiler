"""SCHED-ATTR-026 nested subphase CPU interpretation, exact parity and clock gates."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ci_scheduler_phase_cpu import ARMS, EXPECTED_PACK_SHA, interpret


def valid_records():
    rows={}
    for arm,mode in ARMS:
        task_streams={}
        for path in ("build","execute","call","continuation"):
            off=mode=="off"
            task_streams[path]={
                "calls":0 if off else 32000,
                "samples":0 if off else 1000,
                "cpu_ns":0 if off else (1_000_000 if mode=="empty" else 9_000_000),
                "zero_deltas":0,"nested":0,"final_depth":0,
            }
        phase_streams={}
        for path in ("modifier","executable","command"):
            off=mode=="off"
            clock={"modifier":6_000_000,"executable":7_000_000,"command":6_500_000}
            phase_streams[path]={
                "calls":0 if off else 800,
                "samples":0 if off else 800,
                "cpu_ns":0 if off else (640_000 if mode=="empty" else clock[path]),
                "zero_deltas":0,"nested":0,"final_depth":0,
            }
        rows[arm]={
            "mode":mode,"publisher_sha256":EXPECTED_PACK_SHA,
            "native_state":{"ore":215,"head":1952},
            "server_thread_cpu_running_ns":13_000_000_000,
            "host_quality_pass":True,
            "probe":{"mode":mode,"streams":task_streams},
            "phase_probe":{"mode":mode,"streams":phase_streams},
        }
    return rows


class NestedPhaseCpuContracts(unittest.TestCase):
    def test_control_subtraction_and_nested_sensitivity_are_explicit(self):
        analysis=interpret(valid_records())
        self.assertTrue(analysis["diagnostic_valid"])
        self.assertEqual(analysis["sample_denominator"],32)
        self.assertAlmostEqual(
            analysis["subphases"]["command"]["signed_control_subtracted_ns_per_phase_call"],
            8125-800)
        self.assertIn("runexecutable_outside_commandrun_sensitivity_ns",
                      analysis["nested_difference_sensitivities"])
        self.assertIn("NOT",analysis["limitations"])

    def test_clock_floor_preserves_signed_negative(self):
        row=valid_records()
        row["timed_tasks"]["phase_probe"]["streams"]["modifier"]["cpu_ns"]=500_000
        a=interpret(row)
        self.assertLess(a["subphases"]["modifier"]["signed_control_subtracted_ns_per_phase_call"],0)
        self.assertTrue(a["subphases"]["modifier"]["near_or_below_clock_floor"])
        self.assertIn("inconclusive",a["subphases"]["modifier"]["decision"])

    def test_underpowered_modifier_still_reports_other_phases(self):
        row=valid_records()
        for arm in ("empty_control","timed_tasks"):
            row[arm]["phase_probe"]["streams"]["modifier"].update({
                "calls":20,"samples":20,"cpu_ns":20_000,
            })
        a=interpret(row)
        self.assertIsNone(a["subphases"]["modifier"]["projected_inclusive_cpu_ns"])
        self.assertNotIn("build_outside_runmodifier_sensitivity_ns",
                         a["nested_difference_sensitivities"])
        self.assertEqual(a["subphases"]["command"]["decision"],
                         "descriptive_inclusive_phase_only")

    def test_native_world_state_mismatch_rejected(self):
        row=valid_records()
        row["timed_tasks"]["native_state"]["ore"]=214
        with self.assertRaises(AssertionError): interpret(row)

    def test_sample_exposure_mismatch_rejected(self):
        row=valid_records()
        row["empty_control"]["phase_probe"]["streams"]["command"]["calls"]=500
        with self.assertRaises(AssertionError): interpret(row)

    def test_missing_whole_arm_rejected(self):
        row=valid_records()
        row.pop("empty_control")
        with self.assertRaises(AssertionError): interpret(row)

    def test_host_perturbation_outlier_is_inconclusive(self):
        row=valid_records()
        row["timed_tasks"]["server_thread_cpu_running_ns"]=20_000_000_000
        self.assertFalse(interpret(row)["diagnostic_valid"])

if __name__=="__main__":
    unittest.main()
