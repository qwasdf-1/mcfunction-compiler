"""IR-017 static contracts. Only actual Minecraft differential execution proves parity."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir017 as native


def java(name: str) -> str:
    return (ROOT / "src/main/java/dev/functioncompiler" / name).read_text()


class IR017ConditionalRanges(unittest.TestCase):
    def test_parsed_inclusive_range_and_feature_gate(self):
        condition = java("ScoreConditionCommand.java")
        for token in (
            'System.getenv("FC_TYPED_IR_RANGE_GUARDS")',
            'IR_RANGE', 'IR_BINARY', 'IR_MUTATION', 'matcher.matches()',
            'sameParsedRange(range, matcher.group(4))',
            'Integer.MIN_VALUE', 'Integer.MAX_VALUE',
            'parsed.matches(lower)', 'parsed.matches(upper)',
            'parsed.matches(lower - 1)', 'parsed.matches(upper + 1)',
            'typedIrLiteralGuardShape', 'RANGE_GUARDS_ENABLED',
            'targetHolder', 'score.toMutation(parsed, matcher.group(5))',
            'binary.toBinary(parsed, matcher.group(5))',
        ):
            self.assertIn(token, condition)
        self.assertIn('!matcher.group(4).contains("..")', condition)
        self.assertIn('innerCommand instanceof ScoreOperationCommand', condition)

    def test_guarded_binary_does_not_skip_operation_argument_validation(self):
        op=java("ScoreOperationCommand.java")
        self.assertIn('return toBinary(parsed, parsed.commandInput())', op)
        self.assertIn('TypedScoreIR.Binary toBinary(', op)
        self.assertIn('parsed.command().getTopContext()', op)
        self.assertIn('words[5]', op)
        self.assertIn('default -> null', op)

    def test_semantic_ir_and_asm_emit_direct_terminal(self):
        ir=java("TypedScoreIR.java")
        asm=java("TypedScoreIRBytecode.java")
        self.assertIn("Instruction terminal,", ir)
        self.assertIn("terminal instanceof Mutation || terminal instanceof Binary", ir)
        self.assertIn("condition.terminal() instanceof Binary", ir)
        self.assertIn('" guarded_binary_steps="', ir)
        self.assertIn("if (terminal instanceof Binary binary)", ir)
        self.assertIn('if (terminal instanceof TypedScoreIR.Binary binary)', asm)
        self.assertIn("emitBinary(method, binary)", asm)
        self.assertIn("emitMutation(method, (TypedScoreIR.Mutation) terminal)", asm)
        self.assertNotIn('method.visitMethodInsn(INVOKESTATIC, STATE, "executeStep"', asm)

    def test_runtime_checks_all_objectives_before_writes_and_feedback(self):
        src=java("TypedScoreIRRuntime.java")
        for token in ("Objective guardObjective", "Objective operandObjective",
                      "guard.conditionObjective()", "binary.sourceObjective()",
                      "return original(instruction)", "condition.range().matches",
                      "condition.unless()", "context.incrementCost()",
                      "TypedScoreIR.skippedConditional()", "sourceAccess()",
                      "TypedScoreIR.Instruction terminal", "ScoreboardCommandAccessor",
                      "CommandResponseTracker.create()"):
            self.assertIn(token, src)
        self.assertLess(src.index("Objective guardObjective"),
                        src.index("context.incrementCost();"))
        self.assertIn("terminal instanceof TypedScoreIR.Binary", src)

    def test_native_fixture_real_functions_and_guarded_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            native.fixture(Path(tmp))
            folder=Path(tmp)/"world/datapacks"/native.PACK/"data/fc_ir/function"
            for name,commands in native.FUNCTIONS.items():
                self.assertEqual(
                    (folder/(name+".mcfunction")).read_text().splitlines(), commands)
        self.assertEqual(native.MODES, ("native", "old_bytecode",
                                         "interpreted", "bytecode", "direct"))
        self.assertEqual(len(native.QUOTAS), 13)
        self.assertEqual(native.EXPECTED["ir017_inclusive"]["x"], 6)
        self.assertEqual(native.EXPECTED["ir017_guarded_binary"]["x"], 13)
        self.assertEqual(native.EXPECTED["ir017_reentrant"]["ir014_marker"], 11)
        self.assertEqual(native.EXPECTED["ir017_reentrant"]["x"], 14)
        for mode in native.MODES:
            flags=native.options(mode)
            self.assertEqual(flags["FC_TYPED_IR_RANGE_TEST_HARNESS"],"true")
            self.assertEqual(flags["FC_TYPED_IR_REENTRANT_SAFE"],"true")
            self.assertEqual(flags["FC_TYPED_IR_REENTRANT_TEST_OBSERVER"],"true")
            self.assertEqual(flags["FC_TYPED_IR_RANGE_GUARDS"],
                             "true" if mode in native.MODES[2:] else "false")
            self.assertEqual(flags["FC_FUSED_REGION_PROTOTYPE"],"false")
            self.assertEqual(flags["FC_TYPED_IR_SCORE_CACHE"],"false")
        self.assertIn('id.getPath().matches("ir017_[a-z0-9_]+")',
                      java("ProbeCommands.java"))

    def test_rejects_performance_and_production_promotion(self):
        source=(ROOT/"scripts/ci_typed_ir017.py").read_text()
        self.assertIn('"performance_claim": False', source)
        self.assertIn('"production_promotion": False', source)
        self.assertIn('if observed != reference[case]', source)
        self.assertIn("if stat(report[\"diagnostic\"], \"guarded_binary_steps\")", source)


if __name__ == "__main__":
    unittest.main()
