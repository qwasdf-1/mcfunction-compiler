from __future__ import annotations

import unittest

from scripts.paired_benchmark_analysis import (
    paired_percent_changes,
    summarize_paired_changes,
)


class PairedBenchmarkAnalysisTests(unittest.TestCase):
    def test_five_pairs_report_actual_confidence_and_remain_screening(self) -> None:
        summary = summarize_paired_changes([-12.0, -11.0, -10.0, -13.0, -11.5])

        self.assertEqual(summary["n"], 5)
        self.assertEqual(summary["ci_low_percent"], -13.0)
        self.assertEqual(summary["ci_high_percent"], -10.0)
        self.assertEqual(summary["confidence_achieved"], 0.9375)
        self.assertEqual(summary["decision"], "screening_only")

    def test_six_consistent_pairs_can_meet_a_predeclared_threshold(self) -> None:
        summary = summarize_paired_changes(
            [-12.0, -11.0, -10.0, -13.0, -11.5, -12.5],
            minimum_gain_percent=5.0,
        )

        self.assertEqual(summary["confidence_achieved"], 0.96875)
        self.assertEqual(summary["decision"], "meets_threshold")

    def test_interval_crossing_threshold_is_inconclusive(self) -> None:
        summary = summarize_paired_changes(
            [-20.0, -10.0, -1.0, 0.0, 1.0, 2.0],
            minimum_gain_percent=5.0,
        )

        self.assertEqual(summary["decision"], "inconclusive")

    def test_pair_changes_are_relative_and_negative_is_faster(self) -> None:
        pairs = [
            {"off": {"seconds": 10.0}, "candidate": {"seconds": 8.0}},
            {"off": {"seconds": 20.0}, "candidate": {"seconds": 22.0}},
        ]

        changes = paired_percent_changes(
            pairs,
            metric="seconds",
            baseline_arm="off",
            candidate_arm="candidate",
        )
        self.assertAlmostEqual(changes[0], -20.0)
        self.assertAlmostEqual(changes[1], 10.0)


if __name__ == "__main__":
    unittest.main()
