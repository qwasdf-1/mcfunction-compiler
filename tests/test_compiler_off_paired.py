"""Synthetic-contract checks for the SCHED-HOOK-003 paired campaign."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ci_compiler_off_paired import (
    BOOT_SEQUENCE,
    BLOCK_ORDERS,
    exact_median_interval,
    evaluate_pairs,
)


def fake_boot(boot: int, mode: str, value: float,
              *, noisy: bool = False, drift: float = 0) -> dict:
    return {
        "boot": boot,
        "mode": mode,
        "score_cpu_ns_per_line": value,
        "conditional_true_cpu_ns_per_line": value * 2,
        "conditional_false_cpu_ns_per_line": value * .5,
        "within_boot_score_drift_percent": drift,
        "any_noisy_window": noisy,
        "host_before_boot": {"loadavg_1m": 0.4},
    }


class PairedCampaignTests(unittest.TestCase):
    def test_counterbalanced_blocks(self):
        self.assertEqual(len(BLOCK_ORDERS), 5)
        self.assertEqual(len(BOOT_SEQUENCE), 20)
        for i in range(0, len(BOOT_SEQUENCE), 2):
            self.assertEqual(set(BOOT_SEQUENCE[i:i+2]), {"compiler", "fabric"})
        self.assertEqual(
            [BOOT_SEQUENCE[i:i+2] for i in range(0, 20, 2)].count(
                ("compiler", "fabric")
            ), 5,
        )

    def test_conservative_exact_interval(self):
        ci = exact_median_interval(list(range(10)))
        self.assertEqual(ci["order_stats"], [2, 9])
        self.assertAlmostEqual(ci["coverage"], 0.978515625)
        self.assertEqual((ci["lower"], ci["upper"]), (1, 8))

    def test_positive_regression_all_pairs_when_quiet(self):
        boots = [
            fake_boot(i, mode, 110 if mode == "compiler" else 100)
            for i, mode in enumerate(BOOT_SEQUENCE)
        ]
        result = evaluate_pairs(boots)
        self.assertTrue(result["quality_gate"]["quality_passed"])
        self.assertEqual(result["verdict"], "compiler_off_regression_above_5_percent_supported")
        self.assertAlmostEqual(result["primary"]["median_score_delta_percent"], 10)

    def test_noisy_pair_never_dropped_or_promoted(self):
        boots = [
            fake_boot(i, mode, 110 if mode == "compiler" else 100,
                      noisy=(i == 3))
            for i, mode in enumerate(BOOT_SEQUENCE)
        ]
        result = evaluate_pairs(boots)
        self.assertEqual(len(result["pairs"]), 10)
        self.assertEqual(result["quality_gate"]["noisy_or_unstable_pair_ids"], [1])
        self.assertEqual(result["verdict"], "inconclusive_host_or_stability_gate")

    def test_scoreboard_drift_fails_gate(self):
        boots = [
            fake_boot(i, mode, 110 if mode == "compiler" else 100,
                      drift=25.0 if i == 0 else 0)
            for i, mode in enumerate(BOOT_SEQUENCE)
        ]
        self.assertEqual(
            evaluate_pairs(boots)["verdict"], "inconclusive_host_or_stability_gate"
        )

    def test_no_difference_is_not_claimed_as_regression(self):
        boots = [
            fake_boot(i, mode, 100.0)
            for i, mode in enumerate(BOOT_SEQUENCE)
        ]
        self.assertEqual(
            evaluate_pairs(boots)["verdict"],
            "within_predeclared_5_percent_equivalence_band",
        )


if __name__ == "__main__":
    unittest.main()
