"""Plain Java 25 contract for 1/32 deterministic per-method sparse CPU clocks."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAVA=[
    ROOT/"src/main/java/dev/functioncompiler/SchedulerPathCensus.java",
    ROOT/"src/main/java/dev/functioncompiler/SchedulerTaskCpuProbe.java",
    ROOT/"tests/java/dev/functioncompiler/SchedulerTaskCpuProbeContract.java",
]

class TestSparseTaskCpu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="sched-task-cpu-")
        cls.out=Path(cls.tmp.name)
        subprocess.run(["javac","-d",str(cls.out),*[str(p) for p in JAVA]],
                       check=True,text=True,capture_output=True,timeout=60)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def run_contract(self,mode:str,**additional):
        env=os.environ.copy()
        env["FC_SCHED_PATH_CENSUS"]="true"
        env["FC_SCHED_TASK_CPU_PROBE"]=mode
        env.update(additional)
        return subprocess.run(["java","-cp",str(self.out),
            "dev.functioncompiler.SchedulerTaskCpuProbeContract",mode],
            env=env,text=True,capture_output=True,timeout=60)
    def test_plain(self):
        p=self.run_contract("off")
        self.assertEqual(p.returncode,0,p.stderr)
    def test_empty_clock(self):
        p=self.run_contract("empty")
        self.assertEqual(p.returncode,0,p.stderr)
    def test_timed_clock(self):
        p=self.run_contract("timed")
        self.assertEqual(p.returncode,0,p.stderr)
    def test_invalid_mode(self):
        p=self.run_contract("incorrect")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("FC_SCHED_TASK_CPU_PROBE",p.stderr)
    def test_incompatible_metrics(self):
        p=self.run_contract("empty",FC_COMMAND_CALLBACK_METRICS="true")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("FC_COMMAND_CALLBACK_METRICS",p.stderr)

if __name__=="__main__":
    unittest.main()
