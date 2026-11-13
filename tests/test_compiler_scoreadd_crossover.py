"""Contracts for SCHED-COMP-009: actual compiler vs excluded fallback."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci_compiler_scoreadd_crossover as real
import test_benchmark_crossover as synthetic


class RealCompilerTests(unittest.TestCase):
    def test_config_isolates_scoreadd_without_other_prototypes(self):
        cfg = real.compiler_config()
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["score_add"])
        self.assertFalse(cfg["fused_regions"])
        self.assertFalse(cfg["tiered_bytecode"])
        self.assertFalse(cfg["selective_macros"])
        self.assertEqual(set(cfg["excluded_namespaces"]), {real.BASE, real.NULL})
        self.assertNotIn(real.OPT, cfg["excluded_namespaces"])

    def test_all_three_underlying_functions_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real.make_fixture_with_three_paths(root)
            bodies = []
            for namespace in real.NAMESPACES:
                body = (root / "world" / "datapacks" / real.PACK / "data" /
                        namespace / "function" / "score.mcfunction").read_text()
                bodies.append(body)
            self.assertEqual(bodies[0], bodies[1])
            self.assertEqual(bodies[0], bodies[2])
            self.assertEqual(len(bodies[0].splitlines()), real.COMMANDS_PER_CALL)
            directory = root / "world" / "datapacks" / real.PACK / "data" / real.PACK / "function"
            for alias, function_id in real.FUNCTIONS.items():
                self.assertEqual((directory / (alias+".mcfunction")).read_text(),
                                 f"function {function_id}\n")

    def test_differential_direction_not_assumed(self):
        def boots(delta):
            result = []
            for index in range(real.crossover.N_BOOTS):
                item = synthetic.boot(index, pos_delta=delta)
                result.append(item)
            return result
        faster = real.analyze(boots(-20))
        slower = real.analyze(boots(20))
        self.assertEqual(faster["verdict"], "scoreadd_faster_supported")
        self.assertEqual(slower["verdict"], "scoreadd_slower_supported")

    def test_unknown_effect_is_inconclusive(self):
        result = real.analyze([synthetic.boot(i, pos_delta=0)
                               for i in range(real.crossover.N_BOOTS)])
        self.assertEqual(result["verdict"], "scoreadd_effect_inconclusive")

    def test_compilation_activation_gate(self):
        class FakeRcon:
            def command(self, cmd):
                if real.OPT in cmd:
                    return "FC_STATS score_add_compiled=2000 score_add_executed=0"
                return "FC_STATS score_add_compiled=0 score_add_executed=0"
        stats = real.specialization_stats(FakeRcon())
        self.assertEqual(stats[f"{real.OPT}:score"], 2000)
        self.assertEqual(stats[f"{real.BASE}:score"], 0)

    def test_excluded_compilation_is_a_hard_failure(self):
        class FakeRcon:
            def command(self, cmd):
                return "FC_STATS score_add_compiled=1 score_add_executed=0"
        with self.assertRaises(AssertionError):
            real.specialization_stats(FakeRcon())


if __name__ == "__main__":
    unittest.main()
