"""Compile actual bounded Java callback histogram using JDK-only fake MC contracts.

This is not a Minecraft semantic test. It catches compiler, conservation,
class-normalization, plain-off and response-size issues before native boot.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"src/main/java/dev/functioncompiler/SchedulerResultDelegateTrace.java"
STUBS={
"net/minecraft/commands/CommandResultCallback.java":'''
package net.minecraft.commands;
public interface CommandResultCallback {
    CommandResultCallback EMPTY = (success,result) -> {};
    void onResult(boolean success,int result);
}
''',
"net/minecraft/commands/ExecutionCommandSource.java":'''
package net.minecraft.commands;
public interface ExecutionCommandSource<T extends ExecutionCommandSource<T>> {
    CommandResultCallback callback();
}
''',
"dev/functioncompiler/SchedulerPhaseCpuProbe.java":'''
package dev.functioncompiler;
public final class SchedulerPhaseCpuProbe {
    public static final long SKIP=Long.MIN_VALUE;
    public static final long NESTED=Long.MIN_VALUE+1L;
    public static String modeName() { return "timed"; }
}
''',
"dev/functioncompiler/DelegateContract.java":'''
package dev.functioncompiler;
import net.minecraft.commands.CommandResultCallback;
import net.minecraft.commands.ExecutionCommandSource;
public final class DelegateContract {
    private static final class RealCallback implements CommandResultCallback {
        public void onResult(boolean success,int result) {}
    }
    private record Source(CommandResultCallback callback)
            implements ExecutionCommandSource<Source> {}
    public static void main(String[] args) {
        Thread.currentThread().setName("Server thread");
        Source first = new Source(new RealCallback());
        Source empty = new Source(CommandResultCallback.EMPTY);
        for (int i=0;i<100;i++) {
            SchedulerResultDelegateTrace.observe(first,true,20L,5000L);
        }
        for (int i=0;i<10;i++) {
            SchedulerResultDelegateTrace.observe(empty,false,20L,0L);
        }
        // Never record unselected scopes.
        SchedulerResultDelegateTrace.observe(first,true,
                SchedulerPhaseCpuProbe.SKIP,100L);
        System.out.println(SchedulerResultDelegateTrace.summary());
    }
}
'''
}

class DelegateJavaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="sched-028-javac-")
        cls.root=Path(cls.temp.name)
        files=[TARGET]
        for rel,contents in STUBS.items():
            path=cls.root/rel
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(contents,encoding="utf-8")
            files.append(path)
        subprocess.run(["javac","-d",str(cls.root),*[str(f) for f in files]],
                       capture_output=True,text=True,check=True,timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def invoke(self,enabled:bool):
        env=os.environ.copy()
        env["FC_SCHED_RESULT_DELEGATE_TRACE"]="true" if enabled else "false"
        return subprocess.run(["java","-cp",str(self.root),
            "dev.functioncompiler.DelegateContract"],env=env,
            text=True,capture_output=True,timeout=30)

    def test_enabled_class_histogram_conserves_sampled_cpu_and_outcomes(self):
        p=self.invoke(True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("enabled=true",p.stdout)
        self.assertIn("calls=110",p.stdout)
        self.assertIn("timed_samples=110",p.stdout)
        self.assertIn("raw_cpu_ns=500000",p.stdout)
        self.assertIn("success=100",p.stdout)
        self.assertIn("failure=10",p.stdout)
        self.assertIn("DelegateContract$RealCallback|100|500000|100|100|0",p.stdout)
        self.assertIn("EMPTY|10|0|10|0|10",p.stdout)

    def test_disabled_mode_inert(self):
        p=self.invoke(False)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("enabled=false",p.stdout)
        self.assertIn("calls=0",p.stdout)
        self.assertIn("types=",p.stdout)

if __name__=="__main__":
    unittest.main()
