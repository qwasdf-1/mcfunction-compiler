"""SCHED-COMP-022 opt-in CPU clock contracts, compiled against a plain JDK."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/main/java/dev/functioncompiler/ScoreAddCpuProbe.java"
TEST = ROOT / "tests/java/dev/functioncompiler/ScoreAddCpuProbeContract.java"


class ScoreAddCpuProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="scoreadd-cpu-")
        cls.work = Path(cls.tmp.name)
        subprocess.run(
            ["javac", "-d", str(cls.work), str(SRC), str(TEST)],
            check=True, text=True, capture_output=True, timeout=60,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _run(self, mode):
        env = os.environ.copy()
        env["FC_SCORE_ADD_CPU_PROBE"] = mode
        return subprocess.run(
            ["java", "-cp", str(self.work),
             "dev.functioncompiler.ScoreAddCpuProbeContract", mode],
            env=env, text=True, capture_output=True, timeout=60, check=False,
        )

    def test_uninstrumented_mode_is_inert(self):
        r = self._run("off")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mode=off valid=true", r.stdout)

    def test_empty_clock_read_control(self):
        r = self._run("empty")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mode=empty valid=true", r.stdout)

    def test_bracket_callback_measurement(self):
        r = self._run("timed")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mode=timed valid=true", r.stdout)

    def test_invalid_mode_fails_closed(self):
        env = os.environ.copy()
        env["FC_SCORE_ADD_CPU_PROBE"] = "not-an-arm"
        r = subprocess.run(
            ["java", "-cp", str(self.work),
             "dev.functioncompiler.ScoreAddCpuProbeContract", "off"],
            env=env, text=True, capture_output=True, timeout=60, check=False,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FC_SCORE_ADD_CPU_PROBE", r.stderr)


if __name__ == "__main__":
    unittest.main()
