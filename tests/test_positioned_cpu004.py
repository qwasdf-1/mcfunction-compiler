"""CPU004 sparse clock parser and projection contracts; no Minecraft simulated."""
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_positioned_cpu004 import parse_cpu004, diagnostic_projection

COUNTS = {"positioned_entry": 5616, "enqueue_call_setup": 5616, "enqueue_body_leaf": 15616}


def raw(mode="timed", correction=10000, overflow=False):
    rows = []
    for kind, count in COUNTS.items():
        samples = count // 16 if mode != "plain" else 0
        ns = samples * correction if mode != "plain" else 0
        rows.append(f"FC_CPU004_ROW kind={kind} calls={count} samples={samples} cpu_ns={ns} invalid={int(overflow)}")
    return (
        f"FC_CPU004_BEGIN mode={mode} stride=16\n"
        + "\n".join(rows) + "\n"
        + f"FC_CPU004_END mode={mode} stride=16\n"
    )


class Cpu004Tests(unittest.TestCase):
    def parse(self, payload, mode):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cpu004.log"
            path.write_text(payload, encoding="utf-8")
            return parse_cpu004(path, mode)

    def test_empty_timed_plain_have_exact_samples(self):
        self.assertEqual(self.parse(raw("plain"), "plain")["rows"]["positioned_entry"]["samples"], 0)
        self.assertEqual(self.parse(raw("empty"), "empty")["rows"]["positioned_entry"]["samples"], 351)
        self.assertEqual(self.parse(raw("timed"), "timed")["rows"]["positioned_entry"]["samples"], 351)

    def test_missing_dump_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.parse(raw().replace("FC_CPU004_END", "FC_CPU004_broken"), "timed")

    def test_mismatched_sample_count_rejected(self):
        with self.assertRaisesRegex(ValueError, "sparse CPU clock"):
            self.parse(raw().replace("samples=351", "samples=350"), "timed")

    def test_bad_clock_delta_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid CPU-clock"):
            self.parse(raw(overflow=True), "timed")

    def test_changed_native_exposure_rejected(self):
        with self.assertRaisesRegex(ValueError, "invocation count changed"):
            self.parse(raw("plain").replace("calls=5616", "calls=5615"), "plain")

    def test_control_subtraction_preserves_signed_correction(self):
        p = self.parse(raw("plain"), "plain")
        e = self.parse(raw("empty", correction=900), "empty")
        t = self.parse(raw("timed", correction=5000), "timed")
        result = diagnostic_projection(p, e, t, 1_000_000_000)
        v = result["kind_projections"]["positioned_entry"]
        self.assertEqual(v["signed_control_corrected_cpu_ns_per_call"], 4100)
        self.assertAlmostEqual(v["signed_projected_fraction_of_timed_server_cpu"], 4100 * 5616 / 1e9)
        self.assertFalse(v["can_be_claimed_avoidable"])

    def test_unpaired_different_event_exposure_rejected(self):
        p = self.parse(raw("plain"), "plain")
        e = self.parse(raw("empty"), "empty")
        t = self.parse(raw("timed"), "timed")
        t["rows"]["enqueue_body_leaf"]["calls"] += 1
        with self.assertRaisesRegex(ValueError, "dynamic call exposure"):
            diagnostic_projection(p, e, t, 1_000_000)

    def test_near_clock_floor_warning(self):
        p = self.parse(raw("plain"), "plain")
        e = self.parse(raw("empty", correction=1000), "empty")
        t = self.parse(raw("timed", correction=1200), "timed")
        r = diagnostic_projection(p, e, t, 1_000_000_000)
        self.assertTrue(r["kind_projections"]["positioned_entry"]["clock_floor_warning"])


if __name__ == "__main__":
    unittest.main()
