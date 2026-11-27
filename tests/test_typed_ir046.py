"""IR046 structural contracts; native suite is the semantic oracle."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class IR046(unittest.TestCase):
    def test_boundary(self):
        java=ROOT/"src/main/java/dev/functioncompiler"
        r=(java/"TypedScoreIRRuntime.java").read_text()
        self.assertIn("activeGuardRun == priorFailedRun",r)
        self.assertIn("priorFailedRun = activeGuardRun",r)
        self.assertIn("clearGuardRun();\n            if (quota() <= 0)",r)
        self.assertIn("clearGuardRun();\n            TypedScoreIR.compoundFallback()",r)
        self.assertIn("context instanceof ReentrantQueueEpoch",r)
        self.assertIn("inheritedGuardBits & bit",r)
        p=(java/"GuardRunReuse.java").read_text()
        for token in ("compound.predicates().size() != 2","!b.equals(target)","first.unless()","Mutation","Operation.SET"):
            self.assertIn(token,p)
        self.assertNotIn("ScoreAccess",p)
        self.assertNotIn("ScoreValueRevision",p)
    def test_flag(self):
        p=(ROOT/"src/main/java/dev/functioncompiler/GuardRunReuse.java").read_text()
        self.assertIn('System.getenv("FC_TYPED_IR_GUARD_RUN_REUSE")',p)
        self.assertIn('System.getenv("FC_TYPED_IR046_BENCHMARK")',p)
if __name__=="__main__":unittest.main()
