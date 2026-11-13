"""Synthetic contracts for SCHED-COMP-012: no performance result without activation."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_real_fusion_coverage as coverage
import ci_fetch_real_fusion_packs as acquire


def sample_run(mode: str, cost: float, ticks: int=630) -> dict:
    return {
        "valid_for_native_timing":True,"tick_delta":ticks,
        "cpu_ns_per_witness_tick":cost,"mode":mode,
    }


def pairs(treatment_cost: float) -> list[dict]:
    return [{
        "order":order,
        "arms":{"score-add":sample_run("score-add",200.0),
                "fused":sample_run("fused",treatment_cost)}
    } for order in coverage.paired_orders()]


class FusionCandidateTests(unittest.TestCase):
    def test_seed_balanced(self):
        x=coverage.paired_orders()
        self.assertEqual(x,coverage.paired_orders())
        self.assertEqual(len(x),coverage.PAIR_COUNT)
        self.assertEqual(x.count(("score-add","fused")),3)
        self.assertEqual(x.count(("fused","score-add")),3)

    def test_per_function_diagnostic_parser(self):
        status="FC_STATS function=test:a fused_regions_compiled=7 fused_regions_executed=14 score_add_compiled=2"
        self.assertEqual(coverage.stat_int(status,"fused_regions_compiled"),7)
        self.assertEqual(coverage.stat_int(status,"fused_regions_executed"),14)
        with self.assertRaises(AssertionError):
            coverage.stat_int(status,"fused_regions_executed_typo")

    def test_function_path_must_be_datapack(self):
        self.assertEqual(coverage.function_id("data/erb/function/capture/read.mcfunction"),
                         "erb:capture/read")
        with self.assertRaises(ValueError):
            coverage.function_id("random.mcfunction")

    def test_gain_interpretation_is_fixed_threshold(self):
        report=coverage.analyze_timer_pairs(pairs(160.0))
        self.assertEqual(report["verdict"],"at_least_15pct_gain_supported")
        self.assertAlmostEqual(report["median_percent"],-20.0)
        self.assertEqual(len(report["per_pair_percent"]),6)

    def test_zero_gain_not_promoted(self):
        report=coverage.analyze_timer_pairs(pairs(200.0))
        self.assertEqual(report["verdict"],"inconclusive_or_not_material")

    def test_failed_native_integrity_rejected(self):
        x=pairs(160.0)
        x[0]["arms"]["fused"]["valid_for_native_timing"]=False
        with self.assertRaises(AssertionError):
            coverage.analyze_timer_pairs(x)

    def test_unbalanced_active_tick_count_rejected(self):
        x=pairs(160.0)
        x[0]["arms"]["fused"]["tick_delta"]=700
        with self.assertRaises(AssertionError):
            coverage.analyze_timer_pairs(x)

    def test_incomplete_campaign_rejected(self):
        with self.assertRaises(AssertionError):
            coverage.analyze_timer_pairs(pairs(160.0)[:-1])

    def test_simple_timer_not_latest_unbounded_version(self):
        example=[
            {"id":"new","date_published":"2026-11-05T00:00:00Z",
             "game_versions":["26.3"],
             "files":[{"filename":"new.zip","hashes":{"sha256":"abc"}}]},
            {"id":"old","date_published":"2026-11-01T00:00:00Z",
             "game_versions":["26.2"],
             "files":[{"filename":"old.zip","hashes":{"sha256":"def"}}]},
        ]
        self.assertEqual(acquire.choose_timer_version(example)["version"]["id"],"old")

    def test_missing_historically_bounded_timer_version_fails(self):
        with self.assertRaises(RuntimeError):
            acquire.choose_timer_version([
                {"id":"new","date_published":"2026-11-05T00:00:00Z",
                 "game_versions":["26.3"],
                 "files":[{"filename":"new.zip","hashes":{"sha256":"abc"}}]}
            ])


if __name__=="__main__":
    unittest.main()
