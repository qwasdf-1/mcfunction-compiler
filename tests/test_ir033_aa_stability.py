"""IR-033 A/A placebo stability protocol and hard-gate regression tests."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_ir033_aa_stability import RUN_ORDER, PAIRS, predeclared_screen


def cases(values):
    return [
        {"label": label, "scenario": "stationary", "jfr": False,
         "game_ticks": 1200, "cpu_ns_per_tick": value}
        for label, value in zip(RUN_ORDER, values)
    ]


class IR033AATests(unittest.TestCase):
    def test_six_identical_stationary_arms_pass(self):
        data = cases([2_000_000, 2_010_000, 2_020_000,
                      2_015_000, 2_005_000, 2_010_000])
        result = predeclared_screen(data)
        self.assertTrue(result["noise_qualification_pass"])
        self.assertTrue(result["placebo_labels_are_not_compiler_modes"])
        self.assertTrue(result["is_not_causal_compiler_optimization_evidence"])
        self.assertEqual(len(PAIRS), 3)

    def test_cannot_hide_pseudoeffect_with_acceptable_adjacent_spreads(self):
        # Placebo A/B differs by >5%, but each neighboring pair is <8%.
        data = cases([2_000_000, 2_120_000, 2_120_000,
                      2_000_000, 2_000_000, 2_120_000])
        result = predeclared_screen(data)
        self.assertFalse(result["screens"]["placebo_effect_below_5pct"])
        self.assertTrue(result["screens"]["all_adjacent_pairs_below_8pct"])
        self.assertFalse(result["noise_qualification_pass"])

    def test_pair_outlier_causes_failure(self):
        data = cases([1_800_000, 2_300_000, 2_000_000,
                      2_000_000, 2_000_000, 2_000_000])
        result = predeclared_screen(data)
        self.assertFalse(result["screens"]["all_adjacent_pairs_below_8pct"])
        self.assertFalse(result["screens"]["six_arm_range_below_10pct"])
        self.assertFalse(result["noise_qualification_pass"])

    def test_rejects_order_contamination_and_tick_window_drift(self):
        data = cases([2_000_000] * 6)
        data[0]["label"] = "B9"
        with self.assertRaisesRegex(AssertionError, "order"):
            predeclared_screen(data)
        data = cases([2_000_000] * 6)
        data[0]["jfr"] = True
        with self.assertRaisesRegex(AssertionError, "instrumented"):
            predeclared_screen(data)
        data = cases([2_000_000] * 6)
        data[0]["game_ticks"] = 1000
        with self.assertRaisesRegex(AssertionError, "tick-window"):
            predeclared_screen(data)


if __name__ == "__main__":
    unittest.main()
