"""IR-039 contracts; native differential separately checks execution."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "src/main/java/dev/functioncompiler"
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir039 as native


def src(name):
    return (JAVA / name).read_text()


class IR039(unittest.TestCase):
    def test_ordered_compound_representation_and_proven_predicate_reuse(self):
        ir = src("TypedScoreIR.java")
        plan = src("CompoundScoreIR.java")
        for text in ("record Compound(", "predicates = List.copyOf(predicates)",
                     "CompoundScoreIR.reads(predicates)", "terminal.vanilla() != vanilla"):
            self.assertIn(text, ir)
        for text in ("MAX_PREDICATES = 8", 'TypedCompilerConfiguration.flag("FC_TYPED_IR_COMPOUND_SCORE")',
                     "record RawKey(", "left.key()", "right.key()",
                     "passed.get(p.rawKey())", "passed.putIfAbsent(p.rawKey(), p.unless())",
                     "Evaluation.KNOWN_PASS", "Evaluation.KNOWN_FAIL",
                     "stages = List.copyOf(stages)"):
            self.assertIn(text, plan)
        self.assertIn("TypedScoreIR.slotName(holder, self)", plan)
        self.assertNotIn("getPlayerScoreInfo(", plan)

    def test_native_chain_is_not_mutated(self):
        lowering = src("ScoreAddPrototype.java").split(
            "static TypedScoreIR.Compound lowerCompound(", 1)[1].split(
            "private interface ExecutableCompiler", 1)[0]
        for text in ("parseScoreCondition(modifier, true, true)",
                     "ScoreConditionCommand.typedIrLiteralGuardShape(",
                     "ScoreConditionCommand.sameParsedRange(",
                     "parseOperator(words[4])",
                     "new CommandContext<>(executable.getSource()",
                     "compileScoreAdd(copy, functionId)", "compileScoreOperation(copy, functionId)",
                     "entry, new ContextChain<>(List.of(), copy), input",
                     "new TypedScoreIR.Compound(original, terminal, predicates,"):
            self.assertIn(text, lowering)
        self.assertNotIn("functionCompiler$setCommand(", lowering)
        self.assertIn("ScoreAddPrototype.lowerCompound(entry, original.id())",
                      src("MixedFunctionIR.java"))

    def test_both_backends_preserve_stage_quota_and_branch(self):
        runtime = src("TypedScoreIRRuntime.java")
        asm = src("TypedScoreIRBytecode.java")
        ir = src("TypedScoreIR.java")
        for method in ("compoundReadStage(int index)", "compoundKnownStage(int index, boolean pass)"):
            body = runtime.split("boolean " + method, 1)[1].split("\n        }", 1)[0]
            self.assertNotIn("quota() <= 0", body)
            self.assertIn("context.incrementCost();", body)
        terminal = runtime.split("boolean compoundTerminal()", 1)[1].split("\n        }", 1)[0]
        self.assertIn("if (quota() <= 0) return false;", terminal)
        self.assertIn("context.incrementCost();", terminal)
        # Native BuildContexts charges every subsequent redirect on an empty
        # source list, without reading any more scores or admitting a terminal.
        branch = runtime.split("private boolean compoundBranch(", 1)[1].split(
            "// Called only after all original predicate stages", 1)[0]
        self.assertIn("for (int i = index + 1; i < currentPrepared.compound().stages().size(); i++)", branch)
        self.assertIn("context.incrementCost();", branch)
        self.assertIn("TypedScoreIR.compoundEmptyStage();", branch)
        self.assertNotIn("compoundRead(", branch)
        self.assertNotIn("quota() <= 0", branch)
        self.assertIn("if (!compoundStage(i)) return false;", runtime)
        self.assertIn("prepared.compound() != null && !state.completeCompound()", ir)
        self.assertIn("instruction instanceof Compound && !state.completeCompound()", ir)
        self.assertIn("for (int stageIndex = 0; stageIndex < stages.size(); stageIndex++)", asm)
        self.assertIn('"compoundReadStage", "(I)Z"', asm)
        self.assertIn('"compoundKnownStage", "(IZ)Z"', asm)
        self.assertIn('"compoundTerminal", "()Z"', asm)
        self.assertIn("method.visitJumpInsn(IFEQ, next)", asm)

    def test_missing_and_traced_fallback_queues_untouched_action_and_tail(self):
        runtime = src("TypedScoreIRRuntime.java")
        preflight = runtime.split("private int startCompound(", 1)[1].split(
            "private int compoundNative(", 1)[0]
        self.assertNotIn("incrementCost()", preflight)
        for text in ("context.tracer() != null", "context.forkLimit() <= 1", "source.callback()",
                     "scoreboard.getObjective(plan.objectives().get(i))",
                     "operand.self() ? source.getEntity() : operand.holder()",
                     "return compoundNative(prepared.original())"):
            self.assertIn(text, preflight)
        fallback = runtime.split("private int compoundNative(", 1)[1].split(
            "private Objective compoundObjective(", 1)[0]
        self.assertIn("instruction.vanilla().original().execute(source, execution, commandFrame)", fallback)
        self.assertIn("new QueuedTail(source, instructions, nextIndex)", fallback)
        self.assertIn("return STOP;", fallback)
        self.assertIn("if (left != null)", runtime)
        self.assertIn("stage.leftIndex() == stage.rightIndex()", runtime)

    def test_native_fixture_has_identical_flag_control_and_real_entity_calls(self):
        self.assertEqual(len(native.CASES), 14)
        self.assertEqual(native.QUOTAS, (*range(1, 41), 48))
        self.assertIn("ir017_ir039_empty_suffix", native.NEW)
        self.assertEqual(native.EXPECTED["ir017_ir039_empty_suffix"], 31)
        for line in native.NEW["ir017_ir039_empty_suffix"][1::2]:
            self.assertEqual(line.count(" score "), 8)
        self.assertEqual(len(native.SELF), 2)
        old = native.options("old_bytecode")
        new = native.options("bytecode")
        self.assertEqual(old["FC_TYPED_IR_COMPOUND_SCORE"], "false")
        self.assertEqual(new["FC_TYPED_IR_COMPOUND_SCORE"], "true")
        for key in ("FC_TYPED_IR_EXTENDED_SCORE", "FC_TYPED_IR_RANGE_GUARDS",
                    "FC_TYPED_IR_SELF_HOLDER"):
            self.assertEqual(old[key], new[key])
            self.assertEqual(new[key], "true")
        self.assertIn("ir017_ir039_missing_objective", native.NEW)
        self.assertIn("ir017_ir039_reentrant", native.NEW)


if __name__ == "__main__":
    unittest.main()
