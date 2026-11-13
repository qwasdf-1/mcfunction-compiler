"""SCHED-COMP-011: paired native-workload and compile-overhead contracts."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci_veinminer_fusion_event as research


def arm(mode, event=20.0, ready=34.0, score_ns=5000000, fused_ns=0):
    return {
        "mode": mode,
        "event_completion_seconds": event,
        "launch_to_rcon_seconds": ready,
        "score_add_compile_wall_ns": score_ns,
        "fused_compile_wall_ns": fused_ns,
        "parity_state": {name: (215 if name=="work_after" else 0) for name in research.STATE_FIELDS},
        "exact_native_workload": True,
        "profile_valid": True,
    }


def pairs(fused_event):
    return [
        {"index": i+1, "order": list(research.allocation()[i]),
         "arms": {"score-add":arm("score-add"),
                  "fused":arm("fused", event=fused_event, ready=35.0,
                             score_ns=6000000, fused_ns=2000000)}}
        for i in range(research.PAIR_COUNT)
    ]


class NativeEventTests(unittest.TestCase):
    def test_balanced_reproducible_allocation(self):
        orders = research.allocation()
        self.assertEqual(orders, research.allocation())
        self.assertEqual(len(orders), 10)
        self.assertEqual(orders.count(("score-add", "fused")), 5)
        self.assertEqual(orders.count(("fused", "score-add")), 5)

    def test_event_gain_direction_and_compile_cost_separate(self):
        a = research.analyze(pairs(16.0))
        self.assertEqual(a["verdict"], "real_event_gain_at_least_15pct_supported")
        self.assertAlmostEqual(a["primary"]["median_percent"], -20)
        self.assertAlmostEqual(a["secondary"]["median_incremental_compile_stage_wall_ms"], 3.0)
        self.assertAlmostEqual(a["secondary"]["median_launch_to_rcon_delta_seconds"], 1.0)

    def test_no_real_event_gain_stays_unqualified(self):
        a = research.analyze(pairs(20.0))
        self.assertEqual(a["verdict"], "does_not_meet_15pct_gain")

    def test_bad_state_parity_fatal(self):
        data = pairs(16.0)
        data[3]["arms"]["fused"]["parity_state"]["work_after"] += 1
        with self.assertRaises(AssertionError):
            research.analyze(data)

    def test_partial_campaign_fatal(self):
        with self.assertRaises(AssertionError):
            research.analyze(pairs(16.0)[:-1])

    def test_stat_extraction_precise(self):
        self.assertEqual(research.stats_int("foo score_add_compile_wall_ns=123 fused_compile_wall_ns=456",
                                            "fused_compile_wall_ns"), 456)
        self.assertIsNone(research.stats_int("foo", "fused_compile_wall_ns"))

    def test_no_imaginary_positive_timings(self):
        with self.assertRaises(AssertionError):
            research.paired_percentage(1, 0)


if __name__ == "__main__":
    unittest.main()
