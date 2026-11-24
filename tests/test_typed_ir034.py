"""IR-034: program-immutable instruction vectors are hoisted, not copied in hot paths.

These source-level regression guards complement (not replace) native Minecraft
semantic parity and JVM verification. They intentionally make no CPU claim.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/main/java/dev/functioncompiler"


class IR034LoopInvariantHoist(unittest.TestCase):
    def test_interpreted_materializes_instruction_vector_once_in_constructor(self):
        source = (SOURCE / "TypedScoreIR.java").read_text(encoding="utf-8")
        parsed = source.split("static final class Interpreted implements", 1)[1]
        constructor, execute = parsed.split("public void execute(", 1)
        self.assertIn("private final Instruction[] steps;", constructor)
        self.assertEqual(constructor.count("toArray(Instruction[]::new)"), 1)
        self.assertIn("this.steps = program.instructions().toArray(Instruction[]::new);",
                      constructor)
        self.assertNotIn("toArray(", execute)
        self.assertNotIn("program.instructions()", execute)
        self.assertIn("new TypedScoreIRRuntime.State(source, context, frame, steps)", execute)
        # IR-035 adds a compile-time canonical opcode vector while retaining
        # IR-034's one-time immutable original-instruction array.
        self.assertIn("for (int index = 0; index < opcodes.length; index++)", execute)
        self.assertIn("executeOptimizedStep(opcodes[index], prepared[index], state)", execute)
        self.assertIn("this.prepared = TypedIRPreparedSteps.prepare(optimized);", constructor)
        self.assertIn("this.opcodes = optimized.steps().toArray(", constructor)

    def test_generated_bytecode_loads_final_steps_field_once_per_execution(self):
        source = (SOURCE / "TypedScoreIRBytecode.java").read_text(encoding="utf-8")
        code = source.split("private static byte[] generate(", 1)[1]
        body = code.split("private static void target(", 1)[0]
        begin_loop = body.split("for (int index = 0;", 1)[1]
        self.assertEqual(body.count('method.visitFieldInsn(GETFIELD, internal, "steps", STEPS)'), 1)
        self.assertNotIn('method.visitFieldInsn(GETFIELD, internal, "steps", STEPS)', begin_loop)
        self.assertIn("method.visitVarInsn(ASTORE, 9);", body)
        self.assertGreaterEqual(body.count("method.visitVarInsn(ALOAD, 9);"), 2)
        self.assertIn("method.visitMethodInsn(INVOKEVIRTUAL, STATE, \"begin\"", body)
        self.assertIn("method.visitMethodInsn(INVOKEVIRTUAL, STATE, \"finish\"", body)
        self.assertIn("method.visitJumpInsn(IFEQ, done);", body)
        self.assertIn("method.visitJumpInsn(IF_ICMPEQ, next);", body)
        # JVM instructions remain direct score access and mutation.
        self.assertIn('INVOKEINTERFACE, SCORE, "add"', source)
        self.assertIn('INVOKEINTERFACE, SCORE, "set"', source)

    def test_reentrancy_queues_the_same_readonly_vector(self):
        source = (SOURCE / "TypedScoreIRRuntime.java").read_text(encoding="utf-8")
        self.assertIn("new QueuedTail(source, instructions, nextIndex)", source)
        self.assertIn("TypedScoreIR.Instruction[] instructions", source)
        self.assertIn("new TypedScoreIR.Instruction[]{current}", source)
        self.assertIn("context.incrementCost();", source)
        self.assertIn("FusedRegionPrototype.executeCommand", source)

    def test_existing_native_parity_oracles_still_cover_quota_and_reentrancy(self):
        smoke = (ROOT / "scripts/ci_typed_ir008.py").read_text(encoding="utf-8")
        reentrant = (ROOT / "scripts/ci_typed_ir013.py").read_text(encoding="utf-8")
        self.assertIn('"interpreted"', smoke)
        self.assertIn('"bytecode"', smoke)
        self.assertIn("QUOTAS =", smoke)
        self.assertIn('"bytecode_guarded"', reentrant)
        self.assertIn('"interpreted_guarded"', reentrant)
        self.assertIn('"native"', reentrant)
        self.assertIn("QUOTAS =", reentrant)


if __name__ == "__main__":
    unittest.main()
