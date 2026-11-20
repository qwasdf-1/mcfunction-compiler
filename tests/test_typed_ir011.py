"""COMPILER-IR-011 — singleton feedback specialization research contract."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_typed_ir011 as ir


def java(name: str) -> str:
    return (ROOT / "src/main/java/dev/functioncompiler" / name).read_text(encoding="utf-8")


class SingletonFeedbackIR011(unittest.TestCase):
    def test_all_paths_are_explicit_and_cache_is_independently_disabled(self):
        self.assertEqual(ir.SEMANTIC_MODES, (
            "native", "bytecode_off", "interpreted_on", "bytecode_on"))
        for mode in ir.SEMANTIC_MODES:
            options = ir.options(mode)
            self.assertEqual(options["FC_TYPED_IR_SCORE_CACHE"], "false")
            self.assertEqual(options["FC_TYPED_IR_SCORE_CACHE_TEST_OBSERVER"], "false")
            self.assertEqual(options["FC_TYPED_IR_SINGLETON_FEEDBACK"],
                             str(mode.endswith("_on")).lower())
            self.assertEqual(options["FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE"], "false")
            self.assertEqual(options["FC_COMMAND_CALLBACK_METRICS"], "false")
        cross = ir.options("crossover", crossover=True)
        self.assertEqual(cross["FC_TYPED_IR_MODE"], "bytecode")
        self.assertEqual(cross["FC_TYPED_IR_DIAGNOSTICS"], "false")
        self.assertEqual(cross["FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE"], "true")

    def test_fixtures_contain_zero_negative_binary_guard_and_nonir_barrier(self):
        self.assertEqual(len(ir.CASES["bench64"]), 64)
        self.assertTrue(any("scoreboard players add #a fc_ir 0" in x
                            for x in ir.CASES["zero"]))
        self.assertTrue(any("-2147483648" in x for x in ir.CASES["signed"]))
        self.assertTrue(any("execute unless score" in x for x in ir.CASES["conditional"]))
        self.assertTrue(any("function fc_ir:helper" in x for x in ir.CASES["barrier"]))
        self.assertTrue(any("operation #b fc_ir = #a fc_ir" in x
                            for x in ir.CASES["signed"]))
        self.assertEqual(ir.EXPECTED["signed"]["a"], 2147483642)
        self.assertEqual(ir.EXPECTED["signed"]["b"], 2147483644)

    def test_disposable_original_source_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir.make_pack(Path(tmp))
            root = (Path(tmp) / "world/datapacks" / ir.PACK /
                    "data" / ir.NS / "function")
            for name, commands in ir.CASES.items():
                self.assertEqual((root / f"{name}.mcfunction").read_text().splitlines(),
                                 commands)

    def test_specialization_keeps_vanilla_send_success_callback_and_trace(self):
        runtime = java("TypedScoreIRRuntime.java")
        for token in ("CommandResponseTracker.create()", "response.track(",
                      "response.sendFeedback(", "source.sendSuccess(",
                      "message.onSuccess().onSingle()", ".create(holder, newScore,",
                      "result = newScore;", "tracer.onReturn(", "source.handleError",
                      "TypedScoreIR.singletonFeedbackEnabled()"):
            self.assertIn(token, runtime)
        # The normal tracker remains available for the runtime A/B control.
        self.assertIn("TypedScoreIR.trackerFeedbackUsed()", runtime)
        self.assertIn("TypedScoreIR.singletonFeedbackUsed()", runtime)

    def test_feature_gate_and_native_counters_are_optin(self):
        irsrc = java("TypedScoreIR.java")
        cmds = java("ProbeCommands.java")
        self.assertIn('System.getenv("FC_TYPED_IR_SINGLETON_FEEDBACK")', irsrc)
        self.assertIn('System.getenv("FC_TYPED_IR_SINGLETON_FEEDBACK_TOGGLE")', irsrc)
        self.assertIn("private static volatile boolean singletonFeedbackRuntime", irsrc)
        self.assertIn('Commands.literal("fc_ir011_feedback")', cmds)
        self.assertIn("TypedScoreIR.toggleSingletonFeedback", cmds)
        self.assertIn("singleton_feedback_steps=", irsrc)
        self.assertIn("tracker_feedback_steps=", irsrc)

    def test_same_jvm_design_is_balanced_and_has_aa_control(self):
        self.assertEqual(ir.BOOTS, 2)
        for boot in range(ir.BOOTS):
            plan = ir.plan(boot)
            self.assertEqual(sum(row["kind"] == "singleton_vs_tracker" for row in plan),
                             ir.PAIRS_PER_BOOT)
            self.assertEqual(sum(row["kind"] == "tracker_aa" for row in plan),
                             ir.AA_PER_BOOT)
            orders = [row["order"] for row in plan
                      if row["kind"] == "singleton_vs_tracker"]
            self.assertEqual(orders.count("ABBA"), ir.PAIRS_PER_BOOT // 2)
            self.assertEqual(orders.count("BAAB"), ir.PAIRS_PER_BOOT // 2)
        study = (ROOT / "scripts/ci_typed_ir011.py").read_text()
        self.assertIn('"causal_general_speedup": False', study)
        self.assertIn('"production_promotion": False', study)
        self.assertIn('client.command("fc_ir011_feedback " + label)', study)

    def test_native_low_quota_and_function_result_consumer(self):
        study = (ROOT / "scripts/ci_typed_ir011.py").read_text()
        self.assertIn('"function_result_consumer"', study)
        self.assertIn('"feedback_enabled_" + name', study)
        self.assertIn('f"{name}_quota_{quota}"', study)
        self.assertIn('"singleton_feedback_steps"', study)
        self.assertIn('"tracker_feedback_steps"', study)
        self.assertIn('arm["cases"] != baseline', study)


if __name__ == "__main__":
    unittest.main()
