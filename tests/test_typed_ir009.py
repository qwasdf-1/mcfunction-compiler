"""IR-009 contracts: effect barriers, direct operation lowering and native cases."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir008 as native


def source(name: str) -> str:
    return (ROOT / f"src/main/java/dev/functioncompiler/{name}.java").read_text()


class TypedIR009(unittest.TestCase):
    def test_binary_and_conditional_test_corpus_is_not_only_plain_add(self):
        for key in ("binary", "binary_self", "guarded", "guard_absent",
                    "guard_missing_objective", "binary_division_barrier"):
            self.assertGreaterEqual(len(native.FUNCTIONS[key]), 3)
        self.assertTrue(any("scoreboard players operation" in command
                            for command in native.FUNCTIONS["binary"]))
        self.assertTrue(any("execute unless score" in command
                            for command in native.FUNCTIONS["guarded"]))
        self.assertTrue(any("execute if score" in command
                            for command in native.FUNCTIONS["guarded"]))
        self.assertTrue(any(" /= " in command
                            for command in native.FUNCTIONS["binary_division_barrier"]))
        self.assertIn(1, native.QUOTAS)

    def test_semantic_ir_has_explicit_effects_and_feedback_barriers(self):
        ir = source("TypedScoreIR")
        for token in ("sealed interface Instruction", "record Binary(", "record Conditional(",
                      "record Effects(", "observableBoundary", "return !observableBoundary",
                      "Set.copyOf", "conditionHolder", "sourceHolder"):
            self.assertIn(token, ir)
        self.assertIn("case MULTIPLY", ir)
        self.assertIn("case ASSIGN", ir)

    def test_only_four_binary_operations_are_lowered(self):
        op = source("ScoreOperationCommand")
        for token in ('case "="', 'case "+="', 'case "-="', 'case "*="'):
            self.assertIn(token, op)
        self.assertIn('default -> null', op)
        self.assertIn('!words[3].startsWith("#")', op)
        self.assertIn('!words[6].startsWith("#")', op)

    def test_only_a_literal_score_matches_and_a_typed_terminal_are_lowered(self):
        condition = source("ScoreConditionCommand")
        self.assertIn("matcher.group(5)", condition)
        self.assertIn("score.toMutation", condition)
        self.assertIn("range.matches", condition)
        self.assertIn("lower - 1", condition)
        self.assertIn("upper + 1", condition)
        self.assertIn("sameParsedRange(range, matcher.group(4))", condition)
        self.assertIn("isTargetSelf", condition)
        self.assertIn("operator != null", condition)

    def test_asm_contains_direct_binary_calls_and_generated_branches(self):
        asm = source("TypedScoreIRBytecode")
        for token in ('"sourceAccess"', '"get"', '"add"', '"set"',
                      "IMUL", "INEG", "IF_ICMPEQ", "emitBinary(", "emitMutation("):
            self.assertIn(token, asm)
        self.assertNotIn('method.visitMethodInsn(INVOKESTATIC, STATE, "executeStep"', asm)
        self.assertNotIn('method.visitMethodInsn(INVOKESTATIC, STATE, "runExecutable"', asm)

    def test_guard_runtime_preserves_mod_stage_charge_and_failure_semantics(self):
        runtime = source("TypedScoreIRRuntime")
        for token in ("ReadOnlyScoreInfo", "getPlayerScoreInfo",
                      "condition.range().matches", "condition.unless()",
                      "context.incrementCost()", "quota() < 0",
                      "traceReturn(instruction, 0)", "FusedRegionPrototype.executeCommand",
                      "getOrCreatePlayerScore", "sendFeedback"):
            self.assertIn(token, runtime)
        self.assertIn("ScoreboardCommandAccessor.functionCompiler$getScoreOperationResponse()", runtime)

    def test_missing_objective_and_low_quota_are_native_cases(self):
        runner = (ROOT / "scripts/ci_typed_ir008.py").read_text()
        for token in ("guard_missing_objective_before", "guard_missing_objective_after",
                      "guard_quota_", "binary_quota_", "binary_steps",
                      "conditional_steps", "conditional_skips"):
            self.assertIn(token, runner)


if __name__ == "__main__":
    unittest.main()
