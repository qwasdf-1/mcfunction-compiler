"""IR-036 compiler legality, opt-in cost-selection, and source-span contracts.

These source assertions complement the JDK model unit test and the real native
Minecraft differential gate; they are NOT CPU measurements or speedup claims.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "src/main/java/dev/functioncompiler"


def read(filename):
    return (JAVA / filename).read_text(encoding="utf-8")


class IR036(unittest.TestCase):
    def test_effect_analysis_tracks_reads_writes_and_dynamic_aliases(self):
        code = read("TypedIREffectAnalysis.java")
        for token in (
            "original.effects()", "previous.effects()",
            "intersects(left.writes(), right.reads())",
            "intersects(left.writes(), right.writes())",
            "intersects(left.reads(), right.writes())",
            "guard.conditionSelf()", "terminal.holderSelf()",
            "binary.sourceSelf()", "dynamicAlias",
            "new Boundary(i - 1, conflict, dynamicAlias, true)",
            "new IR036CostModel.Features(",
            "boolean reorderPermitted() { return false; }",
            "boolean eliminateCommandPermitted() { return false; }",
        ):
            self.assertIn(token, code)

    def test_model_is_structural_bounded_and_uncalibrated(self):
        code = read("IR036CostModel.java")
        for token in (
            "enum Backend { VANILLA, INTERPRETED, BYTECODE }",
            "record Features(", "record Decision(",
            "blockedBoundaries != instructions - 1",
            "expectedCalls < 1 || expectedCalls > 1_000_000",
            "if (interpreted < best)", "if (allowBytecode && bytecode < best)",
            "Backend selected = Backend.VANILLA;",
            "DIMENSIONLESS heuristic work units",
        ):
            self.assertIn(token, code)
        self.assertNotIn("System.nanoTime()", code)
        self.assertNotIn("currentTimeMillis()", code)

    def test_selector_is_opt_in_and_falls_back_to_existing_mode(self):
        code = read("TypedScoreIR.java")
        self.assertIn('"select".equals(System.getenv("FC_TYPED_IR_COST_POLICY"))', code)
        self.assertIn('System.getenv("FC_TYPED_IR_EXPECTED_CALLS")', code)
        self.assertIn("if (COST_SELECT)", code)
        self.assertIn("TypedIREffectAnalysis.analyze(optimized)", code)
        self.assertIn("IR036CostModel.choose(", code)
        self.assertIn('IR036CostModel.Backend.BYTECODE', code)
        self.assertIn('IR036CostModel.Backend.INTERPRETED', code)
        self.assertIn("new EmittedRegion(null, false, true)", code)
        self.assertIn("new Interpreted(program, optimized)", code)
        self.assertIn("TypedScoreIRBytecode.emit(optimized)", code)

    def test_vanilla_cost_decision_restores_each_original_queue_action(self):
        code = read("MixedFunctionIR.java")
        for token in (
            "if (emitted.vanilla())",
            "for (int offset = 0; offset < pending.size(); offset++)",
            "new OpaqueBarrier(first + offset,",
            "pending.get(offset).vanilla().original()",
            "BarrierKind.COST_MODEL_VANILLA",
            "nodes.add(new TypedRegion(first, typed, emitted.action(), emitted.bytecode()))",
        ):
            self.assertIn(token, code)
        self.assertIn("node.firstSourceIndex() != expected", code)
        self.assertIn("expected != sourceCount", code)

    def test_no_shortcuts_around_runtime_semantics(self):
        code = read("TypedScoreIRRuntime.java")
        for token in (
            "context.incrementCost();", "tracer.onCommand(",
            "FusedRegionPrototype.executeCommand(", "response.sendFeedback(",
            "new QueuedTail(source, instructions, nextIndex)", "tracer.onReturn(",
        ):
            self.assertIn(token, code)
        opt = read("TypedIROptimizer.java")
        self.assertIn("steps.get(i).original() != source.instructions().get(i)", opt)
        self.assertIn("output.add(classify(original))", opt)
        self.assertNotIn("output.remove(", opt)

    def test_pure_java_cost_gate_is_present(self):
        modeltest = ROOT / "tests/java/dev/functioncompiler/IR036CostModelTest.java"
        self.assertTrue(modeltest.is_file())
        data = modeltest.read_text()
        for candidate in ("Backend.VANILLA", "Backend.INTERPRETED",
                          "Backend.BYTECODE", "IR036_JAVA_MODEL_ACCEPTED"):
            self.assertIn(candidate, data)


if __name__ == "__main__":
    unittest.main()
