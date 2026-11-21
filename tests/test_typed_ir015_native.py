"""IR-015 real native event acceptance contracts, not CPU benchmark assertions."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir015_native as study


class RealEventIR015(unittest.TestCase):
    def test_unchanged_real_source_and_same_wrapper_path(self):
        runner = (ROOT / "scripts/run_veinminer_profile.py").read_text()
        self.assertIn('"typed_ir_status_before": typed_ir_status_before', runner)
        self.assertIn('"typed_ir_status_after": typed_ir_status_after', runner)
        source = (ROOT / "scripts/ci_typed_ir015_native.py").read_text()
        for token in ("--stack", "--compiler-mode", '"wrapper"',
                      "--no-spark", "--side", '"6"', "STATE_FIELDS",
                      "valid_native_workload", "work_expected",
                      "native_parity", "runtime_ir_execution_confirmed"):
            self.assertIn(token, source)

    def test_explicit_namespace_and_opt_in(self):
        baseline, compiled = (study.options(mode) for mode in study.STUDY_MODES)
        self.assertEqual(study.STUDY_MODES, ("wrapper", "typed_ir"))
        self.assertEqual(baseline["FC_TYPED_IR_MODE"], "")
        self.assertEqual(compiled["FC_TYPED_IR_MODE"], "bytecode")
        self.assertEqual(compiled["FC_TYPED_IR_NAMESPACE"], "vm")
        self.assertEqual(compiled["FC_TYPED_IR_REENTRANT_SAFE"], "true")
        for settings in (baseline, compiled):
            self.assertEqual(settings["FC_TYPED_IR_DIRECT_FUNCTION"], "false")
            self.assertEqual(settings["FC_TYPED_IR_SCORE_CACHE"], "false")
            self.assertEqual(settings["FC_TYPED_IR_SINGLETON_FEEDBACK"], "false")
            self.assertEqual(settings["FC_FUSED_REGION_PROTOTYPE"], "false")

    def test_typed_only_parser_rejects_unsupported_before_mutating_context(self):
        base = ROOT / "src/main/java/dev/functioncompiler"
        parser = (base / "ScoreAddPrototype.java").read_text()
        mutation = (base / "ScoreAddCommand.java").read_text()
        binary = (base / "ScoreOperationCommand.java").read_text()
        guard = (base / "ScoreConditionCommand.java").read_text()
        for token in (
            "boolean typedOnly = TypedScoreIR.enabledFor(functionId)",
            "ScoreAddCommand.typedIrLiteralSourceShape(input)",
            "ScoreOperationCommand.typedIrLiteralSourceShape(input)",
            "ScoreConditionCommand.typedIrLiteralGuardShape(input)",
            "if (!acceptedShape) return;",
        ):
            self.assertIn(token, parser)
        self.assertLess(parser.index("if (!acceptedShape) return;"),
                        parser.index("compileChainedModifiers(buildContexts, chain, functionId)"))
        self.assertIn("IR_LITERAL_SOURCE.matcher(source).matches()", mutation)
        self.assertIn("IR_LITERAL_BINARY_SOURCE.matcher(source).matches()", binary)
        self.assertIn("IR_GUARD.matcher(input)", guard)
        self.assertIn("matcher.matches()", guard)

    def test_diagnostic_counting_guards(self):
        self.assertEqual(study.counted("compiled_regions=4 executed_steps=22", "compiled_regions"),4)
        self.assertEqual(study.counted("compiled_regions=4 executed_steps=22", "executed_steps"),22)
        with self.assertRaises(AssertionError):
            study.counted("IR008 disabled", "executed_steps")
        src = (ROOT / "scripts/ci_typed_ir015_native.py").read_text()
        self.assertIn('"performance_claim": False', src)
        self.assertIn('"production_promotion": False', src)
        self.assertIn('if a["state"] != b["state"]', src)


if __name__ == "__main__":
    unittest.main()
