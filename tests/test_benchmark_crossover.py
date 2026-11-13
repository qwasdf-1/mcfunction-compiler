"""SCHED-BENCH-008 synthetic crossover contracts; requires pinned mc-harness."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci_benchmark_crossover as x


def sample(family, cpu):
    return {
        "family": family, "cpu_ns_per_source_line": cpu, "exact_work": True,
        "cgroup_nr_throttled_delta": 0, "runqueue_delay_fraction": .002,
    }


def block(kind, orientation, base=200, delta=0):
    names = {"A": "score_a", "B": "score_null" if kind == "negative" else "score_treatment"}
    return {"kind": kind, "orientation": orientation,
            "windows": [sample(names[ch], base + (delta if ch == "B" else 0))
                        for ch in orientation]}


def boot(index, *, pos_delta=20, quality=True):
    result = {
        "index": index, "status": "complete",
        "qualification": {"qualification_stable": quality},
        "blocks": [block("negative", "ABBA"), block("positive", "BAAB", delta=pos_delta)],
    }
    return result


class CrossoverTests(unittest.TestCase):
    def test_plan_reproducible_and_balanced(self):
        plans = x.schedule()
        self.assertEqual(plans, x.schedule())
        self.assertEqual(len(plans), x.N_BOOTS)
        self.assertEqual(sum(p["blocks"][0]["kind"] == "negative" for p in plans), 6)
        for kind in ("negative", "positive"):
            orientations = [b["orientation"] for p in plans for b in p["blocks"]
                            if b["kind"] == kind]
            self.assertEqual(orientations.count("ABBA"), 6)
            self.assertEqual(orientations.count("BAAB"), 6)
        for p in plans:
            self.assertEqual({b["kind"] for b in p["blocks"]}, {"negative", "positive"})
            self.assertEqual(sum(len(b["functions"]) for b in p["blocks"]), 8)

    def test_negative_zero_and_positive_direction(self):
        r = x.analyze([boot(i) for i in range(x.N_BOOTS)])
        self.assertEqual(r["verdict"], "control_screening_passed")
        self.assertEqual(r["by_kind"]["negative"]["median_log_percent"], 0)
        self.assertGreater(r["by_kind"]["positive"]["exact_median_interval"]["lower"], 0)

    def test_same_boot_drift_cancels(self):
        # Increasing CPU time at a fixed log-rate over four positions cancels
        # because A and B each have mean position 1.5 in ABBA and BAAB.
        import math
        values = [200 * math.exp(i*.025) for i in range(4)]
        for kind in ("negative", "positive"):
            for orientation in ("ABBA", "BAAB"):
                b = block(kind, orientation)
                for w, cpu in zip(b["windows"], values):
                    w["cpu_ns_per_source_line"] = cpu
                self.assertAlmostEqual(x.block_contrast(b), 0, places=8)

    def test_quality_failure_kept(self):
        runs = [boot(i) for i in range(x.N_BOOTS)]
        runs[0]["qualification"]["qualification_stable"] = False
        r = x.analyze(runs)
        self.assertEqual(r["verdict"], "inconclusive_quality")
        self.assertEqual(r["quality_failed_boot_ids"], [0])
        self.assertEqual(len(r["per_boot"]), x.N_BOOTS)

    def test_incomplete_campaign_fails(self):
        with self.assertRaises(AssertionError):
            x.analyze([boot(i) for i in range(x.N_BOOTS-1)])

    def test_missing_scoreboard_integrity_rejected(self):
        runs = [boot(i) for i in range(x.N_BOOTS)]
        runs[3]["blocks"][0]["windows"][2]["exact_work"] = False
        with self.assertRaises(AssertionError):
            x.analyze(runs)

    def test_fixture_has_identical_null_and_work_equivalent_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            x.make_crossover_fixture(root)
            directory = root / "world" / "datapacks" / x.PACK / "data" / x.PACK / "function"
            a = (directory / "score_a.mcfunction").read_text()
            n = (directory / "score_null.mcfunction").read_text()
            t = (directory / "score_treatment.mcfunction").read_text().splitlines()
            self.assertEqual(a, n)
            self.assertEqual(len(t), x.COMMANDS_PER_CALL)
            self.assertEqual(sum(line.startswith("execute if score") for line in t),
                             x.PERTURBED_LINES)
            self.assertEqual(sum("scoreboard players add" in line for line in t),
                             x.COMMANDS_PER_CALL)


if __name__ == "__main__":
    unittest.main()
