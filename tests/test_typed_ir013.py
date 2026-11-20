"""IR-013 re-entrant callback queue order contract; native study is authority."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir013 as study


def source(path: str) -> str:
    return (ROOT / "src/main/java/dev/functioncompiler" / path).read_text()


class ReentrantIR013(unittest.TestCase):
    def test_test_only_scoreboard_adversary_queues_real_function(self):
        mixin = source("mixin/ScoreboardQueueInjectionMixin.java")
        observer = source("ReentrantQueueProbe.java")
        for token in (
            'method = "onScoreChanged"', "ReentrantQueueProbe.scoreChanged",
            'System.getenv("FC_TYPED_IR_REENTRANT_TEST_OBSERVER")',
            "ExecutionContextBridge.currentContext()",
            "ExecutionContext.queueInitialFunctionCall(",
            "ir013_injected", "#ir013_trigger", "INJECTIONS.increment()",
        ):
            self.assertIn(token, mixin + observer)
        self.assertIn('"ScoreboardQueueInjectionMixin"',
                      (ROOT / "src/main/resources/function_compiler.mixins.json").read_text())

    def test_queue_epoch_is_event_based_not_guess_from_ir_effects(self):
        iface = source("ReentrantQueueEpoch.java")
        mixin = source("mixin/ExecutionContextMixin.java")
        runtime = source("TypedScoreIRRuntime.java")
        for token in (
            "functionCompiler$queuedWorkEpoch()",
            'System.getenv("FC_TYPED_IR_REENTRANT_SAFE")',
            '@Inject(method = "queueNext", at = @At("HEAD"))',
        ):
            self.assertIn(token, iface + mixin)
        self.assertIn("initialQueueEpoch", runtime)
        self.assertIn("epoch.functionCompiler$queuedWorkEpoch() != initialQueueEpoch", runtime)
        self.assertIn("nextIndex > 0", runtime)
        self.assertIn("return STOP;", runtime)
        self.assertIn("new VanillaTail(source, instructions, nextIndex)", runtime)

    def test_remainder_only_uses_original_entries_with_no_premature_execution(self):
        runtime = source("TypedScoreIRRuntime.java")
        for token in (
            "private record VanillaTail(",
            "instructions[index].vanilla().original().bind(source)",
            "index + 1 < instructions.length",
            "context.queueNext(new CommandQueueEntry<>",
            "TypedScoreIR.reentrantVanillaStep()",
            "TypedScoreIR.reentrantYield()",
        ):
            self.assertIn(token, runtime)
        self.assertNotIn("instructions[index].vanilla().original().execute(", runtime)

    def test_generated_asm_and_interpreter_pass_immutable_instruction_set(self):
        ir = source("TypedScoreIR.java")
        asm = source("TypedScoreIRBytecode.java")
        self.assertIn("program.instructions().toArray(TypedScoreIR.Instruction[]::new)", ir)
        self.assertIn('method.visitFieldInsn(GETFIELD, internal, "steps", STEPS)', asm)
        self.assertIn(';" + STEPS + ")V"', asm)
        self.assertIn("reentrant_yields=", ir)
        self.assertIn("reentrant_vanilla_steps=", ir)
        self.assertIn("ReentrantQueueProbe.diagnostics()", ir)

    def test_boundary_and_interleaving_fixtures_exact_length(self):
        self.assertEqual(len(study.FUNCTIONS["ir013_inside128"]), 128)
        self.assertEqual(len(study.FUNCTIONS["ir013_boundary128"]), 128)
        self.assertEqual(study.FUNCTIONS["ir013_inside128"][30], study.TRIGGER)
        self.assertEqual(study.FUNCTIONS["ir013_inside128"][31], study.OBSERVE)
        self.assertEqual(study.FUNCTIONS["ir013_boundary128"][63], study.TRIGGER)
        self.assertEqual(study.FUNCTIONS["ir013_boundary128"][64], study.OBSERVE)
        self.assertEqual(study.EXPECTED["ir013_twice"]["seen2"], 14)
        self.assertIn("execute if score", study.FUNCTIONS["ir013_guarded"][1])

    def test_disposable_pack_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as t:
            study.fixture(Path(t))
            folder = Path(t) / "world/datapacks" / study.PACK / "data/fc_ir/function"
            for name, lines in study.FUNCTIONS.items():
                self.assertEqual((folder / f"{name}.mcfunction").read_text().splitlines(),
                                 lines)
        self.assertIn("bytecode_unsafe", study.MODES)
        self.assertIn("direct_unsafe", study.MODES)
        self.assertIn("bytecode_guarded", study.MODES)
        self.assertIn("interpreted_guarded", study.MODES)
        self.assertIn("direct_guarded", study.MODES)
        self.assertIn(1, study.QUOTAS)
        self.assertIn(65, study.QUOTAS)
        self.assertTrue(study.options("direct_unsafe")["FC_TYPED_IR_REENTRANT_SAFE"] == "false")
        self.assertTrue(study.options("direct_guarded")["FC_TYPED_IR_REENTRANT_SAFE"] == "true")
        self.assertEqual(study.options("native")["FC_TYPED_IR_REENTRANT_TEST_OBSERVER"], "true")
        runner = (ROOT / "scripts/ci_typed_ir013.py").read_text()
        self.assertIn('"ir013_inside128" not in differences[mode]', runner)
        self.assertIn('if arm["mode"].endswith("_guarded") and changed:', runner)
        self.assertIn('"production_promotion": False', runner)


if __name__ == "__main__":
    unittest.main()
