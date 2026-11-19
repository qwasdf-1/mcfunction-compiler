"""Unit contracts for CPU005 stream attribution. No Minecraft work simulated."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_queue_cpu005 import EXPECTED_CALLS, parse_cpu005, projection


def log(mode: str, ns: int = 3000) -> str:
    lines = [f"FC_CPU005_BEGIN mode={mode} stride=16"]
    for kind, calls in EXPECTED_CALLS.items():
        samples = 0 if mode == "plain" else calls // 16
        lines.append(f"FC_CPU005_ROW kind={kind} calls={calls} samples={samples} "
                     f"cpu_ns={samples * ns} invalid=0")
    lines.append(f"FC_CPU005_END mode={mode} stride=16")
    return "\n".join(lines) + "\n"


class QueueCpuTests(unittest.TestCase):
    def read(self, raw, mode):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cpu005.log"
            path.write_text(raw, encoding="utf-8")
            return parse_cpu005(path, mode)

    def test_valid_plain_empty_timed(self):
        for mode in ("plain", "empty", "timed"):
            parsed = self.read(log(mode), mode)
            self.assertEqual(parsed["rows"]["enqueue_macro_predicate_build"]["calls"], 5616)

    def test_missing_boundary(self):
        with self.assertRaisesRegex(ValueError, "Exactly one"):
            self.read(log("empty").replace("FC_CPU005_END", "bad"), "empty")

    def test_corrupted_event_exposure(self):
        with self.assertRaisesRegex(ValueError, "exposure drift"):
            self.read(log("plain").replace("calls=5616", "calls=5615"), "plain")

    def test_clock_mode_constraints(self):
        with self.assertRaisesRegex(ValueError, "Plain mode"):
            self.read(log("plain").replace(
                "samples=0 cpu_ns=0", "samples=1 cpu_ns=22"), "plain")

    def test_missing_scheduled_callback_sample(self):
        with self.assertRaisesRegex(ValueError, "sample pairs"):
            self.read(log("timed").replace("samples=121", "samples=119"), "timed")

    def test_unknown_kind(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.read(log("plain").replace(
                "kind=append_tp_execute", "kind=not_a_real_stream"), "plain")

    def test_control_subtracted_projection_and_overlap(self):
        p = self.read(log("plain"), "plain")
        e = self.read(log("empty", ns=500), "empty")
        t = self.read(log("timed", ns=7500), "timed")
        result = projection(p, e, t, 12_000_000_000)
        row = result["streams"]["enqueue_macro_predicate_build"]
        self.assertEqual(row["signed_corrected_ns_per_call"], 7000)
        self.assertAlmostEqual(row["signed_projected_event_cpu_fraction"],
                               5616 * 7000 / 12_000_000_000)
        self.assertIn("overlaps", result["interpretation"])

    def test_below_clock_floor_flag(self):
        p = self.read(log("plain"), "plain")
        e = self.read(log("empty", ns=2000), "empty")
        t = self.read(log("timed", ns=2600), "timed")
        x = projection(p, e, t, 12_000_000_000)
        self.assertTrue(x["streams"]["enqueue_macro_predicate_build"]["at_or_below_clock_floor"])


if __name__ == "__main__":
    unittest.main()
