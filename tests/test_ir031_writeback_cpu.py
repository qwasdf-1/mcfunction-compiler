"""IR-031 source-specific Entity.load CPU attribution contracts."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_ir031_writeback_cpu import EXPECTED, parse, project


def log(mode: str, empty_ns: int = 1600, timed_ns: int = 11600) -> str:
    lines = [f"FC_IR031_BEGIN mode={mode} stride=16"]
    for axis, calls in EXPECTED.items():
        samples = 0 if mode == "plain" else calls // 16
        per_sample = 0 if mode == "plain" else empty_ns if mode == "empty" else timed_ns
        lines.append(
            f"FC_IR031_ROW axis={axis} path_calls={calls} marker_calls={calls} "
            f"eligible={calls} store_completed={calls} load_calls={calls} "
            f"load_completed={calls} mounted=0 other=0 samples={samples} "
            f"cpu_ns={samples * per_sample} invalid=0"
        )
    lines.append(f"FC_IR031_END mode={mode} stride=16")
    return "\n".join(lines) + "\n"


class IR031WritebackAttributionTests(unittest.TestCase):
    def read(self, raw: str, mode: str):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ir031.log"
            path.write_text(raw, encoding="utf-8")
            return parse(path, mode)

    def test_plain_empty_timed_exact_5820_entity_loads(self):
        for mode in ("plain", "empty", "timed"):
            parsed = self.read(log(mode), mode)
            self.assertEqual(
                sum(row["entity_load_calls"] for row in parsed["rows"].values()),
                5820,
            )

    def test_wrong_mode_or_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, "mode or stride"):
            self.read(log("empty"), "timed")
        with self.assertRaisesRegex(ValueError, "start/end"):
            self.read(log("timed").replace("FC_IR031_END", "BROKEN"), "timed")

    def test_wrong_source_site_or_entity_rejected(self):
        bad = log("plain").replace("path_calls=1940", "path_calls=1939", 1)
        with self.assertRaisesRegex(ValueError, "exposure drift"):
            self.read(bad, "plain")
        bad = log("plain").replace("mounted=0", "mounted=1", 1)
        with self.assertRaisesRegex(ValueError, "exposure drift"):
            self.read(bad, "plain")

    def test_plain_never_reads_cpu_clock(self):
        bad = log("plain").replace("samples=0 cpu_ns=0", "samples=0 cpu_ns=1", 1)
        with self.assertRaisesRegex(ValueError, "plain mode"):
            self.read(bad, "plain")

    def test_timed_samples_must_be_complete(self):
        bad = log("timed").replace("samples=121", "samples=120", 1)
        with self.assertRaisesRegex(ValueError, "sample count"):
            self.read(bad, "timed")

    def test_entity_load_only_projection_and_materiality_screen(self):
        plain = self.read(log("plain"), "plain")
        empty = self.read(log("empty", empty_ns=1600), "empty")
        timed = self.read(log("timed", timed_ns=200000), "timed")
        out = project(plain, empty, timed, 20_000_000_000)
        self.assertEqual(
            out["signed_projected_entity_load_cpu_ns"],
            3 * 1940 * (200000 - 1600),
        )
        self.assertTrue(out["candidate_research_warranted"])
        self.assertFalse(out["semantic_equivalence_proven"])
        self.assertFalse(out["cpu_speedup_measured"])
        self.assertIn("do not add enclosing", out["measurement_scope"])

    def test_below_clock_floor_does_not_warrant_candidate(self):
        plain = self.read(log("plain"), "plain")
        empty = self.read(log("empty", empty_ns=2000), "empty")
        timed = self.read(log("timed", timed_ns=2500), "timed")
        out = project(plain, empty, timed, 20_000_000_000)
        self.assertFalse(out["candidate_research_warranted"])

    def test_negative_projection_is_preserved_not_clamped(self):
        plain = self.read(log("plain"), "plain")
        empty = self.read(log("empty", empty_ns=2000), "empty")
        timed = self.read(log("timed", timed_ns=1500), "timed")
        out = project(plain, empty, timed, 20_000_000_000)
        self.assertLess(out["signed_projected_entity_load_cpu_ns"], 0)
        self.assertFalse(out["candidate_research_warranted"])


if __name__ == "__main__":
    unittest.main()
