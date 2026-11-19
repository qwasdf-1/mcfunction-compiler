"""Macro006 parser contracts: counts, event window, clock control, nesting."""
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_macro_load_cpu006 import parse_macro006, interpret, STREAMS


def raw(mode="timed", pair_ns=1500):
    lines = [f"FC_MACRO006_BEGIN mode={mode} stride=8 function=vm:queue/load_next"]
    for s in STREAMS:
        samples = 0 if mode == "plain" else 244
        lines.append(
            f"FC_MACRO006_ROW kind={s} calls=1952 samples={samples} "
            f"cpu_ns={samples * pair_ns} invalid=0")
    lines.extend(("FC_MACRO006_COUNTS cache_hits=0 extraction_null=0",
                  f"FC_MACRO006_END mode={mode} stride=8"))
    return "\n".join(lines) + "\n"


class Macro006Tests(unittest.TestCase):
    def parse(self, text, mode):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macro006.log"
            path.write_text(text, encoding="utf-8")
            return parse_macro006(path, mode)

    def test_all_arms_exact_244_clock_samples(self):
        for mode in ("plain", "empty", "timed"):
            p = self.parse(raw(mode), mode)
            self.assertEqual(p["rows"]["macro_total"]["calls"], 1952)
            self.assertEqual(p["rows"]["macro_total"]["samples"], 0 if mode == "plain" else 244)

    def test_bad_event_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete event"):
            self.parse(raw("timed").replace("FC_MACRO006_END", "FC_MACRO006_BROKEN"), "timed")

    def test_wrong_function_rejected(self):
        with self.assertRaisesRegex(ValueError, "incorrect mode, function"):
            self.parse(raw().replace("vm:queue/load_next", "vm:queue/enqueue_match"), "timed")

    def test_nonzero_cache_hit_rejected(self):
        with self.assertRaisesRegex(ValueError, "cache/argument"):
            self.parse(raw().replace("cache_hits=0", "cache_hits=1"), "timed")

    def test_null_extraction_rejected(self):
        with self.assertRaisesRegex(ValueError, "cache/argument"):
            self.parse(raw().replace("extraction_null=0", "extraction_null=4"), "timed")

    def test_changed_exposure_rejected(self):
        with self.assertRaisesRegex(ValueError, "instantiation exposure"):
            self.parse(raw("plain").replace("calls=1952", "calls=1951"), "plain")

    def test_lost_cpu_pairs_rejected(self):
        with self.assertRaisesRegex(ValueError, "samples lost"):
            self.parse(raw().replace("samples=244", "samples=243"), "timed")

    def test_negative_cpu_interval_rejected(self):
        with self.assertRaisesRegex(ValueError, "failed CPU sample"):
            self.parse(raw().replace("invalid=0", "invalid=1"), "timed")

    def test_plain_cannot_read_clock(self):
        with self.assertRaisesRegex(ValueError, "must not read"):
            self.parse(raw("plain").replace("cpu_ns=0", "cpu_ns=22"), "plain")

    def test_control_subtraction_and_nonexclusive_nested_streams(self):
        p = self.parse(raw("plain"), "plain")
        e = self.parse(raw("empty", 600), "empty")
        t = self.parse(raw("timed", 5100), "timed")
        a = interpret(p, e, t, 15_000_000_000)
        self.assertEqual(a["streams"]["vanilla_macro_instantiation"]["signed_corrected_ns_per_call"], 4500)
        self.assertAlmostEqual(
            a["streams"]["vanilla_macro_instantiation"]["signed_projected_event_cpu_fraction"],
            1952 * 4500 / 15_000_000_000
        )
        self.assertIn("CONTAINS", a["interpretation"])
        self.assertFalse(a["streams"]["macro_total"]["fully_avoidable"])

    def test_clock_floor_and_negative_signed_correction(self):
        p = self.parse(raw("plain"), "plain")
        e = self.parse(raw("empty", 900), "empty")
        t = self.parse(raw("timed", 500), "timed")
        a = interpret(p, e, t, 15_000_000_000)
        row = a["streams"]["macro_total"]
        self.assertTrue(row["at_or_below_clock_floor"])
        self.assertLess(row["signed_corrected_ns_per_call"], 0)


if __name__ == "__main__":
    unittest.main()
