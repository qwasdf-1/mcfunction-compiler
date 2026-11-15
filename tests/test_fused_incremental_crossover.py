"""SCHED-COMP-010: code-path isolation and fusion inference contracts."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import ci_fused_incremental_crossover as research
import test_benchmark_crossover as synthetic


class FusedIncrementalTests(unittest.TestCase):
    def test_config_enables_only_scoreadd_and_fusion(self):
        cfg = research.compiler_config()
        self.assertTrue(cfg["enabled"] and cfg["score_add"] and cfg["fused_regions"])
        self.assertFalse(cfg["tiered_bytecode"])
        self.assertFalse(cfg["selective_macros"])
        self.assertEqual(cfg["excluded_namespaces"], [])
        self.assertEqual(len(research.NAMESPACES), 3)

    def test_identical_2000_scoreboard_commands_in_all_arms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            research.make_fixture_with_three_paths(root)
            bodies = [
                (root / "world" / "datapacks" / research.PACK / "data" /
                 namespace / "function" / "score.mcfunction").read_text()
                for namespace in research.NAMESPACES
            ]
            self.assertEqual(bodies[0], bodies[1])
            self.assertEqual(bodies[0], bodies[2])
            self.assertEqual(len(bodies[0].splitlines()), 2000)
            for alias, fid in research.FUNCTIONS.items():
                path = root / "world" / "datapacks" / research.PACK / "data" / research.PACK / "function" / (alias+".mcfunction")
                self.assertEqual(path.read_text(), f"function {fid}\n")

    def test_activation_requires_scoreadd_all_and_fusion_only_treatment(self):
        class Rcon:
            def command(self, cmd):
                fusion = 1 if research.OPT in cmd else 0
                return f"FC_STATS score_add_compiled=2000 fused_regions_compiled={fusion}"
        values = research.specialization_stats(Rcon())
        self.assertEqual(values[f"{research.BASE}:score"]["fused_regions_compiled"], 0)
        self.assertGreater(values[f"{research.OPT}:score"]["fused_regions_compiled"], 0)

    def test_unexpected_fusion_control_is_fatal(self):
        class Rcon:
            def command(self, cmd):
                return "FC_STATS score_add_compiled=2000 fused_regions_compiled=1"
        with self.assertRaises(AssertionError):
            research.specialization_stats(Rcon())

    def test_missing_fusion_treatment_is_fatal(self):
        class Rcon:
            def command(self, cmd):
                return "FC_STATS score_add_compiled=2000 fused_regions_compiled=0"
        with self.assertRaises(AssertionError):
            research.specialization_stats(Rcon())

    def test_synthetic_speedup_and_slowdown_are_reported(self):
        faster = research.analyze([synthetic.boot(i, pos_delta=-20)
                                    for i in range(research.crossover.N_BOOTS)])
        slower = research.analyze([synthetic.boot(i, pos_delta=20)
                                    for i in range(research.crossover.N_BOOTS)])
        self.assertEqual(faster["verdict"], "fusion_faster_than_scoreadd_supported")
        self.assertEqual(slower["verdict"], "fusion_slower_than_scoreadd_supported")

    def test_zero_effect_remains_inconclusive(self):
        result = research.analyze([synthetic.boot(i, pos_delta=0)
                                   for i in range(research.crossover.N_BOOTS)])
        self.assertEqual(result["verdict"], "fusion_incremental_effect_inconclusive")


if __name__ == "__main__":
    unittest.main()
