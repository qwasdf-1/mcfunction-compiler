"""JDK 25 contracts for nested Brigadier plumbing timing and failure labels."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
    ROOT/"src/main/java/dev/functioncompiler/SchedulerPathCensus.java",
    ROOT/"src/main/java/dev/functioncompiler/SchedulerTaskCpuProbe.java",
    ROOT/"src/main/java/dev/functioncompiler/SchedulerPhaseCpuProbe.java",
    ROOT/"tests/java/dev/functioncompiler/SchedulerPhaseCpuProbeContract.java",
]

class PlumbingClockContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="sched-plumbing-jdk-")
        cls.bin=Path(cls.temp.name)
        subprocess.run(["javac","-d",str(cls.bin),*[str(x) for x in SOURCES]],
                       check=True,text=True,capture_output=True,timeout=90)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def invoke(self,mode:str,extra=None)->subprocess.CompletedProcess:
        env=os.environ.copy()
        env["FC_SCHED_PATH_CENSUS"]="true"
        env["FC_SCHED_TASK_CPU_PROBE"]=mode
        env["FC_SCHED_PHASE_CPU_PROBE"]=mode
        env["FC_SCHED_BRIGADIER_PLUMBING_PROBE"]="true"
        if extra:env.update(extra)
        return subprocess.run(["java","-cp",str(self.bin),
            "dev.functioncompiler.SchedulerPhaseCpuProbeContract",mode],
            env=env,text=True,capture_output=True,timeout=90)

    def test_off_empty_timed(self):
        for mode in ("off","empty","timed"):
            with self.subTest(mode=mode):
                p=self.invoke(mode)
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertIn("valid=true",p.stdout)

    def test_mismatched_parent_clock_rejected(self):
        p=self.invoke("timed",{"FC_SCHED_TASK_CPU_PROBE":"empty"})
        self.assertNotEqual(p.returncode,0)
        self.assertIn("differs",p.stderr)

    def test_invalid_mode_rejected(self):
        p=self.invoke("bad")
        self.assertNotEqual(p.returncode,0)

if __name__=="__main__":
    unittest.main()
