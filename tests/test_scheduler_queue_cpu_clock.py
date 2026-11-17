"""SCHED-ATTR-023 pure-Java ThreadMXBean queue/entry probe contracts."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "src/main/java/dev/functioncompiler/SchedulerQueueCpuProbe.java"
CONTRACT = ROOT / "tests/java/dev/functioncompiler/SchedulerQueueCpuProbeContract.java"


class SchedulerQueueCpuClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="scheduler-cpu-clock-")
        cls.output = Path(cls.temporary.name)
        subprocess.run(
            ["javac", "-d", str(cls.output), str(PROBE), str(CONTRACT)],
            capture_output=True, text=True, timeout=60, check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_contract(self, mode: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["FC_SCHED_QUEUE_CPU_PROBE"] = mode
        return subprocess.run(
            ["java", "-cp", str(self.output),
             "dev.functioncompiler.SchedulerQueueCpuProbeContract", mode],
            env=env, capture_output=True, text=True, timeout=60, check=False,
        )

    def test_off_is_inert(self):
        result = self.run_contract("off")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=off valid=true", result.stdout)

    def test_empty_clock_control(self):
        result = self.run_contract("empty")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=empty valid=true", result.stdout)

    def test_timed_nested_intervals(self):
        result = self.run_contract("timed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=timed valid=true", result.stdout)

    def test_invalid_mode_fails_closed(self):
        result = self.run_contract("unsupported")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FC_SCHED_QUEUE_CPU_PROBE", result.stderr)

    def test_other_profiler_fails_closed(self):
        env = os.environ.copy()
        env["FC_SCHED_QUEUE_CPU_PROBE"] = "timed"
        env["FC_COMMAND_CALLBACK_METRICS"] = "true"
        result = subprocess.run(
            ["java", "-cp", str(self.output),
             "dev.functioncompiler.SchedulerQueueCpuProbeContract", "timed"],
            env=env, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FC_COMMAND_CALLBACK_METRICS", result.stderr)


if __name__ == "__main__":
    unittest.main()
