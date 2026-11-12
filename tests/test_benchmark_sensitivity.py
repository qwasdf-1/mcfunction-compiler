"""SCHED-BENCH-007 design, allocation, fixture, and inference contracts."""
from __future__ import annotations

import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci_benchmark_sensitivity as bench


def boot(value=200, *, qualified=True):
    return {
        "mode": "fabric", "score_cpu_ns_per_line": value,
        "host_at_boot": {"loadavg_1m": 2.0},
        "mean_score_runqueue_delay_fraction": 0.01,
        "boot_quality": {"passed": qualified},
    }


class SensitivityTests(unittest.TestCase):
    def test_balanced_reproducible_plan(self):
        plans = bench.plan()
        self.assertEqual(plans, bench.plan())
        self.assertEqual(len(plans), 40)
        for kind in ("AA", "AB"):
            pairs = [(x,y) for x,y in zip(plans[::2], plans[1::2])
                     if x["kind"] == kind]
            self.assertEqual(len(pairs), 10)
            orders = [x["arm"]+y["arm"] for x,y in pairs]
            self.assertEqual(orders.count("AB"), 5)
            self.assertEqual(orders.count("BA"), 5)
            for x,y in pairs:
                self.assertEqual(x["pair"], y["pair"])
                self.assertEqual(x["modified_lines"], 0)
                self.assertEqual(y["modified_lines"], 300 if y["arm"] == "B" and kind == "AB" else 0)

    def test_identical_negative_and_positive_dose(self):
        plans = bench.plan()
        boots = [boot(200 if x["arm"] == "A" or x["kind"] == "AA" else 230)
                 for x in plans]
        result = bench.analyze(boots, plans)
        self.assertTrue(result["negative_interval_includes_zero"])
        self.assertTrue(result["positive_interval_excludes_zero_in_expected_direction"])
        self.assertEqual(result["verdict"], "passed_defined_control_detections")
        self.assertEqual(len(result["pairs"]), 20)

    def test_noisy_null_is_not_wrongly_declared_detectable(self):
        plans = bench.plan()
        boots = [boot(200) for _ in plans]
        result = bench.analyze(boots, plans)
        self.assertEqual(result["verdict"], "failed_positive_control_detection")

    def test_quality_failure_not_discarded(self):
        plans = bench.plan()
        boots = [boot(200 if x["arm"] == "A" or x["kind"] == "AA" else 230)
                 for x in plans]
        boots[0]["boot_quality"]["passed"] = False
        result = bench.analyze(boots, plans)
        self.assertEqual(result["verdict"], "inconclusive_quality")
        self.assertEqual(len(result["pairs"]), 20)

    def test_incomplete_campaign_not_analyzed(self):
        with self.assertRaises(AssertionError):
            bench.analyze([boot()] * 39, bench.plan())

    def test_positive_fixture_keeps_exact_score_work(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp) / "ci-stable-hooks-01-fabric"
            directory.mkdir()
            original = bench._active_plan
            original_fixture = bench._original_fixture
            try:
                # Only exercise the injected score fixture; no JVM is launched.
                bench._active_plan = ({"modified_lines": 0}, {"modified_lines": 300})
                bench._original_fixture = lambda d: (
                    (d / "world" / "datapacks" / bench.stable.PACK / "data" /
                     bench.stable.PACK / "function").mkdir(parents=True, exist_ok=True),
                    (d / "world" / "datapacks" / bench.stable.PACK / "data" /
                     bench.stable.PACK / "function" / "score.mcfunction").write_text(
                        ("scoreboard players add #x fc_sched 1\n") * 2000, encoding="utf-8"),
                )
                bench.fixture(directory)
                target = (directory / "world" / "datapacks" / bench.stable.PACK /
                          "data" / bench.stable.PACK / "function" / "score.mcfunction")
                lines = target.read_text().splitlines()
                self.assertEqual(len(lines), 2000)
                self.assertEqual(sum(line.startswith("execute if score") for line in lines), 300)
                self.assertEqual(sum("scoreboard players add #x fc_sched 1" in line for line in lines), 2000)
            finally:
                bench._original_fixture = original_fixture
                bench._active_plan = original


if __name__ == "__main__":
    unittest.main()
