"""IR-030 exact source-site count parser tests; no Minecraft simulation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_typed_ir030_sites import parse_site_rows


VALID = """
[Server thread/INFO]: FC_IR030_SITE_ROW axis=x calls=1940
[Server thread/INFO]: FC_IR030_SITE_ROW axis=y calls=1940
[Server thread/INFO]: FC_IR030_SITE_ROW axis=z calls=1940
"""


class IR030SiteCountTests(unittest.TestCase):
    def test_exact_three_sites(self):
        self.assertEqual(parse_site_rows(VALID), {"x": 1940, "y": 1940, "z": 1940})

    def test_missing_site_rejected(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            parse_site_rows(VALID.replace("axis=y calls=1940\n", ""))

    def test_duplicate_site_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_site_rows(VALID + "FC_IR030_SITE_ROW axis=x calls=1940\n")

    def test_site_exposure_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, "exposure drift"):
            parse_site_rows(VALID.replace("axis=z calls=1940", "axis=z calls=1939"))

    def test_non_exact_rows_ignored_then_incomplete(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            parse_site_rows("FC_IR030_SITE_ROW axis=q calls=1940\n")


if __name__ == "__main__":
    unittest.main()
