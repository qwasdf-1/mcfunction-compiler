"""IR047 preflight lifetime and isolated experiment contracts."""
import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir047 as native
import ci_typed_ir047_cpu as cpu

class IR047(unittest.TestCase):
    def test_preflight(self):
        java=ROOT/"src/main/java/dev/functioncompiler"
        r=(java/"TypedScoreIRRuntime.java").read_text()
        p=r.split("private int startCompound(",1)[1].split("private void clearGuardRun()",1)[0]
        self.assertIn("this.reusePreflight = reuseGuards && GuardPreflightReuse.enabled()",r)
        self.assertIn("prepared.guardRun() == priorFailedRun",p)
        self.assertLess(p.index("context.tracer()"),p.index("boolean sameRun"))
        self.assertIn("if (reusePreflight && sameRun)",p)
        self.assertIn("GuardPreflightReuse.reused(plan.objectives().size(), plan.slots().size())",p)
        self.assertIn("scoreboard.getObjective(plan.objectives().get(i))",p)
        self.assertIn("operand.self() ? source.getEntity() : operand.holder()",p)
        self.assertIn("getCriteria().isReadOnly()",p)
        self.assertNotIn("incrementCost()",p)
        self.assertIn("clearGuardRun();\n            if (quota() <= 0)",r)
        self.assertIn("clearGuardRun();\n            TypedScoreIR.compoundFallback()",r)
        h=(java/"GuardPreflightReuse.java").read_text()
        self.assertIn('System.getenv("FC_TYPED_IR_GUARD_PREFLIGHT_REUSE")',h)
        self.assertNotIn("ScoreAccess",h)
        self.assertNotIn("Scoreboard",h)
        self.assertNotIn("ScoreValueRevision",h)
    def test_fixtures(self):
        old=native.options("old_bytecode")
        new=native.options("bytecode")
        for f in (old,new): self.assertEqual(f["FC_TYPED_IR_GUARD_RUN_REUSE"],"true")
        self.assertEqual(old["FC_TYPED_IR_GUARD_PREFLIGHT_REUSE"],"false")
        self.assertEqual(new["FC_TYPED_IR_GUARD_PREFLIGHT_REUSE"],"true")
        for suffix in ("drop","recreate","shape"):
            self.assertIn("ir017_ir046_"+suffix,native.ROOTS)
        self.assertEqual(cpu.ARMS,("base","reuse"))
        self.assertEqual(cpu.options("bytecode")["FC_TYPED_IR_DIAGNOSTICS"],"false")
        self.assertEqual(cpu.protocol.AA_LIMIT,.05)
        self.assertEqual(cpu.protocol.MIN_REDUCTION,.05)
        self.assertEqual(cpu.protocol.BOOTS,2)
if __name__=="__main__":unittest.main()
