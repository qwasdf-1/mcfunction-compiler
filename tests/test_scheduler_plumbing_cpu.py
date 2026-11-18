"""Synthetic strict validity and noncausal interpretation for SCHED-ATTR-027."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ci_scheduler_plumbing_cpu import ARMS,EXPECTED_PACK_SHA,interpret

def records():
    data={}
    for arm,mode in ARMS:
        on=mode!="off"
        streams={}
        for path in ("build","execute","call","continuation"):
            streams[path]={
                "calls":32000 if on else 0,
                "samples":1000 if on else 0,
                "cpu_ns":(1_000_000 if mode=="empty" else 9_000_000)
                         if on else 0,
                "zero_deltas":0,"nested":0,"final_depth":0,
            }
        phases={}
        for phase in ("modifier","executable","command"):
            phases[phase]={
                "calls":800 if on else 0,
                "samples":800 if on else 0,
                "cpu_ns":(640_000 if mode=="empty" else
                          {"modifier":6_000_000,"executable":7_000_000,
                           "command":3_000_000}[phase]) if on else 0,
                "zero_deltas":0,"nested":0,"final_depth":0,
            }
        plumbing={}
        for path in ("copy","result"):
            plumbing[path]={
                "calls":800 if on else 0,"samples":800 if on else 0,
                "cpu_ns":(400_000 if mode=="empty" else
                          {"copy":1_000_000,"result":2_000_000}[path])
                          if on else 0,
                "zero_deltas":0,"nested":0,"final_depth":0,
            }
        data[arm]={
            "mode":mode,
            "publisher_sha256":EXPECTED_PACK_SHA,
            "native_state":{"ore":215,"head":1952},
            "server_thread_cpu_running_ns":13_000_000_000,
            "host_quality_pass":True,
            "probe":{"mode":mode,"streams":streams},
            "phase_probe":{"mode":mode,"streams":phases},
            "plumbing_probe":{"mode":mode,"streams":plumbing,
                "copy_identity":{"reused":600 if on else 0,
                                 "allocated":200 if on else 0},
                "callback_outcome":{"success":798 if on else 0,
                                    "failure":2 if on else 0}},
        }
    return data

class PlumbingCpuInterpretTests(unittest.TestCase):
    def test_copy_and_result_report_separate_noncausal_components(self):
        r=interpret(records())
        self.assertTrue(r["diagnostic_valid"])
        p=r["brigadier_plumbing"]
        self.assertEqual(p["copy_reuse_fraction"],0.75)
        self.assertEqual(p["callback_failure_fraction"],2/800)
        self.assertAlmostEqual(p["copy"]["signed_control_subtracted_ns_per_call"],750)
        self.assertAlmostEqual(p["result_consumer"]["signed_control_subtracted_ns_per_call"],2000)
        self.assertIn("runexecutable_outside_command_copy_and_result_sensitivity_ns",
                      r["nested_difference_sensitivities"])
        self.assertIn("not exact exclusive",r["limitations"])

    def test_timed_smaller_than_control_is_not_clamped(self):
        d=records()
        d["timed_tasks"]["plumbing_probe"]["streams"]["copy"]["cpu_ns"]=100_000
        r=interpret(d)
        self.assertLess(r["brigadier_plumbing"]["copy"]["signed_control_subtracted_ns_per_call"],0)
        self.assertTrue(r["brigadier_plumbing"]["copy"]["near_or_below_clock_floor"])

    def test_incompatible_selected_calls_rejected(self):
        d=records()
        d["timed_tasks"]["plumbing_probe"]["streams"]["result"]["calls"]=400
        with self.assertRaises(AssertionError):interpret(d)

    def test_world_state_parity_rejected(self):
        d=records()
        d["timed_tasks"]["native_state"]["head"]=1951
        with self.assertRaises(AssertionError):interpret(d)

    def test_unexpected_missing_arm_rejected(self):
        d=records()
        d.pop("plain")
        with self.assertRaises(AssertionError):interpret(d)

    def test_large_jvm_cpu_delta_is_inconclusive(self):
        d=records()
        d["timed_tasks"]["server_thread_cpu_running_ns"]=20_000_000_000
        self.assertFalse(interpret(d)["diagnostic_valid"])

if __name__=="__main__":
    unittest.main()
