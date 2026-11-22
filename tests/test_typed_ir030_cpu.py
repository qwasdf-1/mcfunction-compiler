"""IR-030 CPU pilot must reject missing/scrambled arms and A/A instability."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_cpu import RUN_ORDER, analyze


def arms(samples=(100.0, 80.0, 82.0, 102.0)):
    return {
        label: {
            "candidate_enabled": treatment,
            "status": "accepted_native_event_cpu_arm",
            "validation": {"server_thread_cpu_ns_per_work_unit": cpu},
        }
        for (label, treatment), cpu in zip(RUN_ORDER, samples)
    }


class IR030OriginalCpuTests(unittest.TestCase):
    def test_uninstrumented_abba_analysis(self):
        result = analyze(arms())
        self.assertAlmostEqual(result["A_A_relative_spread"], 2 / 101)
        self.assertAlmostEqual(
            result["relative_candidate_cpu_reduction_observed"], 20 / 101)
        self.assertFalse(result["independent_replication_completed"])
        self.assertFalse(result["production_promotion"])
        self.assertTrue(result["A_A_stable_within_8pct"])

    def test_noisy_AA_retained_and_marked_inconclusive(self):
        result = analyze(arms((100.0, 85.0, 86.0, 120.0)))
        self.assertFalse(result["A_A_stable_within_8pct"])
        self.assertGreater(result["A_A_relative_spread"], 0.08)

    def test_requires_all_four_arms(self):
        case = arms()
        case.pop("B2")
        with self.assertRaisesRegex(AssertionError, "Incomplete"):
            analyze(case)

    def test_rejects_reversed_treatment_order(self):
        case = arms()
        case["A1"]["candidate_enabled"] = True
        with self.assertRaisesRegex(AssertionError, "order"):
            analyze(case)

    def test_rejects_unaccepted_arm(self):
        case = arms()
        case["B1"]["status"] = "invalid_arm"
        with self.assertRaisesRegex(AssertionError, "rejected"):
            analyze(case)

    def test_negative_gain_not_confused_with_speedup(self):
        result = analyze(arms((100.0, 120.0, 124.0, 102.0)))
        self.assertLess(result["relative_candidate_cpu_reduction_observed"], 0)
        self.assertFalse(result["meets_raw_15pct_threshold"])
        self.assertFalse(result["causal_speedup_confirmed"])


if __name__ == "__main__":
    unittest.main()
