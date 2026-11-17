"""Synthetic validity gates for SCHED-ATTR-023 queue vs entry CPU clocks."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_scheduler_queue_cpu import (  # noqa: E402
    ARMS, EXPECTED_PACK_SHA, interpret,
)


def records():
    result = {}
    for arm, mode in ARMS:
        cpu = 13_000_000_000
        q = 240
        e = 12_000
        if mode == "empty":
            q_ns, e_ns = 240 * 500, 12_000 * 400
        elif mode == "timed":
            q_ns, e_ns = 7_000_000_000, 6_600_000_000
        else:
            q_ns = e_ns = q = e = 0
        result[arm] = {
            "mode": mode,
            "publisher_sha256": EXPECTED_PACK_SHA,
            "native_state": {"work_after": 215, "queue_head_delta": 1952},
            "server_thread_cpu_running_ns": cpu,
            "queue_score_add_compiled": 4,
            "host_quality_pass": True,
            "probe": {
                "mode": mode, "queue_samples": q, "entry_samples": e,
                "queue_cpu_ns": q_ns, "entry_cpu_ns": e_ns,
                "queue_zero_deltas": 0, "entry_zero_deltas": 0,
                "nested_queue_events": 0, "nested_entry_events": 0,
            },
        }
    return result


class SchedulerCpuPartitionTests(unittest.TestCase):
    def test_raw_residual_excludes_every_inner_entry_interval(self):
        result = interpret(records())
        self.assertTrue(result["diagnostic_valid"])
        self.assertEqual(result["raw_queue_loop_residual_ns"], 400_000_000)
        self.assertEqual(result["timed_dequeued_entry_executions"], 12_000)
        self.assertAlmostEqual(
            result["raw_queue_loop_residual_fraction_of_event_cpu"],
            400_000_000 / 13_000_000_000,
        )
        self.assertEqual(
            result["estimated_two_entry_clock_cost_ns"], 9_600_000.0)
        self.assertIn("INCLUDES nested timer reads", result["limitations"])
        self.assertIn("NOT exclusive", result["limitations"])

    def test_excess_inner_cpu_invalidates_nested_subtraction(self):
        row = records()
        row["timed_queue"]["probe"]["entry_cpu_ns"] = 8_000_000_000
        with self.assertRaises(AssertionError):
            interpret(row)

    def test_nested_queue_invalidates_diagnostic(self):
        row = records()
        row["timed_queue"]["probe"]["nested_queue_events"] = 1
        with self.assertRaises(AssertionError):
            interpret(row)

    def test_mismatched_native_game_state_invalidates(self):
        row = records()
        row["empty_control"]["native_state"]["work_after"] = 214
        with self.assertRaises(AssertionError):
            interpret(row)

    def test_missing_arm_invalidates(self):
        row = records()
        row.pop("empty_control")
        with self.assertRaises(AssertionError):
            interpret(row)

    def test_clock_resolution_zero_gate(self):
        row = records()
        row["timed_queue"]["probe"]["entry_zero_deltas"] = 3_000
        with self.assertRaises(AssertionError):
            interpret(row)

    def test_mismatched_queue_exposure_invalidates(self):
        row = records()
        row["empty_control"]["probe"]["entry_samples"] = 6000
        with self.assertRaises(AssertionError):
            interpret(row)

    def test_large_whole_event_cpu_perturbation_is_inconclusive(self):
        row = records()
        row["timed_queue"]["server_thread_cpu_running_ns"] = 17_000_000_000
        result = interpret(row)
        self.assertFalse(result["diagnostic_valid"])
        self.assertEqual(
            result["decision"],
            "inconclusive_large_instrumentation_or_host_variance")

    def test_signed_sensitivity_not_clamped(self):
        row = records()
        row["timed_queue"]["probe"]["queue_cpu_ns"] = 6_610_000_000
        row["empty_control"]["probe"]["entry_cpu_ns"] = 50_000_000
        result = interpret(row)
        self.assertLess(result["sensitivity_residual_minus_two_entry_clocks_ns"], 0)

    def test_no_causal_speedup_or_exact_queue_claim(self):
        result = interpret(records())
        self.assertTrue(result["independent_jvm_arms"])
        self.assertIn("no speedup or exact avoidable", result["limitations"])


if __name__ == "__main__":
    unittest.main()
