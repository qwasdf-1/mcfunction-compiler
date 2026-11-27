"""IR-038 admission, optimizer and native test contracts."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "src/main/java/dev/functioncompiler"
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir038 as native


class IR038(unittest.TestCase):
    def test_extended_admission_and_all_comparison_operators(self):
        ir = (JAVA / "TypedScoreIR.java").read_text()
        cond = (JAVA / "ScoreConditionCommand.java").read_text()
        op = (JAVA / "ScoreOperationCommand.java").read_text()
        self.assertIn('TypedCompilerConfiguration.flag("FC_TYPED_IR_EXTENDED_SCORE")', ir)
        self.assertIn("MINIMUM, MAXIMUM", ir)
        self.assertIn("exactly one predicate kind required", ir)
        self.assertIn("comparison != null", ir)
        self.assertIn("comparisonHolder, comparisonSelf), comparisonObjective", ir)
        self.assertIn("IR_COMPARISON.matcher", cond)
        self.assertIn("if (operator != expected) return null", cond)
        for symbol, name in (("=", "EQUALS"), ("<", "LESS_THAN"),
                             ("<=", "LESS_THAN_OR_EQUAL"), (">", "GREATER_THAN"),
                             (">=", "GREATER_THAN_OR_EQUAL")):
            self.assertIn(f'case "{symbol}" -> Operator.{name}', cond)
        for symbol, name in (("<", "MINIMUM"), (">", "MAXIMUM")):
            self.assertIn(f'case "{symbol}" -> TypedScoreIR.extendedScoreEnabled()', op)
            self.assertIn(f"TypedScoreIR.BinaryOperator.{name} : null", op)
        self.assertIn("ARITHMETIC || !exceptionalSourceShape(source)", op)

    def test_canonical_opcode_and_both_backends(self):
        optimizer = (JAVA / "TypedIROptimizer.java").read_text()
        ir = (JAVA / "TypedScoreIR.java").read_text()
        asm = (JAVA / "TypedScoreIRBytecode.java").read_text()
        for term in ("case MINIMUM -> Op.MIN_SCORE", "case MAXIMUM -> Op.MAX_SCORE"):
            self.assertEqual(optimizer.count(term), 2)
        for op in ("MIN_SCORE", "MAX_SCORE"):
            self.assertIn(op, ir)
            self.assertIn(op, asm)
        self.assertIn('INVOKESTATIC, "java/lang/Math"', asm)
        self.assertIn('INVOKEINTERFACE, SCORE, "set"', asm)
        self.assertIn("Math.min(score.get(), operand)", ir)

    def test_same_slot_read_elision_preserves_missing_rows_and_effects(self):
        prepared = (JAVA / "TypedIRPreparedSteps.java").read_text()
        runtime = (JAVA / "TypedScoreIRRuntime.java").read_text()
        for t in ("samePredicateSlot", "guard.conditionSelf() == guard.comparisonSelf()",
                  "guard.conditionObjective().equals(guard.comparisonObjective())",
                  "unsound comparison alias metadata", "comparisonSharesTargetObjective",
                  "comparisonSharesGuardObjective", "operandSharesComparisonObjective"):
            self.assertIn(t, prepared)
        self.assertIn("if (info == null)", runtime)
        self.assertIn("if (prepared.comparisonSameSlot())", runtime)
        self.assertIn("right = info;", runtime)
        self.assertIn("comparisonReadReused()", runtime)
        self.assertIn("scoreboard.getPlayerScoreInfo(comparisonHolder, comparisonObjective)", runtime)
        self.assertIn("ScoreConditionCommand.compareScores(", runtime)
        self.assertLess(runtime.index("if (info == null)"), runtime.index("right = info;"))
        self.assertLess(runtime.index("comparisonObjective = scoreboard.getObjective"),
                        runtime.index("context.incrementCost();"))
        self.assertIn("new QueuedTail(source, instructions, nextIndex)", runtime)

    def test_focused_native_suite_covers_on_off_and_legacy(self):
        self.assertEqual(native.ARMS, ("native", "old_bytecode", "interpreted", "bytecode", "direct"))
        self.assertEqual(len(native.CASES), 13)
        self.assertEqual(len(native.QUOTAS), 8)
        self.assertEqual(native.EXPECTED["ir017_ir038_missing_rows"]["never_score"], None)
        self.assertEqual(native.EXPECTED["ir017_ir038_comparisons"]["x"], 127)
        self.assertIn("ir017_reentrant", native.LEGACY)
        self.assertEqual(native.stat("other_ir038_comparisons=0 ir038_comparisons=12",
                                     "ir038_comparisons"), 12)
        with self.assertRaises(AssertionError):
            native.stat("other_ir038_comparisons=0", "ir038_comparisons")


if __name__ == "__main__":
    unittest.main()
