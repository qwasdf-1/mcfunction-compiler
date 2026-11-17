"""Synthetic strict parity and non-causal interpretation for SCHED-ATTR-025."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ci_scheduler_task_cpu import (
    ARMS,PATHS,EXPECTED_PACK_SHA,interpret,validate_native,
)

def example_records():
    out={}
    for arm,mode in ARMS:
        streams={}
        for name in PATHS:
            if mode=="off":
                samples=calls=cpu_ns=0
            else:
                calls=32000
                samples=1000
                cpu_ns=1_000_000 if mode=="empty" else 9_000_000
            streams[name]={
                "calls":calls,"samples":samples,"cpu_ns":cpu_ns,
                "zero_deltas":0,"nested":0,"final_depth":0,
            }
        out[arm]={
            "mode":mode,"publisher_sha256":EXPECTED_PACK_SHA,
            "native_state":{"work_after":215,"queue_head_delta":1952},
            "server_thread_cpu_running_ns":13_000_000_000,
            "queue_score_add_compiled":4,
            "host_quality_pass":True,
            "probe":{"mode":mode,"streams":streams},
        }
    return out

class SparseTaskCpuTests(unittest.TestCase):
    def test_overhead_subtracted_per_task(self):
        r=interpret(example_records())
        self.assertTrue(r["diagnostic_valid"])
        self.assertEqual(r["paths"]["build"]["signed_clock_corrected_ns_per_call"],8000)
        self.assertEqual(r["paths"]["call"]["projected_inclusive_cpu_ns"],256_000_000)
        self.assertTrue(r["paths"]["continuation"]["clock_resolved"])
        self.assertIn("DO NOT SUM",r["limitations"])

    def test_negative_signed_estimate_is_not_clamped(self):
        r=example_records()
        r["timed_tasks"]["probe"]["streams"]["build"]["cpu_ns"]=500_000
        result=interpret(r)
        self.assertLess(result["paths"]["build"]["signed_clock_corrected_ns_per_call"],0)
        self.assertFalse(result["paths"]["build"]["clock_resolved"])

    def test_wrong_sample_count(self):
        r=example_records()
        r["timed_tasks"]["probe"]["streams"]["execute"]["samples"]=200
        with self.assertRaises(AssertionError):interpret(r)

    def test_wrong_method_call_exposure(self):
        r=example_records()
        r["empty_control"]["probe"]["streams"]["call"]["calls"]=15000
        with self.assertRaises(AssertionError):interpret(r)

    def test_mismatched_final_state(self):
        r=example_records()
        r["timed_tasks"]["native_state"]["work_after"]=214
        with self.assertRaises(AssertionError):interpret(r)

    def test_large_native_cpu_difference_is_inconclusive(self):
        r=example_records()
        r["timed_tasks"]["server_thread_cpu_running_ns"]=20_000_000_000
        result=interpret(r)
        self.assertFalse(result["diagnostic_valid"])

    def test_missing_independent_arm(self):
        r=example_records()
        del r["plain"]
        with self.assertRaises(AssertionError):interpret(r)

if __name__=="__main__":
    unittest.main()
