"""Synthetic accounting / no-causal-claim contracts for SCHED-COMP-022."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_scoreadd_cpu_timing import (  # noqa: E402
    ARMS, EXPECTED_PACK_SHA, interpret,
)


def example_records(n=11000, control=110000000, measured=440000000,
                    timed_zero=0):
    records = {}
    for name, mode in ARMS:
        probe = None
        if mode != "off":
            probe = {
                "mode": mode, "callback_samples": n,
                "direct_successes": n,
                "measured_cpu_ns": control if mode == "empty" else measured,
                "zero_delta_samples": 0 if mode == "empty" else timed_zero,
            }
        records[name] = {
            "mode": mode,
            "publisher_sha256": EXPECTED_PACK_SHA,
            "native_state": {"work_after": 215, "queue_head_delta": 1952},
            "queue_score_add_compiled": 4,
            "server_thread_cpu_running_ns": 18000000000,
            "host_quality_pass": True,
            "probe": probe,
        }
    return records


class CpuAttributionTests(unittest.TestCase):
    def test_control_subtraction_is_per_callback_not_total_sum(self):
        d = interpret(example_records())
        self.assertTrue(d["diagnostic_valid"])
        self.assertTrue(d["event_parity_verified"])
        self.assertEqual(d["empty_control_samples"], 11000)
        self.assertEqual(d["timed_callback_samples"], 11000)
        self.assertEqual(d["empty_control_cpu_ns_per_pair"], 10000)
        self.assertEqual(d["timed_cpu_ns_per_callback_including_clock"], 40000)
        self.assertEqual(d["signed_overhead_corrected_cpu_ns_per_callback"], 30000)
        self.assertTrue(d["calibration_interpretable"])
        self.assertTrue(d["independent_jvm_arms"])
        self.assertIn("cannot yield", d["limitations"])

    def test_negative_estimate_is_not_clamped_or_declared_a_b_gain(self):
        d = interpret(example_records(control=500000000, measured=300000000))
        self.assertLess(d["signed_overhead_corrected_cpu_ns_per_callback"], 0)
        self.assertLess(d["signed_overhead_corrected_callback_share_of_timed_server_cpu"], 0)
        self.assertFalse(d["calibration_interpretable"])

    def test_clock_granularity_invalidates_high_zero_delta_fraction(self):
        d = interpret(example_records(timed_zero=2500))
        self.assertFalse(d["calibration_interpretable"])
        self.assertIn("inconclusive", d["decision"])

    def test_reject_wrong_native_state(self):
        r = example_records()
        r["timed_callback"]["native_state"]["work_after"] = 214
        with self.assertRaises(AssertionError):
            interpret(r)

    def test_reject_missing_arm(self):
        r = example_records()
        r.pop("empty_control")
        with self.assertRaises(AssertionError):
            interpret(r)

    def test_reject_mismatched_datapack_and_host_failure(self):
        r = example_records()
        r["plain"]["publisher_sha256"] = "bogus"
        with self.assertRaises(AssertionError):
            interpret(r)
        r = example_records()
        r["timed_callback"]["host_quality_pass"] = False
        with self.assertRaises(AssertionError):
            interpret(r)

    def test_reject_uncalibrated_command_counts(self):
        r = example_records()
        r["timed_callback"]["probe"]["callback_samples"] = 14000
        with self.assertRaises(AssertionError):
            interpret(r)

    def test_no_probe_in_plain_arm(self):
        r = example_records()
        r["plain"]["probe"] = r["timed_callback"]["probe"]
        with self.assertRaises(AssertionError):
            interpret(r)


if __name__ == "__main__":
    unittest.main()
