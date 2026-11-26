"""IR-037: prepared typed-step runtime work reduction and original semantic guards.

These source contracts are not a performance benchmark; native Minecraft
differential parity is the authority for quota, listener and queue behavior.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/main/java/dev/functioncompiler"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


class IR037PreparedRuntime(unittest.TestCase):
    def test_compile_time_preparation_is_one_to_one_and_immutable(self):
        p = source("TypedIRPreparedSteps.java")
        for expected in (
            "record Prepared(", "enum Feedback { ADD, REMOVE, SET, OPERATION }",
            "original.effects().observableBoundary()",
            "Prepared[] result = new Prepared[plan.steps().size()]",
            "original != plan.source().instructions().get(i)",
            "result[i] = prepare(original, shape)",
            "shape.equals(result[i-1].guardRun())",
            "Feedback.OPERATION",
            "case REMOVE -> Feedback.REMOVE",
            "amount = mutation.amount();",
            "original.holderSelf()", "original.objective()",
            "guard.conditionHolder()", "guard.conditionSelf()",
            "binary.sourceHolder()", "binary.sourceSelf()",
            "binary.sourceObjective()",
        ):
            self.assertIn(expected, p)
        # Compile-time description cannot hold live runtime objects or a
        # stale scoreboard value/Objective across arbitrary command callbacks.
        self.assertNotIn("getOrCreatePlayerScore(", p)
        self.assertNotIn("getPlayerScoreInfo(", p)
        self.assertNotIn("getObjective(", p)
        self.assertNotIn("ScoreAccess", p)
        self.assertNotIn("Scoreboard scoreboard", p)
        self.assertNotIn("Math.abs(", p)

    def test_hot_begin_no_longer_reparses_instruction_shapes(self):
        runtime = source("TypedScoreIRRuntime.java")
        assert "int begin(TypedIRPreparedSteps.Prepared prepared)" in runtime
        fast = runtime.split("int begin(TypedIRPreparedSteps.Prepared prepared)", 1)[1]
        fast = fast.split("private int original(", 1)[0]
        for token in (
            "TypedScoreIR.Instruction instruction = prepared.original()",
            "prepared.targetSelf()", "prepared.targetHolder()",
            "scoreboard.getObjective(prepared.targetObjective())",
            "prepared.condition()", "prepared.binary()",
            "scoreboard.getObjective(prepared.conditionObjective())",
            "scoreboard.getObjective(prepared.operandObjective())",
            "scoreboard.getOrCreatePlayerScore(target, selected)",
            "scoreboard.getOrCreatePlayerScore(operandHolder, operandObjective)",
            "context.incrementCost()", "tracer.onCommand(",
            "new QueuedTail(source, instructions, nextIndex)",
            "TypedScoreIR.skippedConditional()",
            "return original(instruction)",
            "currentPrepared = prepared",
        ):
            self.assertIn(token, fast)
        for forbidden in (
            "instanceof TypedScoreIR.Conditional",
            "instanceof TypedScoreIR.Binary",
            ".terminal()",
            ".operation()",
            "TypedIRPreparedSteps.prepare(",
        ):
            self.assertNotIn(forbidden, fast)

    def test_feedback_and_revision_cache_use_original_prepared_metadata(self):
        runtime = source("TypedScoreIRRuntime.java")
        cached = runtime.split("int sourceOperand()", 1)[1].split(
            "private void traceReturn(", 1)[0]
        finish = runtime.split("void finish(int newScore)", 1)[1]
        for expected in (
            "TypedIRPreparedSteps.Prepared prepared = currentPrepared",
            "prepared.feedback() == TypedIRPreparedSteps.Feedback.OPERATION",
            "case ADD ->",
            "case REMOVE ->",
            "case SET ->",
            "prepared.feedbackAmount()",
            "response.sendFeedback(",
            "tracer.onReturn(",
            "currentPrepared = null",
            "source.handleError(error, false, tracer)",
        ):
            self.assertIn(expected, finish)
        self.assertNotIn("instanceof TypedScoreIR.Conditional", finish)
        self.assertNotIn("instanceof TypedScoreIR.Binary", finish)
        self.assertIn("prepared.operandObjective()", cached)
        self.assertIn("versions.functionCompiler$watch(key)", cached)
        self.assertNotIn("instanceof TypedScoreIR.Binary", cached)

    def test_hot_interpreter_and_asm_share_prepared_metadata(self):
        ir = source("TypedScoreIR.java")
        asm = source("TypedScoreIRBytecode.java")
        for token in (
            "this.prepared = TypedIRPreparedSteps.prepare(optimized)",
            "executeOptimizedStep(opcodes[index], prepared[index], state)",
            "int decision = state.begin(prepared)",
            "new TypedScoreIRRuntime.State(source, context, frame, steps)",
        ):
            self.assertIn(token, ir)
        for token in (
            'writer.visitField(ACC_PRIVATE | ACC_FINAL, "steps", STEPS',
            'writer.visitField(ACC_PRIVATE | ACC_FINAL, "prepared", PREPARED_STEPS',
            "TypedIRPreparedSteps.Prepared[].class",
            "(Object) TypedIRPreparedSteps.prepare(optimized)",
            'method.visitFieldInsn(GETFIELD, internal, "prepared", PREPARED_STEPS)',
            'method.visitVarInsn(ASTORE, 10)',
            'method.visitVarInsn(ALOAD, 10)',
            '"(L" + PREPARED + ";)I"',
        ):
            self.assertIn(token, asm)
        self.assertEqual(asm.count('method.visitFieldInsn(GETFIELD, internal, "steps", STEPS)'), 1)
        self.assertEqual(asm.count('method.visitFieldInsn(GETFIELD, internal, "prepared", PREPARED_STEPS)'), 1)
        self.assertIn('INVOKEINTERFACE, SCORE, "add"', asm)
        self.assertIn('INVOKEINTERFACE, SCORE, "set"', asm)

    def test_duplicate_objective_lookup_elision_is_local_to_one_command(self):
        prepared = source("TypedIRPreparedSteps.java")
        runtime = source("TypedScoreIRRuntime.java")
        ir = source("TypedScoreIR.java")
        for token in (
            "boolean guardSharesTargetObjective",
            "boolean operandSharesTargetObjective",
            "boolean operandSharesGuardObjective",
            "targetObjective.equals(conditionObjective)",
            "targetObjective.equals(operandObjective)",
            "conditionObjective.equals(operandObjective)",
            "unsound objective alias metadata",
            "guard.conditionObjective().equals(binary.sourceObjective())",
        ):
            self.assertIn(token, prepared)
        body = runtime.split("int begin(TypedIRPreparedSteps.Prepared prepared)", 1)[1]
        body = body.split("private int original(", 1)[0]
        for token in (
            "scoreboard.getObjective(prepared.targetObjective())",
            "if (prepared.guardSharesTargetObjective())",
            "guardObjective = selected",
            "if (prepared.operandSharesTargetObjective())",
            "operandObjective = selected",
            "else if (prepared.operandSharesGuardObjective())",
            "operandObjective = guardObjective",
            "scoreboard.getObjective(prepared.conditionObjective())",
            "scoreboard.getObjective(prepared.operandObjective())",
            "TypedScoreIR.objectiveLookupReused()",
            "scoreboard.getOrCreatePlayerScore(target, selected)",
            "scoreboard.getOrCreatePlayerScore(operandHolder, operandObjective)",
        ):
            self.assertIn(token, body)
        # Reuse cannot escape begin(): per-command State begins again with a
        # FRESH target lookup, even after synchronous scoreboard callbacks.
        self.assertLess(body.index("scoreboard.getObjective(prepared.targetObjective())"),
                        body.index("context.incrementCost();"))
        self.assertIn("ir037_objective_lookups_reused", ir)
        self.assertIn("if (DIAGNOSTICS) OBJECTIVE_LOOKUPS_REUSED.increment()", ir)

    def test_reentrant_tail_uses_original_actions_and_prepare_is_exceptional(self):
        runtime = source("TypedScoreIRRuntime.java")
        ir = source("TypedScoreIR.java")
        self.assertIn("return begin(TypedIRPreparedSteps.prepare(instruction));", runtime)
        self.assertIn("TypedScoreIR.executeTypedStep(current, state)", runtime)
        self.assertIn("new QueuedTail(source, instructions, nextIndex)", runtime)
        self.assertIn("FusedRegionPrototype.executeCommand(", runtime)
        self.assertIn("TypedScoreIRRuntime.State state =", ir)
        self.assertIn("state.finish(updated)", ir)


if __name__ == "__main__":
    unittest.main()
