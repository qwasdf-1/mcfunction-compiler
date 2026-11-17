from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "mc-harness"))

from mc_harness.paired_stats import (  # noqa: E402
    no_regression_decision,
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


class NoRegressionGateTests(unittest.TestCase):
    """The v1 floor: the same exact interval must exclude a slowdown."""

    def test_interval_entirely_negative_holds_no_regression(self) -> None:
        summary = summarize_paired_changes([-3.0, -2.0, -4.0, -1.0, -2.5, -3.5])

        self.assertEqual(summary["decision"], "screening_only")
        self.assertEqual(summary["no_regression_decision"], "no_regression_holds")

    def test_interval_straddling_zero_is_indeterminate(self) -> None:
        summary = summarize_paired_changes([-3.0, -1.0, 0.5, 2.0, -0.5, 1.0])

        self.assertEqual(summary["no_regression_decision"], "indeterminate")

    def test_interval_entirely_positive_proves_regression(self) -> None:
        summary = summarize_paired_changes([0.5, 1.0, 2.0, 1.5, 3.0, 2.5])

        self.assertEqual(summary["no_regression_decision"], "regression_proven")

    def test_permission_and_promotion_gates_are_independent(self) -> None:
        # Clearing the promotion gate implies clearing the floor.
        summary = summarize_paired_changes(
            [-20.0, -18.0, -22.0, -19.0, -21.0, -17.0],
            minimum_gain_percent=15.0,
        )

        self.assertEqual(summary["decision"], "meets_threshold")
        self.assertEqual(summary["no_regression_decision"], "no_regression_holds")

    def test_promotion_gate_can_pass_while_floor_fails(self) -> None:
        # A single positive pair does not stop a promotion threshold from
        # clearing, provided the interval still excludes -15%; the floor uses
        # the interval, so the two gates can disagree.
        summary = summarize_paired_changes(
            [-20.0, -18.0, -40.0, -19.0, -21.0, -17.0],
            minimum_gain_percent=15.0,
            confidence=0.95,
        )

        self.assertEqual(summary["decision"], "meets_threshold")
        self.assertIn(
            summary["no_regression_decision"],
            {"indeterminate", "no_regression_holds"},
        )

    def test_perf017_fused_result_is_indeterminate(self) -> None:
        # The recorded PERF-017 per-pair changes, as a regression test for the
        # gate that defined it: median +0.69%, interval -3.92% to +2.74%.
        changes = [3.37, 2.52, 2.74, 1.09, -3.92, 0.29, 2.56, -0.90, -6.64, -2.25]

        summary = summarize_paired_changes(changes, minimum_gain_percent=15.0)

        self.assertAlmostEqual(summary["median_percent"], 0.69, places=2)
        self.assertAlmostEqual(summary["ci_low_percent"], -3.92, places=2)
        self.assertAlmostEqual(summary["ci_high_percent"], 2.74, places=2)
        self.assertEqual(summary["decision"], "does_not_meet_threshold")
        self.assertEqual(summary["no_regression_decision"], "indeterminate")

    def test_single_pair_is_insufficient_for_the_floor(self) -> None:
        summary = summarize_paired_changes([-5.0])

        self.assertEqual(summary["no_regression_decision"], "insufficient_pairs")

    def test_no_pairs_is_insufficient_for_the_floor(self) -> None:
        summary = summarize_paired_changes([])

        self.assertEqual(summary["decision"], "insufficient_pairs")
        self.assertEqual(summary["no_regression_decision"], "insufficient_pairs")

    def test_decision_helper_matches_the_summary(self) -> None:
        summary = summarize_paired_changes([-2.0, -1.0, -3.0, -2.0, -1.5, -2.5])

        self.assertEqual(
            no_regression_decision(
                summary["ci_low_percent"], summary["ci_high_percent"], summary["n"]
            ),
            summary["no_regression_decision"],
        )


if __name__ == "__main__":
    unittest.main()
