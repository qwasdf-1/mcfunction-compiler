"""Regression contracts for top-level G1 cycles and overlapping windows."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from gc_cycle_reconstruction import parse_cycles, describe_window


def line(ms, tags, body):
    return (f"[2026-11-12T18:00:00.{ms:03d}+0000][{ms}ms][info]"
            f"[{tags}] GC(3) {body}")


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.lines = [
            line(100, "gc,start    ", "Concurrent Mark Cycle"),
            line(110, "gc,marking  ", "Concurrent Mark From Roots"),
            line(140, "gc,marking  ", "Concurrent Mark From Roots 30.0ms"),
            line(145, "gc,start    ", "Pause Remark"),
            line(151, "gc          ", "Pause Remark 40M->40M(512M) 6.0ms"),
            line(180, "gc          ", "Concurrent Mark Cycle 80.0ms"),
            line(200, "gc,start    ", "Pause Young (Normal) (G1 Evacuation Pause)"),
            line(205, "gc,phases   ", "Evacuate Collection Set: 4.0ms"),
            line(208, "gc          ", "Pause Young (Normal) (G1 Evacuation Pause) 90M->40M(512M) 8.0ms"),
        ]

    def test_only_top_level_cycles_are_counted(self):
        parsed = parse_cycles(self.lines)
        self.assertEqual(len(parsed["cycles"]), 3)
        self.assertEqual(len(parsed["unmatched_starts"]), 0)
        self.assertEqual(sum(c["is_concurrent_cycle"] for c in parsed["cycles"]), 1)
        self.assertEqual(sum(c["is_pause"] for c in parsed["cycles"]), 2)
        concurrent = next(c for c in parsed["cycles"] if c["is_concurrent_cycle"])
        self.assertEqual(concurrent["duration_ms"], 80)
        self.assertEqual(concurrent["start_source"], "explicit")
        self.assertEqual(len(concurrent["nested_phases"]), 1)

    def test_overlap_counts_pause_and_marking_separately(self):
        parsed = parse_cycles(self.lines)
        t = next(c for c in parsed["cycles"] if c["is_concurrent_cycle"])["start_ms"]
        window = describe_window(parsed, t + 40, t + 60)
        self.assertEqual(window["concurrent_cycle_count"], 1)
        self.assertEqual(window["pause_count"], 1)
        self.assertAlmostEqual(window["pause_overlap_ms"], 6)
        self.assertAlmostEqual(window["concurrent_cycle_overlap_ms"], 20)
        self.assertTrue(window["not_a_quiet_certification"])

    def test_inferred_duration_is_flagged(self):
        parsed = parse_cycles([line(120, "gc", "Pause Full (G1 Compaction Pause) 100M->30M(512M) 12.0ms")])
        self.assertEqual(parsed["cycles"][0]["start_source"], "inferred")
        self.assertEqual(parsed["cycles"][0]["heap_after_bytes"], 30*1024*1024)

    def test_incomplete_start_is_retained(self):
        parsed = parse_cycles([line(120, "gc,start", "Concurrent Mark Cycle")])
        self.assertEqual(len(parsed["unmatched_starts"]), 1)
        self.assertFalse(parsed["cycles"])

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            describe_window(parse_cycles([]), 100, 0)


if __name__ == "__main__":
    unittest.main()
