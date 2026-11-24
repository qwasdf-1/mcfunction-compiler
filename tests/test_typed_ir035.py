"""COMPILER-IR-035: preserve every command boundary through the first optimizer pass.

Source-contract checks complement JVM compilation and the real Minecraft
IR-008/IR-013 differential semantic gate. They are not speed measurements.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "src/main/java/dev/functioncompiler"


def java(name: str) -> str:
    return (JAVA / name).read_text(encoding="utf-8")


class TypedIROptimizer035(unittest.TestCase):
    def test_optimizer_is_explicit_boundary_between_lowering_and_both_backends(self):
        source = java("TypedScoreIR.java")
        begin = source.index("static EmittedRegion emitRegion(Program program)")
        end = source.index("static boolean retainsOriginal(", begin)
        emission = source[begin:end]
        self.assertLess(emission.index("TypedIROptimizer.optimize(program)"),
                        emission.index("new Interpreted(program, optimized)"))
        self.assertLess(emission.index("TypedIROptimizer.optimize(program)"),
                        emission.index("TypedScoreIRBytecode.emit(optimized)"))
        self.assertIn("new Interpreted(program, optimized)", emission)
        self.assertIn("TypedScoreIRBytecode.emit(optimized)", emission)

    def test_all_original_entries_retained_in_order_and_no_elision(self):
        source = java("TypedIROptimizer.java")
        for token in (
            "record Plan(TypedScoreIR.Program source, List<Step> steps)",
            "steps = List.copyOf(steps)",
            "steps.size() != source.instructions().size()",
            "steps.get(i).original() != source.instructions().get(i)",
            "original.effects().observableBoundary()",
            "output.add(classify(original))",
            "return new Plan(source, output)",
        ):
            self.assertIn(token, source)
        self.assertNotIn("output.remove(", source)
        self.assertNotIn("output.clear(", source)
        self.assertNotIn("Collections.sort", source)

    def test_signed_literal_canonicalization_keeps_feedback_identity(self):
        optimizer = java("TypedIROptimizer.java")
        runtime = java("TypedScoreIRRuntime.java")
        for token in (
            "case ADD -> new Step(original, Op.ADD_LITERAL, mutation.amount())",
            "case REMOVE -> new Step(original, Op.ADD_LITERAL, -mutation.amount())",
            "case SET -> new Step(original, Op.SET_LITERAL, mutation.amount())",
        ):
            self.assertIn(token, optimizer)
        # The original command still controls feedback, guard and fallback.
        for token in (
            "TypedScoreIR.Instruction instruction = current",
            "mutation.operation()",
            "mutation.amount()",
            "FusedRegionPrototype.executeCommand(",
            "context.incrementCost()",
            "tracer.onCommand(",
            "tracer.onReturn(",
        ):
            self.assertIn(token, runtime)

    def test_binary_opcode_classification_and_both_codegen_paths(self):
        optimizer = java("TypedIROptimizer.java")
        interpreter = java("TypedScoreIR.java")
        asm = java("TypedScoreIRBytecode.java")
        for code in ("ASSIGN_SCORE", "ADD_SCORE", "SUBTRACT_SCORE",
                     "MULTIPLY_SCORE", "ADD_LITERAL", "SET_LITERAL"):
            self.assertIn(code, optimizer)
            self.assertIn(code, interpreter)
            self.assertIn(code, asm)
        self.assertIn("state.begin(prepared)", interpreter)
        self.assertIn("TypedIRPreparedSteps.prepare(optimized)", interpreter)
        self.assertIn("state.finish(updated)", interpreter)
        self.assertIn("state.sourceOperand()", interpreter)
        self.assertIn("state.sourceAccess().get()", interpreter)
        self.assertIn("method.visitVarInsn(ALOAD, 9)", asm)
        self.assertIn("optimized.source().instructions().toArray(", asm)
        self.assertIn("optimized.steps().get(index)", asm)
        self.assertIn('INVOKEINTERFACE, SCORE, "add"', asm)
        self.assertIn('INVOKEINTERFACE, SCORE, "set"', asm)
        self.assertIn("method.visitJumpInsn(IFEQ, done);", asm)

    def test_opaque_barriers_reentrancy_and_existing_native_oracles_remain(self):
        mixed = java("MixedFunctionIR.java")
        runtime = java("TypedScoreIRRuntime.java")
        interpreter = java("TypedScoreIR.java")
        for token in ("new OpaqueBarrier(", "new TypedRegion(", "sourceCount()",
                      "original.entries()", "TypedScoreIR.emitRegion(typed)"):
            self.assertIn(token, mixed)
        self.assertIn("new QueuedTail(source, instructions, nextIndex)", runtime)
        self.assertIn("TypedScoreIR.executeTypedStep(current, state)", runtime)
        self.assertIn("private final Instruction[] steps;", interpreter)
        self.assertIn("this.steps = program.instructions().toArray(Instruction[]::new);",
                      interpreter)
        self.assertNotIn("TypedIROptimizer.optimize(", runtime)

    def test_negative_remove_and_noop_mutations_remain_real_commands(self):
        optimizer = java("TypedIROptimizer.java")
        # No zero or overflow special case skips feedback, scoreboard listeners,
        # row creation, quota debits, or a command's native source position.
        self.assertIn("case REMOVE -> -mutation.amount()", optimizer)
        self.assertNotIn("if (mutation.amount() == 0)", optimizer)
        self.assertNotIn("Math.abs(", optimizer)
        self.assertIn("case ADD_LITERAL -> updated = score.add(step.literal());",
                      java("TypedScoreIR.java"))


if __name__ == "__main__":
    unittest.main()
