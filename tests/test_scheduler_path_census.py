"""Standalone Java 25 test for off/on native execution-task counter behavior."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/main/java/dev/functioncompiler/SchedulerPathCensus.java"
CONTRACT = ROOT / "tests/java/dev/functioncompiler/SchedulerPathCensusContract.java"

class SchedulerPathCensusContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sched-path-census-")
        cls.workdir = Path(cls.temp.name)
        subprocess.run(["javac","-d",str(cls.workdir),str(SOURCE),str(CONTRACT)],
                       check=True, capture_output=True, text=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_default_disabled(self):
        env = os.environ.copy()
        env.pop("FC_SCHED_PATH_CENSUS", None)
        proc = subprocess.run(["java","-cp",str(self.workdir),
            "dev.functioncompiler.SchedulerPathCensusContract","off"],
            env=env, text=True,capture_output=True,timeout=60)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn("mode=off valid=true",proc.stdout)

    def test_enabled_event_window(self):
        env = os.environ.copy()
        env["FC_SCHED_PATH_CENSUS"] = "true"
        proc = subprocess.run(["java","-cp",str(self.workdir),
            "dev.functioncompiler.SchedulerPathCensusContract","on"],
            env=env, text=True,capture_output=True,timeout=60)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertIn("mode=on valid=true",proc.stdout)

if __name__=="__main__":
    unittest.main()
