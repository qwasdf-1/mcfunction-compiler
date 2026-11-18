"""Standalone JDK25 contracts for exact parent-matched modifier/dispatch/command timing."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=(
    ROOT/"src/main/java/dev/functioncompiler/SchedulerPathCensus.java",
    ROOT/"src/main/java/dev/functioncompiler/SchedulerTaskCpuProbe.java",
    ROOT/"src/main/java/dev/functioncompiler/SchedulerPhaseCpuProbe.java",
    ROOT/"tests/java/dev/functioncompiler/SchedulerPhaseCpuProbeContract.java",
)

class PhaseCpuClockContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="scheduler-phases-")
        cls.path=Path(cls.temp.name)
        subprocess.run(
            ["javac","-d",str(cls.path),*[str(p) for p in JAVA]],
            check=True,text=True,capture_output=True,timeout=60
        )
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def mode(self,mode,parent=None,**extras):
        env=os.environ.copy()
        env["FC_SCHED_PATH_CENSUS"]="true"
        env["FC_SCHED_TASK_CPU_PROBE"]=mode if parent is None else parent
        env["FC_SCHED_PHASE_CPU_PROBE"]=mode
        env.update(extras)
        return subprocess.run([
            "java","-cp",str(self.path),
            "dev.functioncompiler.SchedulerPhaseCpuProbeContract",mode,
        ],env=env,text=True,capture_output=True,timeout=75)

    def test_all_three_modes(self):
        for mode in ("off","empty","timed"):
            with self.subTest(mode=mode):
                r=self.mode(mode)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn(f"mode={mode} valid=true",r.stdout)

    def test_invalid_mode_is_rejected(self):
        r=self.mode("bad")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("FC_SCHED_PHASE_CPU_PROBE",r.stderr)

    def test_different_parent_mode_is_rejected(self):
        r=self.mode("timed",parent="empty")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("differs",r.stderr)

    def test_conflicting_callback_metrics_fails_closed(self):
        r=self.mode("empty",FC_COMMAND_CALLBACK_METRICS="true")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("FC_COMMAND_CALLBACK_METRICS",r.stderr)

if __name__=="__main__":
    unittest.main()
