"""Synthetic predeclared A/A and telemetry contracts for SCHED-NOISE-005."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ci_noise_aa_calibration import (
    PAIR_MODES, LABEL_ORDER, BOOT_SEQUENCE, evaluate, pct_change,
    percentile_nearest_rank,
)
from benchmark_noise_telemetry import delta_environment, thread_role


def dummy_boot(index: int, mode: str, cost: float,
               *, qualified: bool = True):
    return {
        "boot": index, "mode": mode,
        "score_cpu_ns_per_line": cost,
        "mean_score_runqueue_delay_fraction": .01,
        "host_at_boot": {"loadavg_1m": 1.5},
        "boot_quality": {"passed": qualified, "historical_loadavg_noisy": False},
        "warmup": {"qualification_stable": qualified},
        "timed_windows": [{"exact_work": True}],
    }


class NullCalibrationTests(unittest.TestCase):
    def test_negative_control_pairing_has_same_binary_both_sides(self):
        self.assertEqual(len(BOOT_SEQUENCE), 20)
        self.assertEqual(PAIR_MODES.count("fabric"), 5)
        self.assertEqual(PAIR_MODES.count("compiler"), 5)
        self.assertEqual(len(LABEL_ORDER), 10)
        for i, mode in enumerate(PAIR_MODES):
            self.assertEqual(BOOT_SEQUENCE[2*i:2*i+2], (mode, mode))
            self.assertEqual(set(LABEL_ORDER[i]), {"A", "B"})

    def test_exact_aa_has_zero_false_effect(self):
        boots = [dummy_boot(i, mode, 200.)
                 for i, mode in enumerate(BOOT_SEQUENCE)]
        data = evaluate(boots)
        self.assertEqual(data["verdict"], "null_calibration_screening_targets_met")
        self.assertEqual(data["pooled_blinded_null"]["max_absolute_percent"], 0)
        self.assertEqual(data["by_stack"]["compiler"]["median_absolute_null_delta_percent"], 0)

    def test_spurious_false_effect_fails_null_target(self):
        boots = [dummy_boot(i, mode, 200. * (1.5 if i == 1 else 1.0))
                 for i, mode in enumerate(BOOT_SEQUENCE)]
        data = evaluate(boots)
        self.assertEqual(data["verdict"], "null_calibration_failed_variance_targets")
        self.assertEqual(len(data["pairs"]), 10)

    def test_qualified_gate_rejects_even_clean_null(self):
        boots = [dummy_boot(i, mode, 200., qualified=(i != 2))
                 for i, mode in enumerate(BOOT_SEQUENCE)]
        data = evaluate(boots)
        self.assertEqual(data["verdict"], "inconclusive_quality_gate")
        self.assertEqual(data["quality"]["failed_pair_ids"], [2])

    def test_incomplete_calibration_never_scored(self):
        with self.assertRaises(AssertionError):
            evaluate([dummy_boot(0, "fabric", 200.)])

    def test_symmetric_scale_aware_abs_ratios(self):
        self.assertAlmostEqual(pct_change(110, 100), 10)
        self.assertAlmostEqual(pct_change(100, 110), -9.090909090909)
        self.assertEqual(percentile_nearest_rank([1, 3, 5, 7, 9], .9), 9)

    def test_linux_comm_truncation_approx_jit(self):
        self.assertEqual(thread_role("C2 CompilerThre"), "jit_compiler")
        self.assertEqual(thread_role("Server thread"), "server")
        self.assertEqual(thread_role("GC Thread#2"), "gc")

    def test_telemetry_deltas_do_not_clip_negative_non_jvm_values(self):
        before = {
            "monotonic_ns": 10, "jvm_process_cpu_ns": 1000,
            "jvm_threads": {"11": {"name": "Server thread", "running_ns": 20, "waiting_ns": 1},
                            "12": {"name": "C2 CompilerThre", "running_ns": 50, "waiting_ns": 2}},
            "loadavg_1m": 1.0, "cgroup_cpu": {"nr_throttled": 0},
            "system_cpu_pressure_us": {"some": 200},
            "process_affinity": [0, 1],
        }
        after = {
            "monotonic_ns": 100, "jvm_process_cpu_ns": 2000,
            "jvm_threads": {"11": {"name": "Server thread", "running_ns": 300, "waiting_ns": 11},
                            "12": {"name": "C2 CompilerThre", "running_ns": 200, "waiting_ns": 12}},
            "loadavg_1m": 2.0, "cgroup_cpu": {"nr_throttled": 2},
            "system_cpu_pressure_us": {"some": 300},
            "process_affinity": [0, 1],
        }
        d = delta_environment(before, after)
        self.assertEqual(d["whole_jvm_cpu_ns"], 1000)
        self.assertEqual(d["surviving_thread_running_ns_by_role"]["jit_compiler"], 150)
        self.assertEqual(d["surviving_thread_wait_ns_by_role"]["server"], 10)
        self.assertEqual(d["cgroup_cpu_delta"]["nr_throttled"], 2)
        self.assertEqual(d["system_cpu_pressure_us_delta"]["some"], 100)
        self.assertTrue(d["affinity_stable"])


if __name__ == "__main__":
    unittest.main()
