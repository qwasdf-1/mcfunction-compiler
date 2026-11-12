"""Synthetic log-parser and time-alignment contracts for SCHED-GC-006."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from gc_phase_telemetry import parse_lines, load_log, window_summary


class GcPhaseTests(unittest.TestCase):
    def setUp(self):
        self.lines = [
            "[2026-11-12T18:00:00.100+0000][1000ms][info][gc,start] GC(7) Pause Young (Normal) (G1 Evacuation Pause)",
            "[2026-11-12T18:00:00.125+0000][1025ms][info][gc] GC(7) Pause Young (Normal) (G1 Evacuation Pause) 90M->40M(512M) 25.0ms",
            "[2026-11-12T18:00:00.220+0000][1120ms][info][gc] GC(8) Concurrent Mark 100.0ms",
        ]

    def test_parse_pause_heap_and_concurrent(self):
        parsed = parse_lines(self.lines)
        self.assertEqual(len(parsed["events"]), 3)
        pause = parsed["events"][1]
        self.assertEqual(pause["gc_id"], 7)
        self.assertEqual(pause["duration_ms"], 25.0)
        self.assertTrue(pause["is_pause"])
        self.assertEqual(pause["heap_before_bytes"], 90 * 1024**2)
        self.assertEqual(pause["heap_after_bytes"], 40 * 1024**2)
        self.assertTrue(parsed["events"][2]["is_concurrent"])

    def test_approximate_overlap(self):
        parsed = parse_lines(self.lines)
        parsed["available"] = True
        base = parsed["events"][0]["epoch_ms"]
        hit = window_summary(parsed, base + 15, base + 30)
        self.assertEqual(hit["observed_pauses"], 1)
        self.assertEqual(hit["observed_logged_pause_ms"], 25.0)

    def test_missing_log_is_unknown_not_quiet(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = load_log(Path(temp) / "missing.log")
        self.assertFalse(window_summary(parsed, 0, 100)["known"])

    def test_invalid_window_is_rejected(self):
        with self.assertRaises(ValueError):
            window_summary({"available": True, "events": []}, 2, 1)

    def test_unknown_gc_messages_are_retained(self):
        parsed = parse_lines(self.lines)
        self.assertGreaterEqual(len(parsed["unclassified_gc_events"]), 1)


if __name__ == "__main__":
    unittest.main()
