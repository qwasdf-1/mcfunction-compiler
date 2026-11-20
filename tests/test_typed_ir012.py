"""IR-012 strict resumable direct-call admission and native regression fixtures."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir012 as ir


def code(name):
    return (ROOT / "src/main/java/dev/functioncompiler" / name).read_text()


class IR012(unittest.TestCase):
    def test_fixture_coverage_and_chunks(self):
        self.assertEqual(len(ir.FUNCTIONS["ir012_chunk_64"]), 64)
        self.assertEqual(len(ir.FUNCTIONS["ir012_chunk_128"]), 128)
        self.assertEqual(len(ir.FUNCTIONS["ir012_chunk_256"]), 256)
        self.assertEqual(len(ir.FUNCTIONS["ir012_chunk_2000"]), 2000)
        self.assertEqual(len(ir.FUNCTIONS["ir012_bad_tail_65"]), 65)
        self.assertTrue(any("function fc_ir:ir012_helper" in x
                            for x in ir.FUNCTIONS["ir012_barrier"]))
        self.assertTrue(any("execute unless score" in x for x in ir.MIXED))
        self.assertTrue(any("scoreboard players operation" in x for x in ir.MIXED))
        self.assertTrue(any("fc_ir012_missing" in x
                            for x in ir.FUNCTIONS["ir012_missing_obj"]))

    def test_admission_is_whole_bytecode_function_only(self):
        irsrc = code("TypedScoreIR.java")
        for expected in (
            "boolean fullyTyped = true;", "fullyTyped = false;",
            "original.entries().size() <= 4096", '"bytecode".equals(MODE)',
            "entry instanceof Interpreted", "original.entries().contains(entry)",
            "directFunctionChunks(", "TypedScoreIRDirectScheduler.eligibleCompiled()",
        ):
            self.assertIn(expected, irsrc)
        self.assertIn('TypedScoreIRDirectScheduler.diagnostics()', irsrc)

    def test_runtime_rechecks_callbacks_traces_and_return_mode(self):
        source = code("TypedScoreIRDirectScheduler.java")
        for expected in (
            "returnParentFrame", "functionCallback != CommandResultCallback.EMPTY",
            "context.tracer() != null", "sender.callback() != CommandResultCallback.EMPTY",
            "sender instanceof CommandSourceStack source", "engine.incrementCost()",
            "TypedScoreIR.directFunctionChunks(function)",
            "context.queueNext(new CommandQueueEntry<>",
            "chunks.get(pc).execute(source, context, frame)",
            "pc + 1 < chunks.size()", "functionCompiler$getCommandQuota() > 0",
        ):
            self.assertIn(expected, source)
        self.assertIn('System.getenv("FC_TYPED_IR_DIRECT_FUNCTION")', source)
        self.assertIn("private record Resume(", source)

    def test_original_call_function_is_preserved_for_all_other_cases(self):
        mixin = code("mixin/CallFunctionMixin.java")
        self.assertIn("TypedScoreIRDirectScheduler.tryExecute(", mixin)
        self.assertIn("DirectSchedulerPrototype.tryExecute(", mixin)
        self.assertIn("@Inject(method = \"execute\", at = @At(\"HEAD\"), cancellable = true)", mixin)
        self.assertIn("ci.cancel();", mixin)
        self.assertIn("TypedScoreIR.originalTraceEntryCount(", mixin)
        self.assertIn("typed.original().entries().size()",
                      code("TypedScoreIR.java"))

    def test_research_call_site_and_toggle_are_explicitly_gated(self):
        source = code("ProbeCommands.java")
        self.assertIn('System.getenv("FC_TYPED_IR_DIRECT_FUNCTION_HARNESS")', source)
        self.assertIn('Commands.literal("fc_ir012_call")', source)
        self.assertIn('Commands.literal("fc_ir012_direct")', source)
        self.assertIn("TypedScoreIRDirectScheduler.toggle(", source)
        self.assertIn("ExecutionContext.queueInitialFunctionCall(", source)

    def test_research_design_is_same_bytecode_balanced_and_conservative(self):
        for mode in ir.SEMANTIC_MODES:
            flags = ir.options(mode)
            self.assertEqual(flags["FC_TYPED_IR_SCORE_CACHE"], "false")
            self.assertEqual(flags["FC_TYPED_IR_SINGLETON_FEEDBACK"], "false")
            self.assertEqual(flags["FC_TYPED_IR_DIRECT_FUNCTION"], "true")
        self.assertEqual(ir.options("crossover", True)["FC_TYPED_IR_DIAGNOSTICS"], "false")
        for boot in range(ir.BOOTS):
            blocks = ir.plan(boot)
            primary = [x["order"] for x in blocks
                       if x["kind"] == "direct_vs_vanilla_scheduler"]
            self.assertEqual(primary.count("ABBA"), ir.PAIRS_PER_BOOT // 2)
            self.assertEqual(primary.count("BAAB"), ir.PAIRS_PER_BOOT // 2)
            self.assertEqual(sum(x["kind"] == "vanilla_aa" for x in blocks),
                             ir.AA_PER_BOOT)
        self.assertIn('"causal_general_speedup": False',
                      (ROOT / "scripts/ci_typed_ir012.py").read_text())
        self.assertIn('"production_promotion": False',
                      (ROOT / "scripts/ci_typed_ir012.py").read_text())

    def test_low_quota_trace_and_callback_acceptance_gates(self):
        s = (ROOT / "scripts/ci_typed_ir012.py").read_text()
        for token in (
            "gamerule minecraft:max_command_sequence_length",
            '"ordinary_function"', '"stored_function_result"',
            "debug function fc_ir:ir012_mixed",
            '"direct_function_executed"', '"direct_function_resumes"',
            '"direct_function_chunks"', "FC_ARCH_CALL queued",
            "Native parity mismatch",
        ):
            self.assertIn(token, s)


if __name__ == "__main__":
    unittest.main()
