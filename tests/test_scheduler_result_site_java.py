"""Plain JDK test for selected synthetic callback site classification, no MC."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"src/main/java/dev/functioncompiler/SchedulerResultSiteTrace.java"
STUBS={
"dev/functioncompiler/SchedulerTaskCpuProbe.java":'''
package dev.functioncompiler;
public final class SchedulerTaskCpuProbe {
    public enum Path { EXECUTE }
    public static boolean activeSampled(Path p) { return true; }
}
''',
"dev/functioncompiler/SchedulerPhaseCpuProbe.java":'''
package dev.functioncompiler;
public final class SchedulerPhaseCpuProbe {
    public static final long SKIP=Long.MIN_VALUE;
    public static final long NESTED=Long.MIN_VALUE+1;
    public static String modeName() { return "timed"; }
}
''',
"dev/functioncompiler/SiteContract.java":'''
package dev.functioncompiler;
public final class SiteContract {
    public static void main(String[] args) {
        Thread.currentThread().setName("Server thread");
        for (int i=0;i<100;i++) {
            SchedulerResultSiteTrace.openSelectedScope();
            if (i<40) {
                SchedulerResultSiteTrace.observeSite(
                        SchedulerResultSiteTrace.Site.SCORE_STORE);
            }
            SchedulerResultSiteTrace.closeSelectedScope(42L,i<40?1000L:5L);
        }
        System.out.println(SchedulerResultSiteTrace.summary());
    }
}
''',
}

class SiteJavaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="sched-028-site-jdk-")
        cls.root=Path(cls.tmp.name)
        sources=[TARGET]
        for rel,txt in STUBS.items():
            path=cls.root/rel
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(txt,encoding="utf-8")
            sources.append(path)
        subprocess.run(["javac","-d",str(cls.root),*[str(s) for s in sources]],
                       check=True,text=True,capture_output=True,timeout=60)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def invoke(self,enabled):
        env=os.environ.copy()
        env["FC_SCHED_RESULT_SITE_TRACE"]="true" if enabled else "false"
        return subprocess.run(["java","-cp",str(self.root),
            "dev.functioncompiler.SiteContract"],env=env,text=True,
            capture_output=True,timeout=30)
    def test_enabled_site_cpu_conservation(self):
        p=self.invoke(True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("callbacks=100",p.stdout)
        self.assertIn("raw_cpu_ns=40300",p.stdout)
        self.assertIn("SCORE_STORE|40|40000",p.stdout)
        self.assertIn("NO_SITE|60|300",p.stdout)
        self.assertIn("MULTIPLE|0|0",p.stdout)
    def test_disabled_by_default(self):
        p=self.invoke(False)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("enabled=false",p.stdout)
        self.assertIn("callbacks=0",p.stdout)
        self.assertIn("SCORE_STORE|0|0",p.stdout)

if __name__=="__main__":
    unittest.main()
