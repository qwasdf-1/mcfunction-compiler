"""IR-018 source-context runtime and native barrier contract checks."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir018 as run


def java(name: str) -> str:
    return (ROOT / "src/main/java/dev/functioncompiler" / name).read_text()


class DynamicSelfAndCallBarriers(unittest.TestCase):
    def test_opt_in_and_parsed_source_gates(self):
        ir = java("TypedScoreIR.java")
        mut = java("ScoreAddCommand.java")
        binary = java("ScoreOperationCommand.java")
        guard = java("ScoreConditionCommand.java")
        for token in (
            'System.getenv("FC_TYPED_IR_SELF_HOLDER")',
            "boolean holderSelf", "boolean sourceSelf",
            "boolean conditionSelf", "slotName(",
        ):
            self.assertIn(token, ir)
        for token in (
            "TypedScoreIR.selfHolderEnabled()",
            '"@s"', "isSelfSelector",
            "isSelfSelector, objectiveName",
        ):
            self.assertIn(token, mut)
        for token in (
            "TypedScoreIR.selfHolderEnabled()",
            "isTargetSelf ? ", "isSourceSelf ? ",
            "sourceHolder, isSourceSelf",
        ):
            self.assertIn(token, binary)
        for token in (
            "TypedScoreIR.selfHolderEnabled()",
            "isTargetSelf ? ", "isTargetSelf, targetObjective",
            "sameParsedRange(range, matcher.group(4))",
        ):
            self.assertIn(token, guard)

    def test_runtime_selector_is_resolved_per_invocation(self):
        runtime=java("TypedScoreIRRuntime.java")
        self.assertIn("source.getEntity()", runtime)
        self.assertIn("if (target == null) return original(instruction);", runtime)
        self.assertIn("guard.conditionSelf()", runtime)
        self.assertIn("binary.sourceSelf()", runtime)
        self.assertIn("targetResolved", runtime)
        self.assertIn("sourceResolved", runtime)
        self.assertIn("response.track(targetResolved, newScore)", runtime)
        self.assertIn("sourceResolved.getScoreboardName()", runtime)
        self.assertLess(runtime.index("if (target == null) return original(instruction);"),
                        runtime.index("context.incrementCost();"))

    def test_dispatch_is_opaque_function_barrier_not_custom_executor(self):
        mixed=java("MixedFunctionIR.java")
        for token in ("FUNCTION_DISPATCH", "isFunctionDispatch(entry)",
                      "DISPATCH_SOURCE", "ir018_dispatch_barriers",
                      "dispatchBarrierCount()", "directBytecodeChunks()"):
            self.assertIn(token, mixed)
        self.assertIn("nodes.add(new OpaqueBarrier(index, entry", mixed)
        self.assertNotIn("queueFunctionFromDirectCursor", mixed)

    def test_real_entity_source_and_unbound_source_fixture(self):
        self.assertEqual(run.MODES, (
            "native", "old_bytecode", "interpreted", "bytecode", "direct"))
        self.assertIn("ir018_dispatch", run.FUNCTIONS)
        self.assertIn("ir018_missing_self", run.NO_ENTITY_CASES)
        self.assertIn("ir018_dispatch_return", run.ENTITY_CASES)
        self.assertIn("FC_TYPED_IR_SELF_HOLDER", run.options("bytecode"))
        self.assertEqual(run.options("old_bytecode")["FC_TYPED_IR_SELF_HOLDER"], "false")
        self.assertEqual(run.options("bytecode")["FC_TYPED_IR_SELF_HOLDER"], "true")
        with tempfile.TemporaryDirectory() as tmp:
            run.fixture(Path(tmp))
            folder=Path(tmp)/"world/datapacks"/run.PACK/"data/fc_ir/function"
            for name, commands in run.FUNCTIONS.items():
                self.assertEqual(
                    (folder/(name + ".mcfunction")).read_text().splitlines(), commands)
        self.assertTrue(any(
            "execute if score @s" in line and "run function " in line
            for line in run.FUNCTIONS["ir018_dispatch"]))
        self.assertEqual(len(run.QUOTAS), 11)
        self.assertEqual(run.EXPECTED_ENTITY["ir018_self_mutation"]["self"], 9)

    def test_prerequisites_gated_without_production_promotion(self):
        code=(ROOT/"scripts/ci_typed_ir018.py").read_text()
        self.assertIn('"performance_claim": False', code)
        self.assertIn('"production_promotion": False', code)
        self.assertIn('if reference[case] != actual', code)
        probe=java("ProbeCommands.java")
        self.assertIn('System.getenv("FC_TYPED_IR_SELF_TEST_HARNESS")', probe)
        self.assertIn('id.getPath().matches("ir018_[a-z0-9_]+")', probe)


if __name__ == "__main__":
    unittest.main()
