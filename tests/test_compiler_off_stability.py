"""Tests for SCHED-HOOK-004's predeclared warmup/stability protocol."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ci_compiler_off_stability import (
    BOOT_SEQUENCE,
    QUALIFICATION_MIN_WINDOWS,
    QUALIFICATION_MAX_WINDOWS,
    qualification_is_stable,
    analyze,
)


def boot(i: int, mode: str, ns: float, *,
         stable: bool = True, drift: float = .01,
         delay: float = .05, throttled: bool = False) -> dict:
    return {
        "boot": i,
        "mode": mode,
        "host_at_boot": {"loadavg_1m": 1.0},
        "score_cpu_ns_per_line": ns,
        "mean_score_runqueue_delay_fraction": delay,
        "score_within_boot_drift": drift,
        "warmup": {"qualification_stable": stable,
                   "windows_needed": 8},
        "boot_quality": {
            "passed": stable and drift <= .08 and delay <= .25 and not throttled,
            "historical_loadavg_noisy": False,
        },
    }


class StabilityProtocolTests(unittest.TestCase):
    def test_too_few_qualification_windows_never_pass(self):
        self.assertFalse(qualification_is_stable([100.0] * (QUALIFICATION_MIN_WINDOWS-1)))

    def test_stable_tail_passes(self):
        self.assertTrue(qualification_is_stable([120.0, 115.0, 100., 102., 101., 101.]))

    def test_monotone_warming_trend_fails(self):
        self.assertFalse(qualification_is_stable([200., 180., 160., 140., 120., 100.]))

    def test_tail_outlier_fails(self):
        self.assertFalse(qualification_is_stable([200., 190., 100., 100., 140., 100.]))

    def test_protocol_warmup_bounded(self):
        self.assertEqual(QUALIFICATION_MIN_WINDOWS, 6)
        self.assertEqual(QUALIFICATION_MAX_WINDOWS, 18)

    def test_pair_balance(self):
        self.assertEqual(len(BOOT_SEQUENCE), 20)
        self.assertEqual(sum(
            BOOT_SEQUENCE[i] == "compiler" for i in range(0, 20, 2)
        ), 5)

    def test_known_regression_requires_quality(self):
        boots = [boot(i, mode, 115.0 if mode == "compiler" else 100.0)
                 for i,mode in enumerate(BOOT_SEQUENCE)]
        verdict = analyze(boots)
        self.assertEqual(verdict["verdict"], "regression_above_5_percent_supported")
        self.assertEqual(verdict["quality"]["passing_pairs"], 10)

    def test_failed_warmup_cannot_be_cherry_picked(self):
        boots = [
            boot(i, mode, 115.0 if mode == "compiler" else 100.0,
                 stable=(i != 1))
            for i,mode in enumerate(BOOT_SEQUENCE)
        ]
        verdict = analyze(boots)
        self.assertEqual(verdict["verdict"], "inconclusive_quality_gate")
        self.assertEqual(verdict["quality"]["failed_pair_ids"], [1])
        self.assertEqual(len(verdict["pairs"]), 10)

    def test_pair_unequal_delay_rejected(self):
        boots = [
            boot(i, mode, 115 if mode == "compiler" else 100,
                 delay=.20 if i == 1 else .04)
            for i,mode in enumerate(BOOT_SEQUENCE)
        ]
        self.assertEqual(analyze(boots)["quality"]["failed_pair_ids"], [1])

    def test_equivalence_requires_tight_interval(self):
        boots = [boot(i, mode, 100.0)
                 for i,mode in enumerate(BOOT_SEQUENCE)]
        self.assertEqual(
            analyze(boots)["verdict"], "within_5_percent_equivalence_band",
        )

    def test_incomplete_campaign_rejected(self):
        with self.assertRaises(AssertionError):
            analyze([boot(0, "fabric", 100)])


if __name__ == "__main__":
    unittest.main()
