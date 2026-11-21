"""IR-008 same-JVM comparison: balanced order and noncausal inference gates."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir008_crossover as m


class IR008CrossoverTests(unittest.TestCase):
    def test_original_bytes_identical_across_compiler_namespaces(self):
        with tempfile.TemporaryDirectory() as directory:
            m.write_pack(Path(directory))
            root = Path(directory) / "world/datapacks/fc_ir008_crossover/data"
            f = (root / "fc_fused/function/bench64.mcfunction").read_bytes()
            b = (root / "fc_ir/function/bench64.mcfunction").read_bytes()
            self.assertEqual(f, b)
            self.assertEqual(f.count(b"\n"), 64)

    def test_ABBA_and_BAAB_alternate_within_each_contrast(self):
        for boot in range(m.BOOTS):
            planned = m.plan(boot)
            self.assertEqual(len(planned),
                             m.REPETITIONS_PER_BOOT + m.SAME_PATH_CONTROLS)
            for contrast, n in (("fused_vs_asm", m.REPETITIONS_PER_BOOT),
                                ("fused_aa", m.SAME_PATH_CONTROLS)):
                arms = [row for row in planned if row["contrast"] == contrast]
                self.assertEqual(len(arms), n)
                self.assertEqual([a["order"] for a in arms].count("ABBA"), n // 2)
                self.assertEqual([a["order"] for a in arms].count("BAAB"), n // 2)

    def test_two_boots_are_mandatory(self):
        with self.assertRaisesRegex(ValueError, "Two accepted"):
            m.summarize([{"status": "accepted", "blocks": []}])

    def test_report_does_not_promote_single_compiled_microfixture(self):
        result = []
        for i in range(m.BOOTS):
            blocks = [
                {"contrast": "fused_vs_asm", "b_vs_a_signed_fraction": -0.12}
                for _ in range(m.REPETITIONS_PER_BOOT)
            ]
            blocks += [
                {"contrast": "fused_aa", "b_vs_a_signed_fraction": 0.01}
                for _ in range(m.SAME_PATH_CONTROLS)
            ]
            result.append({"status": "accepted", "blocks": blocks, "boot": i})
        s = m.summarize(result)
        self.assertEqual(s["fused_vs_asm_blocks"],
                         m.BOOTS * m.REPETITIONS_PER_BOOT)
        self.assertAlmostEqual(s["fused_vs_asm_signed_median_fraction"], -0.12)
        self.assertFalse(s["effect_is_causal_or_general"])
        self.assertFalse(s["production_promotion"])


if __name__ == "__main__":
    unittest.main()
